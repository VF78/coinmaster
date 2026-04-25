import type {
  AssetClass,
  EvidenceBundle,
  ExecutionIntentPolicySnapshot,
  RadarContextAssetOverride,
  RadarContextDirectionMode,
  RadarContextPolicy,
  RadarContextPolicyReasonCode,
  SignalCandidate,
  TradingCoinAllocation,
} from '../shared/dto.js';
import { inferAssetClassFromSymbol } from '../shared/tradingRules.js';

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  if (value <= min) return min;
  if (value >= max) return max;
  return value;
}

function unique<T>(items: T[]): T[] {
  return [...new Set(items)];
}

function chooseNarrativeRegime(candidate: SignalCandidate, bundle?: EvidenceBundle): string {
  const sentiment = bundle?.enrichment?.sentimentScore ?? 0;
  const confirmation = candidate.score?.factors.marketConfirmation ?? 0;
  if (candidate.side === 'buy' && sentiment >= 0.2) return confirmation >= 0.6 ? 'risk_on_trend_confirmation' : 'bullish_catalyst_watch';
  if (candidate.side === 'sell' && sentiment <= -0.2) return confirmation >= 0.6 ? 'risk_off_trend_confirmation' : 'bearish_catalyst_watch';
  return confirmation >= 0.55 ? 'two_way_confirmed_context' : 'mixed_low_conviction_context';
}

function inferDirectionMode(candidate: SignalCandidate, bundle?: EvidenceBundle): RadarContextDirectionMode {
  const sentiment = bundle?.enrichment?.sentimentScore ?? 0;
  const score = candidate.score?.composite ?? 0;
  if (score < 60) return 'blocked';
  if (Math.abs(sentiment) < 0.12 && score >= 65) return 'both';
  return candidate.side === 'buy' ? 'long_only' : 'short_only';
}

function inferRiskMultiplier(candidate: SignalCandidate, directionMode: RadarContextDirectionMode): number {
  if (directionMode === 'blocked') return 0;
  const score = candidate.score?.composite ?? 0;
  if (candidate.state === 'actionable' || candidate.state === 'routed' || candidate.state === 'executed') {
    return Number(clamp(score / 80, 0.75, 1.5).toFixed(2));
  }
  if (candidate.state === 'validated') {
    return Number(clamp(score / 100, 0.35, 0.8).toFixed(2));
  }
  return 0;
}

function isHighImpactLockout(bundle?: EvidenceBundle, candidate?: SignalCandidate): boolean {
  if (!bundle || !candidate) return false;
  const topicTags = new Set((bundle.topicTags ?? []).map((item) => String(item).toLowerCase()));
  const sourceClasses = new Set((bundle.sourceClasses ?? []).map((item) => String(item).toLowerCase()));
  const severity = candidate.score?.factors.eventSeverity ?? 0;
  return severity >= 0.85 || topicTags.has('macro-shock') || topicTags.has('enforcement') || sourceClasses.has('macro');
}

function mergeReasonCodes(reasonCodes: RadarContextPolicyReasonCode[]): RadarContextPolicyReasonCode[] {
  return unique(reasonCodes).sort();
}

function policySnapshotFromPolicy(policy: RadarContextPolicy): ExecutionIntentPolicySnapshot {
  return {
    policyId: policy.id,
    symbol: policy.symbol,
    directionMode: policy.directionMode,
    riskMultiplier: policy.riskMultiplier,
    lockNewEntries: policy.lockNewEntries,
    eventLockoutUntil: policy.eventLockoutUntil,
    narrativeRegime: policy.narrativeRegime,
    priorityScore: policy.priorityScore,
    validUntil: policy.validUntil,
    reasonCodes: [...policy.reasonCodes],
    evidenceIds: [...policy.evidenceIds],
  };
}

function buildBlockedPolicy(params: {
  symbol: string;
  assetClass: AssetClass;
  nowIso: string;
  reasonCodes: RadarContextPolicyReasonCode[];
  evidenceIds?: string[];
  validUntil?: string;
  narrativeRegime?: string;
}): RadarContextPolicy {
  return {
    id: `radar-context-${params.symbol.toLowerCase()}`,
    symbol: params.symbol,
    assetScope: 'symbol',
    assetClass: params.assetClass,
    directionMode: 'blocked',
    riskMultiplier: 0,
    lockNewEntries: true,
    eventLockoutUntil: undefined,
    narrativeRegime: params.narrativeRegime ?? 'blocked_context',
    priorityScore: 0,
    validUntil: params.validUntil,
    assetSpecificOverrides: [],
    reasonCodes: mergeReasonCodes(params.reasonCodes),
    evidenceIds: unique(params.evidenceIds ?? []),
    createdAt: params.nowIso,
    updatedAt: params.nowIso,
  };
}

export function buildRadarContextPolicyBook(params: {
  bundles: EvidenceBundle[];
  candidates: SignalCandidate[];
  monitoredCoins: TradingCoinAllocation[];
  nowIso: string;
  eventLockoutMinutes?: number;
}): RadarContextPolicy[] {
  const bundleById = new Map(params.bundles.map((bundle) => [bundle.id, bundle] as const));
  const nowMs = Date.parse(params.nowIso);
  const monitoredSymbols = params.monitoredCoins
    .filter((coin) => coin.enabled)
    .map((coin) => String(coin.symbol).toUpperCase());

  return monitoredSymbols.map((symbol) => {
    const assetClass = inferAssetClassFromSymbol(symbol);
    const activeCandidates = params.candidates
      .filter((candidate) => candidate.symbol.toUpperCase() === symbol)
      .filter((candidate) => candidate.state !== 'expired' && candidate.state !== 'rejected' && candidate.state !== 'postmortem_ready');

    if (activeCandidates.length === 0) {
      return buildBlockedPolicy({
        symbol,
        assetClass,
        nowIso: params.nowIso,
        reasonCodes: ['missing_required_evidence'],
        narrativeRegime: 'missing_context',
      });
    }

    const bestCandidate = activeCandidates
      .slice()
      .sort((a, b) => (b.score?.composite ?? 0) - (a.score?.composite ?? 0) || Date.parse(b.updatedAt) - Date.parse(a.updatedAt))[0];
    const bundle = bundleById.get(bestCandidate.evidenceBundleId);
    const validUntil = bestCandidate.expiresAt ?? bundle?.lastObservedAt;
    const validUntilMs = validUntil ? Date.parse(validUntil) : Number.NaN;
    if (validUntil && Number.isFinite(validUntilMs) && validUntilMs <= nowMs) {
      return buildBlockedPolicy({
        symbol,
        assetClass,
        nowIso: params.nowIso,
        reasonCodes: ['ttl_expired'],
        evidenceIds: [bestCandidate.evidenceBundleId],
        validUntil,
        narrativeRegime: chooseNarrativeRegime(bestCandidate, bundle),
      });
    }

    const directionMode = inferDirectionMode(bestCandidate, bundle);
    const narrativeRegime = chooseNarrativeRegime(bestCandidate, bundle);
    const riskMultiplier = inferRiskMultiplier(bestCandidate, directionMode);
    const reasonCodes: RadarContextPolicyReasonCode[] = [];
    let lockNewEntries = directionMode === 'blocked';
    let eventLockoutUntil: string | undefined;

    if (directionMode === 'blocked') reasonCodes.push('direction_blocked');
    if (riskMultiplier <= 0) reasonCodes.push('risk_multiplier_blocked');

    if (isHighImpactLockout(bundle, bestCandidate)) {
      const minutes = Math.max(1, Math.round(params.eventLockoutMinutes ?? 60));
      const baseMs = Date.parse(bundle?.lastObservedAt ?? params.nowIso);
      const lockoutMs = Number.isFinite(baseMs) ? baseMs + minutes * 60_000 : nowMs + minutes * 60_000;
      if (lockoutMs > nowMs) {
        eventLockoutUntil = new Date(lockoutMs).toISOString();
        lockNewEntries = true;
        reasonCodes.push('event_lockout');
      }
    }

    if (!bundle) {
      reasonCodes.push('missing_required_evidence');
      lockNewEntries = true;
    }

    const priorityScore = Number(clamp(
      (bestCandidate.score?.composite ?? 0)
      + (bestCandidate.score?.factors.eventSeverity ?? 0) * 10
      + (bestCandidate.score?.factors.sourceReliability ?? 0) * 5,
      0,
      100,
    ).toFixed(2));

    const evidenceIds = unique([bestCandidate.evidenceBundleId]);
    const assetSpecificOverrides: RadarContextAssetOverride[] = unique(bundle?.assetTags ?? [])
      .map((tag) => String(tag).toUpperCase())
      .filter((tag) => monitoredSymbols.includes(tag) && tag !== symbol)
      .slice(0, 4)
      .map((tag) => ({
        symbol: tag,
        directionMode,
        riskMultiplier: Number(clamp(riskMultiplier * 0.5, 0, 1).toFixed(2)),
        lockNewEntries,
        eventLockoutUntil,
        narrativeRegime,
        priorityScore: Number(clamp(priorityScore * 0.75, 0, 100).toFixed(2)),
        validUntil,
        reasonCodes: mergeReasonCodes(reasonCodes),
        evidenceIds,
      }));

    return {
      id: `radar-context-${symbol.toLowerCase()}`,
      symbol,
      assetScope: 'symbol' as const,
      assetClass,
      directionMode,
      riskMultiplier,
      lockNewEntries,
      eventLockoutUntil,
      narrativeRegime,
      priorityScore,
      validUntil,
      assetSpecificOverrides,
      reasonCodes: mergeReasonCodes(reasonCodes),
      evidenceIds,
      signalCandidateId: bestCandidate.id,
      createdAt: params.nowIso,
      updatedAt: params.nowIso,
    };
  }).sort((a, b) => b.priorityScore - a.priorityScore || a.symbol.localeCompare(b.symbol));
}

export function readActiveRadarContextPolicy(params: {
  policies: RadarContextPolicy[];
  symbol: string;
  nowIso?: string;
}): {
  policy?: RadarContextPolicy;
  snapshot?: ExecutionIntentPolicySnapshot;
  reasonCode?: RadarContextPolicyReasonCode;
  expiredPolicy?: RadarContextPolicy;
} {
  const symbol = String(params.symbol).toUpperCase();
  const nowMs = Date.parse(params.nowIso ?? new Date().toISOString());
  const policy = params.policies.find((item) => item.symbol.toUpperCase() === symbol);
  if (!policy) {
    return { reasonCode: 'missing_required_evidence' };
  }
  if (policy.validUntil) {
    const expiresMs = Date.parse(policy.validUntil);
    if (Number.isFinite(expiresMs) && expiresMs <= nowMs) {
      return { reasonCode: 'ttl_expired', expiredPolicy: policy, snapshot: policySnapshotFromPolicy(policy) };
    }
  }
  return { policy, snapshot: policySnapshotFromPolicy(policy) };
}

export function evaluateRadarContextPolicyEntry(params: {
  policies: RadarContextPolicy[];
  symbol: string;
  side: 'buy' | 'sell';
  reduceOnly?: boolean;
  nowIso?: string;
}): {
  allowed: boolean;
  reasonCode?: RadarContextPolicyReasonCode;
  policy?: RadarContextPolicy;
  snapshot?: ExecutionIntentPolicySnapshot;
} {
  if (params.reduceOnly) {
    return { allowed: true };
  }

  const active = readActiveRadarContextPolicy({
    policies: params.policies,
    symbol: params.symbol,
    nowIso: params.nowIso,
  });

  if (!active.policy) {
    return {
      allowed: false,
      reasonCode: active.reasonCode ?? 'missing_required_evidence',
      snapshot: active.snapshot,
    };
  }

  const policy = active.policy;
  const nowMs = Date.parse(params.nowIso ?? new Date().toISOString());
  const side = params.side;

  if (policy.eventLockoutUntil) {
    const lockoutMs = Date.parse(policy.eventLockoutUntil);
    if (Number.isFinite(lockoutMs) && lockoutMs > nowMs) {
      return { allowed: false, reasonCode: 'event_lockout', policy, snapshot: active.snapshot };
    }
  }

  if (policy.reasonCodes.includes('missing_required_evidence') && policy.evidenceIds.length === 0) {
    return { allowed: false, reasonCode: 'missing_required_evidence', policy, snapshot: active.snapshot };
  }

  if (policy.riskMultiplier <= 0 || policy.reasonCodes.includes('risk_multiplier_blocked')) {
    return { allowed: false, reasonCode: 'risk_multiplier_blocked', policy, snapshot: active.snapshot };
  }

  if (
    policy.directionMode === 'blocked'
    || (policy.directionMode === 'long_only' && side !== 'buy')
    || (policy.directionMode === 'short_only' && side !== 'sell')
  ) {
    return { allowed: false, reasonCode: 'direction_blocked', policy, snapshot: active.snapshot };
  }

  return { allowed: true, policy, snapshot: active.snapshot };
}
