# ParkReserve — Frontend

React SPA for the ParkReserve operations console (CITS 5506 Group 29, Subsystem F frontend half).

This is the **driver-facing dashboard** *and* the **admin operations console** in a single deployable app, differentiated by route prefix and the JWT-encoded `role`. The backend lives under [../backend/](../backend/) and is the authoritative source of truth for every screen — see [../doc/frontend/frontend-implementation-plan.md](../doc/frontend/frontend-implementation-plan.md) for the full plan.

## How to use this guide

This README doubles as the rubric-required *How-to-guide* under the **Code (10)** category of [project-report-rubric.md](../doc/report/project-report-rubric.md): it covers hardware setup (by reference to the proposal and backend docs), software installation, and project operation end-to-end.

---

## 1. Hardware setup

Hardware setup lives upstream of this repository — three ESP32-CAM bay nodes and one Raspberry Pi 5 gateway, wired exactly as described in [../doc/proposal/proposal.md](../doc/proposal/proposal.md) §5. The frontend has no direct hardware dependency; it talks to the backend, and the backend mirrors hardware state over MQTT.

For local development you do **not** need any hardware. The backend ships a mock Pi publisher you can run to simulate bay state changes:

```bash
# in another terminal, with the backend running
cd ../backend
.venv/bin/python scripts/mock_pi_publisher.py
```

## 2. Software installation

Prerequisites:

- **Node.js ≥ 20.10** ([https://nodejs.org/](https://nodejs.org/))
- **pnpm 9.x**, installed via Node's built-in `corepack` shim (no global `npm i -g` required)
- A running ParkReserve backend on `http://localhost:8000` — see [../backend/README.md](../backend/README.md). At minimum: `make up && make migrate && make seed && make dev`.

Install:

```bash
cd frontend
corepack enable               # one-time, enables `pnpm` shim shipped with Node
pnpm install
cp .env.example .env          # tweak VITE_BACKEND_ORIGIN if your backend is elsewhere
pnpm dev                      # vite dev server on http://localhost:5173
```

Open `http://localhost:5173` in a modern browser. Vite proxies `/api`, `/healthz`, `/readyz`, and `/socket.io` to the backend origin from `.env`.

## 3. Project working — end-to-end demo flow

The seed script ([../backend/scripts/seed.py](../backend/scripts/seed.py)) creates one admin user and one driver user. After `pnpm dev`:

1. **Driver flow.**
   1. Click **Sign up** (or sign in with the seeded driver) and you land on the driver home at `/app`.
   2. Add a licence plate at `/app/plates` (the backend requires ≥ 1 bound plate before a reservation can be created — see [../backend/app/services/reservation_service.py](../backend/app/services/reservation_service.py), error code `no_bound_plates`).
   3. Click **Book** on any *available* bay tile. The booking wizard collects bay → time → mock card. Card numbers from the seed file (`4111 1111 1111 1111`, CVV `123`) are accepted; any other card returns `card_invalid`.
   4. Run `python scripts/mock_pi_publisher.py` in the backend to push a vehicle-detected MQTT event; the driver cockpit at `/app/reservations/:id` shows the **vehicle detected — please check in** banner. Click **Check in (manual)**, and the status flips to `CHECKED_IN`.
   5. Cancel a not-yet-arrived reservation to see the deposit released on the payments ledger at `/app/payments`.

2. **Admin flow.**
   1. Sign in as the seeded admin user. The router auto-redirects to `/admin/grid`.
   2. The bay grid shows live state for all bays, updating over WebSocket as the mock Pi publishes.
   3. When a strong conflict fires (mismatched LPR plate), it appears in the **Conflicts** queue at `/admin/conflicts`. Click a row to view the evidence JPEG, then resolve with **Vehicle left** or **Admin resolved**.

## 4. Scripts

| Script | What it does |
|--------|--------------|
| `pnpm dev` | Vite dev server with HMR + backend proxy |
| `pnpm build` | Type-check + production build to `dist/` |
| `pnpm preview` | Serve `dist/` locally to sanity-check the production bundle |
| `pnpm typecheck` | `tsc --noEmit` strict mode |
| `pnpm lint` | ESLint with `--max-warnings 0` (CI gate) |
| `pnpm fmt` | Prettier write |
| `pnpm test` | Vitest run with v8 coverage |
| `pnpm test:watch` | Vitest watch mode |

## 5. Tech stack at a glance

| Layer | Choice |
|-------|--------|
| Build | Vite 5 + React 18 + TypeScript 5 (strict) |
| Router | React Router v6 (data routers, `loader` / `action`) |
| Server state | TanStack Query v5 |
| Forms | React Hook Form + Zod resolver |
| HTTP | ky (fetch wrapper) |
| Realtime | socket.io-client v4 on `/ws` |
| Styling | Tailwind CSS 3.4 + CSS-variable theme tokens |
| Headless UI | Radix UI primitives (Toast, Dialog, Tooltip, Tabs, Popover, DropdownMenu) |
| Icons | Lucide React — never emoji |
| Charts | Recharts 2 |
| Money / time | `Intl.NumberFormat` + `date-fns` + `date-fns-tz` |
| Testing | Vitest + Testing Library + Playwright (E2E, future) |

See [../doc/frontend/frontend-implementation-plan.md](../doc/frontend/frontend-implementation-plan.md) §2 for the full rationale.

## 6. File layout

```
src/
  app/         route tree (React Router data routers)
  api/         per-resource REST modules + ky client + query keys helper
  schemas/     Zod mirrors of OpenAPI request / response shapes
  auth/        AuthProvider + role guards
  realtime/    socket singleton + typed event bus
  components/  ui/ (primitives), bay/, reservation/, payment/, conflict/
  lib/         theme tokens, time, money, classname helper
test/          Vitest setup
```

## 7. Caveats

This is a coursework prototype; the **mock-payment banner** is non-negotiable — every card-input view paints a sticky `MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS` warning, and the entire payment ledger is mock data from the in-process `mock_cards` table on the backend. See [../doc/proposal/proposal.md](../doc/proposal/proposal.md) §5.6.
