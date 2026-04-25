import type { EvidenceBundle, SignalCandidate, TradingCoinAllocation } from '../src/shared/dto.js';
import { buildRadarContextPolicyBook, evaluateRadarContextPolicyEntry, readActiveRadarContextPolicy } from '../src/server/radarContextPolicy.js';

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

const nowIso = '2026-04-25T12:00:00.000Z';
const monitoredCoins: TradingCoinAllocation[] = [
  { symbol: 'BTC', enabled: true, pct: 50 },
  { symbol: 'ETH', enabled: true, pct: 50 },
];

function makeBundle(input: Partial<EvidenceBundle> & Pick<EvidenceBundle, 'id'>): EvidenceBundle {
  return {
    id: input.id,
    clusterKey: input.clusterKey ?? input.id,
    title: input.title ?? 'SEC filing update',
    excerpt: input.excerpt ?? 'Fresh catalyst',
    assetTags: input.assetTags ?? ['BTC'],
    topicTags: input.topicTags ?? ['listing'],
    sources: input.sources ?? ['sec'],
    sourceClasses: input.sourceClasses ?? ['official'],
    sourceLayers: input.sourceLayers ?? ['primary'],
    observationIds: input.observationIds ?? ['obs-1'],
    externalIds: input.externalIds ?? ['ext-1'],
    exactMatchCount: input.exactMatchCount ?? 0,
    canonicalUrlMatchCount: input.canonicalUrlMatchCount ?? 0,
    externalIdMatchCount: input.externalIdMatchCount ?? 0,
    fuzzyMatchCount: input.fuzzyMatchCount ?? 0,
    duplicateSuppressedCount: input.duplicateSuppressedCount ?? 0,
    firstObservedAt: input.firstObservedAt ?? '2026-04-25T11:30:00.000Z',
    lastObservedAt: input.lastObservedAt ?? '2026-04-25T11:50:00.000Z',
    status: input.status ?? 'active',
    enrichment: input.enrichment ?? {
      sentimentScore: 0.8,
      sentimentConfidence: 0.8,
      sentimentAdapter: 'test',
      sentimentLabel: 'bullish',
      usedFallback: true,
      computedAt: nowIso,
    },
    createdAt: input.createdAt ?? nowIso,
    updatedAt: input.updatedAt ?? nowIso,
  };
}

function makeCandidate(input: Partial<SignalCandidate> & Pick<SignalCandidate, 'id' | 'evidenceBundleId' | 'symbol' | 'side'>): SignalCandidate {
  return {
    id: input.id,
    evidenceBundleId: input.evidenceBundleId,
    symbol: input.symbol,
    side: input.side,
    state: input.state ?? 'actionable',
    stateReason: input.stateReason ?? 'test',
    transitions: input.transitions ?? [{ from: 'new', to: 'actionable', reason: 'test', at: nowIso }],
    score: input.score ?? {
      composite: 82,
      factors: {
        relevance: 1,
        novelty: 0.7,
        sourceReliability: 0.9,
        eventSeverity: 0.6,
        timeDecay: 0.9,
        marketConfirmation: 0.8,
        executionability: 1,
      },
      weights: {
        relevance: 0.2,
        novelty: 0.1,
        sourceReliability: 0.15,
        eventSeverity: 0.15,
        timeDecay: 0.15,
        marketConfirmation: 0.1,
        executionability: 0.15,
      },
    },
    expiresAt: input.expiresAt ?? '2026-04-25T18:00:00.000Z',
    createdAt: input.createdAt ?? nowIso,
    updatedAt: input.updatedAt ?? nowIso,
  };
}

console.log('\n=== Radar Context Policy Invariants ===\n');

console.log('Test 1: actionable bullish candidate creates long-only active policy');
{
  const policies = buildRadarContextPolicyBook({
    bundles: [makeBundle({ id: 'bundle-btc', assetTags: ['BTC'] })],
    candidates: [makeCandidate({ id: 'candidate-btc', evidenceBundleId: 'bundle-btc', symbol: 'BTC', side: 'buy' })],
    monitoredCoins,
    nowIso,
  });
  const active = readActiveRadarContextPolicy({ policies, symbol: 'BTC', nowIso });
  assert(active.policy?.directionMode === 'long_only', 'BTC policy is long_only');
  assert((active.policy?.riskMultiplier ?? 0) > 0, 'BTC policy has positive risk multiplier');
}

console.log('\nTest 2: missing candidate yields missing_required_evidence block');
{
  const policies = buildRadarContextPolicyBook({ bundles: [], candidates: [], monitoredCoins, nowIso });
  const gate = evaluateRadarContextPolicyEntry({ policies, symbol: 'ETH', side: 'buy', nowIso });
  assert(gate.allowed === false, 'ETH entry is blocked');
  assert(gate.reasonCode === 'missing_required_evidence', 'missing evidence reason is explicit');
}

console.log('\nTest 3: expired candidate yields ttl_expired');
{
  const policies = buildRadarContextPolicyBook({
    bundles: [makeBundle({ id: 'bundle-old', assetTags: ['BTC'] })],
    candidates: [makeCandidate({ id: 'candidate-old', evidenceBundleId: 'bundle-old', symbol: 'BTC', side: 'buy', expiresAt: '2026-04-25T11:00:00.000Z' })],
    monitoredCoins,
    nowIso,
  });
  const gate = evaluateRadarContextPolicyEntry({ policies, symbol: 'BTC', side: 'buy', nowIso });
  assert(gate.allowed === false, 'expired policy blocks entry');
  assert(gate.reasonCode === 'ttl_expired', 'ttl_expired reason is explicit');
}

console.log('\nTest 4: side mismatch yields direction_blocked');
{
  const policies = buildRadarContextPolicyBook({
    bundles: [makeBundle({ id: 'bundle-short', assetTags: ['BTC'], enrichment: { sentimentScore: -0.8, sentimentConfidence: 0.8, sentimentAdapter: 'test', sentimentLabel: 'bearish', usedFallback: true, computedAt: nowIso } })],
    candidates: [makeCandidate({ id: 'candidate-short', evidenceBundleId: 'bundle-short', symbol: 'BTC', side: 'sell' })],
    monitoredCoins,
    nowIso,
  });
  const gate = evaluateRadarContextPolicyEntry({ policies, symbol: 'BTC', side: 'buy', nowIso });
  assert(gate.allowed === false, 'counter-direction entry is blocked');
  assert(gate.reasonCode === 'direction_blocked', 'direction_blocked reason is explicit');
}

console.log('\nTest 5: severe macro evidence activates event lockout');
{
  const policies = buildRadarContextPolicyBook({
    bundles: [makeBundle({ id: 'bundle-lockout', assetTags: ['BTC'], topicTags: ['macro-shock'], sourceClasses: ['macro'] })],
    candidates: [makeCandidate({ id: 'candidate-lockout', evidenceBundleId: 'bundle-lockout', symbol: 'BTC', side: 'buy', score: {
      composite: 88,
      factors: { relevance: 1, novelty: 0.8, sourceReliability: 0.8, eventSeverity: 0.95, timeDecay: 0.9, marketConfirmation: 0.7, executionability: 1 },
      weights: { relevance: 0.2, novelty: 0.1, sourceReliability: 0.15, eventSeverity: 0.15, timeDecay: 0.15, marketConfirmation: 0.1, executionability: 0.15 },
    } })],
    monitoredCoins,
    nowIso,
    eventLockoutMinutes: 90,
  });
  const gate = evaluateRadarContextPolicyEntry({ policies, symbol: 'BTC', side: 'buy', nowIso });
  assert(gate.allowed === false, 'event lockout blocks entry');
  assert(gate.reasonCode === 'event_lockout', 'event_lockout reason is explicit');
}

console.log('\nTest 6: low score blocks via risk multiplier zero');
{
  const policies = buildRadarContextPolicyBook({
    bundles: [makeBundle({ id: 'bundle-low', assetTags: ['BTC'] })],
    candidates: [makeCandidate({ id: 'candidate-low', evidenceBundleId: 'bundle-low', symbol: 'BTC', side: 'buy', state: 'validated', score: {
      composite: 55,
      factors: { relevance: 1, novelty: 0.5, sourceReliability: 0.5, eventSeverity: 0.3, timeDecay: 0.5, marketConfirmation: 0.4, executionability: 1 },
      weights: { relevance: 0.2, novelty: 0.1, sourceReliability: 0.15, eventSeverity: 0.15, timeDecay: 0.15, marketConfirmation: 0.1, executionability: 0.15 },
    } })],
    monitoredCoins,
    nowIso,
  });
  const gate = evaluateRadarContextPolicyEntry({ policies, symbol: 'BTC', side: 'buy', nowIso });
  assert(gate.allowed === false, 'low-conviction policy blocks entry');
  assert(gate.reasonCode === 'risk_multiplier_blocked' || gate.reasonCode === 'direction_blocked', 'zero-risk block is explicit');
}

console.log(`\n${passed} passed, ${failed} failed\n`);

if (failed > 0) {
  process.exit(1);
}
