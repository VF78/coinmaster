import assert from 'node:assert/strict';
import testCase from 'node:test';
import type { HlStagegProjection } from './nautilusApi';
import { positionPresentation } from './traderPresentation';

function projection(overrides: Partial<HlStagegProjection> = {}): HlStagegProjection {
  return {
    account: { status: 'UNAVAILABLE' },
    entry_control: { state: 'RUNNING' },
    environment: 'mainnet-public',
    event_cursor: 0,
    events: [],
    feeds: {},
    funding_state: 'OBSERVED_MODELLED_UNPOSTED',
    gates: {},
    hashes: { candidate_sha256: '', strategy_sha256: '', execution_policy_sha256: '' },
    instance_id: 'hl-stageg-testnet',
    observed_at_ns: 1_000_000,
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

testCase('flat appears only after a ready, recovered empty positions-and-orders projection', () => {
  const flat = projection();
  assert.deepEqual(positionPresentation(flat, 'BTC-USD-PERP.HYPERLIQUID'), {
    state: 'FLAT', side: null, quantity: '0',
  });
  const recovery = projection({ recovery_required: true });
  assert.equal(positionPresentation(recovery, 'BTC-USD-PERP.HYPERLIQUID').state, 'UNKNOWN');
  const stored = projection({
    recovery_required: true,
    positions: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', signed_quantity: '0.53645', provenance: 'SANDBOX' }],
  });
  assert.deepEqual(positionPresentation(stored, 'BTC-USD-PERP.HYPERLIQUID'), {
    state: 'OPEN', side: 'LONG', quantity: '0.53645',
  });
});
