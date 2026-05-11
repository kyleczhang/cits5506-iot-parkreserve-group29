# Pi-Side Change Notes for Reservation Lifecycle Sync

This note is for the Raspberry Pi / gateway implementation. It explains the backend-side design changes that affect Pi behavior, so the Pi code can be updated against the current MQTT contract.

Related references:

- [pi-integration-plan.md](./pi-integration-plan.md)
- [backend-implementation-plan.md](./backend-implementation-plan.md)
- [asyncapi.yaml](./asyncapi.yaml)
- [topics.py](../../backend/app/mqtt/topics.py)

## 1. Why this changed

Previously, the backend updated reservation state in its own database for some timeout and completion paths, but did **not** notify the Pi. That left the Pi's local reservation cache stale.

The problematic cases were:

- `no_show`
- `conflict_weak`
- `completed`

As a result, the Pi could continue treating a bay as reserved even after the reservation had already ended in the cloud.

The backend now sends explicit reservation-lifecycle commands back to the Pi so that Pi-local cache and cloud reservation state stay aligned.

## 2. High-level ownership model

The architecture boundary is now:

- The **Pi owns the physical bay state machine**.
- The **backend owns reservation business timing** such as arrival grace and check-in grace.

That means:

- The Pi still publishes physical events such as vehicle arrival, LPR success, sensor online/offline, and so on.
- The Pi does **not** decide when `no_show` or `conflict_weak` should happen.
- The backend reconcile job decides those timeout-based transitions and then sends commands to the Pi.

Important consequence:

- The Pi should **not** implement its own `ARRIVAL_GRACE_MINUTES` or `CHECK_IN_GRACE_MINUTES` timer logic for reservation business transitions.

## 3. MQTT contract changes

### 3.1 Pi -> backend event enum is now narrower

The Pi may publish only these event values on `cloud/bay/<code>/event`:

```text
auto_check_in
pending_check_in
check_in_confirmed
conflict_strong
sensor_online
sensor_offline
```

The Pi must **not** publish:

- `conflict_weak`
- `no_show`

Those are now backend-internal synthesized events.

If the Pi publishes them anyway, the backend will reject them at schema validation time.

### 3.2 Backend -> Pi reservation command enum is now wider

The backend can now publish these actions on `cloud/bay/<code>/reservation`:

```text
create
cancel
check_in
update_plates
release
expire_check_in
```

The new ones are:

- `release`
- `expire_check_in`

### 3.3 `release` adds a `reason`

When `action="release"`, the payload includes:

```text
reason = no_show | completed | abandoned | admin_override
```

`reason` is required only for `release`.

## 4. New command semantics

### 4.1 `release`

Purpose:

- The reservation is no longer active from the backend's point of view.
- The Pi must stop treating it as a live reservation.

Pi behavior on `action="release"`:

1. Remove the local reservation cache for that bay / reservation.
2. Clear reservation-related warning state.
3. Immediately recompute local bay state from the **current** sensor reading.

Required recompute rule:

- sensor empty -> `available`
- sensor occupied -> `conflict`

Do **not** wait for the next sensor edge before recomputing.

This immediate recompute matters because the backend may already have finalized the reservation lifecycle, and waiting for another sensor change can leave the Pi stuck in a stale local state.

### 4.2 `expire_check_in`

Purpose:

- A vehicle was detected earlier.
- LPR did not auto-resolve the reservation.
- The backend's check-in grace window expired.
- The reservation is **not** finished yet, but the Pi should escalate the bay to weak-conflict behavior.

Pi behavior on `action="expire_check_in"`:

1. Keep the local reservation cache.
2. Move the local bay state to `conflict`.
3. Enable weak-conflict alert behavior locally.
4. Keep accepting a later `check_in` command for the same reservation.

Why cache must be kept:

- The backend still allows a late **manual** check-in for weak conflict.
- If the user later checks in successfully, the backend will send `action="check_in"` and the Pi should clear the alert and move back to `reserved_checked_in`.

## 5. Meaning of each `release.reason`

### 5.1 `no_show`

Meaning:

- The user never arrived in time.
- The backend expired the reservation as a no-show.

Expected Pi result:

- Drop reservation cache.
- Recompute local state.
- In practice this should normally become `available`, because the bay was empty when `no_show` was decided.

### 5.2 `completed`

Meaning:

- The reservation had been successfully checked in.
- The vehicle later left.
- The backend inferred that the reservation ended normally.

Expected Pi result:

- Drop reservation cache.
- Recompute local state.
- In practice this should normally become `available`.

### 5.3 `abandoned`

Meaning:

- The reservation was not completed normally.
- A vehicle may have arrived earlier, but the session did not end in a clean checked-in completion.
- The backend decided the reservation should be released anyway.

Typical examples:

- `pending_check_in -> available`
- `conflict -> available`

Expected Pi result:

- Drop reservation cache.
- Recompute local state immediately.
- If the sensor is still occupied at that moment, fall back to local `conflict`, not `available`.

### 5.4 `admin_override`

Meaning:

- Reserved for future manual operator actions.

For now, Pi can treat it with the same runtime behavior as any other `release`: clear reservation cache and recompute from the sensor.

## 6. Required Pi-side state transitions

The following backend -> Pi sequences are now expected.

### 6.1 Weak conflict timeout path

1. Pi detects vehicle in reserved bay, but cannot auto-match the reservation.
2. Pi publishes `pending_check_in`.
3. Backend grace expires later.
4. Backend sends `expire_check_in`.
5. Pi moves local bay state to `conflict` and raises alert.
6. If the user later checks in manually, backend sends `check_in`.
7. Pi clears alert and moves to `reserved_checked_in`.

### 6.2 No-show path

1. Reservation exists, but no vehicle arrives in time.
2. Backend reconcile job decides `no_show`.
3. Backend sends `release(reason="no_show")`.
4. Pi removes local reservation cache and recomputes state.

### 6.3 Normal completion path

1. Reservation is checked in.
2. Vehicle leaves and Pi reports bay state back to `available`.
3. Backend infers `completed`.
4. Backend sends `release(reason="completed")`.
5. Pi removes local reservation cache and keeps bay `available`.

### 6.4 Abandoned path

1. Bay was in `pending_check_in` or `conflict`.
2. Vehicle leaves or the backend otherwise decides the reservation should end.
3. Backend sends `release(reason="abandoned")`.
4. Pi removes local reservation cache and recomputes state immediately.

## 7. What the Pi does not need to do

The Pi does **not** need to:

- track arrival grace countdowns for reservation business decisions
- decide `no_show`
- decide `conflict_weak`
- publish `no_show`
- publish `conflict_weak`

Those are now backend responsibilities.

## 8. Recommended implementation checklist for the Pi team

1. Extend reservation command parsing to accept:
   - `release`
   - `expire_check_in`
2. Extend `release` parsing to read `reason`.
3. Remove any Pi logic that publishes `conflict_weak` or `no_show`.
4. Implement immediate local recompute on `release`.
5. Keep reservation cache on `expire_check_in`.
6. Ensure a later `check_in` can clear weak-conflict alert state.
7. Update debug logs so outbound commands are easy to inspect during testing.

## 9. Suggested integration tests on the Pi side

### 9.1 Weak conflict late check-in

Verify this sequence:

1. Pi publishes `pending_check_in`.
2. Backend later sends `expire_check_in`.
3. Pi enters `conflict`.
4. User performs manual check-in through the backend API.
5. Backend sends `check_in`.
6. Pi exits alert state and moves to `reserved_checked_in`.

### 9.2 No-show cleanup

Verify this sequence:

1. Reservation exists on Pi.
2. No vehicle arrives.
3. Backend sends `release(reason="no_show")`.
4. Pi deletes reservation cache and keeps the bay `available`.

### 9.3 Normal completion cleanup

Verify this sequence:

1. Vehicle arrives and the reservation is checked in.
2. Vehicle leaves.
3. Backend sends `release(reason="completed")`.
4. Pi deletes reservation cache.

### 9.4 Abandoned cleanup

Verify this sequence:

1. Bay enters `pending_check_in` or `conflict`.
2. Backend sends `release(reason="abandoned")`.
3. Pi deletes reservation cache and recomputes correctly from current sensor occupancy.

## 10. Current limitation to be aware of

If the Pi is offline when the backend sends `release` or `expire_check_in`, delivery is not fully guaranteed by a persistent MQTT session in the current dev setup.

So for now:

- the Pi should still support `cloud/system/resync`
- the Pi should replay current bay state after resync
- the Pi team should expect timeout-driven transitions to converge after reconnect, not necessarily during the disconnection window

That is a current system limitation, not a Pi-only bug.
