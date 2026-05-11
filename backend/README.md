# ParkReserve — Backend (Subsystem F)

Flask + PostgreSQL + MQTT + Socket.IO cloud backend for the ParkReserve IoT parking reservation system (CITS5506 group 29, S1 2026).

This is the "how-to-guide" required by the *Code → Exemplary* row of the project-report rubric: every command below is copy-pasteable and should work on a clean Ubuntu 24.04 or macOS host.

## What it does

- Ingests MQTT bay-state mirrors and state-machine events from the Raspberry Pi edge gateway (topics `cloud/bay/<code>/state` and `cloud/bay/<code>/event`).
- Persists bay state, reservations, sensor readings, audit events, conflicts, and mock-payment ledger rows in PostgreSQL.
- Exposes a REST + Socket.IO API consumed by the React dashboard.
- Publishes reservation commands back to the Pi on `cloud/bay/<code>/reservation` with QoS 1, and requests replays on `cloud/system/resync`.
- Detects strong / weak conflicts, supports JPEG evidence upload for strong conflicts, and exposes admin conflict-resolution endpoints.
- Runs a safety-net reconcile sweep every 30 seconds by default and a periodic evidence-image purge job.

The full design is in [`../doc/backend/backend-implementation-plan.md`](../doc/backend/backend-implementation-plan.md) and the schema in [`../doc/backend/database-design.md`](../doc/backend/database-design.md).

## Requirements

- Python **3.11** (pinned in `pyproject.toml`)
- PostgreSQL **16** — **required in every environment including tests**
- Docker (optional, recommended for local dev)

## Quick start — local dev with Docker

The backend now runs as **one long-lived process**:

- **web runtime** — HTTP, Socket.IO, outbound MQTT publisher, inbound MQTT consumer, APScheduler jobs (`make dev`)

One-time setup:

```bash
# from backend/
make install            # venv + deps
cp .env.example .env    # edit if you want
make up                 # starts postgres + mosquitto via docker-compose
make migrate            # applies Alembic migrations (seeds 3 demo bays)
make seed               # creates demo users, plates, and mock-payment cards
```

Then start the backend:

```bash
make dev                # web + MQTT + jobs on :8000
```

## Demo scenarios

The seed runner is designed for **repeatable demos**. Every seed command clears
the application tables and rebuilds a known state from scratch.

Base dataset:

```bash
make seed               # same as make seed-demo; demo users, bays, plates, cards
```

Scenario shortcuts:

```bash
make seed-ready         # demo + one active reservation approaching arrival
make seed-conflict      # demo + one pending-check-in conflict scenario
make seed-checked-in    # demo + one reservation already checked in
make seed-history       # demo + closed reservations and payment-history records
```

If you want the raw CLI, list dataset names first:

```bash
.venv/bin/python scripts/seed.py --list
```

Example: load multiple scenarios in one reset:

```bash
.venv/bin/python scripts/seed.py \
  --dataset integration_ready \
  --dataset payments_history
```

Recommended presentation flow:

1. `make seed-ready` for the reserve -> arrive / check-in path.
2. `make seed-conflict` for the strong-conflict and admin-resolution path.
3. `make seed-history` for payment outcomes and historical evidence.

Optional — simulate the Raspberry Pi (in a second terminal):

```bash
.venv/bin/python scripts/mock_pi_publisher.py
```

This publishes simulated bay-state / event traffic for A1 / A2 / A3. The `cycle` scenario runs every 3 seconds by default. The backend process consumes those messages and the dashboard updates in real time — if `make dev` isn't running, nothing visible happens.

Optional third terminal to tap the command channel that would normally go to the Pi:

```bash
.venv/bin/python scripts/mock_pi_subscriber.py
```

## Configuration

Every setting is an env var; defaults target local Docker. See [`.env.example`](.env.example) for the full list. The most common:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | Postgres DSN (always postgres — no sqlite) | `postgresql+psycopg://parkreserve:parkreserve@localhost:5432/parkreserve` |
| `PORT` | Flask / Gunicorn bind port | `8000` |
| `MQTT_HOST`, `MQTT_PORT` | Broker to connect to | `localhost:1883` |
| `MQTT_TLS` | `true` when pointing at HiveMQ Cloud | `false` |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | HiveMQ creds | empty |
| `MQTT_ENABLED` | set `false` in unit tests | `true` |
| `MQTT_TOPIC_PREFIX` | Topic root for bay / system channels | `cloud` |
| `BOOKING_WINDOW_MINUTES` | Max advance booking window | `60` |
| `ARRIVAL_GRACE_MINUTES` | No-show grace after expected arrival | `5` |
| `CHECK_IN_GRACE_MINUTES` | Manual check-in grace after `pending_check_in` | `5` |
| `LATE_CANCEL_CUTOFF_MINUTES` | Late-cancel threshold | `15` |
| `DEPOSIT_CENTS` | Mock pre-auth hold amount | `1000` |
| `PENALTY_CENTS` | Default penalty capture amount | `500` |
| `RECONCILE_INTERVAL_SECONDS` | Safety-net sweep interval | `30` |
| `CORS_ORIGINS` | CSV of allowed origins | `http://localhost:3000` |

## REST + Socket.IO API

Base path: `/api/v1`. Quick reference:

| Method | Path | Auth |
|--------|------|------|
| POST | `/auth/register` | — |
| POST | `/auth/login` | — |
| GET  | `/auth/me` | JWT |
| GET  | `/bays` | — |
| GET  | `/bays/<code>` | — |
| GET  | `/bays/<code>/events` | Admin JWT |
| GET  | `/users/me/plates` | JWT |
| POST | `/users/me/plates` | JWT |
| DELETE | `/users/me/plates/<plate>` | JWT |
| POST | `/reservations` | JWT |
| GET  | `/reservations` | JWT |
| GET  | `/reservations/<id>` | JWT / Admin JWT |
| POST | `/reservations/<id>/cancel` | JWT |
| POST | `/reservations/<id>/check-in` | JWT |
| GET  | `/users/me/payments` | JWT |
| GET  | `/users/me/payments/<id>` | JWT |
| GET  | `/conflicts` | Admin JWT |
| GET  | `/conflicts/<id>/evidence` | Admin JWT |
| POST | `/conflicts/<id>/resolve` | Admin JWT |
| POST | `/internal/conflicts/evidence` | Shared bearer token |

Socket.IO namespace `/ws` broadcasts:

- `bay.updated`
- `reservation.updated`
- `reservation.pending_check_in`
- `reservation.auto_checked_in`
- `plate.updated`
- `conflict.raised`
- `conflict.resolved`
- `payment.deposit_released`
- `payment.refunded`
- `payment.penalty_captured`

Health: `GET /healthz` is liveness; `GET /readyz` returns 200 once the database is reachable.

## Tests

All tests run against **real PostgreSQL** via `pytest-postgresql`. No SQLite, no mocked database.

```bash
make test
```

This spins a dedicated PostgreSQL cluster in a temporary directory, enables the required PostgreSQL extensions, builds the schema from SQLAlchemy metadata for each test, runs the suite, and tears the cluster down. Migration coverage is exercised separately by `tests/test_alembic_migration.py`. Coverage gate is 90 %. See `tests/conftest.py` for the fixture layer.

## Database migrations

```bash
make migrate                         # apply latest
make revision m='add xyz column'     # generate a new revision
```

Alembic config is in `alembic.ini` / `migrations/`. The initial revision `20260421_01_initial` creates the PostgreSQL enums, all domain tables, the trigger-backed per-user plate cap, the partial unique indexes from the design doc, and seeds the three demo parking bays.

## Deploying to AWS EC2 (demo day)

The deployment target is `t3.micro` Ubuntu 24.04 with PostgreSQL colocated, Caddy in front for HTTPS, and **one** systemd unit for the backend runtime:

- `parkreserve-web.service` — Gunicorn + eventlet worker; HTTP, Socket.IO, inbound MQTT, outbound MQTT publisher, APScheduler jobs.

```bash
# on the EC2 host, as a sudo user
curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/backend/deploy/bootstrap.sh | bash
```

`deploy/bootstrap.sh` installs Python 3.11, PostgreSQL 16, Caddy, clones or updates the repo into `/opt/parkreserve`, creates `.env` if missing, runs migrations, and enables `parkreserve-web` plus `caddy`.

Note: the bootstrap script does **not** install Mosquitto on EC2. In production you should either point `MQTT_HOST` / `MQTT_PORT` / `MQTT_TLS` at a reachable broker such as HiveMQ Cloud, or provision a broker separately.

Minimum manual steps:

1. Install PostgreSQL 16, Python 3.11, Caddy, and build prerequisites.
2. Create the `parkreserve` PostgreSQL role and database.
3. Clone the repo into `/opt/parkreserve`, create the backend virtualenv, and install the package.
4. Create `backend/.env` with `DATABASE_URL`, JWT secrets, CORS origins, and MQTT broker settings.
5. Run `alembic upgrade head` and optionally `make seed`.
6. Install `deploy/parkreserve-web.service` and `deploy/Caddyfile`, update the domain, then enable the service.

Logs:

```bash
journalctl -u parkreserve-web       -f
```

Health probes: `/healthz` is liveness, `/readyz` returns 200 once the database is reachable.

## Project layout

Key directories are summarised below.

## License

MIT. Part of CITS5506 group 29 coursework.
