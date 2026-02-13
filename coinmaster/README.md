# Paper Trading Control Panel

Lightweight paper-trading control panel with a TypeScript backend/API and a modern responsive React frontend.

## What is included
- Backend API (Express + lowdb) for dashboard/history/bias/simulation endpoints.
- Mobile-first responsive UI (phone/tablet/desktop).
- Reusable UI component set: `Card`, `Stat`, `Badge`, `Button`, `DataTable` (table on desktop, cards on mobile).
- Shared DTO/types module (`src/shared/dto.ts`) used by both backend/core and web client.

## Stack
- TypeScript
- React + Vite
- Express
- lowdb

## Run locally
```bash
cd /Users/vf/.openclaw/workspace/coinmaster
npm install
npm run seed
npm run dev
```

- Web: http://localhost:5173
- API: http://localhost:8787

## Commands
```bash
npm run dev      # start API + web
npm run dev:api  # API only (watch mode)
npm run dev:web  # web only
npm run seed     # reset + populate demo data
npm run check    # TypeScript typecheck
npm run build    # build web bundle
npm run start    # run API only
```

## API quick map (unchanged)
- `GET /api/dashboard`
- `GET /api/history`
- `POST /api/bias` body `{ "symbol": "BTC", "bias": "long|short|off" }`
- `POST /api/simulate/tick` body `{ "symbol": "BTC", "price": 43000 }`

## Project structure highlights
- `src/shared/dto.ts` → transport/domain DTOs shared across clients.
- `src/core/*` → backend domain logic and simulation.
- `src/server/index.ts` → API routes.
- `src/web/*` → web UI and reusable presentational components.
- `docs/UX_NOTES.md` → responsive breakpoints and component behavior.
- `docs/ARCHITECTURE.md` → deployment/evolution architecture.
- `docs/SECURITY_REQUIREMENTS.md` → security baseline for exchange-API trading system.
- `docs/HYPERLIQUID_API_COMMANDS.md` → v1 command scope for Hyperliquid integration.
- `docs/EXCHANGE_ADAPTER_CONTRACT.md` → exchange-agnostic adapter contract (Hyperliquid/Bybit/Binance path).

## Native port path (Expo)
A concrete path to add iOS/Android without rewriting domain contracts:

1. **Create app:** `npx create-expo-app apps/mobile`.
2. **Reuse DTOs:** import from `src/shared/dto.ts` (or move to `packages/shared` if turning into full monorepo package).
3. **Reuse API contract:** implement a small React Native API client mirroring `src/web/lib/api.ts` endpoint methods.
4. **Reuse UI semantics, not CSS:** keep the same component model (`Card`, `Stat`, `Badge`, `Button`, `DataTable/List`) in RN primitives.
5. **Keep domain backend-agnostic:** avoid DOM/browser assumptions in shared/domain code; keep platform specifics in web/mobile layers.
6. **Incremental rollout:** ship mobile read-only dashboard first, then bias controls, then history/audit.

This keeps backend API intact while minimizing duplicated data-model logic across web and mobile.
