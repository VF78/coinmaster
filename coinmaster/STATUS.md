# CoinMaster Status

Updated: 2026-02-13 19:10 Europe/Madrid

## Current focus (Sprint 1-2 days)
1) Exchange-agnostic adapter layer (in progress)
2) Historical replay (pending)
3) Append-only trade event log (pending)
4) Postgres migration baseline (pending)
5) Hetzner deploy baseline + runbook (pending)

## This hour
- Added exchange abstraction in code: `src/exchange/*`.
- Implemented `HyperliquidAdapter` v1 market layer (`getMids`, `getCandles`, `getInstrumentMeta`, WS mids stream).
- Wired server ingest to adapter-based realtime stream.
- Verified: typecheck/build OK, API health OK, BTC ticks updating in real-time.

## Blockers / help needed
- None right now.

## Next hour target
- Start append-only trade event log foundation + integrate into order/signal lifecycle.
