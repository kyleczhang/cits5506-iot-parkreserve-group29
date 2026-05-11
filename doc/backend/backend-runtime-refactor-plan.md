# Backend Runtime Refactor Plan

## Overview

This document proposes a structural cleanup of the backend runtime model.

The current codebase has two coupled problems:

1. Migration entrypoints are split between `flask db ...` and bare `alembic ...`.
2. `create_app()` does more than build a Flask app: it also starts MQTT and APScheduler side effects.

These problems show up as:

- fragile Alembic configuration and path assumptions
- `flask db upgrade` being coupled to application startup side effects
- CLI, shell, scripts, and one-off tasks accidentally starting background services
- unclear runtime boundaries between web, MQTT ingestion, and scheduled jobs

## Goals

- Make Alembic the only migration entrypoint.
- Make `create_app()` a pure application factory.
- Remove background side effects from CLI, tests, and scripts by default.
- Split long-running responsibilities into explicit runtime roles.
- Keep existing business behaviour intact.

## Non-Goals

- Rewriting business rules
- Replacing PostgreSQL
- Changing MQTT topics or payload contracts
- Introducing a full task queue such as Celery

## Proposed Runtime Model

### 1. Alembic As The Only Migration Entry

Remove `flask-migrate` from the project.

The only supported migration commands should be:

```bash
alembic upgrade head
alembic downgrade base
alembic revision --autogenerate -m "..."
```

Project rules:

- `alembic.ini` stays in `backend/`
- `migrations/` only contains Alembic scripts and env code
- Makefile, docs, deploy scripts, and tests all use bare Alembic

### 2. Pure App Factory

`create_app()` should only:

- load settings
- configure Flask
- initialize extensions
- register blueprints
- register error handlers
- import models and socket event modules needed for app assembly

It should not, by default:

- connect to MQTT
- start scheduler threads
- start any long-lived background loop

### 3. Explicit Runtime Roles

The backend should be split into three explicit process roles.

#### Web Process

Responsibilities:

- HTTP API
- Socket.IO
- database writes
- outbound MQTT command publishing

Does not own:

- inbound MQTT subscription loop
- APScheduler jobs

Suggested entrypoints:

- `app.web:main`
- `app:create_wsgi_app()` for Gunicorn/WSGI only

#### MQTT Worker

Responsibilities:

- connect to the broker
- subscribe to inbound MQTT topics
- dispatch inbound state/event messages into the service layer
- handle reconnect and replay behaviour

Does not own:

- HTTP serving
- scheduler jobs

Suggested entrypoint:

- `app.web:main`

#### Scheduler Worker

Responsibilities:

- run `reconcile_reservations`
- run `purge_evidence_images`

Does not own:

- HTTP serving
- inbound MQTT subscription

Suggested entrypoint:

- `app.web:main`

## MQTT Responsibilities

This is the most important boundary to get right.

### Inbound MQTT

Inbound consumption should live only in the MQTT worker.

That worker owns:

- broker connection lifecycle
- topic subscriptions
- handler registration
- background loop

### Outbound MQTT

The web process still needs to publish commands for flows such as:

- create reservation
- cancel reservation
- update plates

But it should not depend on a long-lived app-attached subscriber client.

Recommended approach:

- extract a dedicated outbound publisher abstraction
- let web-facing services call that publisher
- keep outbound publishing separate from inbound subscriber lifecycle

This avoids tying web request handling to a background consumer process model.

## Health Check Semantics

After the split, health endpoints should reflect process ownership.

### `/healthz`

Meaning:

- the web process is alive

### `/readyz`

Meaning:

- the web process can serve requests
- database access works
- required configuration is valid

It should not directly report inbound MQTT worker liveness as if that were part of web readiness.

Worker health should instead be handled by their own process supervision and logs.

## Required Code Changes

### A. Remove `flask-migrate`

Files likely affected:

- `backend/pyproject.toml`
- `backend/app/extensions.py`
- `backend/Makefile`
- any docs or tests still mentioning `flask db`

Changes:

- remove `flask-migrate` dependency
- remove `Migrate(...)` extension wiring
- remove `migrate.init_app(app, db)`
- replace `flask db ...` commands with `alembic ...`

### B. Restore Alembic Layout

Rules:

- move `alembic.ini` back to `backend/alembic.ini`
- keep `migrations/env.py` loading config from the normal bare Alembic layout

Why:

- deploy scripts already use bare Alembic
- migration tests already assume bare Alembic
- this avoids adapting the project to Flask-Migrate-specific expectations

### C. Pure `create_app()`

Current anti-pattern:

- `create_app()` defaults to starting MQTT and scheduler side effects in non-test contexts

Target contract:

```python
def create_app(*, settings: Settings | None = None) -> Flask:
    ...
```

or, if a temporary transition flag is still needed:

```python
def create_app(*, settings: Settings | None = None, start_background: bool = False) -> Flask:
    ...
```

The default must be side-effect free.

### D. Add Explicit Entrypoints

Suggested new files:

- `backend/app/web.py`
- `backend/app/mqtt_worker.py`
- `backend/app/scheduler.py`

Responsibilities:

- `web.py` starts the API and Socket.IO server
- `mqtt_worker.py` starts inbound MQTT consumption
- `scheduler.py` starts periodic jobs

### E. Separate Outbound Publisher

Files likely affected:

- `backend/app/services/mqtt_publisher.py`
- call sites in reservation and plate services
- MQTT client abstractions

Target behaviour:

- outbound publish remains available to web requests
- inbound subscriber client is no longer stored as a general-purpose app singleton

## Makefile Changes

Suggested commands:

```makefile
migrate:
	.venv/bin/alembic upgrade head

revision:
	.venv/bin/alembic revision --autogenerate -m "$(m)"

dev:
	.venv/bin/python -m app.web
```

Optional:

```makefile
migrate-down:
	.venv/bin/alembic downgrade base
```

## Deploy Changes

Production uses one service unit:

- `parkreserve-web.service`

This single process owns HTTP, Socket.IO, inbound/outbound MQTT, and the
background scheduler jobs.

`deploy/bootstrap.sh` should keep using:

```bash
.venv/bin/alembic upgrade head
```

## Test Strategy

The new runtime contract should be pinned by tests.

### 1. App Factory Tests

Examples:

- `create_app()` does not start schedulers
- `create_app()` does not initialize inbound MQTT by default
- explicit runtime entrypoints start only what they own

### 2. Alembic Smoke Contract

At minimum, validate:

```bash
alembic upgrade head
alembic downgrade base
```

This should be enforced either in CI shell steps or dedicated migration coverage.

### 3. Outbound MQTT Contract

Keep tests that prove:

- reservation creation publishes a command
- cancellation publishes a command
- plate updates publish when required

These tests should mock the outbound publisher and avoid real broker dependency.

### 4. MQTT Worker Contract

Worker-level tests should verify:

- handlers are registered
- inbound messages dispatch correctly
- reconnect and replay logic remain intact

## Recommended Rollout Plan

### Phase 1

- move `alembic.ini` back to `backend/`
- remove `flask-migrate`
- update Makefile to use bare Alembic
- update docs, deploy script references, and migration tests

### Phase 2

- remove background startup from default app factory behaviour
- keep CLI, scripts, and tests side-effect free
- add app factory contract tests

### Phase 3

- introduce explicit `web`, `mqtt_worker`, and `scheduler` entrypoints
- move inbound MQTT and scheduler startup out of the web process

### Phase 4

- cleanly separate outbound MQTT publish logic from inbound subscriber lifecycle
- adjust readiness semantics if needed
- split production service units

## Tradeoffs

### Benefits

- one migration path instead of two
- clean app factory semantics
- no hidden CLI side effects
- clearer process ownership
- safer future scaling beyond a single web worker

### Costs

- more moving parts at runtime
- more deployment wiring
- some refactor work around MQTT publishing

## Conclusion

This plan fixes the real architectural issue rather than only patching a symptom.

If the only goal is to make `make migrate` work again, a local path fix is enough.
If the goal is to make migrations, CLI usage, tests, and runtime boundaries stable over time, this refactor is the stronger solution:

- Alembic as the only migration interface
- pure app factory semantics
- explicit web/MQTT/scheduler runtime roles
- tests that lock these contracts in place
