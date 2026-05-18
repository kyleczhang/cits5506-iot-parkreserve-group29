# ParkReserve

ParkReserve is a multi-tier IoT parking reservation system built for CITS5506 Group 29. It combines:

- a cloud backend for accounts, reservations, payments, conflicts, and realtime updates
- a React web app for drivers and admins
- a Raspberry Pi gateway for local orchestration and plate-recognition decisions
- ESP32 bay nodes for sensing, LED/buzzer feedback, and image upload

This README is the entry point for the whole repository. It explains what the system does, how the subsystems fit together, and the fastest way to run the software demo.

## What The System Does

ParkReserve is designed for reserved parking bays in a paid facility.

At a high level:

- drivers register and bind one or more licence plates
- a driver reserves a bay for a future arrival time
- the backend places a mock deposit hold at booking time
- the backend sends the reservation and bound plates to the Raspberry Pi over HiveMQ
- when a vehicle arrives, the Pi evaluates the bay state and the recognised plate
- a matching plate auto-checks in the reservation
- a low-confidence read waits for manual check-in
- a mismatched plate becomes a strong conflict
- no-shows, weak conflicts, and late cancels incur penalties from the held deposit
- strong conflicts refund the reserving user in full because they are treated as the victim

The payment flow in this repository is mock only. It simulates deposit holds, releases, refunds, and penalties, but it does not talk to a real payment provider.

## Architecture

The repository implements three technical layers plus the web UI:

1. **Cloud layer**
   `backend/` owns user accounts, reservations, payment rules, conflict persistence, APIs, and realtime updates.
2. **Gateway layer**
   `raspberry/` runs on the Raspberry Pi and owns the per-bay state machine, local image reception, and local device orchestration.
3. **Device layer**
   `parking_node/` contains the ESP32 firmware for each bay node.
4. **Web UI**
   `frontend/` is the browser application used by drivers and admins.

## MQTT Topology

The project uses two separate MQTT links:

- **Backend <-> Raspberry Pi**
  This is the cloud-side MQTT link. In this project it runs on HiveMQ. Connection details are configured in the backend and Pi configuration.
- **Raspberry Pi <-> ESP32**
  This is the local MQTT link inside the car park. The broker runs on the Pi side, and ESP32 nodes connect to that local broker.

ESP32 nodes do not connect directly to HiveMQ.

## Repository Structure

```text
backend/       Flask + PostgreSQL + MQTT + Socket.IO cloud backend
frontend/      React + Vite web application
parking_node/  ESP32 firmware and edge-node protocol notes
raspberry/     Raspberry Pi gateway service and state machine
doc/           proposal, backend API specs, and coursework documents
```

Subsystem-specific setup lives in:

- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [raspberry/README.md](raspberry/README.md)
- [parking_node/README.md](parking_node/README.md)

## Core Business Rules

These are the most important system rules currently implemented in code:

- a user must bind at least one licence plate before booking
- a reservation must be in the future and within the configured booking window
- a bay can have only one open reservation at a time
- creating a reservation requires a successful mock deposit pre-authorization
- the Pi receives the reservation together with the user's bound plates for LPR matching
- a matching plate triggers automatic check-in
- a low-confidence recognition result leaves the bay in `pending_check_in` until manual check-in or timeout
- a mismatched plate becomes a strong conflict
- a clean cancellation releases the full deposit
- a late cancellation captures a penalty and releases the remainder
- a no-show or weak conflict also captures a penalty and releases the remainder
- a strong conflict refunds the reserving user in full
- after a checked-in vehicle leaves, the reservation completes and the deposit is released

## Quick Start

If you only want to run the software demo locally, the shortest path is `backend + frontend`.

### Prerequisites

- Python `3.11`
- Node.js `>= 20.10`
- Docker and Docker Compose

### 1. Start the backend

```bash
cd backend
make install
cp .env.example .env
make up
make migrate
make seed
make dev
```

This gives you:

- backend API: `http://localhost:8000/api/v1`
- backend health: `http://localhost:8000/healthz`
- PostgreSQL: `localhost:5432`
- local Mosquitto for development: `localhost:1883`

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
corepack enable
pnpm install
cp .env.example .env
pnpm dev
```

Then open `http://localhost:5173`.

## Demo Accounts

After `make seed`, the backend creates these demo accounts:

| Role | Email | Password |
|------|-------|----------|
| driver | `nyx@parkreserve.local` | `nyxParkreserve29!` |
| driver | `riya@parkreserve.local` | `riyaParkreserve29!` |
| driver | `yuan@parkreserve.local` | `yuanParkreserve29!` |
| driver | `cheng@parkreserve.local` | `chengParkreserve29!` |
| admin | `admin@parkreserve.local` | `adminParkreserve29!` |

## Where To Look Next

If you are working on a specific subsystem:

- backend API and runtime: [backend/README.md](backend/README.md)
- frontend routes and scripts: [frontend/README.md](frontend/README.md)
- Pi gateway behaviour: [raspberry/README.md](raspberry/README.md)
- ESP32 node behaviour: [parking_node/README.md](parking_node/README.md)

If you are looking for interfaces and design documents:

- backend HTTP contract: [doc/backend/openapi.yaml](doc/backend/openapi.yaml)
- backend MQTT contract: [doc/backend/asyncapi.yaml](doc/backend/asyncapi.yaml)
- project proposal and system context: [doc/proposal/proposal.md](doc/proposal/proposal.md)

## Scope Notes

- The backend owns reservation and payment policy.
- The Raspberry Pi owns the physical bay state machine.
- The payment flow is mock, not a real bank integration.
- `parking_node/pictureTestServer/` is only a local compatibility stub, not the real gateway.
- Some Pi-side configuration is intentionally local-only and not committed, as described in [raspberry/README.md](raspberry/README.md).

## Team

CITS5506 Group 29:

- Nyx Chen (`24290498`)
- Riya Sakhiya (`24601375`)
- Yuan Cong Yuan (`25003723`)
- Cheng Zhang (`24878502`)
