# Smoke Test Plan (After #7 Complete)

## E2E Order Lifecycle Test

**Prerequisites:**
- All 3 issues (#12, #11, #7) deployed to production
- Server running on localhost:8787
- Hyperliquid account connected + credentials in .env
- Test capital: 30 USDC (per LIVE_MAX_NOTIONAL_USDC)

## Test Sequence

### 1. Risk Check (baseline)
```bash
GET /api/live/risk-check
Expected: canTrade=true, dailyDDPct=0, portfolioLeverage=0, blocks=[]
```

### 2. Place Order (with confirmation)
```bash
POST /api/live/order
{
  "symbol": "BTC",
  "side": "buy",
  "price": 50000,
  "size": 0.0001,
  "leverage": 5,
  "clientOrderId": "smoke-test-1",
  "confirm": true
}
Expected: ok=true OR errorCode with classified reason
```

### 3. Verify Position Created
```bash
GET /api/live/status
Expected: open positions include smoke-test order
```

### 4. Idempotency Replay
```bash
POST /api/live/order (same clientOrderId, same params)
Expected: idempotent=true, cached response
```

### 5. Partial Close (Reduce-Only)
```bash
PUT /api/live/order/{orderId}/reduce
{
  "newSize": 0.00005
}
Expected: ok=true, position reduced
```

### 6. Cancel Remaining
```bash
DELETE /api/live/order/{orderId}?confirm=true
Expected: ok=true, order closed
```

### 7. Risk Check (post-trades)
```bash
GET /api/live/risk-check
Expected: canTrade=true, dailyDDPct should reflect P&L
```

## Pass Criteria
✅ All 7 HTTP requests return 200/409 (no 5xx errors)
✅ Manual confirmation gate works (409 without confirm)
✅ Idempotency replay detected (idempotent:true in response)
✅ All operations logged to audit trail
✅ Risk check endpoints respond correctly

## Automated Check
Run after each task:
```bash
npm run test:smoke  (if available)
# or manually curl each endpoint above
```

---
**Status:** READY (starts after #7 complete)
**Duration:** ~15-20 minutes manual + verification
