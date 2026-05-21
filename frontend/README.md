# ParkReserve Frontend

React + Vite single-page application for both sides of ParkReserve:

- driver app under `/app`
- admin console under `/admin`

The frontend depends on the backend in [../backend](../backend). All business rules, auth, reservation state, and realtime events come from that service.

## Prerequisites

- Node.js `>= 20.10`
- `pnpm` `9.x` via Corepack
- a running backend on `http://localhost:8000`

Minimal backend setup:

```bash
cd ../backend
make install
cp .env.example .env
make up
make migrate
make seed
make dev
```

## Quick Start

From `frontend/`:

```bash
corepack enable
pnpm install
cp .env.example .env
pnpm dev
```

Open `http://localhost:5173`.

By default the browser talks to Vite on `:5173`, and Vite proxies:

- `/api`
- `/healthz`
- `/readyz`
- `/socket.io`

to the backend origin. If you set `VITE_BACKEND_ORIGIN`, the app and dev proxy both use that origin instead of the default `http://127.0.0.1:8000`.

## What The App Currently Includes

Public routes:

- `/`
- `/login`
- `/register`
- `/help`

Driver routes:

- `/app`
- `/app/plates`
- `/app/reservations/new`
- `/app/reservations/:id`
- `/app/payments`

Admin routes:

- `/admin`
- `/admin/grid`
- `/admin/bays/:code`
- `/admin/conflicts`

Role gating is handled in the client from the authenticated user profile returned by the backend.

## Local Demo Accounts

After running `make seed` in the backend, you can sign in with:

| Role | Email | Password |
|------|-------|----------|
| driver | `nyx@parkreserve.local` | `nyxParkreserve29!` |
| driver | `riya@parkreserve.local` | `riyaParkreserve29!` |
| driver | `yuan@parkreserve.local` | `yuanParkreserve29!` |
| driver | `cheng@parkreserve.local` | `chengParkreserve29!` |
| admin | `admin@parkreserve.local` | `adminParkreserve29!` |

## Demo Flow

Driver flow:

1. Sign in as a seeded user or register a new account.
2. Add at least one plate at `/app/plates`.
3. Book an available bay at `/app/reservations/new`.
4. Inspect the reservation cockpit at `/app/reservations/:id`.
5. Review mock ledger entries at `/app/payments`.

To simulate hardware activity while the frontend is open:

```bash
cd ../backend
.venv/bin/python scripts/mock_pi_publisher.py
```

That mock publisher pushes MQTT state and event traffic through the backend, which then updates the frontend.

## Realtime Behavior

- the public landing page polls bay status every 5 seconds
- authenticated driver/admin screens use Socket.IO on namespace `/ws`
- the frontend listens for bay, reservation, plate, conflict, and payment events and refreshes React Query caches from those updates

## Scripts

| Script | Purpose |
|--------|---------|
| `pnpm dev` | start the Vite dev server |
| `pnpm build` | type-check and build production assets into `dist/` |
| `pnpm preview` | preview the production build locally on port `4173` |
| `pnpm typecheck` | run `tsc --noEmit` |
| `pnpm lint` | run ESLint |
| `pnpm fmt` | format files with Prettier |
| `pnpm fmt:check` | check formatting without writing |
| `pnpm test` | run Vitest with coverage |
| `pnpm test:watch` | run Vitest in watch mode |
| `pnpm e2e:install` | install Playwright Chromium dependencies |
| `pnpm e2e` | run Playwright end-to-end tests |

## Testing Notes

- unit/component tests use Vitest + Testing Library
- E2E tests use Playwright and start `pnpm dev` automatically
- E2E tests still require a real backend to be running separately
- frontend coverage thresholds are enforced in [vite.config.ts](./vite.config.ts)

## Stack

| Layer | Choice |
|-------|--------|
| Build | Vite 5 |
| UI | React 18 + TypeScript |
| Routing | React Router |
| Server state | TanStack Query |
| Forms | React Hook Form + Zod |
| HTTP | `ky` |
| Realtime | `socket.io-client` |
| Styling | Tailwind CSS |
| UI primitives | Radix UI |
| Charts | Recharts |
| Tests | Vitest, Testing Library, Playwright |

## Project Layout

```text
src/
  app/          route components
  api/          backend API clients and query keys
  auth/         auth provider and role guards
  components/   UI, bay, reservation, payment, and conflict components
  lib/          shared helpers and runtime config
  realtime/     Socket.IO client and realtime bus
  schemas/      Zod request/response schemas
test/           Vitest setup
e2e/            Playwright tests
```

## Mock Payment Notice

The payment flow is intentionally fake. The app shows a mock-payment warning, and all card checks resolve against backend seed data rather than a real payment gateway.
