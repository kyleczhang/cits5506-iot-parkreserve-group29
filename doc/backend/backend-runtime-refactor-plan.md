# Backend Runtime — Current State and Refactor Notes

## 0. Status

This document started life as a forward-looking refactor plan. Most of the
refactor is now landed; what remains aspirational is called out explicitly
in §6.

Quick summary of what changed and what shipped:

| Goal from the original plan | Status |
|------------------------------|--------|
| Make Alembic the only migration entrypoint | **Done** — `flask-migrate` removed; `backend/alembic.ini` is in place; Makefile / deploy script use bare Alembic. |
| Make `create_app()` a pure factory (no MQTT, no scheduler) | **Done** — see [`app/__init__.py`](../../backend/app/__init__.py). |
| Remove background side effects from CLI / tests / scripts | **Done** — `create_app()` no longer starts long-lived loops; `start_runtime_services(app)` is the explicit opt-in. |
| Separate outbound publisher from inbound subscriber | **Done** — [`app/mqtt/publisher.py`](../../backend/app/mqtt/publisher.py) is publish-only; [`app/mqtt/client.py`](../../backend/app/mqtt/client.py) is subscribe-only. |
| Split web / MQTT-worker / scheduler into three process units | **Not done.** Single-process model (one systemd unit) was chosen instead. The pure factory + opt-in runtime services preserves the *option* to split later without further refactoring. |
| Tests pin the new runtime contract | **Done** — `test_app_factory.py`, `test_runtime_entrypoints.py`, `test_jobs_startup.py`. |

The rest of this document describes the runtime as it ships today, and
keeps the multi-process split as a future option.

---

## 1. Why the original problems happened

The pre-refactor code had two coupled issues:

1. **Two migration entrypoints** — `flask db ...` (flask-migrate) and bare
   `alembic ...` (CI shell + tests). Path assumptions in `alembic.ini`
   drifted between them.
2. **`create_app()` had side effects** — calling the factory connected to
   MQTT and started APScheduler. So CLI commands, ad-hoc shells, one-off
   scripts, and pytest collection would accidentally spin up background
   loops.

Symptoms included:

- `flask db upgrade` failing or running migrations in the wrong directory.
- pytest leaving paho threads attached after a session.
- Unclear ownership when something went wrong: was it the web request, the
  MQTT background thread, or the scheduler?

---

## 2. Current runtime model

### 2.1 One Linux process, three concerns

The backend ships as one systemd unit, `parkreserve-web.service`. That one
process hosts:

| Concern | Module | Threading |
|---------|--------|-----------|
| HTTP + Socket.IO | Flask + flask-socketio + eventlet | Main green pool |
| Outbound MQTT publisher | [`app/mqtt/publisher.py`](../../backend/app/mqtt/publisher.py) | Paho client thread (no subscriptions) |
| Inbound MQTT subscriber | [`app/mqtt/client.py`](../../backend/app/mqtt/client.py) | Paho client thread (subscribes + dispatches into Flask app context) |
| `reconcile_reservations` job | [`app/jobs/reconcile_reservations.py`](../../backend/app/jobs/reconcile_reservations.py) | APScheduler background thread |
| `purge_evidence_images` job | [`app/jobs/purge_evidence_images.py`](../../backend/app/jobs/purge_evidence_images.py) | APScheduler background thread |

The single-process choice keeps deployment simple: one SQLAlchemy
session factory, one Socket.IO emitter, no inter-process coordination.
For one Pi, three bays, and a small dashboard user-base, vertical
scaling on a `t3.micro` is enough.

### 2.2 Eventlet monkey-patch

`eventlet.monkey_patch()` must run **before** anything imports the `app`
package. Otherwise eventlet's "upgrade existing instances" pass trips
over Werkzeug LocalProxy objects already constructed by `app/__init__.py`
and leaves stdlib `RLock`s un-greened, which silently breaks
`socketio.emit()` calls from the paho background thread.

So the dev entrypoint is the top-level file
[`backend/run_dev.py`](../../backend/run_dev.py):

```python
import eventlet
eventlet.monkey_patch()

from app.web import main

if __name__ == "__main__":
    main()
```

[`app/__main__.py`](../../backend/app/__main__.py) refuses
`python -m app` (or `python -m app.web`) with `SystemExit(2)` and a
pointer to `run_dev.py`. `make dev` runs `run_dev.py`.

### 2.3 Factory + opt-in runtime services

`backend/app/__init__.py` exposes three entrypoints:

```python
def create_app(*, settings: Settings | None = None) -> Flask:
    """Pure factory. No MQTT. No scheduler. Safe for tests, CLI, scripts."""

def start_runtime_services(app: Flask) -> None:
    """Attach MQTT publisher + subscriber + both schedulers. Idempotent."""

def create_wsgi_app() -> Flask:
    """create_app() then start_runtime_services(). Used by app.web.main()."""
```

`start_runtime_services` registers an `atexit` cleanup that calls
`stop_runtime_services(app)` (publisher + subscriber stop, schedulers
shut down). `app.extensions["_runtime_started"]` / `"_runtime_stopped"`
flags keep both halves idempotent.

This gives us the testability of a pure factory **and** a single
production WSGI entrypoint that does the right thing on boot.

### 2.4 MQTT split (publisher vs subscriber)

The two paho clients are distinct objects with distinct lifecycles:

- The **publisher** (`PahoPublisher`) never subscribes and never sets an
  `on_message`. Its `on_connect` does nothing beyond setting a "connected"
  event for tests. It is the only client that the HTTP request path
  touches.
- The **subscriber** (`MQTTClient`) connects, subscribes to
  `cloud/bay/+/state`, `cloud/bay/+/event`, and `cloud/system/heartbeat`,
  registers handlers ([`app/mqtt/handlers.py`](../../backend/app/mqtt/handlers.py)),
  and publishes one `cloud/system/resync` on every (re)connect.

Application code only ever calls the publisher
([`app/services/mqtt_publisher.publish_reservation_command`](../../backend/app/services/mqtt_publisher.py)).
If MQTT is disabled (`MQTT_ENABLED=false`) the publisher is `None` and
the helper logs `mqtt.command_skipped_disabled` — the business state
still mutates, the test still passes, no broker is required.

### 2.5 Health endpoints

Reflect the single-process reality:

- **`/healthz`** — process liveness. No I/O. Always 200 while Flask is
  serving requests.
- **`/readyz`** — runs `SELECT 1` against the DB. Returns 200 on success
  or 503 on failure. Does **not** assert MQTT readiness — outbound
  publish is best-effort and the business path degrades gracefully when
  the broker is down (services log a "skipped" line and continue), so
  tying readiness to MQTT would create false negatives.

If we ever do the worker split in §6, worker liveness will be reported
through their own logs / systemd, not through `/readyz`.

---

## 3. Migrations

### 3.1 Bare Alembic

`flask-migrate` is gone. There is one canonical path:

```bash
cd backend
make migrate                          # alembic upgrade head
make revision m="describe change"    # alembic revision --autogenerate
```

Both wrap `.venv/bin/alembic`. `backend/alembic.ini` is the single config.
`backend/migrations/env.py` imports `app.extensions.Base` and the `app.models`
package so `target_metadata = Base.metadata` covers every table.

### 3.2 Migrations directory

```
backend/migrations/
├── env.py
├── script.py.mako
└── versions/
    ├── 20260421_01_initial.py
    └── 20260513_01_conflict_resolution_user_cancelled.py
```

`deploy/bootstrap.sh` runs `.venv/bin/alembic upgrade head` before the
systemd service starts. Tests run real migrations via
`test_alembic_migration.py`.

---

## 4. Testing the runtime contract

Three modules pin the new boundaries:

- **`test_app_factory.py`** — `create_app()` does not start the scheduler;
  does not connect to MQTT by default; registers blueprints; returns a
  Flask app that can serve `/healthz` without any extra wiring.
- **`test_runtime_entrypoints.py`** — `start_runtime_services` is
  idempotent; `stop_runtime_services` is idempotent; `create_wsgi_app`
  starts services exactly once.
- **`test_jobs_startup.py`** — scheduler jobs register with the right
  ids and intervals, and shut down cleanly.

Plus the existing MQTT contract suites
(`test_publisher.py`, `test_mqtt_client.py`, `test_mqtt_handlers.py`,
`test_mqtt_init.py`, `test_mqtt_topics.py`, `test_mqtt_commands.py`,
`test_mqtt_ingest.py`, `test_resilience_reconnect.py`).

Coverage gate is `fail_under = 90` (see `[tool.coverage.report]`).

---

## 5. Operational notes

### 5.1 Makefile

The canonical commands are now bare Alembic + `run_dev.py`:

```makefile
migrate:
    .venv/bin/alembic upgrade head

revision:
    .venv/bin/alembic revision --autogenerate -m "$(m)"

dev:
    .venv/bin/python run_dev.py
```

Additional targets seed scenario datasets (`seed-ready`, `seed-conflict`,
`seed-checked-in`, `seed-history`) and the `reset-run` combo
(`down → up → migrate → seed → dev`).

### 5.2 Deploy

```
backend/deploy/
├── parkreserve-web.service     # single systemd unit
├── Caddyfile                   # auto-HTTPS reverse proxy
└── bootstrap.sh                # alembic upgrade head before restart
```

The `[Service]` entrypoint is `python run_dev.py` (we use the same
entrypoint in prod for now; if/when we move to gunicorn workers, the
unit will swap to `gunicorn -k eventlet -w 1 'app:create_wsgi_app()'`).

### 5.3 Local dev MQTT

`docker/docker-compose.yml` brings up Mosquitto on localhost:1883 with
no auth. `MQTT_TLS=false`, `MQTT_USERNAME` / `MQTT_PASSWORD` unset. In
prod, HiveMQ Cloud over TLS:8883 with username/password.

---

## 6. Future: multi-process split (not done)

The pure factory + opt-in runtime services leaves the door open to
splitting concerns into separate processes:

| Process | Owns |
|---------|------|
| Web | HTTP, Socket.IO, outbound MQTT publisher |
| MQTT worker | Inbound subscriber + handlers |
| Scheduler | `reconcile_reservations` + `purge_evidence_images` |

What would need to change:

- A second entrypoint that calls `create_app()` and starts **only** the
  MQTT subscriber (and not the publisher / scheduler).
- A third entrypoint that calls `create_app()` and starts **only** the
  schedulers.
- Three systemd units. Caddy still fronts only the web unit.
- Socket.IO would need a Redis (or similar) message queue if the MQTT
  worker is going to broadcast `bay.updated` to web-connected clients —
  today both halves are in-process and `socketio.emit` reaches WS clients
  directly. This is the main reason the split has not happened yet.
- `/readyz` would stay focused on web-process needs; MQTT worker and
  scheduler liveness would surface through their own systemd journals
  and metrics (not the HTTP readiness probe).

Reasons to actually do this later: multiple web workers behind a load
balancer (publishing the same reservation command from two processes is
fine, ingesting the same Pi event from two subscribers is not), or
isolating crash domains so a slow paho handler doesn't pause HTTP
requests.

For the current scale (one Pi, three bays, demo dashboard usage) the
single process is simpler and the runtime contract tests pin the
boundaries we'll need when the split happens.

---

## 7. Tradeoffs we accepted

| Decision | Why we chose this |
|----------|-------------------|
| One systemd unit instead of three | Demo scale doesn't justify the operational overhead; pure factory keeps the split option open. |
| Outbound publisher is a separate paho client | Decoupling means a publish-only broker hiccup can't break the inbound subscription loop (and vice-versa), at the cost of one extra TCP connection. |
| Schedulers in-process, no Celery | APScheduler covers the two periodic jobs with zero external dependencies. |
| `/readyz` tied to DB only | MQTT is best-effort; surfacing every MQTT blip as "not ready" would make health checks noisy. |
| `run_dev.py` outside the `app/` package | Required so `eventlet.monkey_patch()` runs before any `app` import. |
| Same entrypoint in dev and prod | Avoids drift between `make dev` behaviour and production behaviour. Both call `create_wsgi_app()` → `start_runtime_services()`. |
