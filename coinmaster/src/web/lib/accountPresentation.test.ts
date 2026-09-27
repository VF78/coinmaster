import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { HlStagegProjection } from './nautilusApi';
import { accountFigures, dashboardState, fundingLabel, protectionIsFresh, protectionIsVerified } from './accountPresentation';

function projection(account: Partial<HlStagegProjection['account']>, overrides: Partial<HlStagegProjection> = {}): HlStagegProjection {
  return {
    account: { status: 'AVAILABLE', ...account },
    entry_control: { state: 'RUNNING' },
    environment: 'mainnet-public',
    event_cursor: 0,
    events: [],
    feeds: {},
    funding_state: 'OBSERVED_MODELLED_UNPOSTED',
    gates: {},
    hashes: { candidate_sha256: '', strategy_sha256: '', execution_policy_sha256: '' },
    instance_id: 'hl-stageg-testnet',
    observed_at_ns: 1,
    orders: [],
    positions: [],
    process_state: 'READY',
    projection_state: 'READY',
    reconciliation: 'RECONCILED',
    warnings: [],
    warmup: { state: 'READY', rows: 0 },
    ...overrides,
  } as HlStagegProjection;
}

test('shows native open-account figures and unposted funding as provided', () => {
  const view = accountFigures(projection({
    native_cash: '9975.0', native_free: '9971.2', native_locked: '3.8', equity: '10004.1',
    realized_pnl_net_fees: '-1.2', unrealized_pnl: '29.1', fees: '0.8', mark_state: 'CURRENT',
  }));
  assert.deepEqual(view.map(({ value }) => value), [
    '9975.0 USDC', '9971.2 USDC', '3.8 USDC', '10004.1 USDC',
    '-1.2 USDC', '29.1 USDC', '0.8 USDC',
  ]);
  assert.equal(fundingLabel(projection({})), 'OBSERVED MODELLED UNPOSTED');
});

test('keeps missing values unknown and marks equity/PnL stale when the mark is stale', () => {
  const view = accountFigures(projection({
    native_cash: '10000', native_free: '9999', native_locked: '1', equity: null,
    realized_pnl_net_fees: '0', unrealized_pnl: null, fees: '0', mark_state: 'STALE_OR_MISSING',
  }));
  assert.deepEqual(view.map(({ value }) => value), [
    '10000 USDC', '9999 USDC', '1 USDC', 'STALE', '0 USDC', 'STALE', '0 USDC',
  ]);
});

test('retains known values in a partial account while leaving absent values unknown', () => {
  const view = accountFigures(projection({
    status: 'PARTIAL', native_cash: '10000', native_free: null, native_locked: null,
    equity: null, realized_pnl_net_fees: '0', unrealized_pnl: null, fees: '0',
  }));
  assert.deepEqual(view.map(({ value }) => value), [
    '10000 USDC', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', '0 USDC', 'UNKNOWN', '0 USDC',
  ]);
  assert.equal(fundingLabel(null), 'UNPOSTED');
});


test("captured recovered worker exposes stored exposure but never claims flat or trusts synthetic protection", () => {
  const captured = JSON.parse(readFileSync(new URL("../../../../runtime/tests/fixtures/hl_stageg_owned_tp_status.json", import.meta.url), "utf8")) as HlStagegProjection;
  const status = dashboardState(captured);
  assert.equal(status.label, "RECOVERY REQUIRED");
  assert.equal(status.exposure, "1 position · 1 order");
  assert.equal(status.canAssertFlat, false);
  assert.equal(captured.positions[0].signed_quantity, "0.53865");
  assert.equal(captured.orders[0].reduce_only, true);
  assert.deepEqual(accountFigures(captured).map(({ value }) => value), Array(7).fill("UNKNOWN"));
  assert.equal(protectionIsVerified({ ...captured, deposit_protection: { state: "ARMED", drawdown_limit_percent: 50, equity: "10000", high_water_equity: "10000", threshold_equity: "5000", daily_sample_missed: false } }), false);
});

test("healthy owned flat projection can say flat and trusts only armed protection", () => {
  const healthy = projection({
    native_cash: "10000", native_free: "10000", native_locked: "0", equity: "10000",
    realized_pnl_net_fees: "0", unrealized_pnl: "0", fees: "0", mark_state: "CURRENT",
  }, { recovery_required: false, positions: [], orders: [] });
  const status = dashboardState(healthy);
  assert.equal(status.label, "READY");
  assert.equal(status.exposure, "Flat");
  assert.equal(status.canAssertFlat, true);
  assert.equal(protectionIsVerified({ ...healthy, deposit_protection: { state: "ARMED", drawdown_limit_percent: 50, equity: "10000", high_water_equity: "10000", threshold_equity: "5000", daily_sample_missed: false } }), true);
});

test('protection values are fresh only for a current sample within the 15-second window', () => {
  const observedAt = 100_000_000_000;
  const armed = projection({}, {
    deposit_protection: {
      state: 'ARMED', drawdown_limit_percent: 50, equity: '10000', high_water_equity: '10000',
      threshold_equity: '5000', daily_sample_missed: false, observed_at_ns: observedAt,
    },
  });
  assert.equal(protectionIsFresh(armed, observedAt + 15_000_000_000), true);
  assert.equal(protectionIsFresh(armed, observedAt + 15_000_000_001), false);
  assert.equal(protectionIsFresh(armed, observedAt - 1), false);
  assert.equal(protectionIsFresh(projection({}, { deposit_protection: { ...armed.deposit_protection!, observed_at_ns: null } }), observedAt), false);
});
