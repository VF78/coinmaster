# Paper Trading Control Panel (MVP)

Production-minded, lightweight scaffold for a paper-trading SaaS.

## Features implemented
- Dashboard with active paper positions, SL/TP, real-time PnL (from latest simulated tick).
- History/Statistics page with closed trades, win-rate, average/realized PnL, and event audit log.
- Manual bias commands ingestion (`BTC long`, `BTC short`, `BTC off`) with persistent logging.
- Simulation engine that opens/closes virtual trades using a **backtest_v1 adapter seam**.
- Domain/UI separation for future mobile reuse.
- Local persistence via JSON DB (`data/db.json`).

## Stack
- TypeScript
- React + Vite (web UI)
- Express (API)
- lowdb (JSON persistence)

## Run locally
```bash
cd /Users/vf/.openclaw/workspace/paper-trading-control-panel
npm install
npm run seed
npm run dev
```

- Web: http://localhost:5173
- API: http://localhost:8787

## Useful commands
```bash
npm run seed      # reset + populate demo data
npm run check     # TypeScript typecheck
npm run build     # build web bundle
npm run start     # run API only
```

## API quick map
- `GET /api/dashboard`
- `GET /api/history`
- `POST /api/bias` body `{ "symbol": "BTC", "bias": "long|short|off" }`
- `POST /api/simulate/tick` body `{ "symbol": "BTC", "price": 43000 }`

## Notes
- Adapter in `src/core/strategyAdapter.ts` is intentionally isolated to swap in direct `backtest_v1` Python signals later.
- See `docs/ARCHITECTURE.md` for SaaS evolution boundaries.
