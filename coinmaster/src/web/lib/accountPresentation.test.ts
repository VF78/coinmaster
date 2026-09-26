import assert from 'node:assert/strict';
import test from 'node:test';
import type { HlStagegProjection } from './nautilusApi';
import { accountFigures, fundingLabel } from './accountPresentation';

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
