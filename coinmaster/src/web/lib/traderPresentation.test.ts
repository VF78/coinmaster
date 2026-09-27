import assert from 'node:assert/strict';
import testCase from 'node:test';
import type { HlStagegProjection } from './nautilusApi';
import { appendSessionMarkSample, markSparklinePath, positionPresentation } from './traderPresentation';

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

testCase('mark history accepts only fresh ready feed samples and resets on stale data', () => {
  const instrumentId = 'BTC-USD-PERP.HYPERLIQUID';
  const fresh = projection({
    feeds: { [instrumentId]: { state: 'READY', mark: '64250.5', mark_age_ns: 2_000_000_000 } },
    observed_at_ns: 2_000_000,
  });
  const one = appendSessionMarkSample([], fresh, instrumentId);
  assert.deepEqual(one, [{ observedAtNs: 2_000_000, mark: 64250.5 }]);
  const stale = projection({
    feeds: { [instrumentId]: { state: 'STALE', mark: '64250.5', mark_age_ns: 20_000_000_000 } },
    observed_at_ns: 3_000_000,
  });
  assert.deepEqual(appendSessionMarkSample(one, stale, instrumentId), []);
  assert.equal(markSparklinePath(one), '');
  assert.match(markSparklinePath([...one, { observedAtNs: 4_000_000, mark: 64255 }]), /^M0\.0,/);
});

testCase('missing mark and missing freshness remain unknown and are not plotted', () => {
  const instrumentId = 'SOL-USD-PERP.HYPERLIQUID';
  const projectionWithMissing = projection({
    feeds: { [instrumentId]: { state: 'READY', mark: null, mark_age_ns: null } },
  });
  assert.deepEqual(appendSessionMarkSample([], projectionWithMissing, instrumentId), []);
});
