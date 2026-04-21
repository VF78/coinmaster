/**
 * Radar read-model: scoring, verdict policy, enrichment, and summary views.
 *
 * Extracted from server/index.ts to maintain single-responsibility.
 * This module contains purely deterministic logic for:
 * - Candidate scoring (freshness, status, metadata richness, duplicates)
 * - Asset-class verdict policy (crypto vs commodity thresholds)
 * - Signal enrichment and candidate grouping
 * - Summary rollup by source/connector/kind/quality
 *
 * Does NOT contain persistence logic or ingest logic — those remain in server/index.ts.
 */

import type {
  AssetClass,
  RadarSignalRecord,
  RadarSignalStatus,
  RadarSignalVerdict,
  RadarSignalView,
} from '../shared/dto.js';
import { inferAssetClassFromSymbol } from '../shared/tradingRules.js';

// ─── Signal Scoring ──────────────────────────────────────────────────────────

function getRadarSignalSeenAt(item: RadarSignalRecord): string | undefined {
  return item.updatedAt || item.createdAt;
}

function getRadarSignalStatusWeight(status: RadarSignalStatus): number {
  if (status === 'auto_order_placed') return 40;
  if (status === 'pending_confirmation') return 30;
  if (status === 'ignored') return 10;
  return 5;
}

function getRadarSignalFreshnessScore(seenAt?: string): number {
  const seenMs = seenAt ? Date.parse(seenAt) : Number.NaN;
  if (!Number.isFinite(seenMs)) return 0;

  const ageMs = Math.max(0, Date.now() - seenMs);
  if (ageMs <= 15 * 60 * 1000) return 30;
  if (ageMs <= 60 * 60 * 1000) return 20;
  if (ageMs <= 4 * 60 * 60 * 1000) return 10;
  return 0;
}

function getRadarSignalSourceMetaRichness(item: RadarSignalRecord): number {
  const meta = item.sourceMeta;
  if (!meta) return 0;

  let count = 0;
  if (meta.connector) count += 1;
  if (meta.kind) count += 1;
  if (meta.channel) count += 1;
  if (meta.externalId) count += 1;
  if (meta.messageTs) count += 1;
  return Math.min(10, count * 2);
}

function getRadarSignalDuplicatePenalty(item: RadarSignalRecord): number {
  return item.duplicateOf || item.error === 'duplicate_signal' ? 20 : 0;
}

/**
 * Composite candidate score (0–100).
 * Higher score = better signal (fresher, richer metadata, confirmed/auto-placed).
 */
export function getRadarSignalCandidateScore(item: RadarSignalRecord): number {
  const score = getRadarSignalStatusWeight(item.status)
    + getRadarSignalFreshnessScore(getRadarSignalSeenAt(item))
    + getRadarSignalSourceMetaRichness(item)
    - getRadarSignalDuplicatePenalty(item);

  return Math.max(0, Math.min(100, score));
}

// ─── Asset-Class Verdict Policy ──────────────────────────────────────────────

/**
 * Asset-class verdict policy.
 *
 * Crypto: standard thresholds (highest risk tolerance, most signals).
 * Commodity (gold/oil): tighter — actionable requires higher conviction.
 * Everything else: falls back to crypto-like defaults.
 *
 * Thresholds are { actionable, bias, watch } minimum scores.
 */
const RADAR_VERDICT_THRESHOLDS: Record<string, { actionable: number; bias: number; watch: number }> = {
  crypto:    { actionable: 70, bias: 45, watch: 20 },
  commodity: { actionable: 80, bias: 55, watch: 30 },
};
const RADAR_VERDICT_THRESHOLDS_DEFAULT = RADAR_VERDICT_THRESHOLDS.crypto;

export function getRadarVerdictThresholds(assetClass: AssetClass) {
  return RADAR_VERDICT_THRESHOLDS[assetClass] ?? RADAR_VERDICT_THRESHOLDS_DEFAULT;
}

export function getRadarSignalVerdict(
  score: number,
  item: Pick<RadarSignalRecord, 'status' | 'duplicateOf' | 'error'>,
  assetClass: AssetClass = 'crypto',
): RadarSignalVerdict {
  if (item.duplicateOf || item.error === 'duplicate_signal') return 'ignore';
  if (item.status === 'rejected') return 'ignore';
  const t = getRadarVerdictThresholds(assetClass);
  if (item.status === 'auto_order_placed' || score >= t.actionable) return 'actionable';
  if (score >= t.bias) return 'bias';
  if (score >= t.watch) return 'watch';
  return 'ignore';
}

export function getRadarVerdictReason(
  score: number,
  verdict: RadarSignalVerdict,
  item: Pick<RadarSignalRecord, 'status' | 'duplicateOf' | 'error'>,
  assetClass: AssetClass = 'crypto',
): string {
  if (item.duplicateOf || item.error === 'duplicate_signal') return 'duplicate signal — auto-ignored';
  if (item.status === 'rejected') return 'rejected signal — auto-ignored';
  const t = getRadarVerdictThresholds(assetClass);
  const classLabel = assetClass === 'crypto' ? 'crypto' : assetClass === 'commodity' ? 'commodity' : assetClass;
  if (item.status === 'auto_order_placed') return `auto-order placed → actionable (${classLabel})`;
  if (verdict === 'actionable') return `score ${score} ≥ ${t.actionable} → actionable (${classLabel})`;
  if (verdict === 'bias') return `score ${score} ≥ ${t.bias} → bias (${classLabel})`;
  if (verdict === 'watch') return `score ${score} ≥ ${t.watch} → watch (${classLabel})`;
  return `score ${score} below ${t.watch} → ignore (${classLabel})`;
}

export function getRadarVerdictLabel(verdict: RadarSignalVerdict): string {
  if (verdict === 'actionable') return 'Actionable';
  if (verdict === 'bias') return 'Bias';
  if (verdict === 'watch') return 'Watch';
  return 'Ignore';
}

export function getRadarCandidateGroupVerdict(bestScore: number, assetClass: AssetClass = 'crypto'): RadarSignalVerdict {
  const t = getRadarVerdictThresholds(assetClass);
  if (bestScore >= t.actionable) return 'actionable';
  if (bestScore >= t.bias) return 'bias';
  if (bestScore >= t.watch) return 'watch';
  return 'ignore';
}

// ─── Signal Enrichment & View Construction ──────────────────────────────────

export function enrichRadarSignal(item: RadarSignalRecord): RadarSignalView {
  const candidateScore = getRadarSignalCandidateScore(item);
  const assetClass = inferAssetClassFromSymbol(item.symbol);
  const verdict = getRadarSignalVerdict(candidateScore, item, assetClass);
  return {
    ...item,
    candidateScore,
    verdict,
    verdictReason: getRadarVerdictReason(candidateScore, verdict, item, assetClass),
  };
}

// ─── Candidate Grouping ──────────────────────────────────────────────────────

export function buildRadarCandidateGroups(items: RadarSignalView[]) {
  const groups = new Map<string, {
    symbol: string;
    side: 'buy' | 'sell';
    bestScore: number;
    verdict: RadarSignalVerdict;
    assetClass: AssetClass;
    sources: Set<string>;
    lastSeenAt?: string;
    count: number;
  }>();

  for (const item of items) {
    const key = `${item.symbol}:${item.side}`;
    const current = groups.get(key);
    const seenAt = getRadarSignalSeenAt(item);
    const ac = inferAssetClassFromSymbol(item.symbol);

    if (current) {
      current.bestScore = Math.max(current.bestScore, item.candidateScore);
      current.verdict = getRadarCandidateGroupVerdict(current.bestScore, ac);
      current.sources.add(item.source);
      current.count += 1;
      if (seenAt && (!current.lastSeenAt || seenAt > current.lastSeenAt)) current.lastSeenAt = seenAt;
      continue;
    }

    groups.set(key, {
      symbol: item.symbol,
      side: item.side,
      bestScore: item.candidateScore,
      verdict: getRadarCandidateGroupVerdict(item.candidateScore, ac),
      assetClass: ac,
      sources: new Set([item.source]),
      lastSeenAt: seenAt,
      count: 1,
    });
  }

  return [...groups.values()]
    .sort((a, b) => b.bestScore - a.bestScore || b.count - a.count || String(b.lastSeenAt ?? '').localeCompare(String(a.lastSeenAt ?? '')))
    .slice(0, 30)
    .map(({ symbol, side, bestScore, verdict, assetClass, sources, lastSeenAt, count }) => {
      const t = getRadarVerdictThresholds(assetClass);
      const classLabel = assetClass === 'crypto' ? 'crypto' : assetClass === 'commodity' ? 'commodity' : assetClass;
      return {
        symbol,
        side,
        signalCount: count,
        bestScore,
        verdict,
        verdictLabel: getRadarVerdictLabel(verdict),
        verdictReason: `best score ${bestScore} vs ${classLabel} thresholds (a≥${t.actionable} b≥${t.bias} w≥${t.watch})`,
        sources: [...sources].sort().slice(0, 10),
        lastSeenAt,
      };
    });
}

// ─── Summary Rollup ──────────────────────────────────────────────────────────

type RadarSignalQualityAccumulator = {
  total: number;
  pendingConfirmation: number;
  autoOrderPlaced: number;
  rejected: number;
  ignored: number;
  duplicates: number;
  lastSeenAt?: string;
};

function summarizeRadarSignalMap(map: Map<string, number>, key: 'source' | 'connector' | 'kind' | 'channel') {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 20)
    .map(([value, count]) => ({ [key]: value, count }));
}

function summarizeRadarSignalQualityMap(
  map: Map<string, RadarSignalQualityAccumulator>,
  key: string,
) {
  return [...map.entries()]
    .sort((a, b) => b[1].total - a[1].total || a[0].localeCompare(b[0]))
    .slice(0, 20)
    .map(([value, stats]) => ({ [key]: value, ...stats }));
}

export function buildRadarSignalsSummary(items: RadarSignalView[]) {
  const sourceCounts = new Map<string, number>();
  const connectorCounts = new Map<string, number>();
  const kindCounts = new Map<string, number>();
  const channelCounts = new Map<string, number>();
  const sourceQuality = new Map<string, RadarSignalQualityAccumulator>();
  const connectorQuality = new Map<string, RadarSignalQualityAccumulator>();
  const assetQuality = new Map<string, RadarSignalQualityAccumulator>();
  const verdictQuality = new Map<string, RadarSignalQualityAccumulator>();
  const familyQuality = new Map<string, RadarSignalQualityAccumulator>();

  const touchQuality = (map: Map<string, RadarSignalQualityAccumulator>, value: string | undefined, item: RadarSignalRecord) => {
    const key = String(value ?? '').trim();
    if (!key) return;

    const current = map.get(key) ?? {
      total: 0,
      pendingConfirmation: 0,
      autoOrderPlaced: 0,
      rejected: 0,
      ignored: 0,
      duplicates: 0,
      lastSeenAt: undefined,
    };

    current.total += 1;
    if (item.status === 'pending_confirmation') current.pendingConfirmation += 1;
    if (item.status === 'auto_order_placed') current.autoOrderPlaced += 1;
    if (item.status === 'rejected') current.rejected += 1;
    if (item.status === 'ignored') current.ignored += 1;
    if (item.duplicateOf || item.error === 'duplicate_signal') current.duplicates += 1;

    const seenAt = getRadarSignalSeenAt(item);
    if (seenAt && (!current.lastSeenAt || seenAt > current.lastSeenAt)) {
      current.lastSeenAt = seenAt;
    }

    map.set(key, current);
  };

  for (const item of items) {
    sourceCounts.set(item.source, (sourceCounts.get(item.source) ?? 0) + 1);
    if (item.sourceMeta?.connector) connectorCounts.set(item.sourceMeta.connector, (connectorCounts.get(item.sourceMeta.connector) ?? 0) + 1);
    if (item.sourceMeta?.kind) kindCounts.set(item.sourceMeta.kind, (kindCounts.get(item.sourceMeta.kind) ?? 0) + 1);
    if (item.sourceMeta?.channel) channelCounts.set(item.sourceMeta.channel, (channelCounts.get(item.sourceMeta.channel) ?? 0) + 1);

    touchQuality(sourceQuality, item.source, item);
    touchQuality(connectorQuality, item.sourceMeta?.connector, item);
    touchQuality(assetQuality, inferAssetClassFromSymbol(item.symbol), item);
    touchQuality(verdictQuality, item.verdict, item);
    touchQuality(familyQuality, item.sourceMeta?.kind, item);
  }

  return {
    total: items.length,
    pendingConfirmation: items.filter((item) => item.status === 'pending_confirmation').length,
    autoOrderPlaced: items.filter((item) => item.status === 'auto_order_placed').length,
    rejected: items.filter((item) => item.status === 'rejected').length,
    ignored: items.filter((item) => item.status === 'ignored').length,
    bySource: summarizeRadarSignalMap(sourceCounts, 'source'),
    byConnector: summarizeRadarSignalMap(connectorCounts, 'connector'),
    byKind: summarizeRadarSignalMap(kindCounts, 'kind'),
    byChannel: summarizeRadarSignalMap(channelCounts, 'channel'),
    qualityBySource: summarizeRadarSignalQualityMap(sourceQuality, 'source'),
    qualityByConnector: summarizeRadarSignalQualityMap(connectorQuality, 'connector'),
    qualityByAsset: summarizeRadarSignalQualityMap(assetQuality, 'asset'),
    qualityByVerdict: summarizeRadarSignalQualityMap(verdictQuality, 'verdict'),
    qualityByFamily: summarizeRadarSignalQualityMap(familyQuality, 'family'),
    candidateGroups: buildRadarCandidateGroups(items),
  };
}
