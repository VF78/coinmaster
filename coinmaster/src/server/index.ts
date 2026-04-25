import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { nanoid } from 'nanoid';
import logger from '../lib/logger.js';
import { getDb } from '../core/db.js';
import { runDeterministicReplay } from '../core/replay.js';
import { applyBacktestAiAnalysisResult, createQueuedBacktestRun, markBacktestAiAnalysisRequested } from '../core/backtest.js';
import { createQueuedOptimization } from '../core/optimizerWorker.js';
import { markComputeJobFailed, reconcileComputeJob } from '../core/computeJob.js';
import { createExperimentFromRun, ensureExperimentCollections, evaluateChampionAcceptance, promoteChampionTrial } from '../core/experimentGovernance.js';
import { submitBias } from '../core/services.js';
import { runSimulationStep } from '../core/simulation.js';
import { appendTradeEvent } from '../core/tradeEvents.js';
import { Bias, DailyDDBaseline, RiskGateAuditEntry } from '../core/types.js';
import type {
  AiMasterInsight,
  AiMasterQaItem,
  AiMasterSnapshotResponse,
  AlphaRadarActivityEvent,
  AlphaRadarCollectorRuntime,
  AlphaRadarConnectorSettings,
  AlphaRadarConnectorRuntimeSummary,
  AlphaRadarConnectorType,
  AlphaRadarIdea,
  AlphaRadarLiveResponse,
  AlphaRadarMonitoringWatchAsset,
  AlphaRadarObservation,
  AlphaRadarSettings,
  AlphaRadarSnapshotResponse,
  AlphaRadarSourceHealth,
  AssetClass,
  BacktestCreateRunRequest,
  BacktestRun,
  ChampionConfig,
  Experiment,
  ExperimentTrial,
  EvidenceBundle,
  OptimizationCreateRequest,
  OptimizationParamRange,
  BiasMode,
  ExchangeConnectionSettingsPayload,
  ExecutionIntent,
  LiveDashboardState,
  LivePosition,
  MarketTick,
  PendingConfirmation,
  RadarContextPolicy,
  RadarContextPolicyReasonCode,
  RadarSignalIngestPayload,
  RadarRuntimeSettings,
  RadarRuntimeSettingsResponse,
  RadarSignalQualityBucket,
  RadarSignalRecord,
  RadarSignalStatus,
  RadarSignalVerdict,
  RadarSignalView,
  SignalCandidate,
  SignalStrategy,
  TelegramOutboxItem,
  TradeEvent,
  TradeSide,
  TradingRulesSettings,
  TradingRulesTimeframe
} from '../shared/dto.js';
import { inferAssetClassFromSymbol, normalizeTradingRules, getMonitoredSymbols, isSymbolMonitored } from '../shared/tradingRules.js';
import { normalizeRadarRuntimeSettings } from '../shared/radarRuntime.js';
import {
  DEFAULT_ALPHA_RADAR_SETTINGS,
  applyAlphaRadarMonitoringFreshnessPolicy,
  applyConnectedIdleSourceHealthPolicy,
  buildAlphaRadarSourceHealth as buildSharedAlphaRadarSourceHealth,
  buildIdeaCandidates,
  buildMarketObservationCandidates,
  buildAlphaRadarMarketObservationDedupeKey,
  buildAlphaRadarObservation,
  enabledAlphaRadarMonitoringWatchlist,
  extractGdeltItems,
  extractJsonFeedItems,
  extractRssItems,
  extractRssItemsWithProvenance,
  normalizeAlphaRadarSettings,
  pruneAlphaRadarObservations,
} from './alphaRadar.js';
import { alphaRadarFetchJson, alphaRadarFetchJsonWithMeta, alphaRadarFetchText, alphaRadarFetchTextWithMeta, mapWithConcurrency, summarizeAlphaRadarFetchFailure } from './alphaRadarHttp.js';
import { buildAlphaRadarConnectorHealth, summarizeAlphaRadarConnectorRuntimes } from './alphaRadarConnectors.js';
import { collectBlueskyConnector, collectRedditConnector, collectTelegramAuthReadyConnector } from './alphaRadarSocial.js';
import { ingestObservationIntoEvidence, pruneEvidenceBundles, syncSignalCandidatesFromEvidence } from './alphaRadarEvidence.js';
import { buildRadarContextPolicyBook, evaluateRadarContextPolicyEntry, readActiveRadarContextPolicy } from './radarContextPolicy.js';
import { RuntimeRulesCache, isSymbolEnabled, maxNotionalForSymbol, computeAllocationSize, maxPortfolioGrossNotional, wouldExceedPortfolioGrossCap } from './runtimeRules.js';
import type { AllocationSizingResult, AllocationSizingOutcome } from './runtimeRules.js';
import { HyperliquidAdapter, MidStreamHandle } from '../exchange/index.js';
import type { Candle, CandleTimeframe, FillEvent, OrderIntent, OrderSnapshot, PositionSnapshot, TradingErrorCode } from '../exchange/types.js';
import { buildLiveDashboardState, getOrderClientOrderId, getSystemManagedProtectiveOrderMeta, toLiveFill } from './liveSnapshot.js';
import { applyAiMasterQaAnswer, buildAiMasterInsight, buildAiMasterQaQuestion, pruneAiMasterCollections } from './aiMaster.js';
import { evaluateMultiTf, evaluateTimeframe } from '../core/engulfingEvaluator.js';
import { evaluateFvg, type FvgTimeframe } from '../core/fvgEvaluator.js';
import { evaluateSignalQuality, type SignalQualityVerdict } from '../core/signalQualityContext.js';
import {
  applyBybitConnectionPatch,
  collectExternalFills,
  getBybitConnectionSettings,
  getMaskedBybitConnectionSettings,
  getExchangeConnectionStatuses,
  testReadOnlyExchangeConnection,
} from '../integrations/readOnlyExchanges/service.js';
import { enrichRadarSignal, buildRadarSignalsSummary } from './radarReadModel.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../');
const distDir = path.join(rootDir, 'dist');
const dbFilePath = process.env.COINMASTER_DB_FILE ?? 'data/db.json';
const alertStateFilePath = path.join(path.dirname(dbFilePath), 'alert_state.json');

if (!existsSync(path.join(distDir, 'index.html'))) {
  throw new Error(`dist/index.html missing at ${distDir}; run build/deploy before starting production server`);
}

const app = express();
const port = Number(process.env.PORT || 8787);
const host = process.env.HOST || '0.0.0.0';

const LIVE_SYMBOL = 'BTC';
const REST_FALLBACK_MS = 60 * 1000; // at least 1m updates if WS unavailable

const LIVE_TICK_STALE_MS = Math.max(5000, Number(process.env.LIVE_TICK_STALE_MS || 120000));

const ENABLE_PAPER_ENGINE = String(process.env.ENABLE_PAPER_ENGINE ?? 'false').toLowerCase() === 'true';
const ENABLE_SIMULATION_API = String(process.env.ENABLE_SIMULATION_API ?? 'false').toLowerCase() === 'true';
const ENABLE_REPLAY_API = String(process.env.ENABLE_REPLAY_API ?? 'false').toLowerCase() === 'true';

const ENABLE_MULTI_TF_ENGULFING = String(process.env.ENABLE_MULTI_TF_ENGULFING ?? 'false').toLowerCase() === 'true';
const ENABLE_FVG_MONITOR = String(process.env.ENABLE_FVG_MONITOR ?? 'false').toLowerCase() === 'true';
const FVG_MONITOR_INTERVAL_MS = Math.max(60_000, Number(process.env.FVG_MONITOR_INTERVAL_MS || 300_000)); // default 5m
const ENABLE_DRAWDOWN_WATCHDOG = String(process.env.ENABLE_DRAWDOWN_WATCHDOG ?? 'true').toLowerCase() !== 'false';
const DRAWDOWN_WATCHDOG_INTERVAL_MS = Math.max(5000, Number(process.env.DRAWDOWN_WATCHDOG_INTERVAL_MS || 5000));

/**
 * Stagger first-tick warmups of the monitor loops so their initial
 * Hyperliquid `info` reads do not collide in the same event-loop turn.
 * The in-adapter request coordinator dedupes concurrent identical reads,
 * but spreading the warmups still reduces peak upstream pressure and
 * gives the read-cache (universe, dex discovery) a chance to warm.
 */
const MONITOR_STARTUP_STAGGER_MS = Math.max(0, Number(process.env.MONITOR_STARTUP_STAGGER_MS || 750));
const DAILY_ANALYTICS_TZ = process.env.DAILY_ANALYTICS_TZ || 'Europe/Madrid';
const DAILY_ANALYTICS_HOUR = Math.min(23, Math.max(0, Number(process.env.DAILY_ANALYTICS_HOUR || 23)));
const DAILY_ANALYTICS_MINUTE = Math.min(59, Math.max(0, Number(process.env.DAILY_ANALYTICS_MINUTE || 5)));
const DAILY_ANALYTICS_TICK_MS = Math.max(60_000, Number(process.env.DAILY_ANALYTICS_TICK_MS || 10 * 60_000));
const TRADABLE_SYMBOLS_CACHE_MS = Math.max(30_000, Number(process.env.TRADABLE_SYMBOLS_CACHE_MS || 5 * 60_000));
const OWNER_AUTH_TOKEN = process.env.OWNER_AUTH_TOKEN || '';
const OWNER_HMAC_SECRET = process.env.OWNER_HMAC_SECRET || '';

const PENDING_CONFIRMATION_TTL_MS = Math.max(5 * 60_000, Number(process.env.PENDING_CONFIRMATION_TTL_MS || 6 * 60 * 60_000)); // default 6h
const TELEGRAM_OUTBOX_RETRY_BASE_MS = Math.max(2000, Number(process.env.TELEGRAM_OUTBOX_RETRY_BASE_MS || 10_000));
const TELEGRAM_OUTBOX_RETRY_MAX_MS = Math.max(30_000, Number(process.env.TELEGRAM_OUTBOX_RETRY_MAX_MS || 15 * 60_000));
const TELEGRAM_OUTBOX_MAX_ATTEMPTS = Math.max(3, Number(process.env.TELEGRAM_OUTBOX_MAX_ATTEMPTS || 12));
const TELEGRAM_OUTBOX_SENT_RETENTION_MS = 24 * 60 * 60_000;
const TELEGRAM_OUTBOX_FAILED_RETENTION_MS = 7 * 24 * 60 * 60_000;
const BACKTEST_RUN_HISTORY_LIMIT = Math.max(20, Number(process.env.BACKTEST_RUN_HISTORY_LIMIT || 200));
const ALPHA_RADAR_COLLECTOR_MIN_INTERVAL_MS = 15_000;
const ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS = Math.max(ALPHA_RADAR_COLLECTOR_MIN_INTERVAL_MS, Number(process.env.ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS || 30_000));
const ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS = Math.max(ALPHA_RADAR_COLLECTOR_MIN_INTERVAL_MS, Number(process.env.ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS || 15_000));
const ALPHA_RADAR_EXTERNAL_FEED_CONCURRENCY = Math.max(1, Number(process.env.ALPHA_RADAR_EXTERNAL_FEED_CONCURRENCY || 4));
const ALPHA_RADAR_MONITORING_STOOQ_CONCURRENCY = Math.max(1, Number(process.env.ALPHA_RADAR_MONITORING_STOOQ_CONCURRENCY || 4));
const ALPHA_RADAR_MARKET_MONITOR_NEAR_RT_MS = Math.max(15_000, Number(process.env.ALPHA_RADAR_MARKET_MONITOR_NEAR_RT_MS || 30_000));
const ALPHA_RADAR_MARKET_MONITOR_FALLBACK_MS = Math.max(60_000, Number(process.env.ALPHA_RADAR_MARKET_MONITOR_FALLBACK_MS || 15 * 60_000));
const ALPHA_RADAR_FEED_FAST_MS = Math.max(15_000, Number(process.env.ALPHA_RADAR_FEED_FAST_MS || 15_000));
const ALPHA_RADAR_FEED_NORMAL_MS = Math.max(60_000, Number(process.env.ALPHA_RADAR_FEED_NORMAL_MS || 3 * 60_000));
const ALPHA_RADAR_FEED_SLOW_MS = Math.max(5 * 60_000, Number(process.env.ALPHA_RADAR_FEED_SLOW_MS || 15 * 60_000));
const ALPHA_RADAR_CONNECTOR_FAST_MS = Math.max(15_000, Number(process.env.ALPHA_RADAR_CONNECTOR_FAST_MS || 20_000));
const ALPHA_RADAR_CONNECTOR_NORMAL_MS = Math.max(60_000, Number(process.env.ALPHA_RADAR_CONNECTOR_NORMAL_MS || 2 * 60_000));
const ALPHA_RADAR_ACTIVITY_LIMIT = 80;

// ─── Runtime Rules Cache (hot-reloads from DB every 5s) ──────────────
const rulesCache = new RuntimeRulesCache(5_000);
const LIVE_SNAPSHOT_CACHE_MS = Math.max(500, Number(process.env.LIVE_SNAPSHOT_CACHE_MS || 2_000));
let liveSnapshotCache: { key: string; expiresAt: number; value: LiveDashboardState } | null = null;
let liveSnapshotRefreshInFlight: Promise<LiveDashboardState> | null = null;

/** Build a fresh LIVE_MODE snapshot from current effective rules. */
function getLiveMode() {
  const r = rulesCache.getEffectiveRules();
  return { manualConfirmation: r.manualConfirmation, maxLeverage: r.maxLeverage };
}

async function getCachedExchangeLiveState(symbol: string, mode = getLiveMode()): Promise<LiveDashboardState> {
  const key = `${symbol}|${mode.manualConfirmation ? 1 : 0}|${mode.maxLeverage}`;
  const now = Date.now();
  if (liveSnapshotCache && liveSnapshotCache.key === key && liveSnapshotCache.expiresAt > now) {
    return liveSnapshotCache.value;
  }

  if (liveSnapshotCache && liveSnapshotCache.key === key) {
    void refreshLiveSnapshotState(symbol, mode).catch((err) =>
      logger.warn({ component: 'live', err }, 'background live snapshot refresh failed')
    );
    return liveSnapshotCache.value;
  }

  return refreshLiveSnapshotState(symbol, mode);
}

async function refreshLiveSnapshotState(symbol: string, mode = getLiveMode()): Promise<LiveDashboardState> {
  const key = `${symbol}|${mode.manualConfirmation ? 1 : 0}|${mode.maxLeverage}`;
  if (liveSnapshotRefreshInFlight) {
    return liveSnapshotRefreshInFlight;
  }

  const run = (async () => {
    const value = await buildLiveDashboardState(exchange, symbol, mode, []);
    liveSnapshotCache = {
      key,
      expiresAt: Date.now() + LIVE_SNAPSHOT_CACHE_MS,
      value: { ...value, pendingConfirmations: [] },
    };
    return liveSnapshotCache.value;
  })();

  liveSnapshotRefreshInFlight = run.finally(() => {
    liveSnapshotRefreshInFlight = null;
  });

  return liveSnapshotRefreshInFlight;
}

function compactBacktestRuns(items: BacktestRun[]): BacktestRun[] {
  return [...items]
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
    .slice(0, BACKTEST_RUN_HISTORY_LIMIT);
}

const RADAR_SIGNAL_HISTORY_LIMIT = 500;
const RADAR_SIGNAL_DEDUP_MS = 5 * 60 * 1000;

function compactRadarSignals(items: RadarSignalRecord[]): RadarSignalRecord[] {
  return [...items]
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, RADAR_SIGNAL_HISTORY_LIMIT);
}

function normalizeRadarSourceMeta(raw: Partial<RadarSignalIngestPayload>['sourceMeta']): RadarSignalRecord['sourceMeta'] | undefined {
  if (!raw || typeof raw !== 'object') return undefined;

  const connector = String(raw.connector ?? '').trim().toLowerCase().slice(0, 40);
  const kind = String(raw.kind ?? '').trim().toLowerCase().slice(0, 40);
  const channel = String(raw.channel ?? '').trim().toLowerCase().slice(0, 80);
  const externalId = String(raw.externalId ?? '').trim().slice(0, 160);
  const messageTs = String(raw.messageTs ?? '').trim().slice(0, 64);

  const meta: RadarSignalRecord['sourceMeta'] = {};
  if (connector) meta.connector = connector;
  if (kind) meta.kind = kind;
  if (channel) meta.channel = channel;
  if (externalId) meta.externalId = externalId;
  if (messageTs) meta.messageTs = messageTs;

  return Object.keys(meta).length > 0 ? meta : undefined;
}

function buildRadarSourceLabel(source: string, meta?: RadarSignalRecord['sourceMeta']): string {
  const base = source.trim().slice(0, 80);
  if (base) return base;

  const parts = [meta?.connector, meta?.kind, meta?.channel]
    .map((value) => String(value ?? '').trim())
    .filter(Boolean);

  return parts.length > 0 ? parts.join(':').slice(0, 80) : '';
}

function buildRadarSignalDedupeKey(params: {
  symbol: string;
  side: 'buy' | 'sell';
  timeframe: TradingRulesTimeframe;
  source: string;
  reason: string;
  sourceMeta?: RadarSignalRecord['sourceMeta'];
}): string | undefined {
  const connector = params.sourceMeta?.connector?.trim().toLowerCase();
  const kind = params.sourceMeta?.kind?.trim().toLowerCase();
  const channel = params.sourceMeta?.channel?.trim().toLowerCase();
  const externalId = params.sourceMeta?.externalId?.trim();
  const messageTs = params.sourceMeta?.messageTs?.trim();

  if (connector && kind && channel && externalId) {
    return [
      connector,
      kind,
      channel,
      externalId,
      messageTs || 'na',
      params.symbol,
      params.side,
      params.timeframe,
    ].join('|');
  }

  return undefined;
}

function ensureRadarSignalsState(db: Awaited<ReturnType<typeof getDb>>): RadarSignalRecord[] {
  db.data.radarSignals = Array.isArray(db.data.radarSignals) ? compactRadarSignals(db.data.radarSignals) : [];
  return db.data.radarSignals;
}

function reconcileRadarSignalOutcome(
  db: Awaited<ReturnType<typeof getDb>>,
  params: {
    pendingId?: string;
    orderId?: string;
    status: RadarSignalStatus;
    error?: string;
  }
): void {
  const pendingId = String(params.pendingId ?? '').trim();
  const orderId = String(params.orderId ?? '').trim();
  if (!pendingId && !orderId) return;

  const signals = ensureRadarSignalsState(db);
  const updatedAt = new Date().toISOString();
  let changed = false;

  db.data.radarSignals = compactRadarSignals(signals.map((item) => {
    const matchesPendingId = !!pendingId && item.pendingId === pendingId;
    const matchesOrderId = !!orderId && item.orderId === orderId;
    if (!matchesPendingId && !matchesOrderId) return item;

    changed = true;
    return {
      ...item,
      status: params.status,
      updatedAt,
      orderId: orderId || item.orderId,
      error: params.error,
    };
  }));

  if (!changed) {
    db.data.radarSignals = signals;
  }
}

type RadarSignalFilters = {
  status?: RadarSignalStatus;
  symbol?: string;
  connector?: string;
  kind?: string;
  channel?: string;
  source?: string;
};

function isRadarSignalStatus(value: unknown): value is RadarSignalStatus {
  return value === 'pending_confirmation' || value === 'auto_order_placed' || value === 'rejected' || value === 'ignored';
}

function normalizeRadarQueryValue(raw: unknown, maxLength: number, transform: 'lower' | 'upper' = 'lower'): string | undefined {
  const value = String(raw ?? '').trim().slice(0, maxLength);
  if (!value) return undefined;
  return transform === 'upper' ? value.toUpperCase() : value.toLowerCase();
}

function parseRadarSignalFilters(query: Request['query']): RadarSignalFilters {
  const statusRaw = normalizeRadarQueryValue(query.status, 32);

  return {
    status: isRadarSignalStatus(statusRaw) ? statusRaw : undefined,
    symbol: normalizeRadarQueryValue(query.symbol, 32, 'upper'),
    connector: normalizeRadarQueryValue(query.connector, 40),
    kind: normalizeRadarQueryValue(query.kind, 40),
    channel: normalizeRadarQueryValue(query.channel, 80),
    source: normalizeRadarQueryValue(query.source, 80),
  };
}

function matchesRadarSignalFilters(item: RadarSignalRecord, filters: RadarSignalFilters): boolean {
  if (filters.status && item.status !== filters.status) return false;
  if (filters.symbol && item.symbol.trim().toUpperCase() !== filters.symbol) return false;
  if (filters.connector && item.sourceMeta?.connector?.trim().toLowerCase() !== filters.connector) return false;
  if (filters.kind && item.sourceMeta?.kind?.trim().toLowerCase() !== filters.kind) return false;
  if (filters.channel && item.sourceMeta?.channel?.trim().toLowerCase() !== filters.channel) return false;
  if (filters.source && item.source.trim().toLowerCase() !== filters.source) return false;
  return true;
}

function summarizeRadarSignalMap(map: Map<string, number>, key: 'source' | 'connector' | 'kind' | 'channel') {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 20)
    .map(([value, count]) => ({ [key]: value, count }));
}

type RadarSignalQualityAccumulator = {
  total: number;
  pendingConfirmation: number;
  autoOrderPlaced: number;
  rejected: number;
  ignored: number;
  duplicates: number;
  lastSeenAt?: string;
};

function summarizeRadarSignalQualityMap(
  map: Map<string, RadarSignalQualityAccumulator>,
  key: string,
) {
  return [...map.entries()]
    .sort((a, b) => b[1].total - a[1].total || a[0].localeCompare(b[0]))
    .slice(0, 20)
    .map(([value, stats]) => ({ [key]: value, ...stats }));
}

function formatPendingTriggerLabel(strategy: SignalStrategy, timeframe: TradingRulesTimeframe): string {
  if (strategy === 'engulfing') return `${timeframe.toUpperCase()} Engulfing`;
  if (strategy === 'fvg') return `${timeframe.toUpperCase()} FVG`;
  return `${timeframe.toUpperCase()} Radar`;
}

function isTradingRulesTimeframe(value: unknown): value is TradingRulesTimeframe {
  return value === '5m' || value === '15m' || value === '1h' || value === '4h';
}

function normalizeRadarRuntimeFromSettings(settings: { radarRuntime?: unknown; tradingRules: TradingRulesSettings }): RadarRuntimeSettings {
  return normalizeRadarRuntimeSettings(settings.radarRuntime, normalizeTradingRules(settings.tradingRules).autoConfirm);
}

let alphaRadarMarketTimer: ReturnType<typeof setInterval> | null = null;
let alphaRadarExternalTimer: ReturnType<typeof setInterval> | null = null;

const alphaRadarCollectors: Record<'market' | 'external', AlphaRadarCollectorRuntime> = {
  market: {
    plane: 'market',
    label: 'Market snapshot',
    intervalMs: ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS,
    enabled: true,
    busy: false,
  },
  external: {
    plane: 'external',
    label: 'External feeds',
    intervalMs: ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS,
    enabled: true,
    busy: false,
  },
};

let alphaRadarActivityEvents: AlphaRadarActivityEvent[] = [];

type AlphaRadarSourceRuntimeState = {
  lastAttemptedAt?: string;
  lastSucceededAt?: string;
  lastStatus?: 'ok' | 'error';
  lastMessage?: string;
};

const alphaRadarSourceRuntime = new Map<string, AlphaRadarSourceRuntimeState>();

function ensureAlphaRadarSettings(input: unknown): AlphaRadarSettings {
  return normalizeAlphaRadarSettings(input ?? DEFAULT_ALPHA_RADAR_SETTINGS);
}

function getAlphaRadarConnectors(settings: AlphaRadarSettings): Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings> {
  return (settings.connectors ?? DEFAULT_ALPHA_RADAR_SETTINGS.connectors ?? {}) as Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings>;
}

function ensureAlphaRadarObservationsState(db: Awaited<ReturnType<typeof getDb>>): AlphaRadarObservation[] {
  db.data.alphaRadarObservations = Array.isArray(db.data.alphaRadarObservations) ? db.data.alphaRadarObservations : [];
  pruneAlphaRadarObservations(db.data.alphaRadarObservations);
  return db.data.alphaRadarObservations;
}

function ensureEvidenceBundlesState(db: Awaited<ReturnType<typeof getDb>>): EvidenceBundle[] {
  db.data.evidenceBundles = Array.isArray(db.data.evidenceBundles) ? db.data.evidenceBundles : [];
  return db.data.evidenceBundles;
}

function ensureSignalCandidatesState(db: Awaited<ReturnType<typeof getDb>>): SignalCandidate[] {
  db.data.signalCandidates = Array.isArray(db.data.signalCandidates) ? db.data.signalCandidates : [];
  return db.data.signalCandidates;
}

function ensureRadarContextPoliciesState(db: Awaited<ReturnType<typeof getDb>>): RadarContextPolicy[] {
  db.data.radarContextPolicies = Array.isArray(db.data.radarContextPolicies) ? db.data.radarContextPolicies : [];
  return db.data.radarContextPolicies;
}

function ensureExecutionIntentsState(db: Awaited<ReturnType<typeof getDb>>): ExecutionIntent[] {
  db.data.executionIntents = Array.isArray(db.data.executionIntents) ? db.data.executionIntents : [];
  return db.data.executionIntents;
}

function ensureExperimentsState(db: Awaited<ReturnType<typeof getDb>>): Experiment[] {
  ensureExperimentCollections(db.data);
  return db.data.experiments;
}

function ensureExperimentTrialsState(db: Awaited<ReturnType<typeof getDb>>): ExperimentTrial[] {
  ensureExperimentCollections(db.data);
  return db.data.experimentTrials;
}

function ensureChampionConfigsState(db: Awaited<ReturnType<typeof getDb>>): ChampionConfig[] {
  ensureExperimentCollections(db.data);
  return db.data.championConfigs;
}

function syncRadarContextPolicies(params: {
  db: Awaited<ReturnType<typeof getDb>>;
  nowIso: string;
}): RadarContextPolicy[] {
  const rules = normalizeTradingRules(params.db.data.settings.tradingRules);
  const policies = buildRadarContextPolicyBook({
    bundles: ensureEvidenceBundlesState(params.db),
    candidates: ensureSignalCandidatesState(params.db),
    monitoredCoins: rules.coins,
    nowIso: params.nowIso,
    eventLockoutMinutes: rules.eventLockoutMinutes,
  });
  params.db.data.radarContextPolicies = policies;
  return policies;
}

function appendExecutionIntent(
  db: Awaited<ReturnType<typeof getDb>>,
  input: Omit<ExecutionIntent, 'id' | 'createdAt' | 'updatedAt'>,
): ExecutionIntent {
  const nowIso = new Date().toISOString();
  const next: ExecutionIntent = {
    ...input,
    id: `intent-${nanoid(10)}`,
    createdAt: nowIso,
    updatedAt: nowIso,
  };
  const intents = ensureExecutionIntentsState(db);
  intents.unshift(next);
  db.data.executionIntents = intents.slice(0, 1000);
  return next;
}

function updateExecutionIntent(
  db: Awaited<ReturnType<typeof getDb>>,
  intentId: string | undefined,
  patch: Partial<ExecutionIntent>,
): void {
  if (!intentId) return;
  const intents = ensureExecutionIntentsState(db);
  db.data.executionIntents = intents.map((item) => (
    item.id === intentId
      ? { ...item, ...patch, updatedAt: new Date().toISOString() }
      : item
  ));
}

async function getAlphaRadarSettingsState(): Promise<AlphaRadarSettings> {
  const db = await getDb();
  const settings = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
  if (JSON.stringify(db.data.settings.alphaRadar ?? null) !== JSON.stringify(settings)) {
    db.data.settings.alphaRadar = settings;
    await db.write();
  }
  return settings;
}

function alphaRadarObservationComparator(sort: 'recent' | 'rank') {
  if (sort === 'recent') {
    return (a: AlphaRadarObservation, b: AlphaRadarObservation) =>
      Date.parse(b.observedAt) - Date.parse(a.observedAt) || b.rank - a.rank;
  }
  return (a: AlphaRadarObservation, b: AlphaRadarObservation) =>
    b.rank - a.rank || Date.parse(b.observedAt) - Date.parse(a.observedAt);
}

function alphaRadarObservationCutoffIso(settings: AlphaRadarSettings, nowIso: string): string {
  return new Date(Date.parse(nowIso) - Math.max(1, settings.collectorLookbackHours) * 60 * 60_000).toISOString();
}

function alphaRadarObservationMatchesCurrentSources(settings: AlphaRadarSettings, observation: AlphaRadarObservation): boolean {
  const monitoringSources = new Set(enabledAlphaRadarMonitoringWatchlist(settings).map((item) => alphaRadarMonitoringSourceId(item)));
  const feedSources = new Set(settings.feeds.filter((item) => item.enabled).map((item) => item.source));
  const connectors = getAlphaRadarConnectors(settings);
  const metadata = observation.metadata && typeof observation.metadata === 'object'
    ? observation.metadata as Record<string, unknown>
    : {};
  const connectorType = String(metadata.connectorType ?? '').trim().toLowerCase();

  if (observation.source === 'coinmaster_market_ticks') return true;
  if (monitoringSources.has(observation.source)) return true;
  if (feedSources.has(observation.source)) return true;
  if (connectorType === 'telegram') return connectors.telegram?.enabled === true;
  if (connectorType === 'reddit') return connectors.reddit?.enabled === true;
  if (connectorType === 'bluesky') return connectors.bluesky?.enabled === true;
  if (observation.source.startsWith('social_telegram:')) return connectors.telegram?.enabled === true;
  if (observation.source === 'social_reddit') return connectors.reddit?.enabled === true;
  if (observation.source === 'social_bluesky') return connectors.bluesky?.enabled === true;
  return false;
}

function currentAlphaRadarObservations(settings: AlphaRadarSettings, observations: AlphaRadarObservation[], nowIso: string): AlphaRadarObservation[] {
  const cutoffIso = alphaRadarObservationCutoffIso(settings, nowIso);
  return observations.filter((item) => item.observedAt >= cutoffIso && alphaRadarObservationMatchesCurrentSources(settings, item));
}

function recordAlphaRadarActivity(input: Omit<AlphaRadarActivityEvent, 'id' | 'createdAt'>) {
  const createdAt = new Date().toISOString();
  alphaRadarActivityEvents = [
    {
      id: `alpha-radar-evt-${nanoid(10)}`,
      createdAt,
      ...input,
    },
    ...alphaRadarActivityEvents,
  ].slice(0, ALPHA_RADAR_ACTIVITY_LIMIT);
}

function updateAlphaRadarSourceRuntime(source: string, patch: Partial<AlphaRadarSourceRuntimeState>) {
  const key = String(source ?? '').trim();
  if (!key) return;
  alphaRadarSourceRuntime.set(key, {
    ...(alphaRadarSourceRuntime.get(key) ?? {}),
    ...patch,
  });
}

function alphaRadarSourceRuntimeLastTouchMs(source: string, fallbackIso?: string): number | null {
  const runtime = alphaRadarSourceRuntime.get(source);
  const candidate = runtime?.lastAttemptedAt ?? runtime?.lastSucceededAt ?? fallbackIso;
  const parsed = candidate ? Date.parse(candidate) : NaN;
  return Number.isFinite(parsed) ? parsed : null;
}

function alphaRadarSourceDue(source: string, cadenceMs: number, nowMs: number, fallbackIso?: string): boolean {
  const lastTouchMs = alphaRadarSourceRuntimeLastTouchMs(source, fallbackIso);
  if (!Number.isFinite(lastTouchMs ?? NaN)) return true;
  return nowMs - (lastTouchMs ?? 0) >= cadenceMs;
}

function alphaRadarLatestObservationBySource(observations: AlphaRadarObservation[]): Map<string, string> {
  const latest = new Map<string, string>();
  for (const observation of observations) {
    const source = String(observation.source ?? '').trim();
    const observedAt = String(observation.observedAt ?? '').trim();
    if (!source || !observedAt) continue;
    const current = latest.get(source);
    if (!current || Date.parse(observedAt) > Date.parse(current)) {
      latest.set(source, observedAt);
    }
  }
  return latest;
}

function alphaRadarMonitoringCadenceMs(asset: AlphaRadarMonitoringWatchAsset): number {
  return asset.realtimeSymbol ? ALPHA_RADAR_MARKET_MONITOR_NEAR_RT_MS : ALPHA_RADAR_MARKET_MONITOR_FALLBACK_MS;
}

function alphaRadarFeedCadenceMs(feed: AlphaRadarSettings['feeds'][number]): number {
  if (feed.id === 'tree-news') return ALPHA_RADAR_FEED_FAST_MS;
  if (feed.parser === 'binance_cms_articles' || feed.parser === 'statuspage_incidents' || feed.parser === 'statuspage_maintenances') {
    return 60_000;
  }
  if (feed.sourceClass === 'official') return ALPHA_RADAR_FEED_SLOW_MS;
  if (feed.collectorType === 'json') return 60_000;
  if (feed.collectorType === 'rss' || feed.collectorType === 'rsshub') return ALPHA_RADAR_FEED_NORMAL_MS;
  return ALPHA_RADAR_FEED_SLOW_MS;
}

function alphaRadarConnectorCadenceMs(type: AlphaRadarConnectorType): number {
  if (type === 'reddit') return ALPHA_RADAR_CONNECTOR_NORMAL_MS;
  return ALPHA_RADAR_CONNECTOR_FAST_MS;
}

function alphaRadarMonitoringSourceId(asset: Pick<AlphaRadarMonitoringWatchAsset, 'id'>): string {
  return `stooq_hourly_${String(asset.id ?? '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_')}`;
}

type AlphaRadarMonitoringQuoteMode = 'near_realtime' | 'hourly';

type AlphaRadarRealtimeBatchQuote = {
  provider: 'yahoo_spark';
  providerSymbol: string;
  price: number;
  timestamp: string;
  providerBarKey: string;
  timeframe: '1m';
};

function alphaRadarMonitoringSourceLabel(asset: Pick<AlphaRadarMonitoringWatchAsset, 'label' | 'monitoringGroup'>, mode: AlphaRadarMonitoringQuoteMode): string {
  const scope = asset.monitoringGroup === 'equity'
    ? 'equity'
    : asset.monitoringGroup === 'proxy'
      ? 'proxy'
      : 'macro';
  return `${asset.label} ${mode === 'near_realtime' ? 'near-real-time' : 'hourly'} ${scope} monitor`;
}

async function fetchAlphaRadarRealtimeBatchQuotes(watchlist: AlphaRadarMonitoringWatchAsset[]): Promise<Map<string, AlphaRadarRealtimeBatchQuote>> {
  const realtimeAssets = watchlist.filter((asset) => typeof asset.realtimeSymbol === 'string' && asset.realtimeSymbol.trim().length > 0);
  if (realtimeAssets.length === 0) return new Map();

  const requestedSymbols = [...new Set(realtimeAssets.map((asset) => String(asset.realtimeSymbol).trim().toUpperCase()).filter(Boolean))];
  if (requestedSymbols.length === 0) return new Map();

  const payload = await alphaRadarFetchJson<Record<string, {
    symbol?: string;
    timestamp?: unknown[];
    close?: unknown[];
  }>>(
    `https://query1.finance.yahoo.com/v8/finance/spark?symbols=${encodeURIComponent(requestedSymbols.join(','))}&range=1d&interval=1m`,
    {
      headers: {
        'user-agent': 'coinmaster-alpha-radar/2.2',
        accept: 'application/json',
      },
    },
  );

  const quotes = new Map<string, AlphaRadarRealtimeBatchQuote>();
  for (const asset of realtimeAssets) {
    const realtimeSymbol = String(asset.realtimeSymbol ?? '').trim().toUpperCase();
    if (!realtimeSymbol) continue;
    const row = payload[realtimeSymbol];
    if (!row || !Array.isArray(row.close) || !Array.isArray(row.timestamp)) continue;

    let lastIndex = Math.min(row.close.length, row.timestamp.length) - 1;
    while (lastIndex >= 0) {
      const close = Number(row.close[lastIndex]);
      const timestamp = Number(row.timestamp[lastIndex]);
      if (Number.isFinite(close) && close > 0 && Number.isFinite(timestamp) && timestamp > 0) {
        quotes.set(asset.id, {
          provider: 'yahoo_spark',
          providerSymbol: realtimeSymbol,
          price: close,
          timestamp: new Date(timestamp * 1000).toISOString(),
          providerBarKey: `${realtimeSymbol}:${timestamp}`,
          timeframe: '1m',
        });
        break;
      }
      lastIndex -= 1;
    }
  }

  return quotes;
}

function parseStooqHourlyClose(payload: string): { providerSymbol: string; providerDate?: string; providerTime?: string; close: number } | null {
  const line = payload
    .split(/\r?\n/)
    .map((item) => item.trim())
    .find(Boolean);
  if (!line) return null;

  const parts = line.split(',').map((item) => item.trim());
  if (parts.length < 7) return null;
  const close = Number(parts[6]);
  if (!Number.isFinite(close) || close <= 0) return null;

  return {
    providerSymbol: parts[0] ?? '',
    providerDate: parts[1] || undefined,
    providerTime: parts[2] || undefined,
    close,
  };
}

function zonedParts(date: Date, timeZone: string): { year: number; month: number; day: number; hour: number; minute: number; second: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const pick = (type: string) => Number(parts.find((item) => item.type === type)?.value ?? 0);
  return {
    year: pick('year'),
    month: pick('month'),
    day: pick('day'),
    hour: pick('hour'),
    minute: pick('minute'),
    second: pick('second'),
  };
}

function zonedLocalIso(input: { year: number; month: number; day: number; hour: number; minute: number; second: number }, timeZone: string): string {
  let guess = Date.UTC(input.year, input.month - 1, input.day, input.hour, input.minute, input.second);
  const target = Date.UTC(input.year, input.month - 1, input.day, input.hour, input.minute, input.second);
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const parts = zonedParts(new Date(guess), timeZone);
    const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
    const diff = asUtc - target;
    if (diff === 0) break;
    guess -= diff;
  }
  return new Date(guess).toISOString();
}

function parseMonitoringProviderTimestamp(asset: Pick<AlphaRadarMonitoringWatchAsset, 'monitoringGroup'>, quote: { providerDate?: string; providerTime?: string }): string | undefined {
  const providerDate = String(quote.providerDate ?? '').trim();
  const providerTime = String(quote.providerTime ?? '').trim();
  if (!/^\d{8}$/.test(providerDate) || !/^\d{4,6}$/.test(providerTime)) return undefined;
  const year = Number(providerDate.slice(0, 4));
  const month = Number(providerDate.slice(4, 6));
  const day = Number(providerDate.slice(6, 8));
  const paddedTime = providerTime.padEnd(6, '0');
  const hour = Number(paddedTime.slice(0, 2));
  const minute = Number(paddedTime.slice(2, 4));
  const second = Number(paddedTime.slice(4, 6));
  if (asset.monitoringGroup === 'equity' || asset.monitoringGroup === 'proxy') {
    return zonedLocalIso({ year, month, day, hour, minute, second }, 'America/New_York');
  }
  const utcMs = Date.UTC(year, month - 1, day, hour, minute, second);
  return Number.isFinite(utcMs) ? new Date(utcMs).toISOString() : undefined;
}

async function fetchAlphaRadarMonitoringQuote(asset: AlphaRadarMonitoringWatchAsset): Promise<{ providerSymbol: string; providerDate?: string; providerTime?: string; close: number; providerTimestamp?: string }> {
  const payload = await alphaRadarFetchText(`https://stooq.com/q/l/?s=${encodeURIComponent(asset.providerSymbol)}&i=60`, {
    headers: { 'user-agent': 'coinmaster-alpha-radar/2.2' },
  });
  const parsed = parseStooqHourlyClose(payload);
  if (!parsed) throw new Error('stooq_parse_failed');
  return {
    ...parsed,
    providerTimestamp: parseMonitoringProviderTimestamp(asset, parsed),
  };
}

async function fetchAlphaRadarMonitoringTicks(input: {
  settings: AlphaRadarSettings;
  latestObservedAtBySource?: Map<string, string>;
  trigger: 'auto' | 'manual';
}): Promise<{
  ticks: MarketTick[];
  profilesBySymbol: Record<string, {
    label: string;
    source: string;
    sourceClass: 'macro' | 'market';
    sourceWeight: number;
    topicTags: string[];
    assetTags: string[];
    timeframe: '1m' | '60m';
    monitoringOnly: true;
    sourceLabel: string;
    publisher: 'stooq' | 'yahoo_spark';
    metadata: Record<string, unknown>;
  }>;
  monitoringOnlyAssets: string[];
}> {
  const watchlist = enabledAlphaRadarMonitoringWatchlist(input.settings);
  if (watchlist.length === 0) {
    return { ticks: [], profilesBySymbol: {}, monitoringOnlyAssets: [] };
  }

  const nowMs = Date.now();
  const dueWatchlist = input.trigger === 'manual'
    ? watchlist
    : watchlist.filter((asset) => {
      const source = alphaRadarMonitoringSourceId(asset);
      return alphaRadarSourceDue(source, alphaRadarMonitoringCadenceMs(asset), nowMs, input.latestObservedAtBySource?.get(source));
    });

  if (dueWatchlist.length === 0) {
    return { ticks: [], profilesBySymbol: {}, monitoringOnlyAssets: watchlist.map((item) => normalizeSymbol(item.symbol)) };
  }

  const realtimeQuotes = await fetchAlphaRadarRealtimeBatchQuotes(dueWatchlist).catch((error) => {
    logger.warn({ component: 'alpha-radar', err: error instanceof Error ? error.message : error }, 'alpha radar realtime quote batch fetch failed');
    return new Map<string, AlphaRadarRealtimeBatchQuote>();
  });

  const results = await mapWithConcurrency(dueWatchlist, ALPHA_RADAR_MONITORING_STOOQ_CONCURRENCY, async (asset) => {
    const normalizedSymbol = normalizeSymbol(asset.symbol);
    const fetchedAt = new Date().toISOString();
    const source = alphaRadarMonitoringSourceId(asset);
    const sourceClass = asset.sourceClass === 'market' ? 'market' as const : 'macro' as const;

    const realtimeQuote = realtimeQuotes.get(asset.id);
    if (realtimeQuote) {
      updateAlphaRadarSourceRuntime(source, {
        lastAttemptedAt: fetchedAt,
        lastSucceededAt: fetchedAt,
        lastStatus: 'ok',
        lastMessage: 'monitor refreshed via yahoo_spark',
      });
      return {
        tick: {
          symbol: normalizedSymbol,
          price: realtimeQuote.price,
          timestamp: realtimeQuote.timestamp,
        } satisfies MarketTick,
        profile: {
          label: asset.label,
          source,
          sourceClass,
          sourceWeight: asset.weight ?? 1.04,
          topicTags: [...(asset.topicTags ?? [])],
          assetTags: [normalizedSymbol],
          timeframe: realtimeQuote.timeframe,
          monitoringOnly: true as const,
          sourceLabel: alphaRadarMonitoringSourceLabel(asset, 'near_realtime'),
          publisher: realtimeQuote.provider,
          metadata: {
            provider: asset.provider,
            providerSymbol: asset.providerSymbol,
            realtimeProvider: realtimeQuote.provider,
            realtimeSymbol: realtimeQuote.providerSymbol,
            providerBarKey: realtimeQuote.providerBarKey,
            monitoringMode: 'near_realtime',
            monitoringOnly: true,
            monitoringGroup: asset.monitoringGroup,
          },
        },
        monitoringOnlyAsset: normalizedSymbol,
      };
    }

    try {
      const parsed = await fetchAlphaRadarMonitoringQuote(asset);
      const providerBarKey = [parsed.providerDate, parsed.providerTime].filter(Boolean).join('T') || fetchedAt;
      updateAlphaRadarSourceRuntime(source, {
        lastAttemptedAt: fetchedAt,
        lastSucceededAt: fetchedAt,
        lastStatus: 'ok',
        lastMessage: 'monitor refreshed via stooq',
      });
      return {
        tick: {
          symbol: normalizedSymbol,
          price: parsed.close,
          timestamp: parsed.providerTimestamp ?? fetchedAt,
        } satisfies MarketTick,
        profile: {
          label: asset.label,
          source,
          sourceClass,
          sourceWeight: asset.weight ?? 1.04,
          topicTags: [...(asset.topicTags ?? [])],
          assetTags: [normalizedSymbol],
          timeframe: '60m' as const,
          monitoringOnly: true as const,
          sourceLabel: alphaRadarMonitoringSourceLabel(asset, 'hourly'),
          publisher: 'stooq' as const,
          metadata: {
            provider: asset.provider,
            providerSymbol: asset.providerSymbol,
            providerTicker: parsed.providerSymbol,
            providerDate: parsed.providerDate,
            providerTime: parsed.providerTime,
            providerTimestamp: parsed.providerTimestamp,
            providerBarKey,
            monitoringMode: 'hourly_fallback',
            monitoringOnly: true,
            monitoringGroup: asset.monitoringGroup,
          },
        },
        monitoringOnlyAsset: normalizedSymbol,
      };
    } catch (error) {
      updateAlphaRadarSourceRuntime(source, {
        lastAttemptedAt: fetchedAt,
        lastStatus: 'error',
        lastMessage: error instanceof Error ? error.message : String(error),
      });
      logger.warn({
        component: 'alpha-radar',
        symbol: normalizedSymbol,
        providerSymbol: asset.providerSymbol,
        realtimeSymbol: asset.realtimeSymbol,
        err: error instanceof Error ? error.message : error,
      }, 'alpha radar monitoring quote fetch failed');
      return {
        tick: null,
        profile: null,
        monitoringOnlyAsset: normalizedSymbol,
      };
    }
  });

  return {
    ticks: results.map((item) => item.tick).filter((item): item is MarketTick => Boolean(item)),
    profilesBySymbol: Object.fromEntries(results.filter((item) => item.profile).map((item) => [String(item.profile?.assetTags[0]), item.profile!])),
    monitoringOnlyAssets: watchlist.map((item) => normalizeSymbol(item.symbol)),
  };
}

function alphaRadarCollectorFinished(
  plane: 'market' | 'external',
  status: 'ok' | 'partial' | 'error',
  message: string,
  createdCount: number,
  errorCount = 0,
) {
  const collector = alphaRadarCollectors[plane];
  collector.busy = false;
  collector.lastCompletedAt = new Date().toISOString();
  collector.lastStatus = status;
  collector.lastMessage = message;
  collector.lastCreatedCount = createdCount;
  collector.lastErrorCount = errorCount;
  collector.nextRunAt = new Date(Date.now() + collector.intervalMs).toISOString();
}

function alphaRadarCollectorStarted(plane: 'market' | 'external') {
  const collector = alphaRadarCollectors[plane];
  collector.busy = true;
  collector.lastStartedAt = new Date().toISOString();
}

function buildAlphaRadarObservationSummary(observations: AlphaRadarObservation[], settings: AlphaRadarSettings) {
  const topAssets = new Map<string, number>();
  for (const observation of observations) {
    for (const asset of observation.assetTags) {
      topAssets.set(asset, (topAssets.get(asset) ?? 0) + 1);
    }
  }

  return {
    total: observations.length,
    external: observations.filter((item) => item.kind === 'external').length,
    market: observations.filter((item) => item.kind === 'market').length,
    topAssets: [...topAssets.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 8)
      .map(([asset, count]) => ({ asset, count })),
    monitoringOnlyAssets: enabledAlphaRadarMonitoringWatchlist(settings)
      .filter((item) => item.monitoringOnly)
      .map((item) => item.symbol),
  };
}

function buildAlphaRadarSourceHealth(settings: AlphaRadarSettings, observations: AlphaRadarObservation[]): AlphaRadarSourceHealth[] {
  const now = Date.now();
  const nowIso = new Date(now).toISOString();
  const maxIso = (...values: Array<string | undefined>) => {
    const valid = values.filter((value): value is string => typeof value === 'string' && Number.isFinite(Date.parse(value)));
    if (valid.length === 0) return undefined;
    return valid.sort((a, b) => Date.parse(b) - Date.parse(a))[0];
  };

  const monitoringExpected = enabledAlphaRadarMonitoringWatchlist(settings).map((asset) => {
    const source = alphaRadarMonitoringSourceId(asset);
    const runtime = alphaRadarSourceRuntime.get(source);
    const sourceClass = asset.sourceClass === 'market' ? 'market' as const : 'macro' as const;
    return {
      source,
      kind: 'market' as const,
      sourceType: 'market' as const,
      sourceLayer: 'primary' as const,
      sourceClass,
      sourceWeight: asset.weight ?? 1.04,
      details: {
        monitoringOnly: true,
        monitoringGroup: asset.monitoringGroup,
        monitoringMode: runtime?.lastMessage?.includes('yahoo_spark') ? 'near_realtime' : 'hourly_fallback',
        cadenceMs: alphaRadarMonitoringCadenceMs(asset),
        symbol: normalizeSymbol(asset.symbol),
        label: asset.label,
        enabled: asset.enabled !== false,
        runtimeLastAttemptedAt: runtime?.lastAttemptedAt,
        runtimeLastSucceededAt: runtime?.lastSucceededAt,
        runtimeLastStatus: runtime?.lastStatus,
        runtimeLastMessage: runtime?.lastMessage,
      },
    };
  });

  const feedExpected = settings.feeds
    .filter((item) => item.enabled)
    .map((feed) => {
      const runtime = alphaRadarSourceRuntime.get(feed.source);
      return {
        source: feed.source,
        kind: 'external' as const,
        sourceType: feed.collectorType === 'gdelt' ? 'news' as const : feed.collectorType === 'json' || feed.collectorType === 'rsshub' ? 'direct' as const : 'rss' as const,
        sourceLayer: feed.sourceLayer,
        sourceClass: feed.sourceClass,
        sourceWeight: feed.weight,
        details: {
          label: feed.label,
          cadenceMs: alphaRadarFeedCadenceMs(feed),
          enabled: true,
          runtimeLastAttemptedAt: runtime?.lastAttemptedAt,
          runtimeLastSucceededAt: runtime?.lastSucceededAt,
          runtimeLastStatus: runtime?.lastStatus,
          runtimeLastMessage: runtime?.lastMessage,
        },
      };
    });

  const expectedSources = [...monitoringExpected, ...feedExpected];
  const expectedKeys = new Set(expectedSources.map((item) => `${item.kind}:${item.source}`));

  const fromObservations = buildSharedAlphaRadarSourceHealth({
    observations: observations.filter((item) => expectedKeys.has(`${item.kind}:${item.source}`)),
    nowIso,
    expectedSources,
    staleAfterMsByKind: {
      market: ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS * 2,
      external: ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS * 2,
    },
  }).map((item) => {
    const details = item.details && typeof item.details === 'object'
      ? { ...item.details }
      : {};
    const runtimeLastAttemptedAt = typeof details.runtimeLastAttemptedAt === 'string' ? details.runtimeLastAttemptedAt : undefined;
    const runtimeLastSucceededAt = typeof details.runtimeLastSucceededAt === 'string' ? details.runtimeLastSucceededAt : undefined;
    const runtimeLastStatus = details.runtimeLastStatus === 'error' || details.runtimeLastStatus === 'ok'
      ? details.runtimeLastStatus
      : undefined;
    const effectiveLastObservedAt = maxIso(item.lastObservedAt, runtimeLastSucceededAt);
    const effectiveAgeMs = effectiveLastObservedAt ? Math.max(0, now - Date.parse(effectiveLastObservedAt)) : undefined;
    const detailsCadenceMs = typeof details.cadenceMs === 'number' && Number.isFinite(details.cadenceMs)
      ? Math.max(ALPHA_RADAR_COLLECTOR_MIN_INTERVAL_MS, Number(details.cadenceMs))
      : undefined;
    const staleAfterMs = detailsCadenceMs
      ? detailsCadenceMs * 2
      : item.kind === 'market'
        ? ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS * 2
        : ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS * 2;

    let next: AlphaRadarSourceHealth = {
      ...item,
      lastObservedAt: effectiveLastObservedAt,
      ageMs: effectiveAgeMs,
      stale: effectiveAgeMs === undefined ? true : effectiveAgeMs > staleAfterMs,
      status: effectiveAgeMs === undefined ? 'inactive' : effectiveAgeMs > staleAfterMs ? 'stale' : 'fresh',
      details: {
        ...details,
        lastContentObservedAt: item.lastObservedAt,
      },
    };

    if (runtimeLastStatus === 'error' && runtimeLastAttemptedAt && (!runtimeLastSucceededAt || Date.parse(runtimeLastAttemptedAt) >= Date.parse(runtimeLastSucceededAt))) {
      next = {
        ...next,
        lastObservedAt: runtimeLastAttemptedAt,
        ageMs: Math.max(0, now - Date.parse(runtimeLastAttemptedAt)),
        stale: true,
        status: 'stale',
        details: {
          ...(next.details ?? {}),
          runtimeState: 'error',
          freshnessNote: typeof details.runtimeLastMessage === 'string' ? details.runtimeLastMessage : 'latest source poll failed',
        },
      };
    }

    if ((next.details as { monitoringOnly?: unknown } | undefined)?.monitoringOnly === true) {
      next = applyAlphaRadarMonitoringFreshnessPolicy({ nowIso, health: next });
    }

    return next;
  });

  const connectorHealth = buildAlphaRadarConnectorHealth(getAlphaRadarConnectors(settings))
    .map((item) => applyConnectedIdleSourceHealthPolicy({ nowIso, health: item }));

  const merged = new Map<string, AlphaRadarSourceHealth>();
  for (const item of [...fromObservations, ...connectorHealth]) {
    merged.set(item.source, item);
  }

  const liveMarketTick = latestTickBySymbol.get(LIVE_SYMBOL);
  if (liveMarketTick) {
    const ageMs = Math.max(0, now - Date.parse(liveMarketTick.timestamp));
    const existing = merged.get('coinmaster_market_ticks');
    merged.set('coinmaster_market_ticks', {
      source: 'coinmaster_market_ticks',
      kind: 'market',
      sourceType: 'market',
      sourceLayer: 'primary',
      sourceClass: 'market',
      sourceWeight: existing?.sourceWeight ?? 1.2,
      lastObservedAt: liveMarketTick.timestamp,
      ageMs,
      stale: ageMs > LIVE_TICK_STALE_MS,
      itemCount: existing?.itemCount ?? 0,
      status: ageMs > LIVE_TICK_STALE_MS ? 'stale' : 'fresh',
      details: {
        title: `${LIVE_SYMBOL} live tick`,
        price: liveMarketTick.price,
        source: liveMarketTick.source,
      },
    });
  }

  return [...merged.values()].sort((a, b) => {
    const severity = (row: AlphaRadarSourceHealth) => row.status === 'stale' ? 0 : row.status === 'inactive' ? 1 : 2;
    return severity(a) - severity(b) || (b.itemCount ?? 0) - (a.itemCount ?? 0) || a.source.localeCompare(b.source);
  });
}

async function saveAlphaRadarObservations(observations: AlphaRadarObservation[]): Promise<number> {
  const db = await getDb();
  const existing = ensureAlphaRadarObservationsState(db);
  const bundles = ensureEvidenceBundlesState(db);
  const existingKeys = new Set(existing.map((item) => {
    if (item.kind === 'market') return buildAlphaRadarMarketObservationDedupeKey(item);
    return `${item.source}|${item.title.toLowerCase()}|${item.observedAt}`;
  }));

  let createdCount = 0;
  const nowIso = new Date().toISOString();
  for (const observation of observations) {
    const dedupeKey = observation.kind === 'market'
      ? buildAlphaRadarMarketObservationDedupeKey(observation)
      : `${observation.source}|${observation.title.toLowerCase()}|${observation.observedAt}`;
    if (existingKeys.has(dedupeKey)) continue;
    const { observation: durableObservation } = await ingestObservationIntoEvidence({
      observation,
      bundles,
      nowIso,
      nextBundleId: () => `evidence-${nanoid(10)}`,
    });
    existing.push(durableObservation);
    existingKeys.add(dedupeKey);
    createdCount += 1;
  }

  pruneAlphaRadarObservations(existing);
  db.data.alphaRadarObservations = existing
    .slice()
    .sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))
    .slice(0, 2000);
  db.data.evidenceBundles = pruneEvidenceBundles(bundles, nowIso);
  db.data.signalCandidates = syncSignalCandidatesFromEvidence({
    bundles: db.data.evidenceBundles,
    candidates: ensureSignalCandidatesState(db),
    monitoredCoins: normalizeTradingRules(db.data.settings.tradingRules).coins,
    nowIso,
  });
  db.data.radarContextPolicies = syncRadarContextPolicies({ db, nowIso });
  await db.write();
  return createdCount;
}

function alphaRadarMarketTickSnapshot(dbTicks: { symbol: string; price: number; timestamp: string }[]) {
  const merged = new Map<string, { symbol: string; price: number; timestamp: string }>();
  for (const tick of dbTicks) {
    merged.set(`${normalizeSymbol(tick.symbol)}|${tick.timestamp}`, tick);
  }
  for (const [symbol, tick] of latestTickBySymbol.entries()) {
    merged.set(`${normalizeSymbol(symbol)}|${tick.timestamp}`, {
      symbol: normalizeSymbol(symbol),
      price: tick.price,
      timestamp: tick.timestamp,
    });
  }
  return [...merged.values()]
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .slice(-5000);
}

async function collectAlphaRadarMarketSnapshotRun(trigger: 'auto' | 'manual'): Promise<{ createdCount: number }> {
  const nowIso = new Date().toISOString();
  alphaRadarCollectorStarted('market');
  try {
    const db = await getDb();
    const settings = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
    const latestObservedAtBySource = alphaRadarLatestObservationBySource(ensureAlphaRadarObservationsState(db));
    const rules = normalizeTradingRules(db.data.settings.tradingRules);
    const tradableSymbols = getMonitoredSymbols(rules);
    const monitoring = await fetchAlphaRadarMonitoringTicks({ settings, latestObservedAtBySource, trigger });
    const candidates = buildMarketObservationCandidates({
      nowIso,
      ticks: alphaRadarMarketTickSnapshot([...db.data.marketTicks, ...monitoring.ticks]),
      positions: db.data.positions,
      tradableSymbols: [...new Set([...tradableSymbols, ...Object.keys(monitoring.profilesBySymbol)])],
      profilesBySymbol: monitoring.profilesBySymbol,
    });
    const observations = candidates
      .map((candidate) => buildAlphaRadarObservation({
        id: `obs-${nanoid(10)}`,
        createdAt: nowIso,
        ...candidate,
      }))
      .filter((row): row is { ok: true; observation: AlphaRadarObservation } => row.ok)
      .map((row) => row.observation);
    const createdCount = await saveAlphaRadarObservations(observations);
    alphaRadarCollectorFinished('market', 'ok', `${trigger} market snapshot collected`, createdCount);
    recordAlphaRadarActivity({
      plane: 'market',
      level: 'info',
      status: 'ok',
      title: 'Market snapshot refreshed',
      message: `${createdCount} new market observations across ${Object.keys(monitoring.profilesBySymbol).length} polled monitoring sources.`,
      observedAt: nowIso,
      topicTags: ['market-source-health'],
      metadata: { trigger, createdCount, polledMonitoringSources: Object.keys(monitoring.profilesBySymbol).length, monitoringUniverse: monitoring.monitoringOnlyAssets.length },
    });
    return { createdCount };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    alphaRadarCollectorFinished('market', 'error', message, 0, 1);
    recordAlphaRadarActivity({
      plane: 'market',
      level: 'error',
      status: 'error',
      title: 'Market snapshot failed',
      message,
      observedAt: nowIso,
      topicTags: ['market-source-health', 'collector-error'],
      metadata: { trigger },
    });
    throw error;
  }
}

async function collectAlphaRadarExternalFeedsRun(trigger: 'auto' | 'manual'): Promise<{ createdCount: number }> {
  const nowIso = new Date().toISOString();
  alphaRadarCollectorStarted('external');
  try {
    const db = await getDb();
    const settings = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
    const latestObservedAtBySource = alphaRadarLatestObservationBySource(ensureAlphaRadarObservationsState(db));
    const nowMs = Date.parse(nowIso);
    const observations: AlphaRadarObservation[] = [];
    let errorCount = 0;

    const enabledFeeds = settings.feeds.filter((item) => item.enabled);
    const dueFeeds = trigger === 'manual'
      ? enabledFeeds
      : enabledFeeds.filter((feed) => alphaRadarSourceDue(feed.source, alphaRadarFeedCadenceMs(feed), nowMs, latestObservedAtBySource.get(feed.source)));
    const feedResults = await mapWithConcurrency(dueFeeds, ALPHA_RADAR_EXTERNAL_FEED_CONCURRENCY, async (feed) => {
      const attemptedAt = new Date().toISOString();
      try {
        let items: ReturnType<typeof extractJsonFeedItems> | ReturnType<typeof extractGdeltItems> | ReturnType<typeof extractRssItems> = [];
        let fetchMeta: Awaited<ReturnType<typeof alphaRadarFetchTextWithMeta>>['meta'];
        if (feed.collectorType === 'json') {
          const fetched = await alphaRadarFetchJsonWithMeta<unknown>(feed.url);
          items = extractJsonFeedItems(fetched.json, feed.parser);
          fetchMeta = fetched.meta;
        } else if (feed.collectorType === 'gdelt') {
          const fetched = await alphaRadarFetchJsonWithMeta<unknown>(feed.url);
          items = extractGdeltItems(fetched.json);
          fetchMeta = fetched.meta;
        } else {
          const fetched = await alphaRadarFetchTextWithMeta(feed.url);
          items = await extractRssItemsWithProvenance(fetched.text);
          fetchMeta = fetched.meta;
        }
        const builtObservations = items
          .map((item) => buildAlphaRadarObservation({
            id: `obs-${nanoid(10)}`,
            createdAt: nowIso,
            kind: 'external',
            source: feed.source,
            sourceType: feed.collectorType === 'json' ? 'direct' : feed.collectorType === 'gdelt' ? 'news' : 'rss',
            sourceLayer: feed.sourceLayer,
            sourceClass: feed.sourceClass,
            sourceWeight: feed.weight,
            title: item.title,
            excerpt: item.excerpt,
            assetTags: [...(feed.assetTags ?? []), ...(item.assetTags ?? [])],
            topicTags: [...(feed.topicTags ?? []), ...(item.topicTags ?? [])],
            observedAt: item.observedAt ?? nowIso,
            provenance: {
              feedId: feed.id,
              sourceLabel: feed.label,
              publisher: item.sourceName,
              author: item.author,
              url: item.link,
              canonicalUrl: item.canonicalUrl,
              publishedAt: item.observedAt,
              ingestedAt: nowIso,
              fetchedAt: fetchMeta.fetchedAt,
              observedAt: item.observedAt ?? nowIso,
              httpEtag: fetchMeta.httpEtag,
              httpLastModified: fetchMeta.lastModified,
              httpStatus: fetchMeta.status,
              rawPayloadRef: item.rawPayloadRef,
              externalId: item.externalId,
              parser: String(item.metadata?.parser ?? (feed.collectorType === 'rss' || feed.collectorType === 'rsshub' ? 'feedparser' : feed.collectorType)).trim(),
            },
            metadata: {
              ...(item.metadata ?? {}),
              fetchedUrl: fetchMeta.url,
            },
          }))
          .filter((row): row is { ok: true; observation: AlphaRadarObservation } => row.ok)
          .map((row) => row.observation);
        return { feed, observations: builtObservations, failure: null, attemptedAt };
      } catch (error) {
        return { feed, observations: [], failure: summarizeAlphaRadarFetchFailure(error), attemptedAt };
      }
    });

    for (const result of feedResults) {
      observations.push(...result.observations);
      if (!result.failure) {
        updateAlphaRadarSourceRuntime(result.feed.source, {
          lastAttemptedAt: result.attemptedAt,
          lastSucceededAt: result.attemptedAt,
          lastStatus: 'ok',
          lastMessage: 'feed refreshed',
        });
        continue;
      }
      updateAlphaRadarSourceRuntime(result.feed.source, {
        lastAttemptedAt: result.attemptedAt,
        lastStatus: 'error',
        lastMessage: result.failure.operatorMessage,
      });
      errorCount += 1;
      recordAlphaRadarActivity({
        plane: 'external',
        level: 'warn',
        status: 'partial',
        title: `${result.feed.label} fetch issue`,
        message: result.failure.operatorMessage,
        source: result.feed.source,
        sourceLabel: result.feed.label,
        observedAt: nowIso,
        topicTags: ['collector-health', 'collector-error'],
        metadata: { code: result.failure.code, trigger },
      });
    }

    const connectorSettings = getAlphaRadarConnectors(settings);
    const connectorCollectors: Array<{ type: AlphaRadarConnectorType; run: typeof collectTelegramAuthReadyConnector | typeof collectRedditConnector | typeof collectBlueskyConnector }> = [
      { type: 'telegram', run: collectTelegramAuthReadyConnector },
      { type: 'reddit', run: collectRedditConnector },
      { type: 'bluesky', run: collectBlueskyConnector },
    ];
    let polledConnectorCount = 0;
    for (const connector of connectorCollectors) {
      const connectorSource = `connector:${connector.type}`;
      const fallbackSyncAt = connectorSettings[connector.type]?.state?.lastSyncAt;
      if (trigger !== 'manual' && !alphaRadarSourceDue(connectorSource, alphaRadarConnectorCadenceMs(connector.type), nowMs, fallbackSyncAt)) {
        continue;
      }
      polledConnectorCount += 1;
      try {
        const result = await connector.run(connectorSettings[connector.type] ?? DEFAULT_ALPHA_RADAR_SETTINGS.connectors?.[connector.type]!);
        if (settings.connectors) settings.connectors[result.type] = { ...connectorSettings[result.type], state: result.state };
        updateAlphaRadarSourceRuntime(connectorSource, {
          lastAttemptedAt: result.state.lastSyncAt ?? nowIso,
          lastSucceededAt: result.state.lastSyncStatus === 'success' ? (result.state.lastSyncAt ?? nowIso) : undefined,
          lastStatus: result.state.lastSyncStatus === 'success' ? 'ok' : 'error',
          lastMessage: result.state.message,
        });
        for (const candidate of result.candidates) {
          const built = buildAlphaRadarObservation({
            id: `obs-${nanoid(10)}`,
            createdAt: nowIso,
            kind: 'external',
            source: candidate.source,
            sourceType: 'social',
            sourceLayer: connectorSettings[result.type]?.sourceLayer,
            sourceClass: connectorSettings[result.type]?.sourceClass,
            sourceWeight: connectorSettings[result.type]?.weight,
            title: candidate.title,
            excerpt: candidate.excerpt,
            assetTags: candidate.assetTags,
            topicTags: candidate.topicTags,
            sentimentScore: candidate.sentimentScore,
            noveltyScore: candidate.noveltyScore,
            urgencyScore: candidate.urgencyScore,
            marketAlignmentScore: candidate.marketAlignmentScore,
            observedAt: candidate.observedAt ?? nowIso,
            provenance: candidate.provenance,
            metadata: candidate.metadata,
          });
          if (built.ok) observations.push(built.observation);
        }
      } catch (error) {
        updateAlphaRadarSourceRuntime(connectorSource, {
          lastAttemptedAt: nowIso,
          lastStatus: 'error',
          lastMessage: error instanceof Error ? error.message : String(error),
        });
        errorCount += 1;
      }
    }

    db.data.settings.alphaRadar = settings;
    const createdCount = await saveAlphaRadarObservations(observations);
    alphaRadarCollectorFinished('external', errorCount > 0 ? 'partial' : 'ok', `${trigger} external collection complete`, createdCount, errorCount);
    recordAlphaRadarActivity({
      plane: 'external',
      level: errorCount > 0 ? 'warn' : 'info',
      status: errorCount > 0 ? 'partial' : 'ok',
      title: 'External collection finished',
      message: `${createdCount} new external observations from ${dueFeeds.length} feeds and ${polledConnectorCount} connectors${errorCount > 0 ? `, ${errorCount} upstream issue(s)` : ''}.`,
      observedAt: nowIso,
      topicTags: ['collector-health'],
      metadata: { trigger, createdCount, errorCount, polledFeeds: dueFeeds.length, polledConnectors: polledConnectorCount },
    });
    return { createdCount };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    alphaRadarCollectorFinished('external', 'error', message, 0, 1);
    recordAlphaRadarActivity({
      plane: 'external',
      level: 'error',
      status: 'error',
      title: 'External collection failed',
      message,
      observedAt: nowIso,
      topicTags: ['collector-health', 'collector-error'],
      metadata: { trigger },
    });
    throw error;
  }
}

async function buildAlphaRadarLiveState(): Promise<AlphaRadarLiveResponse> {
  const db = await getDb();
  const settings = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
  const openPositions = db.data.positions
    .filter((position) => position.status === 'open')
    .map((position) => ({
      id: position.id,
      symbol: position.symbol,
      side: position.side,
      size: position.remainingSize ?? position.size,
      entryPrice: position.entryPrice,
      leverage: position.leverage,
      openedAt: position.openedAt,
      source: position.source,
      unrealizedPnl: position.pnl,
    })) as LivePosition[];
  return {
    ok: true,
    openPositions,
    pendingConfirmations: await loadPendingConfirmationRows(),
    monitoring: {
      autoCollectEnabled: settings.enabled,
      marketSnapshotIntervalMs: ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS,
      externalFeedsIntervalMs: ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS,
      collectors: Object.values(alphaRadarCollectors),
      events: alphaRadarActivityEvents.slice(0, 20),
      sourceHealth: buildAlphaRadarSourceHealth(settings, ensureAlphaRadarObservationsState(db)),
      monitoringOnlyAssets: enabledAlphaRadarMonitoringWatchlist(settings).filter((item) => item.monitoringOnly).map((item) => item.symbol),
      llmMode: 'on_demand',
    },
  };
}

function startAlphaRadarMonitoringPlane() {
  if (alphaRadarMarketTimer || alphaRadarExternalTimer) return;
  const kickMarket = () => {
    if (alphaRadarCollectors.market.busy) return;
    void collectAlphaRadarMarketSnapshotRun('auto').catch((err) =>
      logger.warn({ component: 'alpha-radar', plane: 'market', err }, 'alpha radar market snapshot failed')
    );
  };
  const kickExternal = () => {
    if (alphaRadarCollectors.external.busy) return;
    void collectAlphaRadarExternalFeedsRun('auto').catch((err) =>
      logger.warn({ component: 'alpha-radar', plane: 'external', err }, 'alpha radar external collection failed')
    );
  };
  kickMarket();
  kickExternal();
  alphaRadarCollectors.market.nextRunAt = new Date(Date.now() + ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS).toISOString();
  alphaRadarCollectors.external.nextRunAt = new Date(Date.now() + ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS).toISOString();
  alphaRadarMarketTimer = setInterval(kickMarket, ALPHA_RADAR_MARKET_SNAPSHOT_INTERVAL_MS);
  alphaRadarExternalTimer = setInterval(kickExternal, ALPHA_RADAR_EXTERNAL_FEEDS_INTERVAL_MS);
}

function prunePendingConfirmations(list: PendingConfirmation[]): PendingConfirmation[] {
  const cutoff = Date.now() - PENDING_CONFIRMATION_TTL_MS;
  return list.filter((p) => Date.parse(p.createdAt) >= cutoff && Number.isFinite(p.size) && p.size > 0 && Number.isFinite(p.price) && p.price > 0 && Number.isFinite(p.leverage) && p.leverage > 0);
}

function pendingToLivePosition(pending: PendingConfirmation): LivePosition {
  const triggerLabel = formatPendingTriggerLabel(pending.strategy, pending.timeframe);

  return {
    id: pending.id,
    symbol: pending.symbol,
    side: pending.side,
    size: pending.size,
    entryPrice: pending.price,
    dealValue: Number((pending.price * pending.size).toFixed(2)),
    leverage: pending.leverage,
    openedAt: pending.createdAt,
    source: triggerLabel,
  };
}

async function loadPendingConfirmations(): Promise<PendingConfirmation[]> {
  const db = await getDb();
  const next = prunePendingConfirmations(db.data.pendingConfirmations);
  if (next.length !== db.data.pendingConfirmations.length) {
    db.data.pendingConfirmations = next;
    await db.write();
  }
  return next;
}

async function loadPendingConfirmationRows(): Promise<LivePosition[]> {
  const pending = await loadPendingConfirmations();
  return pending
    .slice()
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .map(pendingToLivePosition);
}

async function getTelegramConfig(): Promise<{
  token: string;
  chatId: string;
  notifyOpen: boolean;
  notifyTp: boolean;
  notifySl: boolean;
  notifyManualConfirm: boolean;
  notifyDailyAnalytics: boolean;
  notifySignalRejected: boolean;
  notifyOrderRejected: boolean;
  notifyPositionClosed: boolean;
} | null> {
  const db = await getDb();
  const s = db.data.settings.telegramNotify;
  const token = String(s?.botToken ?? '').trim();
  const chatId = String(s?.chatId ?? '').trim();
  if (!token || !chatId) return null;
  return {
    token,
    chatId,
    notifyOpen: s?.notifyOpen !== false,
    notifyTp: s?.notifyTp !== false,
    notifySl: s?.notifySl !== false,
    notifyManualConfirm: s?.notifyManualConfirm !== false,
    notifyDailyAnalytics: s?.notifyDailyAnalytics !== false,
    notifySignalRejected: s?.notifySignalRejected === true,
    notifyOrderRejected: s?.notifyOrderRejected === true,
    notifyPositionClosed: s?.notifyPositionClosed === true,
  };
}

function maskBotToken(token: string): string {
  if (!token) return '';
  if (token.length <= 8) return '••••';
  return `${token.slice(0, 4)}••••${token.slice(-4)}`;
}

function parseTelegramRetryAfterMs(body: string): number | undefined {
  if (!body) return undefined;
  try {
    const parsed = JSON.parse(body) as { parameters?: { retry_after?: unknown } };
    const retryAfterSec = Number(parsed?.parameters?.retry_after);
    if (Number.isFinite(retryAfterSec) && retryAfterSec > 0) {
      return retryAfterSec * 1000;
    }
  } catch {
    // ignore non-JSON body
  }

  const match = body.match(/retry after\s+(\d+)/i);
  if (!match) return undefined;
  const retryAfterSec = Number(match[1]);
  return Number.isFinite(retryAfterSec) && retryAfterSec > 0 ? retryAfterSec * 1000 : undefined;
}

function buildTelegramSendError(status: number, body: string): Error {
  const err = new Error(`telegram_send_failed_${status}${body ? `_${body.slice(0, 120)}` : ''}`) as Error & { retryAfterMs?: number; permanent?: boolean };
  if (status === 429) {
    err.retryAfterMs = parseTelegramRetryAfterMs(body);
  }
  err.permanent = status === 400 || status === 401 || status === 403;
  return err;
}

function compactTelegramOutbox(items: TelegramOutboxItem[]): TelegramOutboxItem[] {
  const now = Date.now();
  return items
    .filter((m) => {
      if (m.status === 'sent') {
        return !m.sentAt || now - Date.parse(m.sentAt) < TELEGRAM_OUTBOX_SENT_RETENTION_MS;
      }
      if (m.status === 'failed') {
        const failedAt = m.nextAttemptAt || m.createdAt;
        return !failedAt || now - Date.parse(failedAt) < TELEGRAM_OUTBOX_FAILED_RETENTION_MS;
      }
      return true;
    })
    .slice(-5000);
}

interface AlertState {
  lastNotifiedOpenPositionId?: string | null;
  updatedAt?: string | null;
  emergencyCloseNotificationKey?: string | null;
  ddLock?: {
    active: boolean;
    activatedAt?: string;
    triggeredDailyDDPct?: number;
    dailyDDLimitPct?: number;
    triggeredEquityUsd?: number;
    baselineEquityUsd?: number;
    emergencyCloseNotificationSent?: boolean;
    emergencyCloseSettledAt?: string;
  };
}

interface DdLockState {
  active: boolean;
  activatedAt: string;
  triggeredDailyDDPct?: number;
  dailyDDLimitPct?: number;
  triggeredEquityUsd?: number;
  baselineEquityUsd?: number;
  emergencyCloseNotificationSent: boolean;
  emergencyCloseSettledAt?: string;
}

const DEFAULT_ALERT_STATE: AlertState = {
  lastNotifiedOpenPositionId: null,
  updatedAt: null,
  emergencyCloseNotificationKey: null,
  ddLock: undefined,
};

async function readAlertState(): Promise<AlertState> {
  try {
    const raw = await readFile(alertStateFilePath, 'utf8');
    const parsed = JSON.parse(raw) as AlertState;
    return {
      ...DEFAULT_ALERT_STATE,
      ...parsed,
    };
  } catch {
    return { ...DEFAULT_ALERT_STATE };
  }
}

async function writeAlertState(patch: Partial<AlertState>): Promise<AlertState> {
  const next = {
    ...(await readAlertState()),
    ...patch,
    updatedAt: new Date().toISOString(),
  };
  await mkdir(path.dirname(alertStateFilePath), { recursive: true });
  await writeFile(alertStateFilePath, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
  return next;
}

function loadPersistedDdLockState(): Partial<DdLockState> {
  try {
    const raw = readFileSync(alertStateFilePath, 'utf8');
    const parsed = JSON.parse(raw) as AlertState;
    const lock = parsed.ddLock;
    if (!lock || typeof lock !== 'object') return {};

    return {
      active: lock.active === true,
      activatedAt: typeof lock.activatedAt === 'string' ? lock.activatedAt : '',
      triggeredDailyDDPct: typeof lock.triggeredDailyDDPct === 'number' ? lock.triggeredDailyDDPct : undefined,
      dailyDDLimitPct: typeof lock.dailyDDLimitPct === 'number' ? lock.dailyDDLimitPct : undefined,
      triggeredEquityUsd: typeof lock.triggeredEquityUsd === 'number' ? lock.triggeredEquityUsd : undefined,
      baselineEquityUsd: typeof lock.baselineEquityUsd === 'number' ? lock.baselineEquityUsd : undefined,
      emergencyCloseNotificationSent: lock.emergencyCloseNotificationSent === true,
      emergencyCloseSettledAt: typeof lock.emergencyCloseSettledAt === 'string' ? lock.emergencyCloseSettledAt : undefined,
    };
  } catch {
    return {};
  }
}

async function persistDdLockState(): Promise<void> {
  await writeAlertState({
    ddLock: {
      active: ddLock.active,
      activatedAt: ddLock.activatedAt || undefined,
      triggeredDailyDDPct: ddLock.triggeredDailyDDPct,
      dailyDDLimitPct: ddLock.dailyDDLimitPct,
      triggeredEquityUsd: ddLock.triggeredEquityUsd,
      baselineEquityUsd: ddLock.baselineEquityUsd,
      emergencyCloseNotificationSent: ddLock.emergencyCloseNotificationSent,
      emergencyCloseSettledAt: ddLock.emergencyCloseSettledAt,
    },
  });
}

async function getEmergencyCloseNotificationKey(): Promise<string> {
  const state = await readAlertState();
  if (state.emergencyCloseNotificationKey && state.emergencyCloseNotificationKey.trim().length > 0) {
    return state.emergencyCloseNotificationKey;
  }

  const key = `emergency-close:${nanoid(12)}`;
  await writeAlertState({ emergencyCloseNotificationKey: key });
  return key;
}

async function clearEmergencyCloseNotificationKey(): Promise<void> {
  const state = await readAlertState();
  if (!state.emergencyCloseNotificationKey) return;
  await writeAlertState({ emergencyCloseNotificationKey: null });
}

async function sendTelegramText(text: string, opts?: { replyMarkup?: unknown }): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg) return;
  const response = await fetch(`https://api.telegram.org/bot${cfg.token}/sendMessage`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      chat_id: cfg.chatId,
      text,
      ...(opts?.replyMarkup ? { reply_markup: opts.replyMarkup } : {}),
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw buildTelegramSendError(response.status, body);
  }
}

async function enqueueTelegramOutbox(params: {
  category: TelegramOutboxItem['category'];
  text: string;
  replyMarkup?: unknown;
  dedupeKey?: string;
}): Promise<{ queued: boolean; id?: string }> {
  const cfg = await getTelegramConfig();
  if (!cfg) return { queued: false };

  const db = await getDb();
  db.data.telegramOutbox = Array.isArray(db.data.telegramOutbox) ? db.data.telegramOutbox : [];

  if (params.dedupeKey) {
    const exists = db.data.telegramOutbox.find((m) => m.dedupeKey === params.dedupeKey && m.status !== 'failed');
    if (exists) return { queued: false, id: exists.id };
  }

  const now = new Date().toISOString();
  const msg: TelegramOutboxItem = {
    id: `tg-${nanoid(10)}`,
    category: params.category,
    text: params.text,
    replyMarkup: params.replyMarkup,
    dedupeKey: params.dedupeKey,
    status: 'queued',
    attempts: 0,
    nextAttemptAt: now,
    createdAt: now,
  };

  db.data.telegramOutbox.push(msg);
  db.data.telegramOutbox = compactTelegramOutbox(db.data.telegramOutbox);
  await db.write();
  return { queued: true, id: msg.id };
}

let telegramOutboxTimer: NodeJS.Timeout | null = null;
let telegramOutboxBusy = false;

async function runTelegramOutboxTick(): Promise<void> {
  if (telegramOutboxBusy) return;
  telegramOutboxBusy = true;
  try {
    const cfg = await getTelegramConfig();
    if (!cfg) return;

    const db = await getDb();
    db.data.telegramOutbox = Array.isArray(db.data.telegramOutbox) ? db.data.telegramOutbox : [];

    const now = Date.now();
    const due = db.data.telegramOutbox
      .filter((m) => m.status === 'queued' && Date.parse(m.nextAttemptAt) <= now)
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
      .slice(0, 20);

    if (due.length === 0) return;

    let changed = false;

    for (const msg of due) {
      try {
        const response = await fetch(`https://api.telegram.org/bot${cfg.token}/sendMessage`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            chat_id: cfg.chatId,
            text: msg.text,
            ...(msg.replyMarkup ? { reply_markup: msg.replyMarkup } : {}),
          }),
        });

        if (!response.ok) {
          const body = await response.text().catch(() => '');
          throw buildTelegramSendError(response.status, body);
        }

        msg.status = 'sent';
        msg.sentAt = new Date().toISOString();
        msg.lastError = undefined;
        changed = true;
      } catch (error) {
        msg.attempts += 1;
        msg.lastError = error instanceof Error ? error.message : String(error);
        const permanent = Boolean((error as { permanent?: unknown } | null | undefined)?.permanent);
        const retryAfterMsRaw = Number((error as { retryAfterMs?: unknown } | null | undefined)?.retryAfterMs);
        const retryAfterMs = Number.isFinite(retryAfterMsRaw) && retryAfterMsRaw > 0 ? retryAfterMsRaw : undefined;

        if (permanent || msg.attempts >= TELEGRAM_OUTBOX_MAX_ATTEMPTS) {
          msg.status = 'failed';
          logger.error({ component: 'telegram', outboxId: msg.id, attempts: msg.attempts, permanent, err: msg.lastError }, 'telegram outbox message permanently failed');
        } else {
          const backoff = retryAfterMs ?? Math.min(TELEGRAM_OUTBOX_RETRY_MAX_MS, TELEGRAM_OUTBOX_RETRY_BASE_MS * (2 ** Math.max(0, msg.attempts - 1)));
          msg.nextAttemptAt = new Date(Date.now() + backoff).toISOString();
          logger.warn({ component: 'telegram', outboxId: msg.id, attempts: msg.attempts, retryInMs: backoff, err: msg.lastError }, 'telegram outbox retry scheduled');
        }
        changed = true;
      }
    }

    if (changed) {
      db.data.telegramOutbox = compactTelegramOutbox(db.data.telegramOutbox);
      await db.write();
    }
  } finally {
    telegramOutboxBusy = false;
  }
}

function startTelegramOutboxLoop(): void {
  if (telegramOutboxTimer) return;
  runTelegramOutboxTick().catch((err) => logger.warn({ component: 'telegram', err }, 'initial telegram outbox tick failed'));
  telegramOutboxTimer = setInterval(() => {
    runTelegramOutboxTick().catch((err) => logger.warn({ component: 'telegram', err }, 'telegram outbox tick failed'));
  }, 3000);
  telegramOutboxTimer.unref?.();
}

async function notifyPendingConfirmationTelegram(pending: PendingConfirmation): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyManualConfirm) return;

  const triggerLabel = formatPendingTriggerLabel(pending.strategy, pending.timeframe);
  const dealValue = Number.isFinite(pending.price * pending.size)
    ? Number((pending.price * pending.size).toFixed(2))
    : 0;

  const text = [
    '⚠️ Coinmaster signal requires confirmation',
    `ID: ${pending.id}`,
    `${triggerLabel} • ${pending.symbol} ${pending.side.toUpperCase()}`,
    `Price: ${pending.price}`,
    `Proposed size: ${pending.size}`,
    `Proposed deal value: ${dealValue} USDC`,
    `Leverage: ${pending.leverage}x`,
    `Reason: ${pending.reason}`,
    'Reply command: /confirm <ID> or /reject <ID>',
  ].join('\n');

  await enqueueTelegramOutbox({
    category: 'manual_confirm',
    text,
    dedupeKey: `pending:${pending.id}`,
    replyMarkup: {
      inline_keyboard: [[
        { text: '✅ Confirm', callback_data: `confirm:${pending.id}` },
        { text: '❌ Reject', callback_data: `reject:${pending.id}` },
      ]],
    },
  });
}

async function clearPendingConfirmationForSymbol(symbol: string): Promise<void> {
  const db = await getDb();
  const before = db.data.pendingConfirmations.length;
  db.data.pendingConfirmations = db.data.pendingConfirmations.filter((p) => p.symbol.toUpperCase() !== symbol.toUpperCase());
  if (db.data.pendingConfirmations.length !== before) {
    await db.write();
  }
}

const CLASS_BIAS_PREFIX = '__CLASS_BIAS__';
const ASSET_CLASS_ORDER: AssetClass[] = ['crypto', 'commodity', 'forex', 'index', 'other'];

function classBiasCommandSymbol(assetClass: AssetClass): string {
  return `${CLASS_BIAS_PREFIX}${assetClass.toUpperCase()}`;
}

function getLatestBias(biasCommands: Array<{ symbol: string; bias: Bias }>, symbol: string): Bias | undefined {
  const normalized = normalizeSymbol(symbol);
  return [...biasCommands]
    .reverse()
    .find((b) => normalizeSymbol(b.symbol) === normalized)
    ?.bias;
}

function getLatestClassBias(biasCommands: Array<{ symbol: string; bias: Bias }>, assetClass: AssetClass): Bias | undefined {
  return getLatestBias(biasCommands, classBiasCommandSymbol(assetClass));
}

/**
 * Returns the asset class for a symbol (for bias policy and diagnostics only).
 *
 * NOTE: Asset class does NOT determine whether a symbol is monitored.
 * Monitoring is controlled exclusively by Trading Rules enabled coins list (see getMonitoredSymbols).
 */
function getAssetClassForSymbol(rules: TradingRulesSettings, symbol: string): AssetClass {
  const normalized = normalizeSymbol(symbol);
  const fromRules = rules.coins.find((coin) => normalizeSymbol(coin.symbol) === normalized);
  return fromRules?.assetClass ?? inferAssetClassFromSymbol(normalized);
}

function getBiasModeForSymbol(rules: TradingRulesSettings, symbol: string): { mode: BiasMode } {
  const normalized = normalizeSymbol(symbol);
  const override = rules.biasPolicy?.symbolOverrides?.[normalized];
  return { mode: override?.mode ?? 'global' };
}

function resolveBiasForSymbol(symbol: string, rules: TradingRulesSettings, biasCommands: Array<{ symbol: string; bias: Bias }>): Bias {
  const normalized = normalizeSymbol(symbol);
  const mode = getBiasModeForSymbol(rules, normalized);

  if (mode.mode === 'symbol') {
    const symbolBias = getLatestBias(biasCommands, normalized);
    return symbolBias ?? 'off';
  }

  const assetClass = getAssetClassForSymbol(rules, normalized);
  const classBias = getLatestClassBias(biasCommands, assetClass);
  return classBias ?? 'off';
}

async function getOperatorBias(symbol: string): Promise<Bias> {
  const db = await getDb();
  const rules = normalizeTradingRules(db.data.settings.tradingRules);
  return resolveBiasForSymbol(symbol, rules, db.data.biasCommands);
}

function buildDashboardBiasControls(rules: TradingRulesSettings, biasCommands: Array<{ symbol: string; bias: Bias }>) {
  const enabledCoins = (rules.coins ?? []).filter((coin) => coin.enabled);
  const deduped = new Map<string, typeof enabledCoins[number]>();

  for (const coin of enabledCoins) {
    const normalized = normalizeSymbol(coin.symbol);
    if (!normalized || deduped.has(normalized)) continue;
    deduped.set(normalized, coin);
  }

  const byClass = new Map<AssetClass, string[]>();
  const customSymbolControls: Array<{ symbol: string; assetClass: AssetClass; bias: Bias }> = [];

  for (const coin of deduped.values()) {
    const symbol = normalizeSymbol(coin.symbol);
    const assetClass = getAssetClassForSymbol(rules, symbol);
    const currentMode = getBiasModeForSymbol(rules, symbol).mode;

    const bucket = byClass.get(assetClass) ?? [];
    bucket.push(symbol);
    byClass.set(assetClass, bucket);

    if (currentMode === 'symbol') {
      customSymbolControls.push({
        symbol,
        assetClass,
        bias: resolveBiasForSymbol(symbol, rules, biasCommands),
      });
    }
  }

  const classBiasControls = [...byClass.entries()]
    .map(([assetClass, symbols]) => ({
      assetClass,
      symbols: [...symbols].sort((a, b) => a.localeCompare(b)),
      bias: getLatestClassBias(biasCommands, assetClass) ?? 'off',
    }))
    .sort((a, b) => ASSET_CLASS_ORDER.indexOf(a.assetClass) - ASSET_CLASS_ORDER.indexOf(b.assetClass));

  const customBiasControls = customSymbolControls
    .sort((a, b) => a.symbol.localeCompare(b.symbol));

  return { classBiasControls, customBiasControls };
}

let tradableSymbolsCache: { fetchedAtMs: number; symbols: string[] } | null = null;

async function fetchTradableSymbolsFromExchange(): Promise<string[]> {
  const adapterSymbols = typeof exchange.getTradableSymbols === 'function'
    ? await exchange.getTradableSymbols().catch(() => [] as string[])
    : [];

  const fallbackSymbols = adapterSymbols.length > 0
    ? adapterSymbols
    : Object.keys(await exchange.getMids().catch(() => ({} as Record<string, number>)));

  const normalized = [...new Set(fallbackSymbols.map((s) => normalizeSymbol(s)).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));

  if (normalized.length === 0) {
    throw new Error('symbol_catalog_empty');
  }

  tradableSymbolsCache = {
    fetchedAtMs: Date.now(),
    symbols: normalized,
  };

  return normalized;
}

async function getTradableSymbolsCached(options?: { force?: boolean; allowStale?: boolean }): Promise<string[] | null> {
  const force = options?.force === true;
  const allowStale = options?.allowStale !== false;
  const now = Date.now();

  if (!force && tradableSymbolsCache && (now - tradableSymbolsCache.fetchedAtMs) < TRADABLE_SYMBOLS_CACHE_MS) {
    return tradableSymbolsCache.symbols;
  }

  try {
    return await fetchTradableSymbolsFromExchange();
  } catch (err) {
    if (allowStale && tradableSymbolsCache?.symbols?.length) {
      logger.warn({ component: 'symbols-catalog', err }, 'using stale tradable symbols cache after refresh failure');
      return tradableSymbolsCache.symbols;
    }
    logger.warn({ component: 'symbols-catalog', err }, 'failed to load tradable symbols from exchange');
    return null;
  }
}

function getInvalidRuleSymbols(rules: TradingRulesSettings, allowedSymbols: Set<string>): string[] {
  const invalid = rules.coins
    .map((coin) => normalizeSymbol(coin.symbol))
    .filter((symbol) => symbol.length > 0 && !allowedSymbols.has(symbol));
  return [...new Set(invalid)];
}

async function isSymbolResolvableOnExchange(symbol: string): Promise<boolean> {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) return false;

  try {
    const meta = await exchange.getInstrumentMeta(normalized).catch(() => null);
    if (meta) return true;
  } catch {
    // continue to candle probe
  }

  const endTimeMs = Date.now();
  const startTimeMs = endTimeMs - (15 * 60_000) * 5;

  try {
    const candles = await exchange.getCandles({
      symbol: normalized,
      timeframe: '15m',
      startTimeMs,
      endTimeMs,
    });
    return Array.isArray(candles) && candles.length > 0;
  } catch {
    return false;
  }
}


async function getFreshExitClosePct(fallback = 50): Promise<number> {
  try {
    const db = await getDb();
    const rules = normalizeTradingRules(db.data.settings.tradingRules);
    const pct = Number(rules.exitClosePct);
    if (!Number.isFinite(pct)) return fallback;
    return Math.max(0, Math.min(100, pct));
  } catch {
    return fallback;
  }
}

async function queuePendingConfirmation(params: {
  symbol: string;
  side: 'long' | 'short';
  strategy: SignalStrategy;
  timeframe: TradingRulesTimeframe;
  reason: string;
  price: number;
  size: number;
  leverage: number;
  correlationId: string;
  executionIntentId?: string;
}): Promise<{ queued: boolean; id: string }> {
  const db = await getDb();
  const now = new Date().toISOString();

  const operatorBias = await getOperatorBias(params.symbol);
  const directionBias: Bias = params.side === 'long' ? 'long' : 'short';
  const biasBlocked = operatorBias === 'off' || operatorBias !== directionBias;
  if (biasBlocked) {
    logRiskGateAudit({
      gate: getEntrySignalAuditGate(params.strategy),
      passed: false,
      reason: 'operator_bias_block',
      details: { symbol: params.symbol, strategy: params.strategy, side: params.side, operatorBias },
    });
    await notifySignalRejectedEvent({
      symbol: params.symbol,
      source: `${params.strategy}:pending:${params.timeframe}`,
      reason: 'operator_bias_block',
      blocks: `operatorBias=${operatorBias}`,
    }).catch(() => undefined);
    return { queued: false, id: 'operator_bias_block' };
  }

  const cleaned = prunePendingConfirmations(db.data.pendingConfirmations);
  db.data.pendingConfirmations = cleaned;

  const price = Number(params.price.toFixed(8));
  const size = Number(params.size.toFixed(6));
  const leverage = Number(params.leverage);

  if (!Number.isFinite(price) || price <= 0 || !Number.isFinite(size) || size <= 0 || !Number.isFinite(leverage) || leverage <= 0) {
    return { queued: false, id: 'invalid_size' };
  }

  const next: PendingConfirmation = {
    id: `pc-${nanoid(10)}`,
    symbol: params.symbol,
    side: params.side,
    strategy: params.strategy,
    timeframe: params.timeframe,
    reason: params.reason,
    price,
    size,
    leverage,
    executionIntentId: params.executionIntentId,
    createdAt: now,
  };

  const existingIdx = db.data.pendingConfirmations.findIndex((p) => p.symbol.toUpperCase() === params.symbol.toUpperCase());
  if (existingIdx >= 0) {
    const existing = db.data.pendingConfirmations[existingIdx];
    const duplicate =
      existing.side === next.side &&
      existing.strategy === next.strategy &&
      existing.timeframe === next.timeframe &&
      Math.abs(Date.parse(now) - Date.parse(existing.createdAt)) < 60_000;

    if (duplicate) {
      return { queued: false, id: existing.id };
    }

    db.data.pendingConfirmations.splice(existingIdx, 1, next);
  } else {
    db.data.pendingConfirmations.push(next);
  }

  appendTradeEvent(db.data, {
    symbol: params.symbol,
    source: 'live',
    type: 'signal_detected',
    timestamp: now,
    correlationId: params.correlationId,
    side: params.side,
    price: params.price,
    quantity: params.size,
    reason: `${params.strategy}_signal_pending_confirmation`,
    payload: {
      pendingConfirmationId: next.id,
      timeframe: params.timeframe,
      strategy: params.strategy,
      leverage: params.leverage,
    },
  });

  await db.write();

  try {
    await notifyPendingConfirmationTelegram(next);
  } catch (error) {
    logger.warn({ component: 'pending-confirmation', err: error instanceof Error ? error.message : error }, 'telegram notification failed');
  }

  return { queued: true, id: next.id };
}

async function notifyTradeOpen(params: {
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  source: string;
}): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyOpen) return;
  await enqueueTelegramOutbox({
    category: 'trade_open',
    dedupeKey: `open:${params.symbol}:${params.side}:${params.price}:${params.size}:${params.source}`,
    text: [
      '🟢 Trade opened',
      `${params.symbol} ${params.side.toUpperCase()}`,
      `Price: ${params.price}`,
      `Size: ${params.size}`,
      `Source: ${params.source}`,
    ].join('\n'),
  });
}

async function notifyTpHit(params: { symbol: string; entryPrice: number; remainingSize: number; tpIds: string[] }): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyTp) return;
  await enqueueTelegramOutbox({
    category: 'tp',
    dedupeKey: `tp:${params.symbol}:${params.tpIds.join(',')}`,
    text: [
      '🎯 Take-profit filled',
      `${params.symbol}`,
      `Filled TP orders: ${params.tpIds.join(', ')}`,
      `SL moved to break-even: ${params.entryPrice}`,
      `Remaining size: ${params.remainingSize}`,
    ].join('\n'),
  });
}

async function notifySlEvent(params: { symbol: string; reason: string; closedBy?: string }): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifySl) return;

  const reason = String(params.reason || '').trim() || 'unknown';
  const closedBy = String(params.closedBy || reason).trim() || 'unknown';
  const symbol = String(params.symbol || '').trim().toUpperCase() || 'UNKNOWN';
  const isWatchdogReason = reason.endsWith('_watchdog');
  const local = getTzParts(new Date(), DAILY_ANALYTICS_TZ);

  // Watchdog events can retry every few seconds; notify once per symbol/reason/day.
  // Non-watchdog SL events keep minute-level dedupe for normal trade flows.
  const dedupeKey = isWatchdogReason
    ? `sl:${symbol}:${reason}:${local.dayKey}`
    : `sl:${symbol}:${reason}:${Math.floor(Date.now() / 60000)}`;

  await enqueueTelegramOutbox({
    category: 'sl',
    dedupeKey,
    text: [
      '🛑 Stop-loss / emergency exit event',
      `${symbol}`,
      `Reason: ${reason}`,
      `closed_by: ${closedBy}`,
    ].join('\n'),
  });
}

async function notifySignalRejectedEvent(params: {
  symbol: string;
  source: string;
  reason: string;
  blocks?: string;
}): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifySignalRejected) return;
  await enqueueTelegramOutbox({
    category: 'signal_rejected',
    dedupeKey: `signal_rejected:${params.symbol}:${params.source}:${params.reason}:${Math.floor(Date.now() / 60_000)}`,
    text: [
      '⛔ Signal rejected',
      `${params.symbol} — ${params.source}`,
      `Reason: ${params.reason}`,
      ...(params.blocks ? [`Blocks: ${params.blocks}`] : []),
    ].join('\n'),
  });
}

async function notifyOrderRejectedEvent(params: {
  symbol: string;
  source: string;
  error: string;
}): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyOrderRejected) return;
  await enqueueTelegramOutbox({
    category: 'order_rejected',
    dedupeKey: `order_rejected:${params.symbol}:${params.source}:${params.error.slice(0, 40)}:${Math.floor(Date.now() / 60_000)}`,
    text: [
      '❌ Order rejected by exchange',
      `${params.symbol} — ${params.source}`,
      `Error: ${params.error}`,
    ].join('\n'),
  });
}

async function notifyPositionClosedEvent(params: {
  symbol: string;
  correlationId: string;
  tpsFilled: number;
  reason?: string;
}): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyPositionClosed) return;
  const reason = String(params.reason || 'tp_all_filled');
  const isTimeStop = reason === 'time_stop';
  await enqueueTelegramOutbox({
    category: 'position_closed',
    dedupeKey: `position_closed:${params.correlationId}`,
    text: [
      isTimeStop ? '⏱️ Position closed by time stop' : '✅ Position fully closed',
      `${params.symbol}`,
      isTimeStop ? 'No TP1 follow-through within configured timeStopBars.' : `All TPs filled (${params.tpsFilled}). Position flat.`,
      `closed_by: ${reason}`,
    ].join('\n'),
  });
}

function getTzParts(date: Date, timeZone: string): { dayKey: string; hour: number; minute: number } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);

  const map: Record<string, string> = {};
  for (const p of parts) {
    if (p.type !== 'literal') map[p.type] = p.value;
  }

  const dayKey = `${map.year ?? '0000'}-${map.month ?? '00'}-${map.day ?? '00'}`;
  const hour = Number(map.hour ?? '0');
  const minute = Number(map.minute ?? '0');
  return {
    dayKey,
    hour: Number.isFinite(hour) ? hour : 0,
    minute: Number.isFinite(minute) ? minute : 0,
  };
}

function toFinite(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function fillClosedPnl(fill: FillEvent): number {
  const raw = fill.raw as { closedPnl?: unknown; execPnl?: unknown } | undefined;
  return toFinite(raw?.closedPnl ?? raw?.execPnl, 0);
}

function fillFee(fill: FillEvent): number {
  const raw = fill.raw as { fee?: unknown; execFee?: unknown } | undefined;
  return Math.abs(toFinite(raw?.fee ?? raw?.execFee, 0));
}

function fillDirection(fill: FillEvent): string {
  const raw = fill.raw as { dir?: unknown; closedSize?: unknown } | undefined;
  const dir = String(raw?.dir ?? '').trim();
  if (dir) return dir;

  const closedSize = toFinite(raw?.closedSize, 0);
  return closedSize > 0 ? 'close trade' : 'open trade';
}

function asUsd(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}$`;
}

function asPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatSymbolBreakdown(title: string, rows: Array<{ symbol: string; value: number }>, top = 3): string[] {
  const filtered = rows
    .filter((x) => Number.isFinite(x.value) && x.value !== 0)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, top);
  if (filtered.length === 0) return [];
  return [title, ...filtered.map((x) => `- ${x.symbol}: ${asUsd(x.value)}`)];
}

function isManualOpenFill(fill: FillEvent, tradeEvents: TradeEvent[]): boolean {
  const direction = fillDirection(fill);
  if (!direction.toLowerCase().startsWith('open ')) return false;

  const fillTs = Date.parse(fill.timestamp);
  if (!Number.isFinite(fillTs)) return false;

  const expectedSide = fill.side === 'buy' ? 'long' : 'short';
  return !tradeEvents.some((e) => {
    if (e.type !== 'order_submitted') return false;
    if (String(e.symbol).toUpperCase() !== fill.symbol.toUpperCase()) return false;
    if (e.side !== expectedSide) return false;
    const eventTs = Date.parse(String(e.timestamp));
    if (!Number.isFinite(eventTs)) return false;
    return Math.abs(eventTs - fillTs) <= 3 * 60_000;
  });
}

function isManualCloseFill(fill: FillEvent, tradeEvents: TradeEvent[]): boolean {
  const direction = fillDirection(fill);
  if (!direction.toLowerCase().startsWith('close ')) return false;

  const fillTs = Date.parse(fill.timestamp);
  if (!Number.isFinite(fillTs)) return false;

  return !tradeEvents.some((e) => {
    if (e.type !== 'order_submitted') return false;
    if (String(e.symbol).toUpperCase() !== fill.symbol.toUpperCase()) return false;
    const eventTs = Date.parse(String(e.timestamp));
    if (!Number.isFinite(eventTs)) return false;
    return Math.abs(eventTs - fillTs) <= 3 * 60_000;
  });
}

interface DailyAnalyticsSourceRow {
  source: string;
  fills: number;
  openFills: number;
  closeFills: number;
  realized: number;
  fees: number;
  net: number;
}

interface DailyAnalyticsContext {
  generatedAt: string;
  windowStart: string;
  windowEnd: string;
  localDayKey: string;
  timezone: string;
  fills: {
    total: number;
    open: number;
    close: number;
    executionOnlyOpen: number;
    manualOpenDetected: number;
    manualCloseDetected: number;
  };
  pnl: {
    realized: number;
    fees: number;
    net: number;
    winRatePct: number;
    winners: number;
    losers: number;
  };
  bySymbol: Array<{ symbol: string; realized: number }>;
  bySource: DailyAnalyticsSourceRow[];
  execution: {
    signalDetected: number;
    signalRejected: number;
    ordersSubmitted: number;
    ordersAcked: number;
    ordersRejected: number;
  };
  riskBlocks: {
    bias: number;
    leverage: number;
    dailyDD: number;
  };
  biggestLoss?: { symbol: string; value: number; timestamp: string };
  wins: string[];
  risks: string[];
  suggestions: string[];
}

interface AnalyticsHistorySourceSummary {
  source: string;
  fills: number;
  openFills: number;
  closeFills: number;
  winners: number;
  losers: number;
  winRatePct: number;
  realized: number;
  fees: number;
  net: number;
}

interface AnalyticsHistorySummary {
  generatedAt: string;
  windowStart: string;
  windowEnd: string;
  days: number;
  totals: {
    fills: number;
    openFills: number;
    closeFills: number;
    winners: number;
    losers: number;
    winRatePct: number;
    realized: number;
    fees: number;
    net: number;
  };
  bySource: AnalyticsHistorySourceSummary[];
  bySymbol: Array<{ symbol: string; realized: number; fills: number }>;
}

interface AnalyticsQualityMetrics {
  generatedAt: string;
  windowStart: string;
  windowEnd: string;
  hours: number;
  counts: {
    signalDetected: number;
    signalRejected: number;
    ordersSubmitted: number;
    ordersAcked: number;
    ordersRejected: number;
    openFills: number;
    closeFills: number;
    manualOpenDetected: number;
    manualCloseDetected: number;
  };
  rates: {
    signalToOrderPct: number;
    signalRejectPct: number;
    submitToAckPct: number;
    submitRejectPct: number;
    ackToOpenFillPct: number;
    signalToOpenFillPct: number;
    closeWinRatePct: number;
    manualOpenSharePct: number;
    manualCloseSharePct: number;
  };
}

interface PostTradeAnalyticsItem {
  id: string;
  symbol: string;
  source: string;
  side: 'long' | 'short';
  openTimestamp?: string;
  closeTimestamp: string;
  holdMinutes?: number;
  entryPrice?: number;
  exitPrice?: number;
  size?: number;
  realizedPnlUsd: number;
  feesUsd: number;
  netPnlUsd: number;
  outcome: 'win' | 'loss' | 'flat';
  manualOpenDetected: boolean;
  manualCloseDetected: boolean;
  eventCounts: {
    signalDetected: number;
    signalRejected: number;
    ordersSubmitted: number;
    ordersAcked: number;
    ordersRejected: number;
  };
  notes: string[];
}

function fillSource(fill: FillEvent): string {
  return String((fill.raw as { sourceExchange?: unknown } | undefined)?.sourceExchange ?? exchange.name).toLowerCase();
}

function buildUnifiedTradeEventStream(params: { fills: FillEvent[]; tradeEvents: TradeEvent[] }): TradeEvent[] {
  const { fills, tradeEvents } = params;
  const synthetic: TradeEvent[] = [];
  let seq = tradeEvents.length;
  let prevHash = tradeEvents.length > 0 ? tradeEvents[tradeEvents.length - 1]?.hash ?? null : null;

  const pushSynthetic = (input: {
    type: 'manual_open_detected' | 'manual_close_detected';
    fill: FillEvent;
    side: 'long' | 'short';
    reason: string;
  }) => {
    seq += 1;
    const base: Omit<TradeEvent, 'hash'> = {
      id: `synthetic:${input.type}:${input.fill.id ?? `${input.fill.symbol}:${input.fill.timestamp}:${seq}`}`,
      seq,
      symbol: String(input.fill.symbol).toUpperCase(),
      type: input.type,
      source: 'live',
      timestamp: input.fill.timestamp,
      correlationId: `manual:${String(input.fill.symbol).toUpperCase()}:${input.fill.timestamp}`,
      side: input.side,
      price: input.fill.price,
      quantity: input.fill.size,
      pnl: input.type === 'manual_close_detected' ? fillClosedPnl(input.fill) : undefined,
      reason: input.reason,
      prevHash,
      payload: {
        fillId: input.fill.id,
        sourceExchange: fillSource(input.fill),
        direction: fillDirection(input.fill),
      },
    };
    const hash = crypto.createHash('sha256').update(JSON.stringify(base)).digest('hex');
    const event: TradeEvent = { ...base, hash };
    prevHash = hash;
    synthetic.push(event);
  };

  const sortedFills = fills.slice().sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  for (const fill of sortedFills) {
    if (fillSource(fill) !== exchange.name.toLowerCase()) continue;
    const side = fill.side === 'buy' ? 'long' : 'short';
    if (isManualOpenFill(fill, tradeEvents)) {
      pushSynthetic({ type: 'manual_open_detected', fill, side, reason: 'manual_open_without_system_submit' });
    }
    if (isManualCloseFill(fill, tradeEvents)) {
      pushSynthetic({ type: 'manual_close_detected', fill, side, reason: 'manual_close_without_system_submit' });
    }
  }

  return [...tradeEvents, ...synthetic].sort((a, b) => {
    const diff = Date.parse(a.timestamp) - Date.parse(b.timestamp);
    return diff !== 0 ? diff : a.seq - b.seq;
  });
}

async function buildDailyAnalyticsContext(windowMs = 24 * 60 * 60_000): Promise<DailyAnalyticsContext> {
  const now = Date.now();
  const cutoff = now - windowMs;

  const [executionFills, db] = await Promise.all([
    exchange.getFills().catch(() => [] as FillEvent[]),
    getDb(),
  ]);

  const externalFills = await collectExternalFills(db.data.settings, cutoff);

  const recentFills = [...executionFills, ...externalFills]
    .filter((f) => Date.parse(f.timestamp) >= cutoff)
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));

  const persistedEvents = (db.data.tradeEvents ?? []).filter((e) => Date.parse(e.timestamp) >= cutoff);
  const recentEvents = buildUnifiedTradeEventStream({ fills: recentFills, tradeEvents: persistedEvents }).filter((e) => Date.parse(e.timestamp) >= cutoff);
  const recentAudits = (db.data.riskGateAudit ?? []).filter((a) => Date.parse(a.timestamp) >= cutoff);

  const closeFills = recentFills.filter((f) => fillDirection(f).toLowerCase().startsWith('close '));
  const openFills = recentFills.filter((f) => fillDirection(f).toLowerCase().startsWith('open '));

  const executionRecentFills = executionFills
    .filter((f) => Date.parse(f.timestamp) >= cutoff)
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  const executionOpenFills = executionRecentFills.filter((f) => fillDirection(f).toLowerCase().startsWith('open '));
  const executionCloseFills = executionRecentFills.filter((f) => fillDirection(f).toLowerCase().startsWith('close '));
  const manualOpenFills = executionOpenFills.filter((f) => isManualOpenFill(f, recentEvents));
  const manualCloseFills = executionCloseFills.filter((f) => isManualCloseFill(f, recentEvents));

  const realized = closeFills.reduce((sum, f) => sum + fillClosedPnl(f), 0);
  const fees = recentFills.reduce((sum, f) => sum + fillFee(f), 0);
  const net = realized - fees;

  const winners = closeFills.filter((f) => fillClosedPnl(f) > 0).length;
  const losers = closeFills.filter((f) => fillClosedPnl(f) < 0).length;
  const winRate = closeFills.length > 0 ? (winners / closeFills.length) * 100 : 0;

  const pnlBySymbol = new Map<string, number>();
  for (const f of closeFills) {
    const key = f.symbol.toUpperCase();
    const value = fillClosedPnl(f);
    pnlBySymbol.set(key, (pnlBySymbol.get(key) ?? 0) + value);
  }

  const topRows = [...pnlBySymbol.entries()].map(([symbol, value]) => ({ symbol, realized: value }));

  const bySource = new Map<string, DailyAnalyticsSourceRow>();
  for (const fill of recentFills) {
    const source = fillSource(fill);
    const row = bySource.get(source) ?? { source, fills: 0, openFills: 0, closeFills: 0, realized: 0, fees: 0, net: 0 };
    row.fills += 1;
    if (fillDirection(fill).toLowerCase().startsWith('close ')) row.closeFills += 1;
    if (fillDirection(fill).toLowerCase().startsWith('open ')) row.openFills += 1;
    row.realized += fillClosedPnl(fill);
    row.fees += fillFee(fill);
    row.net = row.realized - row.fees;
    bySource.set(source, row);
  }

  const signalDetected = recentEvents.filter((e) => e.type === 'signal_detected').length;
  const signalRejected = recentEvents.filter((e) => e.type === 'signal_rejected').length;
  const ordersSubmitted = recentEvents.filter((e) => e.type === 'order_submitted').length;
  const ordersAcked = recentEvents.filter((e) => e.type === 'order_acknowledged').length;
  const ordersRejected = recentEvents.filter((e) => e.type === 'order_rejected').length;

  const biasBlocks = recentAudits.filter((a) => a.reason === 'operator_bias_block').length;
  const leverageBlocks = recentEvents.filter((e) => e.reason === 'pending_rejected_risk_gate' && String(e.payload?.blocks ?? '').includes('leverage_limit_exceeded')).length;
  const ddBlocks = recentEvents.filter((e) => e.reason === 'pending_rejected_risk_gate' && String(e.payload?.blocks ?? '').includes('daily_loss_limit_exceeded')).length;

  const biggestLoss = closeFills
    .map((f) => ({ symbol: f.symbol, value: fillClosedPnl(f), timestamp: f.timestamp }))
    .filter((x) => x.value < 0)
    .sort((a, b) => a.value - b.value)[0];

  const wins: string[] = [];
  const risks: string[] = [];
  const suggestions: string[] = [];

  if (net > 0) wins.push(`День закрыт в плюс: ${asUsd(net)} (realized ${asUsd(realized)}, fee ${asUsd(-fees)}).`);
  if (closeFills.length > 0 && winRate >= 50) wins.push(`Стабильность закрытий: win-rate ${asPct(winRate)} (${winners}/${closeFills.length}).`);
  if (ordersRejected === 0 && ordersSubmitted > 0) wins.push('Без отказов биржи по submit/ack в ключевых ордерах.');

  if (net < 0) risks.push(`Итог за окно отрицательный: ${asUsd(net)}.`);
  if (biggestLoss) risks.push(`Крупнейший минус: ${biggestLoss.symbol} ${asUsd(biggestLoss.value)} (${biggestLoss.timestamp}).`);
  if (biasBlocks > 0) risks.push(`Блоки по bias: ${biasBlocks} (проверь актуальность bias-команд).`);
  if (leverageBlocks > 0 || ddBlocks > 0) {
    risks.push(`Risk-gate блоки: leverage=${leverageBlocks}, dailyDD=${ddBlocks}.`);
  }
  if (manualOpenFills.length > 0) {
    risks.push(`Обнаружены ручные открытия без системного submit: ${manualOpenFills.length}.`);
  }
  if (manualCloseFills.length > 0) {
    risks.push(`Обнаружены ручные закрытия без системного submit: ${manualCloseFills.length}.`);
  }

  if (net < 0) suggestions.push('Снизить агрессию: уменьшить leverage/размер до стабилизации equity-кривой.');
  if (winRate < 45 && closeFills.length >= 4) suggestions.push('Ужесточить фильтрацию входов: сократить TF/сигналы с худшей доходностью.');
  if (biasBlocks >= 10) suggestions.push('Пересмотреть частоту смены bias: много сигналов режется операторским bias.');
  if (manualOpenFills.length > 0 || manualCloseFills.length > 0) suggestions.push('Для ручных сделок: соблюдать bias/риск-профиль и по возможности логировать операции через API для полной аналитики.');
  if (suggestions.length === 0) suggestions.push('Сохранить текущую логику, но продолжать мониторинг drawdown и quality сигналов ежедневно.');

  const nowDate = new Date(now);
  const fromDate = new Date(cutoff);
  const localNow = getTzParts(nowDate, DAILY_ANALYTICS_TZ);

  return {
    generatedAt: nowDate.toISOString(),
    windowStart: fromDate.toISOString(),
    windowEnd: nowDate.toISOString(),
    localDayKey: localNow.dayKey,
    timezone: DAILY_ANALYTICS_TZ,
    fills: {
      total: recentFills.length,
      open: openFills.length,
      close: closeFills.length,
      executionOnlyOpen: executionOpenFills.length,
      manualOpenDetected: manualOpenFills.length,
      manualCloseDetected: manualCloseFills.length,
    },
    pnl: {
      realized,
      fees,
      net,
      winRatePct: Number(winRate.toFixed(2)),
      winners,
      losers,
    },
    bySymbol: topRows.sort((a, b) => Math.abs(b.realized) - Math.abs(a.realized)),
    bySource: [...bySource.values()].sort((a, b) => a.source.localeCompare(b.source)),
    execution: {
      signalDetected,
      signalRejected,
      ordersSubmitted,
      ordersAcked,
      ordersRejected,
    },
    riskBlocks: {
      bias: biasBlocks,
      leverage: leverageBlocks,
      dailyDD: ddBlocks,
    },
    biggestLoss,
    wins,
    risks,
    suggestions,
  };
}

async function buildAnalyticsHistorySummary(days = 3650): Promise<AnalyticsHistorySummary> {
  const now = Date.now();
  const safeDays = Math.max(1, Math.min(3650, Math.floor(days)));
  const cutoff = now - safeDays * 24 * 60 * 60_000;

  const [executionFills, db] = await Promise.all([
    exchange.getFills().catch(() => [] as FillEvent[]),
    getDb(),
  ]);

  // External connectors (e.g. Bybit read-only) are bounded by recent API windows.
  // Keep an external cutoff so "full history" still includes all externally available fills.
  const externalCutoff = Math.max(cutoff, now - 180 * 24 * 60 * 60_000);
  const externalFills = await collectExternalFills(db.data.settings, externalCutoff);

  const fills = [...executionFills, ...externalFills]
    .filter((f) => Date.parse(f.timestamp) >= cutoff)
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));

  const closeFills = fills.filter((f) => fillDirection(f).toLowerCase().startsWith('close '));
  const openFills = fills.filter((f) => fillDirection(f).toLowerCase().startsWith('open '));

  const realized = closeFills.reduce((sum, f) => sum + fillClosedPnl(f), 0);
  const fees = fills.reduce((sum, f) => sum + fillFee(f), 0);
  const net = realized - fees;

  const winners = closeFills.filter((f) => fillClosedPnl(f) > 0).length;
  const losers = closeFills.filter((f) => fillClosedPnl(f) < 0).length;
  const winRate = closeFills.length > 0 ? (winners / closeFills.length) * 100 : 0;

  const bySourceMap = new Map<string, AnalyticsHistorySourceSummary>();
  for (const fill of fills) {
    const source = fillSource(fill);
    const row = bySourceMap.get(source) ?? {
      source,
      fills: 0,
      openFills: 0,
      closeFills: 0,
      winners: 0,
      losers: 0,
      winRatePct: 0,
      realized: 0,
      fees: 0,
      net: 0,
    };

    const pnl = fillClosedPnl(fill);
    row.fills += 1;
    if (fillDirection(fill).toLowerCase().startsWith('open ')) row.openFills += 1;
    if (fillDirection(fill).toLowerCase().startsWith('close ')) {
      row.closeFills += 1;
      if (pnl > 0) row.winners += 1;
      if (pnl < 0) row.losers += 1;
    }
    row.realized += pnl;
    row.fees += fillFee(fill);
    row.net = row.realized - row.fees;
    row.winRatePct = row.closeFills > 0 ? Number(((row.winners / row.closeFills) * 100).toFixed(2)) : 0;

    bySourceMap.set(source, row);
  }

  const bySymbolMap = new Map<string, { symbol: string; realized: number; fills: number }>();
  for (const fill of fills) {
    const key = String(fill.symbol ?? '').toUpperCase();
    const row = bySymbolMap.get(key) ?? { symbol: key, realized: 0, fills: 0 };
    row.realized += fillClosedPnl(fill);
    row.fills += 1;
    bySymbolMap.set(key, row);
  }

  return {
    generatedAt: new Date(now).toISOString(),
    windowStart: new Date(cutoff).toISOString(),
    windowEnd: new Date(now).toISOString(),
    days: safeDays,
    totals: {
      fills: fills.length,
      openFills: openFills.length,
      closeFills: closeFills.length,
      winners,
      losers,
      winRatePct: Number(winRate.toFixed(2)),
      realized,
      fees,
      net,
    },
    bySource: [...bySourceMap.values()].sort((a, b) => a.source.localeCompare(b.source)),
    bySymbol: [...bySymbolMap.values()].sort((a, b) => Math.abs(b.realized) - Math.abs(a.realized)).slice(0, 40),
  };
}

function pct(part: number, whole: number): number {
  if (!Number.isFinite(part) || !Number.isFinite(whole) || whole <= 0) return 0;
  return Number(((part / whole) * 100).toFixed(2));
}

async function buildAnalyticsQualityMetrics(hours = 24 * 7): Promise<AnalyticsQualityMetrics> {
  const windowHours = Math.max(1, Math.min(24 * 365, Math.floor(hours)));
  const windowMs = windowHours * 60 * 60_000;
  const context = await buildDailyAnalyticsContext(windowMs);

  const signalBase = context.execution.signalDetected + context.execution.signalRejected;

  return {
    generatedAt: context.generatedAt,
    windowStart: context.windowStart,
    windowEnd: context.windowEnd,
    hours: windowHours,
    counts: {
      signalDetected: context.execution.signalDetected,
      signalRejected: context.execution.signalRejected,
      ordersSubmitted: context.execution.ordersSubmitted,
      ordersAcked: context.execution.ordersAcked,
      ordersRejected: context.execution.ordersRejected,
      openFills: context.fills.open,
      closeFills: context.fills.close,
      manualOpenDetected: context.fills.manualOpenDetected,
      manualCloseDetected: context.fills.manualCloseDetected,
    },
    rates: {
      signalToOrderPct: pct(context.execution.ordersSubmitted, signalBase),
      signalRejectPct: pct(context.execution.signalRejected, signalBase),
      submitToAckPct: pct(context.execution.ordersAcked, context.execution.ordersSubmitted),
      submitRejectPct: pct(context.execution.ordersRejected, context.execution.ordersSubmitted),
      ackToOpenFillPct: pct(context.fills.executionOnlyOpen, context.execution.ordersAcked),
      signalToOpenFillPct: pct(context.fills.open, signalBase),
      closeWinRatePct: context.pnl.winRatePct,
      manualOpenSharePct: pct(context.fills.manualOpenDetected, context.fills.open),
      manualCloseSharePct: pct(context.fills.manualCloseDetected, context.fills.close),
    },
  };
}

async function buildPostTradeAnalytics(hours = 24 * 7): Promise<PostTradeAnalyticsItem[]> {
  const windowHours = Math.max(1, Math.min(24 * 365, Math.floor(hours)));
  const cutoff = Date.now() - windowHours * 60 * 60_000;
  const [executionFills, db] = await Promise.all([
    exchange.getFills().catch(() => [] as FillEvent[]),
    getDb(),
  ]);
  const externalFills = await collectExternalFills(db.data.settings, cutoff);
  const fills = [...executionFills, ...externalFills]
    .filter((f) => Date.parse(f.timestamp) >= cutoff)
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  const events = (db.data.tradeEvents ?? []).filter((e) => Date.parse(e.timestamp) >= cutoff);

  const openQueues = new Map<string, FillEvent[]>();
  const items: PostTradeAnalyticsItem[] = [];

  for (const fill of fills) {
    const dir = fillDirection(fill).toLowerCase();
    const key = `${String(fill.symbol).toUpperCase()}::${String(fill.side).toLowerCase()}`;
    if (dir.startsWith('open ')) {
      const queue = openQueues.get(key) ?? [];
      queue.push(fill);
      openQueues.set(key, queue);
      continue;
    }
    if (!dir.startsWith('close ')) continue;

    const queue = openQueues.get(key) ?? [];
    const matchedOpen = queue.length > 0 ? queue.shift() : undefined;
    if (queue.length > 0) openQueues.set(key, queue); else openQueues.delete(key);

    const closeTs = Date.parse(fill.timestamp);
    const openTs = matchedOpen ? Date.parse(matchedOpen.timestamp) : NaN;
    const symbol = String(fill.symbol).toUpperCase();
    const side = fill.side === 'buy' ? 'long' : 'short';
    const nearbyEvents = events.filter((e) => {
      if (String(e.symbol).toUpperCase() !== symbol) return false;
      const eventTs = Date.parse(String(e.timestamp));
      if (!Number.isFinite(eventTs) || !Number.isFinite(closeTs)) return false;
      const left = Number.isFinite(openTs) ? openTs - 5 * 60_000 : closeTs - 24 * 60 * 60_000;
      return eventTs >= left && eventTs <= closeTs + 5 * 60_000;
    });

    const eventCounts = {
      signalDetected: nearbyEvents.filter((e) => e.type === 'signal_detected').length,
      signalRejected: nearbyEvents.filter((e) => e.type === 'signal_rejected').length,
      ordersSubmitted: nearbyEvents.filter((e) => e.type === 'order_submitted').length,
      ordersAcked: nearbyEvents.filter((e) => e.type === 'order_acknowledged').length,
      ordersRejected: nearbyEvents.filter((e) => e.type === 'order_rejected').length,
    };

    const manualOpenDetected = matchedOpen ? isManualOpenFill(matchedOpen, events) : false;
    const manualCloseDetected = isManualCloseFill(fill, events);
    const realized = fillClosedPnl(fill);
    const fees = fillFee(fill) + (matchedOpen ? fillFee(matchedOpen) : 0);
    const net = realized - fees;
    const notes: string[] = [];

    if (manualOpenDetected) notes.push('manual_open_detected');
    if (manualCloseDetected) notes.push('manual_close_detected');
    if (eventCounts.signalDetected === 0 && eventCounts.ordersSubmitted === 0) notes.push('no_system_signal_or_order_context');
    if (eventCounts.ordersRejected > 0) notes.push('order_rejection_seen_in_trade_window');
    if (!matchedOpen) notes.push('open_fill_not_matched_in_window');

    items.push({
      id: `${symbol}:${fill.timestamp}:${items.length + 1}`,
      symbol,
      source: fillSource(fill),
      side,
      openTimestamp: matchedOpen?.timestamp,
      closeTimestamp: fill.timestamp,
      holdMinutes: Number.isFinite(openTs) && Number.isFinite(closeTs) ? Number(((closeTs - openTs) / 60_000).toFixed(2)) : undefined,
      entryPrice: matchedOpen?.price,
      exitPrice: fill.price,
      size: fill.size,
      realizedPnlUsd: Number(realized.toFixed(6)),
      feesUsd: Number(fees.toFixed(6)),
      netPnlUsd: Number(net.toFixed(6)),
      outcome: net > 0 ? 'win' : net < 0 ? 'loss' : 'flat',
      manualOpenDetected,
      manualCloseDetected,
      eventCounts,
      notes,
    });
  }

  return items.sort((a, b) => b.closeTimestamp.localeCompare(a.closeTimestamp));
}

async function buildWeeklyAnalyticsReport(): Promise<{ text: string; summary: AnalyticsQualityMetrics & { bySource: Array<{ source: string; fills: number; realized: number; fees: number; net: number }>; bySymbol: Array<{ symbol: string; realized: number; fills: number }> } }> {
  const [quality, history, trades] = await Promise.all([
    buildAnalyticsQualityMetrics(24 * 7),
    buildAnalyticsHistorySummary(7),
    buildPostTradeAnalytics(24 * 7),
  ]);

  const winners = trades.filter((t) => t.outcome === 'win').length;
  const losers = trades.filter((t) => t.outcome === 'loss').length;
  const manualTrades = trades.filter((t) => t.manualOpenDetected || t.manualCloseDetected).length;

  const lines = [
    '🗓 Weekly trade / signal report (7d)',
    `Window: ${quality.windowStart} → ${quality.windowEnd}`,
    '',
    '📊 Outcome',
    `- Net: ${asUsd(history.totals.net)} | Realized: ${asUsd(history.totals.realized)} | Fees: ${asUsd(-history.totals.fees)}`,
    `- Fills: ${history.totals.fills} (open ${history.totals.openFills}, close ${history.totals.closeFills})`,
    `- Closed-trade win rate: ${asPct(quality.rates.closeWinRatePct)} (${winners}/${winners + losers || 0})`,
    `- Manual trade share: open ${asPct(quality.rates.manualOpenSharePct)}, close ${asPct(quality.rates.manualCloseSharePct)} (${manualTrades} trade windows touched manually)`,
    '',
    '🎯 Funnel / quality metrics',
    `- signal→order: ${asPct(quality.rates.signalToOrderPct)} | rejected at signal stage: ${asPct(quality.rates.signalRejectPct)}`,
    `- submit→ack: ${asPct(quality.rates.submitToAckPct)} | submit rejects: ${asPct(quality.rates.submitRejectPct)}`,
    `- ack→open fill: ${asPct(quality.rates.ackToOpenFillPct)} | signal→open fill: ${asPct(quality.rates.signalToOpenFillPct)}`,
    ...formatSymbolBreakdown('- Top symbols by realized:', history.bySymbol.map((x) => ({ symbol: x.symbol, value: x.realized })), 5),
    ...(
      history.bySource.length > 1
        ? ['- By source:', ...history.bySource.map((row) => `- ${row.source}: fills ${row.fills}, net ${asUsd(row.net)}`)]
        : []
    ),
  ];

  return {
    text: lines.join('\n').slice(0, 3900),
    summary: {
      ...quality,
      bySource: history.bySource.map((row) => ({ source: row.source, fills: row.fills, realized: row.realized, fees: row.fees, net: row.net })),
      bySymbol: history.bySymbol,
    },
  };
}

function renderDailyAnalyticsText(context: DailyAnalyticsContext): string {
  const lines: string[] = [
    '🧠 Daily AI trade analytics (24h)',
    `Window: ${context.windowStart} → ${context.windowEnd}`,
    `Local day: ${context.localDayKey} (${context.timezone})`,
    '',
    '📌 Сделки и P&L',
    `- Fills: ${context.fills.total} (open ${context.fills.open}, close ${context.fills.close})`,
    `- Realized: ${asUsd(context.pnl.realized)} | Fees: ${asUsd(-context.pnl.fees)} | Net: ${asUsd(context.pnl.net)}`,
    `- Win-rate: ${asPct(context.pnl.winRatePct)} (${context.pnl.winners}/${context.fills.close || 0})`,
    ...formatSymbolBreakdown('- По символам (realized):', context.bySymbol.map((x) => ({ symbol: x.symbol, value: x.realized }))),
    ...(
      context.bySource.length > 1
        ? [
            '- По источникам:',
            ...context.bySource.map((row) => `- ${row.source}: fills ${row.fills}, realized ${asUsd(row.realized)}, fees ${asUsd(-row.fees)}`),
          ]
        : []
    ),
    '',
    '📡 Сигналы и исполнение',
    `- Signal detected: ${context.execution.signalDetected}, rejected: ${context.execution.signalRejected}`,
    `- Orders submitted/acked/rejected: ${context.execution.ordersSubmitted}/${context.execution.ordersAcked}/${context.execution.ordersRejected}`,
    `- Risk blocks: bias=${context.riskBlocks.bias}, leverage=${context.riskBlocks.leverage}, dailyDD=${context.riskBlocks.dailyDD}`,
    '',
    '👤 Ручные операции',
    `- Manual opens detected: ${context.fills.manualOpenDetected}`,
    `- Manual closes detected: ${context.fills.manualCloseDetected}`,
  ];

  if (context.wins.length > 0) {
    lines.push('', '✅ Что было правильно', ...context.wins.map((w) => `- ${w}`));
  }
  if (context.risks.length > 0) {
    lines.push('', '⚠️ Ошибки / причины потерь', ...context.risks.map((r) => `- ${r}`));
  }
  lines.push('', '🎯 Предложения по оптимизации', ...context.suggestions.map((s, idx) => `${idx + 1}. ${s}`));

  return lines.join('\n').slice(0, 3900);
}

async function buildDailyAnalyticsText(): Promise<string | null> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyDailyAnalytics) return null;

  const context = await buildDailyAnalyticsContext();
  return renderDailyAnalyticsText(context);
}

function ensureAiMasterState(): Promise<{ insights: AiMasterInsight[]; qa: AiMasterQaItem[]; write: () => Promise<void> }> {
  return getDb().then((db) => {
    db.data.aiMasterInsights = Array.isArray(db.data.aiMasterInsights) ? db.data.aiMasterInsights : [];
    db.data.aiMasterQa = Array.isArray(db.data.aiMasterQa) ? db.data.aiMasterQa : [];
    return {
      insights: db.data.aiMasterInsights,
      qa: db.data.aiMasterQa,
      write: db.write,
    };
  });
}

let dailyAnalyticsTimer: NodeJS.Timeout | null = null;
let dailyAnalyticsBusy = false;

async function runDailyAnalyticsTick(): Promise<void> {
  if (dailyAnalyticsBusy) return;
  dailyAnalyticsBusy = true;
  try {
    const cfg = await getTelegramConfig();
    if (!cfg || !cfg.notifyDailyAnalytics) return;

    const local = getTzParts(new Date(), DAILY_ANALYTICS_TZ);
    const afterSchedule = local.hour > DAILY_ANALYTICS_HOUR || (local.hour === DAILY_ANALYTICS_HOUR && local.minute >= DAILY_ANALYTICS_MINUTE);
    if (!afterSchedule) return;

    const text = await buildDailyAnalyticsText();
    if (!text) return;

    await enqueueTelegramOutbox({
      category: 'analytics_daily',
      dedupeKey: `analytics-daily:${local.dayKey}`,
      text,
    });
  } catch (err) {
    logger.warn({ component: 'analytics-daily', err }, 'daily analytics tick failed');
  } finally {
    dailyAnalyticsBusy = false;
  }
}

function startDailyAnalyticsLoop(): void {
  if (dailyAnalyticsTimer) return;
  runDailyAnalyticsTick().catch((err) => logger.warn({ component: 'analytics-daily', err }, 'initial daily analytics tick failed'));
  dailyAnalyticsTimer = setInterval(() => {
    runDailyAnalyticsTick().catch((err) => logger.warn({ component: 'analytics-daily', err }, 'daily analytics tick failed'));
  }, DAILY_ANALYTICS_TICK_MS);
  dailyAnalyticsTimer.unref?.();
  logger.info({ component: 'analytics-daily', tz: DAILY_ANALYTICS_TZ, hour: DAILY_ANALYTICS_HOUR, minute: DAILY_ANALYTICS_MINUTE, intervalMs: DAILY_ANALYTICS_TICK_MS }, 'daily analytics loop started');
}

async function executePendingConfirmation(pendingId: string, actor: 'dashboard' | 'telegram'): Promise<{ ok: boolean; error?: string }> {
  const db = await getDb();
  const pending = db.data.pendingConfirmations.find((p) => p.id === pendingId);
  if (!pending) return { ok: false, error: 'pending_not_found' };

  const rules = rulesCache.getEffectiveRules();
  const normalizedSymbol = normalizeSymbol(pending.symbol);
  const side: 'buy' | 'sell' = pending.side === 'long' ? 'buy' : 'sell';
  const now = new Date().toISOString();

  // Risk check before submit
  const risk = await evaluateRiskGates({ emitAudit: false });
  if (!risk.canTrade) {
    updateExecutionIntent(db, pending.executionIntentId, { status: 'rejected' });
    reconcileRadarSignalOutcome(db, {
      pendingId,
      status: 'rejected',
      error: `risk_gate_blocked:${risk.blocks.join(',')}`,
    });
    appendTradeEvent(db.data, {
      symbol: normalizedSymbol,
      source: 'live',
      type: 'signal_rejected',
      timestamp: now,
      correlationId: `pending-${pending.id}`,
      side: pending.side,
      price: pending.price,
      quantity: pending.size,
      reason: 'pending_rejected_risk_gate',
      payload: { blocks: risk.blocks.join(','), actor },
    });
    await db.write();
    await notifySignalRejectedEvent({
      symbol: normalizedSymbol,
      source: `pending:${actor}`,
      reason: 'pending_rejected_risk_gate',
      blocks: risk.blocks.join(','),
    }).catch(() => undefined);
    return { ok: false, error: `risk_gate_blocked:${risk.blocks.join(',')}` };
  }

  // leverage
  if (Number.isFinite(pending.leverage) && pending.leverage > 0) {
    const lev = Math.min(pending.leverage, rules.maxLeverage);
    await exchange.setLeverage(normalizedSymbol, lev);
  }

  const correlationId = `pending-confirm-${pending.id}`;
  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: now,
    correlationId,
    side: pending.side,
    price: pending.price,
    quantity: pending.size,
    reason: 'pending_confirm_submit',
    payload: { actor, strategy: pending.strategy, timeframe: pending.timeframe },
  });

  const withTimeout = async <T>(promise: Promise<T>, timeoutMs: number, tag: string): Promise<T> => {
    let timer: NodeJS.Timeout | null = null;
    try {
      return await Promise.race([
        promise,
        new Promise<T>((_, reject) => {
          timer = setTimeout(() => reject(new Error(`${tag}_timeout`)), timeoutMs);
        }),
      ]);
    } finally {
      if (timer) clearTimeout(timer);
    }
  };

  const computeSizeAtOpen = async (price: number): Promise<AllocationSizingOutcome> => {
    const account = await withTimeout(exchange.getAccountState(), 5000, 'confirm_account_state');
    const equityUsd = account?.equityUsd ?? 0;
    const availableUsd = account?.availableUsd ?? 0;

    let sizeDecimals = 6;
    try {
      const meta = await withTimeout(exchange.getInstrumentMeta(normalizedSymbol), 3000, 'confirm_instrument_meta');
      if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
    } catch {
      // best effort
    }

    return computeAllocationSize({
      symbol: normalizedSymbol,
      price,
      equityUsd,
      availableUsd,
      rules,
      sizeDecimals,
    });
  };

  const placeWithRetry = async () => {
    const attemptPrices: number[] = [pending.price];
    let lastAck: Awaited<ReturnType<typeof exchange.placeLimitOrder>> | null = null;
    let lastSize = pending.size;

    for (let attempt = 0; attempt < attemptPrices.length; attempt++) {
      const price = attemptPrices[attempt];

      try {
        const sizing = await computeSizeAtOpen(price);
        if (!sizing.ok) {
          return {
            ack: { ok: false, error: `allocation_sizing_failed:${sizing.reason}` },
            usedPrice: price,
            usedSize: 0,
          };
        }

        const risk = await withTimeout(evaluateRiskGates({ emitAudit: false }), 5000, 'confirm_risk_gates');
        if (!risk.canTrade) {
          return {
            ack: { ok: false, error: `risk_gate_blocked:${risk.blocks.join(',')}` },
            usedPrice: price,
            usedSize: 0,
          };
        }

        const gross = await checkPortfolioGrossCap({ symbol: normalizedSymbol, price, size: sizing.size, effectiveRules: rules, riskCheck: risk });
        if (!gross.ok) {
          return {
            ack: { ok: false, error: 'portfolio_gross_cap_exceeded' },
            usedPrice: price,
            usedSize: 0,
          };
        }

        lastSize = sizing.size;
        const ack = await withTimeout(exchange.placeLimitOrder({
          symbol: normalizedSymbol,
          side,
          price,
          size: sizing.size,
          reduceOnly: false,
          clientOrderId: `${correlationId}-${attempt + 1}`,
        }), 10_000, 'confirm_place_limit_order');

        if (ack.ok) return { ack, usedPrice: price, usedSize: sizing.size };
        lastAck = ack;

        const err = String(ack.error ?? '').toLowerCase();
        const retryablePriceError = err.includes('tick size') || err.includes('divisible') || err.includes('invalid price') || err.includes('tofixed');
        if (attempt === 0 && retryablePriceError) {
          const mid = await fetchLiveMid(normalizedSymbol);
          if (mid && Number.isFinite(mid) && mid > 0) {
            attemptPrices.push(mid);
            logger.warn({ component: 'pending-confirmation', pendingId, attempt: attempt + 1, originalPrice: price, fallbackMid: mid, err: ack.error }, 'retrying pending confirmation with fresh mid price');
            continue;
          }
        }
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'confirm_place_order_failed';
        logger.warn({ component: 'pending-confirmation', pendingId, attempt: attempt + 1, symbol: normalizedSymbol, err: msg }, 'pending confirmation attempt failed');
        lastAck = { ok: false, error: msg } as Awaited<ReturnType<typeof exchange.placeLimitOrder>>;
      }
    }

    return { ack: lastAck ?? { ok: false, error: 'exchange_rejected' }, usedPrice: pending.price, usedSize: lastSize };
  };

  const { ack, usedPrice, usedSize } = await placeWithRetry();

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: pending.side,
    price: usedPrice,
    quantity: usedSize,
    reason: ack.ok ? 'pending_confirm_ack' : 'pending_confirm_rejected',
    payload: { orderId: ack.orderId ?? null, status: ack.status ?? null, error: ack.error ?? null, actor, usedPrice, usedSize },
  });

  if (!ack.ok) {
    updateExecutionIntent(db, pending.executionIntentId, { status: 'rejected' });
    reconcileRadarSignalOutcome(db, {
      pendingId,
      status: 'rejected',
      error: ack.error ?? 'exchange_rejected',
    });
    await db.write();
    await notifyOrderRejectedEvent({
      symbol: normalizedSymbol,
      source: `pending:${actor}`,
      error: ack.error ?? 'exchange_rejected',
    }).catch(() => undefined);
    return { ok: false, error: ack.error ?? 'exchange_rejected' };
  }

  reconcileRadarSignalOutcome(db, {
    pendingId,
    orderId: ack.orderId,
    status: 'auto_order_placed',
  });
  updateExecutionIntent(db, pending.executionIntentId, { status: 'auto_order_placed', orderId: ack.orderId, pendingId });
  db.data.pendingConfirmations = db.data.pendingConfirmations.filter((p) => p.id !== pendingId);

  const tpSl = resolveTpSlDefaults(usedPrice, side, undefined, undefined);
  if (tpSl) {
    try {
      await placeTpSlTriggerOrders(normalizedSymbol, side, usedSize, tpSl, correlationId, usedPrice, pending.timeframe);
    } catch {
      // best effort
    }
  }

  await db.write();

  try {
    await notifyTradeOpen({ symbol: normalizedSymbol, side, price: usedPrice, size: usedSize, source: `pending:${actor}` });
  } catch (error) {
    logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
  }

  return { ok: true };
}

async function rejectPendingConfirmation(pendingId: string, actor: 'dashboard' | 'telegram'): Promise<{ ok: boolean; error?: string }> {
  const db = await getDb();
  const pending = db.data.pendingConfirmations.find((p) => p.id === pendingId);
  const before = db.data.pendingConfirmations.length;
  db.data.pendingConfirmations = db.data.pendingConfirmations.filter((p) => p.id !== pendingId);
  if (db.data.pendingConfirmations.length === before) {
    return { ok: false, error: 'pending_not_found' };
  }
  reconcileRadarSignalOutcome(db, {
    pendingId,
    status: 'rejected',
    error: 'pending_confirmation_rejected',
  });
  updateExecutionIntent(db, pending?.executionIntentId, { status: 'rejected', pendingId });
  appendTradeEvent(db.data, {
    symbol: LIVE_SYMBOL,
    source: 'live',
    type: 'signal_rejected',
    timestamp: new Date().toISOString(),
    correlationId: `pending-reject-${pendingId}`,
    reason: 'pending_confirmation_rejected',
    payload: { pendingId, actor },
  });
  await db.write();
  return { ok: true };
}

let telegramUpdateTimer: NodeJS.Timeout | null = null;
let telegramUpdateBusy = false;

async function answerTelegramCallback(token: string, callbackQueryId: string, text?: string): Promise<void> {
  await fetch(`https://api.telegram.org/bot${token}/answerCallbackQuery`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ callback_query_id: callbackQueryId, ...(text ? { text } : {}) }),
  }).catch(() => undefined);
}

async function runTelegramUpdateTick(): Promise<void> {
  if (telegramUpdateBusy) return;
  telegramUpdateBusy = true;
  try {
    const cfg = await getTelegramConfig();
    if (!cfg) return;

    const db = await getDb();
    const updateOffset = Math.max(0, Number(db.data.settings.telegramNotify?.updateOffset ?? 0));

    const response = await fetch(`https://api.telegram.org/bot${cfg.token}/getUpdates`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ timeout: 20, offset: updateOffset, allowed_updates: ['message', 'callback_query'] }),
    });
    if (!response.ok) return;

    const payload = await response.json() as { ok?: boolean; result?: any[] };
    if (!payload.ok || !Array.isArray(payload.result) || payload.result.length === 0) return;

    let nextOffset = updateOffset;

    for (const update of payload.result) {
      nextOffset = Math.max(nextOffset, Number(update.update_id || 0) + 1);

      const msg = update.message;
      const cb = update.callback_query;
      const chatIdRaw = cb?.message?.chat?.id ?? msg?.chat?.id;
      if (String(chatIdRaw ?? '') !== String(cfg.chatId)) continue;

      if (msg?.text) {
        const text = String(msg.text).trim();
        if (text.startsWith('/confirm')) {
          const id = text.split(/\s+/)[1];
          if (!id) {
            await sendTelegramText('Usage: /confirm <pending-id>');
            continue;
          }
          const result = await executePendingConfirmation(id, 'telegram');
          await sendTelegramText(result.ok ? `✅ Confirmed: ${id}` : `❌ Confirm failed: ${id} (${result.error})`);
        } else if (text.startsWith('/reject')) {
          const id = text.split(/\s+/)[1];
          if (!id) {
            await sendTelegramText('Usage: /reject <pending-id>');
            continue;
          }
          const result = await rejectPendingConfirmation(id, 'telegram');
          await sendTelegramText(result.ok ? `🗑 Rejected: ${id}` : `❌ Reject failed: ${id} (${result.error})`);
        } else if (text === '/pending') {
          const pending = await loadPendingConfirmations();
          if (!pending.length) {
            await sendTelegramText('No pending confirmations.');
          } else {
            const lines = pending.slice(0, 10).map((p) => `${p.id} • ${p.symbol} ${p.side.toUpperCase()} • ${p.strategy}/${p.timeframe} • px ${p.price}`);
            await sendTelegramText(`Pending confirmations:\n${lines.join('\n')}`);
          }
        }
      }

      if (cb?.id && cb?.data) {
        const data = String(cb.data);
        if (data.startsWith('confirm:')) {
          const id = data.slice('confirm:'.length);
          const result = await executePendingConfirmation(id, 'telegram');
          await answerTelegramCallback(cfg.token, cb.id, result.ok ? 'Confirmed' : `Failed: ${result.error ?? 'error'}`);
          await sendTelegramText(result.ok ? `✅ Confirmed: ${id}` : `❌ Confirm failed: ${id} (${result.error})`);
        } else if (data.startsWith('reject:')) {
          const id = data.slice('reject:'.length);
          const result = await rejectPendingConfirmation(id, 'telegram');
          await answerTelegramCallback(cfg.token, cb.id, result.ok ? 'Rejected' : `Failed: ${result.error ?? 'error'}`);
          await sendTelegramText(result.ok ? `🗑 Rejected: ${id}` : `❌ Reject failed: ${id} (${result.error})`);
        }
      }
    }

    if (nextOffset !== updateOffset) {
      db.data.settings.telegramNotify = db.data.settings.telegramNotify ?? {
        botToken: '',
        chatId: '',
        notifyOpen: true,
        notifyTp: true,
        notifySl: true,
        notifyManualConfirm: true,
        notifyDailyAnalytics: true,
        notifySignalRejected: false,
        notifyOrderRejected: false,
        notifyPositionClosed: false,
      };
      db.data.settings.telegramNotify.updateOffset = nextOffset;
      await db.write();
    }
  } catch (err) {
    logger.warn({ component: 'telegram', err }, 'telegram update tick failed');
  } finally {
    telegramUpdateBusy = false;
  }
}

function startTelegramUpdateLoop(): void {
  if (telegramUpdateTimer) return;
  runTelegramUpdateTick().catch((err) => logger.warn({ component: 'telegram', err }, 'initial telegram tick failed'));
  telegramUpdateTimer = setInterval(() => {
    runTelegramUpdateTick().catch((err) => logger.warn({ component: 'telegram', err }, 'telegram tick failed'));
  }, 5000);
  telegramUpdateTimer.unref?.();
}

// ─── Owner Auth Middleware ────────────────────────────────────────────

function ownerAuth(req: Request, res: Response, next: NextFunction) {
  // If no auth token configured, skip auth (dev mode)
  if (!OWNER_AUTH_TOKEN && !OWNER_HMAC_SECRET) {
    return next();
  }

  // Bearer token check
  const authHeader = req.headers.authorization;
  if (authHeader) {
    const token = authHeader.replace(/^Bearer\s+/i, '');
    if (OWNER_AUTH_TOKEN && token === OWNER_AUTH_TOKEN) {
      return next();
    }
  }

  // Query param token check
  const queryToken = req.query.token as string | undefined;
  if (OWNER_AUTH_TOKEN && queryToken === OWNER_AUTH_TOKEN) {
    return next();
  }

  // HMAC verification: ?ts=<unix_s>&sig=<hex>
  if (OWNER_HMAC_SECRET) {
    const ts = req.query.ts as string | undefined;
    const sig = req.query.sig as string | undefined;
    if (ts && sig) {
      const age = Math.abs(Date.now() / 1000 - Number(ts));
      if (age < 300) { // 5 min window
        const expected = crypto.createHmac('sha256', OWNER_HMAC_SECRET).update(ts).digest('hex');
        if (crypto.timingSafeEqual(Buffer.from(sig, 'hex'), Buffer.from(expected, 'hex'))) {
          return next();
        }
      }
    }
  }

  logRiskGateAudit({ gate: 'auth', passed: false, reason: 'auth_required' });
  return res.status(401).json({ ok: false, errorCode: 'auth_required' as TradingErrorCode, error: 'Authentication required for live trading endpoints' });
}

// ─── Risk Gate Helpers ────────────────────────────────────────────────

/** In-memory risk gate audit buffer, flushed to DB periodically */
const riskAuditBuffer: RiskGateAuditEntry[] = [];

const QUIET_RISK_GATE_REASONS = new Set(['operator_bias_block']);

function logRiskGateAudit(entry: Omit<RiskGateAuditEntry, 'timestamp'>) {
  const full: RiskGateAuditEntry = { ...entry, timestamp: new Date().toISOString() };
  riskAuditBuffer.push(full);

  // Keep persistent DB audit for all checks, but avoid noisy success logs by default.
  if (!full.passed) {
    if (full.reason && QUIET_RISK_GATE_REASONS.has(full.reason)) {
      if (process.env.RISK_GATE_VERBOSE === '1') {
        logger.info({ component: 'risk-gate', gate: full.gate, passed: full.passed, reason: full.reason }, 'risk gate check blocked (expected)');
      }
    } else {
      logger.warn({ component: 'risk-gate', gate: full.gate, passed: full.passed, reason: full.reason ?? undefined }, 'risk gate check failed');
    }
  } else if (process.env.RISK_GATE_VERBOSE === '1') {
    logger.info({ component: 'risk-gate', gate: full.gate, passed: full.passed, reason: full.reason ?? undefined }, 'risk gate check');
  }
}

async function flushRiskAudit() {
  if (!riskAuditBuffer.length) return;
  const db = await getDb();
  const batch = riskAuditBuffer.splice(0, riskAuditBuffer.length);
  db.data.riskGateAudit.push(...batch);
  // Keep last 10000 entries
  if (db.data.riskGateAudit.length > 10000) {
    db.data.riskGateAudit = db.data.riskGateAudit.slice(-10000);
  }
  await db.write();
}

// Flush audit every 30s
const auditFlushTimer = setInterval(() => { flushRiskAudit().catch((err) => logger.warn({ component: 'audit', err }, 'audit flush failed')); }, 30_000);
auditFlushTimer.unref();

function todayDateStr(): string {
  return new Date().toISOString().slice(0, 10);
}

async function getOrCreateDDBaseline(equityUsd: number, meta?: { equitySource?: string; riskValid?: boolean }): Promise<DailyDDBaseline> {
  const today = todayDateStr();
  const db = await getDb();
  let baseline = db.data.dailyDDBaselines.find(b => b.date === today);
  if (!baseline) {
    baseline = {
      date: today,
      startEquityUsd: equityUsd,
      updatedAt: new Date().toISOString(),
      equitySource: meta?.equitySource,
      riskValid: meta?.riskValid ?? true,
    };
    db.data.dailyDDBaselines.push(baseline);
    if (db.data.dailyDDBaselines.length > 90) {
      db.data.dailyDDBaselines = db.data.dailyDDBaselines.slice(-90);
    }
    await db.write();
  } else if ((meta?.equitySource && baseline.equitySource !== meta.equitySource) || (typeof meta?.riskValid === 'boolean' && baseline.riskValid !== meta.riskValid)) {
    baseline.equitySource = meta?.equitySource ?? baseline.equitySource;
    baseline.riskValid = meta?.riskValid ?? baseline.riskValid;
    baseline.updatedAt = new Date().toISOString();
    await db.write();
  }
  return baseline;
}

function msUntilNextUtcMidnight(now = new Date()): number {
  const nextMidnightUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0, 0);
  return Math.max(1000, nextMidnightUtc - now.getTime());
}

let drawdownMidnightBaselineTimer: NodeJS.Timeout | null = null;
let drawdownMidnightBaselineBusy = false;

async function seedNextUtcDailyDrawdownBaseline(reason = 'utc_midnight_seed') {
  if (drawdownMidnightBaselineBusy) return;
  drawdownMidnightBaselineBusy = true;
  try {
    const account = await exchange.getAccountState();
    if (!isRiskUsableAccountSnapshot(account)) {
      logger.warn({
        component: 'risk-gate',
        reason,
        equityQuality: account?.equityQuality,
        equitySource: account?.equitySource,
      }, 'daily drawdown midnight baseline skipped because risk-valid equity is unavailable');
      return;
    }

    const baseline = await getOrCreateDDBaseline(account?.equityUsd ?? 0, {
      equitySource: account?.equitySource,
      riskValid: account?.equityValidForRisk,
    });
    logger.info({ component: 'risk-gate', reason, date: baseline.date, startEquityUsd: baseline.startEquityUsd, equitySource: baseline.equitySource }, 'daily drawdown baseline seeded');
  } catch (error) {
    logger.warn({ component: 'risk-gate', err: error }, 'daily drawdown midnight baseline seed failed');
  } finally {
    drawdownMidnightBaselineBusy = false;
  }
}

function startDailyDrawdownMidnightReset() {
  if (drawdownMidnightBaselineTimer) return;

  const arm = () => {
    const delayMs = msUntilNextUtcMidnight();
    drawdownMidnightBaselineTimer = setTimeout(() => {
      seedNextUtcDailyDrawdownBaseline().finally(() => {
        if (drawdownMidnightBaselineTimer) {
          clearTimeout(drawdownMidnightBaselineTimer);
          drawdownMidnightBaselineTimer = null;
        }
        arm();
      });
    }, delayMs);
    drawdownMidnightBaselineTimer.unref?.();
  };

  arm();
  logger.info({ component: 'risk-gate', nextResetInMs: msUntilNextUtcMidnight() }, 'daily drawdown midnight reset scheduled');
}

interface RiskCheckResult {
  canTrade: boolean;
  dailyDDPct: number;
  dailyDDLimitPct: number;
  portfolioLeverage: number;
  blocks: string[];
  equityUsd: number;
  baselineEquityUsd: number;
  equityValidForRisk: boolean;
  equityQuality?: 'full' | 'partial' | 'unavailable';
  equitySource?: string;
}

interface EmergencyCloseResult {
  flat: boolean;
  verified: boolean;
  ordersCleared: boolean;
  rounds: number;
  remainingPositions: PositionSnapshot[];
  remainingOrders: OrderSnapshot[];
  issues: string[];
}

function isRiskUsableAccountSnapshot(account: Awaited<ReturnType<typeof exchange.getAccountState>>): boolean {
  return Boolean(account && account.equityValidForRisk && Number.isFinite(account.equityUsd ?? NaN) && (account.equityUsd ?? 0) > 0);
}

async function evaluateRiskGates(options?: { emitAudit?: boolean }): Promise<RiskCheckResult> {
  const emitAudit = options?.emitAudit ?? true;
  const blocks: string[] = [];

  const [account, positions] = await Promise.all([
    exchange.getAccountState(),
    exchange.getOpenPositions()
  ]);

  const equityUsd = account?.equityUsd ?? 0;
  const effectiveRules = rulesCache.getEffectiveRules();
  const equityValidForRisk = isRiskUsableAccountSnapshot(account);

  let baselineEquityUsd = 0;
  let ddPct = 0;

  if (equityValidForRisk) {
    const baseline = await getOrCreateDDBaseline(equityUsd, {
      equitySource: account?.equitySource,
      riskValid: account?.equityValidForRisk,
    });
    baselineEquityUsd = baseline.startEquityUsd;
    ddPct = baseline.startEquityUsd > 0
      ? ((baseline.startEquityUsd - equityUsd) / baseline.startEquityUsd) * 100
      : 0;

    if (ddPct >= effectiveRules.dailyDDLimitPct) {
      blocks.push('daily_loss_limit_exceeded');
      if (emitAudit) {
        logRiskGateAudit({ gate: 'daily_dd', passed: false, reason: 'daily_loss_limit_exceeded', details: { ddPct: Number(ddPct.toFixed(2)), limit: effectiveRules.dailyDDLimitPct, equityUsd, baselineEquityUsd: baseline.startEquityUsd, equitySource: account?.equitySource } });
      }
    } else if (emitAudit) {
      logRiskGateAudit({ gate: 'daily_dd', passed: true, details: { ddPct: Number(ddPct.toFixed(2)), equitySource: account?.equitySource } });
    }
  } else {
    blocks.push('risk_check_unavailable');
    if (emitAudit) {
      logRiskGateAudit({ gate: 'daily_dd', passed: false, reason: 'risk_check_unavailable', details: { equityQuality: account?.equityQuality, equitySource: account?.equitySource, equityUsd } });
    }
  }

  let totalNotional = 0;
  for (const pos of positions) {
    const notional = (pos.entryPrice ?? pos.markPrice ?? 0) * pos.size;
    totalNotional += notional;
  }
  const portfolioLeverage = equityUsd > 0 ? totalNotional / equityUsd : 0;

  if (equityValidForRisk && portfolioLeverage > effectiveRules.portfolioLeverageCap) {
    blocks.push('leverage_limit_exceeded');
    if (emitAudit) {
      logRiskGateAudit({ gate: 'leverage_cap', passed: false, reason: 'leverage_limit_exceeded', details: { portfolioLeverage: Number(portfolioLeverage.toFixed(2)), cap: effectiveRules.portfolioLeverageCap } });
    }
  } else if (emitAudit) {
    logRiskGateAudit({ gate: 'leverage_cap', passed: true, details: { portfolioLeverage: Number(portfolioLeverage.toFixed(2)) } });
  }

  return {
    canTrade: blocks.length === 0,
    dailyDDPct: Number(ddPct.toFixed(2)),
    dailyDDLimitPct: effectiveRules.dailyDDLimitPct,
    portfolioLeverage: Number(portfolioLeverage.toFixed(2)),
    blocks,
    equityUsd,
    baselineEquityUsd,
    equityValidForRisk,
    equityQuality: account?.equityQuality,
    equitySource: account?.equitySource,
  };
}

const emergencyCloseLock = {
  running: false,
  hardStopActive: false
};

const ddLock: DdLockState = {
  active: false,
  activatedAt: '',
  triggeredDailyDDPct: undefined as number | undefined,
  dailyDDLimitPct: undefined as number | undefined,
  triggeredEquityUsd: undefined as number | undefined,
  baselineEquityUsd: undefined as number | undefined,
  emergencyCloseNotificationSent: false as boolean,
  emergencyCloseSettledAt: undefined as string | undefined,
  ...loadPersistedDdLockState(),
};

function getDdLockState() {
  return {
    active: ddLock.active,
    activatedAt: ddLock.activatedAt || undefined,
    triggeredDailyDDPct: ddLock.triggeredDailyDDPct,
    dailyDDLimitPct: ddLock.dailyDDLimitPct,
    triggeredEquityUsd: ddLock.triggeredEquityUsd,
    baselineEquityUsd: ddLock.baselineEquityUsd,
    emergencyCloseNotificationSent: ddLock.emergencyCloseNotificationSent,
    emergencyCloseSettledAt: ddLock.emergencyCloseSettledAt || undefined,
  };
}

const WATCHDOG_IDLE_LOG_INTERVAL_MS = 5 * 60 * 1000;
const watchdogLogState: Record<string, number> = {};

function shouldLogWatchdog(key: string, intervalMs = WATCHDOG_IDLE_LOG_INTERVAL_MS): boolean {
  const now = Date.now();
  const last = watchdogLogState[key] ?? 0;
  if (now - last < intervalMs) return false;
  watchdogLogState[key] = now;
  return true;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function emergencyClosePrice(
  pos: { side: 'long' | 'short'; markPrice?: number; entryPrice?: number },
  closeSide: 'buy' | 'sell',
  topOfBook?: { bid: number; ask: number } | null,
): number {
  const mark = pos.markPrice ?? pos.entryPrice ?? 0;
  const bookPrice = closeSide === 'sell' ? topOfBook?.bid : topOfBook?.ask;
  const base = Number.isFinite(bookPrice ?? NaN) && (bookPrice ?? 0) > 0 ? Number(bookPrice) : mark;

  if (!Number.isFinite(base) || base <= 0) {
    return closeSide === 'sell' ? 1 : 999_999;
  }

  const price = closeSide === 'sell' ? base * 0.985 : base * 1.015;
  return Math.max(0.00000001, Number(price.toFixed(8)));
}

/** Close all positions emergency (daily DD hard stop). Best effort but retried by watchdog every few seconds until flat. */
function formatEmergencyClosePosition(pos: PositionSnapshot): string {
  const side = pos.side.toUpperCase();
  const size = Number.isFinite(pos.size) ? pos.size : 0;
  const entry = Number.isFinite(pos.entryPrice ?? NaN) ? ` @ ${Number(pos.entryPrice).toFixed(2)}` : '';
  const mark = Number.isFinite(pos.markPrice ?? NaN) ? ` mark ${Number(pos.markPrice).toFixed(2)}` : '';
  return `- ${pos.symbol} ${side} ${size}${entry}${mark}`;
}

function formatEmergencyCloseIssue(issue: string): string {
  return `- ${issue}`;
}

async function notifyEmergencyCloseResult({
  reason,
  flat,
  verified,
  ordersCleared,
  rounds,
  remainingPositions,
  remainingOrders,
  issues,
}: {
  reason: string;
  flat: boolean;
  verified: boolean;
  ordersCleared: boolean;
  rounds: number;
  remainingPositions: Array<{ symbol?: string; size?: number; side?: string }>;
  remainingOrders: Array<{ symbol?: string; id?: string }>;
  issues: string[];
  }) {
  if (ddLock.emergencyCloseNotificationSent) return;

  const limitPct = ddLock.dailyDDLimitPct ?? rulesCache.getEffectiveRules().dailyDDLimitPct;
  const triggeredPct = ddLock.triggeredDailyDDPct ?? limitPct;
  const limitText = `limit=${limitPct.toFixed(2)}%`;
  const triggeredText = `triggered=${triggeredPct.toFixed(2)}%`;

  if (flat && verified && ordersCleared) {
    const text = `Emergency close completed: ${limitText}, ${triggeredText}, rounds=${rounds}. Positions are flat and open orders are cleared.`;
    const cfg = await getTelegramConfig();
    if (!cfg) return;
    const key = await getEmergencyCloseNotificationKey();
    const queued = await enqueueTelegramOutbox({
      category: 'system',
      text,
      dedupeKey: key,
    });
    if (queued.queued || queued.id) {
      ddLock.emergencyCloseNotificationSent = true;
    }
    return;
  }

  const remainingText = remainingPositions.length > 0
    ? ` Remaining positions: ${remainingPositions.map((p) => `${p.symbol ?? 'unknown'}:${p.side ?? 'na'}:${p.size ?? 'na'}`).join(', ')}`
    : '';
  const remainingOrdersText = remainingOrders.length > 0
    ? ` Remaining orders: ${remainingOrders.map((o) => `${o.symbol ?? 'unknown'}:${o.id ?? 'na'}`).join(', ')}`
    : '';
  const issuesText = issues.length > 0 ? ` Issues: ${issues.join('; ')}` : '';
  const text = [`Emergency close FAILED:`, limitText, triggeredText, `rounds=${rounds}`, remainingText.trim(), remainingOrdersText.trim(), issuesText.trim()]
    .filter(Boolean)
    .join(' ');
  const cfg = await getTelegramConfig();
  if (!cfg) return;
  const key = await getEmergencyCloseNotificationKey();
  await enqueueTelegramOutbox({
    category: 'system',
    text,
    dedupeKey: `${key}:failed`,
  });
}

async function emergencyCloseAll(reason = 'daily_loss_limit_exceeded'): Promise<EmergencyCloseResult> {
  if (emergencyCloseLock.running) {
    return {
      flat: false,
      verified: false,
      ordersCleared: false,
      rounds: 0,
      remainingPositions: [],
      remainingOrders: [],
      issues: ['emergency_close_already_running'],
    };
  }
  emergencyCloseLock.running = true;
  const issues: string[] = [];
  let rounds = 0;
  let remainingPositions: PositionSnapshot[] = [];
  let remainingOrders: OrderSnapshot[] = [];
  let flat = false;
  let verified = false;
  let ordersCleared = false;
  const isWatchdogReason = reason.endsWith('_watchdog');
  const maxRounds = 5;
  try {
    if (!isWatchdogReason || shouldLogWatchdog(`emergency-start:${reason}`)) {
      logger.error({ component: 'risk-gate', reason }, 'EMERGENCY: canceling open orders and closing positions with IOC reduce-only orders');
    }

    try {
      await exchange.cancelAll();
    } catch (cancelErr) {
      issues.push(`cancelAll failed: ${cancelErr instanceof Error ? cancelErr.message : String(cancelErr)}`);
      logger.warn({ component: 'risk-gate', reason, err: cancelErr }, 'failed to cancel open orders during emergency close');
    }

    try {
      remainingOrders = await exchange.getOpenOrders();
      ordersCleared = remainingOrders.length === 0;
      if (!ordersCleared) {
        issues.push(`open orders remain after cancelAll: ${remainingOrders.length}`);
      }
    } catch (ordersErr) {
      issues.push(`open order check failed: ${ordersErr instanceof Error ? ordersErr.message : String(ordersErr)}`);
      logger.warn({ component: 'risk-gate', reason, err: ordersErr }, 'failed to verify open orders during emergency close');
    }

    let initialPositions: PositionSnapshot[] | null = null;
    try {
      initialPositions = await exchange.getOpenPositions();
      if (initialPositions) {
        remainingPositions = initialPositions;
      }
    } catch (readErr) {
      issues.push(`read positions failed: ${readErr instanceof Error ? readErr.message : String(readErr)}`);
      logger.warn({ component: 'risk-gate', reason, err: readErr }, 'failed to read positions during emergency close');
    }

    if (initialPositions && initialPositions.length === 0) {
      flat = true;
      verified = true;
      if (shouldLogWatchdog('already-flat')) {
        logger.warn({ component: 'risk-gate', reason }, 'emergency close: no open positions remain after canceling open orders');
      }
    }

    if (initialPositions && initialPositions.length > 0) {
      for (let round = 0; round < maxRounds; round++) {
        rounds = round + 1;
        let positions: PositionSnapshot[] = [];
        try {
          positions = await exchange.getOpenPositions();
        } catch (readErr) {
          issues.push(`position read failed on round ${rounds}: ${readErr instanceof Error ? readErr.message : String(readErr)}`);
          logger.warn({ component: 'risk-gate', reason, round: rounds, err: readErr }, 'failed to read positions during emergency close round');
          await sleep(700);
          continue;
        }
        if (positions.length === 0) break;

        remainingPositions = positions;

        for (const pos of positions) {
          const closeSide: 'buy' | 'sell' = pos.side === 'long' ? 'sell' : 'buy';
          const topOfBook = typeof exchange.getTopOfBook === 'function'
            ? await exchange.getTopOfBook(pos.symbol).catch(() => null)
            : null;
          const price = emergencyClosePrice(pos, closeSide, topOfBook);

          try {
            const ack = await exchange.placeLimitOrder({
              symbol: pos.symbol,
              side: closeSide,
              price,
              size: pos.size,
              reduceOnly: true,
              timeInForce: 'Ioc',
              clientOrderId: `emergency-${Date.now()}-${nanoid(6)}`
            });

            if (!ack.ok) {
              issues.push(`close submit ack not ok for ${pos.symbol}: ${ack.error ?? ack.status ?? 'unknown'}`);
              logger.warn({ component: 'risk-gate', symbol: pos.symbol, side: pos.side, price, ack }, 'emergency IOC close not fully acknowledged');
            }

            if (!isWatchdogReason || shouldLogWatchdog(`emergency-submit:${reason}:${pos.symbol}`)) {
              logger.warn({ component: 'risk-gate', symbol: pos.symbol, side: pos.side, size: pos.size, closeReason: reason, timeInForce: 'IOC' }, 'position close submitted (emergency)');
            }
          } catch (error) {
            issues.push(`close failed for ${pos.symbol}: ${error instanceof Error ? error.message : String(error)}`);
            if (!isWatchdogReason || shouldLogWatchdog(`emergency-failed:${reason}:${pos.symbol}`)) {
              logger.error({ component: 'risk-gate', symbol: pos.symbol, err: error }, 'failed to emergency-close position');
            }
          }
        }

        await sleep(700);
      }
    }

    try {
      remainingPositions = await exchange.getOpenPositions();
      verified = true;
    } catch (finalReadErr) {
      issues.push(`final position check failed: ${finalReadErr instanceof Error ? finalReadErr.message : String(finalReadErr)}`);
      logger.warn({ component: 'risk-gate', reason, err: finalReadErr }, 'failed to verify positions after emergency close rounds');
    }
    flat = remainingPositions.length === 0;

    try {
      remainingOrders = await exchange.getOpenOrders();
      ordersCleared = remainingOrders.length === 0;
      if (!ordersCleared && !issues.some((issue) => issue.startsWith('open orders remain after cancelAll'))) {
        issues.push(`open orders remain after emergency close: ${remainingOrders.length}`);
      }
    } catch (ordersErr) {
      issues.push(`final open order check failed: ${ordersErr instanceof Error ? ordersErr.message : String(ordersErr)}`);
      logger.warn({ component: 'risk-gate', reason, err: ordersErr }, 'failed to verify open orders after emergency close rounds');
    }

    if (!flat) {
      if (verified && rounds > 0) {
        issues.push(`positions remain open after ${rounds} rounds`);
      }
      if (!isWatchdogReason || shouldLogWatchdog(`emergency-incomplete:${reason}`)) {
        logger.error(
          { component: 'risk-gate', reason, remainingPositions: remainingPositions.length, verified },
          verified
            ? 'emergency close incomplete, watchdog will retry while positions remain open'
            : 'emergency close could not verify flat state, watchdog will retry'
        );
      }
    }
  } finally {
    if (flat) {
      if (!isWatchdogReason || shouldLogWatchdog(`emergency-complete:${reason}`)) {
        logger.info({ component: 'risk-gate', reason, rounds, issues: issues.length }, 'emergency close completed and positions are flat');
      }
    }

    await notifyEmergencyCloseResult({
      reason,
      flat,
      verified,
      ordersCleared,
      rounds,
      remainingPositions,
      remainingOrders,
      issues,
    }).catch((notifyErr) => {
      logger.warn({ component: 'telegram', err: notifyErr instanceof Error ? notifyErr.message : notifyErr }, 'emergency close telegram notify failed');
    });

    emergencyCloseLock.running = false;
    return {
      flat,
      verified,
      ordersCleared,
      rounds,
      remainingPositions,
      remainingOrders,
      issues,
    };
  }
}

/** Close emergency only for one symbol (used by per-symbol strategy exits). */
async function emergencyCloseSymbol(symbol: string, reason = 'strategy_emergency_exit') {
  const normalized = normalizeSymbol(symbol);
  try {
    try {
      await exchange.cancelAll(normalized);
    } catch (cancelErr) {
      logger.warn({ component: 'risk-gate', symbol: normalized, err: cancelErr }, 'failed to cancel open orders before symbol emergency close');
    }

    let positions = await exchange.getOpenPositions(normalized);
    if (positions.length === 0) return;

    for (let round = 0; round < 4; round++) {
      positions = await exchange.getOpenPositions(normalized);
      if (positions.length === 0) break;

      for (const pos of positions) {
        const closeSide: 'buy' | 'sell' = pos.side === 'long' ? 'sell' : 'buy';
        const topOfBook = typeof exchange.getTopOfBook === 'function'
          ? await exchange.getTopOfBook(normalized).catch(() => null)
          : null;
        const price = emergencyClosePrice(pos, closeSide, topOfBook);

        await exchange.placeLimitOrder({
          symbol: normalized,
          side: closeSide,
          price,
          size: pos.size,
          reduceOnly: true,
          timeInForce: 'Ioc',
          clientOrderId: `emergency-${normalized}-${Date.now()}-${nanoid(6)}`,
        }).catch((error) => {
          logger.warn({ component: 'risk-gate', symbol: normalized, err: error }, 'symbol emergency IOC close failed');
        });

        logger.warn({ component: 'risk-gate', symbol: normalized, side: pos.side, size: pos.size, closeReason: reason, timeInForce: 'IOC' }, 'position close submitted (symbol emergency)');
        await notifySlEvent({ symbol: normalized, reason, closedBy: reason }).catch(() => undefined);
      }

      await sleep(700);
    }
  } catch (error) {
    logger.error({ component: 'risk-gate', symbol: normalized, err: error }, 'failed to emergency-close symbol');
  }
}

let drawdownWatchdogTimer: NodeJS.Timeout | null = null;
let drawdownWatchdogBusy = false;

async function runDrawdownWatchdogTick() {
  if (drawdownWatchdogBusy) return;
  drawdownWatchdogBusy = true;
  try {
    if (ddLock.active && ddLock.emergencyCloseSettledAt) {
      if (emergencyCloseLock.hardStopActive) {
        emergencyCloseLock.hardStopActive = false;
      }
      return;
    }

    const risk = await evaluateRiskGates({ emitAudit: false });

    if (!risk.equityValidForRisk) {
      if (shouldLogWatchdog('dd-watchdog-risk-unavailable')) {
        logger.warn({
          component: 'risk-gate',
          equityQuality: risk.equityQuality,
          equitySource: risk.equitySource,
          equityUsd: risk.equityUsd,
        }, 'drawdown watchdog skipped because risk-valid equity is unavailable');
      }
      return;
    }

    if (risk.blocks.includes('daily_loss_limit_exceeded')) {
      if (!emergencyCloseLock.hardStopActive) {
        emergencyCloseLock.hardStopActive = true;
        logRiskGateAudit({
          gate: 'daily_dd',
          passed: false,
          reason: 'daily_loss_limit_exceeded_watchdog',
          details: {
            ddPct: risk.dailyDDPct,
            limit: rulesCache.getEffectiveRules().dailyDDLimitPct,
            equityUsd: risk.equityUsd,
            baselineEquityUsd: risk.baselineEquityUsd
          }
        });
      }

      if (!ddLock.active) {
        ddLock.active = true;
        ddLock.activatedAt = new Date().toISOString();
        ddLock.triggeredDailyDDPct = Number(risk.dailyDDPct.toFixed(2));
        ddLock.dailyDDLimitPct = rulesCache.getEffectiveRules().dailyDDLimitPct;
        ddLock.triggeredEquityUsd = Number(risk.equityUsd.toFixed(2));
        ddLock.baselineEquityUsd = Number(risk.baselineEquityUsd.toFixed(2));
        ddLock.emergencyCloseNotificationSent = false;
        ddLock.emergencyCloseSettledAt = undefined;
        await persistDdLockState();
        logRiskGateAudit({
          gate: 'daily_dd',
          passed: false,
          reason: 'dd_lock_activated_watchdog',
          details: {
            activatedAt: ddLock.activatedAt,
            ddPct: risk.dailyDDPct,
            limit: rulesCache.getEffectiveRules().dailyDDLimitPct,
            triggeredDailyDDPct: Number(risk.dailyDDPct.toFixed(2)),
            dailyDDLimitPct: rulesCache.getEffectiveRules().dailyDDLimitPct,
            triggeredEquityUsd: Number(risk.equityUsd.toFixed(2)),
            baselineEquityUsd: Number(risk.baselineEquityUsd.toFixed(2)),
          },
        });
      }

      const closeResult = await emergencyCloseAll('daily_loss_limit_exceeded_watchdog');
      if (closeResult.flat && closeResult.verified && closeResult.ordersCleared) {
        ddLock.emergencyCloseSettledAt = ddLock.emergencyCloseSettledAt || new Date().toISOString();
        await persistDdLockState();
      }
      return;
    }

    if (emergencyCloseLock.hardStopActive) {
      emergencyCloseLock.hardStopActive = false;
      logRiskGateAudit({
        gate: 'daily_dd',
        passed: true,
        reason: 'daily_loss_recovered_watchdog',
        details: {
          ddPct: risk.dailyDDPct,
          limit: rulesCache.getEffectiveRules().dailyDDLimitPct,
          equityUsd: risk.equityUsd,
          baselineEquityUsd: risk.baselineEquityUsd,
          ddLockActive: ddLock.active,
          ddLockActivatedAt: ddLock.activatedAt || undefined,
        }
      });
    }
  } catch (error) {
    logger.error({ component: 'risk-gate', err: error }, 'drawdown watchdog tick failed');
  } finally {
    drawdownWatchdogBusy = false;
  }
}

function startDrawdownWatchdog(startupDelayMs = 0) {
  if (!ENABLE_DRAWDOWN_WATCHDOG) {
    logger.info({ component: 'risk-gate' }, 'drawdown watchdog disabled via ENABLE_DRAWDOWN_WATCHDOG=false');
    return;
  }
  if (!exchange.capabilities.privateAccount || !exchange.capabilities.privateTrading) {
    logger.info({ component: 'risk-gate' }, 'drawdown watchdog not started (private account/trading unavailable)');
    return;
  }
  if (drawdownWatchdogTimer) return;

  const kickoff = () => {
    // Warm-up tick so baseline is created early in the day.
    runDrawdownWatchdogTick().catch((err) => logger.warn({ component: 'risk-gate', err }, 'drawdown watchdog tick failed'));

    drawdownWatchdogTimer = setInterval(() => {
      runDrawdownWatchdogTick().catch((err) => logger.warn({ component: 'risk-gate', err }, 'drawdown watchdog tick failed'));
    }, DRAWDOWN_WATCHDOG_INTERVAL_MS);
    drawdownWatchdogTimer.unref?.();

    logger.info({ component: 'risk-gate', intervalMs: DRAWDOWN_WATCHDOG_INTERVAL_MS }, 'drawdown watchdog started');
  };

  if (startupDelayMs > 0) {
    const t = setTimeout(kickoff, startupDelayMs);
    t.unref?.();
  } else {
    kickoff();
  }
}

// ─── Engulfing Monitor Loop ───────────────────────────────────────────
let engulfingMonitorTimer: NodeJS.Timeout | null = null;
let engulfingMonitorBusy = false;
let engulfingMonitorIntervalAppliedMs = 0;

/** Per-signal debounce: key = `${symbol}:${tf}:${direction}`, value = last fired ms */
const lastEntrySignalAt = new Map<string, number>();
/** Per-candle emergency-exit debounce: key = `${symbol}:${tf}:${direction}`, value = engulfing candle open timestamp ms. */
const lastEmergencyExitSignalAt = new Map<string, number>();

async function estimateSignalSize(params: {
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  effectiveRules: ReturnType<typeof rulesCache.getEffectiveRules>;
}): Promise<{ size: number; leverage: number }> {
  const { symbol, price, effectiveRules } = params;
  const leverage = effectiveRules.maxLeverage;

  const account = await exchange.getAccountState();
  const equityUsd = account?.equityValidForRisk ? (account.equityUsd ?? 0) : 0;
  const availableUsd = account?.availableUsd ?? 0;

  let sizeDecimals = 6;
  try {
    const meta = await exchange.getInstrumentMeta(symbol);
    if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
  } catch {
    // best effort
  }

  const sizing = computeAllocationSize({ symbol, price, equityUsd, availableUsd, rules: effectiveRules, sizeDecimals });
  if (!sizing.ok) {
    return { size: 0, leverage };
  }
  return { size: sizing.size, leverage };
}

function getEntrySignalAuditGate(strategy: SignalStrategy): RiskGateAuditEntry['gate'] {
  if (strategy === 'engulfing') return 'engulfing_entry_signal';
  if (strategy === 'fvg') return 'fvg_entry_signal';
  return 'radar_entry_signal';
}

function normalizeSignalSourceLabel(strategy: SignalStrategy, timeframe: TradingRulesTimeframe, sourceLabel?: string): string {
  const clean = String(sourceLabel ?? '').trim().toLowerCase().replace(/[^a-z0-9:_-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  return clean ? `${strategy}:${clean}:${timeframe}` : `${strategy}:auto:${timeframe}`;
}

function normalizeExecutionIntentMetadata(details?: Record<string, unknown>): Record<string, string | number | boolean | null> | undefined {
  if (!details) return undefined;
  const metadata: Record<string, string | number | boolean | null> = {};
  for (const [key, value] of Object.entries(details)) {
    if (value === null) {
      metadata[key] = null;
    } else if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      metadata[key] = value;
    } else if (value instanceof Date) {
      metadata[key] = value.toISOString();
    }
  }
  return Object.keys(metadata).length > 0 ? metadata : undefined;
}

async function handoffStrategyEntrySignal(params: {
  component: 'engulfing-monitor' | 'fvg-monitor' | 'radar-ingest';
  strategy: SignalStrategy;
  symbol: string;
  timeframe: TradingRulesTimeframe;
  side: 'buy' | 'sell';
  price: number;
  reason: string;
  effectiveRules: ReturnType<typeof rulesCache.getEffectiveRules>;
  autoConfirm: boolean;
  sourceLabel?: string;
  auditDetails?: Record<string, unknown>;
  radarSignalId?: string;
}): Promise<{
  flow: 'continue' | 'break';
  status: 'pending_confirmation' | 'auto_order_placed' | 'rejected' | 'ignored';
  source: string;
  executionIntentId?: string;
  pendingId?: string;
  orderId?: string;
  error?: string;
}> {
  const { component, strategy, symbol, timeframe, side, price, reason, effectiveRules, autoConfirm, sourceLabel, auditDetails, radarSignalId } = params;
  const source = normalizeSignalSourceLabel(strategy, timeframe, sourceLabel);
  const auditGate = getEntrySignalAuditGate(strategy);
  const db = await getDb();
  const nowIso = new Date().toISOString();
  const policies = syncRadarContextPolicies({ db, nowIso });
  const policyGate = evaluateRadarContextPolicyEntry({
    policies,
    symbol,
    side,
    nowIso,
  });
  const intent = appendExecutionIntent(db, {
    component,
    strategy,
    symbol,
    side,
    timeframe,
    price,
    reduceOnly: false,
    reason,
    sourceLabel: source,
    status: policyGate.allowed ? 'created' : 'policy_rejected',
    auditedOperatorOverride: false,
    policyDecision: policyGate.allowed ? 'accepted' : 'rejected',
    policyReasonCode: policyGate.reasonCode,
    policySnapshot: policyGate.snapshot,
    radarSignalId,
    metadata: normalizeExecutionIntentMetadata(auditDetails),
  });

  if (!policyGate.allowed) {
    logRiskGateAudit({
      gate: auditGate,
      passed: false,
      reason: policyGate.reasonCode ?? 'radar_context_policy_blocked',
      details: { symbol, timeframe, strategy, executionIntentId: intent.id, ...auditDetails },
    });
    appendTradeEvent(db.data, {
      symbol,
      source: 'live',
      type: 'signal_rejected',
      timestamp: nowIso,
      correlationId: `intent-${intent.id}`,
      side: side === 'buy' ? 'long' : 'short',
      price,
      reason: 'radar_context_policy_rejected',
      payload: {
        executionIntentId: intent.id,
        policyReasonCode: policyGate.reasonCode ?? 'radar_context_policy_blocked',
        policyId: policyGate.snapshot?.policyId ?? null,
      },
    });
    await db.write();
    await notifySignalRejectedEvent({
      symbol,
      source,
      reason: policyGate.reasonCode ?? 'radar_context_policy_blocked',
      blocks: policyGate.snapshot?.reasonCodes.join(',') || policyGate.reasonCode,
    }).catch(() => undefined);
    return { flow: 'continue', status: 'rejected', source, executionIntentId: intent.id, error: policyGate.reasonCode ?? 'radar_context_policy_blocked' };
  }

  if (!autoConfirm) {
    const estimate = await estimateSignalSize({ symbol, side, price, effectiveRules });
    if (!estimate.size || estimate.size <= 0) {
      updateExecutionIntent(db, intent.id, { status: 'ignored' });
      await db.write();
      logger.warn({ component, symbol, timeframe, side, reason: 'invalid_sizing', strategy }, 'entry signal skipped: invalid sizing');
      return { flow: 'continue', status: 'ignored', source, executionIntentId: intent.id, error: 'invalid_sizing' };
    }

    const correlationId = `${strategy}-pending-${nanoid(8)}`;
    const queued = await queuePendingConfirmation({
      symbol,
      side: side === 'buy' ? 'long' : 'short',
      strategy,
      timeframe,
      reason,
      price,
      size: estimate.size,
      leverage: estimate.leverage,
      correlationId,
      executionIntentId: intent.id,
    });

    logger.info({ component, symbol, timeframe, side, strategy, pendingId: queued.id, queued: queued.queued, reason, source }, 'entry signal queued for manual confirmation');

    if (queued.queued) {
      updateExecutionIntent(db, intent.id, { status: 'pending_confirmation', pendingId: queued.id });
      await db.write();
      return { flow: 'break', status: 'pending_confirmation', source, executionIntentId: intent.id, pendingId: queued.id };
    }

    if (queued.id.startsWith('pc-')) {
      updateExecutionIntent(db, intent.id, { status: 'pending_confirmation', pendingId: queued.id });
      await db.write();
      return { flow: 'break', status: 'pending_confirmation', source, executionIntentId: intent.id, pendingId: queued.id };
    }

    updateExecutionIntent(db, intent.id, { status: 'rejected' });
    await db.write();
    return { flow: 'break', status: 'rejected', source, executionIntentId: intent.id, error: queued.id };
  }

  try {
    const account = await exchange.getAccountState();
    const equityUsd = account?.equityUsd ?? 0;
    const availableUsd = account?.availableUsd ?? 0;
    if (equityUsd <= 0) {
      updateExecutionIntent(db, intent.id, { status: 'rejected' });
      await db.write();
      logger.warn({ component, strategy, symbol, timeframe }, 'auto-entry: zero equity');
      return { flow: 'continue', status: 'rejected', source, executionIntentId: intent.id, error: 'zero_equity' };
    }

    let sizeDecimals = 6;
    try {
      const meta = await exchange.getInstrumentMeta(symbol);
      if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
    } catch {
      // best effort
    }

    const sizing = computeAllocationSize({ symbol, price, equityUsd, availableUsd, rules: effectiveRules, sizeDecimals });
    if (!sizing.ok) {
      logRiskGateAudit({ gate: auditGate, passed: false, reason: sizing.reason, details: { symbol, timeframe, strategy, ...auditDetails } });
      updateExecutionIntent(db, intent.id, { status: 'rejected' });
      await db.write();
      logger.warn({ component, strategy, symbol, timeframe, reason: sizing.reason }, 'auto-entry sizing failed');
      return { flow: 'continue', status: 'rejected', source, executionIntentId: intent.id, error: sizing.reason };
    }

    const risk = await evaluateRiskGates({ emitAudit: false });
    if (!risk.canTrade) {
      const reasonCode = `risk_gate_blocked:${risk.blocks.join(',')}`;
      logger.warn({ component, strategy, symbol, timeframe, blocks: risk.blocks }, 'auto-entry blocked by risk gates');
      await notifySignalRejectedEvent({
        symbol,
        source,
        reason: 'auto_entry_blocked_risk_gate',
        blocks: risk.blocks.join(','),
      }).catch(() => undefined);
      updateExecutionIntent(db, intent.id, { status: 'rejected' });
      await db.write();
      return { flow: 'continue', status: 'rejected', source, executionIntentId: intent.id, error: reasonCode };
    }

    const gross = await checkPortfolioGrossCap({ symbol, price, size: sizing.size, effectiveRules, riskCheck: risk });
    if (!gross.ok) {
      logRiskGateAudit({
        gate: auditGate,
        passed: false,
        reason: 'portfolio_gross_cap_exceeded',
        details: { symbol, timeframe, strategy, currentGross: gross.currentGross, newNotional: gross.newNotional, totalGross: gross.totalGross, cap: gross.cap },
      });
      await notifySignalRejectedEvent({
        symbol,
        source,
        reason: 'portfolio_gross_cap_exceeded',
        blocks: `gross_${gross.totalGross.toFixed(2)}_gt_${gross.cap.toFixed(2)}`,
      }).catch(() => undefined);
      updateExecutionIntent(db, intent.id, { status: 'rejected' });
      await db.write();
      return { flow: 'continue', status: 'rejected', source, executionIntentId: intent.id, error: 'portfolio_gross_cap_exceeded' };
    }

    const correlationId = `${strategy}-auto-${nanoid(8)}`;
    const ack = await exchange.placeLimitOrder({ symbol, side, price, size: sizing.size, reduceOnly: false, clientOrderId: correlationId });

    logRiskGateAudit({
      gate: auditGate,
      passed: ack.ok,
      reason: ack.ok ? 'auto_order_placed' : 'auto_order_failed',
      details: { symbol, timeframe, strategy, side, size: sizing.size, price, orderId: ack.orderId, error: ack.error, reason, ...auditDetails },
    });
    logger.info({ component, strategy, symbol, timeframe, side, size: sizing.size, price, ok: ack.ok, orderId: ack.orderId, reason, source }, 'auto-entry order result');

    if (ack.ok) {
      try {
        await notifyTradeOpen({ symbol, side, price, size: sizing.size, source });
      } catch (error) {
        logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
      }
      const tpSl = resolveTpSlDefaults(price, side, undefined, undefined);
      if (tpSl) {
        try {
          await placeTpSlTriggerOrders(symbol, side, sizing.size, tpSl, correlationId, price, timeframe);
        } catch {
          // best effort
        }
      }
      updateExecutionIntent(db, intent.id, { status: 'auto_order_placed', orderId: ack.orderId });
      await db.write();
      return { flow: 'break', status: 'auto_order_placed', source, executionIntentId: intent.id, orderId: ack.orderId };
    }

    await notifyOrderRejectedEvent({
      symbol,
      source,
      error: ack.error ?? 'exchange_rejected',
    }).catch(() => undefined);

    updateExecutionIntent(db, intent.id, { status: 'rejected' });
    await db.write();
    return { flow: 'continue', status: 'rejected', source, executionIntentId: intent.id, error: ack.error ?? 'exchange_rejected' };
  } catch (err) {
    logger.error({ component, strategy, symbol, timeframe, err, reason, source }, 'auto-entry order failed');
  }

  updateExecutionIntent(db, intent.id, { status: 'rejected' });
  await db.write();
  return { flow: 'continue', status: 'rejected', source, executionIntentId: intent.id, error: 'auto_entry_failed' };
}

function alphaRadarObservationIsEventLockoutCandidate(observation: AlphaRadarObservation): boolean {
  const tags = new Set((observation.topicTags ?? []).map((tag) => String(tag).toLowerCase()));
  const metadata = observation.metadata && typeof observation.metadata === 'object'
    ? observation.metadata as Record<string, unknown>
    : {};
  return tags.has('macro-shock') || Boolean(metadata.macroShock) || observation.sourceClass === 'macro' && Number(observation.urgencyScore ?? 0) >= 0.8;
}

async function resolveEventLockout(params: { symbol: string; raw: TradingRulesSettings }): Promise<{ active: boolean; reason?: string } | undefined> {
  const minutes = Math.max(0, Math.round(Number(params.raw.eventLockoutMinutes ?? 0)));
  if (minutes <= 0) return undefined;

  const now = Date.now();
  const cutoffMs = now - minutes * 60_000;
  const db = await getDb();
  const settings = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
  const observations = currentAlphaRadarObservations(settings, ensureAlphaRadarObservationsState(db), new Date(now).toISOString());
  const hit = observations.find((observation) => {
    const observedMs = Date.parse(observation.observedAt);
    return Number.isFinite(observedMs)
      && observedMs >= cutoffMs
      && alphaRadarObservationIsEventLockoutCandidate(observation);
  });

  if (!hit) return { active: false };
  const label = hit.topicTags?.includes('macro-shock') ? 'macro-shock' : hit.sourceClass ?? hit.source;
  return { active: true, reason: `event_lockout_${label}_${params.symbol}` };
}

/**
 * Issue #61 — Signal-quality gate shared by the engulfing and FVG monitors.
 * Pulls regime candles for `rules.regimeTf`, computes ATR/EMA/ADX, displacement
 * quality, and expected RR, and returns the deterministic verdict from
 * `signalQualityContext.evaluateSignalQuality`.
 *
 * Designed to fail-safe: when thresholds are zero (default settings) every
 * filter remains permissive so existing operators see no behavioural change
 * until they opt in via the Trading Rules UI.
 */
async function runSignalQualityGate(params: {
  symbol: string;
  side: 'buy' | 'sell';
  entryTf: TradingRulesTimeframe;
  entryCandles: Candle[];
  currentPrice: number;
  raw: TradingRulesSettings;
  impulseTriple?: { c0: Candle; c1: Candle; c2: Candle };
}): Promise<SignalQualityVerdict> {
  const { symbol, side, entryTf, entryCandles, currentPrice, raw, impulseTriple } = params;
  const tradeSide: TradeSide = side === 'buy' ? 'long' : 'short';
  const regimeTf = (raw.regimeTf ?? '1h') as TradingRulesTimeframe;
  const adxMin = Number(raw.adxMin ?? 0);
  const minImpulseAtr = Number(raw.minImpulseAtr ?? 0);
  const minExpectedRr = Number(raw.minExpectedRr ?? 0);
  const eventLockout = await resolveEventLockout({ symbol, raw }).catch((err) => {
    logger.warn({ component: 'signal-quality', symbol, err }, 'event lockout check failed — signal-quality gate blocks entry');
    return { active: true, reason: 'event_lockout_check_unavailable' };
  });

  // When all thresholds are zero, the gate is a no-op; skip the candle fetch.
  if (adxMin <= 0 && minImpulseAtr <= 0 && minExpectedRr <= 0 && !eventLockout?.active) {
    return { ok: true, details: {} };
  }

  // Regime candles: enough history for slow EMA(55) + ADX seed (2*period).
  const regimeTfMs = TF_MS[regimeTf] ?? 3_600_000;
  let regimeCandles: Candle[] = entryCandles;
  if (regimeTf !== entryTf) {
    try {
      const now = Date.now();
      const fetched = await exchange.getCandles({
        symbol,
        timeframe: TF_LABEL_TO_CANDLE_TF[regimeTf],
        startTimeMs: now - regimeTfMs * 120,
        endTimeMs: now,
      });
      regimeCandles = fetched.filter((c) => Date.parse(c.timestamp) <= now - regimeTfMs);
    } catch (err) {
      logger.warn({ component: 'signal-quality', regimeTf, err }, 'regime candle fetch failed — signal-quality gate blocks entry');
      return {
        ok: false,
        reasonCode: 'regime_data_insufficient',
        reason: `regime_fetch_failed_${regimeTf}`,
        details: {},
      };
    }
  }

  const tpSl = resolveTpSlDefaults(currentPrice, side, undefined, undefined);
  const stopLoss = tpSl?.stopLoss ?? 0;
  const takeProfits = tpSl?.takeProfits?.length ? tpSl.takeProfits : [];

  return evaluateSignalQuality({
    side: tradeSide,
    regimeCandles,
    regimeTf,
    entryCandles,
    impulseTriple,
    entry: currentPrice,
    stopLoss,
    takeProfits,
    eventLockout,
    thresholds: {
      adxMin,
      minImpulseAtr,
      minExpectedRr,
      requireQuartile: minImpulseAtr > 0,
    },
  });
}

/**
 * One tick of the engulfing background monitor.
 * - Entry signals: detected on entryTimeframes[] when no open position → log + auto-order if autoConfirm
 * - Emergency exit signals: reverse engulfing on emergencyExitTimeframes[] when position is open → emergencyCloseAll
 */
async function runEngulfingMonitorTick(): Promise<void> {
  if (engulfingMonitorBusy) return;
  engulfingMonitorBusy = true;
  try {
    const effectiveRules = rulesCache.getEffectiveRules();
    const raw = effectiveRules.raw;
    if (!raw) return; // env fallback, no rules configured

    const symbols = getMonitoredSymbols(raw, LIVE_SYMBOL);
    const lookback = raw.engulfingLookbackCandles ?? 30;
    const entryTfs = raw.entryTimeframes?.length ? raw.entryTimeframes : ['15m' as const];
    const exitTfs = raw.emergencyExitTimeframes?.length ? raw.emergencyExitTimeframes : ['1h' as const];
    const minCandles = lookback + 5;
    const now = Date.now();

    // Fetch open positions once
    let positions: PositionSnapshot[] = [];
    try {
      positions = await exchange.getOpenPositions();
    } catch (err) {
      logger.warn({ component: 'engulfing-monitor', err }, 'failed to get open positions');
      return;
    }

    let mids: Record<string, number> = {};
    try {
      mids = await exchange.getMids();
    } catch (err) {
      logger.warn({ component: 'engulfing-monitor', err }, 'failed to get mids');
      return;
    }

    for (const symbol of symbols) {
      const operatorBias = await getOperatorBias(symbol);
      const symbolPosition = positions.find((p) => p.symbol.toUpperCase() === symbol.toUpperCase());
      if (symbolPosition) {
        await clearPendingConfirmationForSymbol(symbol);
      }

      // ── ENTRY signals (only when no open position for symbol) ────────
      if (!symbolPosition) {
      for (const tf of entryTfs) {
        try {
          const tfMs = TF_MS[tf] ?? 900_000;
          const candles = await exchange.getCandles({
            symbol,
            timeframe: TF_LABEL_TO_CANDLE_TF[tf],
            startTimeMs: now - tfMs * (minCandles + 2),
            endTimeMs: now,
          });

          const closedCandles = candles.filter((c) => Date.parse(c.timestamp) <= now - tfMs);
          const signal = evaluateTimeframe(closedCandles, tf, lookback);
          if (!signal.detected || !signal.direction) continue;

          const side: 'buy' | 'sell' = signal.direction === 'bullish' ? 'buy' : 'sell';
          const blockedByBias = operatorBias === 'off'
            || (operatorBias === 'short' && side !== 'sell')
            || (operatorBias === 'long' && side !== 'buy');
          if (blockedByBias) {
            logRiskGateAudit({
              gate: 'engulfing_entry_signal',
              passed: false,
              reason: 'operator_bias_block',
              details: { symbol, tf, direction: signal.direction, operatorBias, side },
            });
            await notifySignalRejectedEvent({
              symbol,
              source: `engulfing:auto:${tf}`,
              reason: 'operator_bias_block',
              blocks: `operatorBias=${operatorBias}`,
            }).catch(() => undefined);
            continue;
          }

          // Debounce: skip if same signal fired within this candle period
          const debounceKey = `${symbol}:${tf}:${signal.direction}`;
          const lastFired = lastEntrySignalAt.get(debounceKey) ?? 0;
          if (now - lastFired < tfMs) continue;
          lastEntrySignalAt.set(debounceKey, now);

          logRiskGateAudit({
            gate: 'engulfing_entry_signal',
            passed: true,
            details: { symbol, tf, direction: signal.direction, confidence: signal.confidence, reason: signal.reason, operatorBias },
          });
          logger.info(
            { component: 'engulfing-monitor', symbol, tf, direction: signal.direction, confidence: signal.confidence, operatorBias },
            'engulfing entry signal detected',
          );

          const currentPrice = resolveMonitorPrice(mids, symbol, closedCandles);
          if (!currentPrice) { logger.warn({ component: 'engulfing-monitor' }, 'entry signal: no price'); continue; }

          // Issue #61 — Signal-quality gate (regime, displacement, RR).
          const quality = await runSignalQualityGate({
            symbol,
            side,
            entryTf: tf,
            entryCandles: closedCandles,
            currentPrice,
            raw,
          });
          if (!quality.ok) {
            logRiskGateAudit({
              gate: 'engulfing_entry_signal',
              passed: false,
              reason: quality.reasonCode ?? 'signal_quality_block',
              details: {
                symbol,
                tf,
                direction: signal.direction,
                regimeTf: raw.regimeTf,
                regime: quality.details.regime?.direction,
                adx: quality.details.regime?.adx,
                bodyAtr: quality.details.displacement?.bodyAtrRatio,
                expectedRr: quality.details.expectedRr,
                reason: quality.reason,
              },
            });
            await notifySignalRejectedEvent({
              symbol,
              source: `engulfing:auto:${tf}`,
              reason: quality.reasonCode ?? 'signal_quality_block',
              blocks: quality.reason,
            }).catch(() => undefined);
            continue;
          }

          const handoff = await handoffStrategyEntrySignal({
            component: 'engulfing-monitor',
            strategy: 'engulfing',
            symbol,
            timeframe: tf,
            side,
            price: currentPrice,
            reason: signal.reason,
            effectiveRules,
            autoConfirm: !!raw.autoConfirm,
            auditDetails: {
              direction: signal.direction,
              confidence: signal.confidence,
              regimeTf: raw.regimeTf,
              regime: quality.details.regime?.direction,
              expectedRr: quality.details.expectedRr,
            },
          });
          if (handoff.flow === 'break') break;
        } catch (err) {
          logger.warn({ component: 'engulfing-monitor', tf, err }, 'entry signal evaluation failed for tf');
        }
      }
    }

    // ── EMERGENCY EXIT signals (only when position is open) ──────────
    if (symbolPosition) {
      for (const tf of exitTfs) {
        try {
          const tfMs = TF_MS[tf] ?? 3_600_000;
          const candles = await exchange.getCandles({
            symbol,
            timeframe: TF_LABEL_TO_CANDLE_TF[tf],
            startTimeMs: now - tfMs * (minCandles + 2),
            endTimeMs: now,
          });

          const closedCandles = candles.filter((c) => Date.parse(c.timestamp) <= now - tfMs);
          const signal = evaluateTimeframe(closedCandles, tf, lookback);
          if (!signal.detected || !signal.direction) continue;

          // Reverse signal check: bullish position + bearish signal → exit
          const isLong = symbolPosition.side === 'long';
          const isReverseSignal = (isLong && signal.direction === 'bearish') || (!isLong && signal.direction === 'bullish');
          if (!isReverseSignal) continue;

          // One-shot per closed engulfing candle: prevent repeated emergency exits
          // on every monitor tick for the same TF signal.
          const signalCandleOpenMs = Date.parse(closedCandles[closedCandles.length - 1]?.timestamp ?? '');
          if (!Number.isFinite(signalCandleOpenMs)) continue;
          const exitDebounceKey = `${symbol}:${tf}:${signal.direction}`;
          const lastProcessedCandleMs = lastEmergencyExitSignalAt.get(exitDebounceKey) ?? -1;
          if (signalCandleOpenMs <= lastProcessedCandleMs) continue;
          lastEmergencyExitSignalAt.set(exitDebounceKey, signalCandleOpenMs);

          const reason = `engulfing_exit_signal_${signal.direction}`;
          const cachedExitClosePct = Number(raw.exitClosePct ?? 50);
          const exitClosePct = await getFreshExitClosePct(cachedExitClosePct);
          const closeFraction = exitClosePct / 100;

          if (exitClosePct <= 0) {
            logRiskGateAudit({
              gate: 'engulfing_emergency_exit',
              passed: true,
              reason: 'exit_close_pct_zero_skip',
              details: {
                symbol,
                tf,
                direction: signal.direction,
                positionSide: symbolPosition.side,
                exitClosePct,
                cachedExitClosePct,
                reason: signal.reason,
              },
            });
            logger.info(
              {
                component: 'engulfing-monitor',
                symbol,
                tf,
                direction: signal.direction,
                position: symbolPosition.side,
                exitClosePct,
                cachedExitClosePct,
              },
              'reverse engulfing detected — emergency exit disabled (0%)',
            );
            break;
          }

          logRiskGateAudit({
            gate: 'engulfing_emergency_exit',
            passed: true,
            details: {
              symbol,
              tf,
              direction: signal.direction,
              positionSide: symbolPosition.side,
              exitClosePct,
              cachedExitClosePct,
              reason: signal.reason,
            },
          });
          logger.warn(
            {
              component: 'engulfing-monitor',
              symbol,
              tf,
              direction: signal.direction,
              position: symbolPosition.side,
              exitClosePct,
              cachedExitClosePct,
            },
            'reverse engulfing detected — exit triggered',
          );

          if (closeFraction >= 0.9999) {
            // Full close for this symbol only.
            await emergencyCloseSymbol(symbol, reason);
          } else {
            // Partial close → then set SL at entry price (break-even)
            const posSize = symbolPosition.size;
            const closeSize = Math.max(0, Math.floor(posSize * closeFraction * 1e6) / 1e6);
            const closingSide: 'buy' | 'sell' = symbolPosition.side === 'long' ? 'sell' : 'buy';
            const markPrice = symbolPosition.markPrice ?? symbolPosition.entryPrice ?? 0;
            const exitPrice = markPrice > 0
              ? (closingSide === 'sell' ? markPrice * 0.985 : markPrice * 1.015)
              : (closingSide === 'sell' ? 1 : 999_999);

            try {
              const closeAck = await exchange.placeLimitOrder({
                symbol, side: closingSide, price: Number(exitPrice.toFixed(8)),
                size: closeSize, reduceOnly: true,
                clientOrderId: `partial-exit-${nanoid(8)}`,
              });
              logRiskGateAudit({
                gate: 'partial_close', passed: closeAck.ok,
                details: { symbol, closeSize, exitPrice, posSize, exitClosePct, orderId: closeAck.orderId, error: closeAck.error ?? null },
              });

              try {
                const db = await getDb();
                appendTradeEvent(db.data, {
                  symbol,
                  source: 'live',
                  type: closeAck.ok ? 'order_submitted' : 'order_rejected',
                  timestamp: new Date().toISOString(),
                  correlationId: closeAck.orderId ? `partial-close-${closeAck.orderId}` : `partial-close-${nanoid(8)}`,
                  side: symbolPosition.side,
                  price: Number(exitPrice.toFixed(8)),
                  quantity: closeSize,
                  reason: closeAck.ok ? 'engulfing_partial_close' : 'engulfing_partial_close_failed',
                  payload: {
                    exitClosePct,
                    posSize,
                    closeFraction,
                    orderId: closeAck.orderId ?? null,
                    error: closeAck.error ?? null,
                  },
                });
                await db.write();
              } catch {
                // best effort forensic log
              }

              if (!closeAck.ok) {
                throw new Error(closeAck.error || 'partial_close_order_rejected');
              }

              // Move SL to entry price (break-even) for remaining position.
              // Guarantee exactly one SL after partial close: cancel old SL(s), then place BE SL.
              const entryPrice = symbolPosition.entryPrice ?? markPrice;
              if (entryPrice > 0) {
                const remainingSize = Math.max(0, Math.round((posSize - closeSize) * 1e6) / 1e6);
                if (remainingSize > 0) {
                  const openOrders = await exchange.getOpenOrders(symbol).catch(() => []);
                  const isLikelyStopLoss = (order: Awaited<ReturnType<typeof exchange.getOpenOrders>>[number]) => {
                    const raw = order.raw as Record<string, unknown> | undefined;
                    const tpsl = String(
                      (raw as { tpsl?: unknown } | undefined)?.tpsl
                      ?? (raw as { trigger?: { tpsl?: unknown } } | undefined)?.trigger?.tpsl
                      ?? (raw as { orderType?: { trigger?: { tpsl?: unknown } } } | undefined)?.orderType?.trigger?.tpsl
                      ?? ''
                    ).toLowerCase();
                    if (tpsl === 'sl') return true;
                    if (tpsl === 'tp') return false;

                    const orderTypeText = JSON.stringify((raw as { orderType?: unknown } | undefined)?.orderType ?? '').toLowerCase();
                    const looksTp = orderTypeText.includes('take') || orderTypeText.includes('tp');
                    const looksSl = orderTypeText.includes('stop') || orderTypeText.includes('sl');
                    return looksSl && !looksTp;
                  };

                  const oldStops = openOrders.filter((o) => o.side === closingSide && isLikelyStopLoss(o));
                  for (const old of oldStops) {
                    await exchange.cancelOrder(old.id).catch(() => undefined);
                  }

                  const beAck = await exchange.placeTriggerOrder({
                    symbol, side: closingSide, size: remainingSize,
                    triggerPrice: entryPrice, kind: 'sl', reduceOnly: true,
                    clientOrderId: `be-sl-partial-${nanoid(8)}`,
                  });

                  logRiskGateAudit({
                    gate: 'break_even_sl_after_partial',
                    passed: beAck.ok,
                    details: {
                      symbol,
                      entryPrice,
                      remainingSize,
                      cancelledStops: oldStops.length,
                      orderId: beAck.orderId ?? null,
                      error: beAck.error ?? null,
                    },
                  });

                  if (!beAck.ok) {
                    throw new Error(beAck.error || 'break_even_sl_failed');
                  }

                  logger.info({ component: 'engulfing-monitor', symbol, entryPrice, remainingSize, cancelledStops: oldStops.length }, 'break-even SL placed after partial close');
                }
              }
            } catch (err) {
              logger.error({ component: 'engulfing-monitor', symbol, err }, 'partial close failed, falling back to symbol emergency close');
              await emergencyCloseSymbol(symbol, reason);
            }
          }
          break; // one exit action per tick is enough
        } catch (err) {
          logger.warn({ component: 'engulfing-monitor', tf, err }, 'exit signal evaluation failed for tf');
        }
      }
    }
  }
  } catch (err) {
    logger.error({ component: 'engulfing-monitor', err }, 'engulfing monitor tick failed');
  } finally {
    engulfingMonitorBusy = false;
  }
}

/** Compute poll interval from current rules: min entry TF / 10, clamped to [30s, 2m]. */
function engulfingMonitorIntervalMs(): number {
  const effective = rulesCache.getEffectiveRules();
  if (effective.source !== 'runtime' || !effective.raw) {
    // On startup before DB rules hydrate, poll fast to avoid a blind window.
    return 30_000;
  }
  const entryTfs = effective.raw.entryTimeframes?.length ? effective.raw.entryTimeframes : ['15m' as const];
  const minTfMs = Math.min(...entryTfs.map(tf => TF_MS[tf] ?? 900_000));
  return Math.max(30_000, Math.min(120_000, Math.floor(minTfMs / 10)));
}

function scheduleNextEngulfingTick(delayMs: number): void {
  if (engulfingMonitorTimer) clearTimeout(engulfingMonitorTimer);
  engulfingMonitorTimer = setTimeout(async () => {
    try {
      await runEngulfingMonitorTick();
    } catch (err) {
      logger.warn({ component: 'engulfing-monitor', err }, 'tick failed');
    } finally {
      const nextInterval = engulfingMonitorIntervalMs();
      if (nextInterval !== engulfingMonitorIntervalAppliedMs) {
        engulfingMonitorIntervalAppliedMs = nextInterval;
        logger.info({ component: 'engulfing-monitor', intervalMs: nextInterval }, 'engulfing monitor interval updated');
      }
      scheduleNextEngulfingTick(nextInterval);
    }
  }, delayMs);
  engulfingMonitorTimer.unref?.();
}

// ─── FVG Monitor Loop ─────────────────────────────────────────────────
/** Timeframes for FVG scanning (spec: 1H/4H only) */
const FVG_TIMEFRAMES: FvgTimeframe[] = ['1h', '4h'];
const FVG_TF_TO_CANDLE_TF: Record<FvgTimeframe, CandleTimeframe> = { '1h': '1h', '4h': '4h' };

let fvgMonitorTimer: NodeJS.Timeout | null = null;
let fvgMonitorBusy = false;

/** Debounce: key = `${symbol}:${tf}:${direction}`, value = last fired ms */
const lastFvgSignalAt = new Map<string, number>();
const lastFvgNoMidWarnAt = new Map<string, number>();
const FVG_NO_MID_WARN_THROTTLE_MS = 60 * 60_000;

async function runFvgMonitorTick(): Promise<void> {
  if (fvgMonitorBusy) return;
  fvgMonitorBusy = true;
  try {
    const effectiveRules = rulesCache.getEffectiveRules();
    const raw = effectiveRules.raw;
    if (!raw) return; // env fallback

    const fvgRetracePct = raw.fvgRetrace ?? 50;
    if (!Number.isFinite(fvgRetracePct) || fvgRetracePct <= 0) return;
    const fvgQualification = {
      minWidthPct: raw.fvgMinWidthPct ?? 0.3,
      requireSweep: raw.fvgRequireSweep ?? false,
      sweepLookbackCandles: raw.fvgSweepLookbackCandles ?? 20,
      requireFirstTouch: raw.fvgRequireFirstTouch ?? false,
      maxZoneAgeCandles: raw.maxZoneAgeCandles ?? 12,
      requireConfirmation: raw.fvgRequireConfirmation ?? false,
      confirmationTimeframes: raw.fvgConfirmationTimeframes ?? ['15m'],
    };

    const symbols = getMonitoredSymbols(raw, LIVE_SYMBOL);
    const now = Date.now();

    // Open positions (entry only when flat for each monitored symbol)
    let positions: PositionSnapshot[] = [];
    try { positions = await exchange.getOpenPositions(); } catch (err) {
      logger.warn({ component: 'fvg-monitor', err }, 'failed to get positions');
      return;
    }

    let mids: Record<string, number> = {};
    try {
      mids = await exchange.getMids();
    } catch (err) {
      logger.warn({ component: 'fvg-monitor', err }, 'failed to get mids');
      return;
    }

    for (const symbol of symbols) {
      const operatorBias = await getOperatorBias(symbol);
      const symbolPosition = positions.find((p) => p.symbol.toUpperCase() === symbol.toUpperCase());

      // Only check entry signals when no open position for this symbol
      if (symbolPosition) {
        await clearPendingConfirmationForSymbol(symbol);
        continue;
      }

      for (const tf of FVG_TIMEFRAMES) {
        try {
          const tfMs = TF_MS[tf];
          const lookback = 10; // fixed lookback for FVG zone detection
          const candles = await exchange.getCandles({
            symbol,
            timeframe: FVG_TF_TO_CANDLE_TF[tf],
            startTimeMs: now - tfMs * (lookback + 25), // extra room for structure break (20 candles)
            endTimeMs: now,
          });

          const closedCandles = candles.filter((c) => Date.parse(c.timestamp) <= now - tfMs);
          const currentPrice = resolveMonitorPrice(mids, symbol, closedCandles);
          if (!currentPrice) continue;

          const lowerTfCandles: Partial<Record<TradingRulesTimeframe, Candle[]>> = {};
          if (fvgQualification.requireConfirmation) {
            for (const confirmationTf of fvgQualification.confirmationTimeframes) {
              const confirmationTfMs = TF_MS[confirmationTf];
              const confirmationCandles = await exchange.getCandles({
                symbol,
                timeframe: confirmationTf,
                startTimeMs: now - confirmationTfMs * (lookback + 40),
                endTimeMs: now,
              });
              lowerTfCandles[confirmationTf] = confirmationCandles.filter((c) => Date.parse(c.timestamp) <= now - confirmationTfMs);
            }
          }

          const signal = evaluateFvg(closedCandles, tf, {
            currentPrice,
            currentTimeMs: now,
            retracePct: fvgRetracePct,
            lookback,
            qualification: fvgQualification,
            lowerTfCandles,
          });
          if (!signal.detected || !signal.direction) continue;

          const side: 'buy' | 'sell' = signal.direction === 'bullish' ? 'buy' : 'sell';
          const blockedByBias = operatorBias === 'off'
            || (operatorBias === 'short' && side !== 'sell')
            || (operatorBias === 'long' && side !== 'buy');
          if (blockedByBias) {
            logRiskGateAudit({
              gate: 'fvg_entry_signal',
              passed: false,
              reason: 'operator_bias_block',
              details: { symbol, tf, direction: signal.direction, operatorBias, side, currentPrice: currentPrice, triggerPrice: signal.triggerPrice },
            });
            await notifySignalRejectedEvent({
              symbol,
              source: `fvg:auto:${tf}`,
              reason: 'operator_bias_block',
              blocks: `operatorBias=${operatorBias}`,
            }).catch(() => undefined);
            continue;
          }

        // Debounce: once per TF interval
        const debounceKey = `${symbol}:${tf}:${signal.direction}`;
        const lastFired = lastFvgSignalAt.get(debounceKey) ?? 0;
        if (now - lastFired < tfMs) continue;
        lastFvgSignalAt.set(debounceKey, now);

        logRiskGateAudit({
          gate: 'fvg_entry_signal',
          passed: true,
          details: {
            symbol, tf, direction: signal.direction,
            currentPrice: currentPrice,
            triggerPrice: signal.triggerPrice,
            zoneTop: signal.zone?.top,
            zoneBottom: signal.zone?.bottom,
            fvgRetracePct,
            fvgMinWidthPct: fvgQualification.minWidthPct,
            operatorBias,
            reason: signal.reason,
            touchTimestamp: signal.touchTimestamp,
            confirmationTimeframe: signal.confirmationTimeframe,
          },
        });
        logger.info(
          { component: 'fvg-monitor', symbol, tf, direction: signal.direction, currentPrice, triggerPrice: signal.triggerPrice, operatorBias },
          'FVG retrace entry signal detected',
        );

        // Issue #61 — Signal-quality gate (regime, impulse displacement, RR).
        const fvgCompletionIndex = signal.zone?.completionIndex;
        const fvgImpulseTriple = typeof fvgCompletionIndex === 'number'
          ? {
              c0: closedCandles[fvgCompletionIndex - 2],
              c1: closedCandles[fvgCompletionIndex - 1],
              c2: closedCandles[fvgCompletionIndex],
            }
          : undefined;
        const fvgQuality = await runSignalQualityGate({
          symbol,
          side,
          entryTf: tf,
          entryCandles: closedCandles,
          currentPrice,
          raw,
          impulseTriple: fvgImpulseTriple?.c0 && fvgImpulseTriple.c1 && fvgImpulseTriple.c2 ? fvgImpulseTriple : undefined,
        });
        if (!fvgQuality.ok) {
          logRiskGateAudit({
            gate: 'fvg_entry_signal',
            passed: false,
            reason: fvgQuality.reasonCode ?? 'signal_quality_block',
            details: {
              symbol,
              tf,
              direction: signal.direction,
              regimeTf: raw.regimeTf,
              regime: fvgQuality.details.regime?.direction,
              adx: fvgQuality.details.regime?.adx,
              bodyAtr: fvgQuality.details.displacement?.bodyAtrRatio,
              expectedRr: fvgQuality.details.expectedRr,
              reason: fvgQuality.reason,
            },
          });
          await notifySignalRejectedEvent({
            symbol,
            source: `fvg:auto:${tf}`,
            reason: fvgQuality.reasonCode ?? 'signal_quality_block',
            blocks: fvgQuality.reason,
          }).catch(() => undefined);
          continue;
        }

        const handoff = await handoffStrategyEntrySignal({
          component: 'fvg-monitor',
          strategy: 'fvg',
          symbol,
          timeframe: tf,
          side,
          price: currentPrice,
          reason: signal.reason,
          effectiveRules,
          autoConfirm: !!raw.autoConfirm,
          auditDetails: {
            direction: signal.direction,
            triggerPrice: signal.triggerPrice,
            zoneTop: signal.zone?.top,
            zoneBottom: signal.zone?.bottom,
            regimeTf: raw.regimeTf,
            regime: fvgQuality.details.regime?.direction,
            expectedRr: fvgQuality.details.expectedRr,
          },
        });
        if (handoff.flow === 'break') break;
      } catch (err) {
        logger.warn({ component: 'fvg-monitor', tf, err }, 'FVG signal evaluation failed for tf');
      }
    }
  }
  } catch (err) {
    logger.error({ component: 'fvg-monitor', err }, 'FVG monitor tick failed');
  } finally {
    fvgMonitorBusy = false;
  }
}

function startFvgMonitor(startupDelayMs = 0): void {
  if (!ENABLE_FVG_MONITOR) {
    logger.info({ component: 'fvg-monitor' }, 'FVG monitor disabled via ENABLE_FVG_MONITOR=false');
    return;
  }
  if (!exchange.capabilities.privateAccount || !exchange.capabilities.privateTrading) {
    logger.info({ component: 'fvg-monitor' }, 'FVG monitor not started (private account/trading unavailable)');
    return;
  }
  if (fvgMonitorTimer) return;

  const kickoff = () => {
    runFvgMonitorTick().catch(err => logger.warn({ component: 'fvg-monitor', err }, 'initial tick failed'));
    fvgMonitorTimer = setInterval(() => {
      runFvgMonitorTick().catch(err => logger.warn({ component: 'fvg-monitor', err }, 'tick failed'));
    }, FVG_MONITOR_INTERVAL_MS);
    fvgMonitorTimer.unref?.();
    logger.info({ component: 'fvg-monitor', intervalMs: FVG_MONITOR_INTERVAL_MS }, 'FVG monitor started');
  };

  if (startupDelayMs > 0) {
    const t = setTimeout(kickoff, startupDelayMs);
    t.unref?.();
  } else {
    kickoff();
  }
}

function startEngulfingMonitor(startupDelayMs = 0): void {
  if (!ENABLE_MULTI_TF_ENGULFING) {
    logger.info({ component: 'engulfing-monitor' }, 'engulfing monitor disabled via ENABLE_MULTI_TF_ENGULFING=false');
    return;
  }
  if (!exchange.capabilities.privateAccount || !exchange.capabilities.privateTrading) {
    logger.info({ component: 'engulfing-monitor' }, 'engulfing monitor not started (private account/trading unavailable)');
    return;
  }
  if (engulfingMonitorTimer) return;

  const intervalMs = engulfingMonitorIntervalMs();
  engulfingMonitorIntervalAppliedMs = intervalMs;
  logger.info({ component: 'engulfing-monitor', intervalMs }, 'engulfing monitor started');

  // First tick after the configured stagger delay, then self-schedule
  // using the dynamic interval derived from latest rules.
  scheduleNextEngulfingTick(Math.max(0, startupDelayMs));
}

/** Risk gate middleware for trading endpoints — checks DD + leverage before allowing order */
function isProtectionOnlyRequest(req: Request): boolean {
  const p = (req.path || req.originalUrl || '').toLowerCase();
  return p.startsWith('/api/live/position/levels');
}

function positionGrossNotional(pos: PositionSnapshot): number {
  const px = Number(pos.markPrice ?? pos.entryPrice ?? 0);
  const size = Number(pos.size ?? 0);
  if (!Number.isFinite(px) || px <= 0 || !Number.isFinite(size) || size <= 0) return 0;
  return px * size;
}

async function checkPortfolioGrossCap(params: {
  symbol: string;
  price: number;
  size: number;
  effectiveRules: ReturnType<typeof rulesCache.getEffectiveRules>;
  riskCheck?: RiskCheckResult;
}): Promise<{ ok: true } | { ok: false; cap: number; currentGross: number; newNotional: number; totalGross: number }> {
  const { symbol, price, size, effectiveRules, riskCheck } = params;
  const equityUsd = Number(riskCheck?.equityUsd ?? 0);
  const cap = maxPortfolioGrossNotional(equityUsd, effectiveRules);
  if (!Number.isFinite(cap)) return { ok: true };

  const positions = await exchange.getOpenPositions().catch(() => null);
  if (!positions) throw new Error('portfolio_positions_unavailable');

  const currentGross = positions.reduce((sum, pos) => sum + positionGrossNotional(pos), 0);
  const newNotional = price * size;
  const totalGross = currentGross + newNotional;
  if (!wouldExceedPortfolioGrossCap({ equityUsd, rules: effectiveRules, currentGrossNotional: currentGross, newOrderNotional: newNotional })) {
    return { ok: true };
  }

  logger.warn({ component: 'risk-gate', symbol, currentGross, newNotional, totalGross, cap }, 'portfolio gross cap exceeded');
  return { ok: false, cap, currentGross, newNotional, totalGross };
}

async function riskGateMiddleware(req: Request, res: Response, next: NextFunction) {
  try {
    const protectionOnly = isProtectionOnlyRequest(req);
    const reduceOnly = req.body?.reduceOnly === true || protectionOnly;

    // If DD lock is active, block new entry orders but always allow reduce-only exits.
    if (ddLock.active && !reduceOnly) {
      return res.status(403).json({
        ok: false,
        errorCode: 'dd_lock_active' as TradingErrorCode,
        error: 'DD lock is active. New entry orders are blocked until owner resets the lock.',
        ddLock: getDdLockState(),
      });
    }

    const risk = await evaluateRiskGates();
    const effectiveRules = rulesCache.getEffectiveRules();

    if (risk.blocks.includes('daily_loss_limit_exceeded')) {
      if (!ddLock.active) {
        ddLock.active = true;
        ddLock.activatedAt = new Date().toISOString();
        ddLock.triggeredDailyDDPct = Number(risk.dailyDDPct.toFixed(2));
        ddLock.dailyDDLimitPct = effectiveRules.dailyDDLimitPct;
        ddLock.triggeredEquityUsd = Number(risk.equityUsd.toFixed(2));
        ddLock.baselineEquityUsd = Number(risk.baselineEquityUsd.toFixed(2));
        ddLock.emergencyCloseNotificationSent = false;
        ddLock.emergencyCloseSettledAt = undefined;
        await persistDdLockState();
      }

      // Keep exits possible even while DD lock is active.
      if (reduceOnly) {
        (req as any)._riskCheck = risk;
        return next();
      }

      // Hard stop for new entries: close everything and block.
      await emergencyCloseAll();
      return res.status(403).json({
        ok: false,
        errorCode: 'dd_lock_active' as TradingErrorCode,
        error: `Daily drawdown ${risk.dailyDDPct}% exceeds ${effectiveRules.dailyDDLimitPct}% limit. DD lock activated; new entries blocked until reset.`,
        riskCheck: risk,
        ddLock: getDdLockState(),
      });
    }

    if (risk.blocks.includes('leverage_limit_exceeded')) {
      // Only block new non-reduceOnly orders
      if (!reduceOnly) {
        return res.status(403).json({
          ok: false,
          errorCode: 'leverage_limit_exceeded' as TradingErrorCode,
          error: `Portfolio leverage ${risk.portfolioLeverage}x exceeds ${effectiveRules.portfolioLeverageCap}x cap. Reduce positions first.`,
          riskCheck: risk
        });
      }
    }

    // Attach risk check to request for downstream use
    (req as any)._riskCheck = risk;
    next();
  } catch (error) {
    logger.error({ component: 'risk-gate', err: error }, 'risk evaluation failed, blocking trade (fail-closed)');
    logRiskGateAudit({ gate: 'daily_dd', passed: false, reason: 'risk_check_unavailable' });
    return res.status(503).json({
      ok: false,
      errorCode: 'risk_check_unavailable' as TradingErrorCode,
      error: 'Risk engine unavailable. Trading is temporarily blocked.'
    });
  }
}

/** Symbol allowlist + allocation cap middleware — runs after riskGateMiddleware */
async function symbolAllocationGate(req: Request, res: Response, next: NextFunction) {
  try {
    // Skip for reduce-only orders and protection-only management endpoints.
    if (req.body?.reduceOnly === true || isProtectionOnlyRequest(req)) return next();

    const symbol = normalizeSymbol(req.body?.symbol);
    const effectiveRules = rulesCache.getEffectiveRules();

    // 1. Symbol allowlist check
    if (!isSymbolEnabled(effectiveRules, symbol)) {
      logRiskGateAudit({
        gate: 'symbol_allowlist',
        passed: false,
        reason: 'symbol_not_enabled',
        details: { symbol }
      });
      return res.status(403).json({
        ok: false,
        errorCode: 'symbol_not_enabled' as TradingErrorCode,
        error: `Symbol ${symbol} is not enabled in trading rules.`,
        symbol
      });
    }

    // 2. Allocation cap check (best-effort: uses mark/entry price from open positions)
    const price = Number(req.body?.price);
    const size = Number(req.body?.size);
    if (Number.isFinite(price) && price > 0 && Number.isFinite(size) && size > 0) {
      const riskCheck: RiskCheckResult | undefined = (req as any)._riskCheck;
      const equityUsd = riskCheck?.equityUsd ?? 0;
      const cap = maxNotionalForSymbol(equityUsd, effectiveRules, symbol);

      if (cap > 0 && equityUsd > 0) {
        // Current exposure for this symbol from open positions
        let currentExposure = 0;
        try {
          const positions = await exchange.getOpenPositions();
          for (const pos of positions) {
            if (pos.symbol.toUpperCase() === symbol) {
              currentExposure += (pos.entryPrice ?? pos.markPrice ?? 0) * pos.size;
            }
          }
        } catch {
          // best-effort: if we can't fetch positions, skip exposure calc
        }

        const newNotional = price * size;
        const totalExposure = currentExposure + newNotional;

        if (totalExposure > cap) {
          logRiskGateAudit({
            gate: 'allocation_cap',
            passed: false,
            reason: 'allocation_limit_exceeded',
            details: {
              symbol,
              newNotional: Number(newNotional.toFixed(2)),
              currentExposure: Number(currentExposure.toFixed(2)),
              totalExposure: Number(totalExposure.toFixed(2)),
              cap: Number(cap.toFixed(2)),
              equityUsd: Number(equityUsd.toFixed(2))
            }
          });
          return res.status(403).json({
            ok: false,
            errorCode: 'allocation_limit_exceeded' as TradingErrorCode,
            error: `Order would bring ${symbol} exposure to $${totalExposure.toFixed(2)}, exceeding allocation cap of $${cap.toFixed(2)}.`,
            symbol,
            currentExposure: Number(currentExposure.toFixed(2)),
            newNotional: Number(newNotional.toFixed(2)),
            totalExposure: Number(totalExposure.toFixed(2)),
            cap: Number(cap.toFixed(2))
          });
        }
      }

      const gross = await checkPortfolioGrossCap({
        symbol,
        price,
        size,
        effectiveRules,
        riskCheck: (req as any)._riskCheck,
      });
      if (!gross.ok) {
        logRiskGateAudit({
          gate: 'allocation_cap',
          passed: false,
          reason: 'portfolio_gross_cap_exceeded',
          details: {
            symbol,
            currentGross: Number(gross.currentGross.toFixed(2)),
            newNotional: Number(gross.newNotional.toFixed(2)),
            totalGross: Number(gross.totalGross.toFixed(2)),
            cap: Number(gross.cap.toFixed(2)),
          },
        });
        return res.status(403).json({
          ok: false,
          errorCode: 'portfolio_gross_cap_exceeded' as TradingErrorCode,
          error: `Order would bring portfolio gross exposure to $${gross.totalGross.toFixed(2)}, exceeding cap of $${gross.cap.toFixed(2)}.`,
          symbol,
          currentGross: Number(gross.currentGross.toFixed(2)),
          newNotional: Number(gross.newNotional.toFixed(2)),
          totalGross: Number(gross.totalGross.toFixed(2)),
          cap: Number(gross.cap.toFixed(2)),
        });
      }

      logRiskGateAudit({
        gate: 'allocation_cap',
        passed: true,
        details: { symbol }
      });
    }

    // Symbol is enabled and within cap
    logRiskGateAudit({
      gate: 'symbol_allowlist',
      passed: true,
      details: { symbol }
    });

    next();
  } catch (error) {
    logger.error({ component: 'risk-gate', err: error }, 'symbol/allocation check failed, blocking trade (fail-closed)');
    logRiskGateAudit({ gate: 'allocation_cap', passed: false, reason: 'allocation_check_unavailable' });
    return res.status(503).json({
      ok: false,
      errorCode: 'allocation_check_unavailable' as TradingErrorCode,
      error: 'Allocation guard unavailable. Trading is temporarily blocked.'
    });
  }
}

async function staleMarketDataGate(req: Request, res: Response, next: NextFunction) {
  try {
    const body = (req.body ?? {}) as { symbol?: string; reduceOnly?: boolean };
    const symbol = normalizeSymbol(body.symbol ?? LIVE_SYMBOL);

    // Reduce-only operations lower risk; allow them even when feed is stale.
    if (body.reduceOnly) {
      return next();
    }

    const fresh = await ensureFreshTick(symbol);
    if (fresh.ok) {
      return next();
    }

    logRiskGateAudit({
      gate: 'market_data',
      passed: false,
      reason: 'stale_market_data',
      details: {
        symbol,
        staleMs: fresh.staleMs,
        staleThresholdMs: LIVE_TICK_STALE_MS,
        source: fresh.source
      }
    });

    return res.status(503).json({
      ok: false,
      errorCode: 'stale_market_data' as TradingErrorCode,
      error: 'Market data is stale. New entry orders are temporarily blocked.',
      details: {
        symbol,
        staleMs: fresh.staleMs,
        staleThresholdMs: LIVE_TICK_STALE_MS
      }
    });
  } catch (error) {
    logger.error({ component: 'market-data', err: error }, 'stale market data gate failed, blocking trade');
    return res.status(503).json({
      ok: false,
      errorCode: 'stale_market_data' as TradingErrorCode,
      error: 'Market data validation unavailable. Trading is temporarily blocked.'
    });
  }
}

await hydrateHyperliquidEnvFromDb();

const exchange = new HyperliquidAdapter();

// ─── Multi-TF Engulfing Gate (feature-flagged) ─────────────────────────
const TF_LABEL_TO_CANDLE_TF: Record<TradingRulesTimeframe, CandleTimeframe> = {
  '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h',
};

const TF_MS: Record<TradingRulesTimeframe, number> = {
  '5m': 5 * 60_000,
  '15m': 15 * 60_000,
  '1h': 60 * 60_000,
  '4h': 4 * 60 * 60_000,
};

async function engulfingGate(req: Request, res: Response, next: NextFunction) {

  const body = (req.body ?? {}) as { symbol?: string; reduceOnly?: boolean; tradingRulesGateOverride?: boolean };
  if (body.reduceOnly) return next();
  const operatorOverride = body.tradingRulesGateOverride === true;

  try {
    const effectiveRules = rulesCache.getEffectiveRules();
    const raw = effectiveRules.raw;

    // Fail-safe: rules unavailable blocks new entry orders unless the operator
    // explicitly includes tradingRulesGateOverride=true in the request.
    if (!raw) {
      logRiskGateAudit({
        gate: 'multi_tf_engulfing',
        passed: operatorOverride,
        reason: operatorOverride ? 'rules_unavailable_operator_override' : 'rules_unavailable_fail_safe_block',
      });
      if (operatorOverride) return next();
      return res.status(503).json({
        ok: false,
        errorCode: 'trading_rules_unavailable' as TradingErrorCode,
        error: 'Trading Rules are unavailable. New entry orders are blocked unless operator override is explicit.',
      });
    }

    const symbol = normalizeSymbol(body.symbol ?? LIVE_SYMBOL);
    const lookback = raw.engulfingLookbackCandles ?? 30;
    const entryTfs = raw.entryTimeframes;
    const exitTfs = raw.emergencyExitTimeframes;

    const allTfs = new Set([...entryTfs, ...exitTfs]);
    const candlesByTf = new Map<TradingRulesTimeframe, Candle[]>();
    const fetchFailedTfs: TradingRulesTimeframe[] = [];

    const now = Date.now();
    const minCandles = lookback + 5;

    await Promise.all([...allTfs].map(async (tf) => {
      try {
        const tfMs = ({ '5m': 300_000, '15m': 900_000, '1h': 3_600_000, '4h': 14_400_000 })[tf] ?? 900_000;
        const startTimeMs = now - tfMs * (minCandles + 2);
        const candles = await exchange.getCandles({
          symbol,
          timeframe: TF_LABEL_TO_CANDLE_TF[tf],
          startTimeMs,
          endTimeMs: now,
        });
        candlesByTf.set(tf, candles);
      } catch (err) {
        fetchFailedTfs.push(tf);
        logger.warn({ component: 'engulfing-gate', tf, err }, 'candle fetch failed for tf');
      }
    }));

    // Fail-safe: data fetch failure blocks new entry orders unless explicitly overridden.
    if (fetchFailedTfs.length > 0) {
      logRiskGateAudit({
        gate: 'multi_tf_engulfing',
        passed: operatorOverride,
        reason: operatorOverride ? 'candle_fetch_error_operator_override' : 'candle_fetch_error_fail_safe_block',
        details: { symbol, failedTimeframes: fetchFailedTfs },
      });
      if (operatorOverride) return next();
      return res.status(503).json({
        ok: false,
        errorCode: 'trading_rules_market_data_unavailable' as TradingErrorCode,
        error: 'Trading Rules market data is unavailable. New entry orders are blocked unless operator override is explicit.',
      });
    }

    const result = evaluateMultiTf(candlesByTf, {
      lookbackCandles: lookback,
      entryTimeframes: entryTfs,
      emergencyExitTimeframes: exitTfs,
    });

    // Attach result for downstream handlers to inspect
    (req as any)._engulfingResult = result;

    // Hard gate: no entry signal blocks, unless the operator explicitly overrides.
    if (!result.anyEntry) {
      logRiskGateAudit({
        gate: 'multi_tf_engulfing',
        passed: operatorOverride,
        reason: operatorOverride ? 'no_engulfing_entry_signal_operator_override' : 'no_engulfing_entry_signal',
        details: {
          symbol,
          signals: result.entry.map((s) => ({ tf: s.timeframe, detected: s.detected, reason: s.reason })),
        },
      });

      if (operatorOverride) return next();
      return res.status(403).json({
        ok: false,
        errorCode: 'no_engulfing_entry_signal' as TradingErrorCode,
        error: 'No engulfing entry signal detected for configured Trading Rules timeframes.',
      });
    }

    logRiskGateAudit({
      gate: 'multi_tf_engulfing',
      passed: true,
      details: {
        symbol,
        anyEntry: result.anyEntry,
        signals: result.entry.map((s) => ({ tf: s.timeframe, detected: s.detected })),
      },
    });

    return next();
  } catch (error) {
    logRiskGateAudit({
      gate: 'multi_tf_engulfing',
      passed: operatorOverride,
      reason: operatorOverride ? 'gate_exception_operator_override' : 'gate_exception_fail_safe_block',
      details: { error: error instanceof Error ? error.message : String(error) },
    });
    logger.error({ component: 'engulfing-gate', err: error, operatorOverride }, 'engulfing gate error');
    if (operatorOverride) return next();
    return res.status(503).json({
      ok: false,
      errorCode: 'trading_rules_gate_unavailable' as TradingErrorCode,
      error: 'Trading Rules gate failed. New entry orders are blocked unless operator override is explicit.',
    });
  }
}

async function radarContextPolicyGate(req: Request, res: Response, next: NextFunction) {
  const body = (req.body ?? {}) as {
    symbol?: string;
    side?: 'buy' | 'sell';
    price?: number;
    reduceOnly?: boolean;
    radarContextPolicyOverride?: boolean;
  };
  if (body.reduceOnly || isProtectionOnlyRequest(req)) return next();
  if (body.side !== 'buy' && body.side !== 'sell') return next();

  const symbol = normalizeSymbol(body.symbol ?? LIVE_SYMBOL);
  const side = body.side;
  const price = Number(body.price);
  const operatorOverride = body.radarContextPolicyOverride === true;
  const component = req.path.includes('/limit') ? 'owner-order-limit-api' : 'owner-order-api';
  const sourceLabel = component === 'owner-order-limit-api' ? 'manual:limit' : 'manual:market';

  const db = await getDb();
  const nowIso = new Date().toISOString();
  const policies = syncRadarContextPolicies({ db, nowIso });
  const policyGate = evaluateRadarContextPolicyEntry({ policies, symbol, side, nowIso });
  const intent = appendExecutionIntent(db, {
    component,
    strategy: 'manual',
    symbol,
    side,
    timeframe: undefined,
    price: Number.isFinite(price) ? price : 0,
    reduceOnly: false,
    reason: 'manual_live_order',
    sourceLabel,
    status: !policyGate.allowed && !operatorOverride ? 'policy_rejected' : 'created',
    auditedOperatorOverride: operatorOverride,
    policyDecision: operatorOverride ? 'override' : policyGate.allowed ? 'accepted' : 'rejected',
    policyReasonCode: policyGate.reasonCode,
    policySnapshot: policyGate.snapshot,
    metadata: {
      requestPath: req.path,
      method: req.method,
    },
  });

  (req as any)._executionIntentId = intent.id;
  (req as any)._radarContextPolicyGate = {
    allowed: policyGate.allowed,
    override: operatorOverride,
    snapshot: policyGate.snapshot,
  };

  logRiskGateAudit({
    gate: 'radar_context_policy',
    passed: policyGate.allowed || operatorOverride,
    reason: operatorOverride ? 'operator_override' : policyGate.reasonCode,
    details: { symbol, side, executionIntentId: intent.id, policyId: policyGate.snapshot?.policyId ?? null, requestPath: req.path },
  });

  if (!policyGate.allowed && !operatorOverride) {
    appendTradeEvent(db.data, {
      symbol,
      source: 'live',
      type: 'signal_rejected',
      timestamp: nowIso,
      correlationId: `intent-${intent.id}`,
      side: toTradeSide(side),
      price: Number.isFinite(price) ? price : undefined,
      reason: 'manual_live_order_radar_policy_rejected',
      payload: {
        executionIntentId: intent.id,
        policyReasonCode: policyGate.reasonCode ?? 'radar_context_policy_blocked',
        policyId: policyGate.snapshot?.policyId ?? null,
      },
    });
    await db.write();
    return res.status(403).json({
      ok: false,
      errorCode: 'invalid_params' as TradingErrorCode,
      error: policyGate.reasonCode ?? 'radar_context_policy_blocked',
      executionIntentId: intent.id,
      policyId: policyGate.snapshot?.policyId ?? null,
    });
  }

  await db.write();
  return next();
}

let ingestBusy = false;
let wsReconnectTimer: NodeJS.Timeout | null = null;
let restFallbackTimer: NodeJS.Timeout | null = null;
let midStreamHandle: MidStreamHandle | null = null;
let latestLiveTick: { symbol: string; price: number; timestamp: string } | null = null;
const latestTickBySymbol = new Map<string, { price: number; timestamp: string; source: 'ws' | 'rest' }>();

// ─── WS reconnect backoff state ──────────────────────────────────────
const WS_BACKOFF_INITIAL_MS = 1000;
const WS_BACKOFF_MAX_MS = 60_000;
let wsBackoffMs = WS_BACKOFF_INITIAL_MS;
const wsDiag = { reconnectAttempts: 0, disconnectCount: 0, lastReconnectDelayMs: 0 };

function parseTimeframe(raw: unknown): CandleTimeframe {
  if (raw === '1m' || raw === '5m' || raw === '15m' || raw === '1h' || raw === '4h') {
    return raw;
  }
  return '5m';
}

function timeframeToMs(timeframe: CandleTimeframe): number {
  if (timeframe === '1m') return 60_000;
  if (timeframe === '5m') return 5 * 60_000;
  if (timeframe === '15m') return 15 * 60_000;
  if (timeframe === '1h') return 60 * 60_000;
  return 4 * 60 * 60_000;
}

function normalizeSymbol(raw: unknown): string {
  const value = String(raw ?? LIVE_SYMBOL).trim();
  if (!value) return LIVE_SYMBOL;

  if (value.includes(':')) {
    const [namespaceRaw, symbolRaw] = value.split(':', 2);
    const namespace = String(namespaceRaw ?? '').trim().toLowerCase();
    const symbol = String(symbolRaw ?? '').trim().toUpperCase();
    if (namespace && symbol) return `${namespace}:${symbol}`;
  }

  return value.toUpperCase();
}

function resolveMidForSymbol(mids: Record<string, number>, symbol: string): number | null {
  const normalized = normalizeSymbol(symbol);
  const direct = Number(mids[normalized]);
  if (Number.isFinite(direct)) return direct;

  if (normalized.includes(':')) {
    const [, coreRaw] = normalized.split(':', 2);
    const core = String(coreRaw ?? '').trim().toUpperCase();
    const fallback = Number(mids[core]);
    if (Number.isFinite(fallback)) return fallback;
  }

  return null;
}

function resolveMonitorPrice(
  mids: Record<string, number>,
  symbol: string,
  candles?: Candle[] | null,
): number | null {
  const mid = resolveMidForSymbol(mids, symbol);
  if (mid !== null && Number.isFinite(mid) && mid > 0) return mid;

  const lastClosedClose = Number(candles?.[candles.length - 1]?.close ?? NaN);
  if (Number.isFinite(lastClosedClose) && lastClosedClose > 0) return lastClosedClose;

  return null;
}

function enabledAllocationTotalPct(rules: TradingRulesSettings): number {
  const total = rules.coins
    .filter((coin) => coin.enabled)
    .reduce((sum, coin) => sum + Number(coin.pct || 0), 0);
  return Math.round(total * 100) / 100;
}

function toTradeSide(side: 'buy' | 'sell'): 'long' | 'short' {
  return side === 'buy' ? 'long' : 'short';
}

function isConfirmed(raw: unknown): boolean {
  return raw === true;
}

function maskAddress(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const v = value.trim();
  if (v.length <= 10) return v;
  return `${v.slice(0, 6)}…${v.slice(-4)}`;
}

function maskPrivateKey(value: string | undefined): string {
  if (!value) return '';
  const v = value.trim();
  if (v.length <= 12) return '••••••';
  return `${v.slice(0, 6)}••••${v.slice(-4)}`;
}

function normalizeHyperliquidEnabled(value: unknown): boolean {
  const normalized = String(value ?? '').trim().toLowerCase();
  return !(normalized === '0' || normalized === 'false' || normalized === 'off' || normalized === 'no');
}

function normalizeStoredHyperliquidSettings(input?: {
  accountAddress?: string;
  apiWalletAddress?: string;
  apiPrivateKey?: string;
  enabled?: boolean;
}) {
  return {
    accountAddress: String(input?.accountAddress ?? '').trim(),
    apiWalletAddress: String(input?.apiWalletAddress ?? '').trim(),
    apiPrivateKey: String(input?.apiPrivateKey ?? '').trim(),
    enabled: input?.enabled !== false,
  };
}

function getConfiguredHyperliquidSettings(settings?: { hyperliquid?: { accountAddress?: string; apiWalletAddress?: string; apiPrivateKey?: string; enabled?: boolean } }) {
  return normalizeStoredHyperliquidSettings(settings?.hyperliquid);
}

function buildHyperliquidExchangeView(settings: { accountAddress: string; apiWalletAddress: string; apiPrivateKey: string; enabled: boolean }, connected = false) {
  const tradingConfigured = Boolean(settings.enabled && settings.accountAddress && settings.apiWalletAddress && settings.apiPrivateKey);
  return {
    accountAddress: settings.accountAddress,
    apiWalletAddress: settings.apiWalletAddress,
    hasPrivateKey: Boolean(settings.apiPrivateKey),
    privateKeyMasked: maskPrivateKey(settings.apiPrivateKey),
    enabled: settings.enabled,
    tradingConfigured,
    connected: connected && tradingConfigured,
  };
}

function applyHyperliquidEnv(settings: {
  accountAddress?: string;
  apiWalletAddress?: string;
  apiPrivateKey?: string;
  enabled?: boolean;
}): void {
  const enabled = settings.enabled !== false;
  process.env.HYPERLIQUID_ENABLED = enabled ? '1' : '0';

  const entries: Array<[string, string | undefined]> = [
    ['HYPERLIQUID_ACCOUNT_ADDRESS', enabled ? settings.accountAddress : ''],
    ['HYPERLIQUID_API_WALLET_ADDRESS', enabled ? settings.apiWalletAddress : ''],
    ['HYPERLIQUID_API_PRIVATE_KEY', enabled ? settings.apiPrivateKey : ''],
  ];

  for (const [key, raw] of entries) {
    const value = String(raw ?? '').trim();
    if (value) process.env[key] = value;
    else delete process.env[key];
  }
}

function getRuntimeHyperliquidSettings() {
  const accountAddress = String(process.env.HYPERLIQUID_ACCOUNT_ADDRESS ?? '').trim();
  const apiWalletAddress = String(process.env.HYPERLIQUID_API_WALLET_ADDRESS ?? '').trim();
  const apiPrivateKey = String(process.env.HYPERLIQUID_API_PRIVATE_KEY ?? '').trim();
  const enabled = normalizeHyperliquidEnabled(process.env.HYPERLIQUID_ENABLED ?? '1');
  return {
    accountAddress,
    apiWalletAddress,
    apiPrivateKey,
    enabled,
    hasPrivateKey: Boolean(apiPrivateKey),
    tradingConfigured: Boolean(enabled && accountAddress && apiWalletAddress && apiPrivateKey),
  };
}

async function hydrateHyperliquidEnvFromDb(): Promise<void> {
  const db = await getDb();
  const stored = normalizeStoredHyperliquidSettings(db.data.settings.hyperliquid);
  applyHyperliquidEnv(stored);
}

async function persistHyperliquidSettings(settings: {
  accountAddress: string;
  apiWalletAddress: string;
  apiPrivateKey: string;
  enabled: boolean;
}): Promise<void> {
  const normalized = normalizeStoredHyperliquidSettings(settings);
  const db = await getDb();
  db.data.settings.hyperliquid = {
    accountAddress: normalized.accountAddress,
    apiWalletAddress: normalized.apiWalletAddress,
    apiPrivateKey: normalized.apiPrivateKey,
    enabled: normalized.enabled,
  };
  await db.write();

  applyHyperliquidEnv(normalized);
}

async function ingestPrice(symbol: string, price: number, source: 'ws' | 'rest') {
  if (!Number.isFinite(price)) return;

  const normalizedSymbol = normalizeSymbol(symbol);
  const timestamp = new Date().toISOString();

  latestTickBySymbol.set(normalizedSymbol, {
    price,
    timestamp,
    source
  });

  // Keep dashboard latest tick anchored to LIVE_SYMBOL.
  if (normalizedSymbol === LIVE_SYMBOL) {
    latestLiveTick = {
      symbol: normalizedSymbol,
      price,
      timestamp
    };
  }

  if (!ENABLE_PAPER_ENGINE) return;
  if (ingestBusy) return;

  ingestBusy = true;
  try {
    const db = await getDb();
    runSimulationStep(db.data, normalizedSymbol, price);
    await db.write();
  } finally {
    ingestBusy = false;
  }
}

function tickAgeMs(symbol: string): number | null {
  const tick = latestTickBySymbol.get(normalizeSymbol(symbol));
  if (!tick) return null;
  const age = Date.now() - new Date(tick.timestamp).getTime();
  return Number.isFinite(age) ? Math.max(0, age) : null;
}

async function fetchLiveMid(symbol = LIVE_SYMBOL): Promise<number | null> {
  try {
    const mids = await exchange.getMids();
    const price = resolveMidForSymbol(mids, symbol);
    return Number.isFinite(price) ? price : null;
  } catch {
    return null;
  }
}

async function ensureFreshTick(symbol: string): Promise<{ ok: boolean; staleMs: number | null; source: 'cache' | 'rest' | 'none' }> {
  const normalizedSymbol = normalizeSymbol(symbol);
  const age = tickAgeMs(normalizedSymbol);
  if (age !== null && age <= LIVE_TICK_STALE_MS) {
    return { ok: true, staleMs: age, source: 'cache' };
  }

  const price = await fetchLiveMid(normalizedSymbol);
  if (price) {
    await ingestPrice(normalizedSymbol, price, 'rest');
    return { ok: true, staleMs: 0, source: 'rest' };
  }

  return { ok: false, staleMs: age, source: 'none' };
}

async function ingestRestFallback() {
  const price = await fetchLiveMid(LIVE_SYMBOL);
  if (!price) return;
  await ingestPrice(LIVE_SYMBOL, price, 'rest');
}

function startRestFallback() {
  if (restFallbackTimer) return;
  restFallbackTimer = setInterval(() => {
    ingestRestFallback().catch((err) => logger.warn({ component: 'live', err }, 'REST fallback ingest failed'));
  }, REST_FALLBACK_MS);
  restFallbackTimer.unref?.();
}

function scheduleWsReconnect() {
  if (wsReconnectTimer) return;
  const delay = wsBackoffMs;
  wsDiag.reconnectAttempts++;
  wsDiag.lastReconnectDelayMs = delay;
  logger.info({ component: 'live', delayMs: delay, attempt: wsDiag.reconnectAttempts }, 'scheduling WS reconnect');
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    startLiveMidStream();
  }, delay);
  wsReconnectTimer.unref?.();
  // Exponential backoff: double up to cap
  wsBackoffMs = Math.min(wsBackoffMs * 2, WS_BACKOFF_MAX_MS);
}

function resetWsBackoff() {
  wsBackoffMs = WS_BACKOFF_INITIAL_MS;
}

function startLiveMidStream() {
  if (!exchange.subscribeMids) {
    logger.info({ component: 'live' }, 'exchange adapter has no mid stream, using REST fallback each minute');
    startRestFallback();
    return;
  }

  if (midStreamHandle) return;

  try {
    midStreamHandle = exchange.subscribeMids({
      symbols: [LIVE_SYMBOL],
      onOpen: () => {
        logger.info({ component: 'live' }, 'Hyperliquid WS connected');
        resetWsBackoff();
        startRestFallback(); // keep fallback as safety net
      },
      onMid: (symbol, price) => {
        ingestPrice(symbol, price, 'ws').catch((err) => logger.warn({ component: 'live', symbol, err }, 'WS price ingest failed'));
      },
      onClose: () => {
        wsDiag.disconnectCount++;
        logger.info({ component: 'live', disconnects: wsDiag.disconnectCount }, 'Hyperliquid WS disconnected, reconnecting...');
        midStreamHandle = null;
        scheduleWsReconnect();
      },
      onError: () => {
        // close event handles reconnect flow
      }
    });
  } catch {
    logger.warn({ component: 'live' }, 'Hyperliquid WS start failed, using REST fallback each minute');
    midStreamHandle = null;
    startRestFallback();
    scheduleWsReconnect();
  }
}

app.use(cors());
app.use(express.json({ limit: process.env.API_JSON_LIMIT || '256kb' }));

// ─── In-memory rate limiter (/api/* except health) ────────────────────
const RATE_LIMIT_READ_RPM = Math.max(1, Number(process.env.API_RATE_LIMIT_READ_RPM || 600));
const RATE_LIMIT_WRITE_RPM = Math.max(1, Number(process.env.API_RATE_LIMIT_WRITE_RPM || 120));
const RATE_LIMIT_WINDOW_MS = 60_000;
const rateLimitMap = new Map<string, number[]>();

// Prune stale entries every 2 minutes to prevent unbounded growth
const rateLimitPruneTimer = setInterval(() => {
  const cutoff = Date.now() - RATE_LIMIT_WINDOW_MS;
  for (const [ip, timestamps] of rateLimitMap) {
    const fresh = timestamps.filter(t => t > cutoff);
    if (fresh.length === 0) rateLimitMap.delete(ip);
    else rateLimitMap.set(ip, fresh);
  }
}, 2 * 60_000);
rateLimitPruneTimer.unref();

app.use('/api', (req: Request, res: Response, next: NextFunction) => {
  // Exclude health endpoints from rate limiting
  if (req.path === '/health' || req.path === '/health/perf') return next();
  // Optimization endpoints are intentionally chatty while a long-running job is active;
  // they are owner-protected and should not be throttled by the generic API limiter.
  if (req.path.startsWith('/optimization')) return next();

  const ip = req.ip || req.socket.remoteAddress || 'unknown';
  const now = Date.now();
  const cutoff = now - RATE_LIMIT_WINDOW_MS;
  const rpm = req.method === 'GET' || req.method === 'HEAD' ? RATE_LIMIT_READ_RPM : RATE_LIMIT_WRITE_RPM;

  let timestamps = rateLimitMap.get(ip);
  if (!timestamps) {
    timestamps = [];
    rateLimitMap.set(ip, timestamps);
  }

  // Remove expired entries for this IP
  while (timestamps.length > 0 && timestamps[0] <= cutoff) {
    timestamps.shift();
  }

  if (timestamps.length >= rpm) {
    logger.warn({ component: 'rate-limit', ip, count: timestamps.length, limit: rpm, method: req.method, path: req.path }, 'rate limit exceeded');
    return res.status(429).json({ ok: false, error: 'rate_limited' });
  }

  timestamps.push(now);
  next();
});

app.get('/api/health', (_req, res) => res.json({ ok: true }));

// ─── Performance / observability (non-invasive) ──────────────────────
app.get('/api/health/perf', ownerAuth, (_req, res) => {
  const mem = process.memoryUsage();
  const start = performance.now();
  setImmediate(() => {
    const lagMs = Math.round((performance.now() - start) * 100) / 100;
    res.json({
      ok: true,
      uptimeSeconds: Math.round(process.uptime()),
      memory: {
        rss: Math.round(mem.rss / 1024 / 1024 * 100) / 100,
        heapTotal: Math.round(mem.heapTotal / 1024 / 1024 * 100) / 100,
        heapUsed: Math.round(mem.heapUsed / 1024 / 1024 * 100) / 100,
        external: Math.round(mem.external / 1024 / 1024 * 100) / 100,
      },
      eventLoopLagMs: lagMs,
      ws: {
        reconnectAttempts: wsDiag.reconnectAttempts,
        lastReconnectDelayMs: wsDiag.lastReconnectDelayMs,
        disconnectCount: wsDiag.disconnectCount,
        connected: midStreamHandle !== null,
      },
      marketData: {
        liveSymbol: LIVE_SYMBOL,
        staleThresholdMs: LIVE_TICK_STALE_MS,
        lastTickAgeMs: tickAgeMs(LIVE_SYMBOL),
        stale: (() => {
          const age = tickAgeMs(LIVE_SYMBOL);
          return age === null ? true : age > LIVE_TICK_STALE_MS;
        })()
      },
      hyperliquidInfo: (exchange as unknown as { getInfoRequestStats?: () => unknown }).getInfoRequestStats?.() ?? null,
      timestamp: new Date().toISOString(),
    });
  });
});

app.get('/api/dashboard', async (_req, res) => {
  const dbPromise = getDb();
  const pendingRowsPromise = loadPendingConfirmationRows();
  const liveBasePromise = getCachedExchangeLiveState(LIVE_SYMBOL, getLiveMode());

  const db = await dbPromise;
  const rules = normalizeTradingRules(db.data.settings.tradingRules);
  const latestBias = resolveBiasForSymbol(LIVE_SYMBOL, rules, db.data.biasCommands);
  const { classBiasControls, customBiasControls } = buildDashboardBiasControls(rules, db.data.biasCommands);

  const latestTickPromise = latestLiveTick
    ? Promise.resolve(latestLiveTick)
    : fetchLiveMid(LIVE_SYMBOL).then((freshMid) => freshMid
      ? {
          symbol: LIVE_SYMBOL,
          price: freshMid,
          timestamp: new Date().toISOString()
        }
      : null);

  const [pendingRows, liveBase, latestTick] = await Promise.all([
    pendingRowsPromise,
    liveBasePromise,
    latestTickPromise,
  ]);
  const live = { ...liveBase, pendingConfirmations: pendingRows };
  const hyperliquid = getRuntimeHyperliquidSettings();

  res.json({
    latestBias,
    latestTick: latestTick ?? null,
    live,
    hyperliquid: {
      tradingConfigured: hyperliquid.tradingConfigured,
      connected: live.connected && hyperliquid.tradingConfigured,
    },
    classBiasControls,
    customBiasControls,
  });
});

app.get('/api/live/history', async (_req, res) => {
  try {
    const [executionFills, db] = await Promise.all([
      exchange.getFills(),
      getDb(),
    ]);

    const historySinceMs = Date.now() - 180 * 24 * 60 * 60_000;
    const externalFills = await collectExternalFills(db.data.settings, historySinceMs);

    const rows = [...executionFills, ...externalFills]
      .map((fill) => toLiveFill(fill, exchange.name))
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp));

    return res.json({ fills: rows });
  } catch (error) {
    return res.status(500).json({
      fills: [],
      error: error instanceof Error ? error.message : 'live_history_failed'
    });
  }
});

app.get('/api/analytics/daily/context', ownerAuth, async (req, res) => {
  const hoursRaw = Number(req.query.hours);
  const hours = Number.isFinite(hoursRaw) ? Math.max(1, Math.min(24 * 30, hoursRaw)) : 24;
  const windowMs = Math.round(hours * 60 * 60_000);

  try {
    const context = await buildDailyAnalyticsContext(windowMs);
    return res.json({ ok: true, context });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error instanceof Error ? error.message : 'daily_analytics_context_failed' });
  }
});

app.get('/api/analytics/daily/text', ownerAuth, async (req, res) => {
  const hoursRaw = Number(req.query.hours);
  const hours = Number.isFinite(hoursRaw) ? Math.max(1, Math.min(24 * 30, hoursRaw)) : 24;
  const windowMs = Math.round(hours * 60 * 60_000);

  try {
    const context = await buildDailyAnalyticsContext(windowMs);
    const text = renderDailyAnalyticsText(context);
    return res.json({ ok: true, context, text });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error instanceof Error ? error.message : 'daily_analytics_text_failed' });
  }
});

app.get('/api/analytics/history/summary', ownerAuth, async (req, res) => {
  const daysRaw = Number(req.query.days);
  const days = Number.isFinite(daysRaw) ? Math.max(1, Math.min(3650, Math.floor(daysRaw))) : 3650;

  try {
    const summary = await buildAnalyticsHistorySummary(days);
    return res.json({ ok: true, summary });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error instanceof Error ? error.message : 'analytics_history_summary_failed' });
  }
});

app.get('/api/analytics/quality', ownerAuth, async (req, res) => {
  const hoursRaw = Number(req.query.hours);
  const hours = Number.isFinite(hoursRaw) ? Math.max(1, Math.min(24 * 365, Math.floor(hoursRaw))) : 24 * 7;

  try {
    const metrics = await buildAnalyticsQualityMetrics(hours);
    return res.json({ ok: true, metrics });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error instanceof Error ? error.message : 'analytics_quality_failed' });
  }
});

app.get('/api/analytics/trades/post-trade', ownerAuth, async (req, res) => {
  const hoursRaw = Number(req.query.hours);
  const hours = Number.isFinite(hoursRaw) ? Math.max(1, Math.min(24 * 365, Math.floor(hoursRaw))) : 24 * 7;

  try {
    const items = await buildPostTradeAnalytics(hours);
    return res.json({ ok: true, hours, items });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error instanceof Error ? error.message : 'post_trade_analytics_failed' });
  }
});

app.get('/api/analytics/weekly/report', ownerAuth, async (_req, res) => {
  try {
    const report = await buildWeeklyAnalyticsReport();
    return res.json({ ok: true, text: report.text, summary: report.summary });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error instanceof Error ? error.message : 'weekly_report_failed' });
  }
});

app.get('/api/ai-master/snapshot', ownerAuth, async (req, res) => {
  const limitRaw = Number(req.query.limit);
  const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(200, Math.floor(limitRaw))) : 50;

  const { insights, qa } = await ensureAiMasterState();

  const payload: AiMasterSnapshotResponse = {
    ok: true,
    insights: insights.slice().sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, limit),
    qa: qa.slice().sort((a, b) => b.askedAt.localeCompare(a.askedAt)).slice(0, limit),
  };

  return res.json(payload);
});

app.post('/api/ai-master/insights', ownerAuth, async (req, res) => {
  const localNow = getTzParts(new Date(), DAILY_ANALYTICS_TZ);
  const state = await ensureAiMasterState();
  const runId = String(req.body?.runId ?? '').trim() || undefined;

  if (runId) {
    const existing = state.insights.find((item) => item.runId === runId);
    if (existing) return res.json({ ok: true, insight: existing, deduped: true });
  }

  const created = buildAiMasterInsight({
    id: `aii-${nanoid(10)}`,
    text: req.body?.text,
    model: req.body?.model,
    source: req.body?.source,
    promptVersion: req.body?.promptVersion,
    runId,
    worker: req.body?.worker,
    dayKey: req.body?.dayKey,
    fallbackDayKey: localNow.dayKey,
    createdAt: new Date().toISOString(),
    latencyMs: req.body?.latencyMs,
    timeoutMs: req.body?.timeoutMs,
    promptChars: req.body?.promptChars,
    responseChars: req.body?.responseChars,
    fallbackUsed: req.body?.fallbackUsed,
  });

  if (!created.ok) return res.status(400).json({ ok: false, error: created.error });

  state.insights.push(created.insight);
  pruneAiMasterCollections(state.insights, state.qa);
  await state.write();

  logger.info({
    component: 'ai-master',
    event: 'insight_saved',
    id: created.insight.id,
    runId: created.insight.runId,
    dayKey: created.insight.dayKey,
    model: created.insight.model,
    worker: created.insight.worker,
    status: created.insight.status,
    latencyMs: created.insight.latencyMs,
    timeoutMs: created.insight.timeoutMs,
    promptChars: created.insight.promptChars,
    responseChars: created.insight.responseChars,
    truncated: created.insight.truncated,
  }, 'ai master insight saved');

  return res.json({ ok: true, insight: created.insight });
});

app.post('/api/ai-master/qa', ownerAuth, async (req, res) => {
  const state = await ensureAiMasterState();
  const created = buildAiMasterQaQuestion({
    id: `aiq-${nanoid(10)}`,
    question: req.body?.question,
    askedAt: new Date().toISOString(),
  });

  if (!created.ok) return res.status(400).json({ ok: false, error: created.error });

  state.qa.push(created.item);
  pruneAiMasterCollections(state.insights, state.qa);
  await state.write();

  logger.info({
    component: 'ai-master',
    event: 'qa_queued',
    id: created.item.id,
    promptChars: created.item.promptChars,
    truncated: created.item.truncated,
  }, 'ai master question queued');

  return res.json({ ok: true, item: created.item });
});

app.get('/api/ai-master/qa/pending', ownerAuth, async (req, res) => {
  const limitRaw = Number(req.query.limit);
  const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(20, Math.floor(limitRaw))) : 1;
  const { qa } = await ensureAiMasterState();
  const pending = qa
    .filter((x) => x.status === 'pending')
    .sort((a, b) => a.askedAt.localeCompare(b.askedAt))
    .slice(0, limit);

  return res.json({ ok: true, pending });
});

app.post('/api/ai-master/qa/:id/answer', ownerAuth, async (req, res) => {
  const id = String(req.params.id || '').trim();
  if (!id) return res.status(400).json({ ok: false, error: 'id_required' });

  const state = await ensureAiMasterState();
  const item = state.qa.find((x) => x.id === id);
  if (!item) return res.status(404).json({ ok: false, error: 'qa_item_not_found' });

  const updated = applyAiMasterQaAnswer(item, {
    answer: req.body?.answer,
    error: req.body?.error,
    model: req.body?.model,
    runId: req.body?.runId,
    worker: req.body?.worker,
    latencyMs: req.body?.latencyMs,
    timeoutMs: req.body?.timeoutMs,
    promptChars: req.body?.promptChars,
    responseChars: req.body?.responseChars,
    fallbackUsed: req.body?.fallbackUsed,
    fallbackMessage: req.body?.fallbackMessage,
    answeredAt: new Date().toISOString(),
  });

  if (!updated.ok) return res.status(400).json({ ok: false, error: updated.error });

  pruneAiMasterCollections(state.insights, state.qa);
  await state.write();

  logger.info({
    component: 'ai-master',
    event: 'qa_answer_recorded',
    id: updated.item.id,
    runId: updated.item.runId,
    model: updated.item.model,
    worker: updated.item.worker,
    status: updated.item.status,
    latencyMs: updated.item.latencyMs,
    timeoutMs: updated.item.timeoutMs,
    promptChars: updated.item.promptChars,
    responseChars: updated.item.responseChars,
    fallbackUsed: updated.item.fallbackUsed,
    truncated: updated.item.truncated,
  }, 'ai master qa answer recorded');

  return res.json({ ok: true, item: updated.item });
});

app.get('/api/live/candles', async (req, res) => {
  const symbol = normalizeSymbol(req.query.symbol);
  const timeframe = parseTimeframe(req.query.timeframe);
  const limit = Math.max(50, Math.min(500, Number(req.query.limit) || 200));
  const endTimeMs = Date.now();
  const startTimeMs = endTimeMs - timeframeToMs(timeframe) * (limit + 5);

  try {
    const candles = await exchange.getCandles({ symbol, timeframe, startTimeMs, endTimeMs });
    const rows = candles.slice(-limit);
    return res.json({ symbol, timeframe, candles: rows });
  } catch (error) {
    return res.status(500).json({
      symbol,
      timeframe,
      candles: [],
      error: error instanceof Error ? error.message : 'live_candles_failed'
    });
  }
});

app.get('/api/settings/trading-rules', async (_req, res) => {
  const db = await getDb();
  const persisted = db.data.settings.tradingRules;
  const rules = normalizeTradingRules(persisted);

  if (JSON.stringify(rules) !== JSON.stringify(persisted)) {
    db.data.settings.tradingRules = rules;
    await db.write();
    await rulesCache.refreshNow().catch((err) => logger.warn({ component: 'runtime-rules', err }, 'forced rules refresh after normalization failed'));
    logger.info({ component: 'trading-rules', persistedType: typeof persisted }, 'trading rules payload normalized and persisted');
  }

  return res.json({ ok: true, rules });
});

app.get('/api/settings/trading-rules/symbols', async (_req, res) => {
  const symbols = await getTradableSymbolsCached({ allowStale: true });
  if (!symbols) {
    return res.status(503).json({ ok: false, error: 'symbol_catalog_unavailable', symbols: [] });
  }

  const db = await getDb();
  const rules = normalizeTradingRules(db.data.settings.tradingRules);
  const configuredSymbols = [...new Set((rules.coins ?? []).map((coin) => normalizeSymbol(coin.symbol)).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));

  return res.json({
    ok: true,
    symbols,
    configuredSymbols,
    cacheAgeMs: tradableSymbolsCache ? Date.now() - tradableSymbolsCache.fetchedAtMs : null,
  });
});

app.put('/api/settings/trading-rules', async (req, res) => {
  const rules = normalizeTradingRules(req.body);
  const enabled = rules.coins.filter((coin) => coin.enabled);
  const totalPct = enabledAllocationTotalPct(rules);

  const tradableSymbols = await getTradableSymbolsCached({ allowStale: true });
  if (!tradableSymbols) {
    return res.status(503).json({ ok: false, error: 'symbol_catalog_unavailable' });
  }

  const allowedSet = new Set(tradableSymbols.map((s) => normalizeSymbol(s)));
  const invalidSymbols = getInvalidRuleSymbols(rules, allowedSet);
  if (invalidSymbols.length > 0) {
    const unresolved: string[] = [];
    for (const symbol of invalidSymbols) {
      const ok = await isSymbolResolvableOnExchange(symbol);
      if (!ok) unresolved.push(symbol);
    }

    if (unresolved.length > 0) {
      return res.status(400).json({
        ok: false,
        error: 'symbols_not_on_exchange',
        invalidSymbols: unresolved,
      });
    }
  }

  if (enabled.length === 0) {
    return res.status(400).json({ ok: false, error: 'at_least_one_coin_required' });
  }

  if (Math.abs(totalPct - 100) > 0.01) {
    return res.status(400).json({
      ok: false,
      error: 'allocation_total_must_be_100',
      totalPct
    });
  }

  const db = await getDb();
  db.data.settings.tradingRules = rules;
  await db.write();

  // Ensure monitors pick up new rules immediately (no cache-delay window).
  await rulesCache.refreshNow().catch((err) => logger.warn({ component: 'runtime-rules', err }, 'forced rules refresh failed'));

  return res.json({ ok: true, rules });
});

// ─── Effective Trading Rules (diagnostic) ─────────────────────────────
app.get('/api/settings/trading-rules/effective', ownerAuth, (_req, res) => {
  return res.json({ ok: true, ...rulesCache.getEffectiveRules() });
});

app.get('/api/settings/radar', async (_req, res) => {
  const db = await getDb();
  const persisted = db.data.settings.radarRuntime;
  const runtime = normalizeRadarRuntimeFromSettings(db.data.settings);

  if (JSON.stringify(runtime) !== JSON.stringify(persisted)) {
    db.data.settings.radarRuntime = runtime;
    await db.write();
  }

  const payload: RadarRuntimeSettingsResponse = { ok: true, runtime };
  return res.json(payload);
});

app.put('/api/settings/radar', async (req, res) => {
  const db = await getDb();
  const current = normalizeRadarRuntimeFromSettings(db.data.settings);
  const runtime = normalizeRadarRuntimeSettings({ ...current, ...(req.body as Record<string, unknown> | undefined) }, current.autoConfirm);
  db.data.settings.radarRuntime = runtime;
  await db.write();

  const payload: RadarRuntimeSettingsResponse = { ok: true, runtime };
  return res.json(payload);
});

app.get('/api/settings/exchange', async (_req, res) => {
  const liveMode = getLiveMode();
  const live = await getCachedExchangeLiveState(LIVE_SYMBOL, liveMode);

  const db = await getDb();
  const tg = db.data.settings.telegramNotify;
  const hyperliquid = getConfiguredHyperliquidSettings(db.data.settings);
  const hyperliquidView = buildHyperliquidExchangeView(hyperliquid, live.connected);
  const connected = hyperliquidView.connected;

  return res.json({
    exchange: exchange.name,
    connected,
    accountAddress: maskAddress(hyperliquid.accountAddress),
    walletAddress: maskAddress(hyperliquid.apiWalletAddress),
    mode: liveMode,
    account: live.account,
    capabilities: {
      privateAccount: exchange.capabilities.privateAccount,
      privateTrading: exchange.capabilities.privateTrading,
      realtimeMids: exchange.capabilities.realtimeMids
    },
    hyperliquid: hyperliquidView,
    externalExchanges: {
      bybit: getMaskedBybitConnectionSettings(db.data.settings),
    },
    telegramNotify: {
      hasToken: Boolean(tg?.botToken?.trim()),
      chatId: tg?.chatId || '',
      botTokenMasked: maskBotToken(String(tg?.botToken || '')),
      notifyOpen: tg?.notifyOpen !== false,
      notifyTp: tg?.notifyTp !== false,
      notifySl: tg?.notifySl !== false,
      notifyManualConfirm: tg?.notifyManualConfirm !== false,
      notifyDailyAnalytics: tg?.notifyDailyAnalytics !== false,
      notifySignalRejected: tg?.notifySignalRejected === true,
      notifyOrderRejected: tg?.notifyOrderRejected === true,
      notifyPositionClosed: tg?.notifyPositionClosed === true,
    },
    error: live.error
  });
});

app.put('/api/settings/exchange/hyperliquid', ownerAuth, async (req, res) => {
  const {
    accountAddress,
    apiWalletAddress,
    apiPrivateKey,
  } = req.body as {
    accountAddress?: string;
    apiWalletAddress?: string;
    apiPrivateKey?: string;
  };

  if (accountAddress === undefined && apiWalletAddress === undefined && apiPrivateKey === undefined) {
    return res.status(400).json({ ok: false, error: 'no_fields_provided' });
  }

  const db = await getDb();
  const current = getConfiguredHyperliquidSettings(db.data.settings);
  const next = {
    accountAddress: accountAddress !== undefined ? String(accountAddress).trim() : current.accountAddress,
    apiWalletAddress: apiWalletAddress !== undefined ? String(apiWalletAddress).trim() : current.apiWalletAddress,
    apiPrivateKey: apiPrivateKey !== undefined ? String(apiPrivateKey).trim() : current.apiPrivateKey,
    enabled: true,
  };

  if (next.accountAddress && !/^0x[a-fA-F0-9]{40}$/.test(next.accountAddress)) {
    return res.status(400).json({ ok: false, error: 'invalid_account_address' });
  }

  if (next.apiWalletAddress && !/^0x[a-fA-F0-9]{40}$/.test(next.apiWalletAddress)) {
    return res.status(400).json({ ok: false, error: 'invalid_api_wallet_address' });
  }

  if (next.apiPrivateKey && !/^0x[a-fA-F0-9]{64}$/.test(next.apiPrivateKey)) {
    return res.status(400).json({ ok: false, error: 'invalid_api_private_key_format' });
  }

  await persistHyperliquidSettings(next);

  res.json({
    ok: true,
    restartScheduled: true,
    exchange: buildHyperliquidExchangeView(next, false),
  });

  setTimeout(() => {
    logger.warn({ component: 'server' }, 'restarting process to apply Hyperliquid credential changes');
    process.exit(0);
  }, 350);
});

app.delete('/api/settings/exchange/hyperliquid', ownerAuth, async (_req, res) => {
  const db = await getDb();
  const current = getConfiguredHyperliquidSettings(db.data.settings);
  const next = {
    ...current,
    enabled: false,
  };

  await persistHyperliquidSettings(next);

  res.json({
    ok: true,
    restartScheduled: true,
    exchange: buildHyperliquidExchangeView(next, false),
  });

  setTimeout(() => {
    logger.warn({ component: 'server' }, 'restarting process to apply Hyperliquid logout');
    process.exit(0);
  }, 350);
});

app.put('/api/settings/telegram-notify', ownerAuth, async (req, res) => {
  const {
    botToken,
    chatId,
    notifyOpen,
    notifyTp,
    notifySl,
    notifyManualConfirm,
    notifyDailyAnalytics,
    notifySignalRejected,
    notifyOrderRejected,
    notifyPositionClosed,
  } = req.body as {
    botToken?: string;
    chatId?: string;
    notifyOpen?: boolean;
    notifyTp?: boolean;
    notifySl?: boolean;
    notifyManualConfirm?: boolean;
    notifyDailyAnalytics?: boolean;
    notifySignalRejected?: boolean;
    notifyOrderRejected?: boolean;
    notifyPositionClosed?: boolean;
  };

  const db = await getDb();
  const current = db.data.settings.telegramNotify ?? {
    botToken: '',
    chatId: '',
    notifyOpen: true,
    notifyTp: true,
    notifySl: true,
    notifyManualConfirm: true,
    notifyDailyAnalytics: true,
    notifySignalRejected: false,
    notifyOrderRejected: false,
    notifyPositionClosed: false,
  };

  db.data.settings.telegramNotify = {
    botToken: botToken !== undefined ? String(botToken).trim() : current.botToken,
    chatId: chatId !== undefined ? String(chatId).trim() : current.chatId,
    notifyOpen: notifyOpen !== undefined ? Boolean(notifyOpen) : current.notifyOpen,
    notifyTp: notifyTp !== undefined ? Boolean(notifyTp) : current.notifyTp,
    notifySl: notifySl !== undefined ? Boolean(notifySl) : current.notifySl,
    notifyManualConfirm: notifyManualConfirm !== undefined ? Boolean(notifyManualConfirm) : current.notifyManualConfirm,
    notifyDailyAnalytics: notifyDailyAnalytics !== undefined ? Boolean(notifyDailyAnalytics) : current.notifyDailyAnalytics !== false,
    notifySignalRejected: notifySignalRejected !== undefined ? Boolean(notifySignalRejected) : current.notifySignalRejected === true,
    notifyOrderRejected: notifyOrderRejected !== undefined ? Boolean(notifyOrderRejected) : current.notifyOrderRejected === true,
    notifyPositionClosed: notifyPositionClosed !== undefined ? Boolean(notifyPositionClosed) : current.notifyPositionClosed === true,
  };

  await db.write();

  if (!telegramUpdateTimer) startTelegramUpdateLoop();
  if (!telegramOutboxTimer) startTelegramOutboxLoop();

  return res.json({
    ok: true,
    telegramNotify: {
      hasToken: Boolean(db.data.settings.telegramNotify.botToken),
      chatId: db.data.settings.telegramNotify.chatId,
      botTokenMasked: maskBotToken(db.data.settings.telegramNotify.botToken),
      notifyOpen: db.data.settings.telegramNotify.notifyOpen,
      notifyTp: db.data.settings.telegramNotify.notifyTp,
      notifySl: db.data.settings.telegramNotify.notifySl,
      notifyManualConfirm: db.data.settings.telegramNotify.notifyManualConfirm,
      notifyDailyAnalytics: db.data.settings.telegramNotify.notifyDailyAnalytics,
      notifySignalRejected: db.data.settings.telegramNotify.notifySignalRejected === true,
      notifyOrderRejected: db.data.settings.telegramNotify.notifyOrderRejected === true,
      notifyPositionClosed: db.data.settings.telegramNotify.notifyPositionClosed === true,
    },
  });
});

app.post('/api/settings/telegram-notify/test', ownerAuth, async (_req, res) => {
  const cfg = await getTelegramConfig();
  if (!cfg) {
    return res.status(400).json({ ok: false, error: 'telegram_not_configured' });
  }
  await enqueueTelegramOutbox({
    category: 'system',
    dedupeKey: `test:${Math.floor(Date.now() / 10000)}`,
    text: `✅ Coinmaster Telegram test ping\nTime: ${new Date().toISOString()}`,
  });
  return res.json({ ok: true });
});

// ─── Read-Only Exchanges Settings ───────────────────────────────────────
app.get('/api/settings/read-only-exchanges', ownerAuth, async (_req, res) => {
  const db = await getDb();
  const statuses = await getExchangeConnectionStatuses(db.data.settings);

  return res.json({
    ok: true,
    exchanges: {
      bybit: getMaskedBybitConnectionSettings(db.data.settings),
    },
    status: statuses,
  });
});

app.put('/api/settings/read-only-exchanges/:exchangeId', ownerAuth, async (req, res) => {
  const { exchangeId } = req.params;
  if (exchangeId !== 'bybit') {
    return res.status(400).json({ ok: false, error: 'exchange_not_supported' });
  }

  const payload = req.body as ExchangeConnectionSettingsPayload;
  const db = await getDb();

  applyBybitConnectionPatch(db.data.settings, payload);
  await db.write();

  return res.json({
    ok: true,
    bybit: getMaskedBybitConnectionSettings(db.data.settings),
  });
});

app.post('/api/settings/read-only-exchanges/:exchangeId/test', ownerAuth, async (req, res) => {
  const { exchangeId } = req.params;
  if (exchangeId !== 'bybit') {
    return res.status(400).json({ ok: false, error: 'exchange_not_supported' });
  }

  const db = await getDb();
  const status = await testReadOnlyExchangeConnection(db.data.settings, exchangeId);

  return res.json({
    ok: status.connected,
    status,
  });
});

app.get('/api/settings/telegram-notify/health', ownerAuth, async (_req, res) => {
  const db = await getDb();
  const outbox = Array.isArray(db.data.telegramOutbox) ? db.data.telegramOutbox : [];
  const queued = outbox.filter((m) => m.status === 'queued');
  const failed = outbox.filter((m) => m.status === 'failed');
  const oldestQueued = queued
    .map((m) => Date.parse(m.createdAt))
    .filter((ts) => Number.isFinite(ts))
    .sort((a, b) => a - b)[0];

  return res.json({
    ok: true,
    totals: {
      queued: queued.length,
      failed: failed.length,
      all: outbox.length,
    },
    oldestQueuedAgeSec: oldestQueued ? Math.max(0, Math.floor((Date.now() - oldestQueued) / 1000)) : 0,
    failedSample: failed.slice(-5).map((m) => ({ id: m.id, attempts: m.attempts, error: m.lastError })),
    loop: {
      outboxRunning: Boolean(telegramOutboxTimer),
      updateRunning: Boolean(telegramUpdateTimer),
    },
    configPresent: Boolean(db.data.settings.telegramNotify?.botToken && db.data.settings.telegramNotify?.chatId),
  });
});

app.post('/api/bias', async (req, res) => {
  const payload = req.body as {
    targetType?: 'symbol' | 'class';
    symbol?: string;
    assetClass?: AssetClass;
    bias?: Bias;
  };

  const bias = payload?.bias;
  if (bias !== 'long' && bias !== 'short' && bias !== 'off') {
    return res.status(400).json({ error: 'invalid_payload' });
  }

  let targetSymbol = '';

  if (payload?.targetType === 'class') {
    const klass = String(payload.assetClass ?? '').trim().toLowerCase();
    if (!ASSET_CLASS_ORDER.includes(klass as AssetClass)) {
      return res.status(400).json({ error: 'invalid_asset_class' });
    }
    targetSymbol = classBiasCommandSymbol(klass as AssetClass);
  } else {
    const rawSymbol = String(payload?.symbol ?? '').trim();
    const normalizedSymbol = normalizeSymbol(rawSymbol);
    if (!normalizedSymbol) {
      return res.status(400).json({ error: 'invalid_payload' });
    }
    targetSymbol = normalizedSymbol;
  }

  const db = await getDb();
  const cmd = submitBias(db.data, targetSymbol, bias);
  await db.write();
  return res.json({ ok: true, command: cmd });
});

if (ENABLE_SIMULATION_API) {
  app.post('/api/simulate/tick', async (req, res) => {
    const { symbol = LIVE_SYMBOL, price } = req.body as { symbol?: string; price: number };
    if (price === undefined || Number.isNaN(price)) {
      return res.status(400).json({ error: 'price_required' });
    }

    const db = await getDb();
    const signal = runSimulationStep(db.data, symbol.toUpperCase(), Number(price));
    await db.write();
    return res.json({ ok: true, signal });
  });
}

if (ENABLE_REPLAY_API) {
  app.post('/api/replay/run', async (req, res) => {
    const {
      symbol = LIVE_SYMBOL,
      bias,
      timeframe,
      startTimeMs,
      endTimeMs,
      depositUsd
    } = req.body as {
      symbol?: string;
      bias?: Bias;
      timeframe?: CandleTimeframe;
      startTimeMs?: number;
      endTimeMs?: number;
      depositUsd?: number;
    };

    if (bias !== 'long' && bias !== 'short') {
      return res.status(400).json({ error: 'bias_required_long_or_short' });
    }

    const fromMs = Number(startTimeMs);
    const toMs = Number(endTimeMs);
    if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || toMs <= fromMs) {
      return res.status(400).json({ error: 'invalid_time_range' });
    }

    const tf = parseTimeframe(timeframe);

    try {
      const candles = await exchange.getCandles({
        symbol: symbol.toUpperCase(),
        timeframe: tf,
        startTimeMs: fromMs,
        endTimeMs: toMs
      });

      const summary = runDeterministicReplay({
        symbol: symbol.toUpperCase(),
        bias,
        timeframe: tf,
        candles,
        depositUsd
      });

      return res.json({ ok: true, summary });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'replay_failed';
      const status = message === 'not_enough_candles_for_replay' ? 400 : 500;
      return res.status(status).json({ error: message });
    }
  });
}

app.get('/api/backtest/runs', ownerAuth, async (_req, res) => {
  const db = await getDb();
  await db.reload();
  await reconcileBacktestState(db);
  await reconcileOptimizationState(db);
  db.data.backtestRuns = compactBacktestRuns(Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : []);
  return res.json({ ok: true, runs: db.data.backtestRuns });
});

app.get('/api/backtest/runs/:id', ownerAuth, async (req, res) => {
  const db = await getDb();
  await db.reload();
  await reconcileBacktestState(db);
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const run = db.data.backtestRuns.find((item) => item.id === req.params.id);
  if (!run) {
    return res.status(404).json({ ok: false, error: 'backtest_run_not_found' });
  }
  return res.json({ ok: true, run });
});

app.get('/api/backtest/ai-analysis/pending', ownerAuth, async (_req, res) => {
  const db = await getDb();
  await db.reload();
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const runs = db.data.backtestRuns.filter((run) => run.status === 'completed' && run.aiAnalysis?.status === 'pending');
  return res.json({ ok: true, runs });
});

app.post('/api/backtest/runs/:id/ai-analysis/request', ownerAuth, async (req, res) => {
  const db = await getDb();
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const run = db.data.backtestRuns.find((item) => item.id === req.params.id);
  if (!run) {
    return res.status(404).json({ ok: false, error: 'backtest_run_not_found' });
  }
  if (run.status !== 'completed') {
    return res.status(409).json({ ok: false, error: 'backtest_run_not_completed' });
  }
  if (run.aiAnalysis?.status === 'completed' && run.aiAnalysis?.report) {
    return res.json({ ok: true, run });
  }

  markBacktestAiAnalysisRequested(run);
  await db.write();
  return res.json({ ok: true, run });
});

app.post('/api/backtest/runs/:id/ai-analysis/complete', ownerAuth, async (req, res) => {
  const db = await getDb();
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const run = db.data.backtestRuns.find((item) => item.id === req.params.id);
  if (!run) {
    return res.status(404).json({ ok: false, error: 'backtest_run_not_found' });
  }
  if (run.status !== 'completed') {
    return res.status(409).json({ ok: false, error: 'backtest_run_not_completed' });
  }

  applyBacktestAiAnalysisResult(run, {
    model: (req.body as { model?: unknown } | undefined)?.model,
    summary: (req.body as { summary?: unknown } | undefined)?.summary,
    report: (req.body as { report?: unknown } | undefined)?.report,
    recommendations: (req.body as { recommendations?: unknown } | undefined)?.recommendations,
    error: (req.body as { error?: unknown } | undefined)?.error,
  });
  await db.write();
  return res.json({ ok: true, run });
});

app.post('/api/backtest/runs', ownerAuth, async (req, res) => {
  const body = (req.body ?? {}) as Partial<BacktestCreateRunRequest>;
  const symbol = normalizeSymbol(body.symbol);
  const startTimeMs = Number(body.startTimeMs);
  const endTimeMs = Number(body.endTimeMs);

  if (!symbol) {
    return res.status(400).json({ ok: false, error: 'symbol_required' });
  }
  if (!Number.isFinite(startTimeMs) || !Number.isFinite(endTimeMs) || endTimeMs <= startTimeMs) {
    return res.status(400).json({ ok: false, error: 'invalid_time_range' });
  }

  const db = await getDb();
  await db.reload();
  const baseRules = body.rules && typeof body.rules === 'object'
    ? normalizeTradingRules(body.rules as TradingRulesSettings)
    : normalizeTradingRules(db.data.settings?.tradingRules);

  const run = createQueuedBacktestRun({
    request: {
      symbol,
      biasMode: body.biasMode,
      startTimeMs,
      endTimeMs,
      rules: baseRules,
    },
    rules: baseRules,
    symbol,
    requestedBy: 'owner',
  });

  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  await reconcileBacktestState(db);
  await reconcileOptimizationState(db);
  const activeBacktest = db.data.backtestRuns.find((item) => item.status === 'queued' || item.status === 'running') ?? null;

  if (activeBacktest) {
    return res.status(409).json({ ok: false, error: 'backtest_already_running', activeRunId: activeBacktest.id ?? null });
  }
  if (hasInFlightOptimization(db.data.optimizationResults)) {
    const activeOpt = db.data.optimizationResults.find((item) => item.status === 'queued' || item.status === 'running') ?? null;
    return res.status(409).json({ ok: false, error: 'optimization_running', activeId: activeOpt?.id ?? null });
  }

  db.data.backtestRuns = compactBacktestRuns([run, ...(Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [])]);
  await db.write();

  try {
    spawnComputeJobProcess('backtest', run.id);
  } catch (err) {
    markComputeJobFailed(run, err instanceof Error ? err.message : String(err), { stage: 'failed' });
    await db.write();
    return res.status(500).json({ ok: false, error: 'backtest_spawn_failed' });
  }

  return res.status(201).json({ ok: true, run });
});

// ─── Optimization Endpoints ───────────────────────────────────────────

const OPTIMIZATION_HISTORY_LIMIT = 50;

function hasInFlightOptimization(optimizations: Array<{ status?: string }>): boolean {
  return optimizations.some((item) => item.status === 'queued' || item.status === 'running');
}

function isPidAlive(pid?: number | null): boolean {
  if (!pid || !Number.isFinite(pid)) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function reconcileOptimizationState(db: Awaited<ReturnType<typeof getDb>>): Promise<void> {
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  const activeOpt = db.data.optimizationResults.find((item) => item.status === 'queued' || item.status === 'running');
  if (!activeOpt) return;

  const failureReason = reconcileComputeJob({
    job: activeOpt,
    isWorkerAlive: activeOpt.workerPid ? isPidAlive(activeOpt.workerPid) : undefined,
    queuedFailureReason: 'optimizer worker did not start',
    runningFailureReason: activeOpt.workerHeartbeatAt
      ? 'optimizer heartbeat timed out'
      : 'optimizer worker is not active',
    missingWorkerReason: 'optimizer worker exited unexpectedly',
  });

  if (failureReason) {
    markComputeJobFailed(activeOpt, failureReason, { stage: 'failed' });
    await db.write();
  }
}

async function reconcileBacktestState(db: Awaited<ReturnType<typeof getDb>>): Promise<void> {
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const activeRun = db.data.backtestRuns.find((item) => item.status === 'queued' || item.status === 'running');
  if (!activeRun) return;

  const failureReason = reconcileComputeJob({
    job: activeRun,
    isWorkerAlive: activeRun.workerPid ? isPidAlive(activeRun.workerPid) : undefined,
    queuedFailureReason: 'backtest worker did not start',
    runningFailureReason: activeRun.workerHeartbeatAt
      ? 'backtest heartbeat timed out'
      : 'backtest worker is not active',
    missingWorkerReason: 'backtest worker exited unexpectedly',
  });

  if (failureReason) {
    markComputeJobFailed(activeRun, failureReason, { stage: 'failed' });
    await db.write();
  }
}

function spawnComputeJobProcess(kind: 'backtest' | 'optimization', jobId: string): void {
  const child = spawn(process.execPath, ['--import', 'tsx/esm', 'src/core/computeJobProcess.ts', kind, jobId], {
    cwd: rootDir,
    detached: true,
    stdio: 'ignore',
    env: { ...process.env },
  });
  child.unref();
}

const OPTIMIZABLE_PARAMS = new Set([
  'slPct', 'tpLevels[0]', 'tpLevels[1]', 'tpLevels[2]',
  'tp1Pct', 'tp2Pct', 'tp3Pct',
  'maxLeverage', 'engulfingLookbackCandles', 'fvgRetrace',
  'fvgMinWidthPct', 'exitClosePct', 'dailyDrawdown',
]);

app.get('/api/optimization/results', ownerAuth, async (_req, res) => {
  const db = await getDb();
  await db.reload();
  await reconcileOptimizationState(db);
  await reconcileBacktestState(db);
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  return res.json({ ok: true, optimizations: db.data.optimizationResults });
});

app.get('/api/optimization/results/:id', ownerAuth, async (req, res) => {
  const db = await getDb();
  await db.reload();
  await reconcileOptimizationState(db);
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  const opt = db.data.optimizationResults.find((o) => o.id === req.params.id);
  if (!opt) {
    return res.status(404).json({ ok: false, error: 'optimization_not_found' });
  }
  return res.json({ ok: true, optimization: opt });
});

app.get('/api/optimization/status', ownerAuth, async (_req, res) => {
  const db = await getDb();
  await db.reload();
  await reconcileOptimizationState(db);
  await reconcileBacktestState(db);
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  const activeOpt = db.data.optimizationResults.find((o) => o.status === 'queued' || o.status === 'running') ?? null;
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const runningBacktest = db.data.backtestRuns.find((run) => run.status === 'queued' || run.status === 'running') ?? null;
  return res.json({
    ok: true,
    running: Boolean(activeOpt),
    activeId: activeOpt?.id ?? null,
    activeOptimization: activeOpt,
    blockedByBacktestId: runningBacktest?.id ?? null,
    blockedByBacktestSymbol: runningBacktest?.symbol ?? null,
    blockedByBacktestStatus: runningBacktest?.status ?? null,
  });
});

app.post('/api/optimization/start', ownerAuth, async (req, res) => {
  const body = (req.body ?? {}) as Partial<OptimizationCreateRequest>;

  if (!body.sourceRunId || typeof body.sourceRunId !== 'string') {
    return res.status(400).json({ ok: false, error: 'source_run_id_required' });
  }

  if (!Array.isArray(body.paramRanges) || body.paramRanges.length === 0) {
    return res.status(400).json({ ok: false, error: 'param_ranges_required' });
  }

  const db = await getDb();
  await db.reload();
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  await reconcileBacktestState(db);
  await reconcileOptimizationState(db);
  const activeBacktest = db.data.backtestRuns.find((item) => item.status === 'queued' || item.status === 'running') ?? null;

  if (hasInFlightOptimization(db.data.optimizationResults)) {
    const activeOpt = db.data.optimizationResults.find((item) => item.status === 'queued' || item.status === 'running') ?? null;
    return res.status(409).json({ ok: false, error: 'optimization_already_running', activeId: activeOpt?.id ?? null });
  }

  // Validate param ranges
  for (const pr of body.paramRanges) {
    if (!OPTIMIZABLE_PARAMS.has(pr.param)) {
      return res.status(400).json({ ok: false, error: `invalid_param:${pr.param}` });
    }
    if (!Number.isFinite(pr.min) || !Number.isFinite(pr.max) || !Number.isFinite(pr.step)) {
      return res.status(400).json({ ok: false, error: `invalid_range:${pr.param}` });
    }
    if (pr.min > pr.max || pr.step <= 0) {
      return res.status(400).json({ ok: false, error: `invalid_range_values:${pr.param}` });
    }
  }

  if (activeBacktest) {
    return res.status(409).json({ ok: false, error: 'backtest_already_running', activeRunId: activeBacktest.id ?? null });
  }
  const sourceRun = db.data.backtestRuns.find((r) => r.id === body.sourceRunId);
  if (!sourceRun) {
    return res.status(404).json({ ok: false, error: 'source_run_not_found' });
  }
  if (sourceRun.status !== 'completed') {
    return res.status(409).json({ ok: false, error: 'source_run_not_completed' });
  }

  const optimization = createQueuedOptimization({
    sourceRun,
    paramRanges: body.paramRanges as OptimizationParamRange[],
  });
  const experiments = ensureExperimentsState(db);
  if (optimization.experimentId && !experiments.some((item) => item.id === optimization.experimentId)) {
    const experiment = createExperimentFromRun({
      sourceRun,
      optimizationResultId: optimization.id,
      requestedBy: 'owner',
    });
    experiment.id = optimization.experimentId;
    experiment.schedule = optimization.rollingWindowSchedule ?? experiment.schedule;
    experiment.coverage = experiment.schedule.coverage;
    experiment.replayAssumptions = optimization.replayAssumptions ?? experiment.replayAssumptions;
    experiment.acceptanceCriteria = optimization.acceptanceCriteria ?? experiment.acceptanceCriteria;
    experiment.objectiveName = optimization.objectiveName ?? experiment.objectiveName;
    experiments.unshift(experiment);
  }

  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  db.data.optimizationResults = [optimization, ...db.data.optimizationResults].slice(0, OPTIMIZATION_HISTORY_LIMIT);
  await db.write();

  try {
    spawnComputeJobProcess('optimization', optimization.id);
  } catch (err) {
    markComputeJobFailed(optimization, err instanceof Error ? err.message : String(err), { stage: 'failed' });
    await db.write();
    return res.status(500).json({ ok: false, error: 'optimization_spawn_failed' });
  }

  return res.status(201).json({ ok: true, optimization });
});

app.get('/api/experiments', ownerAuth, async (_req, res) => {
  const db = await getDb();
  await db.reload();
  return res.json({
    ok: true,
    experiments: ensureExperimentsState(db),
    trials: ensureExperimentTrialsState(db),
  });
});

app.get('/api/champions', ownerAuth, async (_req, res) => {
  const db = await getDb();
  await db.reload();
  return res.json({
    ok: true,
    champions: ensureChampionConfigsState(db),
  });
});

app.post('/api/champions/promote', ownerAuth, async (req, res) => {
  const body = (req.body ?? {}) as { experimentId?: string; trialId?: string };
  if (!body.experimentId || typeof body.experimentId !== 'string') {
    return res.status(400).json({ ok: false, error: 'experiment_id_required' });
  }

  const db = await getDb();
  await db.reload();
  const experiment = ensureExperimentsState(db).find((item) => item.id === body.experimentId);
  if (!experiment) {
    return res.status(404).json({ ok: false, error: 'experiment_not_found' });
  }

  const trialId = typeof body.trialId === 'string' && body.trialId.trim()
    ? body.trialId
    : experiment.candidateTrialId;
  if (!trialId) {
    return res.status(409).json({ ok: false, error: 'candidate_trial_not_selected' });
  }

  const trial = ensureExperimentTrialsState(db).find((item) => item.id === trialId && item.experimentId === experiment.id);
  if (!trial) {
    return res.status(404).json({ ok: false, error: 'experiment_trial_not_found' });
  }
  if (trial.status !== 'completed') {
    return res.status(409).json({ ok: false, error: 'experiment_trial_not_completed' });
  }

  const acceptance = evaluateChampionAcceptance({ trial, experiment });
  if (!acceptance.passed) {
    return res.status(409).json({ ok: false, error: 'acceptance_criteria_failed', notes: acceptance.notes });
  }

  const champion = promoteChampionTrial({
    db: db.data,
    experiment,
    trial,
    promotedBy: 'owner',
  });
  await db.write();
  return res.status(201).json({ ok: true, champion });
});

// ─── Risk Check Endpoint ──────────────────────────────────────────────
app.get('/api/live/risk-check', ownerAuth, async (_req, res) => {
  try {
    const risk = await evaluateRiskGates();
    return res.json({
      ...risk,
      ddLock: getDdLockState(),
    });
  } catch (error) {
    return res.status(500).json({
      canTrade: false,
      dailyDDPct: 0,
      dailyDDLimitPct: rulesCache.getEffectiveRules().dailyDDLimitPct,
      portfolioLeverage: 0,
      blocks: ['risk_check_failed'],
      ddLock: getDdLockState(),
      error: error instanceof Error ? error.message : 'risk_check_failed'
    });
  }
});

app.post('/api/live/dd-lock/reset', ownerAuth, async (_req, res) => {
  let openPositions: PositionSnapshot[] = [];
  try {
    openPositions = await exchange.getOpenPositions();
  } catch (error) {
    logger.warn({ component: 'risk-gate', err: error }, 'DD lock reset rejected because open-position check failed');
    return res.status(503).json({ ok: false, error: 'positions_check_failed' });
  }

  if (openPositions.length > 0) {
    return res.status(409).json({
      ok: false,
      error: 'positions_not_flat',
      openPositions: openPositions.length,
    });
  }

  ddLock.active = false;
  ddLock.activatedAt = '';
  ddLock.triggeredDailyDDPct = undefined;
  ddLock.dailyDDLimitPct = undefined;
  ddLock.triggeredEquityUsd = undefined;
  ddLock.baselineEquityUsd = undefined;
  ddLock.emergencyCloseNotificationSent = false;
  ddLock.emergencyCloseSettledAt = undefined;
  await clearEmergencyCloseNotificationKey();
  await persistDdLockState();
  logger.info({ component: 'risk-gate' }, 'DD lock manually reset by owner');
  return res.json({ ok: true, ddLockActive: false, ddLock: getDdLockState() });
});

app.get('/api/live/status', ownerAuth, async (_req, res) => {
  const pendingRows = await loadPendingConfirmationRows();
  const liveBase = await getCachedExchangeLiveState(LIVE_SYMBOL, getLiveMode());
  const live = { ...liveBase, pendingConfirmations: pendingRows };
  return res.json({
    ok: live.connected,
    ...live,
    ddLock: getDdLockState(),
  });
});

app.get('/api/live/orders/diagnostics', ownerAuth, async (_req, res) => {
  try {
    const openOrders = await exchange.getOpenOrders();
    const rows = openOrders.map((order) => {
      const meta = getSystemManagedProtectiveOrderMeta(order);
      const raw = order.raw as Record<string, unknown> | undefined;
      const reduceOnly = raw?.reduceOnly;
      const orderType = String(
        (raw as { orderType?: unknown } | undefined)?.orderType
        ?? (raw as { trigger?: { tpsl?: unknown } } | undefined)?.trigger?.tpsl
        ?? (raw as { tpsl?: unknown } | undefined)?.tpsl
        ?? ''
      ).trim();

      return {
        id: order.id,
        symbol: order.symbol,
        side: order.side,
        price: order.price,
        size: order.size,
        clientOrderId: getOrderClientOrderId(order) || undefined,
        reduceOnly: reduceOnly === undefined ? undefined : Boolean(reduceOnly === true || reduceOnly === 'true' || reduceOnly === 1 || reduceOnly === '1'),
        orderType: orderType || undefined,
        classification: meta?.kind === 'tp'
          ? 'system_take_profit'
          : meta?.kind === 'sl'
            ? 'system_stop_loss'
            : 'other_manual_or_external',
      };
    });

    return res.json({
      ok: true,
      summary: {
        total: rows.length,
        systemTakeProfit: rows.filter((row) => row.classification === 'system_take_profit').length,
        systemStopLoss: rows.filter((row) => row.classification === 'system_stop_loss').length,
        otherManualOrExternal: rows.filter((row) => row.classification === 'other_manual_or_external').length,
      },
      orders: rows,
    });
  } catch (error) {
    return res.status(500).json({
      ok: false,
      error: error instanceof Error ? error.message : 'live_order_diagnostics_failed',
      orders: [],
    });
  }
});

/**
 * Ingest a Radar signal from upstream source (external API, webhook, etc).
 *
 * Architecture:
 *   1. Validate + normalize payload → create RadarSignalRecord
 *   2. Deduplicate (ignore if same signal seen recently)
 *   3. Handoff to unified entry flow via handoffStrategyEntrySignal
 *      - This respects Trading Rules: only enabled symbols can proceed
 *      - Asset class is used ONLY for verdict thresholds/diagnostics, NOT for gating which symbols are monitored
 *   4. Update RadarSignalRecord with handoff outcome (pending/order_placed/rejected)
 *
 * The concrete list of monitored symbols is controlled by Trading Rules enabled coins list (see getMonitoredSymbols).
 * Radar does NOT use asset classes to determine which symbols to monitor.
 */
async function ingestRadarSignal(payload: Partial<RadarSignalIngestPayload>, ingestSource: string): Promise<{
  ok: boolean;
  status: number;
  signal?: RadarSignalRecord;
  error?: string;
}> {
  const symbol = normalizeSymbol(String(payload.symbol ?? ''));
  const side = payload.side === 'buy' || payload.side === 'sell' ? payload.side : null;
  const timeframe = isTradingRulesTimeframe(payload.timeframe) ? payload.timeframe : '15m';
  const sourceMeta = normalizeRadarSourceMeta(payload.sourceMeta);
  const source = buildRadarSourceLabel(String(payload.source ?? ''), sourceMeta);
  const reason = String(payload.reason ?? '').trim().slice(0, 280);
  const price = Number(payload.price);
  const dedupeKey = side
    ? buildRadarSignalDedupeKey({ symbol, side, timeframe, source, reason, sourceMeta })
    : undefined;

  if (!symbol || !side || !source || !reason || !Number.isFinite(price) || price <= 0) {
    return { ok: false, status: 400, error: 'invalid_radar_signal_payload' };
  }

  const db = await getDb();
  const signals = ensureRadarSignalsState(db);
  const radarRuntime = normalizeRadarRuntimeFromSettings(db.data.settings);
  const nowIso = new Date().toISOString();
  const duplicate = signals.find((item) =>
    (dedupeKey && item.dedupeKey ? item.dedupeKey === dedupeKey : (
      item.symbol === symbol
      && item.side === side
      && item.timeframe === timeframe
      && item.source === source
      && item.reason === reason
    ))
    && Number.isFinite(Date.parse(item.createdAt))
    && (Date.now() - Date.parse(item.createdAt)) <= RADAR_SIGNAL_DEDUP_MS
  );

  const record: RadarSignalRecord = {
    id: `radar-${nanoid(10)}`,
    symbol,
    side,
    timeframe,
    source,
    sourceMeta,
    reason,
    price,
    status: 'ignored',
    createdAt: nowIso,
    updatedAt: nowIso,
    dedupeKey,
    duplicateOf: duplicate?.id,
    error: duplicate ? 'duplicate_signal' : undefined,
  };

  signals.unshift(record);
  db.data.radarSignals = compactRadarSignals(signals);
  await db.write();

  if (duplicate) {
    return { ok: true, status: 200, signal: record };
  }

  if (!radarRuntime.enabled) {
    record.status = 'ignored';
    record.error = 'radar_disabled';
    record.updatedAt = new Date().toISOString();
    db.data.radarSignals = compactRadarSignals(db.data.radarSignals.map((item) => item.id === record.id ? record : item));
    await db.write();
    logger.info({ component: 'radar-ingest', symbol, source, reason: 'radar_disabled' }, 'Radar signal ignored: runtime disabled');
    return { ok: false, status: 409, signal: record, error: 'radar_disabled' };
  }

  // Explicit monitored-symbol scope check: reject signals for symbols not in Trading Rules enabled set.
  const effectiveRules = rulesCache.getEffectiveRules();
  if (!effectiveRules.raw || !isSymbolMonitored(effectiveRules.raw, symbol)) {
    record.status = 'rejected';
    record.error = 'symbol_not_monitored';
    record.updatedAt = new Date().toISOString();
    db.data.radarSignals = compactRadarSignals(db.data.radarSignals.map((item) => item.id === record.id ? record : item));
    await db.write();
    logger.info({ component: 'radar-ingest', symbol, source, reason: 'symbol_not_monitored' }, 'Radar signal rejected: symbol not in Trading Rules enabled set');
    return { ok: false, status: 400, signal: record, error: 'symbol_not_monitored' };
  }

  const handoff = await handoffStrategyEntrySignal({
    component: 'radar-ingest',
    strategy: 'radar',
    symbol,
    timeframe,
    side,
    price,
    reason,
    effectiveRules,
    autoConfirm: radarRuntime.autoConfirm,
    sourceLabel: source,
    auditDetails: { radarSource: source, ingest: ingestSource },
    radarSignalId: record.id,
  });

  record.status = handoff.status;
  record.updatedAt = new Date().toISOString();
  record.pendingId = handoff.pendingId;
  record.orderId = handoff.orderId;
  record.executionIntentId = handoff.executionIntentId;
  record.error = handoff.error;
  db.data.radarSignals = compactRadarSignals(db.data.radarSignals.map((item) => item.id === record.id ? record : item));
  await db.write();

  return { ok: record.status !== 'rejected', status: record.status === 'rejected' ? 400 : 200, signal: record };
}

app.get('/api/radar/signals', ownerAuth, async (req, res) => {
  const limitRaw = Number(req.query.limit ?? 50);
  const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(200, Math.trunc(limitRaw))) : 50;
  const filters = parseRadarSignalFilters(req.query);

  const db = await getDb();
  const allSignals = ensureRadarSignalsState(db);
  const filteredSignals = allSignals.filter((item) => matchesRadarSignalFilters(item, filters));
  const enrichedSignals = filteredSignals.map(enrichRadarSignal);
  const signals = enrichedSignals.slice(0, limit);

  return res.json({
    ok: true,
    signals,
    summary: buildRadarSignalsSummary(enrichedSignals),
  });
});

app.post('/api/radar/signals', ownerAuth, async (req, res) => {
  const result = await ingestRadarSignal((req.body ?? {}) as Partial<RadarSignalIngestPayload>, 'owner_api');
  if (!result.signal) return res.status(result.status).json({ ok: false, error: result.error ?? 'radar_signal_ingest_failed' });
  return res.status(result.status).json({ ok: result.ok, signal: result.signal });
});

app.post('/api/radar/signals/batch', ownerAuth, async (req, res) => {
  const items = Array.isArray((req.body as { signals?: unknown } | undefined)?.signals)
    ? ((req.body as { signals: unknown[] }).signals)
    : [];

  if (items.length === 0 || items.length > 50) {
    return res.status(400).json({ ok: false, error: 'invalid_radar_signal_batch' });
  }

  const results: Array<{ ok: boolean; signal?: RadarSignalRecord; error?: string }> = [];
  let rejected = 0;
  for (const item of items) {
    const result = await ingestRadarSignal((item ?? {}) as Partial<RadarSignalIngestPayload>, 'owner_batch_api');
    if (!result.ok) rejected += 1;
    results.push({ ok: result.ok, signal: result.signal, error: result.error });
  }

  return res.status(rejected > 0 ? 207 : 200).json({
    ok: rejected === 0,
    accepted: results.length - rejected,
    rejected,
    results,
  });
});

app.get('/api/settings/alpha-radar', ownerAuth, async (_req, res) => {
  const settings = await getAlphaRadarSettingsState();
  return res.json({ ok: true, settings });
});

app.put('/api/settings/alpha-radar', ownerAuth, async (req, res) => {
  const db = await getDb();
  const current = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
  const settings = normalizeAlphaRadarSettings({ ...current, ...(req.body as Record<string, unknown> | undefined) });
  db.data.settings.alphaRadar = settings;
  await db.write();
  return res.json({ ok: true, settings });
});

app.get('/api/alpha-radar/observations', ownerAuth, async (req, res) => {
  const db = await getDb();
  const settings = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
  const nowIso = new Date().toISOString();
  const sort = req.query.sort === 'recent' ? 'recent' : 'rank';
  const limitRaw = Number(req.query.limit ?? 25);
  const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(200, Math.trunc(limitRaw))) : 25;
  const observations = currentAlphaRadarObservations(settings, ensureAlphaRadarObservationsState(db), nowIso)
    .slice()
    .sort(alphaRadarObservationComparator(sort))
    .slice(0, limit);
  const connectorRuntimes = summarizeAlphaRadarConnectorRuntimes(getAlphaRadarConnectors(settings));
  const payload: AlphaRadarSnapshotResponse = {
    ok: true,
    observations,
    settings,
    connectorRuntimes,
    summary: buildAlphaRadarObservationSummary(currentAlphaRadarObservations(settings, ensureAlphaRadarObservationsState(db), nowIso), settings),
  };
  return res.json(payload);
});

app.get('/api/alpha-radar/live', ownerAuth, async (_req, res) => {
  return res.json(await buildAlphaRadarLiveState());
});

app.get('/api/alpha-radar/ideas', ownerAuth, async (_req, res) => {
  const db = await getDb();
  const settings = ensureAlphaRadarSettings(db.data.settings.alphaRadar);
  const nowIso = new Date().toISOString();
  const evidenceBundles = pruneEvidenceBundles(ensureEvidenceBundlesState(db), nowIso);
  const signalCandidates = syncSignalCandidatesFromEvidence({
    bundles: evidenceBundles,
    candidates: ensureSignalCandidatesState(db),
    monitoredCoins: normalizeTradingRules(db.data.settings.tradingRules).coins,
    nowIso,
  });
  const radarContextPolicies = buildRadarContextPolicyBook({
    bundles: evidenceBundles,
    candidates: signalCandidates,
    monitoredCoins: normalizeTradingRules(db.data.settings.tradingRules).coins,
    nowIso,
    eventLockoutMinutes: normalizeTradingRules(db.data.settings.tradingRules).eventLockoutMinutes,
  });
  const observations = currentAlphaRadarObservations(settings, ensureAlphaRadarObservationsState(db), nowIso)
    .slice()
    .sort(alphaRadarObservationComparator('rank'))
    .slice(0, 250);
  const rules = normalizeTradingRules(db.data.settings.tradingRules);
  const tradableSymbols = getMonitoredSymbols(rules);
  const ideas: AlphaRadarIdea[] = buildIdeaCandidates({
    observations,
    ticks: alphaRadarMarketTickSnapshot(db.data.marketTicks),
    positions: db.data.positions,
    settings,
    tradableSymbols,
    evidenceBundles,
    signalCandidates,
    nowIso,
  });
  const dedupeSuppressed = evidenceBundles.reduce((acc, bundle) => acc + bundle.duplicateSuppressedCount + bundle.exactMatchCount + bundle.canonicalUrlMatchCount + bundle.externalIdMatchCount + bundle.fuzzyMatchCount, 0);
  const policyAcceptedEntries = ensureExecutionIntentsState(db).filter((item) => item.policyDecision === 'accepted' && item.status !== 'created').length;
  const policyBlockedEntries = ensureExecutionIntentsState(db).filter((item) => item.policyDecision === 'rejected').length;
  return res.json({
    ok: true,
    settings,
    connectorRuntimes: summarizeAlphaRadarConnectorRuntimes(getAlphaRadarConnectors(settings)),
    ideas,
    marketSummary: {
      trackedAssets: tradableSymbols.length,
      monitoringOnlyAssets: enabledAlphaRadarMonitoringWatchlist(settings).filter((item) => item.monitoringOnly).map((item) => item.symbol),
      openPositions: db.data.positions.filter((item) => item.status === 'open').length,
      strongestObservation: observations[0]?.title,
      evidenceBundles: evidenceBundles.filter((item) => item.status === 'active').length,
      signalCandidates: signalCandidates.length,
      dedupeSuppressed,
      radarContextPolicies: radarContextPolicies.length,
      activeRadarContextPolicies: radarContextPolicies.filter((item) => readActiveRadarContextPolicy({ policies: radarContextPolicies, symbol: item.symbol, nowIso }).policy).length,
      lockedRadarContextPolicies: radarContextPolicies.filter((item) => item.lockNewEntries || item.directionMode === 'blocked').length,
      expiredRadarContextPolicies: radarContextPolicies.filter((item) => readActiveRadarContextPolicy({ policies: radarContextPolicies, symbol: item.symbol, nowIso }).reasonCode === 'ttl_expired').length,
      policyAcceptedEntries,
      policyBlockedEntries,
      sourceHealth: buildAlphaRadarSourceHealth(settings, ensureAlphaRadarObservationsState(db)),
      llmMode: 'on_demand',
    },
  });
});

app.post('/api/alpha-radar/collect/market-snapshot', ownerAuth, async (_req, res) => {
  const result = await collectAlphaRadarMarketSnapshotRun('manual');
  return res.json({ ok: true, createdCount: result.createdCount });
});

app.post('/api/alpha-radar/collect/external-feeds', ownerAuth, async (_req, res) => {
  const result = await collectAlphaRadarExternalFeedsRun('manual');
  return res.json({ ok: true, createdCount: result.createdCount });
});

app.get('/api/live/pending-confirmations', ownerAuth, async (_req, res) => {
  const pending = await loadPendingConfirmations();
  return res.json({ ok: true, pending });
});

app.post('/api/live/pending-confirmations/:id/confirm', ownerAuth, async (req, res) => {
  const result = await executePendingConfirmation(req.params.id, 'dashboard');
  return res.status(result.ok ? 200 : 400).json(result);
});

app.post('/api/live/pending-confirmations/:id/reject', ownerAuth, async (req, res) => {
  const result = await rejectPendingConfirmation(req.params.id, 'dashboard');
  return res.status(result.ok ? 200 : 400).json(result);
});

app.post('/api/live/leverage', ownerAuth, async (req, res) => {
  const { symbol = LIVE_SYMBOL, leverage, confirm } = req.body as {
    symbol?: string;
    leverage?: number;
    confirm?: boolean;
  };

  const lev = Number(leverage);
  if (!Number.isFinite(lev) || lev <= 0 || lev > rulesCache.getEffectiveRules().maxLeverage) {
    return res.status(400).json({ error: 'invalid_leverage' });
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const result = await exchange.setLeverage(normalizeSymbol(symbol), lev);
  return res.status(result.ok ? 200 : 400).json({ ok: result.ok, result });
});

app.post('/api/live/position/levels', ownerAuth, riskGateMiddleware, symbolAllocationGate, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    size,
    stopLoss,
    takeProfit,
    takeProfits,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'long' | 'short';
    size?: number;
    stopLoss?: number;
    takeProfit?: number;
    takeProfits?: number[];
    confirm?: boolean;
  };

  if (side !== 'long' && side !== 'short') {
    return res.status(400).json({ ok: false, error: 'invalid_side' });
  }

  const normalizedSymbol = normalizeSymbol(symbol);
  const qtyRaw = Number(size);
  const slRaw = Number(stopLoss);

  const meta = await exchange.getInstrumentMeta(normalizedSymbol).catch(() => null);
  const sizeDecimals = Math.max(0, Math.min(8, Number(meta?.sizeDecimals ?? 5)));
  const qty = Number.isFinite(qtyRaw) ? Number(qtyRaw.toFixed(sizeDecimals)) : qtyRaw;

  // Hyperliquid price normalization:
  // - max 5 significant digits
  // - max (6 - szDecimals) decimal places
  const maxPriceDecimals = Math.max(0, 6 - sizeDecimals);
  const normalizeHlPrice = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) return value;
    const abs = Math.abs(value);
    const digitsBefore = abs >= 1 ? Math.floor(Math.log10(abs)) + 1 : 0;
    const decimalsBySig = Math.max(0, 5 - digitsBefore);
    const decimals = Math.max(0, Math.min(maxPriceDecimals, decimalsBySig));
    return Number(value.toFixed(decimals));
  };

  const sl = normalizeHlPrice(slRaw);

  const rawTps = Array.isArray(takeProfits) && takeProfits.length > 0
    ? takeProfits
    : (takeProfit !== undefined ? [takeProfit] : []);

  const normalizedTps = rawTps
    .map((x) => Number(x))
    .filter((x) => Number.isFinite(x) && x > 0)
    .slice(0, 3)
    .map((x) => normalizeHlPrice(x));

  if (!Number.isFinite(qty) || qty <= 0 || !Number.isFinite(sl) || sl <= 0 || normalizedTps.length === 0) {
    return res.status(400).json({ ok: false, error: 'invalid_size_or_levels' });
  }

  const sortedTps = side === 'long'
    ? [...normalizedTps].sort((a, b) => a - b)
    : [...normalizedTps].sort((a, b) => b - a);

  const levelOrderValid = side === 'long'
    ? sortedTps.every((tp) => tp > sl)
    : sortedTps.every((tp) => tp < sl);

  if (!levelOrderValid) {
    return res.status(400).json({ ok: false, error: 'invalid_level_order' });
  }

  // Validate levels against actual entry price to prevent dangerous SL/TP placement.
  let entryPrice: number | undefined;
  try {
    const expectedSide = side === 'long' ? 'long' : 'short';
    const openPositions = await exchange.getOpenPositions(normalizedSymbol);
    const pos = openPositions.find((p) => p.symbol === normalizedSymbol && p.side === expectedSide);
    if (pos?.entryPrice && Number.isFinite(pos.entryPrice) && pos.entryPrice > 0) {
      entryPrice = pos.entryPrice;
    }
  } catch {
    // best-effort validation
  }

  if (entryPrice) {
    const tpsValidVsEntry = side === 'long'
      ? sortedTps.every((tp) => tp > entryPrice)
      : sortedTps.every((tp) => tp < entryPrice);

    if (!tpsValidVsEntry) {
      return res.status(400).json({
        ok: false,
        error: 'invalid_take_profits_vs_entry',
        entryPrice,
        hint: side === 'long'
          ? 'LONG requires all TP levels above entry price'
          : 'SHORT requires all TP levels below entry price',
      });
    }
  }

  // Validate SL vs current market to prevent instant/invalid trigger side.
  const liveMid = await fetchLiveMid(normalizedSymbol);
  if (liveMid && Number.isFinite(liveMid) && liveMid > 0) {
    const validVsMarket = side === 'long' ? sl < liveMid : sl > liveMid;
    if (!validVsMarket) {
      return res.status(400).json({
        ok: false,
        error: 'invalid_stop_loss_vs_market',
        marketPrice: liveMid,
        hint: side === 'long'
          ? 'LONG requires SL below current market price'
          : 'SHORT requires SL above current market price',
      });
    }
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  // No-op guard: if requested levels are already active on exchange, exit early without touching orders.
  try {
    const live = await buildLiveDashboardState(exchange, normalizedSymbol, getLiveMode(), []);
    const current = live.openPositions.find((p) => p.symbol === normalizedSymbol && p.side === side);
    if (current) {
      const currentSl = Number(current.stopLoss ?? NaN);
      const currentTps = (Array.isArray(current.takeProfits) && current.takeProfits.length > 0
        ? current.takeProfits
        : (current.takeProfit !== undefined ? [current.takeProfit] : [])
      ).map((x) => Number(x)).filter((x) => Number.isFinite(x));

      const requestedTps = [...sortedTps];
      const sortedCurrent = side === 'long'
        ? [...currentTps].sort((a, b) => a - b)
        : [...currentTps].sort((a, b) => b - a);
      const sortedRequested = side === 'long'
        ? [...requestedTps].sort((a, b) => a - b)
        : [...requestedTps].sort((a, b) => b - a);

      const closeEnough = (a: number, b: number) => Math.abs(a - b) <= 1e-6;
      const sameSl = Number.isFinite(currentSl) && closeEnough(currentSl, sl);
      const sameTp = sortedCurrent.length === sortedRequested.length
        && sortedCurrent.every((v, i) => closeEnough(v, sortedRequested[i]));

      if (sameSl && sameTp) {
        return res.status(200).json({
          ok: true,
          noop: true,
          symbol: normalizedSymbol,
          side,
          size: qty,
          stopLoss: sl,
          takeProfit: sortedTps[0],
          takeProfits: sortedTps,
          existingOrdersPreserved: true,
          message: 'levels_already_set_on_exchange',
        });
      }
    }
  } catch {
    // best-effort no-op detection
  }

  const haltState = getSymbolHaltState(normalizedSymbol);
  if (haltState) {
    const retryAfterMs = Math.max(0, haltState.untilMs - Date.now());
    return res.status(409).json({
      ok: false,
      symbol: normalizedSymbol,
      side,
      size: qty,
      stopLoss: sl,
      takeProfit: sortedTps[0],
      takeProfits: sortedTps,
      existingOrdersPreserved: true,
      error: 'exchange_trading_halted_cached',
      hint: 'Exchange is currently halted for this symbol. Existing TP/SL are preserved; retry after backoff.',
      retryAfterMs,
      retryAfterSec: Math.ceil(retryAfterMs / 1000),
      lastHaltAt: haltState.updatedAt,
      reason: haltState.reason,
    });
  }

  const closingSide: 'buy' | 'sell' = side === 'long' ? 'sell' : 'buy';

  const isReduceOnlyOrder = (order: { raw?: unknown }) => {
    const raw = (order.raw ?? {}) as Record<string, unknown>;
    const reduceOnly = raw.reduceOnly;
    if (reduceOnly === true || reduceOnly === 'true' || reduceOnly === 1 || reduceOnly === '1') return true;
    if (reduceOnly === false || reduceOnly === 'false' || reduceOnly === 0 || reduceOnly === '0') return false;
    return true;
  };

  const isTriggerOrder = (order: { raw?: unknown }) => {
    const raw = (order.raw ?? {}) as Record<string, unknown>;
    if (raw.isTrigger === true) return true;
    if (raw.triggerPx !== undefined || raw.triggerPrice !== undefined) return true;
    const orderTypeText = String(raw.orderType ?? '').toLowerCase();
    if (orderTypeText.includes('stop') || orderTypeText.includes('take profit')) return true;
    const tpsl = String(
      (raw as { tpsl?: unknown } | undefined)?.tpsl
      ?? (raw as { trigger?: { tpsl?: unknown } } | undefined)?.trigger?.tpsl
      ?? (raw as { orderType?: { trigger?: { tpsl?: unknown } } } | undefined)?.orderType?.trigger?.tpsl
      ?? ''
    ).toLowerCase();
    return tpsl === 'tp' || tpsl === 'sl';
  };

  const isHaltedError = (value: unknown) => String(value ?? '').toLowerCase().includes('trading is halted');

  const existingOrdersBefore = await exchange.getOpenOrders(normalizedSymbol).catch(() => []);
  const isManagedByCoinmaster = (order: { raw?: unknown }) => {
    const raw = (order.raw ?? {}) as Record<string, unknown>;
    const cloid = String(raw.cloid ?? raw.clientOrderId ?? '').trim().toLowerCase();
    if (!cloid) return false;
    return cloid.startsWith('tp') || cloid.startsWith('sl') || cloid.startsWith('be-sl');
  };

  const existingManagedOrderIds = existingOrdersBefore
    .filter((o) => o.side === closingSide)
    .filter((o) => isManagedByCoinmaster(o))
    .map((o) => String(o.id));

  const tpCount = sortedTps.length;
  const tpSizes = splitTakeProfitSizes(qty, tpCount, sizeDecimals);

  const isNonRetriableTriggerError = (errorText: string) => {
    const e = String(errorText ?? '').toLowerCase();
    return e.includes('trading is halted') || e.includes('unknown asset') || e.includes('invalid level') || e.includes('trigger');
  };

  async function placeTriggerWithRetry(args: Parameters<typeof exchange.placeTriggerOrder>[0], retries = 2) {
    let last: Awaited<ReturnType<typeof exchange.placeTriggerOrder>> | null = null;
    let lastErr = '';
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const ack = await exchange.placeTriggerOrder(args);
        last = ack;
        if (ack.ok) return ack;
        lastErr = ack.error || 'trigger_order_failed';
        if (isNonRetriableTriggerError(lastErr)) {
          return ack;
        }
      } catch (error) {
        lastErr = error instanceof Error ? error.message : 'trigger_order_exception';
        if (isNonRetriableTriggerError(lastErr)) {
          return { ok: false, error: lastErr } as Awaited<ReturnType<typeof exchange.placeTriggerOrder>>;
        }
      }
      if (attempt < retries) {
        await sleep(300 * (attempt + 1));
      }
    }
    return { ok: false, error: last?.error || lastErr } as Awaited<ReturnType<typeof exchange.placeTriggerOrder>>;
  }

  async function placeReduceOnlyLimitTpWithRetry(args: {
    symbol: string;
    side: 'buy' | 'sell';
    size: number;
    price: number;
    clientOrderId: string;
  }, retries = 2) {
    let last: Awaited<ReturnType<typeof exchange.placeReduceOnlyExit>> | null = null;
    let lastErr = '';

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const ack = await exchange.placeReduceOnlyExit({
          symbol: args.symbol,
          side: args.side,
          size: args.size,
          price: args.price,
          reduceOnly: true,
          clientOrderId: args.clientOrderId,
        });
        last = ack;
        if (ack.ok) return ack;
        lastErr = ack.error || 'tp_limit_order_failed';
        if (isNonRetriableTriggerError(lastErr)) {
          return ack;
        }
      } catch (error) {
        lastErr = error instanceof Error ? error.message : 'tp_limit_order_exception';
        if (isNonRetriableTriggerError(lastErr)) {
          return { ok: false, error: lastErr } as Awaited<ReturnType<typeof exchange.placeReduceOnlyExit>>;
        }
      }
      if (attempt < retries) {
        await sleep(300 * (attempt + 1));
      }
    }
    return { ok: false, error: last?.error || lastErr } as Awaited<ReturnType<typeof exchange.placeReduceOnlyExit>>;
  }

  // Safe strategy:
  // 1) Place new TP/SL first
  // 2) Verify they are visible
  // 3) Then cleanup old TP/SL orders
  const slOrder = await placeTriggerWithRetry({
    symbol: normalizedSymbol,
    side: closingSide,
    size: qty,
    triggerPrice: sl,
    kind: 'sl',
    reduceOnly: true,
    clientOrderId: `sl-${nanoid()}`
  });

  if (!slOrder.ok && isHaltedError(slOrder.error)) {
    setSymbolHaltState(normalizedSymbol, String(slOrder.error ?? 'Trading is halted.'));
    return res.status(400).json({
      ok: false,
      symbol: normalizedSymbol,
      side,
      size: qty,
      stopLoss: sl,
      takeProfit: sortedTps[0],
      takeProfits: sortedTps,
      existingOrdersPreserved: true,
      stopLossOrder: {
        ok: false,
        orderId: slOrder.orderId,
        error: String(slOrder.error ?? '').trim() || 'Trading is halted.'
      },
      takeProfitOrder: {
        ok: false,
        error: 'skipped_due_to_sl_halt'
      },
      takeProfitOrders: [],
      error: 'exchange_trading_halted',
      hint: 'Exchange reports trading is halted for this symbol. Existing TP/SL orders were kept.',
    });
  }

  let tpOrders: Array<{ ok: boolean; orderId?: string; error?: string }> = [];

  // Systemic approach: TP levels are placed as reduce-only trigger orders for all symbols.
  // This avoids venue-specific reduce-only LIMIT rejections and keeps SL/TP model consistent.
  for (let i = 0; i < sortedTps.length; i++) {
    const levelSize = Number(tpSizes[i] ?? 0);
    if (!Number.isFinite(levelSize) || levelSize <= 0) {
      // For coarse lot-size symbols (e.g. integer contracts), some TP levels can collapse to 0.
      // Skip zero-size level instead of failing whole set-levels operation.
      continue;
    }

    const ack = await placeTriggerWithRetry({
      symbol: normalizedSymbol,
      side: closingSide,
      size: levelSize,
      triggerPrice: sortedTps[i],
      kind: 'tp',
      reduceOnly: true,
      clientOrderId: `tptr${i + 1}-${nanoid(8)}`,
    }, 0);
    tpOrders.push({ ok: ack.ok, orderId: ack.orderId, error: ack.error });
  }

  // Fallback: if split TP sizes fail due to invalid size, place one TP trigger on full size.
  if (tpOrders.length > 1 && tpOrders.every((o) => !o.ok && String(o.error ?? '').toLowerCase().includes('invalid size'))) {
    const singleTp = await placeTriggerWithRetry({
      symbol: normalizedSymbol,
      side: closingSide,
      size: qty,
      triggerPrice: sortedTps[0],
      kind: 'tp',
      reduceOnly: true,
      clientOrderId: `tptr-single-${nanoid(8)}`,
    });
    tpOrders = [{ ok: singleTp.ok, orderId: singleTp.orderId, error: singleTp.error }];
    logger.warn({ component: 'levels', symbol: normalizedSymbol, side, qty, reason: 'tp_split_invalid_size_fallback_single_trigger_tp' }, 'fallback to single TP trigger after split TP invalid-size errors');
  }

  let ok = slOrder.ok && tpOrders.length > 0 && tpOrders.every((o) => o.ok);
  const expectedIds = [slOrder.orderId, ...tpOrders.map((o) => o.orderId)].filter((x): x is string => Boolean(x));

  // Extra confirmation with strict time budget (non-blocking for UX).
  // If the exchange/info API is slow, we do not hold the HTTP response indefinitely.
  let verificationWarning: string | undefined;
  const verifyBudgetMs = 2500;
  const verifyDeadline = Date.now() + verifyBudgetMs;

  const withTimeout = async <T>(promise: Promise<T>, timeoutMs: number, tag: string): Promise<T> => {
    let timer: NodeJS.Timeout | null = null;
    try {
      return await Promise.race([
        promise,
        new Promise<T>((_, reject) => {
          timer = setTimeout(() => reject(new Error(`${tag}_timeout`)), timeoutMs);
        }),
      ]);
    } finally {
      if (timer) clearTimeout(timer);
    }
  };

  if (ok && expectedIds.length > 0) {
    let verifiedById = false;
    for (let attempt = 0; attempt < 2; attempt++) {
      if (Date.now() >= verifyDeadline) break;
      try {
        const remainingMs = Math.max(150, verifyDeadline - Date.now());
        const allOrders = await withTimeout(exchange.getOpenOrders().catch(() => []), Math.min(remainingMs, 1200), 'verify_open_orders');
        const openIds = new Set((allOrders || []).map((o) => String(o?.id ?? '')));
        verifiedById = expectedIds.every((id) => openIds.has(String(id)));
        if (verifiedById) {
          console.log(`[levels] trigger orders verified by id: ${expectedIds.join(',')}`);
          break;
        }
      } catch (e) {
        console.log(`[levels] verification query failed:`, e instanceof Error ? e.message : String(e));
        break;
      }
      await sleep(120);
    }

    if (!verifiedById && Date.now() < verifyDeadline) {
      try {
        const remainingMs = Math.max(150, verifyDeadline - Date.now());
        const live = await withTimeout(buildLiveDashboardState(exchange, normalizedSymbol, getLiveMode(), []), Math.min(remainingMs, 1200), 'verify_live_state');
        const current = live.openPositions.find((p) => p.symbol === normalizedSymbol && p.side === side);

        let quoteDecimals = 0;
        try {
          const getter = (exchange as any).getInstrumentMeta;
          if (typeof getter === 'function') {
            const metaAny = await withTimeout(getter.call(exchange, normalizedSymbol), 500, 'verify_meta') as any;
            if (Number.isFinite(Number(metaAny?.quoteDecimals))) {
              quoteDecimals = Math.max(0, Math.min(8, Number(metaAny.quoteDecimals)));
            }
          }
        } catch {
          quoteDecimals = 0;
        }

        const tickTol = quoteDecimals > 0 ? 10 ** (-quoteDecimals) : 0;
        const priceTol = Math.max(1e-6, tickTol, 0.5);
        const closeEnough = (a: number, b: number) => Math.abs(a - b) <= priceTol;

        const currentSl = Number(current?.stopLoss ?? NaN);
        const currentTps = (Array.isArray(current?.takeProfits) && current?.takeProfits.length > 0
          ? current!.takeProfits
          : (current?.takeProfit !== undefined ? [current.takeProfit] : [])
        ).map((x) => Number(x)).filter((x) => Number.isFinite(x));

        const sortedCurrent = side === 'long'
          ? [...currentTps].sort((a, b) => a - b)
          : [...currentTps].sort((a, b) => b - a);
        const sortedRequested = side === 'long'
          ? [...sortedTps].sort((a, b) => a - b)
          : [...sortedTps].sort((a, b) => b - a);

        const sameSl = Number.isFinite(currentSl) && closeEnough(currentSl, sl);
        const sameTp = sortedCurrent.length >= sortedRequested.length
          && sortedRequested.every((v, i) => closeEnough(sortedCurrent[i], v));

        if (sameSl && sameTp) {
          console.log('[levels] verified by semantic level match (id mismatch tolerated)');
        } else {
          verificationWarning = 'orders_not_visible_after_ack';
        }
      } catch {
        verificationWarning = 'orders_not_visible_after_ack';
      }
    }
  }

  if (!ok) {
    const placementErrors = [slOrder.error, ...tpOrders.map((o) => o.error)].filter(Boolean).map(String);
    const halted = placementErrors.some((e) => isHaltedError(e));
    if (halted) {
      setSymbolHaltState(normalizedSymbol, placementErrors.find((e) => isHaltedError(e)) ?? 'Trading is halted.');
    }

    // Rollback only newly created orders; keep previous protection orders untouched.
    const rollbackIds = expectedIds;
    const rollbackResults: Array<{ id: string; ok: boolean; error?: string }> = [];
    for (const id of rollbackIds) {
      try {
        const result = await exchange.cancelOrder(id);
        rollbackResults.push({ id, ok: result.ok, error: result.error });
      } catch (error) {
        rollbackResults.push({ id, ok: false, error: error instanceof Error ? error.message : 'rollback_cancel_failed' });
      }
    }

    return res.status(400).json({
      ok: false,
      symbol: normalizedSymbol,
      side,
      size: qty,
      stopLoss: sl,
      takeProfit: sortedTps[0],
      takeProfits: sortedTps,
      existingOrdersPreserved: true,
      rollback: {
        attempted: rollbackIds.length,
        failed: rollbackResults.filter((x) => !x.ok).length,
      },
      stopLossOrder: {
        ok: slOrder.ok,
        orderId: slOrder.orderId,
        error: String(slOrder.error ?? '').trim() || undefined
      },
      takeProfitOrder: {
        ok: tpOrders[0]?.ok,
        orderId: tpOrders[0]?.orderId,
        error: String(tpOrders[0]?.error ?? '').trim() || undefined
      },
      takeProfitOrders: tpOrders.map((o) => ({
        ok: o.ok,
        orderId: o.orderId,
        error: String(o.error ?? '').trim() || undefined
      })),
      error: halted ? 'exchange_trading_halted' : 'set_levels_failed',
      hint: halted ? 'Exchange reports trading is halted for this symbol. Existing TP/SL orders were kept.' : undefined
    });
  }

  clearSymbolHaltState(normalizedSymbol);

  // Cleanup old TP/SL orders only after new levels are safely in place.
  const expectedSet = new Set(expectedIds.map(String));
  const oldToCancel = existingManagedOrderIds.filter((id) => !expectedSet.has(String(id)));
  const oldCleanup: Array<{ id: string; ok: boolean; error?: string }> = [];

  for (const id of oldToCancel) {
    try {
      const result = await exchange.cancelOrder(id);
      oldCleanup.push({ id, ok: result.ok, error: result.error });
    } catch (error) {
      oldCleanup.push({ id, ok: false, error: error instanceof Error ? error.message : 'cancel_failed' });
    }
  }

  return res.status(200).json({
    ok: true,
    symbol: normalizedSymbol,
    side,
    size: qty,
    stopLoss: sl,
    takeProfit: sortedTps[0],
    takeProfits: sortedTps,
    existingOrdersPreserved: true,
    cleanup: {
      canceledOld: oldCleanup.filter((x) => x.ok).length,
      failedOld: oldCleanup.filter((x) => !x.ok).length,
    },
    stopLossOrder: {
      ok: slOrder.ok,
      orderId: slOrder.orderId,
      error: String(slOrder.error ?? '').trim() || undefined
    },
    takeProfitOrder: {
      ok: tpOrders[0]?.ok,
      orderId: tpOrders[0]?.orderId,
      error: String(tpOrders[0]?.error ?? '').trim() || undefined
    },
    takeProfitOrders: tpOrders.map((o) => ({
      ok: o.ok,
      orderId: o.orderId,
      error: String(o.error ?? '').trim() || undefined
    })),
    verificationWarning,
  });
});

app.post('/api/live/order/limit', ownerAuth, staleMarketDataGate, riskGateMiddleware, symbolAllocationGate, engulfingGate, radarContextPolicyGate, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    price,
    size,
    reduceOnly = false,
    clientOrderId,
    stopLoss: requestStopLoss,
    takeProfit: requestTakeProfit,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'buy' | 'sell';
    price?: number;
    size?: number;
    reduceOnly?: boolean;
    clientOrderId?: string;
    stopLoss?: number;
    takeProfit?: number;
    confirm?: boolean;
  };
  const executionIntentId = (req as any)._executionIntentId as string | undefined;
  const radarPolicyGate = (req as any)._radarContextPolicyGate as { snapshot?: { policyId?: string }; override?: boolean } | undefined;

  if (side !== 'buy' && side !== 'sell') {
    return res.status(400).json({ error: 'invalid_side' });
  }

  const px = Number(price);
  if (!Number.isFinite(px) || px <= 0) {
    return res.status(400).json({ error: 'invalid_price' });
  }

  // ── Allocation sizing: compute size when not provided ──────────────
  let qty = Number(size);
  let sizingSource: 'explicit' | 'runtime_allocation' = 'explicit';
  let sizingMeta: { marginUsd: number; notionalUsd: number; effectiveLeverage: number } | undefined;

  if (!Number.isFinite(qty) || qty <= 0) {
    const normalizedSym = normalizeSymbol(symbol);
    const effectiveRules = rulesCache.getEffectiveRules();
    const riskCheck: RiskCheckResult | undefined = (req as any)._riskCheck;

    let equityUsd = riskCheck?.equityUsd ?? 0;
    let availableUsd = 0;
    try {
      const account = await exchange.getAccountState();
      if (account) {
        if (!equityUsd && account.equityValidForRisk) equityUsd = account.equityUsd ?? 0;
        availableUsd = account.availableUsd ?? 0;
      }
    } catch {
      // best-effort
    }

    let sizeDecimals = 6;
    try {
      const meta = await exchange.getInstrumentMeta(normalizedSym);
      if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
    } catch {
      // best-effort: use default
    }

    const sizing = computeAllocationSize({
      symbol: normalizedSym,
      price: px,
      equityUsd,
      availableUsd,
      rules: effectiveRules,
      sizeDecimals,
    });

    if (!sizing.ok) {
      const db = await getDb();
      updateExecutionIntent(db, executionIntentId, { status: 'rejected' });
      await db.write();
      logRiskGateAudit({ gate: 'allocation_sizing', passed: false, reason: sizing.reason, details: { symbol: normalizedSym, price: px, equityUsd, availableUsd } });
      return res.status(400).json({
        ok: false,
        errorCode: 'allocation_sizing_failed' as TradingErrorCode,
        error: `Allocation sizing failed: ${sizing.reason}`,
      });
    }

    qty = sizing.size;
    sizingSource = 'runtime_allocation';
    sizingMeta = { marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage };

    logRiskGateAudit({
      gate: 'allocation_sizing',
      passed: true,
      details: { symbol: normalizedSym, size: qty, marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage, allocationPct: sizing.allocationPct },
    });
  }

  const notional = px * qty;
  const normalizedSymbol = normalizeSymbol(symbol);

  if (!reduceOnly && sizingSource === 'runtime_allocation') {
    let gross: Awaited<ReturnType<typeof checkPortfolioGrossCap>>;
    try {
      gross = await checkPortfolioGrossCap({
        symbol: normalizedSymbol,
        price: px,
        size: qty,
        effectiveRules: rulesCache.getEffectiveRules(),
        riskCheck: (req as any)._riskCheck,
      });
    } catch (error) {
      logger.error({ component: 'risk-gate', err: error }, 'portfolio gross cap check failed');
      return res.status(503).json({
        ok: false,
        errorCode: 'allocation_check_unavailable' as TradingErrorCode,
        error: 'Portfolio gross exposure guard unavailable. Trading is temporarily blocked.',
      });
    }
    if (!gross.ok) {
      const db = await getDb();
      updateExecutionIntent(db, executionIntentId, { status: 'rejected' });
      await db.write();
      return res.status(403).json({
        ok: false,
        errorCode: 'portfolio_gross_cap_exceeded' as TradingErrorCode,
        error: `Order would bring portfolio gross exposure to $${gross.totalGross.toFixed(2)}, exceeding cap of $${gross.cap.toFixed(2)}.`,
        currentGross: Number(gross.currentGross.toFixed(2)),
        newNotional: Number(gross.newNotional.toFixed(2)),
        totalGross: Number(gross.totalGross.toFixed(2)),
        cap: Number(gross.cap.toFixed(2)),
      });
    }
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const correlationId = clientOrderId || nanoid();
  const now = new Date().toISOString();

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: now,
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: 'manual_live_order',
    payload: {
      reduceOnly: Boolean(reduceOnly),
      notionalUsdc: Number(notional.toFixed(4)),
      manualConfirmation: rulesCache.getEffectiveRules().manualConfirmation,
      executionIntentId: executionIntentId ?? null,
      radarPolicyId: radarPolicyGate?.snapshot?.policyId ?? null,
      radarContextOverride: radarPolicyGate?.override === true,
    }
  });

  const intent: OrderIntent = {
    symbol: normalizedSymbol,
    side,
    price: px,
    size: qty,
    reduceOnly: Boolean(reduceOnly),
    clientOrderId: correlationId
  };

  const ack = await exchange.placeLimitOrder(intent);

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: ack.ok ? 'manual_live_order_ack' : 'manual_live_order_rejected',
    payload: {
      orderId: ack.orderId ?? null,
      status: ack.status ?? null,
      error: ack.error ?? null,
      executionIntentId: executionIntentId ?? null,
    }
  });

  updateExecutionIntent(db, executionIntentId, ack.ok
    ? { status: 'auto_order_placed', orderId: ack.orderId }
    : { status: 'rejected' });

  if (!ack.ok) {
    await notifyOrderRejectedEvent({
      symbol: normalizedSymbol,
      source: 'api:order_limit',
      error: ack.error ?? 'exchange_rejected',
    }).catch(() => undefined);
  }

  // TP/SL defaults: auto-apply after successful non-reduceOnly order
  let tpSlResult: Awaited<ReturnType<typeof placeTpSlTriggerOrders>> | undefined;
  let tpSlApplied: TpSlDefaults | null = null;

  if (ack.ok && !reduceOnly) {
    await clearPendingConfirmationForSymbol(normalizedSymbol);
    try {
      await notifyTradeOpen({ symbol: normalizedSymbol, side, price: px, size: qty, source: 'api:order_limit' });
    } catch (error) {
      logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
    }
    tpSlApplied = resolveTpSlDefaults(px, side, requestStopLoss, requestTakeProfit);
    if (tpSlApplied) {
      try {
        tpSlResult = await placeTpSlTriggerOrders(normalizedSymbol, side, qty, tpSlApplied, correlationId, px);
      } catch {
        tpSlResult = {
          stopLossOrder: { ok: false, error: 'tp_sl_placement_failed' },
          takeProfitOrder: { ok: false, error: 'tp_sl_placement_failed' }, takeProfitOrders: [{ ok: false, error: 'tp_sl_placement_failed' }]
        };
      }

      logRiskGateAudit({
        gate: 'tp_sl_defaults',
        passed: true,
        reason: tpSlApplied.applied ? 'runtime_defaults_applied' : 'explicit_values_used',
        details: {
          source: tpSlApplied.source,
          stopLoss: tpSlApplied.stopLoss,
          takeProfit: tpSlApplied.takeProfit,
          entryPrice: px,
          side,
          slOrderOk: tpSlResult?.stopLossOrder.ok ?? false,
          tpOrderOk: tpSlResult?.takeProfitOrder.ok ?? false
        }
      });
    }
  }

  await db.write();

  const responseBody: Record<string, unknown> = {
    ok: ack.ok,
    notionalUsdc: Number(notional.toFixed(4)),
    sizingSource,
    ack
  };

  if (sizingMeta) {
    responseBody.marginUsd = sizingMeta.marginUsd;
    responseBody.notionalUsd = sizingMeta.notionalUsd;
    responseBody.effectiveLeverage = sizingMeta.effectiveLeverage;
  }

  if (tpSlApplied && tpSlResult) {
    responseBody.stopLoss = tpSlApplied.stopLoss;
    responseBody.takeProfit = tpSlApplied.takeProfit;
    responseBody.tpSlSource = tpSlApplied.source;
    responseBody.stopLossOrder = tpSlResult.stopLossOrder;
    responseBody.takeProfitOrder = tpSlResult.takeProfitOrder;
  }

  return res.status(ack.ok ? 200 : 400).json(responseBody);
});

app.post('/api/live/order/cancel', ownerAuth, async (req, res) => {
  const { orderId, symbol = LIVE_SYMBOL, confirm } = req.body as {
    orderId?: string;
    symbol?: string;
    confirm?: boolean;
  };

  if (!orderId) {
    return res.status(400).json({ error: 'order_id_required' });
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const result = await exchange.cancelOrder(orderId);

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: normalizeSymbol(symbol),
    source: 'live',
    type: result.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId: nanoid(),
    reason: result.ok ? 'manual_cancel_order' : 'manual_cancel_order_failed',
    payload: {
      orderId,
      error: result.error ?? null
    }
  });
  await db.write();

  return res.status(result.ok ? 200 : 400).json({ ok: result.ok, result });
});

app.post('/api/live/order/cancel-all', ownerAuth, async (req, res) => {
  const { symbol = LIVE_SYMBOL, confirm } = req.body as {
    symbol?: string;
    confirm?: boolean;
  };

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const result = await exchange.cancelAll(normalizeSymbol(symbol));

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: normalizeSymbol(symbol),
    source: 'live',
    type: result.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId: nanoid(),
    reason: result.ok ? 'manual_cancel_all' : 'manual_cancel_all_failed',
    payload: {
      error: result.error ?? null
    }
  });
  await db.write();

  return res.status(result.ok ? 200 : 400).json({ ok: result.ok, result });
});

// ─── TP/SL Defaults Helper ────────────────────────────────────────────

interface TpSlDefaults {
  stopLoss: number;
  /** All computed TP trigger prices (1–3), sorted ascending for longs / descending for shorts */
  takeProfits: number[];
  /** First TP price (back-compat) */
  takeProfit: number;
  applied: boolean;
  source: 'explicit' | 'runtime_defaults';
}

// ─── Active Trade TP Tracking ─────────────────────────────────────────
interface ActiveTradeState {
  symbol: string;
  side: 'buy' | 'sell';
  entryPrice: number;
  slOrderId: string | null;
  tpOrderIds: string[];        // pending TP order IDs (removed as they fill)
  firstTpFired: boolean;
  positionSize: number;
  openedAt?: string;
  entryTimeframe?: TradingRulesTimeframe;
}

function splitTakeProfitSizes(totalSize: number, tpCount: number, sizeDecimals: number): number[] {
  if (!Number.isFinite(totalSize) || totalSize <= 0 || tpCount <= 0) return [];

  // Explicit policy requested by owner:
  // - 2 TP -> 50/50
  // - 3 TP -> 33/33/34
  // - fallback: equal split
  const weights = tpCount === 2
    ? [0.5, 0.5]
    : tpCount === 3
      ? [0.33, 0.33, 0.34]
      : Array.from({ length: tpCount }, () => 1 / tpCount);

  // Convert to instrument lot units first (works for integer-lot symbols too).
  const factor = 10 ** Math.max(0, sizeDecimals);
  const totalUnits = Math.max(0, Math.round(totalSize * factor));
  if (totalUnits <= 0) return [];

  const targetUnits = weights.map((w) => totalUnits * w);
  const units = targetUnits.map((v) => Math.floor(v));

  let remainderUnits = totalUnits - units.reduce((sum, v) => sum + v, 0);
  if (remainderUnits > 0) {
    const ranked = targetUnits
      .map((target, i) => ({ i, frac: target - Math.floor(target), target }))
      .sort((a, b) => (b.frac - a.frac) || (b.target - a.target) || (a.i - b.i));

    for (let r = 0; r < ranked.length && remainderUnits > 0; r++) {
      units[ranked[r].i] += 1;
      remainderUnits -= 1;
      if (r === ranked.length - 1 && remainderUnits > 0) r = -1;
    }
  }

  return units.map((u) => u / factor);
}
/** correlationId → ActiveTradeState */
const activeTrades = new Map<string, ActiveTradeState>();

async function recoverActiveTradesFromExchange(): Promise<void> {
  if (activeTrades.size > 0) return;

  const [positions, openOrders] = await Promise.all([
    exchange.getOpenPositions(),
    exchange.getOpenOrders(),
  ]);

  if (positions.length === 0 || openOrders.length === 0) return;

  const grouped = new Map<string, { symbol: string; slOrderId: string | null; tpOrderIds: string[] }>();

  for (const order of openOrders) {
    const meta = getSystemManagedProtectiveOrderMeta(order);
    if (!meta) continue;

    const current = grouped.get(meta.correlationId) ?? {
      symbol: order.symbol,
      slOrderId: null,
      tpOrderIds: [],
    };

    if (meta.kind === 'tp') current.tpOrderIds.push(order.id);
    if (meta.kind === 'sl') current.slOrderId = order.id;
    grouped.set(meta.correlationId, current);
  }

  let recovered = 0;
  for (const [correlationId, row] of grouped) {
    const position = positions.find((p) => normalizeSymbol(p.symbol) === normalizeSymbol(row.symbol));
    if (!position || row.tpOrderIds.length === 0) continue;

    activeTrades.set(correlationId, {
      symbol: position.symbol,
      side: position.side === 'long' ? 'buy' : 'sell',
      entryPrice: position.entryPrice ?? position.markPrice ?? 0,
      slOrderId: row.slOrderId,
      tpOrderIds: [...new Set(row.tpOrderIds)],
      firstTpFired: false,
      positionSize: position.size,
    });
    recovered += 1;
  }

  if (recovered > 0) {
    logger.info({ component: 'tp-monitor', recovered }, 'recovered system-managed TP tracking state from live exchange orders');
  }
}

const symbolHaltBackoff = new Map<string, { untilMs: number; reason: string; updatedAt: string }>();
const HALT_BACKOFF_MS = 10 * 60_000;

function getSymbolHaltState(symbol: string): { untilMs: number; reason: string; updatedAt: string } | null {
  const key = normalizeSymbol(symbol);
  const row = symbolHaltBackoff.get(key);
  if (!row) return null;
  if (Date.now() > row.untilMs) {
    symbolHaltBackoff.delete(key);
    return null;
  }
  return row;
}

function setSymbolHaltState(symbol: string, reason: string): void {
  const key = normalizeSymbol(symbol);
  symbolHaltBackoff.set(key, {
    untilMs: Date.now() + HALT_BACKOFF_MS,
    reason,
    updatedAt: new Date().toISOString(),
  });
}

function clearSymbolHaltState(symbol: string): void {
  symbolHaltBackoff.delete(normalizeSymbol(symbol));
}

/**
 * Compute TP/SL levels from runtime rules when the client omits them.
 * Priority: explicit request > runtime defaults.
 * Returns up to 3 TP prices and a SL price.
 */
function resolveTpSlDefaults(
  entryPrice: number,
  side: 'buy' | 'sell',
  requestSl: number | undefined,
  requestTp: number | undefined
): TpSlDefaults | null {
  const hasSl = requestSl !== undefined && Number.isFinite(Number(requestSl)) && Number(requestSl) > 0;
  const hasTp = requestTp !== undefined && Number.isFinite(Number(requestTp)) && Number(requestTp) > 0;

  if (hasSl && hasTp) {
    const tp = Number(requestTp);
    return { stopLoss: Number(requestSl), takeProfits: [tp], takeProfit: tp, applied: false, source: 'explicit' };
  }

  const rules = rulesCache.getEffectiveRules();
  if (!rules.raw) return null;

  const tpLevels = rules.raw.tpLevels?.length ? rules.raw.tpLevels : (rules.raw.tpPct ? [rules.raw.tpPct] : null);
  const slPct = rules.raw.slPct;
  if (!tpLevels || !slPct) return null;

  const isLong = side === 'buy';
  const takeProfits = tpLevels.map(pct => {
    const price = isLong ? entryPrice * (1 + pct / 100) : entryPrice * (1 - pct / 100);
    return Number(price.toFixed(8));
  });
  const defaultSl = isLong ? entryPrice * (1 - slPct / 100) : entryPrice * (1 + slPct / 100);

  return {
    stopLoss: hasSl ? Number(requestSl) : Number(defaultSl.toFixed(8)),
    takeProfits,
    takeProfit: takeProfits[0],
    applied: true,
    source: 'runtime_defaults',
  };
}

/**
 * Place SL + up to 3 TP orders after a successful entry.
 * SL = trigger stop, TP = reduce-only limit exits with deterministic split sizing.
 * Registers trade state for the TP fill monitor (SL→entry on first TP hit).
 */
async function placeTpSlTriggerOrders(
  symbol: string,
  side: 'buy' | 'sell',
  size: number,
  tpSl: TpSlDefaults,
  correlationId: string,
  entryPrice?: number,
  entryTimeframe?: TradingRulesTimeframe,
): Promise<{
  stopLossOrder: { ok: boolean; orderId?: string; error?: string };
  takeProfitOrder: { ok: boolean; orderId?: string; error?: string };
  takeProfitOrders: { ok: boolean; orderId?: string; error?: string }[];
}> {
  const closingSide: 'buy' | 'sell' = side === 'buy' ? 'sell' : 'buy';
  const tpCount = tpSl.takeProfits.length;

  let meta: { sizeDecimals?: number } | undefined;
  try {
    const getter = (exchange as any).getInstrumentMeta;
    if (typeof getter === 'function') {
      meta = await getter.call(exchange, symbol);
    }
  } catch {
    meta = undefined;
  }

  const sizeDecimals = Math.max(0, Math.min(8, Number(meta?.sizeDecimals ?? 6)));
  const tpSizes = splitTakeProfitSizes(size, tpCount, sizeDecimals);

  // Place SL (full position)
  const slOrder = await exchange.placeTriggerOrder({
    symbol, side: closingSide, size, triggerPrice: tpSl.stopLoss,
    kind: 'sl', reduceOnly: true, clientOrderId: `sl-auto-${correlationId}`,
  });

  // Place TP orders as reduce-only triggers (systemic, venue-agnostic behavior)
  const tpOrders: { ok: boolean; orderId?: string; error?: string }[] = [];
  for (let i = 0; i < tpSl.takeProfits.length; i++) {
    try {
      const levelSize = Number(tpSizes[i] ?? 0);
      if (!Number.isFinite(levelSize) || levelSize <= 0) {
        // For coarse lot-size symbols (e.g. integer contracts), some TP levels can collapse to 0.
        // Skip zero-size TP leg and continue with valid levels.
        continue;
      }

      const ack = await exchange.placeTriggerOrder({
        symbol,
        side: closingSide,
        size: levelSize,
        triggerPrice: tpSl.takeProfits[i],
        kind: 'tp',
        reduceOnly: true,
        clientOrderId: `tptr${i + 1}-auto-${correlationId}`,
      });
      tpOrders.push({ ok: ack.ok, orderId: ack.orderId, error: ack.error });
    } catch (err) {
      tpOrders.push({ ok: false, error: err instanceof Error ? err.message : 'tp_placement_failed' });
    }
  }

  // Register in active trade tracking (for TP fill monitor)
  const tpOrderIds = tpOrders.map(o => o.orderId).filter((id): id is string => Boolean(id));
  const timeStopBars = Math.max(0, Math.round(Number(rulesCache.getEffectiveRules().raw?.timeStopBars ?? 0)));
  if (tpOrderIds.length > 0 && (tpCount > 1 || (timeStopBars > 0 && entryTimeframe))) {
    activeTrades.set(correlationId, {
      symbol, side, entryPrice: entryPrice ?? tpSl.stopLoss,
      slOrderId: slOrder.orderId ?? null,
      tpOrderIds, firstTpFired: false, positionSize: size,
      openedAt: new Date().toISOString(),
      entryTimeframe,
    });
  }

  return {
    stopLossOrder: { ok: slOrder.ok, orderId: slOrder.orderId, error: slOrder.error },
    takeProfitOrder: tpOrders[0] ?? { ok: false, error: 'no_tp' },
    takeProfitOrders: tpOrders,
  };
}

// ─── TP Fill Monitor (SL → entry price after first TP) ────────────────
let tpFillMonitorTimer: NodeJS.Timeout | null = null;
let tpFillMonitorBusy = false;

async function maybeApplyActiveTradeTimeStop(correlationId: string, trade: ActiveTradeState): Promise<boolean> {
  const timeStopBars = Math.max(0, Math.round(Number(rulesCache.getEffectiveRules().raw?.timeStopBars ?? 0)));
  if (timeStopBars <= 0 || trade.firstTpFired || !trade.openedAt || !trade.entryTimeframe) return false;

  const tfMs = TF_MS[trade.entryTimeframe] ?? 0;
  const openedMs = Date.parse(trade.openedAt);
  if (!tfMs || !Number.isFinite(openedMs)) return false;
  if (Date.now() - openedMs < timeStopBars * tfMs) return false;

  const positions = await exchange.getOpenPositions(trade.symbol).catch(() => []);
  const pos = positions.find((p) => normalizeSymbol(p.symbol) === normalizeSymbol(trade.symbol));
  if (!pos || pos.size <= 0) {
    activeTrades.delete(correlationId);
    return true;
  }

  const closingSide: 'buy' | 'sell' = pos.side === 'long' ? 'sell' : 'buy';
  const topOfBook = typeof exchange.getTopOfBook === 'function'
    ? await exchange.getTopOfBook(trade.symbol).catch(() => null)
    : null;
  const price = emergencyClosePrice(pos, closingSide, topOfBook);

  const ack = await exchange.placeLimitOrder({
    symbol: trade.symbol,
    side: closingSide,
    price,
    size: pos.size,
    reduceOnly: true,
    timeInForce: 'Ioc',
    clientOrderId: `time-stop-${correlationId}-${nanoid(6)}`,
  }).catch((error) => ({ ok: false, error: error instanceof Error ? error.message : 'time_stop_close_failed' }));

  logRiskGateAudit({
    gate: 'tp_fill_monitor',
    passed: ack.ok,
    reason: ack.ok ? 'time_stop_close_submitted' : 'time_stop_close_failed',
    details: { symbol: trade.symbol, correlationId, timeStopBars, entryTimeframe: trade.entryTimeframe, size: pos.size, price, error: ack.error ?? null },
  });

  if (!ack.ok) return false;

  for (const orderId of [trade.slOrderId, ...trade.tpOrderIds].filter((id): id is string => Boolean(id))) {
    await exchange.cancelOrder(orderId).catch(() => undefined);
  }

  await notifyPositionClosedEvent({
    symbol: trade.symbol,
    correlationId,
    tpsFilled: 0,
    reason: 'time_stop',
  }).catch(() => undefined);
  activeTrades.delete(correlationId);
  return true;
}

async function runTpFillMonitorTick(): Promise<void> {
  if (tpFillMonitorBusy) return;

  if (activeTrades.size === 0) {
    try {
      await recoverActiveTradesFromExchange();
    } catch (err) {
      logger.warn({ component: 'tp-monitor', err }, 'failed to recover TP tracking state from live exchange orders');
    }
  }

  if (activeTrades.size === 0) return;
  tpFillMonitorBusy = true;
  try {
    const openOrders = await exchange.getOpenOrders();
    const openOrderIds = new Set(openOrders.map(o => o.id));

    for (const [correlationId, trade] of activeTrades) {
      const stillPending = trade.tpOrderIds.filter(id => openOrderIds.has(id));
      const justFilled = trade.tpOrderIds.filter(id => !openOrderIds.has(id));

      if (await maybeApplyActiveTradeTimeStop(correlationId, trade)) continue;

      // If SL order disappeared before any TP fill, DO NOT assume immediate SL fill.
      // Confirm with live position state first to avoid false alerts from order id churn.
      if (!trade.firstTpFired && trade.slOrderId && !openOrderIds.has(trade.slOrderId)) {
        let remainingSize = 0;
        try {
          const positions = await exchange.getOpenPositions(trade.symbol);
          const pos = positions.find((p) => p.symbol.toUpperCase() === trade.symbol.toUpperCase());
          remainingSize = pos?.size ?? 0;
        } catch {
          remainingSize = 0;
        }

        if (remainingSize <= 0) {
          try {
            await notifySlEvent({ symbol: trade.symbol, reason: 'stop_loss_trigger_filled', closedBy: 'stop_loss_trigger_filled' });
          } catch (error) {
            logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'SL telegram notify failed');
          }
          activeTrades.delete(correlationId);
          continue;
        }

        const closingSide: 'buy' | 'sell' = trade.side === 'buy' ? 'sell' : 'buy';
        const slCandidate = openOrders.find((o) => {
          if (o.symbol.toUpperCase() !== trade.symbol.toUpperCase()) return false;
          if (o.side !== closingSide) return false;
          const raw = o.raw as Record<string, unknown> | undefined;
          const tpsl = String(
            (raw as { tpsl?: unknown } | undefined)?.tpsl
            ?? (raw as { trigger?: { tpsl?: unknown } } | undefined)?.trigger?.tpsl
            ?? (raw as { orderType?: { trigger?: { tpsl?: unknown } } } | undefined)?.orderType?.trigger?.tpsl
            ?? ''
          ).toLowerCase();
          return tpsl === 'sl';
        });

        const oldSlOrderId = trade.slOrderId;
        trade.slOrderId = slCandidate?.id ?? null;
        logger.warn(
          { component: 'tp-monitor', symbol: trade.symbol, correlationId, oldSlOrderId, reboundSlOrderId: slCandidate?.id ?? null, remainingSize },
          'SL order disappeared but position remains open; skip SL alert and continue tracking',
        );
      }

      if (justFilled.length === 0) continue;

      trade.tpOrderIds = stillPending;

      if (!trade.firstTpFired && justFilled.length > 0) {
        trade.firstTpFired = true;
        logger.info({ component: 'tp-monitor', symbol: trade.symbol, correlationId, filledTp: justFilled }, 'first TP filled → moving SL to entry (break-even)');

        // Cancel current SL
        if (trade.slOrderId) {
          try { await exchange.cancelOrder(trade.slOrderId); } catch { /* best-effort */ }
        }

        // Determine remaining position size
        let remainingSize = 0;
        try {
          const positions = await exchange.getOpenPositions();
          const pos = positions.find(p => p.symbol.toUpperCase() === trade.symbol.toUpperCase());
          remainingSize = pos?.size ?? 0;
        } catch { remainingSize = 0; }

        if (remainingSize > 0 && trade.entryPrice > 0) {
          const closingSide: 'buy' | 'sell' = trade.side === 'buy' ? 'sell' : 'buy';
          try {
            const beSlAck = await exchange.placeTriggerOrder({
              symbol: trade.symbol, side: closingSide, size: remainingSize,
              triggerPrice: trade.entryPrice, kind: 'sl', reduceOnly: true,
              clientOrderId: `be-sl-${correlationId}`,
            });
            trade.slOrderId = beSlAck.orderId ?? null;
            logRiskGateAudit({
              gate: 'tp_fill_monitor', passed: beSlAck.ok,
              reason: beSlAck.ok ? 'break_even_sl_placed' : 'break_even_sl_failed',
              details: { symbol: trade.symbol, entryPrice: trade.entryPrice, remainingSize, orderId: beSlAck.orderId },
            });
            if (beSlAck.ok) {
              try {
                await notifyTpHit({ symbol: trade.symbol, entryPrice: trade.entryPrice, remainingSize, tpIds: justFilled });
              } catch (error) {
                logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'TP telegram notify failed');
              }
            }
          } catch (err) {
            logger.error({ component: 'tp-monitor', err }, 'failed to place break-even SL');
          }
        }
      }

      if (stillPending.length === 0) {
        try {
          await notifyPositionClosedEvent({
            symbol: trade.symbol,
            correlationId,
            tpsFilled: justFilled.length,
            reason: 'tp_all_filled',
          });
        } catch (error) {
          logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'position-closed telegram notify failed');
        }
        activeTrades.delete(correlationId);
      }
    }
  } catch (err) {
    logger.warn({ component: 'tp-monitor', err }, 'TP fill monitor tick failed');
  } finally {
    tpFillMonitorBusy = false;
  }
}

function startTpFillMonitor(): void {
  if (tpFillMonitorTimer) return;
  tpFillMonitorTimer = setInterval(() => {
    runTpFillMonitorTick().catch(err => logger.warn({ component: 'tp-monitor', err }, 'tick error'));
  }, 30_000);
  tpFillMonitorTimer.unref?.();
  logger.info({ component: 'tp-monitor' }, 'TP fill monitor started');
}

// ─── RESTful Trading Command Layer (ISSUE #12) ───────────────────────

/** Classify exchange errors into standard codes */
function classifyError(error: string | undefined): TradingErrorCode {
  if (!error) return 'exchange_error';
  const lower = error.toLowerCase();
  if (lower.includes('rate limit') || lower.includes('429') || lower.includes('too many')) return 'rate_limited';
  if (lower.includes('insufficient') || lower.includes('not enough') || lower.includes('balance')) return 'insufficient_balance';
  if (lower.includes('invalid') || lower.includes('bad') || lower.includes('param')) return 'invalid_params';
  if (lower.includes('not found') || lower.includes('not_found') || lower.includes('no order')) return 'order_not_found';
  if (lower.includes('already') && (lower.includes('cancel') || lower.includes('filled'))) return 'already_canceled';
  return 'exchange_error';
}

/** Idempotency store: clientOrderId → response (in-memory, survives within process) */
const idempotencyCache = new Map<string, { timestamp: number; response: any }>();
const IDEMPOTENCY_TTL_MS = 30 * 60 * 1000; // 30 minutes
const IDEMPOTENCY_MAX_SIZE = 1000;

function pruneIdempotencyCache() {
  const cutoff = Date.now() - IDEMPOTENCY_TTL_MS;
  for (const [key, entry] of idempotencyCache) {
    if (entry.timestamp < cutoff) idempotencyCache.delete(key);
  }
  // FIFO eviction if still over max size
  while (idempotencyCache.size > IDEMPOTENCY_MAX_SIZE) {
    const oldest = idempotencyCache.keys().next().value;
    if (oldest !== undefined) idempotencyCache.delete(oldest);
    else break;
  }
}

// POST /api/live/order — idempotent place order
app.post('/api/live/order', ownerAuth, staleMarketDataGate, riskGateMiddleware, symbolAllocationGate, engulfingGate, radarContextPolicyGate, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    price,
    size,
    leverage,
    clientOrderId,
    reduceOnly = false,
    stopLoss: requestStopLoss,
    takeProfit: requestTakeProfit,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'buy' | 'sell';
    price?: number;
    size?: number;
    leverage?: number;
    clientOrderId?: string;
    reduceOnly?: boolean;
    stopLoss?: number;
    takeProfit?: number;
    confirm?: boolean;
  };
  const executionIntentId = (req as any)._executionIntentId as string | undefined;
  const radarPolicyGate = (req as any)._radarContextPolicyGate as { snapshot?: { policyId?: string }; override?: boolean } | undefined;

  // Validation
  if (side !== 'buy' && side !== 'sell') {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'side must be buy or sell' });
  }
  const px = Number(price);
  if (!Number.isFinite(px) || px <= 0) {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'invalid price' });
  }

  // ── Allocation sizing: compute size when not provided ──────────────
  let qty = Number(size);
  let sizingSource: 'explicit' | 'runtime_allocation' = 'explicit';
  let sizingMeta: { marginUsd: number; notionalUsd: number; effectiveLeverage: number } | undefined;

  if (!Number.isFinite(qty) || qty <= 0) {
    // Auto-size from runtime allocation rules
    const normalizedSym = normalizeSymbol(symbol);
    const effectiveRules = rulesCache.getEffectiveRules();
    const riskCheck: RiskCheckResult | undefined = (req as any)._riskCheck;

    let equityUsd = riskCheck?.equityUsd ?? 0;
    let availableUsd = 0;
    try {
      const account = await exchange.getAccountState();
      if (account) {
        if (!equityUsd && account.equityValidForRisk) equityUsd = account.equityUsd ?? 0;
        availableUsd = account.availableUsd ?? 0;
      }
    } catch {
      // best-effort
    }

    let sizeDecimals = 6;
    try {
      const meta = await exchange.getInstrumentMeta(normalizedSym);
      if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
    } catch {
      // best-effort: use default
    }

    const sizing = computeAllocationSize({
      symbol: normalizedSym,
      price: px,
      equityUsd,
      availableUsd,
      rules: effectiveRules,
      sizeDecimals,
    });

    if (!sizing.ok) {
      const db = await getDb();
      updateExecutionIntent(db, executionIntentId, { status: 'rejected' });
      await db.write();
      logRiskGateAudit({ gate: 'allocation_sizing', passed: false, reason: sizing.reason, details: { symbol: normalizedSym, price: px, equityUsd, availableUsd } });
      return res.status(400).json({
        ok: false,
        errorCode: 'allocation_sizing_failed' as TradingErrorCode,
        error: `Allocation sizing failed: ${sizing.reason}`,
      });
    }

    qty = sizing.size;
    sizingSource = 'runtime_allocation';
    sizingMeta = { marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage };

    logRiskGateAudit({
      gate: 'allocation_sizing',
      passed: true,
      details: { symbol: normalizedSym, size: qty, marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage, allocationPct: sizing.allocationPct },
    });
  }

  const notional = px * qty;
  const normalizedSymbol = normalizeSymbol(symbol);

  if (!reduceOnly && sizingSource === 'runtime_allocation') {
    let gross: Awaited<ReturnType<typeof checkPortfolioGrossCap>>;
    try {
      gross = await checkPortfolioGrossCap({
        symbol: normalizedSymbol,
        price: px,
        size: qty,
        effectiveRules: rulesCache.getEffectiveRules(),
        riskCheck: (req as any)._riskCheck,
      });
    } catch (error) {
      const db = await getDb();
      updateExecutionIntent(db, executionIntentId, { status: 'rejected' });
      await db.write();
      logger.error({ component: 'risk-gate', err: error }, 'portfolio gross cap check failed');
      return res.status(503).json({
        ok: false,
        errorCode: 'allocation_check_unavailable' as TradingErrorCode,
        error: 'Portfolio gross exposure guard unavailable. Trading is temporarily blocked.',
      });
    }
    if (!gross.ok) {
      const db = await getDb();
      updateExecutionIntent(db, executionIntentId, { status: 'rejected' });
      await db.write();
      return res.status(403).json({
        ok: false,
        errorCode: 'portfolio_gross_cap_exceeded' as TradingErrorCode,
        error: `Order would bring portfolio gross exposure to $${gross.totalGross.toFixed(2)}, exceeding cap of $${gross.cap.toFixed(2)}.`,
        currentGross: Number(gross.currentGross.toFixed(2)),
        newNotional: Number(gross.newNotional.toFixed(2)),
        totalGross: Number(gross.totalGross.toFixed(2)),
        cap: Number(gross.cap.toFixed(2)),
      });
    }
  }

  // Manual confirmation gate
  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({ ok: false, errorCode: 'manual_confirmation_required' as TradingErrorCode, hint: 'resend with {"confirm": true}' });
  }

  const correlationId = clientOrderId || nanoid();

  // Idempotency check
  pruneIdempotencyCache();
  if (clientOrderId && idempotencyCache.has(clientOrderId)) {
    const cached = idempotencyCache.get(clientOrderId)!;
    return res.status(200).json({ ...cached.response, idempotent: true });
  }

  // Set leverage if provided — enforce runtime maxLeverage cap
  if (leverage !== undefined) {
    const lev = Number(leverage);
    if (!Number.isFinite(lev) || lev <= 0 || lev > rulesCache.getEffectiveRules().maxLeverage) {
      logRiskGateAudit({ gate: 'leverage_cap', passed: false, reason: 'leverage_limit_exceeded', details: { requested: lev, max: rulesCache.getEffectiveRules().maxLeverage } });
      return res.status(400).json({ ok: false, errorCode: 'leverage_limit_exceeded' as TradingErrorCode, error: `Leverage ${lev}x exceeds max ${rulesCache.getEffectiveRules().maxLeverage}x` });
    }
    await exchange.setLeverage(normalizedSymbol, lev);
  }

  const db = await getDb();
  const now = new Date().toISOString();

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: now,
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: 'live_place_order',
    payload: { reduceOnly: Boolean(reduceOnly), notionalUsdc: Number(notional.toFixed(4)), clientOrderId: correlationId }
  });
  db.data.tradeEvents[db.data.tradeEvents.length - 1].payload = {
    ...(db.data.tradeEvents[db.data.tradeEvents.length - 1].payload ?? {}),
    executionIntentId: executionIntentId ?? null,
    radarPolicyId: radarPolicyGate?.snapshot?.policyId ?? null,
    radarContextOverride: radarPolicyGate?.override === true,
  };

  const intent: OrderIntent = { symbol: normalizedSymbol, side, price: px, size: qty, reduceOnly: Boolean(reduceOnly), clientOrderId: correlationId };
  const ack = await exchange.placeLimitOrder(intent);

  const errorCode = ack.ok ? undefined : classifyError(ack.error);

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: ack.ok ? 'live_order_ack' : 'live_order_rejected',
    payload: { orderId: ack.orderId ?? null, status: ack.status ?? null, error: ack.error ?? null, errorCode: errorCode ?? null }
  });
  db.data.tradeEvents[db.data.tradeEvents.length - 1].payload = {
    ...(db.data.tradeEvents[db.data.tradeEvents.length - 1].payload ?? {}),
    executionIntentId: executionIntentId ?? null,
  };

  updateExecutionIntent(db, executionIntentId, ack.ok
    ? { status: 'auto_order_placed', orderId: ack.orderId }
    : { status: 'rejected' });

  if (!ack.ok) {
    await notifyOrderRejectedEvent({
      symbol: normalizedSymbol,
      source: 'api:order',
      error: ack.error ?? 'exchange_rejected',
    }).catch(() => undefined);
  }

  // TP/SL defaults: auto-apply after successful non-reduceOnly order
  let tpSlResult: Awaited<ReturnType<typeof placeTpSlTriggerOrders>> | undefined;
  let tpSlApplied: TpSlDefaults | null = null;

  if (ack.ok && !reduceOnly) {
    await clearPendingConfirmationForSymbol(normalizedSymbol);
    try {
      await notifyTradeOpen({ symbol: normalizedSymbol, side, price: px, size: qty, source: 'api:order' });
    } catch (error) {
      logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
    }
    tpSlApplied = resolveTpSlDefaults(px, side, requestStopLoss, requestTakeProfit);
    if (tpSlApplied) {
      try {
        tpSlResult = await placeTpSlTriggerOrders(normalizedSymbol, side, qty, tpSlApplied, correlationId, px);
      } catch (err) {
        tpSlResult = {
          stopLossOrder: { ok: false, error: 'tp_sl_placement_failed' },
          takeProfitOrder: { ok: false, error: 'tp_sl_placement_failed' }, takeProfitOrders: [{ ok: false, error: 'tp_sl_placement_failed' }]
        };
      }

      logRiskGateAudit({
        gate: 'tp_sl_defaults',
        passed: true,
        reason: tpSlApplied.applied ? 'runtime_defaults_applied' : 'explicit_values_used',
        details: {
          source: tpSlApplied.source,
          stopLoss: tpSlApplied.stopLoss,
          takeProfit: tpSlApplied.takeProfit,
          entryPrice: px,
          side,
          slOrderOk: tpSlResult?.stopLossOrder.ok ?? false,
          tpOrderOk: tpSlResult?.takeProfitOrder.ok ?? false
        }
      });
    }
  }

  await db.write();

  const response: Record<string, unknown> = { ok: ack.ok, orderId: ack.orderId, clientOrderId: correlationId, status: ack.status, errorCode, error: ack.error, sizingSource };

  if (sizingMeta) {
    response.marginUsd = sizingMeta.marginUsd;
    response.notionalUsd = sizingMeta.notionalUsd;
    response.effectiveLeverage = sizingMeta.effectiveLeverage;
  }

  if (tpSlApplied && tpSlResult) {
    response.stopLoss = tpSlApplied.stopLoss;
    response.takeProfit = tpSlApplied.takeProfit;
    response.tpSlSource = tpSlApplied.source;
    response.stopLossOrder = tpSlResult.stopLossOrder;
    response.takeProfitOrder = tpSlResult.takeProfitOrder;
  }

  // Cache for idempotency
  if (clientOrderId) {
    idempotencyCache.set(clientOrderId, { timestamp: Date.now(), response });
  }

  return res.status(ack.ok ? 200 : 400).json(response);
});

// DELETE /api/live/order/:id — safe re-cancel
app.delete('/api/live/order/:id', ownerAuth, async (req, res) => {
  const orderId = req.params.id;
  const { confirm } = req.query as { confirm?: string };
  const confirmed = confirm === 'true' || confirm === '1';

  if (rulesCache.getEffectiveRules().manualConfirmation && !confirmed) {
    return res.status(409).json({ ok: false, errorCode: 'manual_confirmation_required' as TradingErrorCode, hint: 'add ?confirm=true' });
  }

  const result = await exchange.cancelOrder(orderId);

  // Safe re-cancel: if order not found, treat as success (already canceled/filled)
  const safeOk = result.ok || classifyError(result.error) === 'order_not_found' || classifyError(result.error) === 'already_canceled';

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: LIVE_SYMBOL,
    source: 'live',
    type: safeOk ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId: nanoid(),
    reason: safeOk ? 'live_cancel_order' : 'live_cancel_failed',
    payload: { orderId, originalOk: result.ok, safeOk, error: result.error ?? null, errorCode: safeOk ? null : classifyError(result.error) }
  });
  await db.write();

  return res.status(safeOk ? 200 : 400).json({
    ok: safeOk,
    orderId,
    alreadyCanceled: !result.ok && safeOk,
    errorCode: safeOk ? undefined : classifyError(result.error),
    error: safeOk ? undefined : result.error
  });
});

// PUT /api/live/order/:id/reduce — reduce-only modify with audit
app.put('/api/live/order/:id/reduce', ownerAuth, async (req, res) => {
  const orderId = req.params.id;
  const { newSize, confirm } = req.body as { newSize?: number; confirm?: boolean };

  const qty = Number(newSize);
  if (!Number.isFinite(qty) || qty <= 0) {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'newSize must be a positive number' });
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({ ok: false, errorCode: 'manual_confirmation_required' as TradingErrorCode, hint: 'resend with {"confirm": true}' });
  }

  const db = await getDb();
  const correlationId = nanoid();
  const user = process.env.HYPERLIQUID_ACCOUNT_ADDRESS?.trim();

  // Find the existing order
  let existingOrder: any = null;
  try {
    const openOrders = await exchange.getOpenOrders();
    existingOrder = openOrders.find((o) => o.id === orderId);
  } catch {
    // continue
  }

  if (!existingOrder) {
    appendTradeEvent(db.data, {
      symbol: LIVE_SYMBOL,
      source: 'live',
      type: 'order_rejected',
      timestamp: new Date().toISOString(),
      correlationId,
      reason: 'live_reduce_order_not_found',
      payload: { orderId, newSize: qty }
    });
    await db.write();
    return res.status(404).json({ ok: false, errorCode: 'order_not_found' as TradingErrorCode, error: 'order not found in open orders' });
  }

  if (qty >= existingOrder.size) {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: `newSize (${qty}) must be less than current size (${existingOrder.size})` });
  }

  // Log the reduce intent
  appendTradeEvent(db.data, {
    symbol: existingOrder.symbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(existingOrder.side),
    price: existingOrder.price,
    quantity: qty,
    reason: 'live_reduce_order',
    payload: { orderId, originalSize: existingOrder.size, newSize: qty, action: 'reduce' }
  });

  // Cancel existing order
  const cancelResult = await exchange.cancelOrder(orderId);
  if (!cancelResult.ok) {
    const errorCode = classifyError(cancelResult.error);
    appendTradeEvent(db.data, {
      symbol: existingOrder.symbol,
      source: 'live',
      type: 'order_rejected',
      timestamp: new Date().toISOString(),
      correlationId,
      reason: 'live_reduce_cancel_failed',
      payload: { orderId, error: cancelResult.error ?? null, errorCode }
    });
    await db.write();
    await notifyOrderRejectedEvent({
      symbol: existingOrder.symbol,
      source: 'api:order/reduce:cancel',
      error: cancelResult.error ?? 'cancel_failed',
    }).catch(() => undefined);
    return res.status(400).json({ ok: false, errorCode, error: cancelResult.error });
  }

  // Place new order with reduced size (reduce-only)
  const newClientOrderId = `reduce-${correlationId}`;
  const intent: OrderIntent = {
    symbol: existingOrder.symbol,
    side: existingOrder.side,
    price: existingOrder.price,
    size: qty,
    reduceOnly: true,
    clientOrderId: newClientOrderId
  };

  const ack = await exchange.placeLimitOrder(intent);
  const errorCode = ack.ok ? undefined : classifyError(ack.error);

  appendTradeEvent(db.data, {
    symbol: existingOrder.symbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(existingOrder.side),
    price: existingOrder.price,
    quantity: qty,
    reason: ack.ok ? 'live_reduce_order_ack' : 'live_reduce_order_failed',
    payload: {
      originalOrderId: orderId,
      newOrderId: ack.orderId ?? null,
      originalSize: existingOrder.size,
      newSize: qty,
      error: ack.error ?? null,
      errorCode: errorCode ?? null
    }
  });
  await db.write();

  if (!ack.ok) {
    await notifyOrderRejectedEvent({
      symbol: existingOrder.symbol,
      source: 'api:order/reduce:submit',
      error: ack.error ?? 'exchange_rejected',
    }).catch(() => undefined);
  }

  return res.status(ack.ok ? 200 : 400).json({
    ok: ack.ok,
    originalOrderId: orderId,
    newOrderId: ack.orderId,
    originalSize: existingOrder.size,
    newSize: qty,
    errorCode,
    error: ack.error
  });
});

app.use(express.static(distDir));
app.get('*', (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

// ─── Process-level error handlers ─────────────────────────────────────
process.on('unhandledRejection', (reason) => {
  logger.error({ component: 'process', err: reason }, 'unhandled rejection');
});

process.on('uncaughtException', (error) => {
  logger.fatal({ component: 'process', err: error }, 'uncaught exception');
  // Let the process crash after logging — do not swallow fatal errors
  process.exit(1);
});

// ─── Graceful shutdown ────────────────────────────────────────────────
let shuttingDown = false;

const server = app.listen(port, host, () => {
  logger.info({ component: 'server', host, port }, `server listening on http://${host}:${port}`);
  rulesCache.start();
  ingestRestFallback().catch((err) => logger.warn({ component: 'live', err }, 'initial REST fallback ingest failed'));
  startLiveMidStream();

  // Stagger monitor warmups so their initial Hyperliquid reads do not collide.
  // The adapter-level coordinator dedupes concurrent duplicates, but spacing
  // the first ticks also reduces peak concurrency against the info endpoint.
  const baseStagger = MONITOR_STARTUP_STAGGER_MS;
  startDrawdownWatchdog(baseStagger * 1);
  startDailyDrawdownMidnightReset();
  startEngulfingMonitor(baseStagger * 2);
  startFvgMonitor(baseStagger * 3);
  startTpFillMonitor();
  startTelegramOutboxLoop();
  startTelegramUpdateLoop();
  startDailyAnalyticsLoop();
  startAlphaRadarMonitoringPlane();
  void refreshLiveSnapshotState(LIVE_SYMBOL, getLiveMode()).catch((err) => logger.warn({ component: 'live', err }, 'initial live snapshot warmup failed'));
  getTelegramConfig()
    .then((cfg) => {
      if (!cfg) {
        logger.warn({ component: 'pending-confirmation' }, 'Telegram alerts disabled (configure bot token + chat id in Settings)');
      } else {
        logger.info({ component: 'telegram', chatId: cfg.chatId }, 'Telegram notifications enabled');
      }
    })
    .catch(() => undefined);
});

async function gracefulShutdown(signal: string) {
  if (shuttingDown) return;
  shuttingDown = true;
  logger.info({ component: 'shutdown', signal }, 'received signal, shutting down gracefully');

  // 1. Stop accepting new connections
  server.close(() => {
    logger.info({ component: 'shutdown' }, 'HTTP server closed');
  });

  // 2. Clear timers
  rulesCache.stop();
  clearInterval(auditFlushTimer);
  clearInterval(rateLimitPruneTimer);
  if (drawdownWatchdogTimer) { clearInterval(drawdownWatchdogTimer); drawdownWatchdogTimer = null; }
  if (drawdownMidnightBaselineTimer) { clearTimeout(drawdownMidnightBaselineTimer); drawdownMidnightBaselineTimer = null; }
  if (engulfingMonitorTimer) { clearInterval(engulfingMonitorTimer); engulfingMonitorTimer = null; }
  if (fvgMonitorTimer) { clearInterval(fvgMonitorTimer); fvgMonitorTimer = null; }
  if (tpFillMonitorTimer) { clearInterval(tpFillMonitorTimer); tpFillMonitorTimer = null; }
  if (telegramOutboxTimer) { clearInterval(telegramOutboxTimer); telegramOutboxTimer = null; }
  if (telegramUpdateTimer) { clearInterval(telegramUpdateTimer); telegramUpdateTimer = null; }
  if (dailyAnalyticsTimer) { clearInterval(dailyAnalyticsTimer); dailyAnalyticsTimer = null; }
  if (alphaRadarMarketTimer) { clearInterval(alphaRadarMarketTimer); alphaRadarMarketTimer = null; }
  if (alphaRadarExternalTimer) { clearInterval(alphaRadarExternalTimer); alphaRadarExternalTimer = null; }
  if (restFallbackTimer) { clearInterval(restFallbackTimer); restFallbackTimer = null; }
  if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }

  // 3. Close WS stream
  if (midStreamHandle) { midStreamHandle.close(); midStreamHandle = null; }

  // 4. Best-effort: flush risk audit + close persistence
  try { await flushRiskAudit(); } catch { /* best effort */ }
  try {
    const { getStore } = await import('../core/persistence/index.js');
    const store = await getStore();
    await store.close();
    logger.info({ component: 'shutdown' }, 'persistence store closed');
  } catch { /* store may not have been initialised */ }

  logger.info({ component: 'shutdown' }, 'cleanup complete, exiting');
  process.exit(0);
}

process.on('SIGTERM', () => { gracefulShutdown('SIGTERM'); });
process.on('SIGINT', () => { gracefulShutdown('SIGINT'); });
