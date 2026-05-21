# ParkReserve Backend

Flask + PostgreSQL + MQTT + Socket.IO backend for the ParkReserve IoT parking-reservation system.

## Overview

Current backend responsibilities:

- expose REST endpoints under `/api/v1`
- push realtime updates over Socket.IO namespace `/ws`
- persist bays, reservations, plates, payments, conflicts, bay events, and sensor readings in PostgreSQL
- consume bay state / event messages from MQTT
- publish reservation commands back to the edge gateway
- run background jobs for reservation reconciliation and evidence cleanup

In local development, `make dev` starts the whole runtime as one process: HTTP + Socket.IO + MQTT + scheduled jobs.

MQTT deployment model:

- backend <-> Raspberry Pi uses the cloud-side MQTT broker
- in this project that cloud-side broker is HiveMQ
- broker host, port, TLS, username, and password are configured via backend environment variables

## Business Rules

The backend owns the main reservation and payment rules, while the Pi owns the physical bay state machine.

Current backend-side rules:

- a user must bind at least one licence plate before creating a reservation
- a reservation must be in the future and within the configured booking window
- a bay can have only one open reservation at a time
- reservation creation is gated on a successful mock deposit pre-authorization
- the backend publishes reservation commands to the Pi together with the user's bound plates for LPR matching
- cancelling 15 minutes or more before arrival releases the full deposit
- cancelling within the late-cancel cutoff captures a penalty and releases the remainder
- no-show and weak-conflict outcomes also capture a penalty and release the remainder
- a strong conflict is treated as a victim case for the reserving user, so the held deposit is refunded in full
- manual check-in is only a fallback; automatic check-in via plate match is the normal path

The mock-payment service is idempotent, so repeated MQTT messages, retries, or double-clicked actions do not create duplicate charges.

## Prerequisites

- Python `3.11`
- PostgreSQL `16`
- Docker and Docker Compose if you want the provided local Postgres + Mosquitto stack

## Quick Start

From `backend/`:

```bash
make install
cp .env.example .env
make up
make migrate
make seed
make dev
```

At that point:

- API base URL: `http://localhost:8000/api/v1`
- health check: `http://localhost:8000/healthz`
- readiness check: `http://localhost:8000/readyz`

`make up` starts:

- PostgreSQL on `localhost:5432`
- Mosquitto on `localhost:1883`

The bundled Mosquitto container is only a local-development convenience. In the intended full deployment, the backend connects to the Pi side through the configured cloud MQTT broker rather than a local in-repo broker.

If you want a clean reset and then an immediate boot:

```bash
make reset-run
```

## Seed Data And Demo Accounts

`make seed` truncates application tables and rebuilds a known demo dataset. The base seed creates:

- 3 bays: `A1`, `A2`, `A3`
- 5 users
- demo licence plates
- mock payment cards

Seeded accounts:

| Role | Email | Password |
|------|-------|----------|
| driver | `nyx@parkreserve.local` | `nyxParkreserve29!` |
| driver | `riya@parkreserve.local` | `riyaParkreserve29!` |
| driver | `yuan@parkreserve.local` | `yuanParkreserve29!` |
| driver | `cheng@parkreserve.local` | `chengParkreserve29!` |
| admin | `admin@parkreserve.local` | `adminParkreserve29!` |

Scenario shortcuts layer extra reservations and payment history on top of that base dataset:

```bash
make seed-ready       # one upcoming active reservation, for booking/arrival/check-in demos
make seed-conflict    # one pending-check-in reservation, for conflict and admin resolution demos
make seed-checked-in  # one reservation already checked in, for leave-bay/completion demos
make seed-history     # closed reservations and ledger history, for payment outcome demos
```

To inspect or combine datasets manually:

```bash
.venv/bin/python scripts/seed.py --list
.venv/bin/python scripts/seed.py --dataset integration_ready --dataset payments_history
```

## Configuration

Settings are loaded from environment variables, with `backend/.env` read automatically by the runtime. Start from [`.env.example`](.env.example).

Common variables:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL DSN |
| `PORT` | backend HTTP port |
| `CORS_ORIGINS` | comma-separated allowed origins |
| `MQTT_ENABLED` | enable inbound/outbound MQTT |
| `MQTT_HOST`, `MQTT_PORT` | broker address |
| `MQTT_TLS` | turn on TLS for the HiveMQ broker |
| `MQTT_USERNAME`, `MQTT_PASSWORD` | broker credentials |
| `MQTT_TOPIC_PREFIX` | topic root, default `cloud` |
| `BOOKING_WINDOW_MINUTES` | max lead time for reservation creation |
| `ARRIVAL_GRACE_MINUTES` | grace before no-show logic |
| `CHECK_IN_GRACE_MINUTES` | grace after `pending_check_in` |
| `LATE_CANCEL_CUTOFF_MINUTES` | late-cancel threshold |
| `PLATES_PER_USER_MAX` | per-user plate cap |
| `LPR_CONFIDENCE_THRESHOLD` | accepted LPR threshold |
| `DEPOSIT_CENTS` | mock deposit hold amount |
| `PENALTY_CENTS` | mock penalty capture amount |
| `EVIDENCE_STORAGE_PATH` | stored conflict JPEG directory |
| `EVIDENCE_UPLOAD_TOKEN` | bearer token for internal evidence upload |
| `RECONCILE_INTERVAL_SECONDS` | reservation reconciliation job cadence |
| `PURGE_INTERVAL_HOURS` | evidence cleanup job cadence |

Note: the values shown in [`.env.example`](.env.example) are the intended local-dev defaults. If `.env` is absent, the Python settings layer still applies built-in fallbacks.

For this project, these MQTT variables should point to the HiveMQ broker used for the backend/Pi link.

## API Summary

Base path: `/api/v1`

Auth:

| Method | Path | Access |
|--------|------|--------|
| `POST` | `/auth/register` | public |
| `POST` | `/auth/login` | public |
| `GET` | `/auth/me` | JWT |

Bays:

| Method | Path | Access |
|--------|------|--------|
| `GET` | `/bays` | public |
| `GET` | `/bays/<code>` | public |
| `GET` | `/bays/<code>/events` | admin JWT |

Driver resources:

| Method | Path | Access |
|--------|------|--------|
| `GET` | `/users/me/plates` | JWT |
| `POST` | `/users/me/plates` | JWT |
| `DELETE` | `/users/me/plates/<plate>` | JWT |
| `POST` | `/reservations` | JWT |
| `GET` | `/reservations` | JWT |
| `GET` | `/reservations/<id>` | owner or admin JWT |
| `POST` | `/reservations/<id>/cancel` | JWT |
| `POST` | `/reservations/<id>/check-in` | JWT |
| `GET` | `/users/me/payments` | JWT |
| `GET` | `/users/me/payments/<id>` | JWT |

Admin conflict workflow:

| Method | Path | Access |
|--------|------|--------|
| `GET` | `/conflicts` | admin JWT |
| `GET` | `/conflicts/<id>/evidence` | admin JWT |
| `POST` | `/conflicts/<id>/resolve` | admin JWT |
| `POST` | `/internal/conflicts/evidence` | shared bearer token |

Health endpoints are outside `/api/v1`:

- `GET /healthz`: process liveness
- `GET /readyz`: returns `200` only when the database is reachable

## Realtime Events

Socket.IO namespace: `/ws`

Current server-to-client events:

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

## Tests

Run the backend test suite with:

```bash
make test
```

The suite uses real PostgreSQL via `pytest-postgresql`; it does not swap in SQLite. Coverage is enforced at 90% in [pyproject.toml](./pyproject.toml).

## Migrations

Alembic files live in [`migrations/`](./migrations/) and are driven by [`alembic.ini`](./alembic.ini).

```bash
make migrate
make revision m='add new column'
```

## Deployment Notes

The repo includes deployment helpers in [`deploy/`](./deploy/):

- [`deploy/bootstrap.sh`](./deploy/bootstrap.sh)
- [`deploy/parkreserve-web.service`](./deploy/parkreserve-web.service)
- [`deploy/Caddyfile`](./deploy/Caddyfile)

The intended deployed runtime is still the same application shape as local dev: one backend service process running HTTP, Socket.IO, MQTT, and scheduled jobs.
