import type { EvidenceBundle, EvidenceBundleEnrichment } from '../shared/dto.js';

const ENRICHMENT_CACHE_TTL_MS = 10 * 60 * 1000;

type CacheEntry = {
  hash: string;
  atMs: number;
  enrichment: EvidenceBundleEnrichment;
};

const cache = new Map<string, CacheEntry>();

const TICKER_PATTERNS = [
  'BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB', 'ADA', 'AVAX', 'LINK', 'MATIC', 'ARB', 'OP', 'SUI', 'WLD', 'HYPE',
];
const REGULATOR_PATTERNS = ['SEC', 'CFTC', 'DOJ', 'Treasury', 'Fed', 'FOMC', 'ECB', 'ESMA'];
const VENUE_PATTERNS = ['Binance', 'Coinbase', 'Kraken', 'Bybit', 'OKX', 'Hyperliquid'];
const ISSUER_PATTERNS = ['BlackRock', 'Grayscale', 'MicroStrategy', 'Strategy', 'Tether', 'Circle'];
const BULLISH = ['approval', 'approved', 'launch', 'listed', 'listing', 'partnership', 'integration', 'buyback', 'inflow', 'upgrade'];
const BEARISH = ['hack', 'exploit', 'breach', 'lawsuit', 'charged', 'ban', 'sanction', 'outflow', 'liquidation', 'drain', 'seized'];

function normalizedHash(bundle: Pick<EvidenceBundle, 'title' | 'excerpt' | 'observationIds'>): string {
  return `${bundle.title}|||${bundle.excerpt}|||${bundle.observationIds.join(',')}`.toLowerCase();
}

function extractMatches(text: string, values: string[], type: 'ticker' | 'org' | 'event') {
  return values
    .filter((value) => new RegExp(`\\b${value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i').test(text))
    .map((value) => ({ type, value }));
}

function sentimentScore(text: string): { score: number; confidence: number; label: 'bearish' | 'neutral' | 'bullish' } {
  const lower = text.toLowerCase();
  const bullishHits = BULLISH.filter((word) => lower.includes(word.toLowerCase())).length;
  const bearishHits = BEARISH.filter((word) => lower.includes(word.toLowerCase())).length;
  const total = bullishHits + bearishHits;
  if (total === 0) {
    return { score: 0, confidence: 0.25, label: 'neutral' };
  }
  const raw = (bullishHits - bearishHits) / Math.max(1, total);
  const score = Number(Math.max(-1, Math.min(1, raw)).toFixed(4));
  return {
    score,
    confidence: Number(Math.min(0.85, 0.35 + total * 0.12).toFixed(4)),
    label: score > 0.15 ? 'bullish' : score < -0.15 ? 'bearish' : 'neutral',
  };
}

export async function enrichEvidenceBundle(bundle: EvidenceBundle, nowIso: string): Promise<EvidenceBundleEnrichment> {
  const hash = normalizedHash(bundle);
  const nowMs = Date.parse(nowIso);
  const cached = cache.get(bundle.id);
  if (cached && cached.hash === hash && nowMs - cached.atMs <= ENRICHMENT_CACHE_TTL_MS) {
    return cached.enrichment;
  }

  const text = `${bundle.title} ${bundle.excerpt} ${bundle.topicTags.join(' ')}`.replace(/\s+/g, ' ').trim();
  const entities = [
    ...extractMatches(text, TICKER_PATTERNS, 'ticker'),
    ...extractMatches(text, REGULATOR_PATTERNS, 'org'),
    ...extractMatches(text, VENUE_PATTERNS, 'org'),
    ...extractMatches(text, ISSUER_PATTERNS, 'org'),
  ];
  const financeSentiment = sentimentScore(text);
  const enrichment: EvidenceBundleEnrichment = {
    sentimentScore: financeSentiment.score,
    sentimentConfidence: financeSentiment.confidence,
    sentimentAdapter: 'lexicon-fallback',
    sentimentLabel: financeSentiment.label,
    namedEntities: entities,
    nerAdapter: 'pattern-fallback',
    usedFallback: true,
    computedAt: nowIso,
  };
  cache.set(bundle.id, { hash, atMs: nowMs, enrichment });
  return enrichment;
}

