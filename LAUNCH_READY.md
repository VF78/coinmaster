# LAUNCH_READY.md — Issue #25C Complete

Generated: 2026-03-02

## What Was Built (L1–L2.1)

| Layer | Commit | Description |
|-------|--------|-------------|
| L1 | `a069a87` | Consumed `MultiTfEngulfingResult` in `/api/live/order` and `/api/live/order/limit`; added `multi_tf_engulfing` gate type to audit log |
| L2 | `47e1517` | Deterministic multi-TF flag gating in `engulfingGate`: hard block on `no_engulfing_entry_signal`, pass-through failsafes for data errors |
| L2.1 | `df63a5b` + `4325c2f` | DD lock gate: one-shot latch on DD breach, blocks new entries, always allows reduce-only exits, `POST /api/live/dd-lock/reset` owner endpoint |

## Production Status (verified 2026-03-02)

| Check | Result |
|-------|--------|
| `npm run check` (TypeScript) | ✅ PASS |
| `npm run invariants:rule-engine` | ✅ 39/39 PASS |
| `npm run ops:smoke` | ✅ 3/3 PASS |
| `coinmaster.service` | ✅ active |
| `GET /api/settings/trading-rules/effective` | ✅ returns rules from DB |
| `POST /api/live/dd-lock/reset` | ✅ `{"ok":true,"ddLockActive":false}` |
| New entry blocked by DD lock | ✅ `dd_lock_active` 403 |
| Reduce-only exits NOT blocked by DD lock | ✅ passes through to next gate |

## Current Effective Rules

- Coins: BTC (50%), ETH (25%), SOL (25%)
- entryTf: 15m / exitTf: 1h
- maxLeverage: 10x / portfolioLeverageCap: 10x
- dailyDrawdown limit: 15%
- TP: 3% / SL: 2%
- manualConfirmation: **true** (all orders require `{"confirm":true}`)
- autoConfirm: false

## Known Limitations

1. **DD baseline resets daily at midnight** — `ddLock` state is in-memory only; resets on service restart. If service restarts mid-day, baseline re-anchors to current equity.
2. **`ENABLE_MULTI_TF_ENGULFING=false` by default** — multi-TF signal gate is disabled. Set `ENABLE_MULTI_TF_ENGULFING=true` in `/etc/coinmaster/coinmaster.env` to enable.
3. **`manualConfirmation=true`** — every order requires explicit `{"confirm":true}` in body. Set `autoConfirm=true` in Trading Rules UI to remove this gate.
4. **Current DD is >50%** — `ddLock` will activate on first order attempt. Reset with `POST /api/live/dd-lock/reset` at start of new trading day.

## Steps to Start Live Trading

```bash
# 1. At start of new trading day — reset DD baseline and lock
curl -sS -X POST -H "authorization: Bearer $OWNER_AUTH_TOKEN" \
  http://127.0.0.1:8787/api/live/dd-lock/reset

# 2. (Optional) Enable multi-TF signal gate
# Edit /etc/coinmaster/coinmaster.env:
# ENABLE_MULTI_TF_ENGULFING=true
# Then: systemctl restart coinmaster.service

# 3. (Optional) Disable manual confirmation
# In Trading Rules UI: set autoConfirm=true

# 4. Place order (with confirm if manualConfirmation=true)
curl -sS -X POST -H "authorization: Bearer $OWNER_AUTH_TOKEN" \
  -H "content-type: application/json" \
  http://127.0.0.1:8787/api/live/order \
  -d '{"symbol":"BTC","side":"buy","price":XXXXX,"size":0.001,"confirm":true}'

# 5. Check status at any time
curl -sS -H "authorization: Bearer $OWNER_AUTH_TOKEN" \
  http://127.0.0.1:8787/api/live/risk-check
```
