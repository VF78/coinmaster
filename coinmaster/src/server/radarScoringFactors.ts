/**
 * Radar scoring factors — seven explicit, deterministic factors composed into a candidate score.
 *
 * Each factor is in [0, 1] and intentionally simple enough to be explained in a sentence:
 *
 *   relevance         — does the evidence map to a Trading Rules monitored symbol?
 *   novelty           — how new is this evidence vs. recent bundles?
 *   sourceReliability — credibility of the contributing sources (primary vs. duplicate, source class).
 *   eventSeverity     — how impactful is the event (regulatory > listing > general news).
 *   timeDecay         — recency: 1.0 = ≤15 min, decays linearly to 0 over 4 h.
 *   marketConfirmation — alignment with live market structure (price/move proxy, optional).
 *   executionability  — symbol monitored, sizing possible, no risk-gate veto.
 *
 * The composite score is a fixed-weight linear combination, then clamped to [0, 100].
 * Weights are exported as `RADAR_SCORING_WEIGHTS` so they can be persisted alongside
 * the score for auditability.
 */

import type {
  AlphaRadarSourceClass,
  AlphaRadarSourceLayer,
  EvidenceBundle,
  SignalCandidateScore,
  SignalCandidateScoringFactors,
} from '../shared/dto.js';

const FRESH_WINDOW_MS = 15 * 60 * 1000;
const STALE_WINDOW_MS = 4 * 60 * 60 * 1000;
const NOVELTY_LOOKBACK_MS = 6 * 60 * 60 * 1000;

/** Default fixed weights (sum: 1.0). Persisted alongside the score so audits don't drift. */
export const RADAR_SCORING_WEIGHTS: SignalCandidateScoringFactors = {
  relevance: 0.20,
  novelty: 0.10,
  sourceReliability: 0.15,
  eventSeverity: 0.15,
  timeDecay: 0.15,
  marketConfirmation: 0.10,
  executionability: 0.15,
};

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value <= 0) return 0;
  if (value >= 1) return 1;
  return value;
}

function weightForSourceClass(sourceClass: AlphaRadarSourceClass | undefined): number {
  if (sourceClass === 'official') return 1;
  if (sourceClass === 'newswire') return 0.85;
  if (sourceClass === 'market') return 0.8;
  if (sourceClass === 'macro') return 0.75;
  if (sourceClass === 'flow') return 0.6;
  if (sourceClass === 'social') return 0.5;
  return 0.5;
}

function weightForSourceLayer(layer: AlphaRadarSourceLayer | undefined): number {
  if (layer === 'primary') return 1;
  if (layer === 'duplicate') return 0.6;
  if (layer === 'narrative') return 0.4;
  return 0.6;
}

export function computeRelevanceFactor(input: {
  symbol?: string;
  monitoredSymbols: string[];
  assetTags: string[];
}): number {
  if (!input.symbol) {
    if (input.assetTags.length === 0) return 0;
    const overlap = input.assetTags.some((tag) =>
      input.monitoredSymbols.some((s) => s.toUpperCase() === tag.toUpperCase()),
    );
    return overlap ? 0.5 : 0.1;
  }
  const upper = input.symbol.toUpperCase();
  return input.monitoredSymbols.some((s) => s.toUpperCase() === upper) ? 1 : 0;
}

export function computeNoveltyFactor(input: {
  bundle: Pick<EvidenceBundle, 'firstObservedAt' | 'duplicateSuppressedCount'>;
  nowMs?: number;
}): number {
  const nowMs = input.nowMs ?? Date.now();
  const firstMs = Date.parse(input.bundle.firstObservedAt);
  if (!Number.isFinite(firstMs)) return 0.5;
  const ageMs = Math.max(0, nowMs - firstMs);
  const ageFactor = ageMs >= NOVELTY_LOOKBACK_MS ? 0 : 1 - ageMs / NOVELTY_LOOKBACK_MS;
  const dupePenalty = Math.min(0.5, (input.bundle.duplicateSuppressedCount ?? 0) * 0.05);
  return clamp01(ageFactor - dupePenalty);
}

export function computeSourceReliabilityFactor(input: {
  bundle: Pick<EvidenceBundle, 'sources' | 'sourceClasses' | 'sourceLayers'>;
}): number {
  if (input.bundle.sources.length === 0) return 0;
  const classScore = input.bundle.sourceClasses.length === 0
    ? 0.5
    : input.bundle.sourceClasses.reduce((acc, cls) => Math.max(acc, weightForSourceClass(cls)), 0);
  const layerScore = input.bundle.sourceLayers.length === 0
    ? 0.6
    : input.bundle.sourceLayers.reduce((acc, layer) => Math.max(acc, weightForSourceLayer(layer)), 0);
  const breadth = Math.min(1, input.bundle.sources.length / 3);
  return clamp01(0.4 * classScore + 0.4 * layerScore + 0.2 * breadth);
}

const SEVERITY_KEYWORDS: Array<{ pattern: RegExp; weight: number }> = [
  { pattern: /\b(?:hack(?:ed)?|exploit|breach|seize|sanctioned?|enforcement)\b/i, weight: 1 },
  { pattern: /\b(?:sec|cftc|doj|treasury|regul(?:ation|atory)|lawsuit|charged?)\b/i, weight: 0.85 },
  { pattern: /\b(?:halt(?:ed)?|delisted?|suspend(?:ed)?|frozen|liquidat(?:ion|ed))\b/i, weight: 0.8 },
  { pattern: /\b(?:listing|listed|launch(?:ed|ing)?|airdrop)\b/i, weight: 0.6 },
  { pattern: /\b(?:upgrade|fork|partnership|integration)\b/i, weight: 0.45 },
];

export function computeEventSeverityFactor(input: {
  bundle: Pick<EvidenceBundle, 'title' | 'excerpt' | 'topicTags'>;
}): number {
  const haystack = `${input.bundle.title} ${input.bundle.excerpt} ${input.bundle.topicTags.join(' ')}`;
  let best = 0;
  for (const entry of SEVERITY_KEYWORDS) {
    if (entry.pattern.test(haystack)) {
      if (entry.weight > best) best = entry.weight;
    }
  }
  return best || 0.3;
}

export function computeTimeDecayFactor(input: {
  bundle: Pick<EvidenceBundle, 'lastObservedAt'>;
  nowMs?: number;
}): number {
  const nowMs = input.nowMs ?? Date.now();
  const lastMs = Date.parse(input.bundle.lastObservedAt);
  if (!Number.isFinite(lastMs)) return 0;
  const ageMs = Math.max(0, nowMs - lastMs);
  if (ageMs <= FRESH_WINDOW_MS) return 1;
  if (ageMs >= STALE_WINDOW_MS) return 0;
  return 1 - (ageMs - FRESH_WINDOW_MS) / (STALE_WINDOW_MS - FRESH_WINDOW_MS);
}

export function computeMarketConfirmationFactor(input: {
  marketAlignmentScore?: number;
  marketStructureAligned?: boolean;
}): number {
  if (typeof input.marketAlignmentScore === 'number' && Number.isFinite(input.marketAlignmentScore)) {
    return clamp01(input.marketAlignmentScore);
  }
  if (input.marketStructureAligned === true) return 0.7;
  if (input.marketStructureAligned === false) return 0.2;
  return 0.5;
}

export function computeExecutionabilityFactor(input: {
  symbolMonitored: boolean;
  sizeable: boolean;
  riskBlocked?: boolean;
}): number {
  if (input.riskBlocked) return 0;
  if (!input.symbolMonitored) return 0;
  return input.sizeable ? 1 : 0.4;
}

export function compositeFromFactors(
  factors: SignalCandidateScoringFactors,
  weights: SignalCandidateScoringFactors = RADAR_SCORING_WEIGHTS,
): number {
  const raw =
    factors.relevance * weights.relevance +
    factors.novelty * weights.novelty +
    factors.sourceReliability * weights.sourceReliability +
    factors.eventSeverity * weights.eventSeverity +
    factors.timeDecay * weights.timeDecay +
    factors.marketConfirmation * weights.marketConfirmation +
    factors.executionability * weights.executionability;
  const totalWeight =
    weights.relevance + weights.novelty + weights.sourceReliability + weights.eventSeverity +
    weights.timeDecay + weights.marketConfirmation + weights.executionability;
  const normalized = totalWeight > 0 ? raw / totalWeight : 0;
  return Math.max(0, Math.min(100, Math.round(normalized * 100)));
}

export function scoreSignalCandidate(input: {
  bundle: EvidenceBundle;
  symbol?: string;
  monitoredSymbols: string[];
  symbolMonitored: boolean;
  sizeable: boolean;
  riskBlocked?: boolean;
  marketAlignmentScore?: number;
  marketStructureAligned?: boolean;
  weights?: SignalCandidateScoringFactors;
  nowMs?: number;
}): SignalCandidateScore {
  const weights = input.weights ?? RADAR_SCORING_WEIGHTS;
  const factors: SignalCandidateScoringFactors = {
    relevance: clamp01(computeRelevanceFactor({
      symbol: input.symbol,
      monitoredSymbols: input.monitoredSymbols,
      assetTags: input.bundle.assetTags,
    })),
    novelty: clamp01(computeNoveltyFactor({ bundle: input.bundle, nowMs: input.nowMs })),
    sourceReliability: clamp01(computeSourceReliabilityFactor({ bundle: input.bundle })),
    eventSeverity: clamp01(computeEventSeverityFactor({ bundle: input.bundle })),
    timeDecay: clamp01(computeTimeDecayFactor({ bundle: input.bundle, nowMs: input.nowMs })),
    marketConfirmation: clamp01(computeMarketConfirmationFactor({
      marketAlignmentScore: input.marketAlignmentScore,
      marketStructureAligned: input.marketStructureAligned,
    })),
    executionability: clamp01(computeExecutionabilityFactor({
      symbolMonitored: input.symbolMonitored,
      sizeable: input.sizeable,
      riskBlocked: input.riskBlocked,
    })),
  };
  return {
    factors,
    composite: compositeFromFactors(factors, weights),
    weights,
  };
}
