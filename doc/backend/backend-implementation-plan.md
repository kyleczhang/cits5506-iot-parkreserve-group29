# Backend Implementation Plan — ParkReserve

**Unit:** CITS5506 The Internet of Things | **Semester:** 1, 2026 | **Group:** 29
**Subsystem:** F — Cloud Backend (Flask + PostgreSQL + MQTT) on AWS
**Owner:** Cheng Zhang (24878502)
**Document status:** Implementation-ready (aligned with `doc/proposal/proposal.md`)

---

## 1. Purpose and Scope

This document specifies how **Subsystem F (Cloud Backend)** of the ParkReserve system
will be designed, built, tested, and deployed. It is the authoritative reference for all
backend work and is written to satisfy the *Exemplary* band of the CITS5506 Project
Report and Project Presentation / Demo rubrics.

The backend is responsible for:

1. Terminating the cloud MQTT channel that bridges the Raspberry Pi edge gateway
   (Subsystem E) to the cloud tier.
2. Persisting the authoritative system state in **PostgreSQL** (both production and
   automated tests — no SQLite, no in-memory fallbacks).
3. Managing per-account **licence-plate bindings** (proposal §5.5): each user
   binds 1–5 plates; a reservation is not pinned to a specific plate — *any*
   currently bound plate counts as a valid match. The bound-plate list is
   published with every reservation update so the Pi can match LPR results
   locally. Plate ownership is **not** verified in the prototype (proposal §5.6).
4. Running the reservation business logic: enforcing the one-hour booking
   window (proposal §5.5), handling reserve / cancel / check-in / auto-release
   (where check-in is automatic via LPR plate match in the typical case, with
   QR-scan and manual button as fallbacks), and capturing **fees and
   penalties** (`late_cancel`, `no_show`, `weak_conflict`) directly against
   the user's pre-authorized card via the mock-payment service (see §8.8 and
   proposal §5.5 fee + penalty schedule). **Strong-evidence conflicts**
   (recognised plate ∉ user's bound plates) are logged as *facility
   incidents* and trigger a **full refund** of the reserving user's hold —
   the user is a victim, not at fault (proposal §5.5).
4a. Hosting an in-process **mock-payment service** (proposal §5.6): a seeded
    mock-bank table simulates card validation; idempotent `validate_card` /
    `preauthorize` / `release` / `charge_penalty` / `refund` methods mirror
    a real gateway's integration surface so a future real-provider swap is
    a single-module change. **The service intentionally does *not* expose
    a `capture` method** — the prototype handles only the reservation
    deposit; per-time parking-fee billing is the facility's exit-side
    concern, out of scope (proposal §5.6). Reservation creation is gated
    on a successful pre-auth — the reservation row and its `pre_auth`
    payment row are inserted in the same transaction.
5. Consuming Pi-originated state-machine events (`auto_check_in`,
   `pending_check_in`, `conflict_strong`, `check_in_confirmed`,
   `sensor_online`, `sensor_offline`), plus internally synthesised
   reservation-timeout events (`conflict_weak`, `no_show`) dispatched through
   the same service entrypoint. These events are persisted along with any
   plate evidence and image references, and drive notifications — to the
   reserving user on `auto_check_in` ("you're checked in at Bay X") and
   `pending_check_in` ("vehicle detected — please check in manually"), to
   facility admins on `conflict_strong` / `conflict_weak` (with recognised
   plate evidence on strong-evidence conflicts).
6. Receiving and persisting **conflict-evidence images** uploaded by the Pi
   over HTTPS for `conflict_strong` events; retaining them for 30 days then
   purging (proposal §5.5 retention policy).
7. Exposing a REST + WebSocket API consumed by the React.js dashboard
   (Subsystem F frontend, owned by Riya), including plate management
   (add / remove / list), reservations, and the QR-code / manual fallback
   check-in endpoint (the primary check-in path is automatic via LPR — no
   user request is involved).
8. Keeping the system responsive when the cloud link flaps, by letting the edge
   continue local control while the cloud re-syncs on reconnect.

Out of scope for this document: ESP32 firmware (Subsystems A/B), Raspberry Pi
state-machine service (Subsystem C+E — the authoritative per-bay state machine
lives on the Pi; the backend mirrors it for the dashboard and reservation
business logic), React UI (frontend half of Subsystem F).

---

## 2. Requirements Trace

Every requirement below links back to a specific section of the proposal or to a
target metric in the testing plan. This trace is used to verify completeness in the
final report.

| # | Requirement | Source |
|---|-------------|--------|
| R1 | Ingest `cloud/bay/<id>/state` updates and `cloud/bay/<id>/event` state-machine events from HiveMQ and persist the latest state per bay | Proposal §5.1 step 6, §5.2, §5.3 F |
| R2 | Publish reservation updates (create / cancel / check-in) — *together with the reserving user's bound-plate list* — on `cloud/bay/<id>/reservation` so the Pi state machine and LPR matcher pick them up | Proposal §5.1 step 7, §5.2, §5.3 F, §5.5 |
| R3 | REST endpoints for listing bays, plate management, and creating / cancelling / checking-in reservations (auto via LPR is primary; QR-scan is fallback; manual button is further fallback) | Proposal §5.3 F, §5.5, §7 Week 4 |
| R4 | Real-time push of bay state changes and reservation events to the dashboard (WebSocket) | Proposal §5.1 step 7 |
| R5 | Persist reservation history, bay events, conflicts (with plate evidence + image reference for strong-evidence cases), and the full transactions ledger (pre-auth / release / refund / penalty_capture — no `capture` action; per-time parking-fee billing is out of scope) in PostgreSQL | Proposal §5.3 F, §5.5, §7.3 |
| R6 | Receive and persist `conflict_strong` (LPR plate mismatch) events from the Pi, and synthesise / persist `conflict_weak` (LPR did not auto-resolve and grace expired) plus `no_show` from the reconcile sweeper; retain image evidence for `conflict_strong` for 30 days then purge; alert facility admins | Proposal §5.3 C/F, §5.5, §7.3 "Strong/Weak Conflict" — target 100 % |
| R7 | Cloud-disconnection resilience: local control unaffected; backend re-syncs on reconnect | Proposal §7.3 "Cloud Disconnection Resilience" |
| R8 | MQTT message delivery ≥ 99 %, end-to-end reservation latency (click → LED state change) < 5 s; auto-check-in latency (vehicle detection → "you're checked in" notification) < 8 s | Proposal §7.3 |
| R9 | Deployable on AWS EC2 free tier, reachable via public URL over HTTPS | Proposal §5.1 step 6, §8 |
| R10 | Dashboard accuracy 100 %: API response == physical LED state across all bays | Proposal §7.3 |
| R11 | Enforce booking window: reservations allowed only up to 1 hour before `expected_arrival_time` | Proposal §5.5 |
| R12 | **Penalty capture (replaces the prior monthly-ban model — proposal §5.5):** automatically `charge_penalty` on `late_cancel` (< 15 min to arrival), `no_show`, and `weak_conflict` (LPR did not auto-resolve and no manual check-in within 5 min grace), each at the configured penalty amount, with the deposit remainder released. **Strong-evidence conflict is NOT a user penalty** — it triggers a **full refund** of the user's deposit and a facility-incident log of the recognised plate. No automatic monthly suspension; admins may suspend repeat offenders manually | Proposal §5.5, §7.3 "Mock Payment Correctness" / "Strong-Conflict Refund" |
| R13 | Check-in mechanisms: (a) automatic via LPR plate match (primary, no user action — server-side on Pi event); (b) QR-code scan at the bay (fallback); (c) manual "I'm here" button (further fallback). User-initiated paths reject the call if `bay_code` ≠ reservation's bay | Proposal §5.5 |
| R14 | Push notifications: on `auto_check_in` to the reserving user ("you're checked in at Bay X"); on `pending_check_in` ("vehicle detected — please check in manually"); on **successful normal-exit deposit release** ("your deposit of $X.YZ has been released — see receipt"); on **strong-conflict refund** ("your reservation was disrupted — full refund issued"); on penalty captures ("penalty captured: …"); on `conflict_strong` / `conflict_weak` to facility admins (recognised plate string included on strong) | Proposal §5.3 F, §5.5 |
| R15 | Plate management: each user account binds 1–5 licence plates; CRUD endpoints; reservations match against any currently-bound plate; plate ownership not verified in prototype (production caveat documented) | Proposal §5.5, §5.6 |
| R16 | Receive conflict-evidence image uploads from the Pi over HTTPS for `conflict_strong` events; persist a stable URL and `image_purge_at = detected_at + 30 days`; nightly job purges expired images | Proposal §5.5 retention policy |
| R17 | LPR runs *only* when the bay state is `reserved` — backend never instructs the Pi to capture casual-occupancy plates (no LPR for casual parking, per privacy policy §5.5) | Proposal §5.5 retention policy |
| **R18** | **Mock-payment service (proposal §5.6):** in-process mock-bank database (`mock_cards`) seeded with test cards; service exposes `validate_card`, `preauthorize`, `release`, `charge_penalty`, `refund`. **No `capture` method** — per-time parking-fee billing is out of scope. Card form on the dashboard shows a "MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS" banner. No real bank network is ever contacted | Proposal §5.6, §7.3 "Card Validation" / "Deposit Release on Completion" |
| **R19** | **Idempotent payment endpoints:** every payment action is keyed on `(reservation_id, action[, qualifier])` so MQTT redeliveries, sweeper retries, network blips, and user double-clicks collapse to a single row. The `payments.idempotency_key` UNIQUE constraint enforces this at the DB level (DB design I16) | Proposal §5.6, §7.3 "Idempotency" |
| **R20** | **Booking gated on successful pre-auth:** the reservation row and its `pre_auth` payment row are inserted in the same transaction; if card validation or balance check fails the transaction rolls back and no orphan reservation exists. Concurrent bookings against the same card are serialised by `SELECT ... FOR UPDATE` on the `mock_cards` row | Proposal §5.5 step 1, §5.6 |

Each requirement is covered by at least one automated test in `tests/` — see §9.

---

## 3. High-Level Architecture

```
  React SPA (Riya)           ESP32-CAM nodes × 3 (Yuan Cong)
        │                              │
        │ HTTPS / WSS                  │ Local WiFi (MQTT + HTTP image upload)
        ▼                              ▼
 ┌─────────────────┐          ┌──────────────────────────────┐
 │ Flask backend   │◄────────►│ Raspberry Pi 5               │
 │ (this doc)      │  HiveMQ  │  Mosquitto + control logic   │
 │  - REST API     │  TLS 8883│  + per-bay state machine     │
 │  - WebSocket    │          │  + OpenALPR (plate matching) │
 │  - MQTT client  │          │  + image-receiver (HTTP)     │
 │  - HTTPS image  │◄─────────│  (Nyx)                       │
 │    receiver     │  HTTPS   └──────────────────────────────┘
 │  - SQLAlchemy   │  (conflict_strong evidence)
 └────────┬────────┘
          │
          ▼
   PostgreSQL 16 (AWS RDS or EC2-colocated) +
   Object storage for evidence images (S3 or local /var/lib)
```

The backend runs as **one process** that hosts three concurrent concerns:

- **HTTP** (`gunicorn` / `eventlet` worker) serving REST + WebSocket.
- **MQTT client** (`paho-mqtt` in a background thread inside the same process) that
  subscribes to `cloud/bay/+/state` and `cloud/bay/+/event` and publishes
  `cloud/bay/<id>/reservation`.
- **Reservation safety-net sweeper** (APScheduler job in the same process, every
  30 s) that closes reservations whose `no_show` or `conflict_weak` event
  from the Pi was missed (cloud outage, broker restart), keeping the backend's
  view eventually consistent with the authoritative Pi state machine. The
  sweeper never synthesises `conflict_strong` — it has no LPR evidence and
  must wait for the Pi to replay the real event after reconnect.

A single process is chosen deliberately: one SQLAlchemy session factory, one
SocketIO emitter, and no inter-process coordination. With one Raspberry Pi, three
bays, and a handful of concurrent users, vertical scaling on an EC2 `t3.micro` is
sufficient, and the simplicity directly helps Rubric → *Technical Content* and
*Technical Implementation* ("efficient use of hardware and software").

**Ownership split with the Pi.** The authoritative per-bay state machine
(proposal §5.4) runs on the Raspberry Pi (Subsystem C), *not* on the backend.
The Pi owns the merge of sensor readings + **LPR results** + reservation state
into a bay state, drives LEDs **and the per-bay buzzer**, runs OpenALPR
locally, performs plate matching against the reserving user's bound-plate list
(supplied by the backend over MQTT), and emits events on transition. The
backend is a *mirror + business layer*: it persists the state the Pi reports,
manages account/plate CRUD, enforces reservation business rules (booking
window, deposit-only payment surface — pre-auth on booking, full release
on normal completion, penalty capture on contract breach, refund on
strong conflict — proposal §5.5),
**runs the mock-payment service** (in-process; no external bank network),
publishes reservation updates and the bound-plate list back to the Pi,
ingests strong-evidence images uploaded by the Pi for the conflict log,
and handles user-facing concerns (REST, WebSocket, notifications). The Pi
is **payment-agnostic** — it never sees card details, hold amounts, or
penalty events; payment is purely a backend concern triggered by Pi
state-machine events (no_show / conflict_weak / conflict_strong / vehicle
left after check-in).

---

## 4. Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.11 | Required by proposal (Flask); matches team skill set |
| Web framework | Flask 3 + Flask-RESTful patterns | Lightweight, explicit, matches proposal §5.1 |
| ORM | SQLAlchemy 2.x (ORM + Core) | De-facto standard; typed models |
| Migrations | Alembic (via Flask-Migrate) | Repeatable schema migrations; required for rubric "how-to-guide" |
| DB | **PostgreSQL 16** in all environments | User mandate — prod *and* test |
| DB driver | `psycopg` (v3) | Current supported driver; `psycopg2` is legacy |
| MQTT | `paho-mqtt` 2.x | Proposal §5.3 F; TLS to HiveMQ Cloud |
| Realtime | Flask-SocketIO 5 + `python-socketio` | Lower-latency dashboard updates (R4) |
| Auth | Flask-JWT-Extended | Stateless JWT for dashboard users |
| Password hashing | `argon2-cffi` | OWASP recommended |
| Validation | `pydantic` v2 | Request/response schemas, explicit errors |
| Scheduler | `APScheduler` | In-process safety-net sweeper (see §8.4) reconciling reservation state with the Pi when events are lost |
| Testing | `pytest`, `pytest-postgresql`, `pytest-socketio`, `fakeredis`-free (we use pg only) | Real PostgreSQL per-session, template DB cloned per test |
| Container | Docker + docker-compose | Local dev parity with prod |
| CI | GitHub Actions (matrix: Python 3.11, PostgreSQL 16 service container) | Runs migrations + pytest on every PR |
| Deployment | AWS EC2 (Ubuntu 24.04) + systemd + Caddy (auto-HTTPS) | Free-tier friendly; one box for demo |

Why **no SQLite anywhere**: JSONB, enums, `CITEXT`, partial unique indexes, and
`INSERT ... ON CONFLICT (...) DO NOTHING` are used by the design (see
`database-design.md` §3 and §5). Tests must exercise production constraints,
otherwise the rubric row "Testing details, its analysis, limitations" is
undermined by behaviour that only exists in prod.

---

## 5. Project Layout

```
backend/
├── app/
│   ├── __init__.py              # create_app factory
│   ├── config.py                # Dev / Test / Prod settings
│   ├── extensions.py            # db, migrate, jwt, socketio, scheduler
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py              # TimestampMixin, UUID PK helper
│   │   ├── user.py
│   │   ├── licence_plate.py     # per-user bound plates (1–5)
│   │   ├── bay.py
│   │   ├── reservation.py
│   │   ├── bay_event.py
│   │   ├── sensor_reading.py
│   │   ├── conflict.py          # strong/weak kind + plate evidence + image ref
│   │   ├── mock_card.py         # mock-bank simulator card record (proposal §5.6)
│   │   └── payment.py           # transactions ledger: pre_auth / release / refund / penalty_capture (no `capture` — per-time billing is out of scope)
│   ├── schemas/                 # pydantic request/response
│   │   ├── bay.py
│   │   ├── plate.py
│   │   ├── reservation.py       # booking request now includes the card sub-object
│   │   ├── payment.py           # CardDetails input schema; Transaction output schema
│   │   └── auth.py
│   ├── api/
│   │   ├── __init__.py          # blueprint registration
│   │   ├── auth.py              # /api/v1/auth/*
│   │   ├── bays.py              # /api/v1/bays
│   │   ├── plates.py            # /api/v1/users/me/plates  (CRUD)
│   │   ├── reservations.py      # /api/v1/reservations (booking takes card details)
│   │   ├── payments.py          # /api/v1/users/me/payments (transaction history; receipt detail)
│   │   ├── conflicts.py         # /api/v1/conflicts (admin) + Pi image-evidence upload
│   │   └── health.py            # /healthz, /readyz
│   ├── mqtt/
│   │   ├── __init__.py
│   │   ├── client.py            # paho wrapper with reconnect
│   │   ├── topics.py            # topic name constants + parsers
│   │   └── handlers.py          # on_state, on_event dispatchers
│   ├── services/
│   │   ├── bay_service.py       # persist bay state from Pi + mirror events
│   │   ├── plate_service.py     # add/remove/list bound plates; publish updated list to Pi
│   │   ├── reservation_service.py # gates booking on pre-auth; also publishes bound-plate list
│   │   ├── payment_service.py   # mock-payment surface: validate_card / preauthorize / release / charge_penalty / refund (idempotent on (reservation_id, action))
│   │   ├── conflict_service.py  # strong/weak persistence + image retention
│   │   ├── notification_service.py # push on auto_check_in / pending_check_in / deposit_released / refund / penalty / conflict_*
│   │   └── event_service.py     # audit log writer
│   ├── sockets/
│   │   └── events.py            # emit bay.updated, reservation.updated
│   ├── jobs/
│   │   ├── reconcile_reservations.py  # safety-net sweeper (see §8.4)
│   │   └── purge_evidence_images.py   # nightly purge of conflict images > 30 days
│   └── utils/
│       ├── errors.py            # APIError, error handler registration
│       ├── plate.py             # plate normalisation (uppercase, strip spaces)
│       └── time.py              # UTC helpers
├── migrations/                  # Alembic
├── tests/
│   ├── conftest.py              # postgres fixture, app fixture
│   ├── factories.py             # factory_boy objects
│   ├── test_api_auth.py
│   ├── test_api_bays.py
│   ├── test_api_plates.py       # plate CRUD + bound-list publish to Pi
│   ├── test_api_reservations.py # incl. booking-with-card flows and reject paths
│   ├── test_api_payments.py     # transaction-history endpoint; receipt detail
│   ├── test_api_conflicts.py    # admin list + Pi evidence upload
│   ├── test_payment_service.py  # validate_card / preauthorize / release / charge_penalty / refund unit tests + idempotency
│   ├── test_mqtt_ingest.py
│   ├── test_mqtt_commands.py
│   ├── test_event_handlers.py   # auto_check_in / pending_check_in / conflict_strong (refund) / conflict_weak (penalty) / no_show (penalty) / release-on-completion / dedupe
│   ├── test_reconcile_job.py    # safety-net sweeper (synthesises no_show / conflict_weak — never strong; sweeper-driven penalty captures are also idempotent)
│   ├── test_purge_job.py        # 30-day image purge
│   └── test_resilience_reconnect.py
├── scripts/
│   ├── seed.py                  # seed 3 demo bays, 1 demo user with 2 bound plates, ~10 mock cards (varied balances + 1 expired + 1 empty)
│   ├── mock_pi_publisher.py     # emulates Pi (state + events incl. auto_check_in / conflict_strong) for demo without hardware
│   └── mock_pi_subscriber.py    # verifies reservation-command flow incl. bound-plate payload
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml       # postgres + mosquitto + backend
│   └── mosquitto/mosquitto.conf # local broker for dev (stand-in for Pi)
├── deploy/
│   ├── parkreserve.service      # systemd unit
│   └── Caddyfile                # HTTPS reverse proxy
├── .env.example
├── pyproject.toml
├── README.md                    # how-to-guide (rubric: Code → Exemplary)
└── Makefile                     # make dev, make test, make migrate
```

---

## 6. Runtime State Model

The authoritative per-bay state machine lives on the Raspberry Pi (Subsystem C,
proposal §5.4). The backend **mirrors** the Pi's bay state in PostgreSQL for the
dashboard and runs its own **reservation** state machine for business rules
(booking window, deposit pre-auth + release on completion, penalty capture
on contract breach, refund on strong conflict). The two machines are
coupled by MQTT events.

### 6.1 Bay state (mirrored from Pi)

The six states (plus `offline`) and LED + buzzer encodings are defined in
proposal §5.4:

| Bay state | Populated from | LED | Buzzer |
|-----------|----------------|-----|--------|
| `AVAILABLE` | Pi `cloud/bay/<id>/state` | green solid | off |
| `RESERVED` | Pi — set when backend publishes a reservation | yellow solid | off |
| `PENDING_CHECK_IN` | Pi event `pending_check_in` (vehicle in reserved bay; LPR running, failed, or low confidence) | yellow blinking | off |
| `OCCUPIED` | Pi — casual parking, no active reservation (no LPR run, per privacy policy) | red solid | off |
| `RESERVED_CHECKED_IN` | Pi event `auto_check_in` (LPR plate match) or `check_in_confirmed` (manual / QR) | red solid | off |
| `CONFLICT` | Pi event `conflict_strong` (LPR plate mismatch) or `conflict_weak` (grace expired with no manual check-in) | red blinking (~2 Hz) | **on** (~2 Hz, mirrors LED) |
| `OFFLINE` | No heartbeat > 30 s on `cloud/system/heartbeat` | (LED unchanged) | off |

Backend behaviour: treat the bay-state column in `parking_bays` as a mirror.
Do not compute it from sensor readings on the backend — trust the Pi. The
`BayService.apply_state()` method is the *only* code path that writes it, and
every write produces a `bay_events` audit row in the same transaction. The
single `CONFLICT` bay state covers both strong and weak conflicts (proposal
§5.4 — "Both strong and weak conflicts share the same Conflict state"); the
distinction is carried on the matching `conflicts` row (`kind = 'strong' |
'weak'`) and the `bay_events` row (`kind = conflict_strong | conflict_weak`),
because the financial implications differ (see §6.3).

### 6.2 Reservation state (owned by backend)

```
                        cancel (≥15 min before arrival) ─► CANCELLED (release hold,
                       /                                                  no charge)
 [create+pre_auth]     │
   ─► ACTIVE ──────────┼─ cancel (<15 min)             ─► CANCELLED_LATE (+late_cancel
                       │                                                 penalty capture)
                       ├─ pi:pending_check_in          ─► PENDING_CHECK_IN
                       │   (LPR running / failed /             │
                       │    low confidence)                    │
                       │                                       │
                       │                                       ├─ pi:auto_check_in
                       │                                       │   (LPR plate ∈
                       │                                       │    bound plates)   ─► CHECKED_IN
                       │                                       │                          │
                       │                                       ├─ user QR/manual          │
                       │                                       │  +pi:check_in_           │
                       │                                       │  confirmed       ────────┤
                       │                                       │                          │
                       │                                       │                          │ bay state
                       │                                       │                          │ → AVAILABLE
                       │                                       │                          │ (inferred)
                       │                                       │                          ▼
                       │                                       │                      COMPLETED
                       │                                       │                      (release full
                       │                                       │                       deposit; no
                       │                                       │                       parking-fee
                       │                                       │                       capture — out
                       │                                       │                       of scope)
                       │                                       │
                       │                                       ├─ pi:conflict_strong  ─► IN_CONFLICT
                       │                                       │   (LPR plate ∉            (REFUND full hold;
                       │                                       │    bound plates)           facility incident
                       │                                       │                            with plate evidence)
                       │                                       │
                       │                                       └─ sweeper:conflict_weak ─► IN_CONFLICT
                       │                                          (5 min grace expired      (+weak_conflict
                       │                                          with no manual            penalty capture)
                       │                                          check-in)
                       │
                       └─ sweeper:no_show (arrival +5 min, ─► EXPIRED_NO_SHOW (+no_show
                          bay empty)                                            penalty capture)
```

Note: the Pi does not emit a dedicated "session ended" event — proposal §5.3 C
lists only the physical events `auto_check_in`, `pending_check_in`,
`check_in_confirmed`, `conflict_strong`, `sensor_online`, `sensor_offline`.
`conflict_weak` and `no_show` are backend-synthesised timeout events, not Pi
messages. Backend infers `COMPLETED` from the `cloud/bay/<code>/state`
transition `reserved_checked_in → available`
while an active `CHECKED_IN` reservation exists; see §8.3. There is
intentionally **no** direct `ACTIVE → CHECKED_IN` transition: the Pi's state
machine (proposal §5.4) routes every arrival through `Pending Check-in` while
LPR runs. A user-initiated check-in (QR / manual) attempt while the
reservation is still `ACTIVE` (vehicle not yet detected) is rejected HTTP 409
with `code = "vehicle_not_detected_yet"` — the dashboard retries once the
vehicle sensor fires (typically within 2 s).

Although strong and weak conflicts converge on the same `IN_CONFLICT` status
(matching the bay's single `CONFLICT` state in proposal §5.4), the two paths
*differ* in the side-effects committed in the same transaction:

- **Strong** — open a `conflicts` row with `kind='strong'`, `recognised_plate`,
  and `evidence_image_url`; alert admins; **issue a `refund` payment row** for
  the full hold (§6.3) — the user is a victim, not at fault.
- **Weak** — open a `conflicts` row with `kind='weak'`; alert admins; **issue
  a `penalty_capture` payment row** with `penalty_kind='weak_conflict'` against
  the user, plus a `release` for the remainder of the hold.

Business rules (all enforced in `reservation_service.py`, never at the view layer):

- **Booking window (R11):** `0 < expected_arrival_time - now() ≤ 60 min`; rejected with HTTP 422 otherwise.
- **Pre-auth gate (R20):** reject the booking with HTTP 402 if card validation fails (`code="card_invalid"` / `"card_expired"`) or the card has insufficient balance (`code="insufficient_funds"`); the reservation row is never inserted in this branch (§8.2).
- **Uniqueness:** a bay has at most one reservation in `ACTIVE` / `PENDING_CHECK_IN` / `CHECKED_IN` at any time — enforced by a partial unique index (database design §3.5). Concurrent requests that race past the application check are caught by `unique_violation` and translated to HTTP 409 — the just-placed pre-auth deposit is `release`d in the same handler so the loser of the race isn't left with a $10 hold for a reservation they don't have.
- **Reserve bay state check:** reject if the mirrored `bay.state` is `OCCUPIED` / `CONFLICT` (409) or `OFFLINE` (503). `AVAILABLE` is accepted; `RESERVED` / `PENDING_CHECK_IN` / `RESERVED_CHECKED_IN` are caught by the unique index. **Known stale-read window:** the mirror lags the Pi by up to one MQTT round-trip (≤ 2 s in practice). A casual vehicle that occupies a bay just before a reservation request may yield a reservation on a bay the Pi will immediately flag `pending_check_in`; the design accepts this because (a) the Pi always wins — LPR will run on the now-reserved bay and emit `conflict_strong` if the recognised plate is not the holder's, or `auto_check_in` if (improbably) it is, and (b) the user gets a notification within seconds either way.
- **Cancel** is idempotent (repeated calls on an already-`CANCELLED*` reservation return 200 no-op). Only valid from `ACTIVE` or `PENDING_CHECK_IN` — once `CHECKED_IN`, the user is using the bay and ends the session simply by driving away (Pi sensor → bay state `AVAILABLE` → backend infers `COMPLETED`). Other non-cancellable states (`CHECKED_IN` / `COMPLETED` / `EXPIRED_NO_SHOW` / `IN_CONFLICT`) return 409. The 15-min cutoff is computed against `expected_arrival_time`, not against booking time, so even a 20-min-ahead booking has a 5-min safe-cancel window.
- **Check-in (user-initiated, fallback path)** — only used when LPR did not auto-resolve. Accepted from `PENDING_CHECK_IN` (vehicle detected, LPR failed / low confidence) **and from `IN_CONFLICT` when the bay's open `conflicts` row has `kind='weak'`** (proposal §5.5: "the alarm stops when ... a late manual check-in succeeds" — weak only). On a weak-conflict late check-in the handler additionally marks the matching `conflicts` row resolved with `resolution='user_arrived_and_checked_in'`, then transitions the reservation to `CHECKED_IN`; the Pi receives the `check_in` action over MQTT and clears the buzzer + LED. Note that the `weak_conflict` penalty capture (already issued when the grace expired) is NOT refunded — proposal §5.5 frames the loss as the user's failure to verify within the grace, which the late check-in does not undo. A check-in attempt from `ACTIVE` returns HTTP 409 `code = "vehicle_not_detected_yet"` and the dashboard auto-retries on the next `reservation.pending_check_in` WebSocket event. A check-in against an `IN_CONFLICT` reservation whose conflict has `kind='strong'` returns 409 (DB invariant I12 also rejects this resolution). The submitted `bay_code` must equal the reservation's `bay_code` (rejected with HTTP 422 otherwise — input validation, not state conflict). Accepted via either QR scan (`source: "qr"`, persisted as `check_in_mechanism='qr'`) or the manual fallback button (`source: "manual"`, persisted as `check_in_mechanism='manual'`); both go through the same endpoint and `check_in_recognised_plate` is left NULL (DB invariant I14). A second check-in call while already `CHECKED_IN` returns 200 no-op. **Auto check-in via LPR does NOT use this endpoint** — the Pi emits `auto_check_in` over MQTT and the backend transitions the reservation server-side without any user request.

### 6.3 Penalty classification (replaces the prior breach-counter model)

Per proposal §5.5, every "user broke the contract" event now triggers a
direct **penalty capture** against the user's pre-authorized card via
`PaymentService.charge_penalty(reservation_id, penalty_kind=...)`. There is
no separate `breaches` table — the captured penalty IS the user
reliability record (DB design §3.6 / §3.10). The captures fire as follows:

| Event | `penalty_kind` | Default amount | Trigger | Rationale (proposal §5.5) |
|-------|----------------|----------------|---------|---------------------------|
| User cancels < 15 min before `expected_arrival_time` | `late_cancel` | $5 | `POST /reservations/{id}/cancel` handler | The user committed to a slot late enough that re-booking is hard |
| Reconcile sweeper synthesises `no_show` (bay still empty at `expected_arrival_time + 5 min`) | `no_show` | $10 | `dispatch_event(no_show)` | Reservation held a bay no-one used |
| Reconcile sweeper synthesises `conflict_weak` on a bay whose reservation is in `PENDING_CHECK_IN` (LPR did not auto-resolve and the 5 min check-in grace expired with no manual check-in) | `weak_conflict` | $10 | `dispatch_event(conflict_weak)` | A vehicle parked there but no one verified — the user could have checked in manually if it was them |

**Strong-evidence conflicts trigger a refund, not a penalty.** When the Pi
emits `conflict_strong`, the recognised plate is provably *not* one of the
reservation holder's bound plates — the holder is a victim of misuse, not at
fault. The handler calls `PaymentService.refund(reservation_id,
reason='strong_conflict')`, which restores the full hold to the user's mock
card balance. The event is recorded against the *facility* (in `conflicts`
with `kind='strong'`, `recognised_plate`, and the captured image retained 30
days), not against the user. The `penalty_kind` enum intentionally has no
`strong_conflict` value, so even a buggy handler that tried to insert a
penalty row for a strong conflict would fail the
`payments_penalty_kind_only_for_penalty` CHECK at the DB level (DB design
I13 / I18).

For `weak_conflict`, the system retains the **presumption of ownership** —
LPR could not return a confident result, so we cannot prove the misusing
vehicle isn't the holder's, and the holder's failure to verify (via QR /
manual button) within the grace counts as a penalty against them.

**No automatic monthly suspension.** The pre-payment design suspended a
user's reservation privilege after > 2 breaches in a rolling month
(deprecated R12). Proposal §5.5 replaces that mechanism with direct
financial penalties — the user is billed each time, so no separate
suspension trigger is needed. The `BreachService.is_banned(user)` check at
`POST /reservations` time is **removed**. Admins can still suspend a user
manually via the admin view (out-of-band; not implemented as an automatic
backend trigger).

**Normal exit (no penalty).** When a checked-in vehicle leaves, the bay
state transitions `reserved_checked_in → available`; the backend simply
calls `PaymentService.release(reservation_id, reason='completed')` to
return the **full deposit** to the user's card. There is no `capture`
step — per-time parking-fee billing is the facility's exit-side concern
and is out of scope (proposal §5.6). This path is handled in
`on_bay_event` for the `state_changed` transition (see §8.3).

---

## 7. External Interfaces

### 7.1 REST API (v1)

All endpoints are JSON, versioned under `/api/v1`. Responses use `application/json`
and a uniform error envelope `{ "error": { "code": "...", "message": "...", "details": {...} } }`.

| Method | Path | Auth | Purpose | Requirement |
|--------|------|------|---------|-------------|
| POST | `/api/v1/auth/register` | — | Create a user | R3 |
| POST | `/api/v1/auth/login` | — | Exchange credentials for JWT | R3 |
| GET  | `/api/v1/auth/me` | JWT | Current user profile | R3 |
| GET  | `/api/v1/bays` | — | List all bays with current state | R3, R10 |
| GET  | `/api/v1/bays/{code}` | — | Bay detail incl. last sensor reading | R3 |
| GET  | `/api/v1/bays/{code}/events` | JWT admin | Audit log per bay | R5 |
| GET  | `/api/v1/users/me/plates` | JWT | List current user's bound plates | R3, R15 |
| POST | `/api/v1/users/me/plates` | JWT | Bind a plate — body: `{ plate, label? }`. 422 on > 5 plates per user, on duplicate (`unique_violation`), or on bad plate format. Plate is normalised (uppercase, no spaces). On success, publishes the updated bound-plate list to the Pi for any active reservation of this user | R2, R15 |
| DELETE | `/api/v1/users/me/plates/{plate}` | JWT | Remove a bound plate. Re-publishes the updated list to the Pi for any active reservation | R2, R15 |
| POST | `/api/v1/reservations` | JWT | Reserve a bay — body: `{ bay_code, expected_arrival_time, card: { number, cvv, expiry_year, expiry_month, holder_name } }`. The card sub-object is validated against the mock-bank table; the booking transaction inserts the reservation row and the `pre_auth` payment row atomically (R20). 422 if `expected_arrival_time - now() > 60 min` (R11) or if user has zero bound plates (auto check-in is impossible); 402 if card validation fails (unknown card / wrong CVV / expired) or balance < deposit amount; 409 if bay is unavailable. On success, publishes `cloud/bay/<code>/reservation` with `action: "create"` *including* the user's bound-plate list, and returns the reservation row plus the pre-auth confirmation `{ deposit_cents }` | R2, R3, R11, R15, R18, R20 |
| GET  | `/api/v1/reservations` | JWT | Current user's reservations | R3 |
| GET  | `/api/v1/reservations/{id}` | JWT | Reservation detail | R3 |
| POST | `/api/v1/reservations/{id}/check-in` | JWT | **Fallback** check-in — body: `{ bay_code, source: "qr"\|"manual" }`. Used only when LPR did not auto-resolve. Accepted from `PENDING_CHECK_IN` and from `IN_CONFLICT` when the open `conflicts` row has `kind='weak'` (proposal §5.5: weak conflict can be cleared by a late manual check-in; the matching `conflicts` row is resolved with `user_arrived_and_checked_in` and the Pi clears the buzzer/LED — the prior `weak_conflict` penalty capture is NOT refunded). Persists `check_in_mechanism = body.source` (`qr` or `manual`) on the reservation; `check_in_recognised_plate` stays NULL (DB I14). 422 if `bay_code` ≠ reservation's bay (input validation); 409 `code="vehicle_not_detected_yet"` if reservation is still `ACTIVE`; 409 if `IN_CONFLICT` with `kind='strong'` (cannot be cleared by user — proposal §5.5; DB I12 also rejects this); 409 if other non-cancellable state (`COMPLETED` / `EXPIRED_NO_SHOW` / `CANCELLED*`); 200 no-op if already `CHECKED_IN`. Auto check-in is server-driven via the Pi `auto_check_in` event and never reaches this endpoint | R2, R13 |
| POST | `/api/v1/reservations/{id}/cancel` | JWT | Release the reservation. If ≥ 15 min to arrival, calls `PaymentService.release(reservation_id, reason='clean_cancel')` — full hold returned to card. If < 15 min, calls `PaymentService.charge_penalty(reservation_id, penalty_kind='late_cancel')` and releases the remainder. Idempotent | R2, R12, R18, R19 |
| GET  | `/api/v1/users/me/payments` | JWT | Current user's transaction history (pre-auth / release / refund / penalty_capture) ordered by `occurred_at DESC`, paginated. Drives the dashboard's "your charges" tab | R5, R18 |
| GET  | `/api/v1/users/me/payments/{id}` | JWT | Single transaction detail (receipt) | R5, R18 |
| GET  | `/api/v1/conflicts` | JWT admin | Unresolved conflicts (with `kind: "strong"\|"weak"`, `recognised_plate?`, `evidence_image_url?` for strong) | R6 |
| GET  | `/api/v1/conflicts/{id}/evidence` | JWT admin | Stream the captured image (404 once `image_purge_at < now()`) | R6, R16 |
| POST | `/api/v1/conflicts/{id}/resolve` | JWT admin | Clear a conflict — body: `{ resolution }` | R6 |
| POST | `/api/v1/internal/conflicts/evidence` | mTLS / shared-token | **Pi → backend** image upload for `conflict_strong`. Multipart: `bay_code`, `source_event_id`, `recognised_plate`, JPEG body. Idempotent on `source_event_id` | R6, R16 |
| GET  | `/healthz` | — | Liveness | ops |
| GET  | `/readyz` | — | DB + MQTT readiness | ops |

Every write endpoint is idempotent where meaningful (e.g. cancelling an already
cancelled reservation is a 200 no-op, not a 500).

### 7.2 WebSocket (Socket.IO, namespace `/ws`)

Events emitted by server (R4):

- `bay.updated` — `{ code, state, last_distance_cm?, reservation_id?, updated_at }`
- `reservation.updated` — `{ id, bay_code, status, user_id, expected_arrival_time, ... }`
- `reservation.pending_check_in` — `{ id, bay_code, detected_at, check_in_grace_expires_at }` — fires the dashboard's "please check in manually" prompt when LPR did not auto-resolve (R14)
- `reservation.auto_checked_in` — `{ id, bay_code, checked_in_at, recognised_plate }` — fires the "you're checked in at Bay X" confirmation (R14)
- `payment.deposit_released` — `{ reservation_id, amount_cents, occurred_at, reason: "completed"\|"clean_cancel" }` — fires the "your deposit of $X.YZ has been released" receipt on normal exit or clean cancel (R14)
- `payment.refunded` — `{ reservation_id, amount_cents, occurred_at, reason: "strong_conflict" }` — fires the "your reservation was disrupted — full refund issued" notification (R14)
- `payment.penalty_captured` — `{ reservation_id, penalty_kind: "late_cancel"\|"no_show"\|"weak_conflict", amount_cents, occurred_at }` (R14)
- `plate.updated` — `{ user_id, plates: [...] }` — emitted to the user's room when their bound list changes
- `conflict.raised` — `{ id, bay_code, kind: "strong"\|"weak", recognised_plate?, detected_at }` — admin channel
- `conflict.resolved` — `{ id, bay_code, resolved_at, resolution }`

Events accepted from client:

- `subscribe` — `{ bay_codes?: [...] }` — default subscribes to all bays.

### 7.3 MQTT topics (cloud broker — HiveMQ)

| Topic | Direction | Payload | QoS |
|-------|-----------|---------|-----|
| `cloud/bay/<code>/state` | Pi → Backend | `{ "state": <bay_state>, "last_distance_cm": <num>, "ts": <iso8601>, "event_id": <uuid> }` where `<bay_state>` is one of the six states in §6.1 | 1 |
| `cloud/bay/<code>/event` | Pi → Backend | `{ "event": "auto_check_in"\|"pending_check_in"\|"check_in_confirmed"\|"conflict_strong"\|"sensor_online"\|"sensor_offline", "reservation_id"?: "...", "recognised_plate"?: "ABC123", "lpr_confidence"?: 0.92, "ts": ..., "event_id": <uuid> }`. `recognised_plate` and `lpr_confidence` are present on `auto_check_in` and `conflict_strong` only. `conflict_weak` / `no_show` are internal-only events synthesised by the reconcile sweeper and never published by the Pi | 1 |
| `cloud/bay/<code>/reservation` | Backend → Pi | `{ "action": "create"\|"cancel"\|"check_in"\|"update_plates"\|"release"\|"expire_check_in", "reservation_id": "...", "user_id": "...", "bound_plates": ["ABC123","XYZ789"], "expected_arrival_time"?: ..., "reason"?: "no_show"\|"completed"\|"abandoned"\|"admin_override", "ts": ... }`. `bound_plates` is the reserving user's *current* bound list — published on every `create` and re-published on `update_plates` whenever the user adds/removes a plate while a reservation is active. `reason` is required only when `action="release"` | 1 |
| `cloud/system/heartbeat` | Pi → Backend | `{ "pi_id": "pi-01", "ts": ... }` every 10 s | 0 |
| `cloud/system/resync`    | Backend → Pi | Empty payload; sent on backend reconnect to request bay-state replay (Pi also re-emits the latest `cloud/bay/<code>/reservation` for any open reservation, with the bound-plate list) | 1 |

Conflict-evidence images are **not** carried over MQTT — JPEG payloads are
unsuitable for the broker. The Pi uploads them out-of-band over HTTPS to
`POST /api/v1/internal/conflicts/evidence` (proposal §5.3 D rationale; §7.1).

All payloads are validated by pydantic schemas in `app/mqtt/topics.py`.
Invalid messages are logged and dropped — never crash the consumer. The
backend now distinguishes **Pi-originated** event payloads from
**backend-internal** timeout events at schema level: the MQTT consumer accepts
only the physical Pi events listed above, while `conflict_weak` / `no_show`
are dispatched internally by the reconcile sweeper. The pre-LPR design's
single `conflict_detected` event has been split into `conflict_strong`
(LPR plate mismatch) and `conflict_weak` (LPR did not auto-resolve and grace
expired); `auto_check_in` is new (proposal §5.4 / §5.5). The previous
`barrier_opened` / `barrier_closed` events are removed (no physical barriers
— proposal §5.6).

---

## 8. Subsystem-Level Design Notes

### 8.1 MQTT client (R1, R2, R7, R8)

- Single shared `paho.mqtt.Client` started in `create_app()` via an `AppContext`
  hook when `ENABLE_MQTT=true`. In tests, `ENABLE_MQTT=false` and handlers are
  invoked directly.
- TLS required when `MQTT_TLS=true`. Credentials come from env vars
  (`MQTT_USERNAME`, `MQTT_PASSWORD`).
- Subscribes to `cloud/bay/+/state`, `cloud/bay/+/event`,
  `cloud/system/heartbeat`. Publishes to `cloud/bay/<code>/reservation` and
  `cloud/system/resync`.
- **Reconnection strategy**: `paho`'s built-in exponential backoff (min 1 s, max
  60 s). On reconnect the client re-subscribes and publishes to
  `cloud/system/resync` — the Pi responds by republishing the latest state for
  every bay. This closes R7.
- Inbound dispatch:
    - `cloud/bay/<code>/state` → `bay_service.apply_state()` — mirror only, no
      derivation.
    - `cloud/bay/<code>/event` → `event_handler.dispatch()` — routes
      `auto_check_in` / `pending_check_in` / `check_in_confirmed` /
      `conflict_strong` / `conflict_weak` / `no_show` to the corresponding
      service method. Per §8.3, `auto_check_in` and `conflict_strong` carry
      `recognised_plate`; `conflict_strong` is also paired with the
      out-of-band image upload on `/api/v1/internal/conflicts/evidence`.

### 8.2 Reservation service (R2, R3, R8, R11, R12, R18, R20)

- All state mutations inside `with db.session.begin():` so the audit event,
  the payment row(s), and the reservation update commit atomically.
- On `POST /reservations`:
    1. Validate `expected_arrival_time - now() ≤ 60 min` (R11). Reject with 422.
    2. Reject with 422 if the user has zero bound plates (auto check-in is
       impossible; the user can still bind a plate and retry — proposal §5.5).
    3. Call `PaymentService.preauthorize(card, deposit_cents=settings.DEPOSIT_CENTS)`
       (R18, R20):
       - `validate_card` against `mock_cards` (number / CVV / expiry); reject
         402 on miss with `code="card_invalid"` / `code="card_expired"`.
       - `SELECT ... FOR UPDATE` on the matching card row (serialises
         concurrent bookings against the same card).
       - Reject 402 with `code="insufficient_funds"` if
         `balance_cents < deposit_cents`.
       - Decrement balance, reserve a placeholder `pre_auth` row keyed
         `pre_auth:<reservation_id>`. The reservation row hasn't been
         inserted yet — see step 4; the placeholder approach + deferrable
         FK keeps the booking transaction single-pass.
    4. INSERT the reservation row (partial unique index in DB catches the
       double-book race — translate `unique_violation` to 409 and
       `release` the just-placed deposit so we don't strand the user's
       $10). The Pi-bound MQTT publish (step 5) only fires after the
       transaction commits.
    5. Publish `cloud/bay/<code>/reservation` with `action: "create"` and
       include the user's *current* bound-plate list so the Pi can match LPR
       results locally.

  Return a 201 body containing the reservation plus
  `{ payment: { deposit_cents } }` so the dashboard can show the pre-auth
  confirmation without a follow-up GET. There is no
  `expected_max_fee_cents` field — per-time parking-fee billing is out
  of scope for this prototype (proposal §5.6).

- On cancel: idempotent. If `expected_arrival_time - now() ≥ 15 min`,
  call `PaymentService.release(reservation_id, reason='clean_cancel')` —
  full deposit restored to the card, no charge. If `< 15 min`, call
  `PaymentService.charge_penalty(reservation_id,
  penalty_kind='late_cancel')` (default $5), then
  `PaymentService.release` for the remainder. Both paths publish
  `reservation` with `action: "cancel"` to the Pi after the transaction
  commits.
- On user-initiated check-in (QR / manual fallback only — auto check-in is
  handled by the `auto_check_in` event handler, §8.3):
    1. Accept if reservation is in `PENDING_CHECK_IN`, **or** in `IN_CONFLICT`
       when the open `conflicts` row has `kind='weak'` (proposal §5.5: a late
       manual check-in clears a weak conflict). Reject 409
       `code="vehicle_not_detected_yet"` from `ACTIVE`; reject 409 from
       `IN_CONFLICT` with `kind='strong'` (DB invariant I12 also rejects this
       resolution at the row level); reject 409 from any other non-cancellable
       state.
    2. Verify `body.bay_code == reservation.bay_code` (defeats "scanned the
       wrong QR") → 422 otherwise.
    3. In one transaction: if entering from `IN_CONFLICT/weak`, mark the
       matching `conflicts` row resolved with
       `resolution='user_arrived_and_checked_in'` and `resolved_at=NOW()`
       (the existing `weak_conflict` penalty-capture payment row is left in
       place — proposal §5.5 attributes the loss to the user's failure to
       verify within the grace, which the late check-in does not undo;
       no `refund` is issued). Set
       `reservation.status='CHECKED_IN'`, `checked_in_at=NOW()`,
       `check_in_mechanism = body.source` (`qr` or `manual`), and leave
       `check_in_recognised_plate` NULL (DB invariant I14).
    4. Publish `cloud/bay/<code>/reservation` with `action: "check_in"` so the
       Pi clears the buzzer + switches the LED to red solid. The Pi echoes
       with `check_in_confirmed`, which is idempotent and serves as an audit
       acknowledgement.
- On plate add/remove (`PlateService`): if the user has any reservation in
  `ACTIVE` / `PENDING_CHECK_IN` / `CHECKED_IN`, publish
  `cloud/bay/<code>/reservation` with `action: "update_plates"` and the new
  bound-plate list, so the Pi's LPR matcher uses the freshest set. This
  addresses proposal §5.5's "any of the reserving user's *currently* bound
  plates counts as a valid match".
- Emits a domain event (Python object) **after** commit; the emitter routes it
  to both the Socket.IO namespace (R4) and the MQTT publisher (R2). Splitting
  the emit from the transaction avoids the "published then rolled back" bug.
- **Known limitation (committed-but-not-published):** if the process crashes
  between commit and publish, the reservation exists in DB but no MQTT
  message was ever sent. The safety-net sweeper (§8.4) only covers *outbound*
  expirations, not create/cancel/check-in publishes. Accepted trade-off for
  the project's scope; a production-grade fix would be a `outbox_events`
  table written inside the same transaction and drained by a separate
  publisher loop (transactional outbox pattern). Mentioned in the final
  report's limitations section.

### 8.3 Event handlers & conflict persistence (R6, R14, R16)

The backend no longer detects conflicts or check-ins — the Pi state machine
does both (proposal §5.4 + LPR pipeline). The backend receives events and
reacts:

- `pending_check_in` → transition reservation to `PENDING_CHECK_IN`, insert a
  `bay_events` row, emit WebSocket `reservation.pending_check_in`, and call
  `notification_service.push_pending_check_in(user)` (R14). Record
  `check_in_grace_expires_at = event.ts + 5 min` on the reservation. (This
  fires when LPR fails or returns low confidence; if LPR returns a confident
  match the Pi skips this event and emits `auto_check_in` directly.)
- `auto_check_in` → transition reservation directly to `CHECKED_IN`, set
  `checked_in_at = event.ts`, `check_in_mechanism = 'auto_lpr'`, and
  `check_in_recognised_plate = event.recognised_plate` (proposal §5.3 F /
  §5.5: "recognised plate is logged with the reservation record"; DB
  invariant I14 enforces both columns are populated together). Also persist
  the plate on the bay_event payload for the audit log. Emit WebSocket
  `reservation.auto_checked_in`, and call
  `notification_service.push_auto_check_in(user, bay, plate)` ("you're checked
  in at Bay X"). The corresponding image is **not** retained (proposal §5.5
  privacy policy: discarded immediately on successful auto check-in). No user
  action is required — this is the typical happy path.
- `check_in_confirmed` → echo of a successful user-initiated QR / manual
  check-in. Idempotent — if reservation is already `CHECKED_IN` (we set it on
  the user's request in §8.2), this is just an audit acknowledgement.
- `conflict_strong` → open a `conflicts` row with `kind='strong'`,
  `recognised_plate`, and (if the matching evidence-image upload has arrived)
  `evidence_image_url` and `image_purge_at = detected_at + 30 days`; if the
  reservation associated with the bay is in `PENDING_CHECK_IN`, transition it
  to `IN_CONFLICT`. **Issue a full refund** via
  `PaymentService.refund(reservation_id, source_event_id=event.event_id,
  reason='strong_conflict')` — restores the held amount to the reserving
  user's mock card, since the user is a victim (proposal §5.5). The
  `conflict_strong` handler must **never** call `charge_penalty` —
  enforced at the DB level by the absence of `strong_conflict` from the
  `penalty_kind` enum (DB I13 / I18). Emit WebSocket `conflict.raised`
  (with `kind: "strong"` + plate evidence) and `payment.refunded` to the
  user; call `notification_service.push_conflict_alert(admins,
  kind='strong', plate=...)` and
  `notification_service.push_strong_conflict_refund(user, amount)` (R14).
- `conflict_weak` → open a `conflicts` row with `kind='weak'` (no
  `recognised_plate`, no image — proposal §5.5: weak conflicts retain no
  evidence); if the reservation is in `PENDING_CHECK_IN`, transition it to
  `IN_CONFLICT` **and call `PaymentService.charge_penalty(reservation_id,
  penalty_kind='weak_conflict', source_event_id=event.event_id)`** (default
  $10) followed by `release` for the remainder of the hold. Emit WebSocket
  `conflict.raised` (with `kind: "weak"`) and `payment.penalty_captured`
  to the user; call
  `notification_service.push_conflict_alert(admins, kind='weak')`.
- `no_show` → transition reservation to `EXPIRED_NO_SHOW`, then call
  `PaymentService.charge_penalty(reservation_id, penalty_kind='no_show',
  source_event_id=event.event_id)` (default $10) followed by `release` for
  the remainder. Emit WebSocket `payment.penalty_captured` to the user.

**Conflict-evidence image ingest.** The Pi uploads a JPEG to
`POST /api/v1/internal/conflicts/evidence` (multipart) shortly after emitting
`conflict_strong`. The handler:

1. Looks up the `conflicts` row by `source_event_id` (created by the
   `conflict_strong` handler — the two flows can race, so the upload handler
   creates a placeholder row if none exists yet, and the MQTT handler upserts
   on the same `source_event_id`).
2. Stores the image to object storage (S3 in production, local
   `/var/lib/parkreserve/evidence/<conflict_id>.jpg` in dev).
3. Sets `evidence_image_url` and `image_purge_at = detected_at + 30 days` on
   the conflict row.
4. The nightly `purge_evidence_images` job deletes the object and clears
   `evidence_image_url` once `image_purge_at < now()`. The conflict row itself
   is retained for the audit trail; only the image is purged.

**Reservation completion + deposit release.** Completion is not a Pi event;
it is inferred in `BayService.apply_state()` whenever a bay transitions
from `reserved_checked_in` or `pending_check_in` back to `available` (the
user drove off). If an active `CHECKED_IN` reservation exists, in the same
transaction as the bay mirror write the handler:

1. Transitions the reservation to `COMPLETED` with `completed_at = event.ts`.
2. Calls `PaymentService.release(reservation_id, reason='completed',
   source_event_id=event.event_id)` — restores the **full deposit** to the
   user's card, emits `payment.deposit_released` over WebSocket, pushes
   the "deposit released" receipt (R14).

There is **no** `capture` step. Per-time parking-fee billing is the
facility's exit-side concern (gate / kiosk) and is out of scope (proposal
§5.6). The user pays for the parking session through the facility's own
billing path, which our system does not touch.

**Edge case — weak conflict followed by late check-in then completion.**
If a weak-conflict penalty was already captured (the deposit is gone) and
the user then late-checked-in (`reservation.status` was set back to
`CHECKED_IN`), the deposit's remaining amount is $0. The release call in
step 2 above queries the remaining-deposit value before issuing the
`payments` row and skips the row entirely when zero (or writes an
amount-0 audit row — see DB design §6.3a / §3.11). The completion path
is therefore safe: no double-charge, no spurious release.

**Edge case — vehicle left from `PENDING_CHECK_IN`.** If the bay was in
`PENDING_CHECK_IN` when the vehicle left (the user arrived, was never
auto- or manually-checked-in, then drove off before the grace expired —
rare in practice), no penalty fires (`conflict_weak` only fires once the
grace expires), and the deposit is released via
`PaymentService.release(reason='clean_cancel')`. The reservation
transitions to `COMPLETED` with no charge.

All handlers (including the completion-inference path and the payment
side-effects) are idempotent on `source_event_id` and on the
`(reservation_id, action)` idempotency key — the Pi stamps every outbound
MQTT message with a UUID, and the DB enforces uniqueness on that column in
`bay_events`, `conflicts`, and (partial unique) `payments` (database
design §3.7 / §3.9 / §3.10 / §3.11, invariants I9 + I16). Replays after
backend reconnect are no-ops, so penalties are never double-charged and
the same evidence image is not double-stored.

### 8.4 Safety-net sweeper (R8)

APScheduler cron `*/30 * * * * *` (every 30 s). The Pi is the primary source of
truth; this job closes the window where the backend was offline during a Pi
event and the event was never replayed (HiveMQ session queue expired, broker
restart, etc.). It selects:

- `ACTIVE` reservations with `expected_arrival_time + 5 min < now()` and the
  latest mirrored bay state is `AVAILABLE` → synthesise a `no_show`.
- `PENDING_CHECK_IN` reservations with `check_in_grace_expires_at < now()` →
  synthesise a `conflict_weak`. (The sweeper *only* synthesises weak — it has
  no LPR evidence, so it cannot manufacture a strong-evidence conflict; if the
  Pi truly observed an LPR mismatch it will replay the event after reconnect.)

Both code paths reuse `event_handler.dispatch()`, which means they share the
penalty-capture logic in §8.3. For idempotency, the sweeper generates a
deterministic `source_event_id = uuid5(namespace,
f"{reservation_id}:{kind}:safety_net")` so (a) repeated sweeper runs
collapse to a single bay-event row, and (b) a real Pi event arriving after
the sweeper wins on whichever `source_event_id` lands first — the loser's
`INSERT ... ON CONFLICT (source_event_id) DO NOTHING` is a no-op. The
penalty-capture payment row is *additionally* keyed on
`(reservation_id, 'penalty_capture', penalty_kind)` (I16), so even a
sweeper-then-Pi race that somehow produced two distinct
`source_event_id`s for the same logical event would still collapse to a
single charge.

This job *never* drives LEDs directly — the Pi remains the LED authority.
If the Pi is actually alive but momentarily out of touch with the cloud,
its local state is already correct; the sweeper only corrects the backend
mirror and the payments ledger.

### 8.5 Notifications (R14)

`notification_service.py` is a thin abstraction with two drivers:

- **WebSocket** (always-on; used for in-app prompts).
- **Web Push / email** (pluggable; out of core scope — a stub that logs the
  payload is acceptable for M3, a real driver is a stretch for M4).

Call sites:

- `auto_check_in` → notify reservation holder ("you're checked in at Bay X").
- `pending_check_in` → notify reservation holder ("vehicle detected — please
  check in manually within 5 min").
- **deposit released on completion** → notify reservation holder ("your
  deposit of $X.YZ has been released — see receipt") with the receipt id.
  No parking-fee notification fires from us — that flow is the facility's
  exit-side billing concern (proposal §5.6).
- **strong-conflict refund** → notify reservation holder ("your reservation
  was disrupted — full refund issued") with the refund amount. (This is
  *new* for the holder; previously holders received no notification on
  `conflict_strong`. Now they do, because money is involved and they need
  to see the refund hit their card.)
- **penalty captures** (`late_cancel`, `no_show`, `weak_conflict`) → notify
  reservation holder ("penalty captured: …") with the captured amount and
  the reason.
- `conflict_strong` / `conflict_weak` → notify admins subscribed to the
  `/admin` channel; `conflict_strong` payloads include the recognised
  plate; both include the resulting refund/penalty action.

The reservation holder is *still not* notified about the `conflict_strong`
*event itself* (audible alarm + admin alert remain the in-the-moment
response — proposal §5.5 frames the holder as a victim, and the system has
no proof the holder is even on-site). The new strong-conflict refund
notification is a separate, after-the-fact message about money having been
returned to their card. The reservation also surfaces in their dashboard
history with `IN_CONFLICT` status so they can see what happened.

### 8.6 Resilience to cloud disconnection (R7)

The backend never "pushes" synchronously to the Pi. Reservation updates are
published to MQTT with QoS 1 and `retained=false`; if the Pi is briefly offline,
HiveMQ queues them per session. If the backend itself is offline, the Pi
continues local sensing + LED control using its own state view (proposal §5.3 C
and §5.3 E). When the backend restarts it re-subscribes and publishes on
`cloud/system/resync` — idempotent inserts plus the event-id dedupe in §8.3
reconcile state.

### 8.7 Observability (rubric: *Technical Content → analysis*)

- Structured JSON logs via `structlog` — every request and every MQTT message is
  logged with a correlation id.
- Prometheus `/metrics` endpoint exposes: `mqtt_messages_total{topic,result}`,
  `reservation_latency_seconds` (histogram for R8 end-to-end latency),
  `auto_check_in_latency_seconds` (vehicle detection → "you're checked in"),
  `bay_state_transitions_total{from,to}`,
  `payments_total{action}` (over `pre_auth`, `release`, `refund`,
  `penalty_capture` — **no `capture`**; per-time billing is out of scope),
  `payments_penalty_total{penalty_kind}` (over `late_cancel`, `no_show`,
  `weak_conflict`),
  `payments_amount_cents_total{action}` (sum of released / refunded /
  penalty-captured cents — feeds the operator-revenue panel; only
  penalty-captured contributes to operator revenue, the rest are
  return-to-card flows),
  `payments_idempotency_replays_total` (counts retries that hit the
  `idempotency_key` UNIQUE — a non-zero healthy steady-state proves
  idempotency is exercised),
  `conflicts_total{kind}` (over `strong`, `weak`),
  `lpr_outcome_total{outcome}` (over `auto_check_in`, `mismatch_strong`,
  `low_confidence`),
  `notifications_sent_total{kind}`.
- A one-page Grafana board (`deploy/grafana/parkreserve.json`) visualises the
  metrics that map directly onto the testing plan thresholds in proposal §7.3
  (State Machine correctness, LPR Recognition Accuracy, Auto Check-in
  Correctness, Strong/Weak Conflict, No-show / Auto-release, **Mock Payment
  Correctness** — pre-auth/capture/penalty/refund counts and idempotency
  replays), making the final-report evaluation section data-driven.

### 8.8 Mock-payment service (R18, R19, R20)

`payment_service.py` is the in-process mock-bank gateway. It exposes
five methods, each idempotent on a deterministic `(reservation_id,
action[, qualifier])` key (R19, DB design §3.11 / I16). Every method is
a thin wrapper around a single `with db.session.begin():` transaction
that touches `mock_cards` and `payments` together.

> **There is intentionally no `capture` method.** Per-time parking-fee
> billing is the facility's exit-side concern (gate / kiosk) and is out
> of scope for this prototype — see proposal §5.6. The deposit is
> *only* used to back the reservation contract; on a normal session it
> is released in full at completion.

| Method | Effect | Idempotency-key shape |
|--------|--------|-----------------------|
| `validate_card(card_details, today)` | Look up `mock_cards` by number + CVV; check expiry. Returns the card row or raises `CardInvalidError` / `CardExpiredError`. **No DB writes.** | n/a (read-only) |
| `preauthorize(card, reservation_id, deposit_cents)` | `SELECT … FOR UPDATE` on the card; raise `InsufficientFundsError` if `balance < deposit_cents`; `UPDATE balance -= deposit_cents`; INSERT `payments` row with `action='pre_auth'`, key `pre_auth:<reservation_id>` | `pre_auth:<reservation_id>` |
| `release(reservation_id, reason)` | Compute the *remaining* deposit on this reservation (`pre_auth.amount` minus prior `release` / `refund` / `penalty_capture` amounts). If > 0, INSERT `payments` row with `action='release'`, amount = remaining; `UPDATE mock_cards.balance += amount`. If 0, no-op (audit-only row optional). | `release:<reservation_id>:<reason>` (`clean_cancel` / `completed` / `remainder`) |
| `refund(reservation_id, source_event_id, reason='strong_conflict')` | INSERT `payments` row with `action='refund'`; `UPDATE mock_cards.balance += deposit_amount`. Conceptually equivalent to `release` but flagged in the user-facing receipt as a victim refund | `refund:<reservation_id>:strong_conflict` |
| `charge_penalty(reservation_id, penalty_kind, source_event_id?)` | Look up the configured penalty amount for `penalty_kind` (default $5/$10/$10); INSERT `payments` row with `action='penalty_capture'`, `penalty_kind` set, no balance change. Caller (event handler / cancel handler) is responsible for following up with `release` for the remainder of the deposit | `penalty_capture:<reservation_id>:<penalty_kind>` |

**Integration shape with a real gateway.** The interface is intentionally
provider-agnostic: a future swap to Stripe / Adyen / Worldpay (proposal
§5.7) replaces `payment_service.py` only. The reservation service (§8.2)
and event handlers (§8.3) call into this surface and would not need to
change. In a real deployment the `card` parameter would be a
gateway-provided token rather than raw card details (PCI-DSS) — the
prototype takes raw details only because no real money flows (proposal
§5.6). A real deployment would *also* swap in a `capture` method (and a
matching exit-side billing flow), since real gateways are by-time —
that's exactly the integration the production roadmap calls for.

**Pricing values** (defaults in `Settings`, configurable per facility):

| Setting | Default | Notes |
|---------|---------|-------|
| `DEPOSIT_CENTS` | 1000 (= $10) | Pre-auth deposit at booking. Sized to comfortably exceed the largest single penalty so a partial-penalty + remainder-release flow is always demonstrable, while staying small enough to be reasonable for users. |
| `LATE_CANCEL_PENALTY_CENTS` | 500 (= $5) | Captured on `< 15 min` cancel |
| `NO_SHOW_PENALTY_CENTS` | 1000 (= $10) | Captured on Pi `no_show` (or sweeper-synthesised) |
| `WEAK_CONFLICT_PENALTY_CENTS` | 1000 (= $10) | Captured on Pi `conflict_weak` |

> No `HOURLY_RATE_CENTS` / `MINIMUM_CAPTURE_CENTS` settings any more —
> per-time billing is out of scope (proposal §5.6). When the no-show or
> weak-conflict penalty equals the full deposit ($10 = $10), the
> follow-up `release` writes amount = 0 (or is skipped).

**Mock-bank seed.** `scripts/seed.py` and the
`20260421_03_seed_mock_cards` migration insert ~10 demo cards (DB design
§8) with varied balances, including one expired and one zero-balance card
to exercise the rejection paths in tests. The seed is checked into source
because there is nothing sensitive to keep out — these are not real cards.

---

## 9. Testing Strategy (rubric: *Technical Content*, *Code*, proposal §7.3)

All tests run against **real PostgreSQL**. No mocks of the DB. MQTT is tested two
ways: (a) unit tests against handler functions with synthesised payloads; (b)
integration tests that run a local `mosquitto` in docker-compose.

### 9.1 Test infrastructure

- `tests/conftest.py` uses `pytest-postgresql` to spin one PostgreSQL cluster per
  test session, create a template DB with migrations applied, and `CREATE DATABASE
  ... TEMPLATE ...` per test function for isolation. This runs in < 50 ms/test.
- `factory_boy` builds realistic User / Bay / Reservation / MockCard / Payment fixtures.
- MQTT integration tests use `docker-compose -f docker/docker-compose.test.yml up`
  started once per session via a pytest plugin hook.

### 9.2 Test inventory (mapped to proposal §7.3 metrics)

| Test module | Proposal metric | Target |
|-------------|-----------------|--------|
| `test_api_bays.py::test_list_returns_all_three_bays_after_seed` | Dashboard accuracy | 100 % |
| `test_api_plates.py::test_add_plate_publishes_updated_list_for_active_reservation` | Plate management (R15) + Pi sync (R2) | 100 % |
| `test_api_plates.py::test_cannot_bind_more_than_five_plates` | Plate management (R15) | 100 % |
| `test_api_plates.py::test_remove_plate_republishes_to_pi` | Plate management (R15) | 100 % |
| `test_api_reservations.py::test_reserve_emits_command_with_bound_plates` | Reservation correctness + R2 plate payload | 100 % |
| `test_api_reservations.py::test_reserve_rejected_when_user_has_no_plates` | R15 (auto check-in impossible without plates) | 100 % |
| `test_api_reservations.py::test_reserve_rejected_when_beyond_one_hour_window` | Booking window (R11) | 100 % |
| `test_api_reservations.py::test_reserve_rejected_when_card_invalid` | Card validation (R18, proposal §7.3 Card Validation) | 100 % |
| `test_api_reservations.py::test_reserve_rejected_when_card_expired` | Card validation (R18) | 100 % |
| `test_api_reservations.py::test_reserve_rejected_when_card_balance_insufficient` | Card validation (R18) | 100 % |
| `test_api_reservations.py::test_reserve_writes_pre_auth_row_and_decrements_card_balance` | Pre-auth + booking transaction atomicity (R20, DB I15) | 100 % |
| `test_api_reservations.py::test_double_post_reserve_with_same_idempotency_key_collapses_to_one_pre_auth` | Idempotency under HTTP retry (R19, DB I16) | 100 % |
| `test_api_reservations.py::test_cancel_idempotent` | Reservation correctness + cancel idempotency (R19) | 100 % |
| `test_api_reservations.py::test_clean_cancel_releases_full_hold` | Free-cancel window (proposal §7.3) | 100 % |
| `test_api_reservations.py::test_late_cancel_captures_penalty` | Penalty capture (R12, proposal §7.3 Penalty Capture) | 100 % |
| `test_api_reservations.py::test_double_reserve_rejected_409` | Partial unique index | 100 % |
| `test_api_reservations.py::test_check_in_rejects_mismatched_bay_code` | Check-in QR verification (R13) | 100 % |
| `test_api_reservations.py::test_check_in_rejected_when_in_strong_conflict` | Strong-conflict immutability (proposal §5.5; DB I12) | 100 % |
| `test_api_reservations.py::test_late_check_in_clears_weak_conflict_and_keeps_penalty` | Weak-conflict late check-in (proposal §5.5: alarm clears, penalty capture stands — no refund) | 100 % |
| `test_api_reservations.py::test_check_in_persists_mechanism_and_plate_columns` | `check_in_mechanism` + `check_in_recognised_plate` (DB I14) | 100 % |
| `test_event_handlers.py::test_auto_check_in_transitions_to_checked_in_and_notifies_user` | Auto check-in (proposal §7.3) | 100 % |
| `test_event_handlers.py::test_pending_check_in_notifies_user_and_emits_ws` | Notifications + state (R14) | 100 % |
| `test_event_handlers.py::test_conflict_strong_refunds_user_and_logs_facility_incident` | Strong conflict (R6) — full refund, no penalty (DB I13) | 100 % |
| `test_event_handlers.py::test_conflict_strong_evidence_image_persisted_and_purge_scheduled` | Image retention (R16) | 100 % |
| `test_event_handlers.py::test_conflict_weak_captures_weak_conflict_penalty` | Weak conflict (R6, R12) + penalty capture | 100 % |
| `test_event_handlers.py::test_no_show_expires_reservation_and_captures_penalty` | No-show / Auto-release + penalty capture | 100 % |
| `test_event_handlers.py::test_normal_exit_releases_full_deposit` | Deposit Release on Completion (proposal §7.3) — exactly one `release` row, full deposit, no `capture` row | 100 % |
| `test_event_handlers.py::test_weak_conflict_then_late_check_in_then_exit_is_payment_no_op` | Weak-Conflict + Late Check-in (proposal §7.3) — completion path skips release when remaining deposit is 0 | 100 % |
| `test_event_handlers.py::test_duplicate_event_id_is_idempotent` | Event-id dedupe (§8.3) — applies to bay_events, conflicts, AND payments | 100 % |
| `test_payment_service.py::test_validate_card_accepts_valid_rejects_invalid_paths` | Card validation paths (R18) | 100 % |
| `test_payment_service.py::test_preauthorize_decrements_balance_and_writes_one_row` | Pre-auth correctness (R18, R20) | 100 % |
| `test_payment_service.py::test_release_full_deposit_on_completion` | Release math (proposal §7.3 Deposit Release on Completion) — full deposit returned, no `capture` action invoked | 100 % |
| `test_payment_service.py::test_release_restores_card_balance` | Release correctness (R18) | 100 % |
| `test_payment_service.py::test_refund_restores_full_hold_on_strong_conflict` | Strong-conflict refund (proposal §7.3 Strong-Conflict Refund) | 100 % |
| `test_payment_service.py::test_charge_penalty_uses_configured_amount_per_kind` | Penalty defaults (proposal §5.5 / §7.3) | 100 % |
| `test_payment_service.py::test_idempotent_replay_collapses_to_one_row` | Idempotency (R19, proposal §7.3 — replay 50 actions 3× each) | 100 % |
| `test_payment_service.py::test_concurrent_pre_auth_against_same_card_serialises_via_for_update` | Concurrency (DB I19) | 100 % |
| `test_mqtt_ingest.py::test_state_update_persisted_and_websocket_emitted` | MQTT delivery + dashboard accuracy | ≥ 99 % / 100 % |
| `test_mqtt_commands.py::test_reserve_publishes_reservation_topic_with_qos1_and_bound_plates` | MQTT commands | 100 % |
| `test_mqtt_commands.py::test_update_plates_action_published_on_plate_change_during_active_reservation` | R2 / R15 | 100 % |
| `test_api_conflicts.py::test_pi_evidence_upload_persists_url_and_purge_at` | R6, R16 | 100 % |
| `test_api_conflicts.py::test_evidence_404_after_purge` | R16 | 100 % |
| `test_purge_job.py::test_30_day_image_purge_clears_evidence_url_and_object` | R16 | Pass |
| `test_reconcile_job.py::test_sweeper_synthesises_no_show_when_pi_event_missed` | Safety-net behaviour | Pass |
| `test_reconcile_job.py::test_sweeper_synthesises_only_weak_conflict_never_strong` | Safety-net constrained to weak | Pass |
| `test_resilience_reconnect.py::test_resync_on_reconnect_restores_state` | Cloud disconnection resilience | Pass |
| `test_api_reservations.py::test_end_to_end_latency_under_5_seconds` | End-to-end latency | < 5 s |
| `test_api_reservations.py::test_auto_check_in_latency_under_8_seconds` | Auto-check-in round-trip | < 8 s |

Coverage target: **≥ 90 % lines**, **100 %** of `services/` and `mqtt/` modules.
Enforced in CI with `pytest --cov --cov-fail-under=90`.

### 9.3 Manual / demo scripts

- `scripts/mock_pi_publisher.py` publishes simulated `cloud/bay/<code>/state`
  readings and `cloud/bay/<code>/event` transitions to HiveMQ so the dashboard
  can be demoed without hardware — critical for the presentation rubric row
  *Demonstration Effectiveness* (worth 25 %) in case a physical device
  misbehaves on the day. It can drive all six bay states and emit every event
  type — including `auto_check_in` (with a synthetic `recognised_plate` on the
  user's bound list), `conflict_strong` (with a non-matching plate, plus a
  companion HTTPS POST to `/api/v1/internal/conflicts/evidence` with a fixture
  JPEG), and `conflict_weak`. Driving `conflict_strong` end-to-end exercises
  the strong-conflict refund path (the dashboard should display a refund
  receipt for the reserving user); driving `no_show` and `conflict_weak`
  exercises the penalty-capture paths (receipts visible in
  `/users/me/payments`); driving a clean `vehicle_leaves` after `auto_check_in`
  exercises the normal **deposit-release** path (full $10 returned to the
  card, no parking-fee capture — proposal §5.6). The combination of these
  four scripted flows covers the entire proposal §7.3 "Mock Payment
  Correctness" block.

---

## 10. Deployment Plan (R9)

- AWS EC2 `t3.micro` (free tier) running Ubuntu 24.04.
- Backend installed as a systemd unit (`deploy/parkreserve.service`) using a
  virtualenv, run under `gunicorn --workers 1 --worker-class eventlet`. The
  single-worker constraint is **load-bearing**, not an arbitrary tuning choice:
  §3 specifies one MQTT client and one APScheduler-driven sweeper *per
  process*. Running multiple workers would spawn parallel MQTT subscribers
  (duplicate event ingest → double-charges even with `source_event_id` dedupe
  in tight races) and parallel sweepers (redundant safety-net work). If
  horizontal scaling is ever required, the MQTT consumer and the sweeper must
  first be extracted into independent sidecar processes — see §12 Risks.
- PostgreSQL 16 installed locally on the same EC2 instance for the free-tier demo;
  a short note in the deployment doc explains how to move to AWS RDS by swapping
  the `DATABASE_URL` env var.
- Caddy 2 fronts the service and issues a Let's Encrypt cert for the public URL,
  giving HTTPS with zero manual cert work.
- A first-boot bootstrap script (`deploy/bootstrap.sh`) installs deps, clones the
  repo, applies migrations, seeds demo data, and starts the service. The rubric's
  *Code → Exemplary* row demands a how-to-guide: the backend `README.md` is that
  guide, with copy-pasteable sections for local Docker, AWS deploy, and demo-day
  reset.

---

## 11. Work Breakdown and Milestone Mapping

The plan below matches the proposal's Gantt (§7.1) — the backend work owned by
Cheng lands inside Weeks 2–4 and contributes to M2–M3.

| Week | Task | Proposal milestone | Deliverable in this plan |
|------|------|--------------------|--------------------------|
| 2 (Apr 14–20) | Scaffold Flask app, PostgreSQL dockerised, first migration (incl. `licence_plates` table + `penalty_kind` / `payment_action` / `payment_status` / `bay_event_kind` / `conflict_kind` enums + `mock_cards` + `payments` tables), seed (incl. `20260421_03_seed_mock_cards`), CI pipeline | M1 → on track to M2 | §5 layout in place; `/healthz` green |
| 2 | REST skeleton: `GET /bays`, `POST /auth/*`, plate management CRUD (`/users/me/plates`) | — | `test_api_bays`, `test_api_auth`, `test_api_plates` |
| 2 | AWS EC2 deploy of scaffold + REST skeleton with Caddy HTTPS (matches proposal §7 Wk2 "deploy to AWS EC2") | — | Public URL live |
| 3 (Apr 21–27) | MQTT ingest (state + event topics, incl. `auto_check_in` / `conflict_strong` / `conflict_weak`) + Socket.IO emit; seed 3 bays; ingest from `mock_pi_publisher.py`. **Build the standalone `payment_service.py`** with full unit-test coverage (validate_card, preauthorize, release, charge_penalty, refund — no `capture` method, per §8.8) before §8.2 / §8.3 wire it in — keeps the payment surface independently testable | M2 individual subsystems | `test_mqtt_ingest`, `test_payment_service` green |
| 4 (Apr 28–May 4) | Reservation endpoints (booking window + zero-plate guard + **mock card pre-auth gate** — R20), cancel (late-cancel penalty capture), QR/manual fallback check-in, plate-list publish on reserve and on plate add/remove, event handlers for `auto_check_in` / `pending_check_in` / `conflict_strong` (refund + image upload) / `conflict_weak` (penalty capture) / `no_show` (penalty capture) / vehicle-leaves (deposit release on completion), notifications including deposit-released / refund-issued / penalty-captured, transaction-history endpoint, 30-day evidence-purge job, safety-net sweeper (weak only, with payment-side idempotency) | M2 | `test_api_reservations`, `test_api_plates`, `test_api_payments`, `test_api_conflicts`, `test_event_handlers`, `test_purge_job`, `test_reconcile_job` |
| 5 (May 5–11) | Integration with Subsystems C/D/E (Nyx lead); resync flow; latency tuning | M3 end-to-end | `test_resilience_reconnect`, `test_end_to_end_latency_under_5_seconds` |
| 6 (May 12–18) | Evaluation against §7.3 targets (Yuan Cong lead); fix-ups; Grafana board | M4 | Metrics captured for final report |
| 7 (May 19–22) | How-to-guide polish, demo script rehearsal | M5 | `README.md` final, `scripts/mock_pi_publisher.py` demo-ready |

---

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| HiveMQ free-tier connection cap (100) | Cannot fan out | Only backend + Pi + 1 mock = 3 connections — safely under cap |
| Eventlet / Socket.IO / psycopg incompatibility | WebSocket breaks | Pin versions in `pyproject.toml`; CI matrix runs socketio smoke test |
| PostgreSQL on EC2 runs out of memory on `t3.micro` | Prod outage during demo | `shared_buffers=64MB`, enable swap; fallback script to restart Postgres |
| Student-network NAT blocks outbound MQTT 8883 | Dev blocked | Local `mosquitto` via docker-compose covers all dev; HiveMQ only needed on EC2 |
| Frontend (Riya) schema drifts | Integration delay | OpenAPI spec generated from pydantic schemas, published at `/api/v1/openapi.json` and reviewed weekly |
| Reservation logic drift between backend business rules and Pi state machine | Demo glitch; incorrect penalty captures | Shared contract doc (this §7.3 MQTT table + proposal §5.4 state machine) is source of truth; contract tests on both sides; event-id dedupe (§8.3) prevents double-event |
| Pi missed event (backend offline during transition) silently skips a penalty | Under-counted penalties; lost operator revenue | Safety-net sweeper (§8.4) synthesises `no_show` / `conflict_weak` when the mirrored state contradicts the reservation record, and the synthetic event is dispatched through the same handler that captures the penalty |
| **Backend mistakenly captures a penalty for a strong-evidence conflict** | Wrongly debits a victim | DB-level enforcement: `penalty_kind` enum has no `strong_conflict` value, so `payments_penalty_kind_only_for_penalty` CHECK rejects the row (DB I13 / I18). Also unit-tested: `test_conflict_strong_refunds_user_and_logs_facility_incident` |
| **MQTT redelivery / sweeper retry / user double-click double-charges** | User sees two charges for one event | DB-level enforcement: `payments_idempotency_key_unique` (DB I16). Tested by `test_payment_service.py::test_idempotent_replay_collapses_to_one_row` (replay 50 actions 3× each; expect exactly one row per key) |
| **Concurrent bookings against the same mock card race the balance check** | Card balance could go negative; or one booking succeeds spuriously | `SELECT … FOR UPDATE` in the booking transaction serialises card-row access; `mock_cards_balance_nonneg` CHECK is the safety net (DB I19) |
| Strong-conflict image upload races the MQTT event (image arrives before / after / not at all) | Missing or unattached evidence | `conflicts` row is upserted on `source_event_id`; either side creates a placeholder; image-upload endpoint is idempotent and can be retried by the Pi |
| User binds another driver's plate (not verified — proposal §5.6) | Abuse vector: misuse another driver as auto check-in | Documented limitation; flagged as production must-fix in §13 + proposal §5.7 (registration-document OCR) |
| 30-day evidence retention skipped (purge job fails silently) | Privacy / GDPR-style risk | Purge job emits a Prometheus counter `evidence_purged_total`; alert on > 24 h since last successful run; `image_purge_at` queryable so backlog is visible |
| Mock-bank table mistakenly populated with real card data in production | Data-leak risk | Seed migration `20260421_03_seed_mock_cards` is the only insertion path; the dashboard banner prevents user input from being mistaken for a real gateway; the production-deployment checklist explicitly flags "drop the `mock_cards` table when swapping to a real gateway" (proposal §5.7) |

---

## 13. Open Decisions (to confirm with team by end of Wk 2)

1. JWT lifetime: default 24 h — confirm with Riya for UX.
2. Whether to expose a public read-only `GET /api/v1/bays` without auth (current
   default: yes, to match the proposal's "visible from a distance" framing).
3. ~~Whether check-in is automatic on sensor-occupied for a reserved spot, or
   requires a user tap.~~ **Re-settled by proposal §5.5 (LPR addition)**:
   primary check-in is now **automatic** via LPR plate match — no user action
   required in the typical case. The QR-code scan is a fallback (LPR failed /
   low confidence), and the manual "I'm here" button is a further fallback
   (QR damaged). The Pi transitions the bay to `PENDING_CHECK_IN` while LPR
   runs; on a confident match it emits `auto_check_in` directly, otherwise it
   waits for user action.
4. Notification transport for `auto_check_in` / `pending_check_in` /
   `conflict_strong` / `conflict_weak` (R14). Default for M3: WebSocket only.
   Stretch for M4: web-push via a single VAPID key, or a SendGrid-backed
   email fallback. Confirm with Riya whether the dashboard has a service
   worker in scope.
5. Whether `/api/v1/users/me/payments` exposes a per-`penalty_kind` summary
   alongside the raw transaction list. Default: list view only; the
   summary panel is a dashboard-side roll-up that re-uses §6.5 of the DB
   design.
6. LPR confidence threshold for "match". Default: 0.80 (proposal §5.4 defaults
   table). Owned by Nyx on the Pi side; the backend doesn't enforce it but
   logs `lpr_confidence` from the event payload for tuning.
7. Plate-format validation policy. Default: backend stores the user's input
   normalised to uppercase + stripped of spaces, and accepts any string of 1–10
   alphanumerics. We do **not** validate against an Australian-plate regex
   because the proposal targets a casual / generic deployment. The Pi's LPR
   matcher does an exact case-insensitive match against the bound list.
8. Whether to retain conflict-evidence images for `conflict_strong` in S3 or
   on the EC2 local disk. Default for M3: local disk under
   `/var/lib/parkreserve/evidence` (free-tier friendly); migrate to S3 if the
   demo facility is provisioned an S3 bucket.
9. **Default pricing values** (proposal §5.5 — defaults shown in §8.8):
   $10 deposit, $5 late-cancel, $10 no-show, $10 weak-conflict. There is
   no hourly rate — per-time parking-fee billing is out of scope (proposal
   §5.6). Confirm with the team that these are sensible-enough for the
   demo narrative; the values are configurable via `Settings` so they can
   be tuned without code changes.
10. **Whether to expose mock-card management to the user** (e.g. let a user
    save a card on their account so they don't re-enter it on every
    booking). Default for M3: **no** — the dashboard collects card details
    fresh per booking, matching the prototype's mock posture and avoiding
    any temptation to persist card-on-user. A real gateway swap (proposal
    §5.7) would replace this with a tokenized-saved-card flow at the
    browser, which is the only PCI-compliant way to do "save card."

---

## 14. Rubric Self-Check

| Rubric row | Weight | How this plan scores *Exemplary* |
|------------|-------:|----------------------------------|
| Report → Technical Content | 20 | Block diagram (§3), subsystem design (§8), evaluation tied to metrics (§9.2), limitations (§12) |
| Report → Organization & Development | 10 | Numbered sections, requirement trace (§2), milestone map (§11) |
| Report → Word Usage & Format | 10 | IEEE-style tables, consistent heading depth, all figures captioned when materialised |
| Report → Code | 10 | `README.md` how-to-guide, `Makefile`, docker-compose, seed + mock scripts, ≥ 90 % coverage |
| Report → References | 5 | Rely on proposal refs [1]–[7] + Flask / SQLAlchemy / paho docs, IEEE-formatted in final report |
| Demo → Content | 20 | Grafana board + Prometheus metrics make demo data-driven |
| Demo → Technical Implementation | 20 | Real PostgreSQL, TLS MQTT, CI, idempotent APIs, resync on reconnect |
| Demo → Demonstration Effectiveness | 25 | `mock_pi_publisher.py` is a hardware-independent failover for demo day |
| Demo → Q&A | 15 | Requirement trace (§2) and open-decisions list (§13) pre-empt common questions |
