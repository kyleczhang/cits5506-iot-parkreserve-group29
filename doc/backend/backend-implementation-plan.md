# Backend Implementation — ParkReserve

**Unit:** CITS5506 The Internet of Things | **Semester:** 1, 2026 | **Group:** 29
**Subsystem:** F — Cloud Backend (Flask + PostgreSQL + MQTT) on AWS
**Owner:** Cheng Zhang (24878502)
**Document status:** Describes the implementation as it ships today. Aligns with
[doc/proposal/proposal.md](../proposal/proposal.md) and the code under
[backend/](../../backend/).

---

## 1. Purpose and scope

Subsystem F (cloud backend) is responsible for:

1. **Terminating the cloud MQTT channel** that bridges the Raspberry Pi
   edge gateway (Subsystem E) to the cloud tier. The backend subscribes to
   `cloud/bay/+/state`, `cloud/bay/+/event`, and `cloud/system/heartbeat`,
   and publishes `cloud/bay/<code>/reservation` and `cloud/system/resync`.
2. **Persisting authoritative state in PostgreSQL** — bay-state mirror,
   reservation lifecycle, conflicts, audit log, and a transactions ledger.
   Tests run against real PostgreSQL too — no SQLite.
3. **Managing per-account licence-plate bindings** (proposal §5.5). Each user
   binds 1–5 plates; a reservation is not pinned to a specific plate — any
   currently-bound plate matches. The bound-plate list is published with
   every reservation command so the Pi's LPR matcher always has the
   freshest set. Ownership is not verified in the prototype (proposal §5.6).
4. **Running the reservation business logic** — booking-window enforcement
   (1 hour), arrival / check-in grace, late-cancel cutoff, no-show, and the
   strong/weak conflict outcomes. The state machine that physically owns
   a bay still lives on the Pi (proposal §5.4); the backend mirrors the
   bay state and owns the reservation state.
5. **Hosting an in-process mock-payment service** (proposal §5.6) — a
   seeded `mock_cards` table simulates card validation; idempotent
   `validate_card` / `preauthorize` / `release` / `charge_penalty` / `refund`
   actions write rows to `payments`. There is no `capture` action — per-time
   parking-fee billing is the facility's exit-side concern and is out of
   scope. Reservation creation is **gated on a successful pre-auth**: the
   reservation row and its `pre_auth` payment row are inserted in the same
   transaction.
6. **Consuming Pi-originated state-machine events** — `auto_check_in`,
   `pending_check_in`, `conflict_strong`, `check_in_confirmed`,
   `sensor_online`, `sensor_offline`. The backend additionally synthesises
   two internal events from the safety-net sweeper (`conflict_weak`,
   `no_show`) and dispatches them through the same handler entrypoint.
7. **Receiving strong-conflict evidence images** over HTTPS from the Pi
   (`POST /api/v1/internal/conflicts/evidence`), persisting the JPEG, and
   purging it after 30 days while keeping the conflict row for audit.
8. **Exposing a REST + WebSocket API** for the React dashboard (the rest of
   Subsystem F — frontend owned by Riya). The WebSocket is on the `/ws`
   namespace and pushes bay updates, reservation updates, conflict alerts,
   plate changes, and payment events.
9. **Resilient to cloud-link flaps.** Local control on the Pi continues
   unaffected; on reconnect the backend publishes `cloud/system/resync` so
   the Pi replays its current bay state, and idempotency keys collapse
   replayed events.

Out of scope: ESP32 firmware (subsystems A/B), Raspberry Pi state machine
(subsystem C+E), React UI implementation details.

---

## 2. Requirements trace

| # | Requirement | Source |
|---|-------------|--------|
| R1 | Subscribe to `cloud/bay/<code>/state` and `cloud/bay/<code>/event` and mirror the latest state per bay | Proposal §5.1 step 6, §5.2, §5.3 F |
| R2 | Publish `cloud/bay/<code>/reservation` commands — including the reserving user's bound-plate list — for create / cancel / check_in / update_plates / release / expire_check_in | Proposal §5.1 step 7, §5.2, §5.3 F, §5.5 |
| R3 | REST endpoints for bay listing, plate CRUD, reservation create / cancel / check-in (QR / manual), payment history, conflict admin | Proposal §5.3 F, §5.5 |
| R4 | Real-time push of bay / reservation / conflict / payment changes via WebSocket | Proposal §5.1 step 7 |
| R5 | Persist reservation history, bay events, sensor readings, conflicts (with plate evidence + image URL for strong cases), and the payments ledger | Proposal §5.3 F, §5.5, §7.3 |
| R6 | Synthesise `no_show` and `conflict_weak` from a safety-net sweeper when the user fails to arrive or fails to check in within grace; never synthesise `conflict_strong` | Proposal §5.3 C/F, §5.5 |
| R7 | Tolerate cloud disconnection: idempotent ingestion, resync on reconnect | Proposal §7.3 |
| R8 | MQTT message reliability ≥ 99 %; click → LED < 5 s; vehicle detection → "you're checked in" < 8 s | Proposal §7.3 |
| R9 | Deployable on AWS EC2 free tier, HTTPS public URL | Proposal §5.1, §8 |
| R10 | Dashboard accuracy 100 % — API state == physical LED state | Proposal §7.3 |
| R11 | Booking window 1 h: `expected_arrival_time ∈ (now, now + 1h]` | Proposal §5.5 |
| R12 | Penalty capture: `late_cancel` (cancel < 15 min before arrival), `no_show`, and `weak_conflict` each capture the configured penalty against the deposit, with the remainder released. **Strong-evidence conflict is NOT a user penalty** — the holder is refunded in full if and only if their reservation is explicitly terminated (admin path or holder's voluntary no-fault cancel) | Proposal §5.5, §7.3 |
| R13 | Check-in mechanisms: (a) auto via LPR plate match (primary, Pi-driven); (b) QR fallback (user POSTs `/check-in` with `source=qr`); (c) manual button (`source=manual`) | Proposal §5.5 |
| R14 | Push notifications via WebSocket for `auto_check_in`, `pending_check_in`, deposit released, penalty captured, refund issued, conflict raised / resolved | Proposal §5.3 F, §5.5 |
| R15 | Plate CRUD: 1–5 plates per user; reservation matches any bound plate; reservation creation rejected if user has zero plates | Proposal §5.5, §5.6 |
| R16 | Receive `conflict_strong` evidence images over HTTPS; store on disk; nightly purge after 30 days; conflict row preserved | Proposal §5.5 |
| R17 | LPR runs only when bay state is `reserved` (privacy policy — no LPR for casual parking) | Proposal §5.5 |
| R18 | In-process mock-payment service: seeded `mock_cards`; `validate_card` / `preauthorize` / `release` / `charge_penalty` / `refund`; **no `capture` action**; "MOCK PAYMENT" banner on the frontend card form | Proposal §5.6 |
| R19 | Idempotent payment actions: deterministic `idempotency_key` collapses MQTT replays, sweeper retries, and user double-clicks to a single row | Proposal §5.6, §7.3 |
| R20 | Booking gated on successful pre-auth: reservation row + `pre_auth` payment row inserted in the same transaction; concurrent bookings against the same card serialised via `SELECT ... FOR UPDATE` on `mock_cards` | Proposal §5.5 step 1, §5.6 |

Every requirement has at least one test in [backend/tests/](../../backend/tests/) — see §10.

---

## 3. Architecture

```
  React SPA (Riya)             ESP32-CAM nodes × 3 (Yuan Cong)
        │                              │
        │ HTTPS / WSS                  │ Local WiFi (MQTT)
        ▼                              ▼
 ┌─────────────────┐          ┌──────────────────────────────┐
 │ Flask backend   │◄────────►│ Raspberry Pi 5               │
 │ (this doc)      │  HiveMQ  │  Mosquitto + bay state       │
 │  - REST API     │  TLS 8883│  machine + OpenALPR plate    │
 │  - WebSocket /ws│          │  matching + camera capture   │
 │  - paho-mqtt    │          │                              │
 │  - HTTPS image  │◄─────────│  POST /internal/conflicts/   │
 │    receiver     │  HTTPS   │       evidence  (Pi token)   │
 │  - SQLAlchemy   │          └──────────────────────────────┘
 └────────┬────────┘
          │
          ▼
   PostgreSQL 16 + local-disk evidence images
   (EVIDENCE_STORAGE_PATH; AWS S3 not used)
```

### One process, three concerns

The backend runs as **one Linux process**:
[backend/run_dev.py](../../backend/run_dev.py) → `app.web.main` →
[`create_wsgi_app()`](../../backend/app/__init__.py). That single process
hosts:

- **HTTP + Socket.IO** under `eventlet`. Routes registered in
  [`app/api/__init__.py`](../../backend/app/api/__init__.py); WebSocket
  emissions in [`app/sockets/events.py`](../../backend/app/sockets/events.py).
- **Inbound MQTT subscriber** ([`app/mqtt/client.py`](../../backend/app/mqtt/client.py))
  in a paho background thread. Subscribes to
  `cloud/bay/+/state`, `cloud/bay/+/event`, `cloud/system/heartbeat`.
  Issues a `cloud/system/resync` publish on each connect.
- **Outbound MQTT publisher** ([`app/mqtt/publisher.py`](../../backend/app/mqtt/publisher.py))
  on its own paho client (no subscriptions, no `on_message`). Decoupled
  from the inbound subscriber so a broker hiccup on one side does not
  silently break the other.
- **Two APScheduler jobs**:
  - [`reconcile_reservations`](../../backend/app/jobs/reconcile_reservations.py)
    runs every `RECONCILE_INTERVAL_SECONDS` (default 30) and synthesises
    missed `no_show` / `conflict_weak` events.
  - [`purge_evidence_images`](../../backend/app/jobs/purge_evidence_images.py)
    runs every `PURGE_INTERVAL_HOURS` (default 24) and deletes JPEGs past
    their 30-day retention.

The single-process choice is deliberate (one SQLAlchemy session factory,
one Socket.IO emitter, no inter-process coordination); deployment is one
`systemd` unit, `parkreserve-web.service`.

### eventlet monkey-patch

`eventlet.monkey_patch()` must run **before** anything imports the `app`
package, otherwise eventlet leaves stdlib `RLock`s un-greened and
`socketio.emit()` calls from the paho background thread silently fail to
reach connected WebSocket clients. That is why the dev entrypoint is
`run_dev.py` (top-level file) — `python -m app` and `python -m app.web`
are explicitly refused by [`app/__main__.py`](../../backend/app/__main__.py).

### Ownership split with the Pi

The Pi (Subsystem C, proposal §5.4) owns the **per-bay state machine**:
it merges sensor readings + LPR + active reservation into a bay state,
drives LEDs and the buzzer, and emits state-change / event MQTT messages.

The backend is the cloud mirror plus the business layer:

- mirrors bay state from `cloud/bay/<code>/state`;
- maintains the **reservation** state machine (booking window, grace
  timers, no-show, weak-conflict, completion inference);
- runs the **mock-payment** service in-process;
- publishes reservation commands and the bound-plate list back to the Pi;
- ingests strong-evidence images for the conflict log;
- handles user / admin REST and WebSocket traffic.

The Pi is payment-agnostic — it never sees card details, deposits, or
penalty events.

---

## 4. Technology stack

From [backend/pyproject.toml](../../backend/pyproject.toml):

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.11 | `requires-python = ">=3.11"` |
| Web framework | Flask 3.0 + per-resource blueprints | |
| ORM | SQLAlchemy 2.0 (declarative `Mapped[]` types) | Single `Base` in [`app/extensions.py`](../../backend/app/extensions.py) |
| Migrations | Alembic 1.13 (bare; no flask-migrate) | [`backend/alembic.ini`](../../backend/alembic.ini) |
| Database | PostgreSQL 16 (prod and tests) | Mandatory — JSONB / CITEXT / partial indexes / enum DDL |
| DB driver | `psycopg` v3 (binary wheel) | |
| MQTT client | `paho-mqtt` 2.1 | Two clients: outbound publisher + inbound subscriber |
| Realtime | Flask-SocketIO 5.3 + `python-socketio` (eventlet async mode) | `/ws` namespace |
| Auth | flask-jwt-extended 4.6 | Stateless JWT in `Authorization: Bearer …` |
| Password hashing | `argon2-cffi` | |
| Request validation | `pydantic` v2 | Schemas under [`app/schemas/`](../../backend/app/schemas/) |
| Scheduler | APScheduler 3 (background) | Two jobs |
| Logging | `structlog` + JSON renderer | |
| WSGI / web server | `eventlet` + `gunicorn` (prod) | Dev uses `socketio.run(..., allow_unsafe_werkzeug=True)` |
| Reverse proxy | Caddy (auto-HTTPS) | [`backend/deploy/Caddyfile`](../../backend/deploy/Caddyfile) |
| Testing | `pytest`, `pytest-postgresql`, `pytest-mock`, `factory-boy`, `freezegun` | `fail_under = 90` |
| Lint / format | `ruff` 0.6, `mypy` 1.11 | |

There is no Celery / no separate task queue and no Redis. The reconcile
sweeper plus MQTT idempotency keys are enough for the scale of the demo.

---

## 5. Project layout

```
backend/
├── app/
│   ├── __init__.py            # create_app + start_runtime_services + create_wsgi_app
│   ├── __main__.py            # refuses `python -m app` (must use run_dev.py)
│   ├── web.py                 # main() for the single-process runtime
│   ├── config.py              # Settings dataclass + load_settings()
│   ├── extensions.py          # SQLAlchemy `db`, `jwt`, `socketio` singletons
│   ├── models/                # SQLAlchemy models (one file per table)
│   │   ├── user.py            licence_plate.py    bay.py
│   │   ├── reservation.py     bay_event.py        sensor_reading.py
│   │   ├── conflict.py        mock_card.py        payment.py
│   │   └── base.py            # TimestampMixin
│   ├── schemas/               # pydantic request/response schemas
│   │   ├── auth.py            bay.py              plate.py
│   │   ├── reservation.py     payment.py          conflict.py
│   ├── api/                   # Flask blueprints
│   │   ├── __init__.py        # register_blueprints()
│   │   ├── auth.py            bays.py             plates.py
│   │   ├── reservations.py    payments.py         conflicts.py
│   │   └── health.py
│   ├── mqtt/
│   │   ├── client.py          # inbound MQTTClient (subscribe + dispatch)
│   │   ├── publisher.py       # outbound PahoPublisher (publish-only)
│   │   ├── handlers.py        # wires inbound topics → service layer
│   │   └── topics.py          # topic builders + pydantic payload schemas
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── bay_service.py     # mirrors Pi state + completion inference
│   │   │                      #   + strong-conflict restore
│   │   │                      #   + pending-check-in rollback
│   │   ├── bay_event_service.py
│   │   ├── conflict_service.py
│   │   ├── event_dispatcher.py # Pi/synthesised event → service handler
│   │   ├── event_service.py   # bay_events writer (idempotent on source_event_id)
│   │   ├── mqtt_publisher.py  # publish_reservation_command (single source)
│   │   ├── notification_service.py
│   │   ├── payment_service.py # mock-payment surface (idempotent)
│   │   ├── plate_service.py
│   │   └── reservation_service.py
│   ├── sockets/events.py      # /ws emitters
│   ├── jobs/
│   │   ├── reconcile_reservations.py
│   │   └── purge_evidence_images.py
│   └── utils/                 # errors, plate normalisation, time, security
├── migrations/                # Alembic env.py + versions/
├── tests/                     # ~30 pytest modules
├── scripts/                   # seed.py, mock_pi_publisher.py, mock_pi_subscriber.py
├── docker/                    # docker-compose for local postgres + mosquitto
├── deploy/                    # systemd unit + Caddyfile + bootstrap.sh
├── alembic.ini
├── pyproject.toml
├── Makefile
└── run_dev.py                 # entrypoint: eventlet.monkey_patch() then app.web.main
```

---

## 6. Runtime state model

The Pi owns the bay state machine; the backend owns reservation state.
The two are coupled by MQTT.

### 6.1 Bay state (mirror)

| Bay state | Set by | LED (Pi) | Buzzer (Pi) |
|-----------|--------|----------|-------------|
| `available` | Pi `/state` | green solid | off |
| `reserved` | Pi `/state` (driven by backend `reservation/create`) | yellow solid | off |
| `pending_check_in` | Pi `event=pending_check_in` (vehicle in reserved bay; LPR did not auto-match) | yellow blinking | off |
| `occupied` | Pi `/state` (casual parking; no active reservation; no LPR) | red solid | off |
| `reserved_checked_in` | Pi `event=auto_check_in` (LPR plate match) or `event=check_in_confirmed` (QR/manual echo) | red solid | off |
| `conflict` | Pi `event=conflict_strong` or backend-synthesised `conflict_weak` | red blinking ~2 Hz | on (mirrors LED) |
| `offline` | No `cloud/system/heartbeat` > 30 s | unchanged | off |

`parking_bays.state` is written **only** by
[`bay_service.apply_state`](../../backend/app/services/bay_service.py).
The single `conflict` state covers both strong and weak; the strong/weak
distinction lives on the matching `conflicts` row (DB §3.10) and on the
`bay_events` row (`kind = conflict_strong | conflict_weak`).

The API surfaces both `state` (the user-facing rollup from
`ParkingBay.public_state()`) and `mirror_state` (the raw Pi-reported
value). They differ during the brief window after `create` when the bay
has a reservation but the Pi has not yet pushed its first state — see
[`app/models/bay.py`](../../backend/app/models/bay.py).

### 6.2 Reservation state (backend-owned)

```
                cancel ≥15 min before arrival ─► CANCELLED        (release: clean_cancel)
               /
ACTIVE ────────┼ cancel <15 min                ─► CANCELLED_LATE  (penalty_capture: late_cancel
   (created    │                                                    + release: remainder)
    with       ├ pi:pending_check_in           ─► PENDING_CHECK_IN
    pre_auth)  │
               ├ pi:auto_check_in              ─► CHECKED_IN      (no immediate payment)
               │   (LPR plate ∈ bound)
               │
               ├ pi:conflict_strong            ─► ACTIVE preserved
               │   (LPR plate ∉ bound)            (conflict_strong row opened;
               │                                   no refund here)
               │
               └ sweeper:no_show               ─► EXPIRED_NO_SHOW (penalty_capture: no_show
                  (arrival + grace,                                 + release: remainder)
                   bay still empty,
                   bay not in CONFLICT)

PENDING_CHECK_IN
       ├ pi:auto_check_in                      ─► CHECKED_IN
       ├ user POST /check-in (source=qr|manual)─► CHECKED_IN
       └ sweeper:conflict_weak                 ─► IN_CONFLICT     (penalty_capture: weak_conflict
                                                                    + release: remainder
                                                                    + publish expire_check_in
                                                                      to Pi)

CHECKED_IN
       └ bay /state: RESERVED_CHECKED_IN → AVAILABLE ─► COMPLETED (release: completed)

Strong-conflict restore (bay_service):
   bay /state: CONFLICT → {AVAILABLE, RESERVED, RESERVED_CHECKED_IN}
   AND open strong conflict + resumable reservation
       ⇒ conflict resolves as vehicle_left
       ⇒ reservation resumes (PENDING_CHECK_IN rolls back to ACTIVE)
       ⇒ create / check_in republished to Pi
       ⇒ no payment side-effect

Holder voluntary cancel under strong conflict (reservation_service.cancel):
   reservation has an open strong conflict
       ⇒ reservation → CANCELLED
       ⇒ conflict resolves as user_cancelled
       ⇒ refund issued
       ⇒ release(reason=admin_override) published to Pi
       ⇒ bay.state left alone (wrong vehicle still physically present)
```

There is intentionally no direct `ACTIVE → CHECKED_IN` transition: the Pi
routes every arrival through `pending_check_in` while LPR runs. A user
calling `/check-in` while still `ACTIVE` is rejected with HTTP 409
`code=vehicle_not_detected_yet`; the dashboard waits for the
`reservation.pending_check_in` WebSocket event.

### 6.3 Backend safety-net sweeper

Implemented in [`app/jobs/reconcile_reservations.py`](../../backend/app/jobs/reconcile_reservations.py).
Every `RECONCILE_INTERVAL_SECONDS`:

- Rows with `status=active` and `expected_arrival_time < now - ARRIVAL_GRACE_MINUTES`
  AND bay not in `CONFLICT`: dispatch a synthesised `no_show` event.
- Rows with `status=pending_check_in` and `check_in_grace_expires_at < now`:
  dispatch a synthesised `conflict_weak` event.

The sweeper uses `SELECT ... FOR UPDATE SKIP LOCKED` to keep concurrent
runs harmless. The synthesised `event_id` is
`uuid5(NAMESPACE_URL, "reservation/<id>/<kind>/safety_net")` — deterministic,
so the `bay_events` and `payments` idempotency machinery collapses
repeated sweeps to one row.

The sweeper never synthesises `conflict_strong`: it has no LPR evidence,
and the Pi will replay the real event on reconnect anyway.

---

## 7. MQTT contract

Topic builders + payload pydantic schemas live in
[`app/mqtt/topics.py`](../../backend/app/mqtt/topics.py).

### 7.1 Topics

| Direction | Topic | Purpose |
|-----------|-------|---------|
| Pi → backend | `cloud/bay/<code>/state` | Bay-state mirror + last sensor reading |
| Pi → backend | `cloud/bay/<code>/event` | State-machine events |
| Pi → backend | `cloud/system/heartbeat` | Pi heartbeat (~10 s) |
| Backend → Pi | `cloud/bay/<code>/reservation` | Reservation commands + bound plates |
| Backend → Pi | `cloud/system/resync` | "Replay your current state" |

Prefix is configurable via `MQTT_TOPIC_PREFIX` (default `cloud`).

### 7.2 Pi-inbound payloads

`StatePayload`:

```json
{ "state": "available",
  "last_distance_cm": 120.5,
  "ts": "2026-05-01T10:00:00Z",
  "event_id": "..." }
```

`PiInboundEventPayload` — allowed `event` values:

```
sensor_online, sensor_offline,
auto_check_in, pending_check_in, check_in_confirmed,
conflict_strong
```

Optional fields: `event_id`, `reservation_id`, `recognised_plate` (≤ 16
chars), `lpr_confidence` (`0.0 ≤ x ≤ 1.0`). `model_config = ConfigDict(extra="forbid")`
— unknown fields are rejected at schema validation.

`conflict_weak` and `no_show` are **internal** events synthesised by the
sweeper. They share a pydantic schema (`InternalEventPayload`) and route
through the same `dispatch_event()` entrypoint as Pi events, but the
inbound MQTT topic schema rejects them. See pi-side-change-notes.md §3.

### 7.3 Backend-outbound `reservation` command

`ReservationCommand` actions:

```
create, cancel, check_in, update_plates, release, expire_check_in
```

Payload (every command):

```json
{ "action": "create",
  "reservation_id": "...",
  "user_id": "...",
  "bound_plates": ["ABC123", "XYZ789"],
  "expected_arrival_time": "2026-05-01T10:30:00Z",
  "reason": null,
  "ts": "2026-05-01T10:00:00Z" }
```

`reason` is **required** when `action=release` and **forbidden** otherwise
(validator in `ReservationCommand.validate_reason`). Allowed reasons:
`no_show | completed | abandoned | admin_override`.

The publisher is [`app/services/mqtt_publisher.publish_reservation_command`](../../backend/app/services/mqtt_publisher.py)
— the single source for outbound reservation traffic, used by every
business service. It always includes the user's *current* bound-plate
list so the Pi's LPR matcher has the freshest set.

### 7.4 Resync

The inbound `MQTTClient` issues `cloud/system/resync` (`{ "request": "replay" }`)
on every `on_connect`. The Pi's expected response is to replay its current
bay states on `cloud/bay/<code>/state` so the backend mirror reconverges.

---

## 8. HTTP + WebSocket API

JSON envelope on every error:

```json
{ "error": { "code": "reservation_not_found",
             "message": "...",
             "details": { ... } } }
```

Handled centrally in [`app/utils/errors.py`](../../backend/app/utils/errors.py).
HTTP status comes from the `APIError` subclass (`NotFoundError=404`,
`ConflictError=409`, `ValidationError=422`, `UnauthorizedError=401`,
`ForbiddenError=403`, `PaymentError=402`). Frontend's
[`api/client.ts`](../../frontend/src/api/client.ts) parses this envelope
into a `ApiError` class.

### 8.1 Routes

| Method | Path | Auth | Handler |
|--------|------|------|---------|
| GET | `/healthz` | — | liveness |
| GET | `/readyz` | — | DB ping; 503 when DB unreachable |
| POST | `/api/v1/auth/register` | — | `auth_service.register` |
| POST | `/api/v1/auth/login` | — | `auth_service.login` (JWT in body) |
| GET | `/api/v1/auth/me` | JWT | current user |
| GET | `/api/v1/bays` | — | list bays (public) |
| GET | `/api/v1/bays/{code}` | — | bay detail |
| GET | `/api/v1/bays/{code}/events` | JWT + admin | paged audit log, `?limit` `?before` |
| GET | `/api/v1/users/me/plates` | JWT | list bound plates |
| POST | `/api/v1/users/me/plates` | JWT | add plate; 422 `plate_limit_exceeded` / 409 `plate_already_bound` |
| DELETE | `/api/v1/users/me/plates/{plate}` | JWT | remove plate (returns 200 `{}` — see code note re: eventlet + 204) |
| POST | `/api/v1/reservations` | JWT | create reservation; gates booking on pre-auth |
| GET | `/api/v1/reservations` | JWT | list user's reservations |
| GET | `/api/v1/reservations/{id}` | JWT | reservation detail (admin can see any) |
| POST | `/api/v1/reservations/{id}/cancel` | JWT | cancel; 409 if not cancellable |
| POST | `/api/v1/reservations/{id}/check-in` | JWT | QR / manual check-in; 409 `vehicle_not_detected_yet` while `ACTIVE` |
| GET | `/api/v1/users/me/payments` | JWT | payment history |
| GET | `/api/v1/users/me/payments/{id}` | JWT | one payment |
| GET | `/api/v1/conflicts` | JWT + admin | open conflicts |
| GET | `/api/v1/conflicts/{id}/evidence` | JWT + admin | JPEG (`send_file`); 404 `evidence_purged` if past retention |
| POST | `/api/v1/conflicts/{id}/resolve` | JWT + admin | resolve (`vehicle_left / admin_resolved / user_arrived_and_checked_in`) |
| POST | `/api/v1/internal/conflicts/evidence` | Pi bearer token | upload strong-conflict JPEG (`multipart/form-data`) |

Authoritative schemas: [openapi.yaml](./openapi.yaml).

### 8.2 Booking request

`POST /api/v1/reservations`:

```json
{ "bay_code": "A1",
  "expected_arrival_time": "2026-05-01T10:30:00Z",
  "card": {
    "number": "4242424242424242",
    "cvv": "123",
    "expiry_month": 12,
    "expiry_year": 2030,
    "holder_name": "Alice Demo"
  } }
```

The card is validated against the in-process mock bank
([`payment_service.validate_card`](../../backend/app/services/payment_service.py)),
the deposit is debited (`SELECT ... FOR UPDATE` on `mock_cards`), the
reservation row is inserted, and the `pre_auth` payment row is inserted
in the **same transaction**. Failure modes (in priority order):

- `validation_error` `invalid_arrival_time` / `outside_booking_window`
- `validation_error` `no_bound_plates` — user has zero bound plates
- `not_found` `bay_not_found`
- `conflict` `bay_offline` / `bay_not_available`
- `payment_error` `card_invalid` / `card_expired` / `insufficient_funds`
- `conflict` `reservation_already_active` — race lost the partial unique index

Successful response is `ReservationOut` with a `payment: { deposit_cents }`
sub-object that the dashboard renders as "$XX.YY held on your card".

### 8.3 WebSocket — `/ws` namespace

[`app/sockets/events.py`](../../backend/app/sockets/events.py) emits:

| Event | Payload (summary) | When |
|-------|--------------------|------|
| `bay.updated` | bay code, public state, mirror state, last distance, sensor seen | Any bay-state change |
| `reservation.updated` | reservation snapshot | Any status transition |
| `reservation.pending_check_in` | reservation id + grace expires | On `pending_check_in` event |
| `reservation.auto_checked_in` | reservation snapshot + recognised plate | On `auto_check_in` event (LPR match) |
| `plate.updated` | user id + new plate list | After plate add/remove |
| `conflict.raised` / `conflict.resolved` | conflict id, kind, recognised plate | Strong/weak alert lifecycle |
| `payment.deposit_released` | reservation id, amount, reason | On clean cancel / completion / remainder release |
| `payment.refunded` | reservation id, amount | On strong-conflict refund (admin or holder no-fault cancel) |
| `payment.penalty_captured` | reservation id, penalty kind, amount | On `late_cancel` / `no_show` / `weak_conflict` |

The frontend filters owner-targeted events client-side
([`realtime/bus.ts`](../../frontend/src/realtime/bus.ts)) — there is no
per-user room today; every authenticated client sees every event and
drops anything whose `user_id` is not theirs.

---

## 9. Configuration

Settings come from [`backend/app/config.py`](../../backend/app/config.py)
(a frozen `Settings` dataclass). Defaults are loaded from
`backend/.env` via `python-dotenv`; real `os.environ` always wins. Example
values live in [`backend/.env.example`](../../backend/.env.example).

Important keys:

| Key | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | `postgresql+psycopg://parkreserve:parkreserve@localhost:5432/parkreserve` | DB |
| `PORT` | `8000` | HTTP port |
| `CORS_ORIGINS` | `http://localhost:3000` | comma-separated allow-list (`.env.example` adds `:5173` for Vite) |
| `MQTT_ENABLED` | `true` | Skip MQTT entirely when false (tests / disconnected dev) |
| `MQTT_HOST` / `MQTT_PORT` / `MQTT_TLS` / `MQTT_USERNAME` / `MQTT_PASSWORD` | local mosquitto | HiveMQ Cloud in prod |
| `MQTT_TOPIC_PREFIX` | `cloud` | Topic root |
| `BOOKING_WINDOW_MINUTES` | `60` | R11 |
| `ARRIVAL_GRACE_MINUTES` | `5` (code) / `1` (`.env.example` dev) | No-show grace |
| `CHECK_IN_GRACE_MINUTES` | `5` (code) / `1` (`.env.example` dev) | Weak-conflict grace |
| `LATE_CANCEL_CUTOFF_MINUTES` | `15` | Late-cancel threshold |
| `PLATES_PER_USER_MAX` | `5` | Plate cap (DB trigger is hard-coded to 5) |
| `LPR_CONFIDENCE_THRESHOLD` | `0.80` | Reserved (LPR runs on the Pi; backend records the value) |
| `DEPOSIT_CENTS` | `1000` ($10) | Deposit at booking |
| `PENALTY_CENTS` | `500` ($5) | Penalty per breach kind |
| `EVIDENCE_RETENTION_DAYS` | `30` | Image purge |
| `EVIDENCE_STORAGE_PATH` | `/var/lib/parkreserve/evidence` | JPEG storage on disk |
| `EVIDENCE_UPLOAD_TOKEN` | unset → no token check | Shared bearer for Pi → backend image upload |
| `RECONCILE_INTERVAL_SECONDS` | `30` | Sweeper period |
| `PURGE_INTERVAL_HOURS` | `24` | Nightly purge period |

`Settings.is_production` is `env == "production"`; the dev / test path
keeps `DEBUG` logging and disables some prod-only behaviours.

---

## 10. Testing

Layout under [backend/tests/](../../backend/tests/) (~30 files):

| File | Covers |
|------|--------|
| `test_app_factory.py`, `test_runtime_entrypoints.py` | `create_app` is side-effect-free; `start_runtime_services` is idempotent |
| `test_alembic_migration.py` | Upgrade + downgrade against real Postgres |
| `test_api_auth.py` | Register / login / me |
| `test_api_bays.py`, `test_api_extras.py` | Bay listing, event log paging |
| `test_api_plates.py` | Plate CRUD + cap trigger |
| `test_api_reservations.py` | Booking with card, late cancel, double-book guard, check-in 409 |
| `test_api_payments.py` | Payment history + receipt detail |
| `test_api_conflicts.py`, `test_api_conflicts_more.py` | Admin list, resolve, evidence upload |
| `test_api_health.py` | `/healthz` `/readyz` |
| `test_payment_service.py` | Idempotency, insufficient funds, refund / release accounting |
| `test_mqtt_topics.py` | Topic parsing + payload schemas (especially `extra="forbid"`) |
| `test_mqtt_client.py`, `test_mqtt_init.py`, `test_publisher.py` | Connect / subscribe / dispatch |
| `test_mqtt_handlers.py`, `test_mqtt_ingest.py`, `test_mqtt_commands.py` | End-to-end ingest paths |
| `test_event_handlers.py`, `test_event_dispatcher_extra.py`, `test_event_dispatcher_more.py` | auto_check_in / pending_check_in / conflict_strong / conflict_weak / no_show / dedupe |
| `test_strong_conflict_recovery.py` | `bay_service` restore + rollback paths |
| `test_bay_service_extra.py`, `test_conflict_service_extra.py` | Mirror writes, image purge, upsert |
| `test_reconcile_job.py` | Sweeper synthesises correct events |
| `test_purge_job.py` | 30-day image purge |
| `test_jobs_startup.py` | Scheduler wiring |
| `test_resilience_reconnect.py` | Reconnect + resync semantics |
| `test_seed_data.py`, `test_config.py` | Seed scripts + settings overrides |

`pyproject.toml` enforces `fail_under = 90` on coverage. Tests use the
real PostgreSQL service via `pytest-postgresql`; there is no SQLite path.

The Pi mock under [`backend/scripts/`](../../backend/scripts/) supports
running demos and integration tests without hardware:

- `mock_pi_publisher.py` — emits the realistic Pi event stream including
  `auto_check_in` and `conflict_strong`.
- `mock_pi_subscriber.py` — listens for `cloud/bay/<code>/reservation` and
  verifies the bound-plate list is published correctly.

---

## 11. Operations

### 11.1 Local development

```bash
cd backend
make install                 # python3.11 -m venv .venv + pip install -e .[dev]
make up                      # docker compose: postgres + mosquitto
make migrate                 # alembic upgrade head
make seed                    # 3 bays, demo user with plates, mock cards
make dev                     # python run_dev.py — HTTP + Socket.IO + MQTT + jobs
```

Convenience scenarios live in `make seed-ready / seed-conflict /
seed-checked-in / seed-history` — see [scripts/seed.py](../../backend/scripts/seed.py)
for the dataset definitions.

### 11.2 Production deployment

One systemd unit, `parkreserve-web.service`, runs the same `app.web.main`
entrypoint behind Caddy:

```
[Unit]
Description=ParkReserve backend (web + MQTT + jobs)
After=network.target postgresql.service

[Service]
WorkingDirectory=/opt/parkreserve/backend
ExecStart=/opt/parkreserve/backend/.venv/bin/python run_dev.py
Restart=on-failure
```

`deploy/bootstrap.sh` runs `alembic upgrade head` before the service
restarts. Caddy fronts the process for auto-HTTPS; the WebSocket and
REST API share the same origin (no cross-origin friction with `/ws`).

### 11.3 Health endpoints

After the runtime refactor (see `backend-runtime-refactor-plan.md`):

- `/healthz` — process is up; no I/O. Always 200 while Flask is serving.
- `/readyz` — runs `SELECT 1` against the DB; returns 200 on success or
  503 on failure. Does **not** assert MQTT readiness (the publisher
  degrades gracefully when the broker is down — services log
  `mqtt.command_skipped_disabled` and business state still mutates).

---

## 12. Frontend integration summary

The frontend [`frontend/`](../../frontend) is a Vite + React 18 + TanStack
Query SPA, talking to this backend over:

- REST (`api/client.ts` wraps `ky`, attaches `Authorization: Bearer …`,
  translates the JSON error envelope).
- WebSocket (`realtime/socket.ts` lazily opens one `/ws` connection;
  `realtime/bus.ts` validates every payload with Zod, invalidates
  TanStack Query caches, and surfaces toasts).

Routing is in [`frontend/src/app/root.tsx`](../../frontend/src/app/root.tsx):

- `/`, `/login`, `/register`, `/help` — public.
- `/app/*` — driver (auth gated): home, plates, booking wizard, cockpit,
  payments history.
- `/admin/*` — admin (role gated): grid, bay detail + event log,
  conflicts queue.

Card schema in [`frontend/src/schemas/reservation.ts`](../../frontend/src/schemas/reservation.ts)
mirrors the backend's `CardDetails` 1:1. WS event schemas in
[`frontend/src/schemas/realtime.ts`](../../frontend/src/schemas/realtime.ts)
match [`app/sockets/events.py`](../../backend/app/sockets/events.py)
field-for-field. Any drift trips a Zod error at runtime (logged + dropped
by the bus, not crashed).

---

## 13. What's intentionally NOT here

- **Celery / Redis / external queue.** APScheduler in-process is enough.
- **Multi-process worker split.** The original runtime refactor plan
  proposed separating web / MQTT / scheduler into three units; the
  implementation kept them in one. See `backend-runtime-refactor-plan.md`
  §"Current state".
- **`capture` payment action.** Per-time parking-fee capture is out of
  scope (proposal §5.6).
- **Real payment provider.** All cards are in-process mock-bank rows;
  the frontend booking form carries a "MOCK PAYMENT — DO NOT ENTER REAL
  CARD DETAILS" banner.
- **Ownership-verified plates.** Plate strings are taken from user input
  as-is (proposal §5.6). Cross-user plate collisions are tolerated
  because matching is always scoped to one reservation's bound list.
- **S3 / object storage.** Evidence JPEGs are on local disk under
  `EVIDENCE_STORAGE_PATH`. Sufficient for the EC2-colocated demo.
- **Retained MQTT messages / LWT.** Resync on connect is the recovery
  mechanism.
