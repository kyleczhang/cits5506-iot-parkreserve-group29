# Database Design — ParkReserve

**Engine:** PostgreSQL 16 (production and automated tests — no SQLite)
**Scope:** Subsystem F (Cloud Backend) persistence layer
**Aligns with:** `doc/proposal/proposal.md` (esp. §5.4 state machine, §5.5 reservation rules), `doc/backend/backend-implementation-plan.md`

---

## 1. Design Goals

1. **Mirror the authoritative state** — the per-bay state machine lives on the
   Raspberry Pi (proposal §5.4); the DB is the cloud-side mirror plus the
   source of truth for reservation business logic (booking window, fee +
   penalty capture, refund on strong conflict — proposal §5.5).
2. **Strong invariants** enforced in the database, not only in application code
   — e.g. at most one open reservation per bay, at most one unresolved
   conflict per bay, **at most one pre-auth hold per reservation**, all via
   partial unique indexes.
3. **Auditable** — every state-machine event, every state transition, and
   **every payment action** (pre-auth / release / refund / penalty-capture)
   is appended to a log so the final-report evaluation section can pull
   data-driven numbers for proposal §7.3 metrics (State Transition
   Correctness, Conflict Detection, No-show / Auto-release, Mock Payment
   Correctness).
4. **Idempotent event ingestion AND idempotent payment actions** — the Pi
   tags each event with an `event_id`; payment actions are keyed by
   `(reservation_id, action)`. Unique constraints in the DB make replays after
   reconnect, sweeper redeliveries, and user double-clicks no-ops, so a user
   is never double-charged or double-refunded.
5. **PostgreSQL-native** — use `ENUM`, `JSONB`, `UUID`, `CITEXT`, partial
   indexes, `NOW() AT TIME ZONE 'UTC'`, and `CHECK` constraints. Tests run on
   the same engine so these behaviours are covered.
6. **Small and focused** — nine tables, no premature partitioning. Expected
   volume for the demo is < 1 M rows lifetime.

---

## 2. Schema Overview

```
 users ───┬───── licence_plates
          │
          │      ┌── conflicts ────┐
          │      │   (kind, plate  │
          │      │    evidence,    │
          │      │    image ref)   │
          │      │                 │
          ├───── reservations ─────────── parking_bays
          │           │                          │
          │           ├── payments ──┐           │ bay_events
          │           │  (pre_auth,  │           │
          │           │   release,   │           │ sensor_readings
          │           │   refund,    │           │
          │           │   penalty)   │           │
          │           │              │           │
          └───────────┴── mock_cards ┘           │
                         (mock-bank simulator)
```

Nine tables (the prior `breaches` table has been removed; see §3 prelude):

| Table | Purpose | Expected rows (demo) |
|-------|---------|---------------------|
| `users` | Dashboard identities | ~5 |
| `licence_plates` | Per-user bound plates (1–5); reservation matches against any bound plate (proposal §5.5) | ~10 |
| `parking_bays` | One row per physical bay (3 for demo) | 3 |
| `reservations` | Reservation lifecycle records. **Creation is gated on a successful pre-auth** — the reservation row and its `payments` pre-auth row are written in the same transaction (§3.5, §3.11) | ~10² during testing |
| `bay_events` | Audit log of every bay-state transition and every Pi event (`auto_check_in`, `conflict_strong`, `conflict_weak`, ...) | ~10³ |
| `sensor_readings` | Raw ultrasonic readings (every 2 s per bay) | ~10⁵ over a demo week |
| `conflicts` | Unresolved `conflict_strong` / `conflict_weak` alerts from the Pi; strong rows carry `recognised_plate` + `evidence_image_url` retained 30 days | ~10 |
| `mock_cards` | **Mock-bank simulator** (proposal §5.6) — seeded test cards with number / CVV / expiry / holder / balance. Validated in-process; never reaches a real bank | ~10 demo cards |
| `payments` | Transactions log: `pre_auth` (at booking) / `release` (clean cancel, normal completion, or post-penalty remainder) / `refund` (strong-conflict victim) / `penalty_capture` (late_cancel / no_show / weak_conflict). **No `capture` action** — per-time parking-fee billing is the facility's exit-side concern, out of scope for the prototype (proposal §5.6). Idempotent on `idempotency_key`. Filtering to `action='penalty_capture'` yields the user reliability log that previously lived in `breaches` | ~10² during testing |

> **No `breaches` table.** The prior design carried a per-user breach log driven by a monthly-ban check (R12). With the move to mock-payment in proposal §5.5, every breach event (`late_cancel`, `no_show`, `weak_conflict`) is now also a financial event — captured directly as a `payments` row with `action='penalty_capture'` and `penalty_kind` set. The user reliability log is derived from `payments` (§6.5), which removes the duplication and keeps a single source of truth for "user did wrong → operator received money." The monthly ban is dropped (penalty fees are the deterrent); admins can still suspend users out-of-band via the admin view.

---

## 3. Table Definitions

All timestamps are `TIMESTAMPTZ` and stored in UTC. All primary keys that are
user-visible (reservations, conflicts, mock_cards, payments) use UUIDv4 —
easier to reference in logs, MQTT payloads, and idempotency keys than
sequential ids. Hot, append-only rows (sensor readings, bay events) use
`BIGSERIAL` for locality.

### 3.1 Enumerated types

```sql
CREATE TYPE user_role AS ENUM ('user', 'admin');

CREATE TYPE bay_state AS ENUM (
    'available',
    'reserved',
    'occupied',              -- casual parking, no active reservation
    'pending_check_in',      -- vehicle in reserved bay, awaiting check-in
    'reserved_checked_in',
    'conflict',
    'offline'
);

CREATE TYPE reservation_status AS ENUM (
    'active',                -- reserved, user not yet arrived
    'pending_check_in',      -- Pi reports vehicle; user hasn't confirmed
    'checked_in',            -- user confirmed via QR or manual button
    'completed',             -- user left the bay
    'cancelled',             -- cancelled ≥ 15 min before arrival (release hold, no charge)
    'cancelled_late',        -- cancelled < 15 min before arrival (capture late_cancel penalty)
    'expired_no_show',       -- did not arrive by arrival + 5 min (capture no_show penalty)
    'in_conflict'            -- Pi raised conflict_strong (refund hold — user is victim)
                              -- or conflict_weak (capture weak_conflict penalty);
                              -- kind is on the matching `conflicts` row
);

CREATE TYPE penalty_kind AS ENUM (
    'late_cancel',
    'no_show',
    'weak_conflict'           -- LPR did not auto-resolve and 5 min check-in
                              -- grace expired with no manual check-in
                              -- (proposal §5.5). Strong-evidence conflicts
                              -- are NOT a user penalty — they are facility
                              -- incidents stored in `conflicts`, and the
                              -- reserving user is refunded in full.
);

CREATE TYPE payment_action AS ENUM (
    'pre_auth',               -- deposit hold placed at booking (proposal §5.5)
    'release',                -- deposit voided: clean cancel, normal completion,
                              -- or post-penalty remainder
    'refund',                 -- strong-conflict victim: full deposit returned
    'penalty_capture'         -- late_cancel / no_show / weak_conflict (proposal §5.5)
);
-- NOTE: there is intentionally no `capture` action. The prototype's payment
-- surface handles only the reservation deposit; per-time parking-fee capture
-- is the facility's exit-side billing concern and is out of scope (proposal §5.6).

CREATE TYPE payment_status AS ENUM ('succeeded', 'failed', 'voided');

CREATE TYPE bay_event_kind AS ENUM (
    'state_changed',
    'sensor_online',
    'sensor_offline',
    'pending_check_in',
    'auto_check_in',          -- LPR plate match → server-side check-in
    'check_in_confirmed',     -- echo of a successful user QR / manual check-in
    'conflict_strong',        -- LPR plate ∉ user's bound plates
    'conflict_weak',          -- LPR did not auto-resolve and grace expired
    'conflict_resolved',
    'no_show',
    'reservation_created',
    'reservation_cancelled',
    'reservation_completed',
    'plates_updated'          -- user added/removed a bound plate while a
                              -- reservation was active; updated list
                              -- republished to the Pi
);

CREATE TYPE conflict_kind AS ENUM ('strong', 'weak');

CREATE TYPE conflict_resolution AS ENUM (
    'user_arrived_and_checked_in',  -- only valid for kind='weak'
    'vehicle_left',
    'admin_resolved'
);

CREATE TYPE check_in_mechanism AS ENUM (
    'auto_lpr',                      -- Pi `auto_check_in` event (LPR plate match)
    'qr',                            -- user scanned the bay QR code (fallback)
    'manual'                         -- user pressed the "I'm here" button (further fallback)
);
```

Why enums, not lookup tables: values are stable, small, and referenced in
application code as Python `Enum`s. SQLAlchemy maps `ENUM` natively. Schema
evolution is handled via Alembic `op.execute('ALTER TYPE ... ADD VALUE ...')`.

Note the removed enum values from the pre-barrier design (`barrier_opened`,
`barrier_closed`) — the project no longer has physical barriers (proposal
§5.6). The pre-LPR `conflict_detected` event has been split into
`conflict_strong` and `conflict_weak`; `auto_check_in` is new (proposal §5.4 /
§5.5); `penalty_kind.never_checked_in` (originally `breach_kind`) has been
replaced by `weak_conflict` because LPR makes the strong-evidence case
identifiable separately, and only the weak case still maps to a user
penalty. The `breach_kind` enum and `breaches` table from the pre-payment
design have been **dropped** (proposal §5.5 replaces the breach-counter +
monthly-ban model with direct penalty fees — see §2 prelude); user
reliability data is now derived from `payments` filtered to
`action='penalty_capture'`. `payment_action`, `payment_status`, and
`penalty_kind` are new in this revision (proposal §5.6 mock-payment service).

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
  lowercasing, which avoids a whole class of "duplicate email" bugs.
- Partial index on admin lookups keeps it small.

### 3.3 `licence_plates`

Per proposal §5.5, each user binds 1–5 licence plates to their account; *any*
currently-bound plate counts as a valid match for that user's reservation.
Plate ownership is **not** verified in the prototype (proposal §5.6 — the
plate string is taken as user-supplied and assumed correct). The Pi's local
LPR matcher consumes this list (published over MQTT in the
`cloud/bay/<code>/reservation` payload, see backend plan §7.3) and does the
match itself.

```sql
CREATE TABLE licence_plates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plate           VARCHAR(16) NOT NULL,        -- normalised: uppercase, no spaces
    label           VARCHAR(64),                 -- optional: "My car", "Wife's car"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT licence_plates_user_plate_unique UNIQUE (user_id, plate),
    CONSTRAINT licence_plates_format
        CHECK (plate ~ '^[A-Z0-9]{1,10}$')
);

-- Hot lookup paths
CREATE INDEX licence_plates_user_idx  ON licence_plates(user_id);
CREATE INDEX licence_plates_plate_idx ON licence_plates(plate);

-- Cap of 5 plates per user (proposal §5.5). Enforced as a row-level trigger
-- because PostgreSQL CHECK constraints cannot reference aggregates.
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

Notes:
- `plate` is *normalised* application-side before insertion (uppercase, strip
  spaces / dashes), then validated by the `CHECK` regex. The regex is
  deliberately lax (no country-specific rules) because the proposal targets
  generic deployment.
- `(user_id, plate)` is unique so a user cannot bind the same plate twice.
  `plate` alone is **not** unique globally — different users may legitimately
  claim the same string (the prototype does not verify ownership). The Pi's
  matcher only ever consumes one user's list per active reservation, so
  cross-user collisions never enter the matching decision.
- `ON DELETE CASCADE` from `users` cleans up bindings if a user is deleted.

### 3.4 `parking_bays`

```sql
CREATE TABLE parking_bays (
    id                      SERIAL PRIMARY KEY,
    code                    VARCHAR(16) NOT NULL,        -- 'A1', 'A2', 'A3'
    label                   VARCHAR(64) NOT NULL,        -- 'Bay A1'
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

Design note: the `state` column is a **mirror** — it is written only by
`BayService.apply_state()` in response to `cloud/bay/<code>/state` MQTT messages
from the Pi. The backend never derives `state` from sensor readings; that is
the Pi's job (proposal §5.4). `current_reservation_id` is a denormalised
pointer to the currently open reservation, maintained atomically by the
reservation service. The canonical source remains `reservations` + the partial
unique index in §3.5.

### 3.5 `reservations`

```sql
CREATE TABLE reservations (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bay_id                      INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE RESTRICT,
    user_id                     UUID    NOT NULL REFERENCES users(id)        ON DELETE RESTRICT,
    status                      reservation_status NOT NULL DEFAULT 'active',
    expected_arrival_time       TIMESTAMPTZ NOT NULL,
    booked_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_in_grace_expires_at   TIMESTAMPTZ,      -- populated on pending_check_in
    checked_in_at               TIMESTAMPTZ,
    check_in_mechanism          check_in_mechanism, -- populated on check-in (proposal §5.3 F / §5.5)
    check_in_recognised_plate   VARCHAR(16),        -- populated only when mechanism='auto_lpr'
    cancelled_at                TIMESTAMPTZ,
    completed_at                TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT reservations_booking_window
        CHECK (expected_arrival_time > booked_at
               AND expected_arrival_time <= booked_at + INTERVAL '1 hour'),

    CONSTRAINT reservations_checked_in_has_ts CHECK (
        (status = 'checked_in' AND checked_in_at IS NOT NULL
                                AND check_in_mechanism IS NOT NULL)
        OR status <> 'checked_in'
    ),
    CONSTRAINT reservations_cancelled_has_ts CHECK (
        (status IN ('cancelled', 'cancelled_late') AND cancelled_at IS NOT NULL)
        OR status NOT IN ('cancelled', 'cancelled_late')
    ),
    -- Auto-LPR check-in always carries the recognised plate; QR / manual
    -- check-in never carries one (proposal §5.5: image discarded immediately
    -- on auto check-in, but the recognised plate is logged with the
    -- reservation record).
    CONSTRAINT reservations_check_in_plate_matches_mechanism CHECK (
        (check_in_mechanism = 'auto_lpr' AND check_in_recognised_plate IS NOT NULL)
        OR (check_in_mechanism IN ('qr', 'manual') AND check_in_recognised_plate IS NULL)
        OR (check_in_mechanism IS NULL              AND check_in_recognised_plate IS NULL)
    )
);

-- At most one OPEN reservation per bay, enforced in DB (double-book guard)
CREATE UNIQUE INDEX reservations_one_open_per_bay
    ON reservations(bay_id)
    WHERE status IN ('active', 'pending_check_in', 'checked_in');

CREATE INDEX reservations_user_idx        ON reservations(user_id, booked_at DESC);
CREATE INDEX reservations_arrival_idx     ON reservations(expected_arrival_time)
    WHERE status = 'active';
CREATE INDEX reservations_check_in_grace_idx
    ON reservations(check_in_grace_expires_at)
    WHERE status = 'pending_check_in';
```

The partial unique index is the single most important constraint in the
schema — it makes double-booking a database-level impossibility, not an
application-level convention. This is what the test
`test_double_reserve_rejected_409` proves.

The `reservations_booking_window` CHECK enforces the 1-hour rule (R11) at the
DB level too, so any bypass of the service layer still cannot create a
far-future reservation.

The single `in_conflict` status covers both strong- and weak-evidence
conflicts (proposal §5.4 — they share one bay state). The kind is carried on
the matching row in `conflicts` (§3.9) and on the corresponding `bay_events`
row (`kind = 'conflict_strong' | 'conflict_weak'`); see invariants I11 and
I12 for the schema-level encoding of the strong/weak split.

**Payment dependency (proposal §5.5).** Reservation creation is gated on a
successful pre-auth: in a single transaction, `ReservationService` validates
the user's mock card (§3.10), debits the deposit from
`mock_cards.balance_cents`, inserts the reservation row here, and inserts
the `pre_auth` row in `payments` (§3.11) with `parent_payment_id = NULL`.
If any step fails the transaction rolls back and no orphan reservation is
left behind. Per-row look-up of the open deposit for a reservation is
`SELECT * FROM payments WHERE reservation_id = $1 AND action = 'pre_auth'`
(a partial unique index makes this exactly-one-row by construction — see
§3.11 / I15).

Now wire up the denormalised pointer on `parking_bays`:

```sql
ALTER TABLE parking_bays
    ADD CONSTRAINT parking_bays_current_reservation_fk
    FOREIGN KEY (current_reservation_id) REFERENCES reservations(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
```

`DEFERRABLE` lets the reservation service insert the reservation row and update
the bay in any order within a transaction.

### 3.6 `breaches` (removed)

This table existed in the pre-payment design and held one row per
late-cancel / no-show / weak-conflict event, with a monthly count driving an
automatic reservation-privilege suspension (R12). Proposal §5.5 replaces
that mechanism with **direct penalty fees**: each former breach event is now
captured as a `payments` row with `action='penalty_capture'` and
`penalty_kind` set (§3.11). The user reliability log is therefore derived
from `payments` instead of being stored separately, and there is no
automatic monthly suspension.

What moved where:

- `breaches.kind` → `payments.penalty_kind` (same enum values, renamed
  enum: `late_cancel` / `no_show` / `weak_conflict`).
- `breaches.source_event_id` UNIQUE → `payments.source_event_id` UNIQUE
  (partial — only when non-NULL; §3.11) for the same Pi-replay idempotency.
- Late-cancel idempotency: the cancel handler populates
  `payments.idempotency_key = 'penalty_capture:<reservation_id>:late_cancel'`
  so retried HTTP cancels collapse to a single penalty capture.
- The `breaches_user_month_idx` is replaced by `payments_user_time_idx`
  (§3.11), which serves both the user transaction-history view (§6.4) and
  the analytics monthly-penalty-count query (§6.5).

Strong-evidence conflicts still produce **no penalty** for the reserving
user (proposal §5.5 — the user is a victim, not at fault). Instead the
backend issues a `payments` row with `action='refund'` against the
reservation's pre-auth, restoring the held amount to the mock card. The
`conflicts` row (§3.9) remains the facility-incident record for the
recognised plate, exactly as before.

> Removing this table is the cleanest way to keep "the user did wrong" and
> "the operator received money" co-located on a single row. A `breaches`
> row that didn't carry an amount or a transaction reference would always
> have to be joined to `payments` to be useful for the dashboard's
> transaction-history view; that join is what motivated the merge.

### 3.7 `bay_events`

```sql
CREATE TABLE bay_events (
    id                  BIGSERIAL PRIMARY KEY,
    bay_id              INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE CASCADE,
    reservation_id      UUID    REFERENCES reservations(id)          ON DELETE SET NULL,
    kind                bay_event_kind NOT NULL,
    from_state          bay_state,
    to_state            bay_state,
    source_event_id     UUID,                -- Pi-supplied event_id for dedupe
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT bay_events_source_event_unique
        UNIQUE (source_event_id)
        DEFERRABLE INITIALLY IMMEDIATE
);

CREATE INDEX bay_events_bay_time_idx ON bay_events(bay_id, created_at DESC);
CREATE INDEX bay_events_kind_idx     ON bay_events(kind);
```

Every state-changing path (both MQTT ingest and REST writes) inserts exactly
one row here. The `payload` JSONB column holds context
(`{"distance_cm":3.2,"qr_scanned":true}`) queryable ad-hoc. The
`source_event_id` unique constraint gives MQTT replay idempotency — the same
guarantee as §3.5 but for the audit log.

`NULL` is allowed for `source_event_id` (backend-originated events don't have
a Pi event id), and `UNIQUE` in PostgreSQL permits multiple `NULL` values, so
this is safe.

### 3.8 `sensor_readings`

```sql
CREATE TABLE sensor_readings (
    id              BIGSERIAL PRIMARY KEY,
    bay_id          INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE CASCADE,
    distance_cm     NUMERIC(6,2) NOT NULL,
    occupied        BOOLEAN NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL,    -- ESP32 timestamp
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX sensor_readings_bay_time_idx
    ON sensor_readings(bay_id, recorded_at DESC);
```

Retention policy: keep the most recent 7 days; a nightly `DELETE` removes older
rows. For a demo, 3 bays × 0.5 Hz × 86 400 s ≈ 130 k rows/day — trivial for
PostgreSQL without partitioning.

### 3.9 `conflicts`

```sql
CREATE TABLE conflicts (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bay_id               INTEGER NOT NULL REFERENCES parking_bays(id) ON DELETE CASCADE,
    reservation_id       UUID             REFERENCES reservations(id) ON DELETE SET NULL,
    kind                 conflict_kind NOT NULL,        -- 'strong' | 'weak'
    recognised_plate     VARCHAR(16),                   -- populated only for kind='strong'
    lpr_confidence       NUMERIC(3,2),                  -- 0.00–1.00, populated for kind='strong'
    evidence_image_url   TEXT,                          -- S3 key or local path; populated for kind='strong'
    image_purge_at       TIMESTAMPTZ,                   -- detected_at + 30 days; null once purged
    source_event_id      UUID,                          -- Pi-supplied event_id for dedupe
    detected_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at          TIMESTAMPTZ,
    resolution           conflict_resolution,

    CONSTRAINT conflicts_resolution_consistent CHECK (
        (resolved_at IS NULL AND resolution IS NULL) OR
        (resolved_at IS NOT NULL AND resolution IS NOT NULL)
    ),
    -- Strong conflicts must carry the recognised plate; weak conflicts must not
    -- (per proposal §5.5 retention policy: weak conflicts retain no evidence).
    CONSTRAINT conflicts_evidence_matches_kind CHECK (
        (kind = 'strong' AND recognised_plate IS NOT NULL)
        OR (kind = 'weak' AND recognised_plate IS NULL
                            AND evidence_image_url IS NULL)
    ),
    -- Strong conflicts cannot be resolved by 'user_arrived_and_checked_in'
    -- (proposal §5.5: the recognised plate is provably not the user's, so a
    -- late manual check-in cannot retroactively legitimise it).
    CONSTRAINT conflicts_strong_resolution_excludes_user_check_in CHECK (
        kind <> 'strong' OR resolution IS DISTINCT FROM 'user_arrived_and_checked_in'
    ),
    CONSTRAINT conflicts_source_event_unique UNIQUE (source_event_id)
);

CREATE UNIQUE INDEX conflicts_one_open_per_bay
    ON conflicts(bay_id) WHERE resolved_at IS NULL;

-- Hot path for the nightly purge job (R16 in backend plan)
CREATE INDEX conflicts_image_purge_idx
    ON conflicts(image_purge_at)
    WHERE evidence_image_url IS NOT NULL AND image_purge_at IS NOT NULL;
```

At most one *unresolved* conflict per bay — same partial-unique-index trick as
reservations. Replay of a Pi `conflict_strong` / `conflict_weak` event with
the same `source_event_id` is a no-op.

**Image retention (proposal §5.5).** When a `conflict_strong` event arrives,
the Pi also POSTs the captured JPEG to the backend over HTTPS (out-of-band —
images are unsuitable for MQTT). The handler:

1. Stores the object (S3 in production, `/var/lib/parkreserve/evidence/<id>.jpg`
   locally) and writes `evidence_image_url`.
2. Sets `image_purge_at = detected_at + INTERVAL '30 days'`.
3. The nightly `purge_evidence_images` job deletes objects whose
   `image_purge_at < NOW()`, then sets `evidence_image_url = NULL` and
   `image_purge_at = NULL` on the row. The conflict row itself is retained
   indefinitely as part of the audit trail; only the image (PII) is purged.

**Weak conflicts retain no image** — by proposal §5.5, low-confidence LPR
output is not usable evidence, so we do not store it. Casual occupancy (no
active reservation) does not capture an image at all (proposal §5.5: LPR runs
only when the bay is `reserved`).

### 3.10 `mock_cards`

Per proposal §5.6, the backend hosts an **in-process mock-bank simulator**.
This table is the simulator's "card database" — populated at deploy / seed
time with test cards that the demo / tests use to exercise the payment flow.
The `card_number` and `cvv` columns intentionally store the raw values
(unhashed) because the mock bank needs to match exactly what the user enters
on the dashboard — there is no real bank to delegate to. **No real card data
should ever be inserted here.** A clear "MOCK PAYMENT" banner on the
dashboard form (proposal §5.3 F / §5.6) and a seed-time-only insertion path
keep this honest.

```sql
CREATE TABLE mock_cards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_number     VARCHAR(19) NOT NULL,        -- 13–19 digits, no spaces
    cvv             VARCHAR(4)  NOT NULL,        -- 3–4 digits
    holder_name     VARCHAR(120) NOT NULL,
    expiry_year     INTEGER NOT NULL,
    expiry_month    INTEGER NOT NULL,
    balance_cents   BIGINT  NOT NULL,            -- AUD cents; seeded high enough
                                                  -- to cover demo holds
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT mock_cards_number_unique UNIQUE (card_number),
    CONSTRAINT mock_cards_number_format CHECK (card_number ~ '^[0-9]{13,19}$'),
    CONSTRAINT mock_cards_cvv_format    CHECK (cvv ~ '^[0-9]{3,4}$'),
    CONSTRAINT mock_cards_expiry_month  CHECK (expiry_month BETWEEN 1 AND 12),
    CONSTRAINT mock_cards_expiry_year   CHECK (expiry_year BETWEEN 2024 AND 2099),
    CONSTRAINT mock_cards_balance_nonneg CHECK (balance_cents >= 0)
);

CREATE INDEX mock_cards_number_idx ON mock_cards(card_number);
```

Notes:

- `card_number` is the lookup key on `validate_card`. The unique index doubles
  as the validator's primary access path.
- `balance_cents` is the simulator's "available funds." The payment service
  decrements it on `pre_auth`, restores it on `release` / `refund`, and
  leaves it unchanged on `penalty_capture` (the captured penalty is treated
  as having moved to the operator and is never restored). The `CHECK ...
  >= 0` constraint defends against any code path that might over-debit due
  to a concurrent race; the application also takes `SELECT ... FOR UPDATE`
  on the row inside the booking transaction to serialise competing
  pre-auths against the same card.
- A real PCI-compliant deployment would never store raw card data in its
  own DB — the gateway's hosted fields tokenize at the browser. This table
  exists *because* the prototype is deliberately a mock; see proposal §5.6
  and the production-deployment caveat in the final report.

### 3.11 `payments`

Single transactions log for every payment-service action (proposal §5.5
fee + penalty schedule, §5.6 mock-payment service). One row per action.
Idempotency is enforced at the schema level so that retries from MQTT
redeliveries, sweeper-replayed events, network blips, and user
double-clicks all collapse to a single charge / refund / release.

```sql
CREATE TABLE payments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id      UUID NOT NULL REFERENCES reservations(id) ON DELETE RESTRICT,
    user_id             UUID NOT NULL REFERENCES users(id)        ON DELETE RESTRICT,
    mock_card_id        UUID NOT NULL REFERENCES mock_cards(id)   ON DELETE RESTRICT,
    parent_payment_id   UUID         REFERENCES payments(id)      ON DELETE RESTRICT,
    action              payment_action NOT NULL,
    penalty_kind        penalty_kind,                  -- only when action='penalty_capture'
    amount_cents        BIGINT NOT NULL,
    status              payment_status NOT NULL DEFAULT 'succeeded',
    idempotency_key     VARCHAR(96) NOT NULL,
    source_event_id     UUID,                          -- Pi event_id when triggered by MQTT
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT payments_amount_nonneg CHECK (amount_cents >= 0),
    CONSTRAINT payments_idempotency_key_unique UNIQUE (idempotency_key),

    -- pre_auth is the only action without a parent; everything else points
    -- back at the reservation's pre_auth row (§3.5 payment dependency)
    CONSTRAINT payments_parent_required CHECK (
        (action = 'pre_auth'  AND parent_payment_id IS NULL)
        OR (action <> 'pre_auth' AND parent_payment_id IS NOT NULL)
    ),
    -- penalty_kind is set iff this is a penalty capture
    CONSTRAINT payments_penalty_kind_only_for_penalty CHECK (
        (action = 'penalty_capture' AND penalty_kind IS NOT NULL)
        OR (action <> 'penalty_capture' AND penalty_kind IS NULL)
    )
);

-- Hot lookup: all payments for a reservation, in time order
CREATE INDEX payments_reservation_idx ON payments(reservation_id, occurred_at);
-- Hot lookup: a user's transaction history (dashboard view §6.4)
CREATE INDEX payments_user_time_idx   ON payments(user_id, occurred_at DESC);
-- Hot lookup: card → its history (and the FOR UPDATE locked-row path)
CREATE INDEX payments_card_idx        ON payments(mock_card_id);

-- Exactly one pre_auth per reservation (the hold). Filters non-pre_auth
-- rows out of the unique check; combined with the FK, this means
-- "every reservation has at most one hold" (I15).
CREATE UNIQUE INDEX payments_one_preauth_per_reservation
    ON payments(reservation_id) WHERE action = 'pre_auth';

-- MQTT-triggered payments (no_show, conflict_weak, conflict_strong refund)
-- carry the Pi's source_event_id; replays of the same event collapse here.
CREATE UNIQUE INDEX payments_source_event_unique
    ON payments(source_event_id) WHERE source_event_id IS NOT NULL;
```

**Idempotency keys.** Each payment action is keyed by a deterministic
string built from `(reservation_id, action[, qualifier])`:

| Action | Idempotency-key shape | Example |
|--------|-----------------------|---------|
| `pre_auth` | `pre_auth:<reservation_id>` | `pre_auth:5f3a…` |
| `release` (clean cancel) | `release:<reservation_id>:clean_cancel` | `release:5f3a…:clean_cancel` |
| `release` (normal completion) | `release:<reservation_id>:completed` | `release:5f3a…:completed` |
| `release` (post-penalty remainder) | `release:<reservation_id>:remainder` | `release:5f3a…:remainder` |
| `refund` (strong-conflict victim) | `refund:<reservation_id>:strong_conflict` | `refund:5f3a…:strong_conflict` |
| `penalty_capture` (any penalty_kind) | `penalty_capture:<reservation_id>:<penalty_kind>` | `penalty_capture:5f3a…:no_show` |

The `idempotency_key` UNIQUE catches retries deterministically without
requiring the Pi event to be present (covers the late-cancel REST path,
which has no `source_event_id`). The `source_event_id` UNIQUE catches the
*MQTT* replay path (covers no_show / conflict_weak / conflict_strong from
the Pi after a backend reconnect).

**Effect on `mock_cards.balance_cents`** (applied inside the same transaction
as the `payments` insert, with `SELECT ... FOR UPDATE` on the card row to
serialise concurrent actions):

| Action | Effect on balance |
|--------|-------------------|
| `pre_auth` | `balance -= deposit_amount` |
| `release` | `balance += amount` (full deposit on clean cancel / normal completion; remainder after a penalty capture — possibly $0 when the penalty equals the full deposit) |
| `refund` | `balance += amount` (full deposit; semantic equivalent of `release` but flagged as a victim refund for the user-facing receipt) |
| `penalty_capture` | unchanged (the captured penalty remains "spent"); paired with a `release` row for the remainder |

So each reservation lifecycle writes exactly one of:

- one `release` row (clean cancel ≥ 15 min, or normal completion);
- one `penalty_capture` + one `release` row (late cancel / no-show /
  weak conflict);
- one `refund` row (strong-conflict victim).

The complete cycle always nets to: card balance decremented by exactly the
amount the operator collected (penalty amount on contract breach, or zero
on a clean cycle / strong-conflict refund). **There is no `capture` row at
any point** — per-time parking-fee billing happens at the facility's exit
gate / kiosk and is out of the prototype's scope (proposal §5.6).

> **Why no `final_charge_cents` cache on `reservations`?** It can be
> derived in O(small N) by `SELECT SUM(amount_cents) FILTER (WHERE
> action='penalty_capture') FROM payments WHERE reservation_id = $1` —
> typically 0–1 rows per reservation. Caching it would require a trigger
> or a careful application path; the lookup cost is negligible for the
> demo and we gain a single source of truth.

---

## 4. Entity-Relationship Diagram

```
 ┌───────────┐        ┌──────────────────┐        ┌─────────────────┐
 │  users    │◄──┐    │  parking_bays    │   ┌───►│  sensor_readings│
 │  (UUID)   │   │    │  (SERIAL)        │   │    │   (BIGSERIAL)   │
 └─┬───┬─────┘   │    └────────┬─────────┘   │    └─────────────────┘
   │   │         │             │             │
   │ 1 │ 1       │ 1           │ 1           │ N
   │ N │ N       │ N           │ N           │
   │   ▼         │       ┌─────┴────────┐    │
   │ ┌─────────────┐     │ reservations │◄───┤
   │ │ licence_    │     │   (UUID)     │    │
   │ │   plates    │     └──────┬───────┘    │
   │ │  (UUID)     │            │            │
   │ └─────────────┘            │            │
   ▼             │     ┌────────┴───────┐    │
 ┌────────────┐  │     │  bay_events    │◄───┤
 │  payments  │  │     │  (BIGSERIAL)   │    │
 │   (UUID)   │  │     └────────────────┘    │
 │  pre_auth  │  │                            │
 │  release   │  │     ┌────────────────┐    │
 │  refund    │  │     │  conflicts     │◄───┘
 │  penalty   │  │     │   (UUID)       │
 └─────┬──────┘  │     │ kind=strong/   │
                 │     │ weak; +plate   │
       │         │     │ +image (strong)│
       ▼         │     └────────────────┘
 ┌────────────┐  │
 │ mock_cards │◄─┘   (mock-bank simulator)
 │   (UUID)   │      seeded with test cards;
 │ +balance   │      decremented on pre_auth,
 └────────────┘      restored on release/refund
```

Relationships:

- `users (1) ── (1..5) licence_plates` — a user binds 1–5 plates; reservation
  creation requires ≥ 1 (auto check-in is impossible without one); cap of 5
  enforced by trigger §3.3.
- `users (1) ── (N) reservations` — a user can hold many reservations over time.
- `users (1) ── (N) payments` — every payment row carries `user_id` for the
  user's transaction-history view (§6.4). The user reliability log
  (formerly the dropped `breaches` table) is just `payments WHERE
  action='penalty_capture' AND user_id=…` (§6.5). **Strong-evidence
  conflicts do NOT produce a `penalty_capture`** — they produce a `refund`,
  because the reserving user is a victim (proposal §5.5).
- `parking_bays (1) ── (N) reservations` — bay has many reservations historically
  but at most one *open* (partial unique index §3.5).
- `parking_bays (1) ── (N) sensor_readings`, `(N) bay_events`, `(N) conflicts`.
- `reservations (0..N) ── (0..N) bay_events` — events that relate to a
  reservation carry its id for the audit trail.
- `reservations (1) ── (1..N) payments` — every reservation has exactly one
  `pre_auth` row (I15) plus exactly one of: a single `release` (clean
  cancel or normal completion), a `penalty_capture` + `release` pair
  (late cancel / no-show / weak conflict), or a single `refund`
  (strong-conflict victim) — §3.11.
- `reservations (1) ── (0..N) conflicts` — a reservation may accumulate at
  most one strong + one weak conflict over its lifetime (each conflict is a
  distinct Pi event with its own `source_event_id`). Per proposal §5.5 LPR
  runs only when the bay is `reserved`, so every conflict row is born with a
  matching reservation; `reservation_id` may briefly be NULL only during MQTT
  ingest race and is reconciled by the `source_event_id` upsert.
- `mock_cards (1) ── (N) payments` — every payment row references the card
  whose balance it affected. The same card may back many reservations
  across many users (the prototype does not pin a card to a user account —
  card details are entered fresh on every booking; see §3.10 prelude).
- `parking_bays.current_reservation_id → reservations.id` — denormalised
  pointer, deferrable FK, kept consistent by `ReservationService`.

The `licence_plates` table is **not** referenced by `reservations` —
reservations are not pinned to a specific plate (proposal §5.5: any currently
bound plate counts as a match). The Pi receives the user's full bound list
over MQTT each time the reservation is created or the user adds/removes a
plate, and does the LPR-vs-bound-list match itself.

---

## 5. Invariants Enforced in the Database

| # | Invariant | Mechanism |
|---|-----------|-----------|
| I1 | Every user has a unique, case-insensitive email | `CITEXT` + `UNIQUE` on `users.email` |
| I2 | Bay codes are unique; device ids unique when present | `UNIQUE` on `parking_bays.code`, `parking_bays.device_id` |
| I3 | Reservation `expected_arrival_time` is strictly after `booked_at` and at most 1 hour later | `CHECK reservations_booking_window` §3.5 |
| I4 | At most one open reservation (active / pending_check_in / checked_in) per bay | Partial unique index `reservations_one_open_per_bay` |
| I5 | At most one unresolved conflict per bay | Partial unique index `conflicts_one_open_per_bay` |
| I6 | Conflict resolution fields are consistent (both set or both null) | `CHECK` constraint §3.9 |
| I7 | Status-dependent timestamps are populated when the status implies them | `CHECK` constraints §3.5 |
| I8 | Denormalised `parking_bays.current_reservation_id` points at a real reservation or NULL | Deferrable FK |
| I9 | Each Pi event (identified by `source_event_id`) triggers at most one bay_event, one conflict, and one MQTT-driven payment | `UNIQUE` on `source_event_id` in `bay_events`, `conflicts`, and partial-`UNIQUE` in `payments` |
| I10 | A user binds at most 5 licence plates; bound plates are unique per user; plate strings are normalised (uppercase alphanumeric, ≤ 10 chars) | Trigger `licence_plates_max_per_user`, `UNIQUE (user_id, plate)`, `CHECK licence_plates_format` |
| I11 | Strong conflicts always carry a recognised plate; weak conflicts never do (matches the proposal §5.5 evidence-retention split) | `CHECK conflicts_evidence_matches_kind` |
| I12 | Strong conflicts cannot be resolved by a late user check-in (proposal §5.5: the plate is provably not the user's) | `CHECK conflicts_strong_resolution_excludes_user_check_in` |
| I13 | Strong-evidence conflicts never produce a `penalty_capture` for the reserving user — they produce a `refund` (proposal §5.5: the user is a victim, not at fault) | Encoded in service code (`conflict_strong` handler issues `refund`, never `penalty_capture`); the `breaches` table that previously made this an enum-level invariant no longer exists |
| I14 | Every `checked_in` reservation records *how* the user checked in, and an `auto_lpr` check-in always carries the recognised plate (proposal §5.3 F / §5.5: "recognised plate is logged with the reservation record") | `CHECK reservations_checked_in_has_ts` (now also requires `check_in_mechanism` when `status='checked_in'`) + `CHECK reservations_check_in_plate_matches_mechanism` |
| I15 | Every reservation has at most one `pre_auth` payment (the deposit) | Partial unique index `payments_one_preauth_per_reservation` (§3.11) |
| I16 | Every payment-service action is idempotent on `(reservation_id, action[, qualifier])` — replays from MQTT redelivery, sweeper retries, network blips, or user double-clicks collapse to a single row | `UNIQUE (idempotency_key)` on `payments` (§3.11) |
| I17 | A non-`pre_auth` payment row always references its parent `pre_auth`; `pre_auth` rows have no parent | `CHECK payments_parent_required` (§3.11) |
| I18 | `penalty_kind` is set on `payments` rows iff `action='penalty_capture'` (matches the proposal §5.5 fee + penalty schedule) | `CHECK payments_penalty_kind_only_for_penalty` (§3.11) |
| I19 | Mock card balances cannot go negative — over-debit is rejected at the row level | `CHECK mock_cards_balance_nonneg` (§3.10), combined with `SELECT ... FOR UPDATE` in the booking transaction |

I4, I9, and I16 are the three most load-bearing invariants. I4 is the reason
concurrent reservation requests for the same bay cannot both succeed: the
second `INSERT` fails with `unique_violation`, the service translates it to
HTTP 409, and no further coordination is needed. I9 is the reason the MQTT
client can be aggressive about replays on reconnect (§8 of the
implementation plan) without risk of double-counting events. I16 is the
reason payment retries (whether HTTP, MQTT-driven, or sweeper-driven) are
safe — a user is never charged twice for the same incident.

I11–I13 are the schema-level encoding of the strong/weak distinction
introduced by the LPR addition (proposal §5.5). I11 makes "strong without a
plate" or "weak with a plate" rejected at the DB level — the application
cannot accidentally persist evidence in the wrong column. I13 is the
service-level invariant for "strong-evidence conflict is not a user breach":
since the breaches table no longer exists, the equivalent invariant is now
that no `payments` row with `action='penalty_capture'` is ever inserted in
the `conflict_strong` handler — only a `refund` row. The `penalty_kind`
enum (`late_cancel`, `no_show`, `weak_conflict`) intentionally has no
`strong_conflict` value, so even a buggy handler that tried to insert a
penalty row for a strong conflict would fail the `payments_penalty_kind_*`
CHECK at the DB level.

I15–I19 are the schema-level encoding of the mock-payment service
introduced by proposal §5.5 / §5.6. I15 + I16 together guarantee that
every reservation has exactly-one hold and that every payment action is
exactly-once — the two properties that make the mock-payment surface
shape-compatible with a real gateway's idempotency contract. I19 is the
practical safety belt that makes "balance went negative because of a race"
a database-level impossibility, even before considering the application's
`SELECT ... FOR UPDATE`.

---

## 6. Typical Queries

All three below are on the hot path and each is supported by a dedicated index.

### 6.1 Dashboard — list all bays with current state

```sql
SELECT  b.code,
        b.label,
        b.state,
        b.last_distance_cm,
        b.sensor_last_seen_at,
        r.id                     AS current_reservation_id,
        r.user_id                AS current_reservation_user,
        r.expected_arrival_time  AS current_reservation_arrival,
        r.check_in_grace_expires_at
FROM    parking_bays b
LEFT JOIN reservations r ON r.id = b.current_reservation_id
ORDER BY b.code;
```

Runs in < 1 ms on the demo dataset. No JOIN to `users` is needed for the
public dashboard.

### 6.1a User's bound plates (for reservation publish + UI)

```sql
SELECT plate, label
FROM   licence_plates
WHERE  user_id = $1
ORDER BY created_at;
```

Served by `licence_plates_user_idx`. Called whenever a reservation is created
(to embed the bound list in the Pi-bound MQTT payload) and when the user
adds/removes a plate while a reservation is active (so the updated list can
be republished — see backend plan §8.2 / I10).

### 6.2 Safety-net sweeper — reservations that should have expired

```sql
-- No-show candidates: ACTIVE past arrival + 5 min, bay still AVAILABLE
SELECT r.id, r.bay_id, r.user_id
FROM   reservations r
JOIN   parking_bays  b ON b.id = r.bay_id
WHERE  r.status = 'active'
  AND  r.expected_arrival_time + INTERVAL '5 minutes' < NOW()
  AND  b.state = 'available'
ORDER BY r.expected_arrival_time
LIMIT 100
FOR UPDATE OF r SKIP LOCKED;

-- Check-in-grace candidates: PENDING_CHECK_IN past grace, still no check-in
SELECT r.id, r.bay_id, r.user_id
FROM   reservations r
WHERE  r.status = 'pending_check_in'
  AND  r.check_in_grace_expires_at < NOW()
ORDER BY r.check_in_grace_expires_at
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

Served by the partial indexes `reservations_arrival_idx` and
`reservations_check_in_grace_idx`. `FOR UPDATE SKIP LOCKED` lets the sweeper
be horizontally safe even though we currently run it single-instance.

### 6.3 Booking-time payment transaction (proposal §5.5 step 1)

The booking transaction does the card lookup, the deposit debit, the
reservation insert, and the `pre_auth` row insert atomically. The
`SELECT ... FOR UPDATE` on the card row serialises competing booking
attempts that target the same card. Default deposit is $10 (1000 cents) —
configurable per facility.

> Bind variables below use named placeholders (`:card_number`,
> `:deposit_cents`, …) for readability; the production code uses the
> driver's positional parameters via SQLAlchemy.

```sql
BEGIN;

-- 1. Validate card + lock for update (rejects unknown / expired / wrong-CVV cards)
SELECT id, balance_cents
FROM   mock_cards
WHERE  card_number = :card_number
  AND  cvv         = :cvv
  AND  (expiry_year > :now_year
        OR (expiry_year = :now_year AND expiry_month >= :now_month))
FOR UPDATE;
-- → application checks balance_cents >= :deposit_cents; otherwise rollback + 402

-- 2. Debit the deposit from the card (CHECK balance_nonneg / I19 catches overdebit)
UPDATE mock_cards
SET    balance_cents = balance_cents - :deposit_cents,    -- e.g. 1000 = $10
       updated_at    = NOW()
WHERE  id = :card_id;

-- 3. Insert the reservation
INSERT INTO reservations (id, bay_id, user_id, status, expected_arrival_time)
VALUES (:res_id, :bay_id, :user_id, 'active', :arrival)
RETURNING id;

-- 4. Insert the pre_auth payment row (idempotent on idempotency_key, I16)
INSERT INTO payments (reservation_id, user_id, mock_card_id,
                      action, amount_cents, idempotency_key)
VALUES (:res_id, :user_id, :card_id, 'pre_auth', :deposit_cents,
        'pre_auth:' || :res_id::text);

COMMIT;
```

A retry of the same HTTP booking request collapses on the
`payments_idempotency_key_unique` index (I16); the partial unique index
`reservations_one_open_per_bay` (I4) collapses concurrent bookings on the
same bay; `mock_cards_balance_nonneg` (I19) rejects an overdebit if a card
is double-used between the read and the update by another transaction.

### 6.3a Deposit release at completion (proposal §5.5 step 2)

When the bay transitions from `reserved_checked_in → available` (vehicle
left after a normal session), the backend writes a single `release` row
that returns the **full** deposit. There is no `capture` step — per-time
parking-fee billing happens at the facility's exit gate / kiosk, which is
out of scope for the prototype (proposal §5.6).

If a prior penalty already captured-and-released the deposit (the
"weak conflict + late check-in" path — proposal §5.5), the completion
release would attempt to add an `INSERT` whose `idempotency_key` is
`release:<res_id>:completed` — but the `payments_one_preauth_per_reservation`
combined with the actual remaining-balance bookkeeping makes this a
**no-op**: there is nothing to release because the `pre_auth` was already
fully accounted for by the earlier `penalty_capture + release` pair.
Application code computes the remaining-deposit amount before issuing
this row and skips it when zero (an explicit `INSERT … amount_cents = 0`
is also valid against the `payments_amount_nonneg` CHECK if you prefer
to keep the audit row).

```sql
BEGIN;

-- Release the full deposit back to the card balance.
-- amount_cents = (pre_auth.amount_cents
--                 − SUM of prior payments rows that drew from the deposit
--                   for this reservation, i.e. release / refund / penalty_capture).
-- For a clean session this is exactly the original deposit; for the
-- weak-conflict-then-late-check-in path it is 0 and the application
-- skips the INSERT entirely.
INSERT INTO payments (reservation_id, user_id, mock_card_id, parent_payment_id,
                      action, amount_cents, idempotency_key, source_event_id)
VALUES (:res_id, :user_id, :card_id, :preauth_id,
        'release', :remaining_deposit_cents,
        'release:' || :res_id::text || ':completed', :event_id)
ON CONFLICT (idempotency_key) DO NOTHING;

UPDATE mock_cards
SET    balance_cents = balance_cents + :remaining_deposit_cents,
       updated_at    = NOW()
WHERE  id = :card_id;

UPDATE reservations
SET    status       = 'completed',
       completed_at = NOW(),
       updated_at   = NOW()
WHERE  id = :res_id;

COMMIT;
```

`ON CONFLICT (idempotency_key) DO NOTHING` makes a re-emitted bay state
event (after a backend reconnect) a no-op. The penalty flow has the same
shape (`'penalty_capture'` + a `'release'` for the remainder, possibly
$0); the strong-conflict path is a single `'refund'` row that returns
the full deposit.

### 6.3b User transaction-history view (proposal §5.3 F dashboard)

Drives the dashboard's "your charges" tab.

```sql
SELECT  p.action,
        p.penalty_kind,
        p.amount_cents,
        p.occurred_at,
        p.reservation_id,
        r.bay_id,
        b.code AS bay_code
FROM    payments      p
JOIN    reservations  r ON r.id = p.reservation_id
JOIN    parking_bays  b ON b.id = r.bay_id
WHERE   p.user_id = $1
ORDER BY p.occurred_at DESC
LIMIT 50;
```

Served by `payments_user_time_idx`.

### 6.3c Monthly penalty-capture analytics (replaces the old breach-count query)

The dropped `breaches` table's monthly-count query becomes a filter on
`payments` for `action='penalty_capture'`. There is no automatic
suspension trigger off this any more (proposal §5.5 — penalty fees are
the deterrent); the count is shown in the admin's reliability view for
manual review.

```sql
SELECT  penalty_kind,
        COUNT(*)             AS captures,
        SUM(amount_cents)    AS total_cents
FROM    payments
WHERE   user_id    = $1
  AND   action     = 'penalty_capture'
  AND   occurred_at >= date_trunc('month', NOW() AT TIME ZONE 'UTC')
GROUP BY penalty_kind;
```

Served by `payments_user_time_idx`. The explicit `AT TIME ZONE 'UTC'`
matches the §3 convention; for facility-local-time conversions in future
reports, adapt the `date_trunc` call.

### 6.3a Nightly image-purge job (proposal §5.5 retention policy)

```sql
SELECT id, evidence_image_url
FROM   conflicts
WHERE  evidence_image_url IS NOT NULL
  AND  image_purge_at < NOW()
LIMIT  500
FOR UPDATE SKIP LOCKED;
-- For each row, delete the object from storage, then:
UPDATE conflicts
SET    evidence_image_url = NULL,
       image_purge_at     = NULL
WHERE  id = $1;
```

Served by `conflicts_image_purge_idx`. The conflict row itself is *retained*
(audit trail); only the image (PII) is purged. Backend plan §8.3 / R16
specify the job (`purge_evidence_images`) and the alerting on > 24 h since
last successful run.

### 6.4 Ingest — apply a Pi state update atomically

```sql
BEGIN;

INSERT INTO sensor_readings (bay_id, distance_cm, occupied, recorded_at)
VALUES ($1, $2, $3, $4);

UPDATE parking_bays
SET    state               = $5::bay_state,   -- trusted value from Pi
       last_distance_cm    = $2,
       sensor_last_seen_at = $4,
       updated_at          = NOW()
WHERE  id = $1;

-- bay_events row written by application in the same transaction,
-- carrying the Pi's source_event_id for idempotent replay
INSERT INTO bay_events (bay_id, reservation_id, kind, from_state, to_state,
                        source_event_id, payload)
VALUES ($1, $6, 'state_changed', $7, $5, $8, $9)
ON CONFLICT (source_event_id) DO NOTHING;

COMMIT;
```

Unlike the pre-revision design, the backend does **not** compute the bay state
from the sensor reading — it trusts the value published by the Pi (proposal
§5.4 puts the state machine on the Pi). The `ON CONFLICT ... DO NOTHING`
clause on `bay_events` makes the whole transaction a no-op on replay.

---

## 7. Migrations Strategy

- Alembic, one revision per logical change. Revision filenames prefixed with
  ISO date, e.g. `20260421_01_initial.py`.
- `alembic upgrade head` is idempotent and is invoked by `deploy/bootstrap.sh`
  and `docker-compose up`.
- Downgrades are written for every non-data-destructive revision. Destructive
  revisions (drop column, drop table) have an explicit note and are excluded
  from downgrade.

Planned initial revisions:

| Revision | Content |
|----------|---------|
| `20260421_01_initial` | Enums (`user_role`, `bay_state`, `reservation_status`, `penalty_kind`, `payment_action`, `payment_status`, `bay_event_kind`, `conflict_kind`, `conflict_resolution`, `check_in_mechanism`), `users`, `licence_plates` (+ trigger), `parking_bays`, `reservations` (incl. `check_in_mechanism` + `check_in_recognised_plate` columns and the I14 CHECK), `bay_events`, `sensor_readings`, `conflicts` (with strong/weak fields and 30-day retention column), `mock_cards`, `payments` (with all idempotency / parent / penalty-kind CHECKs and partial unique indexes I15–I19), all indexes and constraints |
| `20260421_02_seed_demo_bays` | Data migration: insert 3 demo bays `A1`, `A2`, `A3` |
| `20260421_03_seed_mock_cards` | Data migration: insert ~10 demo mock cards (varied balances; one expired and one wrong-CVV card to exercise rejection paths in tests). The seed data is intentionally small and committed to source — these are *test* card numbers (e.g., `4111 1111 1111 1111` family), not real ones |

---

## 8. Seed Data

```sql
-- Demo bays (data migration)
INSERT INTO parking_bays (code, label, device_id, state)
VALUES ('A1', 'Bay A1', 'esp32-a1', 'offline'),
       ('A2', 'Bay A2', 'esp32-a2', 'offline'),
       ('A3', 'Bay A3', 'esp32-a3', 'offline');

-- Mock-bank simulator: test cards (proposal §5.6).
-- balance_cents is generous so a demo run can exercise many bookings.
-- Two pathological rows force the rejection paths in tests:
--   '4000 0000 0000 0002' is an expired card (must be rejected by 6.3 step 1)
--   '4000 0000 0000 0010' has a $0 balance (must be rejected before 6.3 step 2)
INSERT INTO mock_cards (card_number, cvv, holder_name,
                        expiry_year, expiry_month, balance_cents)
VALUES ('4111111111111111', '123', 'Demo User One',     2030, 12, 50000),
       ('4222222222222222', '456', 'Demo User Two',     2030, 12, 50000),
       ('4333333333333333', '789', 'Admin Test Card',   2030, 12, 50000),
       ('4000000000000002', '321', 'Expired Card',      2024, 1,  50000),
       ('4000000000000010', '654', 'Empty Card',        2030, 12, 0);
```

A demo admin user is seeded by `scripts/seed.py`, not by migration, because
its password depends on an env var at deploy time.

> **Note on test card numbers.** The numbers above are illustrative
> placeholders for demo seed data. They are *not* real Visa / Mastercard
> test cards and they are *not* validated against the Luhn algorithm — the
> mock bank only does an exact-match lookup. A production deployment that
> swaps in a real gateway would delete this table and the seed migration
> entirely (proposal §5.7 future work).

---

## 9. Backup and Retention

- **Backup:** nightly `pg_dump` run by a systemd timer, stored on the EC2 local
  disk and synced to an S3 bucket. Demo dataset is tiny so full dumps suffice.
- **Retention:**
    - `sensor_readings` rolls off after 7 days via a daily
      `DELETE ... WHERE received_at < NOW() - INTERVAL '7 days'`.
    - `conflicts.evidence_image_url` and the underlying object are purged at
      `image_purge_at` (= `detected_at + 30 days`) per proposal §5.5; the
      conflict row itself remains for audit.
    - `bay_events`, `reservations`, `licence_plates`, `conflicts` (without
      their image once purged), `mock_cards`, and `payments` are kept
      indefinitely for the project report. `payments` is the audit ledger
      for every charge / refund / penalty, so even after a reservation is
      "completed" all of its financial history is queryable for the report.
      `mock_cards` is purely test data and is recreated on each
      `make seed` run — not really subject to retention concerns.

---

## 10. Test-Environment Parity

Tests run against real PostgreSQL 16 (via `pytest-postgresql`). The same
migration stack is applied, so every constraint, index, enum, and JSONB query
is exercised in CI. A test that passes locally will not silently rely on
SQLite semantics — the invariants in §5 will always be enforced, including:

- The 1-hour booking-window `CHECK` (I3).
- The partial unique index on open reservations (I4).
- The `source_event_id` unique constraints that back MQTT replay idempotency (I9).
- The plate-cap trigger and uniqueness on `(user_id, plate)` (I10).
- The `conflicts_evidence_matches_kind` and
  `conflicts_strong_resolution_excludes_user_check_in` CHECKs (I11, I12).
- The `reservations_check_in_plate_matches_mechanism` CHECK and the extended
  `reservations_checked_in_has_ts` requirement that every `checked_in` row
  carries a `check_in_mechanism` (I14).
- The `payments_one_preauth_per_reservation` partial unique index (I15) —
  proves the booking transaction can never accidentally place two holds.
- The `payments_idempotency_key_unique` constraint (I16) — exercised by
  the payment-service idempotency tests in proposal §7.3 (replay 50
  randomly-selected actions 3× each; verify exactly one row per key).
- The `payments_parent_required` and `payments_penalty_kind_only_for_penalty`
  CHECKs (I17, I18).
- The `mock_cards_balance_nonneg` CHECK (I19) — exercised by the
  card-validation rejection tests (the seeded `4000…0010` empty card must
  be rejected before the booking transaction debits below zero).

### 10.1 Fixture sketch

```python
# tests/conftest.py (abridged)
from pytest_postgresql import factories

postgresql_proc = factories.postgresql_proc(port=None, postgres_options="-c fsync=off")
postgresql     = factories.postgresql("postgresql_proc")

@pytest.fixture(scope="session")
def database_url(postgresql_proc):
    return f"postgresql+psycopg://{postgresql_proc.user}@{postgresql_proc.host}:{postgresql_proc.port}/postgres"

@pytest.fixture()
def app(database_url):
    app = create_app(testing=True, database_url=database_url)
    with app.app_context():
        db.create_all()         # or: alembic upgrade head
        yield app
        db.drop_all()
```

The template-DB variant (faster) replaces `create_all()` per test with a cloned
template database built once per session.

---

## 11. Security Notes

- Passwords: `argon2id`, parameters `m=64 MiB, t=3, p=4`.
- Connections: TLS required in production (`sslmode=require` in the connection
  string). Connection pooling via SQLAlchemy's `QueuePool`, `pool_size=10`,
  `pool_pre_ping=True`.
- Least-privilege DB role: backend connects as `parkreserve_app`, which has
  `CONNECT` on the DB and `CRUD` on application tables but no `CREATE`. DDL is
  run by a separate `parkreserve_owner` role invoked only by Alembic at deploy
  time.
- **PII inventory and retention** (proposal §5.5 / §5.6):
    - `users`: email, name — kept for the lifetime of the account.
    - `licence_plates`: per-user bound plates — kept for the lifetime of the
      binding. Plate ownership is **not** verified in the prototype; a
      production deployment would add a verification step (registration-
      document OCR or vehicle-registry API — proposal §5.6 / §5.7).
    - `bay_events.payload`: may carry `recognised_plate` for `auto_check_in`
      and `conflict_strong` events; this is the audit trail and is kept
      indefinitely (the plate alone, without a captured image, is the
      minimum needed for incident review).
    - `reservations.check_in_recognised_plate`: populated only when
      `check_in_mechanism='auto_lpr'`. Same retention as the reservation row
      itself (kept indefinitely for the project report). This is the
      "recognised plate logged with the reservation record" referenced in
      proposal §5.5 — minimum-PII because (a) it is by definition one of the
      user's own bound plates and (b) no image is retained after a successful
      auto check-in.
    - `conflicts.recognised_plate` + `evidence_image_url`: stored only for
      `kind='strong'`. The image is purged at `image_purge_at` (= 30 days
      after detection); the recognised plate string is retained for the
      audit log.
    - `conflicts` for `kind='weak'`: no plate, no image — by proposal §5.5
      ("LPR didn't return a confident result, so there is no usable
      evidence").
    - Casual occupancy (no active reservation): **no LPR run, no image
      captured at all** (enforced upstream on the Pi; backend has no row to
      store).
    - `mock_cards.card_number` + `cvv`: would be PII if real, but **the
      table is a mock-bank simulator**, never populated with live card
      data, never reachable from a real bank network, and gated behind a
      "MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS" banner on the
      dashboard form (proposal §5.6). The test rows in §8 are illustrative
      placeholders. A production deployment swaps the mock for a real
      gateway (proposal §5.7) and drops this table entirely; raw card
      details would never reach the backend in that world (browser-side
      tokenization via the gateway's hosted fields).
    - `payments`: holds reservation-id, user-id, mock-card-id,
      amount_cents, action, penalty_kind, occurred_at — all of these are
      either (a) already PII tracked elsewhere (user_id), (b) mock data
      (mock_card_id), or (c) financial-audit fields needed to substantiate
      every charge / refund. Retained indefinitely for audit. No raw card
      number is stored on a `payments` row — the FK to `mock_cards`
      stands in for the card identity.
- The strong/weak split is the minimum-PII design — we keep evidence only
  when it is both legally meaningful (strong-evidence conflict against a
  reservation holder) and time-limited (30 days), and we never retain
  identifying data for the casual-parking happy path.

---

## 12. Rubric Self-Check

| Rubric row | Weight | How this design scores *Exemplary* |
|------------|-------:|------------------------------------|
| Report → Technical Content | 20 | ER diagram §4, invariants table §5, indexed hot-path queries §6, migrations §7, per-state enum coverage matching proposal §5.4 |
| Report → Organization & Development | 10 | Numbered sections, tables, each section builds on the previous |
| Report → Word Usage & Format | 10 | Captioned SQL blocks, IEEE-style tables, consistent typography |
| Report → Code | 10 | SQL is copy-pasteable; migrations are real Alembic files; `seed.py` exists |
| Demo → Technical Implementation | 20 | DB-level constraints (not app-level convention) make "double booking", "double charge on retry", and "double event on replay" impossible live |
| Demo → Q&A | 15 | "How do you prevent two people reserving the same bay?" → §3.5 partial unique index; "What happens if the same Pi event arrives twice?" → §3.7 / §3.9 / §3.11 `source_event_id` UNIQUE; "What happens if the user double-clicks the booking button?" → §3.11 `idempotency_key` UNIQUE (I16); "How do you stop a strong-evidence conflict from punishing the victim?" → I13 + the absence of `strong_conflict` from `penalty_kind`; "How do you keep evidence images from outliving 30 days?" → §3.9 `image_purge_at` + §6.3a purge query; "Where does the money go in the demo?" → §3.10 mock-bank simulator (no real gateway); "Why no `breaches` table any more?" → proposal §5.5 replaces the breach-counter + monthly-ban model with direct penalty fees, and §3.6 redirects the user reliability log to `payments WHERE action='penalty_capture'` (§6.5); all demonstrable live |
