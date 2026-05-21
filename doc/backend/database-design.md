# Database Design — ParkReserve

**Engine:** PostgreSQL 16 (production and automated tests — no SQLite)
**Scope:** Subsystem F (Cloud Backend) persistence layer
**Status:** Describes the schema as it ships today (Alembic head = `20260513_01`).
**Aligns with:** `doc/proposal/proposal.md` §5.4 (bay state machine), §5.5 (reservation
rules + fee/penalty schedule), §5.6 (mock-payment service), and the implementation
in [backend/app/models/](../../backend/app/models/) + [backend/migrations/versions/](../../backend/migrations/versions/).

---

## 1. Design Goals

1. **Mirror, don't compute** — the per-bay state machine is owned by the Raspberry
   Pi (proposal §5.4). The backend's `parking_bays.state` column is a mirror,
   written only by [bay_service.apply_state](../../backend/app/services/bay_service.py).
   Reservation state is owned by the backend.
2. **Hard invariants in the DB, not application code** — at most one open
   reservation per bay, one unresolved conflict per bay, and one `pre_auth`
   payment per reservation are enforced by **partial unique indexes**, so a
   service-layer bug or concurrent insert cannot break them.
3. **Idempotent ingestion + idempotent payments** — every Pi event carries an
   `event_id` UUID; every payment action is keyed on a deterministic
   `idempotency_key` (e.g. `pre_auth:<reservation_id>`,
   `penalty_capture:<reservation_id>:<kind>`). Unique constraints collapse
   replays, sweeper retries, and user double-clicks to a single row, so users
   are never double-charged.
4. **Auditable** — every state transition writes a `bay_events` row (with
   `from_state`/`to_state`/`payload`); every payment action writes a `payments`
   row. The two tables together are the source of truth for proposal §7.3
   metrics.
5. **PostgreSQL-native** — `ENUM`, `JSONB`, `UUID`, `CITEXT`, partial indexes,
   `INSERT ... ON CONFLICT DO NOTHING`, deferrable FKs, and row-level triggers
   are all in use. Tests run on real Postgres so these are exercised.
6. **Small and focused** — nine tables, no partitioning. The demo expects
   < 1 M rows lifetime.

---

## 2. Schema Overview

```
 users ───┬───── licence_plates
          │
          │      ┌── conflicts ────┐
          │      │  (kind, plate   │
          │      │   evidence,     │
          │      │   image ref)    │
          │      │                 │
          ├───── reservations ────────── parking_bays
          │           │                       │
          │           ├── payments ──┐        │── bay_events
          │           │              │        │
          │           │  (pre_auth,  │        │── sensor_readings
          │           │   release,   │        │
          │           │   refund,    │        │
          │           │   penalty)   │        │
          │           │              │
          └───────────┴── mock_cards ┘
                         (mock-bank simulator)
```

### Nine tables

| Table | Purpose | Expected rows (demo) |
|-------|---------|---------------------|
| `users` | Dashboard identities; Argon2-hashed passwords; `role ∈ {user, admin}` | ~5 |
| `licence_plates` | Per-user bound plates (1–5); reservation matches against *any* bound plate | ~10 |
| `parking_bays` | One row per physical bay (3 for the demo, seeded by the initial migration) | 3 |
| `reservations` | Reservation lifecycle. **Creation is gated on a successful `pre_auth`** — the reservation row and its `payments` pre-auth row are written in the same transaction | ~10² |
| `bay_events` | Append-only audit log for every bay-state change, Pi event, and reservation lifecycle event | ~10³ |
| `sensor_readings` | Raw ultrasonic distance + occupied flag, one per `cloud/bay/<code>/state` message | ~10⁵ over a demo week |
| `conflicts` | Open/resolved `conflict_strong` / `conflict_weak` rows; strong rows carry `recognised_plate` + `evidence_image_url` retained 30 days | ~10 |
| `mock_cards` | **In-process mock-bank simulator** (proposal §5.6) — seeded test cards with number / CVV / expiry / holder / balance. Never reaches a real bank | ~10 |
| `payments` | Transactions ledger: `pre_auth` / `release` / `refund` / `penalty_capture`. Idempotent on `idempotency_key`. Filtering to `action='penalty_capture'` yields the user reliability log | ~10² |

> **No `breaches` table.** Penalty fees (proposal §5.5) replaced the old
> monthly-ban model: every breach is now a `payments` row with
> `action='penalty_capture'` and `penalty_kind` set. User reliability data
> is derived from `payments`. The monthly auto-suspension is gone; admins can
> still suspend users out-of-band.

---

## 3. Table definitions

All timestamps are `TIMESTAMPTZ` stored in UTC. User-visible primary keys
(reservations, conflicts, mock_cards, payments, users, licence_plates) use
UUIDv4 — easy to reference in MQTT payloads and idempotency keys. Hot
append-only rows (`sensor_readings`, `bay_events`) use `BIGSERIAL`.

The canonical SQL is the initial migration
[migrations/versions/20260421_01_initial.py](../../backend/migrations/versions/20260421_01_initial.py).
A follow-up migration
[20260513_01_conflict_resolution_user_cancelled.py](../../backend/migrations/versions/20260513_01_conflict_resolution_user_cancelled.py)
adds one enum value.

### 3.1 Enumerated types

```sql
CREATE TYPE user_role AS ENUM ('user', 'admin');

CREATE TYPE bay_state AS ENUM (
    'available',
    'reserved',
    'occupied',                -- casual parking, no active reservation
    'pending_check_in',        -- vehicle in reserved bay, awaiting check-in
    'reserved_checked_in',
    'conflict',                -- strong or weak; kind on `conflicts` row
    'offline'
);

CREATE TYPE reservation_status AS ENUM (
    'active',                  -- reserved, user not yet arrived
    'pending_check_in',        -- Pi reports vehicle; LPR did not auto-resolve
    'checked_in',              -- auto via LPR, or manual QR / button
    'completed',               -- vehicle drove off after check-in
    'cancelled',               -- clean cancel (≥15 min before arrival)
    'cancelled_late',          -- cancel <15 min before arrival (+late_cancel)
    'expired_no_show',         -- arrival + grace, bay still empty (+no_show)
    'in_conflict'              -- strong (no penalty) or weak (+weak_conflict);
                               -- kind lives on the matching `conflicts` row
);

CREATE TYPE check_in_mechanism AS ENUM (
    'auto_lpr',                -- Pi `auto_check_in` event (LPR plate match)
    'qr',                      -- user scanned the bay QR code
    'manual'                   -- user pressed the "I'm here" button
);

CREATE TYPE penalty_kind AS ENUM (
    'late_cancel',
    'no_show',
    'weak_conflict'            -- LPR did not auto-resolve and grace expired.
                               -- Strong-evidence conflicts are NEVER a user
                               -- penalty — those are facility incidents and
                               -- result in a refund, not a capture.
);

CREATE TYPE payment_action AS ENUM (
    'pre_auth',                -- deposit hold placed at booking
    'release',                 -- deposit voided: clean cancel, normal
                               -- completion, or post-penalty remainder
    'refund',                  -- strong-conflict victim: full remaining
                               -- deposit returned (admin path only)
    'penalty_capture'          -- late_cancel / no_show / weak_conflict
);
-- No `capture` action: per-time parking-fee capture is out of scope (proposal §5.6).

CREATE TYPE payment_status AS ENUM ('succeeded', 'failed', 'voided');

CREATE TYPE bay_event_kind AS ENUM (
    'state_changed',
    'sensor_online',
    'sensor_offline',
    'pending_check_in',
    'auto_check_in',           -- LPR plate match → server-side check-in
    'check_in_confirmed',      -- echo of successful user QR / manual check-in
    'conflict_strong',         -- LPR plate ∉ user's bound plates
    'conflict_weak',           -- LPR did not auto-resolve and grace expired
    'conflict_resolved',
    'no_show',
    'reservation_created',
    'reservation_cancelled',
    'reservation_completed',
    'plates_updated'           -- user changed bound plates during a live
                               -- reservation; new list republished to the Pi
);

CREATE TYPE conflict_kind AS ENUM ('strong', 'weak');

CREATE TYPE conflict_resolution AS ENUM (
    'user_arrived_and_checked_in',  -- only valid for kind='weak'
    'vehicle_left',
    'admin_resolved',
    'user_cancelled'                -- holder voluntarily cancelled while a
                                    -- strong conflict was open on their bay
                                    -- (no-fault refund path; added by
                                    --  migration 20260513_01)
);
```

The enum surface is also exported as Python `enum.Enum` subclasses in
[app/models/](../../backend/app/models/) and as Zod literal unions in
[frontend/src/schemas/](../../frontend/src/schemas/).

### 3.2 `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT NOT NULL,
    name            VARCHAR(120) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,     -- argon2id
    role            user_role NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE INDEX users_role_idx ON users(role) WHERE role = 'admin';
```

Notes:
- `CITEXT` makes email comparison case-insensitive without application-side
  lowercasing.
- `password_hash` is produced by [app/utils/security.py](../../backend/app/utils/security.py)
  using `argon2-cffi` defaults.
- Partial admin index keeps admin lookups small.

### 3.3 `licence_plates`

Each user binds 1–5 plates. *Any* currently-bound plate counts as a valid
match for that user's reservation; the Pi's LPR matcher consumes the list
each time a reservation is published or republished. Ownership is not
verified in the prototype (proposal §5.6).

```sql
CREATE TABLE licence_plates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plate           VARCHAR(16) NOT NULL,        -- normalised: uppercase, alphanumeric
    label           VARCHAR(64),                 -- "My car", optional
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT licence_plates_user_plate_unique UNIQUE (user_id, plate),
    CONSTRAINT licence_plates_format CHECK (plate ~ '^[A-Z0-9]{1,10}$')
);

CREATE INDEX licence_plates_user_idx  ON licence_plates(user_id);
CREATE INDEX licence_plates_plate_idx ON licence_plates(plate);
```

Five-plate cap is a row-level trigger because a plain CHECK cannot reference
an aggregate:

```sql
CREATE OR REPLACE FUNCTION licence_plates_max_per_user()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT COUNT(*) FROM licence_plates WHERE user_id = NEW.user_id) >= 5 THEN
        RAISE EXCEPTION 'plate_limit_exceeded'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER licence_plates_max_per_user_tg
BEFORE INSERT ON licence_plates
FOR EACH ROW EXECUTE FUNCTION licence_plates_max_per_user();
```

The same DDL is emitted by [app/models/licence_plate.py](../../backend/app/models/licence_plate.py)
via SQLAlchemy `event.listen(..., "after_create", ...)` so tests that build
schema with `Base.metadata.create_all()` still get the trigger.

Application-side, [app/utils/plate.py](../../backend/app/utils/plate.py)
normalises inputs (strips spaces / hyphens, uppercases) before insert, so
`"abc 123"` and `"ABC-123"` both end up as `ABC123`.

`plate` alone is **not** globally unique — different users may legitimately
register the same plate string. The Pi's matcher only ever sees one user's
list per active reservation, so cross-user collisions never enter the match
decision.

### 3.4 `parking_bays`

```sql
CREATE TABLE parking_bays (
    id                      SERIAL PRIMARY KEY,
    code                    VARCHAR(16) NOT NULL,        -- 'A1', 'A2', 'A3'
    label                   VARCHAR(64) NOT NULL,
    device_id               VARCHAR(64),                 -- ESP32 chip id
    state                   bay_state NOT NULL DEFAULT 'offline',
    last_distance_cm        NUMERIC(6,2),
    sensor_last_seen_at     TIMESTAMPTZ,
    current_reservation_id  UUID,                        -- FK set below
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT parking_bays_code_unique UNIQUE (code),
    CONSTRAINT parking_bays_device_unique UNIQUE (device_id)
);

CREATE INDEX parking_bays_state_idx ON parking_bays(state);
```

`state` is a **mirror** written only by
[`bay_service.apply_state`](../../backend/app/services/bay_service.py).
`current_reservation_id` is a denormalised pointer maintained by the
reservation service; the canonical truth is `reservations` + the partial
unique index in §3.5.

The initial migration also seeds three demo bays:

```sql
INSERT INTO parking_bays (code, label, device_id, state) VALUES
    ('A1', 'Bay A1', 'esp32-a1', 'offline'),
    ('A2', 'Bay A2', 'esp32-a2', 'offline'),
    ('A3', 'Bay A3', 'esp32-a3', 'offline');
```

#### Public state vs mirror state

[`ParkingBay.public_state()`](../../backend/app/models/bay.py) returns
`'reserved'` whenever the mirror is `'available'` *but* a reservation is
already attached (`current_reservation_id IS NOT NULL`). This avoids a brief
window after `reservation_service.create()` where the Pi has not yet pushed
its first state update; clients see `reserved` immediately, never a phantom
`available`. The API exposes both via [`BayOut.state` and `BayOut.mirror_state`](../../backend/app/schemas/bay.py).

### 3.5 `reservations`

```sql
CREATE TABLE reservations (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bay_id                      INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE RESTRICT,
    user_id                     UUID    NOT NULL REFERENCES users(id)        ON DELETE RESTRICT,
    status                      reservation_status NOT NULL DEFAULT 'active',
    expected_arrival_time       TIMESTAMPTZ NOT NULL,
    booked_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_in_grace_expires_at   TIMESTAMPTZ,
    checked_in_at               TIMESTAMPTZ,
    check_in_mechanism          check_in_mechanism,
    check_in_recognised_plate   VARCHAR(16),
    cancelled_at                TIMESTAMPTZ,
    completed_at                TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT reservations_booking_window CHECK (
        expected_arrival_time > booked_at
        AND expected_arrival_time <= booked_at + INTERVAL '1 hour'
    ),

    CONSTRAINT reservations_checked_in_has_ts CHECK (
        (status = 'checked_in' AND checked_in_at IS NOT NULL
                                AND check_in_mechanism IS NOT NULL)
        OR status <> 'checked_in'
    ),

    CONSTRAINT reservations_cancelled_has_ts CHECK (
        (status IN ('cancelled', 'cancelled_late') AND cancelled_at IS NOT NULL)
        OR status NOT IN ('cancelled', 'cancelled_late')
    ),

    -- Auto-LPR check-in always carries the recognised plate;
    -- QR / manual never do (image discarded immediately on auto check-in,
    -- proposal §5.5).
    CONSTRAINT reservations_check_in_plate_matches_mechanism CHECK (
        (check_in_mechanism = 'auto_lpr' AND check_in_recognised_plate IS NOT NULL)
        OR (check_in_mechanism IN ('qr','manual') AND check_in_recognised_plate IS NULL)
        OR (check_in_mechanism IS NULL              AND check_in_recognised_plate IS NULL)
    )
);

-- Double-book guard: at most one OPEN reservation per bay.
CREATE UNIQUE INDEX reservations_one_open_per_bay
    ON reservations(bay_id)
    WHERE status IN ('active', 'pending_check_in', 'checked_in');

CREATE INDEX reservations_user_idx     ON reservations(user_id, booked_at);
CREATE INDEX reservations_arrival_idx  ON reservations(expected_arrival_time)
    WHERE status = 'active';
CREATE INDEX reservations_check_in_grace_idx
    ON reservations(check_in_grace_expires_at)
    WHERE status = 'pending_check_in';
```

Key invariants and where they come from:

- **One open reservation per bay** — the partial unique index
  `reservations_one_open_per_bay`. The service translates the resulting
  `IntegrityError` into HTTP 409 `code=reservation_already_active`
  ([reservation_service.create](../../backend/app/services/reservation_service.py)).
- **1-hour booking window** — `reservations_booking_window` CHECK + the
  application-level `BOOKING_WINDOW_MINUTES` check in the service
  (configurable via env, default 60).
- **Single `in_conflict` status, two financial outcomes** — the `kind` lives
  on the matching `conflicts` row. Strong = facility incident, no user
  penalty, refund only via the explicit admin path. Weak = `weak_conflict`
  penalty capture + remainder release.

Once the reservation table exists, the deferred FK on `parking_bays` is
attached:

```sql
ALTER TABLE parking_bays
    ADD CONSTRAINT parking_bays_current_reservation_fk
    FOREIGN KEY (current_reservation_id) REFERENCES reservations(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
```

`DEFERRABLE INITIALLY DEFERRED` allows insert-reservation + update-bay
ordering to be either way inside the same transaction.

### 3.6 `mock_cards`

```sql
CREATE TABLE mock_cards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_number     VARCHAR(19)  NOT NULL UNIQUE,
    cvv             VARCHAR(4)   NOT NULL,
    holder_name     VARCHAR(120) NOT NULL,
    expiry_month    INTEGER      NOT NULL,
    expiry_year     INTEGER      NOT NULL,
    balance_cents   BIGINT       NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT mock_cards_number_format  CHECK (card_number ~ '^[0-9]{13,19}$'),
    CONSTRAINT mock_cards_cvv_format     CHECK (cvv ~ '^[0-9]{3,4}$'),
    CONSTRAINT mock_cards_expiry_month   CHECK (expiry_month BETWEEN 1 AND 12),
    CONSTRAINT mock_cards_expiry_year    CHECK (expiry_year BETWEEN 2024 AND 2099),
    CONSTRAINT mock_cards_balance_nonneg CHECK (balance_cents >= 0)
);

CREATE INDEX mock_cards_number_idx ON mock_cards(card_number);
```

This is the in-process mock bank (proposal §5.6).
[payment_service.validate_card](../../backend/app/services/payment_service.py)
performs `SELECT ... FOR UPDATE` on a row that matches all four of
`card_number`, `cvv`, `holder_name`, and `(expiry_month, expiry_year)` — that
row-level lock serialises concurrent bookings against the same card. The
service raises `PaymentError`:

- `card_invalid` — number/CVV/holder/expiry mismatch.
- `card_expired` — `(expiry_year, expiry_month)` strictly before today.
- `insufficient_funds` — `balance_cents < deposit_cents` (checked in
  `preauthorize`).

`balance_cents` is decremented on `pre_auth` and restored on
`release` / `refund`. Penalty captures leave the balance untouched (the
"spent" amount comes out of the deposit and is reflected in a smaller
`release` row).

[scripts/seed.py](../../backend/scripts/seed.py) loads a fixed set of
demo cards: varied balances + at least one expired card + at least one
empty-balance card so demos can exercise every payment-failure path.

### 3.7 `payments`

Transactions ledger. One row per payment action; every action is idempotent
on `idempotency_key`.

```sql
CREATE TABLE payments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id      UUID NOT NULL REFERENCES reservations(id) ON DELETE RESTRICT,
    user_id             UUID NOT NULL REFERENCES users(id)        ON DELETE RESTRICT,
    mock_card_id        UUID NOT NULL REFERENCES mock_cards(id)   ON DELETE RESTRICT,
    parent_payment_id   UUID REFERENCES payments(id) ON DELETE RESTRICT,
    action              payment_action NOT NULL,
    penalty_kind        penalty_kind,
    amount_cents        BIGINT  NOT NULL,
    status              payment_status NOT NULL DEFAULT 'succeeded',
    idempotency_key     VARCHAR(128) NOT NULL UNIQUE,
    source_event_id     UUID,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT payments_amount_nonneg CHECK (amount_cents >= 0),

    -- pre_auth has no parent; everything else points back at its pre_auth.
    CONSTRAINT payments_parent_required CHECK (
        (action = 'pre_auth' AND parent_payment_id IS NULL)
        OR (action <> 'pre_auth' AND parent_payment_id IS NOT NULL)
    ),

    -- penalty_kind ↔ action = 'penalty_capture'.
    CONSTRAINT payments_penalty_kind_only_for_penalty CHECK (
        (action = 'penalty_capture' AND penalty_kind IS NOT NULL)
        OR (action <> 'penalty_capture' AND penalty_kind IS NULL)
    )
);

CREATE INDEX payments_reservation_idx ON payments(reservation_id, occurred_at);
CREATE INDEX payments_user_time_idx   ON payments(user_id, occurred_at DESC);
CREATE INDEX payments_card_idx        ON payments(mock_card_id);

-- At most one pre_auth row per reservation. Service-layer query
-- `SELECT ... WHERE action='pre_auth'` is exactly-one-row by construction.
CREATE UNIQUE INDEX payments_one_preauth_per_reservation
    ON payments(reservation_id)
    WHERE action = 'pre_auth';

-- Optional `source_event_id` is unique when present — keeps event-driven
-- captures from doubling on MQTT replay.
CREATE UNIQUE INDEX payments_source_event_unique
    ON payments(source_event_id)
    WHERE source_event_id IS NOT NULL;
```

#### Idempotency keys

[payment_service](../../backend/app/services/payment_service.py) builds the
key deterministically per action:

| Action | Key |
|--------|-----|
| `pre_auth` | `pre_auth:<reservation_id>` |
| `release` | `release:<reservation_id>:<reason>` where `reason ∈ {clean_cancel, completed, remainder}` |
| `refund` | `refund:<reservation_id>` |
| `penalty_capture` | `penalty_capture:<reservation_id>:<penalty_kind>` |

Same reservation + same action ⇒ same key ⇒ same row.

#### Remaining-deposit accounting

`release`, `refund`, and `penalty_capture` all consult
`pre_auth.amount_cents − SUM(release|refund|penalty_capture.amount_cents)`.
When the remainder is `0`, the call is a no-op (returns `None`) — that is how
a no-show that captures the full deposit still safely emits a "release the
remainder" call without double-touching the card.

### 3.8 `sensor_readings`

```sql
CREATE TABLE sensor_readings (
    id           BIGSERIAL PRIMARY KEY,
    bay_id       INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE CASCADE,
    distance_cm  NUMERIC(6,2) NOT NULL,
    occupied     BOOLEAN NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL,
    received_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX sensor_readings_bay_time_idx ON sensor_readings(bay_id, recorded_at);
```

One row is appended on every `cloud/bay/<code>/state` message
(in [bay_service.apply_state](../../backend/app/services/bay_service.py)).
`occupied` is derived from the Pi-reported state — `true` for
`OCCUPIED / PENDING_CHECK_IN / RESERVED_CHECKED_IN / CONFLICT`, `false`
otherwise. No partitioning yet — the demo's expected volume sits inside one
table comfortably.

### 3.9 `bay_events`

Append-only audit log. Every state-changing path (MQTT ingest + REST writes
+ safety-net sweeper) writes exactly one row through
[event_service.record](../../backend/app/services/event_service.py).

```sql
CREATE TABLE bay_events (
    id              BIGSERIAL PRIMARY KEY,
    bay_id          INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE CASCADE,
    reservation_id  UUID REFERENCES reservations(id) ON DELETE SET NULL,
    kind            bay_event_kind NOT NULL,
    from_state      bay_state,
    to_state        bay_state,
    source_event_id UUID,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT bay_events_source_event_unique UNIQUE (source_event_id)
);

CREATE INDEX bay_events_bay_time_idx ON bay_events(bay_id, created_at);
CREATE INDEX bay_events_kind_idx      ON bay_events(kind);
```

`source_event_id` is the Pi-supplied UUID. Backend-originated audit rows
(reservation create/cancel/complete, plate updates, sweeper-synthesised
events) leave `source_event_id` NULL. For Pi events, `event_service.record`
uses `INSERT ... ON CONFLICT (source_event_id) DO NOTHING` so MQTT replays
after a reconnect collapse to a single row.

Admin browsing is supported by
[`GET /api/v1/bays/{code}/events`](../../backend/app/api/bays.py), backed by
the `(bay_id, created_at)` index.

### 3.10 `conflicts`

```sql
CREATE TABLE conflicts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bay_id              INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE CASCADE,
    reservation_id      UUID REFERENCES reservations(id) ON DELETE SET NULL,
    kind                conflict_kind NOT NULL,
    recognised_plate    VARCHAR(16),
    lpr_confidence      NUMERIC(3,2),
    evidence_image_url  TEXT,
    image_purge_at      TIMESTAMPTZ,
    source_event_id     UUID,
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    resolution          conflict_resolution,

    CONSTRAINT conflicts_source_event_unique UNIQUE (source_event_id),

    CONSTRAINT conflicts_resolution_consistent CHECK (
        (resolved_at IS NULL AND resolution IS NULL)
        OR (resolved_at IS NOT NULL AND resolution IS NOT NULL)
    ),

    -- Strong: must carry recognised_plate. Weak: must NOT carry plate/image.
    CONSTRAINT conflicts_evidence_matches_kind CHECK (
        (kind = 'strong' AND recognised_plate IS NOT NULL)
        OR (kind = 'weak'
            AND recognised_plate IS NULL
            AND evidence_image_url IS NULL)
    ),

    -- A strong conflict cannot be closed by a user check-in
    -- (the wrong vehicle is still physically in the bay).
    CONSTRAINT conflicts_strong_resolution_excludes_user_check_in CHECK (
        kind <> 'strong' OR resolution IS DISTINCT FROM 'user_arrived_and_checked_in'
    )
);

-- At most one unresolved conflict per bay.
CREATE UNIQUE INDEX conflicts_one_open_per_bay
    ON conflicts(bay_id)
    WHERE resolved_at IS NULL;

-- Purge job index — only scans rows that still have an image.
CREATE INDEX conflicts_image_purge_idx
    ON conflicts(image_purge_at)
    WHERE evidence_image_url IS NOT NULL AND image_purge_at IS NOT NULL;
```

Strong-conflict evidence images travel out-of-band over HTTPS to
[`POST /api/v1/internal/conflicts/evidence`](../../backend/app/api/conflicts.py).
The MQTT event and the HTTPS upload may arrive in either order:
[conflict_service.upsert_strong / attach_evidence_image](../../backend/app/services/conflict_service.py)
both upsert by `source_event_id`, filling in whichever fields the other
half has not yet supplied. `image_purge_at = detected_at + 30 days`
(configurable via `EVIDENCE_RETENTION_DAYS`).

[purge_evidence_images](../../backend/app/jobs/purge_evidence_images.py)
runs every `PURGE_INTERVAL_HOURS` (default 24) and calls
[conflict_service.purge_expired_evidence](../../backend/app/services/conflict_service.py),
which `SELECT ... FOR UPDATE SKIP LOCKED` rows past their purge time, deletes
the JPEG from disk, and nulls `evidence_image_url` / `image_purge_at`. The
conflict row itself is preserved for the audit trail.

#### Resolution semantics

| Resolution | Trigger |
|-----------|---------|
| `vehicle_left` | Pi reports the bay returning to `available` (or `reserved`) while a strong conflict was open. The reservation is **resumed**, not completed (`bay_service._maybe_restore_after_strong_conflict`). |
| `user_arrived_and_checked_in` | The holder performs QR / manual check-in while a *weak* conflict is open (`reservation_service.check_in`). |
| `admin_resolved` | Admin uses `POST /conflicts/{id}/resolve` or `reservation_service.admin_terminate`. |
| `user_cancelled` | Holder voluntarily cancels while their reservation has an open *strong* conflict (`reservation_service._cancel_no_fault_under_strong_conflict`). Full refund, no penalty. |

---

## 4. End-to-end invariants (DB-level)

| # | Invariant | Mechanism |
|---|-----------|-----------|
| I1 | At most one open reservation per bay | Partial unique `reservations_one_open_per_bay` |
| I2 | At most one unresolved conflict per bay | Partial unique `conflicts_one_open_per_bay` |
| I3 | At most one `pre_auth` payment per reservation | Partial unique `payments_one_preauth_per_reservation` |
| I4 | Reservation booked at most 1 h ahead | CHECK `reservations_booking_window` |
| I5 | `status='checked_in'` implies `checked_in_at` + `check_in_mechanism` set | CHECK `reservations_checked_in_has_ts` |
| I6 | `status IN (cancelled, cancelled_late)` implies `cancelled_at` set | CHECK `reservations_cancelled_has_ts` |
| I7 | Auto-LPR check-in carries a recognised plate; QR/manual never do | CHECK `reservations_check_in_plate_matches_mechanism` |
| I8 | Strong conflicts carry `recognised_plate`; weak conflicts carry no plate/image | CHECK `conflicts_evidence_matches_kind` |
| I9 | Strong conflicts cannot be closed by user check-in | CHECK `conflicts_strong_resolution_excludes_user_check_in` |
| I10 | Bay events idempotent on Pi-supplied `source_event_id` | UNIQUE `bay_events_source_event_unique` + `ON CONFLICT DO NOTHING` |
| I11 | Conflicts idempotent on `source_event_id` | UNIQUE `conflicts_source_event_unique` + upsert in service |
| I12 | Payments idempotent on action key | UNIQUE `payments.idempotency_key` + service-side existing-row check |
| I13 | Payments with a Pi `source_event_id` deduplicate | Partial unique `payments_source_event_unique` |
| I14 | `penalty_kind` set iff `action='penalty_capture'` | CHECK `payments_penalty_kind_only_for_penalty` |
| I15 | Non-`pre_auth` payments carry a `parent_payment_id`; `pre_auth` does not | CHECK `payments_parent_required` |
| I16 | Per-user plate cap (5) | Row-level trigger `licence_plates_max_per_user_tg` |

Every invariant is exercised by tests under
[backend/tests/](../../backend/tests/) — e.g. `test_api_reservations.py`,
`test_payment_service.py`, `test_event_handlers.py`.

---

## 5. Reservation × payments × conflicts state machine

The reservation status diagram is owned by
[reservation_service](../../backend/app/services/reservation_service.py)
and [event_dispatcher](../../backend/app/services/event_dispatcher.py).
The financial side-effects below are the *only* ones the system performs
(per row direction — release / refund / penalty_capture):

```
        cancel ≥15 min before arrival  ─► CANCELLED        (release: clean_cancel)
       /
ACTIVE ┼ cancel <15 min before arrival ─► CANCELLED_LATE   (penalty_capture: late_cancel
       │                                                    + release: remainder)
       │
       ├ pi:pending_check_in          ─► PENDING_CHECK_IN
       │   │
       │   ├ pi:auto_check_in         ─► CHECKED_IN        (no payment yet)
       │   │
       │   ├ user qr/manual           ─► CHECKED_IN        (no payment yet)
       │   │
       │   └ sweeper:conflict_weak    ─► IN_CONFLICT       (penalty_capture: weak_conflict
       │     (check-in grace expired                        + release: remainder)
       │      with no check-in)
       │
       ├ pi:conflict_strong           ─► ACTIVE (preserved)
       │     (LPR plate ∉ bound)         conflict_strong row opened; NO refund here
       │
       └ sweeper:no_show              ─► EXPIRED_NO_SHOW   (penalty_capture: no_show
         (arrival + grace,                                  + release: remainder)
          bay still empty,
          bay not in CONFLICT)

CHECKED_IN
       │
       └ bay state RESERVED_CHECKED_IN → AVAILABLE         ─► COMPLETED
         (vehicle left, inferred in bay_service)              (release: completed)

Open strong conflict → wrong vehicle drives away:
        bay state CONFLICT → {AVAILABLE, RESERVED, RESERVED_CHECKED_IN}
        conflict row resolves as `vehicle_left`; reservation resumes
        (rollbacks PENDING_CHECK_IN → ACTIVE if applicable). No payment.
```

Strong-conflict **refunds** only happen via the explicit admin path
([reservation_service.admin_terminate](../../backend/app/services/reservation_service.py))
or the holder's "cancel under strong conflict" no-fault branch. The raw
`conflict_strong` event preserves the reservation; the wrong vehicle may yet
drive away.

---

## 6. Derived queries (no separate table)

### 6.1 User reliability log

"Show me every breach a user has had" — derived, not stored:

```sql
SELECT id, reservation_id, penalty_kind, amount_cents, occurred_at
FROM payments
WHERE user_id = $1
  AND action = 'penalty_capture'
ORDER BY occurred_at DESC;
```

Index `payments_user_time_idx` covers this. The endpoint
[`GET /api/v1/users/me/payments`](../../backend/app/api/payments.py) returns
*all* the user's payments and the dashboard filters client-side.

### 6.2 Open conflicts (admin queue)

```sql
SELECT * FROM conflicts WHERE resolved_at IS NULL
ORDER BY detected_at DESC;
```

Backed by `conflicts_one_open_per_bay`. Served by
[`GET /api/v1/conflicts`](../../backend/app/api/conflicts.py) (admin only).

### 6.3 Audit-log replay

```sql
SELECT * FROM bay_events WHERE bay_id = $1
  AND created_at < $2  -- keyset cursor
ORDER BY created_at DESC, id DESC
LIMIT $3;
```

Served by [`GET /api/v1/bays/{code}/events`](../../backend/app/api/bays.py)
(admin only).

---

## 7. Indexes — recap

| Table | Index | Why |
|-------|-------|-----|
| `users` | `users_role_idx` (partial: admin) | Admin lookups |
| `licence_plates` | `licence_plates_user_idx`, `_plate_idx` | User-scoped queries + LPR debugging |
| `parking_bays` | `parking_bays_state_idx` | Available-bay listing |
| `reservations` | `reservations_one_open_per_bay` (partial unique) | Double-book guard |
| | `reservations_user_idx` | "My reservations" page |
| | `reservations_arrival_idx` (partial) | Sweeper's "active past arrival" scan |
| | `reservations_check_in_grace_idx` (partial) | Sweeper's "pending past grace" scan |
| `bay_events` | `bay_events_bay_time_idx` | Audit-log paging |
| | `bay_events_kind_idx` | Targeted event-kind queries |
| | `bay_events_source_event_unique` | Replay idempotency |
| `sensor_readings` | `sensor_readings_bay_time_idx` | Sensor history charts |
| `conflicts` | `conflicts_one_open_per_bay` (partial unique) | One-open guard |
| | `conflicts_image_purge_idx` (partial) | Purge job's scan |
| `mock_cards` | `mock_cards_number_idx` | Card lookup during `validate_card` |
| `payments` | `payments_reservation_idx` | Per-reservation receipt |
| | `payments_user_time_idx` | User payment history |
| | `payments_card_idx` | Card-scoped queries |
| | `payments_one_preauth_per_reservation` (partial unique) | Exactly-one pre-auth invariant |
| | `payments_source_event_unique` (partial unique) | Event-driven idempotency |
| | `idempotency_key` UNIQUE | Action-level idempotency |

---

## 8. Migrations

Bare Alembic. `flask-migrate` is not used.

```
backend/migrations/
├── env.py                                              # bootstraps Base.metadata
└── versions/
    ├── 20260421_01_initial.py                          # all 9 tables + enums + trigger + seed
    └── 20260513_01_conflict_resolution_user_cancelled.py  # adds enum value
```

`alembic.ini` lives in `backend/`. Operational commands:

```bash
make migrate                       # alembic upgrade head
make revision m="describe change"  # alembic revision --autogenerate
```

Both wrap `.venv/bin/alembic`. Production uses
[deploy/bootstrap.sh](../../backend/deploy/bootstrap.sh) to run
`alembic upgrade head` before the web service starts.

---

## 9. What's *not* in the database

- **Notifications.** WebSocket emissions are stateless; nothing is queued
  or persisted for retry. See [sockets/events.py](../../backend/app/sockets/events.py).
- **Evidence image bytes.** Stored on local disk under
  `EVIDENCE_STORAGE_PATH` (default `/var/lib/parkreserve/evidence`).
  `conflicts.evidence_image_url` holds the path; the bytes themselves
  never enter Postgres.
- **MQTT-side retain or LWT.** The backend's publisher and inbound client
  do not use retained messages; resync is requested on each reconnect via
  `cloud/system/resync`. See `pi-side-change-notes.md` §10.
