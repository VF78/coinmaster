import type { AlphaRadarObservation, EvidenceBundle } from '../src/shared/dto.js';
import { ingestObservationIntoEvidence, normalizeObservationForEvidence, syncSignalCandidatesFromEvidence } from '../src/server/alphaRadarEvidence.js';
import { extractRssItemsWithFeedparser } from '../src/server/alphaRadarFeedParser.js';
import { scoreSignalCandidate } from '../src/server/radarScoringFactors.js';
import { createSignalCandidate, transitionSignalCandidate } from '../src/server/radarSignalCandidate.js';

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string): void {
  if (condition) {
    passed += 1;
    console.log(`  ✓ ${label}`);
  } else {
    failed += 1;
    console.error(`  ✗ FAIL: ${label}`);
  }
}

const nowIso = '2026-04-25T20:00:00.000Z';

function baseObservation(partial: Partial<AlphaRadarObservation>): AlphaRadarObservation {
  return {
    id: partial.id ?? 'obs-1',
    kind: 'external',
    source: partial.source ?? 'coindesk_rss',
    sourceType: 'rss',
    sourceLayer: 'primary',
    sourceClass: 'newswire',
    sourceWeight: 1,
    title: partial.title ?? 'SEC approves major Bitcoin product',
    excerpt: partial.excerpt ?? 'Bitcoin ETF approval drives crypto sentiment higher.',
    assetTags: partial.assetTags ?? ['BTC'],
    topicTags: partial.topicTags ?? ['etf', 'regulation'],
    rank: 0.8,
    observedAt: partial.observedAt ?? nowIso,
    provenance: partial.provenance ?? {
      url: 'https://example.com/news?id=1&utm_source=test',
      publishedAt: nowIso,
      fetchedAt: nowIso,
      externalId: 'item-1',
      parser: 'feedparser',
    },
    metadata: partial.metadata,
    createdAt: partial.createdAt ?? nowIso,
  };
}

console.log('\n=== Radar Evidence Invariants ===\n');

console.log('Test 1: observation normalization adds canonical URL and payload hash');
{
  const normalized = normalizeObservationForEvidence(baseObservation({}), nowIso);
  assert(normalized.provenance?.canonicalUrl === 'https://example.com/news?id=1', 'canonical URL strips tracking params');
  assert(typeof normalized.provenance?.payloadHash === 'string' && normalized.provenance.payloadHash.length > 10, 'payload hash created');
}

console.log('\nTest 2: exact-hash duplicates merge into one evidence bundle');
{
  const bundles: EvidenceBundle[] = [];
  const first = await ingestObservationIntoEvidence({
    observation: baseObservation({ id: 'obs-a' }),
    bundles,
    nowIso,
    nextBundleId: () => 'bundle-a',
  });
  const second = await ingestObservationIntoEvidence({
    observation: baseObservation({ id: 'obs-b', source: 'cointelegraph_rss' }),
    bundles,
    nowIso,
    nextBundleId: () => 'bundle-b',
  });
  assert(first.bundle.id === 'bundle-a', 'first observation creates bundle');
  assert(second.bundle.id === 'bundle-a', 'duplicate observation reuses existing bundle');
  assert(bundles.length === 1, 'only one bundle exists after merge');
}

console.log('\nTest 3: fuzzy title match merges related headlines');
{
  const bundles: EvidenceBundle[] = [];
  await ingestObservationIntoEvidence({
    observation: baseObservation({ id: 'obs-c', title: 'BlackRock ETF approval lifts Bitcoin', excerpt: 'ETF approval lifts BTC.' }),
    bundles,
    nowIso,
    nextBundleId: () => 'bundle-c',
  });
  const second = await ingestObservationIntoEvidence({
    observation: baseObservation({
      id: 'obs-d',
      title: 'Bitcoin lifts as BlackRock ETF gets approval',
      excerpt: 'Market reacts to ETF approval for BTC.',
      provenance: { url: 'https://example.com/other', publishedAt: nowIso, fetchedAt: nowIso, parser: 'feedparser' },
    }),
    bundles,
    nowIso,
    nextBundleId: () => 'bundle-d',
  });
  assert(second.bundle.id === 'bundle-c', 'fuzzy match reused original bundle');
}

console.log('\nTest 4: candidate scoring produces deterministic explicit factors');
{
  const bundle: EvidenceBundle = {
    id: 'bundle-score',
    clusterKey: 'btc-approval',
    payloadHash: 'abc',
    canonicalUrl: 'https://example.com/x',
    title: 'SEC approves Bitcoin ETF',
    excerpt: 'Bitcoin ETF approval reaches market',
    assetTags: ['BTC'],
    topicTags: ['etf', 'regulation'],
    sources: ['coindesk_rss', 'cointelegraph_rss'],
    sourceClasses: ['newswire', 'official'],
    sourceLayers: ['primary'],
    observationIds: ['obs-1', 'obs-2'],
    externalIds: ['item-1'],
    exactMatchCount: 1,
    canonicalUrlMatchCount: 0,
    externalIdMatchCount: 0,
    fuzzyMatchCount: 0,
    duplicateSuppressedCount: 0,
    firstObservedAt: nowIso,
    lastObservedAt: nowIso,
    status: 'active',
    createdAt: nowIso,
    updatedAt: nowIso,
  };
  const score = scoreSignalCandidate({
    bundle,
    symbol: 'BTC',
    monitoredSymbols: ['BTC', 'ETH'],
    symbolMonitored: true,
    sizeable: true,
    nowMs: Date.parse(nowIso),
  });
  assert(score.composite > 0, 'composite score computed');
  assert(score.factors.relevance === 1, 'relevance factor is explicit and full for monitored symbol');
}

console.log('\nTest 5: state machine rejects illegal transitions');
{
  const candidate = createSignalCandidate({
    id: 'candidate-a',
    evidenceBundleId: 'bundle-a',
    symbol: 'BTC',
    side: 'buy',
    nowIso,
  });
  const illegal = transitionSignalCandidate(candidate, { to: 'executed', reason: 'skip', at: nowIso });
  assert(illegal.ok === false && illegal.error === 'illegal_transition', 'illegal jump to executed is blocked');
}

console.log('\nTest 6: feedparser primary parser preserves provenance metadata');
{
  const rss = `<?xml version="1.0"?><rss version="2.0"><channel><title>Test Feed</title><item><title>SEC approves Bitcoin ETF</title><description>BTC market reacts.</description><link>https://Example.com/news?utm_source=x&amp;id=1</link><guid>guid-1</guid><pubDate>Sat, 25 Apr 2026 20:00:00 GMT</pubDate></item></channel></rss>`;
  const items = await extractRssItemsWithFeedparser(rss);
  assert(items.length === 1, 'feedparser extracted one RSS item');
  assert(items[0]?.metadata?.parser === 'feedparser', 'primary parser reports feedparser metadata');
  assert(items[0]?.canonicalUrl === 'https://example.com/news?id=1', 'parser canonicalizes URL for provenance');
  assert(items[0]?.externalId === 'guid-1', 'parser keeps source external id/guid');
}

console.log('\nTest 7: active evidence generates durable candidates');
{
  const bundles: EvidenceBundle[] = [{
    id: 'bundle-live',
    clusterKey: 'btc-live',
    payloadHash: 'live',
    canonicalUrl: 'https://example.com/live',
    title: 'Bitcoin breakout after ETF approval',
    excerpt: 'BTC trades higher after approval headline.',
    assetTags: ['BTC'],
    topicTags: ['etf'],
    sources: ['coindesk_rss'],
    sourceClasses: ['newswire'],
    sourceLayers: ['primary'],
    observationIds: ['obs-live'],
    externalIds: ['live-1'],
    exactMatchCount: 0,
    canonicalUrlMatchCount: 0,
    externalIdMatchCount: 0,
    fuzzyMatchCount: 0,
    duplicateSuppressedCount: 0,
    firstObservedAt: nowIso,
    lastObservedAt: nowIso,
    status: 'active',
    createdAt: nowIso,
    updatedAt: nowIso,
  }];
  const candidates = syncSignalCandidatesFromEvidence({
    bundles,
    candidates: [],
    monitoredCoins: [{ symbol: 'BTC', enabled: true, pct: 50 }],
    nowIso,
  });
  assert(candidates.length === 1, 'candidate created from active evidence');
  assert(candidates[0]?.evidenceBundleId === 'bundle-live', 'candidate points to evidence bundle');
}

console.log(`\nPassed: ${passed}, Failed: ${failed}\n`);
if (failed > 0) process.exit(1);
