import type { RadarContextPolicy, RadarContextPolicyReasonCode, TradingCoinAllocation } from '../shared/dto.js';

export type FreqtradeRadarMode = 'both' | 'long_only' | 'short_only' | 'off';

export interface FreqtradeRadarScope {
  mode: FreqtradeRadarMode;
  risk_multiplier: number;
  lock_new_entries?: boolean;
  reason: string;
  reason_codes?: RadarContextPolicyReasonCode[];
  narrative_regime?: string;
  priority_score?: number;
  evidence_ids?: string[];
  signal_candidate_id?: string;
  source_policy_id?: string;
}

export interface FreqtradeRadarPolicySnapshot {
  schema_version: 1;
  source: 'coinmaster-alpha-radar';
  generated_by: 'coinmaster-freqtrade-radar-producer';
  updated_at: string;
  valid_until: string;
  global: FreqtradeRadarScope & { enabled: boolean };
  pairs: Record<string, FreqtradeRadarScope>;
  diagnostics: {
    monitored_pairs: number;
    active_pair_overrides: number;
    ignored_neutral_policies: number;
    ignored_expired_policies: number;
    ignored_unmonitored_policies: number;
  };
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  if (value <= min) return min;
  if (value >= max) return max;
  return value;
}

function normalizeSymbol(value: unknown): string {
  return String(value ?? '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9:_-]/g, '')
    .slice(0, 32);
}

export function coinmasterSymbolToFreqtradeRadarPair(symbol: string): string | null {
  const raw = normalizeSymbol(symbol);
  if (!raw) return null;

  if (raw.includes(':')) {
    const [namespace, asset] = raw.split(':', 2);
    if (!namespace || !asset) return null;
    return `${namespace}-${asset}/USDC:USDC`;
  }

  return `${raw}/USDC:USDC`;
}

function modeFromPolicy(policy: RadarContextPolicy): FreqtradeRadarMode {
  if (policy.lockNewEntries || policy.directionMode === 'blocked' || policy.riskMultiplier <= 0) return 'off';
  if (policy.directionMode === 'long_only') return 'long_only';
  if (policy.directionMode === 'short_only') return 'short_only';
  return 'both';
}

function reasonFromPolicy(policy: RadarContextPolicy): string {
  const reasonCodes = policy.reasonCodes.length > 0 ? policy.reasonCodes.join(',') : 'context_policy';
  return [policy.narrativeRegime, reasonCodes]
    .filter(Boolean)
    .join(':')
    .slice(0, 120) || 'context_policy';
}

function isMissingEvidenceNeutral(policy: RadarContextPolicy): boolean {
  return policy.reasonCodes.includes('missing_required_evidence') && policy.evidenceIds.length === 0 && !policy.signalCandidateId;
}

function isExpired(policy: RadarContextPolicy, nowMs: number): boolean {
  if (!policy.validUntil) return false;
  const validUntilMs = Date.parse(policy.validUntil);
  return Number.isFinite(validUntilMs) && validUntilMs <= nowMs;
}

function policyPriority(policy: RadarContextPolicy): number {
  return Number.isFinite(policy.priorityScore) ? policy.priorityScore : 0;
}

function safeTime(value: unknown): number {
  const parsed = Date.parse(String(value ?? ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function buildFreqtradeRadarPolicySnapshot(params: {
  policies: RadarContextPolicy[];
  monitoredCoins: TradingCoinAllocation[];
  nowIso: string;
  ttlMs?: number;
}): FreqtradeRadarPolicySnapshot {
  const nowMs = Date.parse(params.nowIso);
  const safeNowMs = Number.isFinite(nowMs) ? nowMs : Date.now();
  const ttlMs = Math.max(60_000, Math.min(60 * 60_000, Math.round(params.ttlMs ?? 10 * 60_000)));
  const validUntil = new Date(safeNowMs + ttlMs).toISOString();

  const monitoredPairs = new Map<string, string>();
  for (const coin of params.monitoredCoins) {
    if (!coin.enabled) continue;
    const symbol = normalizeSymbol(coin.symbol);
    const pair = coinmasterSymbolToFreqtradeRadarPair(symbol);
    if (symbol && pair) monitoredPairs.set(symbol, pair);
  }

  const sortedPolicies = params.policies
    .slice()
    .sort((a, b) => policyPriority(b) - policyPriority(a) || safeTime(b.updatedAt) - safeTime(a.updatedAt));

  const pairs: Record<string, FreqtradeRadarScope> = {};
  let ignoredNeutral = 0;
  let ignoredExpired = 0;
  let ignoredUnmonitored = 0;

  for (const policy of sortedPolicies) {
    const symbol = normalizeSymbol(policy.symbol);
    const pair = monitoredPairs.get(symbol);
    if (!pair) {
      ignoredUnmonitored += 1;
      continue;
    }
    if (pairs[pair]) continue;
    if (isExpired(policy, safeNowMs)) {
      ignoredExpired += 1;
      continue;
    }
    if (isMissingEvidenceNeutral(policy)) {
      ignoredNeutral += 1;
      continue;
    }

    const mode = modeFromPolicy(policy);
    const riskMultiplier = mode === 'off' ? 0 : clamp(policy.riskMultiplier, 0, 1);
    pairs[pair] = {
      mode,
      risk_multiplier: Number(riskMultiplier.toFixed(2)),
      lock_new_entries: mode === 'off' || policy.lockNewEntries,
      reason: reasonFromPolicy(policy),
      reason_codes: [...policy.reasonCodes],
      narrative_regime: policy.narrativeRegime,
      priority_score: Number(clamp(policy.priorityScore, 0, 100).toFixed(2)),
      evidence_ids: [...policy.evidenceIds],
      signal_candidate_id: policy.signalCandidateId,
      source_policy_id: policy.id,
    };
  }

  const activePairOverrides = Object.keys(pairs).length;
  return {
    schema_version: 1,
    source: 'coinmaster-alpha-radar',
    generated_by: 'coinmaster-freqtrade-radar-producer',
    updated_at: params.nowIso,
    valid_until: validUntil,
    global: {
      enabled: true,
      mode: 'both',
      risk_multiplier: 1,
      lock_new_entries: false,
      reason: activePairOverrides > 0 ? 'pair_context_overrides_active' : 'neutral_no_active_radar_overrides',
    },
    pairs,
    diagnostics: {
      monitored_pairs: monitoredPairs.size,
      active_pair_overrides: activePairOverrides,
      ignored_neutral_policies: ignoredNeutral,
      ignored_expired_policies: ignoredExpired,
      ignored_unmonitored_policies: ignoredUnmonitored,
    },
  };
}
