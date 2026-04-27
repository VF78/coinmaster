import type { RadarContextPolicy, TradingCoinAllocation } from '../src/shared/dto.js';
import { buildFreqtradeRadarPolicySnapshot } from '../src/server/freqtradeRadarPolicy.js';

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string): void {
  if (condition) {
    passed++;
    console.log(`  ✓ ${label}`);
  } else {
    failed++;
    console.error(`  ✗ FAIL: ${label}`);
  }
}

const nowIso = '2026-04-27T12:00:00.000Z';
const monitoredCoins: TradingCoinAllocation[] = [
  { symbol: 'BTC', enabled: true, pct: 34 },
  { symbol: 'ETH', enabled: true, pct: 33 },
  { symbol: 'HYPE', enabled: true, pct: 33 },
];

function makePolicy(input: Partial<RadarContextPolicy> & Pick<RadarContextPolicy, 'id' | 'symbol'>): RadarContextPolicy {
  return {
    id: input.id,
    symbol: input.symbol,
    assetScope: input.assetScope ?? 'symbol',
    assetClass: input.assetClass ?? 'crypto',
    directionMode: input.directionMode ?? 'both',
    riskMultiplier: input.riskMultiplier ?? 1,
    lockNewEntries: input.lockNewEntries ?? false,
    eventLockoutUntil: input.eventLockoutUntil,
    narrativeRegime: input.narrativeRegime ?? 'test_context',
    priorityScore: input.priorityScore ?? 80,
    validUntil: input.validUntil,
    assetSpecificOverrides: input.assetSpecificOverrides ?? [],
    reasonCodes: input.reasonCodes ?? [],
    evidenceIds: input.evidenceIds ?? ['evidence-1'],
    signalCandidateId: Object.prototype.hasOwnProperty.call(input, 'signalCandidateId') ? input.signalCandidateId : 'candidate-1',
    createdAt: input.createdAt ?? nowIso,
    updatedAt: input.updatedAt ?? nowIso,
  };
}

console.log('\n=== Freqtrade Radar Policy Export Invariants ===\n');

console.log('Test 1: missing evidence policies are neutral and omitted');
{
  const snapshot = buildFreqtradeRadarPolicySnapshot({
    policies: [makePolicy({ id: 'missing-btc', symbol: 'BTC', directionMode: 'blocked', riskMultiplier: 0, lockNewEntries: true, reasonCodes: ['missing_required_evidence'], evidenceIds: [], signalCandidateId: undefined })],
    monitoredCoins,
    nowIso,
  });
  assert(snapshot.global.mode === 'both', 'global policy remains neutral');
  assert(snapshot.global.risk_multiplier === 1, 'global risk remains unchanged');
  assert(Object.keys(snapshot.pairs).length === 0, 'missing-evidence pair is not exported as a block');
  assert(snapshot.diagnostics.ignored_neutral_policies === 1, 'neutral ignored counter increments');
}

console.log('\nTest 2: active directional policy maps to Freqtrade pair scope');
{
  const snapshot = buildFreqtradeRadarPolicySnapshot({
    policies: [makePolicy({ id: 'eth-long', symbol: 'ETH', directionMode: 'long_only', riskMultiplier: 0.75, reasonCodes: [], narrativeRegime: 'bullish_context' })],
    monitoredCoins,
    nowIso,
  });
  const eth = snapshot.pairs['ETH/USDC:USDC'];
  assert(eth?.mode === 'long_only', 'ETH exports long_only');
  assert(eth?.risk_multiplier === 0.75, 'ETH risk multiplier is preserved');
  assert(eth?.lock_new_entries === false, 'ETH is not hard blocked');
}

console.log('\nTest 3: blocked/event policy maps to pair off and never increases risk');
{
  const snapshot = buildFreqtradeRadarPolicySnapshot({
    policies: [makePolicy({ id: 'hype-off', symbol: 'HYPE', directionMode: 'both', riskMultiplier: 1.5, lockNewEntries: true, reasonCodes: ['event_lockout'], narrativeRegime: 'event_lockout' })],
    monitoredCoins,
    nowIso,
  });
  const hype = snapshot.pairs['HYPE/USDC:USDC'];
  assert(hype?.mode === 'off', 'HYPE exports off when lockNewEntries is true');
  assert(hype?.risk_multiplier === 0, 'off mode exports zero risk');
  assert(hype?.lock_new_entries === true, 'pair hard block is explicit');
}

console.log('\nTest 4: expired and unmonitored policies are ignored');
{
  const snapshot = buildFreqtradeRadarPolicySnapshot({
    policies: [
      makePolicy({ id: 'old-btc', symbol: 'BTC', validUntil: '2026-04-27T11:59:00.000Z' }),
      makePolicy({ id: 'sol-policy', symbol: 'SOL', directionMode: 'short_only' }),
    ],
    monitoredCoins,
    nowIso,
  });
  assert(Object.keys(snapshot.pairs).length === 0, 'expired/unmonitored policies do not affect Freqtrade');
  assert(snapshot.diagnostics.ignored_expired_policies === 1, 'expired counter increments');
  assert(snapshot.diagnostics.ignored_unmonitored_policies === 1, 'unmonitored counter increments');
}

console.log('\nTest 5: snapshot has short TTL and active diagnostics');
{
  const snapshot = buildFreqtradeRadarPolicySnapshot({
    policies: [makePolicy({ id: 'btc-short', symbol: 'BTC', directionMode: 'short_only', riskMultiplier: 0.5 })],
    monitoredCoins,
    nowIso,
    ttlMs: 120_000,
  });
  assert(snapshot.schema_version === 1, 'schema version is fixed');
  assert(snapshot.valid_until === '2026-04-27T12:02:00.000Z', 'valid_until follows TTL');
  assert(snapshot.diagnostics.active_pair_overrides === 1, 'active override counter increments');
}

console.log(`\n${passed} passed, ${failed} failed\n`);

if (failed > 0) {
  process.exit(1);
}
