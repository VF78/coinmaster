import { createHash } from 'node:crypto';

import type {
  AlphaRadarObservation,
  EvidenceBundle,
  SignalCandidate,
  TradingCoinAllocation,
} from '../shared/dto.js';
import { enrichEvidenceBundle } from './alphaRadarNlp.js';
import { RADAR_SCORING_WEIGHTS, scoreSignalCandidate } from './radarScoringFactors.js';
import { createSignalCandidate, isSignalCandidateExpired, transitionSignalCandidate } from './radarSignalCandidate.js';

const MAX_ACTIVE_BUNDLES = 800;
const EVIDENCE_BUNDLE_TTL_MS = 24 * 60 * 60 * 1000;
const FUZZY_MATCH_THRESHOLD = 0.6;
const CANDIDATE_VALIDATE_SCORE = 45;
const CANDIDATE_ACTIONABLE_SCORE = 70;

export type EvidenceMatchType = 'new' | 'exact_hash' | 'canonical_url' | 'external_id' | 'fuzzy';

function unique<T>(items: T[]): T[] {
  return [...new Set(items)];
}

export function canonicalizeUrl(url: unknown): string | undefined {
  const raw = String(url ?? '').trim();
  if (!raw) return undefined;
  try {
    const parsed = new URL(raw);
    parsed.hash = '';
    for (const key of [...parsed.searchParams.keys()]) {
      if (/^(utm_|fbclid$|gclid$|mc_cid$|mc_eid$|ref$|ref_src$)/i.test(key)) {
        parsed.searchParams.delete(key);
      }
    }
    parsed.hostname = parsed.hostname.toLowerCase();
    if ((parsed.protocol === 'https:' && parsed.port === '443') || (parsed.protocol === 'http:' && parsed.port === '80')) {
      parsed.port = '';
    }
    return parsed.toString();
  } catch {
    return raw;
  }
}

function compactRawPayloadRef(input: unknown, maxChars = 1_200): string | undefined {
  const raw = typeof input === 'string' ? input : input && typeof input === 'object' ? JSON.stringify(input) : '';
  const compact = String(raw ?? '').replace(/\s+/g, ' ').trim();
  return compact ? compact.slice(0, maxChars) : undefined;
}

function normalizeTimestamp(value: unknown, fallbackIso: string): string {
  const raw = String(value ?? '').trim();
  if (!raw) return fallbackIso;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : fallbackIso;
}

function buildPayloadHash(input: Pick<AlphaRadarObservation, 'title' | 'excerpt' | 'assetTags' | 'topicTags' | 'provenance'>): string {
  return createHash('sha1').update(
    [
      input.title.trim().toLowerCase(),
      input.excerpt.trim().toLowerCase(),
      canonicalizeUrl(input.provenance?.canonicalUrl ?? input.provenance?.url) ?? '',
      [...input.assetTags].sort().join(','),
      [...input.topicTags].sort().join(','),
    ].join('|'),
  ).digest('hex');
}

function normalizeDedupeText(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((token) => token && token.length > 2);
}

function fuzzySimilarity(left: string, right: string): number {
  const a = normalizeDedupeText(left);
  const b = normalizeDedupeText(right);
  if (a.length === 0 || b.length === 0) return 0;
  const aSet = new Set(a);
  const bSet = new Set(b);
  let shared = 0;
  for (const token of aSet) {
    if (bSet.has(token)) shared += 1;
  }
  return Number((shared / Math.max(aSet.size, bSet.size)).toFixed(4));
}

export function normalizeObservationForEvidence(observation: AlphaRadarObservation, nowIso: string): AlphaRadarObservation {
  const canonicalUrl = canonicalizeUrl(observation.provenance?.canonicalUrl ?? observation.provenance?.url);
  const observedAt = normalizeTimestamp(observation.observedAt ?? observation.provenance?.observedAt, nowIso);
  const fetchedAt = normalizeTimestamp(observation.provenance?.fetchedAt ?? observation.createdAt, nowIso);
  const payloadHash = observation.provenance?.payloadHash ?? buildPayloadHash({
    title: observation.title,
    excerpt: observation.excerpt,
    assetTags: observation.assetTags,
    topicTags: observation.topicTags,
    provenance: { ...observation.provenance, canonicalUrl },
  });
  return {
    ...observation,
    observedAt,
    provenance: {
      ...observation.provenance,
      canonicalUrl,
      payloadHash,
      publishedAt: observation.provenance?.publishedAt ? normalizeTimestamp(observation.provenance.publishedAt, observedAt) : undefined,
      observedAt,
      fetchedAt,
      rawPayloadRef: observation.provenance?.rawPayloadRef ?? compactRawPayloadRef(observation.metadata),
      parser: String(observation.provenance?.parser ?? (observation.metadata?.parser as string | undefined) ?? 'native').trim() || 'native',
    },
  };
}

function createBundleFromObservation(observation: AlphaRadarObservation, nowIso: string, bundleId: string): EvidenceBundle {
  return {
    id: bundleId,
    clusterKey: observation.provenance?.canonicalUrl ?? observation.title.toLowerCase(),
    payloadHash: observation.provenance?.payloadHash,
    canonicalUrl: observation.provenance?.canonicalUrl,
    title: observation.title,
    excerpt: observation.excerpt,
    assetTags: [...observation.assetTags],
    topicTags: [...observation.topicTags],
    sources: [observation.source],
    sourceClasses: observation.sourceClass ? [observation.sourceClass] : [],
    sourceLayers: observation.sourceLayer ? [observation.sourceLayer] : [],
    observationIds: [observation.id],
    externalIds: observation.provenance?.externalId ? [observation.provenance.externalId] : [],
    exactMatchCount: 0,
    canonicalUrlMatchCount: 0,
    externalIdMatchCount: 0,
    fuzzyMatchCount: 0,
    duplicateSuppressedCount: 0,
    firstObservedAt: observation.observedAt,
    lastObservedAt: observation.observedAt,
    status: 'active',
    createdAt: nowIso,
    updatedAt: nowIso,
  };
}

function findBundleMatch(
  bundles: EvidenceBundle[],
  observation: AlphaRadarObservation,
): { bundle: EvidenceBundle; type: EvidenceMatchType; similarity?: number } | null {
  const payloadHash = observation.provenance?.payloadHash;
  const canonicalUrl = observation.provenance?.canonicalUrl;
  const externalId = observation.provenance?.externalId;
  if (payloadHash) {
    const byHash = bundles.find((bundle) => bundle.status === 'active' && bundle.payloadHash === payloadHash);
    if (byHash) return { bundle: byHash, type: 'exact_hash' };
  }
  if (canonicalUrl) {
    const byUrl = bundles.find((bundle) => bundle.status === 'active' && bundle.canonicalUrl === canonicalUrl);
    if (byUrl) return { bundle: byUrl, type: 'canonical_url' };
  }
  if (externalId) {
    const byExternal = bundles.find((bundle) => bundle.status === 'active' && (bundle.externalIds ?? []).includes(externalId));
    if (byExternal) return { bundle: byExternal, type: 'external_id' };
  }
  const left = `${observation.title} ${observation.excerpt}`;
  let best: { bundle: EvidenceBundle; type: EvidenceMatchType; similarity?: number } | null = null;
  for (const bundle of bundles) {
    if (bundle.status !== 'active') continue;
    const similarity = fuzzySimilarity(left, `${bundle.title} ${bundle.excerpt}`);
    if (similarity < FUZZY_MATCH_THRESHOLD) continue;
    if (!best || similarity > (best.similarity ?? 0)) {
      best = { bundle, type: 'fuzzy', similarity };
    }
  }
  return best;
}

export async function ingestObservationIntoEvidence(params: {
  observation: AlphaRadarObservation;
  bundles: EvidenceBundle[];
  nowIso: string;
  nextBundleId: () => string;
}): Promise<{ bundle: EvidenceBundle; observation: AlphaRadarObservation; matchType: EvidenceMatchType; created: boolean }> {
  const normalized = normalizeObservationForEvidence(params.observation, params.nowIso);
  const existingMatch = findBundleMatch(params.bundles, normalized);
  if (!existingMatch) {
    const bundle = createBundleFromObservation(normalized, params.nowIso, params.nextBundleId());
    bundle.enrichment = await enrichEvidenceBundle(bundle, params.nowIso);
    params.bundles.push(bundle);
    return {
      bundle,
      created: true,
      matchType: 'new',
      observation: {
        ...normalized,
        metadata: {
          ...(normalized.metadata ?? {}),
          evidenceBundleId: bundle.id,
          dedupeMatchType: 'new',
          dedupeMergedCount: 0,
        },
      },
    };
  }

  const bundle = existingMatch.bundle;
  bundle.title = bundle.title.length >= normalized.title.length ? bundle.title : normalized.title;
  bundle.excerpt = bundle.excerpt.length >= normalized.excerpt.length ? bundle.excerpt : normalized.excerpt;
  bundle.assetTags = unique([...bundle.assetTags, ...normalized.assetTags]);
  bundle.topicTags = unique([...bundle.topicTags, ...normalized.topicTags]);
  bundle.sources = unique([...bundle.sources, normalized.source]);
  bundle.sourceClasses = unique([...bundle.sourceClasses, ...(normalized.sourceClass ? [normalized.sourceClass] : [])]);
  bundle.sourceLayers = unique([...bundle.sourceLayers, ...(normalized.sourceLayer ? [normalized.sourceLayer] : [])]);
  bundle.externalIds = unique([...(bundle.externalIds ?? []), ...(normalized.provenance?.externalId ? [normalized.provenance.externalId] : [])]);
  if (!bundle.observationIds.includes(normalized.id)) {
    bundle.observationIds.push(normalized.id);
  } else {
    bundle.duplicateSuppressedCount += 1;
  }
  bundle.lastObservedAt = bundle.lastObservedAt > normalized.observedAt ? bundle.lastObservedAt : normalized.observedAt;
  bundle.updatedAt = params.nowIso;
  if (existingMatch.type === 'exact_hash') bundle.exactMatchCount += 1;
  if (existingMatch.type === 'canonical_url') bundle.canonicalUrlMatchCount += 1;
  if (existingMatch.type === 'external_id') bundle.externalIdMatchCount += 1;
  if (existingMatch.type === 'fuzzy') bundle.fuzzyMatchCount += 1;
  bundle.enrichment = await enrichEvidenceBundle(bundle, params.nowIso);

  return {
    bundle,
    created: false,
    matchType: existingMatch.type,
    observation: {
      ...normalized,
      metadata: {
        ...(normalized.metadata ?? {}),
        evidenceBundleId: bundle.id,
        dedupeMatchType: existingMatch.type,
        dedupeMergedCount: (normalized.metadata?.dedupeMergedCount as number | undefined) ?? 1,
        fuzzyMatchScore: existingMatch.similarity,
      },
    },
  };
}

export function pruneEvidenceBundles(bundles: EvidenceBundle[], nowIso: string): EvidenceBundle[] {
  const cutoffMs = Date.parse(nowIso) - EVIDENCE_BUNDLE_TTL_MS;
  const active = bundles
    .map((bundle) => {
      if (bundle.status !== 'active') return bundle;
      const lastObservedMs = Date.parse(bundle.lastObservedAt);
      if (Number.isFinite(lastObservedMs) && lastObservedMs < cutoffMs) {
        return { ...bundle, status: 'expired' as const, expiredReason: 'staleness', updatedAt: nowIso };
      }
      return bundle;
    })
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, MAX_ACTIVE_BUNDLES);
  return active;
}

function inferCandidateSide(bundle: EvidenceBundle): 'buy' | 'sell' {
  const score = bundle.enrichment?.sentimentScore ?? 0;
  return score < 0 ? 'sell' : 'buy';
}

function inferBundleSymbol(bundle: EvidenceBundle, monitoredSymbols: string[]): string | undefined {
  const monitored = new Set(monitoredSymbols.map((item) => item.toUpperCase()));
  return bundle.assetTags.find((tag) => monitored.has(tag.toUpperCase()));
}

function candidateExpiresAt(bundle: EvidenceBundle): string {
  return new Date(Date.parse(bundle.lastObservedAt) + 6 * 60 * 60 * 1000).toISOString();
}

export function syncSignalCandidatesFromEvidence(params: {
  bundles: EvidenceBundle[];
  candidates: SignalCandidate[];
  monitoredCoins: TradingCoinAllocation[];
  nowIso: string;
}): SignalCandidate[] {
  const monitoredSymbols = params.monitoredCoins.filter((coin) => coin.enabled).map((coin) => coin.symbol.toUpperCase());
  const next = [...params.candidates];
  for (const bundle of params.bundles) {
    if (bundle.status !== 'active') continue;
    const symbol = inferBundleSymbol(bundle, monitoredSymbols);
    if (!symbol) continue;
    const existingIndex = next.findIndex((candidate) => candidate.evidenceBundleId === bundle.id && candidate.symbol.toUpperCase() === symbol.toUpperCase());
    const score = scoreSignalCandidate({
      bundle,
      symbol,
      monitoredSymbols,
      symbolMonitored: true,
      sizeable: true,
      riskBlocked: false,
      marketAlignmentScore: undefined,
      marketStructureAligned: undefined,
      weights: RADAR_SCORING_WEIGHTS,
      nowMs: Date.parse(params.nowIso),
    });
    if (existingIndex === -1) {
      const candidate = createSignalCandidate({
        id: `sigcand-${bundle.id}-${symbol.toLowerCase()}`,
        evidenceBundleId: bundle.id,
        symbol,
        side: inferCandidateSide(bundle),
        expiresAt: candidateExpiresAt(bundle),
        score,
        nowIso: params.nowIso,
      });
      next.push(candidate);
      continue;
    }

    let candidate: SignalCandidate = {
      ...next[existingIndex],
      score,
      expiresAt: candidateExpiresAt(bundle),
      updatedAt: params.nowIso,
    };
    if (isSignalCandidateExpired(candidate, Date.parse(params.nowIso))) {
      const expired = transitionSignalCandidate(candidate, { to: 'expired', reason: 'evidence_ttl_elapsed', at: params.nowIso, score });
      if (expired.ok) candidate = expired.candidate;
      next[existingIndex] = candidate;
      continue;
    }
    if (candidate.state === 'new' && score.composite >= CANDIDATE_VALIDATE_SCORE) {
      const validated = transitionSignalCandidate(candidate, { to: 'validated', reason: 'score_reached_validation_threshold', at: params.nowIso, score });
      if (validated.ok) candidate = validated.candidate;
    }
    if (candidate.state === 'validated' && score.composite >= CANDIDATE_ACTIONABLE_SCORE) {
      const actionable = transitionSignalCandidate(candidate, { to: 'actionable', reason: 'score_reached_actionable_threshold', at: params.nowIso, score });
      if (actionable.ok) candidate = actionable.candidate;
    }
    next[existingIndex] = candidate;
  }
  return next.sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt));
}
