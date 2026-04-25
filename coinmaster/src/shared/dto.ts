export type Bias = 'long' | 'short' | 'off';
export type TradeSide = 'long' | 'short';
export type PositionStatus = 'open' | 'closed';
export type StatsPeriod = 'week' | 'month';

export type TradingRulesTimeframe = '5m' | '15m' | '1h' | '4h';
export type FvgTimeframe = '1h' | '4h';
export type SignalStrategy = 'engulfing' | 'fvg' | 'radar';
export type AssetClass = 'crypto' | 'commodity' | 'forex' | 'index' | 'other';
export type BiasMode = 'global' | 'symbol';

export interface BiasPolicySymbolOverride {
  /** global => uses shared class bias, symbol => custom per-symbol bias */
  mode: BiasMode;
}

export interface BiasPolicySettings {
  /** Per-symbol mode override; absent => uses shared class bias. */
  symbolOverrides: Record<string, BiasPolicySymbolOverride>;
}

export interface TradingCoinAllocation {
  symbol: 'BTC' | 'ETH' | 'SOL' | string;
  enabled: boolean;
  pct: number;
  assetClass?: AssetClass;
}

export interface TradingRulesSettings {
  coins: TradingCoinAllocation[];
  /** @deprecated use entryTimeframes[] — kept for back-compat serialisation */
  entryTf: TradingRulesTimeframe;
  /** @deprecated use emergencyExitTimeframes[] — kept for back-compat serialisation */
  exitTf: TradingRulesTimeframe;
  /** Multi-timeframe entry signals (≥1 required). */
  entryTimeframes: TradingRulesTimeframe[];
  /** Multi-timeframe emergency-exit signals (≥1 required). */
  emergencyExitTimeframes: TradingRulesTimeframe[];
  /** Lookback window for engulfing / breakout detection (candles). */
  engulfingLookbackCandles: number;
  fvgRetrace: number;
  /** Minimum FVG zone width as % of current price (filters out micro-gaps/noise). */
  fvgMinWidthPct: number;
  /** Require the originating HTF FVG impulse to include a liquidity sweep over the configured lookback. */
  fvgRequireSweep: boolean;
  /** Prior HTF candles checked for the qualifying liquidity sweep. */
  fvgSweepLookbackCandles: number;
  /** Only allow the first touch of a fresh HTF FVG; reject already mitigated zones. */
  fvgRequireFirstTouch: boolean;
  /** Maximum age of an FVG zone, in candles, when first-touch mode is enabled. */
  maxZoneAgeCandles: number;
  /** Require engulfing-body confirmation after the HTF FVG retrace touch. */
  fvgRequireConfirmation: boolean;
  /** Allowed confirmation timeframes after the HTF FVG retrace touch. */
  fvgConfirmationTimeframes: TradingRulesTimeframe[];
  maxLeverage: number;
  dailyDrawdown: number;
  /** @deprecated use tpLevels[] — kept for back-compat serialisation */
  tpPct: number;
  /** Up to 3 take-profit levels in % (sorted ascending). After TP1 hits → SL moves to entry (break-even). */
  tpLevels: number[];
  slPct: number;
  /** Percentage of position to close on opposite engulfing exit signal (0–100, default 50).
   *  0% disables emergency exit execution; partial close (>0 and <100) moves SL to entry. */
  exitClosePct: number;
  autoConfirm: boolean;
  biasPolicy?: BiasPolicySettings;

  // ── Stage-1 SignalQualityContext / portfolio fields (issue #61) ─────
  /** Higher-timeframe used for the regime filter (EMA slope + ADX). */
  regimeTf?: TradingRulesTimeframe;
  /** Minimum ADX required on the regime timeframe to consider direction trending. */
  adxMin?: number;
  /** Minimum impulse body / range as a fraction of ATR for displacement quality. */
  minImpulseAtr?: number;
  /** Hard reject gate: minimum expected reward-to-risk before handoff. */
  minExpectedRr?: number;
  /** Time stop for new entries — close if no follow-through after N bars. */
  timeStopBars?: number;
  /** Per-trade risk in % of equity used by sizing helpers. */
  riskPerTradePct?: number;
  /** Lock new entries for N minutes after a flagged macro/event window. */
  eventLockoutMinutes?: number;
  /** Maximum aggregate gross exposure across the portfolio, in % of equity. */
  portfolioGrossCap?: number;
}

export interface RadarRuntimeSettings {
  enabled: boolean;
  autoConfirm: boolean;
}

export type AlphaRadarObservationKind = 'external' | 'market';
export type AlphaRadarSourceType = 'rss' | 'news' | 'market' | 'manual' | 'direct' | 'social';
export type AlphaRadarSourceLayer = 'primary' | 'duplicate' | 'narrative';
export type AlphaRadarSourceClass = 'market' | 'official' | 'newswire' | 'macro' | 'flow' | 'social';
export type AlphaRadarConnectorType = 'telegram' | 'reddit' | 'bluesky';
export type AlphaRadarMonitoringGroup = 'macro' | 'proxy' | 'equity';

export interface AlphaRadarConnectorAuthSession {
  kind: 'telegram_qr';
  status: 'pending' | 'expired' | 'cancelled' | 'error';
  startedAt?: string;
  expiresAt?: string;
  pollAfterMs?: number;
  qrUrl?: string;
  qrTokenBase64Url?: string;
  message?: string;
  error?: string;
}

export interface AlphaRadarConnectorState {
  status: 'idle' | 'connected' | 'needs_auth' | 'awaiting_code' | 'awaiting_qr' | 'error';
  configured: boolean;
  needsAuth: boolean;
  lastSyncAt?: string;
  lastSyncStatus: 'pending' | 'success' | 'error';
  lastSyncCursor?: string;
  connectionLabel?: string;
  message?: string;
  error?: string;
  authSession?: AlphaRadarConnectorAuthSession;
}

export interface AlphaRadarConnectorSettings {
  enabled: boolean;
  sourceLabel?: string;
  sourceLayer?: AlphaRadarSourceLayer;
  sourceClass?: AlphaRadarSourceClass;
  weight?: number;
  watchlist: string[];
  allowlist: string[];
  state: AlphaRadarConnectorState;
}

export interface AlphaRadarConnectorRuntime {
  type: AlphaRadarConnectorType;
  source: string;
  sourceType: 'social';
  settings: AlphaRadarConnectorSettings;
}

export interface AlphaRadarConnectorRuntimeSummary {
  type: AlphaRadarConnectorType;
  source: string;
  sourceType: 'social';
  sourceLayer?: AlphaRadarSourceLayer;
  sourceClass?: AlphaRadarSourceClass;
  enabled: boolean;
  watchlistCount: number;
  allowlistCount: number;
  weight: number;
  sourceLabel?: string;
  state: AlphaRadarConnectorState;
}

export interface AlphaRadarProvenance {
  feedId?: string;
  sourceLabel?: string;
  publisher?: string;
  author?: string;
  url?: string;
  publishedAt?: string;
  ingestedAt?: string;
  /** Canonicalized URL (lowercased host, stripped tracking params) used for cross-source dedupe. */
  canonicalUrl?: string;
  /** Hash (sha-1 hex) of the normalized title+excerpt+url payload — used as exact-match dedupe key. */
  payloadHash?: string;
  /** External/source-supplied id (RSS guid, GDELT id, statuspage incident id, etc.). */
  externalId?: string;
  /** When the upstream item was actually fetched (HTTP response time). */
  fetchedAt?: string;
  /** When this observation was first written to durable storage. */
  observedAt?: string;
  /** HTTP cache headers from the most recent fetch, used for conditional requests. */
  httpEtag?: string;
  httpLastModified?: string;
  httpStatus?: number;
  /** Compact reference to the raw upstream payload (truncated; for audit only — not full payloads). */
  rawPayloadRef?: string;
  /** Identifier of the parser that produced this observation (e.g. 'rss-xml', 'gdelt', 'statuspage_incidents'). */
  parser?: string;
  /** Arbitrary upstream metadata kept verbatim for audit (cap enforced at write site). */
  raw?: Record<string, unknown>;
}

export interface AlphaRadarFeedConfig {
  id: string;
  label: string;
  url: string;
  enabled: boolean;
  source: string;
  collectorType?: 'rss' | 'rsshub' | 'gdelt' | 'json';
  parser?: 'statuspage_incidents' | 'statuspage_maintenances' | 'binance_cms_articles' | 'tree_news';
  sourceLayer?: AlphaRadarSourceLayer;
  sourceClass?: AlphaRadarSourceClass;
  weight?: number;
  assetTags?: string[];
  topicTags?: string[];
}

export interface AlphaRadarMonitoringWatchAsset {
  id: string;
  label: string;
  symbol: string;
  provider: 'stooq';
  providerSymbol: string;
  realtimeSymbol?: string;
  enabled: boolean;
  monitoringOnly: boolean;
  monitoringGroup?: AlphaRadarMonitoringGroup;
  sourceClass?: AlphaRadarSourceClass;
  weight?: number;
  topicTags?: string[];
}

export interface AlphaRadarMarketSnapshotSettings {
  macroWatchlist: AlphaRadarMonitoringWatchAsset[];
  equityWatchlist: AlphaRadarMonitoringWatchAsset[];
}

export interface AlphaRadarSettings {
  enabled: boolean;
  manualQueueOnly: boolean;
  autoConfirmOrders: boolean;
  allowHypothesisEntries: boolean;
  maxIdeasPerCycle: number;
  minIdeaScore: number;
  collectorLookbackHours: number;
  refreshIntervalMinutes: number;
  feeds: AlphaRadarFeedConfig[];
  marketSnapshot?: AlphaRadarMarketSnapshotSettings;
  connectors?: Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings>;
}

export interface TelegramNotifySettings {
  botToken: string;
  chatId: string;
  notifyOpen: boolean;
  notifyTp: boolean;
  notifySl: boolean;
  notifyManualConfirm: boolean;
  notifyDailyAnalytics: boolean;
  /** Notify when a trade signal is blocked by risk gate or bias */
  notifySignalRejected: boolean;
  /** Notify when an exchange order is rejected (auth, balance, validation) */
  notifyOrderRejected: boolean;
  /** Notify when a trade position is fully closed via all TPs */
  notifyPositionClosed: boolean;
  updateOffset?: number;
}

export interface TelegramOutboxItem {
  id: string;
  category: 'manual_confirm' | 'trade_open' | 'tp' | 'sl' | 'analytics_daily' | 'signal_rejected' | 'order_rejected' | 'position_closed' | 'system';
  text: string;
  replyMarkup?: unknown;
  dedupeKey?: string;
  status: 'queued' | 'sent' | 'failed';
  attempts: number;
  nextAttemptAt: string;
  createdAt: string;
  sentAt?: string;
  lastError?: string;
}

/** off = disabled, read_only = fetch data only (no trading), live = full trading enabled */
export type ExchangeConnectionMode = 'off' | 'read_only' | 'live';

/** @deprecated use ExchangeConnectionMode */
export type ReadOnlyExchangeMode = ExchangeConnectionMode;

export interface BybitConnectionSettings {
  mode: ExchangeConnectionMode;
  apiKey: string;
  apiSecret: string;
  accountType: 'UNIFIED' | 'CONTRACT' | 'SPOT';
  categories: Array<'linear' | 'inverse' | 'spot' | 'option'>;
}

export interface ExternalExchangesSettings {
  bybit: BybitConnectionSettings;
}

export interface HyperliquidCredentialsSettings {
  accountAddress: string;
  apiWalletAddress: string;
  apiPrivateKey: string;
  enabled?: boolean;
}

/** @deprecated use ExternalExchangesSettings */
export type ReadOnlyExchangesSettings = ExternalExchangesSettings;

export interface AppSettings {
  depositUsd: number;
  tradingRules: TradingRulesSettings;
  radarRuntime: RadarRuntimeSettings;
  alphaRadar?: AlphaRadarSettings;
  telegramNotify?: TelegramNotifySettings;
  hyperliquid?: HyperliquidCredentialsSettings;
  /** External exchange connections (Bybit, Binance, etc.) */
  externalExchanges?: ExternalExchangesSettings;
  /** @deprecated use externalExchanges */
  readOnlyExchanges?: ExternalExchangesSettings;
}

export interface Position {
  id: string;
  symbol: string;
  side: TradeSide;
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  size: number;
  remainingSize?: number;
  realizedPnl?: number;
  tp1Price?: number;
  tp2Price?: number;
  tp3Price?: number;
  tp1Done?: boolean;
  tp2Done?: boolean;
  tp3Done?: boolean;
  leverage?: number;
  openedAt: string;
  closedAt?: string;
  status: PositionStatus;
  pnl: number;
  source: 'manual' | 'sim' | 'live';
  correlationId?: string;
}

export interface TradeLog {
  id: string;
  positionId?: string;
  symbol: string;
  action: 'open' | 'partial' | 'close' | 'bias';
  side?: TradeSide;
  price?: number;
  quantity?: number;
  pnl?: number;
  note?: string;
  timestamp: string;
}

export type TradeEventType =
  | 'bias_changed'
  | 'signal_detected'
  | 'signal_rejected'
  | 'order_submitted'
  | 'order_acknowledged'
  | 'order_rejected'
  | 'partial_fill'
  | 'position_closed'
  | 'manual_open_detected'
  | 'manual_close_detected';

export type TradeEventSource = 'paper' | 'live' | 'replay';

export type TradeEventPayload = Record<string, string | number | boolean | null>;

export interface TradeEvent {
  id: string;
  seq: number;
  symbol: string;
  type: TradeEventType;
  source: TradeEventSource;
  timestamp: string;
  correlationId: string;
  positionId?: string;
  side?: TradeSide;
  price?: number;
  quantity?: number;
  pnl?: number;
  reason?: string;
  prevHash: string | null;
  hash: string;
  payload?: TradeEventPayload;
}

export interface DailyDDBaseline {
  date: string; // YYYY-MM-DD
  startEquityUsd: number;
  updatedAt: string;
  equitySource?: string;
  riskValid?: boolean;
}

export interface RiskGateAuditEntry {
  timestamp: string;
  gate: 'daily_dd' | 'leverage_cap' | 'auth' | 'symbol_allowlist' | 'allocation_cap' | 'allocation_sizing' | 'tp_sl_defaults' | 'market_data' | 'multi_tf_engulfing' | 'engulfing_entry_signal' | 'engulfing_emergency_exit' | 'fvg_entry_signal' | 'radar_entry_signal' | 'radar_context_policy' | 'tp_fill_monitor' | 'partial_close' | 'break_even_sl_after_partial';
  passed: boolean;
  reason?: string;
  details?: Record<string, unknown>;
}

export interface BiasCommand {
  id: string;
  symbol: string;
  bias: Bias;
  createdAt: string;
}

export interface MarketTick {
  symbol: string;
  price: number;
  timestamp: string;
}

export interface Stats {
  period: StatsPeriod;
  periodDays: number;
  depositUsd: number;
  totalTrades: number;
  winRate: number;
  realizedPnl: number;
  realizedPnlPct: number;
  openPnl: number;
  openPnlPct: number;
  avgPnl: number;
  equityUsd: number;
  equityPct: number;
}

export interface LiveAccountSummary {
  equityUsd?: number;
  availableUsd?: number;
  usedMarginUsd?: number;
}

export interface LivePnlSummary {
  dailyNetUsd: number;
  weeklyNetUsd: number;
  monthlyNetUsd: number;
  dailyRealizedUsd: number;
  weeklyRealizedUsd: number;
  monthlyRealizedUsd: number;
}

export interface LivePosition {
  id: string;
  symbol: string;
  side: TradeSide;
  size: number;
  entryPrice?: number;
  dealValue?: number;
  stopLoss?: number;
  takeProfit?: number;
  takeProfits?: number[];
  openedAt?: string;
  leverage?: number;
  unrealizedPnl?: number;
  productType?: 'perp' | 'spot' | 'other';
  accountScope?: string;
  source?: string;
}

export interface PendingConfirmation {
  id: string;
  symbol: string;
  side: TradeSide;
  strategy: SignalStrategy;
  timeframe: TradingRulesTimeframe;
  reason: string;
  price: number;
  size: number;
  leverage: number;
  executionIntentId?: string;
  createdAt: string;
}

export type RadarSignalStatus = 'pending_confirmation' | 'auto_order_placed' | 'rejected' | 'ignored';
export type RadarSignalVerdict = 'ignore' | 'watch' | 'bias' | 'actionable';
export type RadarContextDirectionMode = 'long_only' | 'short_only' | 'both' | 'blocked';
export type RadarContextPolicyReasonCode =
  | 'direction_blocked'
  | 'event_lockout'
  | 'ttl_expired'
  | 'risk_multiplier_blocked'
  | 'missing_required_evidence';

export interface RadarSignalSourceMeta {
  connector?: string;
  kind?: string;
  channel?: string;
  externalId?: string;
  messageTs?: string;
}

export interface RadarSignalRecord {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  timeframe: TradingRulesTimeframe;
  source: string;
  sourceMeta?: RadarSignalSourceMeta;
  reason: string;
  price: number;
  status: RadarSignalStatus;
  createdAt: string;
  updatedAt: string;
  dedupeKey?: string;
  pendingId?: string;
  orderId?: string;
  executionIntentId?: string;
  error?: string;
  duplicateOf?: string;
}

export interface RadarSignalView extends RadarSignalRecord {
  candidateScore: number;
  verdict: RadarSignalVerdict;
  /** Human-readable explanation of why this verdict was chosen. */
  verdictReason?: string;
}

export interface RadarSignalCandidateGroup {
  symbol: string;
  side: 'buy' | 'sell';
  signalCount: number;
  bestScore: number;
  verdict: RadarSignalVerdict;
  verdictLabel: string;
  /** Human-readable explanation of the group verdict. */
  verdictReason?: string;
  sources: string[];
  lastSeenAt?: string;
}

export interface RadarContextAssetOverride {
  symbol: string;
  directionMode?: RadarContextDirectionMode;
  riskMultiplier?: number;
  lockNewEntries?: boolean;
  eventLockoutUntil?: string;
  narrativeRegime?: string;
  priorityScore?: number;
  validUntil?: string;
  reasonCodes?: RadarContextPolicyReasonCode[];
  evidenceIds?: string[];
}

export interface RadarContextPolicy {
  id: string;
  symbol: string;
  assetScope: 'symbol' | 'asset_class';
  assetClass?: AssetClass;
  directionMode: RadarContextDirectionMode;
  riskMultiplier: number;
  lockNewEntries: boolean;
  eventLockoutUntil?: string;
  narrativeRegime: string;
  priorityScore: number;
  validUntil?: string;
  assetSpecificOverrides: RadarContextAssetOverride[];
  reasonCodes: RadarContextPolicyReasonCode[];
  evidenceIds: string[];
  signalCandidateId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ExecutionIntentPolicySnapshot {
  policyId?: string;
  signalCandidateId?: string;
  symbol: string;
  directionMode?: RadarContextDirectionMode;
  riskMultiplier?: number;
  lockNewEntries?: boolean;
  eventLockoutUntil?: string;
  narrativeRegime?: string;
  priorityScore?: number;
  validUntil?: string;
  reasonCodes: RadarContextPolicyReasonCode[];
  evidenceIds: string[];
}

export type ExecutionIntentPolicyDecision = 'accepted' | 'rejected' | 'override' | 'not_applicable';
export type ExecutionIntentStatus =
  | 'created'
  | 'policy_rejected'
  | 'pending_confirmation'
  | 'auto_order_placed'
  | 'rejected'
  | 'ignored';

export interface ExecutionIntent {
  id: string;
  component: 'engulfing-monitor' | 'fvg-monitor' | 'radar-ingest' | 'owner-order-api' | 'owner-order-limit-api' | 'pending-confirmation';
  strategy: SignalStrategy | 'manual';
  symbol: string;
  side: 'buy' | 'sell';
  timeframe?: TradingRulesTimeframe;
  price: number;
  reduceOnly: boolean;
  reason: string;
  sourceLabel: string;
  status: ExecutionIntentStatus;
  auditedOperatorOverride: boolean;
  policyDecision: ExecutionIntentPolicyDecision;
  policyReasonCode?: RadarContextPolicyReasonCode;
  policySnapshot?: ExecutionIntentPolicySnapshot;
  pendingId?: string;
  orderId?: string;
  radarSignalId?: string;
  metadata?: Record<string, string | number | boolean | null>;
  createdAt: string;
  updatedAt: string;
}

export interface RadarSignalsQuery {
  limit?: number;
  status?: RadarSignalStatus;
  symbol?: string;
  connector?: string;
  kind?: string;
  channel?: string;
  source?: string;
}

export interface LiveOpenOrderBreakdown {
  total: number;
  systemManagedProtective: number;
  systemManagedTakeProfit: number;
  systemManagedStopLoss: number;
  other: number;
}

export interface LiveDashboardState {
  connected: boolean;
  mode: {
    manualConfirmation: boolean;
    maxLeverage: number;
  };
  account: LiveAccountSummary | null;
  pnl: LivePnlSummary;
  openOrders: number;
  openOrderBreakdown?: LiveOpenOrderBreakdown;
  openPositions: LivePosition[];
  pendingConfirmations: LivePosition[];
  error?: string;
}

export interface DashboardClassBiasControl {
  assetClass: AssetClass;
  bias: Bias;
  symbols: string[];
}

export interface DashboardCustomBiasControl {
  symbol: string;
  assetClass: AssetClass;
  bias: Bias;
}

export interface DashboardResponse {
  latestBias: Bias;
  latestTick: MarketTick | null;
  live: LiveDashboardState;
  hyperliquid?: {
    tradingConfigured: boolean;
    connected: boolean;
  };
  classBiasControls: DashboardClassBiasControl[];
  customBiasControls: DashboardCustomBiasControl[];
}

export interface RadarSignalQualityBucket {
  total: number;
  pendingConfirmation: number;
  autoOrderPlaced: number;
  rejected: number;
  ignored: number;
  duplicates: number;
  lastSeenAt?: string;
}

export interface RadarSignalsResponse {
  ok: boolean;
  signals: RadarSignalView[];
  summary: {
    total: number;
    pendingConfirmation: number;
    autoOrderPlaced: number;
    rejected: number;
    ignored: number;
    bySource: Array<{ source: string; count: number }>;
    byConnector: Array<{ connector: string; count: number }>;
    byKind: Array<{ kind: string; count: number }>;
    byChannel: Array<{ channel: string; count: number }>;
    qualityBySource: Array<({ source: string } & RadarSignalQualityBucket)>;
    qualityByConnector: Array<({ connector: string } & RadarSignalQualityBucket)>;
    /** Outcome rollup by asset class (crypto, commodity, …). */
    qualityByAsset: Array<{ asset: string } & RadarSignalQualityBucket>;
    /** Outcome rollup by verdict class (ignore, watch, bias, actionable). */
    qualityByVerdict: Array<{ verdict: string } & RadarSignalQualityBucket>;
    /** Outcome rollup by signal family / kind (sourceMeta.kind). */
    qualityByFamily: Array<{ family: string } & RadarSignalQualityBucket>;
    candidateGroups: RadarSignalCandidateGroup[];
  };
}

export interface RadarSignalIngestPayload {
  symbol: string;
  side: 'buy' | 'sell';
  timeframe?: TradingRulesTimeframe;
  source?: string;
  sourceMeta?: RadarSignalSourceMeta;
  reason: string;
  price: number;
}

export interface RadarSignalIngestResponse {
  ok: boolean;
  signal: RadarSignalRecord;
}

export type AlphaRadarActivityLevel = 'info' | 'warn' | 'error';
export type AlphaRadarActivityPlane = 'market' | 'external' | 'system';

export interface AlphaRadarActivityEvent {
  id: string;
  plane: AlphaRadarActivityPlane;
  level: AlphaRadarActivityLevel;
  status: 'started' | 'ok' | 'partial' | 'error';
  title: string;
  message: string;
  source?: string;
  sourceLabel?: string;
  observedAt: string;
  createdAt: string;
  assetTags?: string[];
  topicTags?: string[];
  metadata?: Record<string, unknown>;
}

export interface AlphaRadarCollectorRuntime {
  plane: AlphaRadarActivityPlane;
  label: string;
  intervalMs: number;
  enabled: boolean;
  busy: boolean;
  lastStartedAt?: string;
  lastCompletedAt?: string;
  nextRunAt?: string;
  lastStatus?: 'ok' | 'partial' | 'error';
  lastMessage?: string;
  lastCreatedCount?: number;
  lastErrorCount?: number;
}

export interface AlphaRadarSourceHealth {
  source: string;
  kind: 'market' | 'external';
  sourceType?: AlphaRadarSourceType;
  sourceLayer?: AlphaRadarSourceLayer;
  sourceClass?: AlphaRadarSourceClass;
  sourceWeight?: number;
  lastObservedAt?: string;
  ageMs?: number;
  stale: boolean;
  itemCount: number;
  status: 'fresh' | 'stale' | 'inactive';
  details?: Record<string, unknown>;
}

export interface AlphaRadarLiveResponse {
  ok: boolean;
  openPositions: LivePosition[];
  pendingConfirmations: LivePosition[];
  monitoring: {
    autoCollectEnabled: boolean;
    marketSnapshotIntervalMs: number;
    externalFeedsIntervalMs: number;
    collectors: AlphaRadarCollectorRuntime[];
    events: AlphaRadarActivityEvent[];
    sourceHealth?: AlphaRadarSourceHealth[];
    monitoringOnlyAssets?: string[];
    llmMode: 'on_demand';
  };
}

export interface AlphaRadarObservation {
  id: string;
  kind: AlphaRadarObservationKind;
  source: string;
  sourceType: AlphaRadarSourceType;
  sourceLayer?: AlphaRadarSourceLayer;
  sourceClass?: AlphaRadarSourceClass;
  sourceWeight?: number;
  title: string;
  excerpt: string;
  assetTags: string[];
  topicTags: string[];
  sentimentScore?: number;
  noveltyScore?: number;
  urgencyScore?: number;
  marketAlignmentScore?: number;
  rank: number;
  observedAt: string;
  cycleId?: string;
  runId?: string;
  timeframe?: string;
  provenance?: AlphaRadarProvenance;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

export interface AlphaRadarSnapshotResponse {
  ok: boolean;
  observations: AlphaRadarObservation[];
  settings?: AlphaRadarSettings;
  connectorRuntimes?: AlphaRadarConnectorRuntimeSummary[];
  summary: {
    total: number;
    external: number;
    market: number;
    topAssets: Array<{ asset: string; count: number }>;
    monitoringOnlyAssets?: string[];
  };
}

export type EvidenceBundleStatus = 'active' | 'merged' | 'expired';

/**
 * Durable evidence bundle: one or more AlphaRadar observations clustered around the same
 * underlying news event (matched by exact hash, canonical URL, or fuzzy title), used as the
 * upstream record for SignalCandidate promotion. EvidenceBundles are append-only — when a
 * later observation matches an existing bundle, it is appended to `observationIds` and the
 * dedupe counters are incremented.
 */
export interface EvidenceBundle {
  id: string;
  /** Stable cluster key (canonicalUrl or normalized title) used for dedupe lookup. */
  clusterKey: string;
  /** Exact-match hash for the canonical payload (if known). */
  payloadHash?: string;
  /** Canonical URL of the underlying event (best one across observations). */
  canonicalUrl?: string;
  /** Best title across all observations in the cluster. */
  title: string;
  /** Best short excerpt across all observations. */
  excerpt: string;
  /** Asset tags merged from all observations. */
  assetTags: string[];
  /** Topic tags merged from all observations. */
  topicTags: string[];
  /** Distinct source identifiers that contributed to this bundle. */
  sources: string[];
  /** Distinct source classes (official, newswire, social, …) that contributed. */
  sourceClasses: AlphaRadarSourceClass[];
  /** Distinct source layers (primary, duplicate, narrative). */
  sourceLayers: AlphaRadarSourceLayer[];
  /** Observation ids in this bundle (most-recent last). */
  observationIds: string[];
  /** Source-supplied external ids/guids merged into this bundle. */
  externalIds: string[];
  /** Observations matched by exact hash. */
  exactMatchCount: number;
  /** Observations matched by canonical URL. */
  canonicalUrlMatchCount: number;
  /** Observations matched by source-supplied external id. */
  externalIdMatchCount: number;
  /** Observations matched by fuzzy title similarity (no hash/url overlap). */
  fuzzyMatchCount: number;
  /** Observations rejected as duplicates (exact match within suppression window). */
  duplicateSuppressedCount: number;
  /** When the cluster was first formed. */
  firstObservedAt: string;
  /** Most recent observation timestamp. */
  lastObservedAt: string;
  status: EvidenceBundleStatus;
  /** If status is 'merged', the bundle id this one was folded into. */
  mergedIntoId?: string;
  /** If status is 'expired', the reason (e.g. 'staleness', 'pruned'). */
  expiredReason?: string;
  /** Optional NLP/sentiment enrichment — adapter-driven, fail-safe with deterministic fallback. */
  enrichment?: EvidenceBundleEnrichment;
  createdAt: string;
  updatedAt: string;
}

/** Adapter-driven enrichment kept on the bundle. Always optional and never blocking. */
export interface EvidenceBundleEnrichment {
  /** Sentiment score in [-1, 1] (positive = bullish, negative = bearish). */
  sentimentScore?: number;
  /** Confidence the score should be trusted, in [0, 1]. */
  sentimentConfidence?: number;
  /** Adapter that produced the score (e.g. 'lexicon-fallback', 'finbert', 'manual'). */
  sentimentAdapter?: string;
  /** Human-readable label inferred from the score. */
  sentimentLabel?: 'bearish' | 'neutral' | 'bullish';
  /** Named entity recognition hits (tickers, organizations, locations). */
  namedEntities?: Array<{ type: 'ticker' | 'org' | 'person' | 'location' | 'event'; value: string }>;
  /** Adapter that produced the NER hits. */
  nerAdapter?: string;
  /** Whether enrichment used the deterministic fallback path. */
  usedFallback: boolean;
  /** Last enrichment attempt timestamp. */
  computedAt: string;
}

/**
 * SignalCandidate state machine. Drives the lifecycle of a tradable candidate
 * derived from an EvidenceBundle. States are intentionally narrow:
 *
 *   new → validated → actionable → routed → executed
 *           │             │
 *           ↓             ↓
 *       expired        rejected
 *           │             │
 *           └────► postmortem_ready
 */
export type SignalCandidateState =
  | 'new'
  | 'validated'
  | 'actionable'
  | 'routed'
  | 'executed'
  | 'expired'
  | 'rejected'
  | 'postmortem_ready';

export interface SignalCandidateScoringFactors {
  /** Topical/asset relevance to monitored Trading Rules symbols (0..1). */
  relevance: number;
  /** Novelty vs. recently-seen evidence bundles (0..1, 1 = brand new). */
  novelty: number;
  /** Reliability of contributing sources (0..1). */
  sourceReliability: number;
  /** Severity of the underlying event (regulatory, security, listing, …) (0..1). */
  eventSeverity: number;
  /** Time decay factor — how recent the freshest observation is (0..1). */
  timeDecay: number;
  /** Live-market confirmation (price/volume/structure aligns) (0..1). */
  marketConfirmation: number;
  /** Executability — whether the symbol is monitored, sized, and not blocked (0..1). */
  executionability: number;
}

export interface SignalCandidateScore {
  factors: SignalCandidateScoringFactors;
  /** Composite score in [0, 100], computed from factors via deterministic weights. */
  composite: number;
  /** Weights used to compose the score, kept on the candidate for auditability. */
  weights: SignalCandidateScoringFactors;
}

export interface SignalCandidateStateTransition {
  from: SignalCandidateState;
  to: SignalCandidateState;
  reason: string;
  at: string;
  /** Optional pointer to the radar signal record this transition produced. */
  radarSignalId?: string;
  /** Optional pointer to the pending confirmation produced. */
  pendingId?: string;
  /** Optional pointer to the placed order id. */
  orderId?: string;
}

export interface SignalCandidate {
  id: string;
  /** EvidenceBundle this candidate was derived from. */
  evidenceBundleId: string;
  symbol: string;
  side: 'buy' | 'sell';
  state: SignalCandidateState;
  /** When this candidate stops being eligible for promotion (ISO timestamp). */
  expiresAt?: string;
  /** Why the candidate is in its current state (last transition reason). */
  stateReason?: string;
  /** Full transition history — append-only. */
  transitions: SignalCandidateStateTransition[];
  /** Latest scoring snapshot (recomputed on transitions). */
  score?: SignalCandidateScore;
  /** Reference to the radar signal record once the candidate routes to handoff. */
  radarSignalId?: string;
  /** Pending confirmation id if manual queue. */
  pendingId?: string;
  /** Order id if auto-routed. */
  orderId?: string;
  /** Final outcome string for postmortem ('filled', 'tp_hit', 'sl_hit', 'rejected', 'manual_dismiss'). */
  outcome?: string;
  /** Free-text postmortem notes — only present once state === 'postmortem_ready'. */
  postmortemNotes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface AlphaRadarPerpContext {
  symbol: string;
  asOf: string;
  fundingRate8h?: number;
  openInterestUsd?: number;
  volume24hUsd?: number;
}

export interface AlphaRadarIdea {
  id: string;
  evidenceBundleId?: string;
  signalCandidateId?: string;
  signalCandidateState?: SignalCandidateState;
  durableScore?: SignalCandidateScore;
  symbol?: string;
  direction?: TradeSide;
  score: number;
  observationQualityScore?: number;
  tradeActionabilityScore?: number;
  verdict: 'idea' | 'watch_breakout' | 'cash';
  signalFamily: 'catalyst' | 'expansion' | 'rotation' | 'cash';
  actionability: {
    actionable: boolean;
    summary: string;
    blockers: string[];
  };
  title: string;
  whyNow: string[];
  trigger?: number;
  invalidation?: number;
  targets: number[];
  expectedRr?: number;
  rotationAction: 'rotate' | 'keep' | 'cash';
  rotationSummary: string;
  thesis: string;
  assetTags: string[];
  topicTags: string[];
  supportingObservationIds: string[];
  supportingObservationTitles: string[];
  primarySource?: string;
  marketStructure?: {
    regime: 'trend' | 'range' | 'chop' | 'thin';
    windowChangePct?: number;
    latestMovePct?: number;
    rangePosition?: number;
    trendEfficiency?: number;
    structureAlignmentScore?: number;
    structureMetrics?: Record<string, unknown>;
  };
  confirmation?: {
    sourceCount: number;
    sourceTypeCount: number;
    layerCount: number;
    sourceClassCount: number;
    primaryCount: number;
    crossTypeConfirmed: boolean;
    crossLayerConfirmed: boolean;
    crossClassConfirmed: boolean;
    sourceTypes: AlphaRadarSourceType[];
    sourceLayers: AlphaRadarSourceLayer[];
    sourceClasses: AlphaRadarSourceClass[];
  };
  actionabilityInputs?: {
    fundingRate8h?: number;
    openInterestUsd?: number;
    volume24hUsd?: number;
    liquidityScore?: number;
    crowdingScore?: number;
    actionabilityBias?: number;
    notes: string[];
  };
  rotationContext?: {
    openRiskCount: number;
    weakestOpenSymbol?: string;
    weakestOpenUnrealizedPnlPct?: number;
    rotationEdgeScore?: number;
  };
  hypothesisVersion?: string;
  warnings: string[];
  asOf: string;
}

export interface AlphaRadarIdeasResponse {
  ok: boolean;
  settings: AlphaRadarSettings;
  connectorRuntimes?: AlphaRadarConnectorRuntimeSummary[];
  ideas: AlphaRadarIdea[];
  marketSummary: {
    trackedAssets: number;
    monitoringOnlyAssets?: string[];
    openPositions: number;
    strongestObservation?: string;
    evidenceBundles?: number;
    signalCandidates?: number;
    dedupeSuppressed?: number;
    radarContextPolicies?: number;
    activeRadarContextPolicies?: number;
    lockedRadarContextPolicies?: number;
    expiredRadarContextPolicies?: number;
    policyAcceptedEntries?: number;
    policyBlockedEntries?: number;
    sourceHealth?: AlphaRadarSourceHealth[];
    llmMode?: 'on_demand';
  };
}

export interface AlphaRadarSettingsResponse {
  ok: boolean;
  settings: AlphaRadarSettings;
}

export interface HistoryResponse {
  closedPositions: Position[];
  logs: TradeLog[];
  events: TradeEvent[];
  stats: Stats;
}

export interface LiveFill {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  sourceExchange?: string;
  direction?: string;
  price: number;
  size: number;
  feeUsd?: number;
  closedPnlUsd?: number;
  timestamp: string;
}

export interface LiveHistoryResponse {
  fills: LiveFill[];
}

export interface AnalyticsQualityMetrics {
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

export interface PostTradeAnalyticsItem {
  id: string;
  symbol: string;
  source: string;
  side: TradeSide;
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

export interface PostTradeAnalyticsResponse {
  ok: boolean;
  hours: number;
  items: PostTradeAnalyticsItem[];
}

export interface AnalyticsWeeklyReportResponse {
  ok: boolean;
  text: string;
  summary: AnalyticsQualityMetrics & {
    bySource: Array<{ source: string; fills: number; realized: number; fees: number; net: number }>;
    bySymbol: Array<{ symbol: string; realized: number; fills: number }>;
  };
}

export interface LiveCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface LiveCandlesResponse {
  symbol: string;
  timeframe: '1m' | '5m' | '15m' | '1h' | '4h';
  candles: LiveCandle[];
}

export interface LivePositionLevelsPayload {
  symbol: string;
  side: TradeSide;
  size: number;
  stopLoss: number;
  takeProfit?: number;
  takeProfits?: number[];
  confirm?: boolean;
}

export interface LivePositionLevelsResponse {
  ok: boolean;
  symbol: string;
  side: TradeSide;
  size: number;
  stopLoss: number;
  takeProfit: number;
  takeProfits: number[];
  cancelAllResult?: {
    ok: boolean;
    error?: string;
  };
  stopLossOrder?: {
    ok: boolean;
    orderId?: string;
    error?: string;
  };
  takeProfitOrder?: {
    ok: boolean;
    orderId?: string;
    error?: string;
  };
  takeProfitOrders?: Array<{
    ok: boolean;
    orderId?: string;
    error?: string;
  }>;
  error?: string;
}

export interface MaskedBybitConnectionSettings {
  mode: ExchangeConnectionMode;
  hasApiKey: boolean;
  apiKeyMasked: string;
  hasApiSecret: boolean;
  apiSecretMasked: string;
  accountType: 'UNIFIED' | 'CONTRACT' | 'SPOT';
  categories: Array<'linear' | 'inverse' | 'spot' | 'option'>;
}

export interface ExchangeConnectionStatus {
  exchange: 'bybit' | string;
  mode: ExchangeConnectionMode;
  configured: boolean;
  connected: boolean;
  /** true = currently only reading data, not executing orders */
  readOnly: boolean;
  message?: string;
  account?: LiveAccountSummary | null;
}

/** @deprecated use ExchangeConnectionStatus */
export type ReadOnlyExchangeStatus = ExchangeConnectionStatus;

export interface ExchangeSettingsResponse {
  exchange: string;
  connected: boolean;
  accountAddress?: string;
  walletAddress?: string;
  mode: {
    manualConfirmation: boolean;
    maxLeverage: number;
  };
  account: LiveAccountSummary | null;
  capabilities: {
    privateAccount: boolean;
    privateTrading: boolean;
    realtimeMids: boolean;
  };
  hyperliquid?: {
    accountAddress: string;
    apiWalletAddress: string;
    hasPrivateKey: boolean;
    privateKeyMasked: string;
    enabled: boolean;
    tradingConfigured: boolean;
    connected: boolean;
  };
  externalExchanges?: {
    bybit: MaskedBybitConnectionSettings;
  };
  telegramNotify?: {
    hasToken: boolean;
    chatId: string;
    botTokenMasked: string;
    notifyOpen: boolean;
    notifyTp: boolean;
    notifySl: boolean;
    notifyManualConfirm: boolean;
    notifyDailyAnalytics: boolean;
    notifySignalRejected: boolean;
    notifyOrderRejected: boolean;
    notifyPositionClosed: boolean;
  };
  error?: string;
}

export interface ExternalExchangesSettingsResponse {
  ok: boolean;
  exchanges: {
    bybit: MaskedBybitConnectionSettings;
  };
  status: ExchangeConnectionStatus[];
}

/** @deprecated use ExternalExchangesSettingsResponse */
export type ReadOnlyExchangesSettingsResponse = ExternalExchangesSettingsResponse;

export interface TradingRulesSettingsResponse {
  ok: boolean;
  rules: TradingRulesSettings;
}

export interface RadarRuntimeSettingsResponse {
  ok: boolean;
  runtime: RadarRuntimeSettings;
}

export interface TradingRulesSymbolsResponse {
  ok: boolean;
  symbols: string[];
  configuredSymbols?: string[];
  cacheAgeMs?: number | null;
}

export interface ExchangeConnectionSettingsPayload {
  mode?: ExchangeConnectionMode;
  apiKey?: string;
  apiSecret?: string;
  accountType?: 'UNIFIED' | 'CONTRACT' | 'SPOT';
  categories?: Array<'linear' | 'inverse' | 'spot' | 'option'>;
}

/** @deprecated use ExchangeConnectionSettingsPayload */
export type ReadOnlyExchangeSettingsPayload = ExchangeConnectionSettingsPayload;

export interface BiasPayload {
  bias: Bias;
  symbol?: string;
  assetClass?: AssetClass;
  targetType?: 'symbol' | 'class';
}

export interface AiMasterInsight {
  id: string;
  dayKey: string;
  source: 'telegram_daily' | 'manual' | string;
  text: string;
  model?: string;
  promptVersion?: string;
  runId?: string;
  worker?: string;
  status?: 'success' | 'fallback';
  latencyMs?: number;
  timeoutMs?: number;
  promptChars?: number;
  responseChars?: number;
  fallbackUsed?: boolean;
  truncated?: boolean;
  createdAt: string;
}

export type AiMasterQaStatus = 'pending' | 'answered' | 'failed';

export interface AiMasterQaItem {
  id: string;
  question: string;
  answer?: string;
  status: AiMasterQaStatus;
  askedAt: string;
  answeredAt?: string;
  model?: string;
  runId?: string;
  worker?: string;
  latencyMs?: number;
  timeoutMs?: number;
  promptChars?: number;
  responseChars?: number;
  fallbackUsed?: boolean;
  truncated?: boolean;
  error?: string;
}

export interface AiMasterSnapshotResponse {
  ok: boolean;
  insights: AiMasterInsight[];
  qa: AiMasterQaItem[];
}

export type BacktestRunStatus = 'queued' | 'running' | 'completed' | 'failed';
export type BacktestAiAnalysisStatus = 'idle' | 'pending' | 'completed' | 'failed';
export type BacktestBiasMode = 'long' | 'short' | 'both';
export type ComputeJobLifecycleStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface ComputeJobProgress {
  completed: number;
  total: number;
  percent: number;
  stage?: string;
  updatedAt: string;
}

export interface BacktestRunSummary {
  totalTrades: number;
  winRatePct: number;
  realizedPnlUsd: number;
  openPnlUsd: number;
  netPnlUsd: number;
  roiPct: number;
  maxDrawdownPct: number;
  expectancyUsd?: number;
}

export interface BacktestRunSymbolStats {
  symbol: string;
  totalTrades: number;
  wins: number;
  losses: number;
  realizedPnlUsd: number;
  netPnlUsd: number;
  slCount: number;
  tp1Count: number;
  tp2Count: number;
  tp3Count: number;
  emergencyExitCount: number;
  rejectedSignals: number;
}

export interface BacktestRunAiAnalysis {
  status: BacktestAiAnalysisStatus;
  model?: string;
  requestedAt?: string;
  completedAt?: string;
  error?: string;
  summary?: string;
  report?: string;
  recommendations?: string[];
}

export interface ResearchWindowRange {
  startTimeMs: number;
  endTimeMs: number;
}

export interface ResearchCoverage {
  symbols: string[];
  timeframes: TradingRulesTimeframe[];
  window: ResearchWindowRange;
}

export interface RollingWindowSlice {
  index: number;
  train: ResearchWindowRange;
  test: ResearchWindowRange;
  coverage: ResearchCoverage;
}

export interface RollingWindowSchedule {
  anchorTimeMs: number;
  trainWindowMonths: number;
  testWindowMonths: number;
  walkForwardStepMonths: number;
  coverage: ResearchCoverage;
  windows: RollingWindowSlice[];
}

export interface ResearchReplayAssumptions {
  mode: 'no_policy_replay' | 'snapshot_only' | 'deterministic_policy_replay';
  notes: string[];
  policySnapshots: ExecutionIntentPolicySnapshot[];
  contextPolicyIds?: string[];
  capturedAt?: string;
}

export interface ResearchObjectiveMetrics {
  objectiveName: 'net_pnl_usd' | 'roi_pct' | 'expectancy_usd' | 'win_rate_pct' | 'drawdown_adjusted_return';
  objectiveValue: number;
  totalTrades: number;
  winRatePct: number;
  expectancyUsd: number;
  netPnlUsd: number;
  roiPct: number;
  maxDrawdownPct: number;
}

export interface ResearchRejectionStats {
  totalRejectedSignals: number;
  policyBlockedSignals: number;
  sizingRejectedSignals: number;
  riskRejectedSignals: number;
  emergencyExitCount: number;
  stopLossCount: number;
}

export interface BacktestTradeBreakdownItem {
  setup: string;
  timeframe: TradingRulesTimeframe;
  source: string;
  tradeCount: number;
  wins: number;
  losses: number;
  netPnlUsd: number;
}

export interface BacktestLiveDeltaBreakdownItem {
  setup: string;
  timeframe?: TradingRulesTimeframe;
  source: string;
  expectedTrades: number;
  realizedTrades: number;
}

export interface BacktestLiveDeltaReport {
  status: 'available' | 'insufficient_data';
  expectedTradeCount: number;
  realizedTradeCount: number;
  tradeCountDrift: number;
  expectedWinRatePct?: number;
  realizedWinRatePct?: number;
  winRateDriftPct?: number;
  expectedExpectancyUsd?: number;
  realizedExpectancyUsd?: number;
  expectancyDriftUsd?: number;
  expectedMaxDrawdownPct?: number;
  realizedMaxDrawdownPct?: number;
  drawdownDriftPct?: number;
  breakdown: BacktestLiveDeltaBreakdownItem[];
  notes: string[];
  generatedAt: string;
}

export interface QuantStatsReportRecord {
  status: 'pending' | 'completed' | 'failed' | 'unavailable' | 'skipped';
  requestedAt?: string;
  completedAt?: string;
  adapter: 'python_quantstats';
  reason?: string;
  artifactPath?: string;
}

export interface BacktestResearchArtifacts {
  eventCount?: number;
  tradeCount?: number;
  equityCurvePoints?: number;
  tradeBreakdown?: BacktestTradeBreakdownItem[];
}

export interface BacktestRun {
  id: string;
  status: BacktestRunStatus;
  symbol: string;
  biasMode: BacktestBiasMode;
  startedAt?: string;
  finishedAt?: string;
  createdAt: string;
  workerPid?: number;
  workerHeartbeatAt?: string;
  requestedBy?: string;
  startTimeMs: number;
  endTimeMs: number;
  engineVersion: string;
  engineCommit: string;
  marketDataCoverage?: {
    requestedFromMs: number;
    requestedToMs: number;
    loadedFromMs?: number;
    loadedToMs?: number;
  };
  progress?: ComputeJobProgress;
  rulesSnapshot: TradingRulesSettings;
  summary?: BacktestRunSummary;
  bySymbol: BacktestRunSymbolStats[];
  aiAnalysis: BacktestRunAiAnalysis;
  replayAssumptions?: ResearchReplayAssumptions;
  coverage?: ResearchCoverage;
  objectiveMetrics?: ResearchObjectiveMetrics;
  rejectionStats?: ResearchRejectionStats;
  deltaReport?: BacktestLiveDeltaReport;
  quantStatsReport?: QuantStatsReportRecord;
  artifacts?: BacktestResearchArtifacts;
  error?: string;
}

export interface BacktestCreateRunRequest {
  symbol: string;
  biasMode?: BacktestBiasMode;
  startTimeMs: number;
  endTimeMs: number;
  rules?: TradingRulesSettings;
}

export interface BacktestRunResponse {
  ok: boolean;
  run: BacktestRun;
}

export interface BacktestRunListResponse {
  ok: boolean;
  runs: BacktestRun[];
}

export interface BacktestAiAnalysisRequestResponse {
  ok: boolean;
  run: BacktestRun;
}

export interface BacktestAiPendingResponse {
  ok: boolean;
  runs: BacktestRun[];
}

// ─── Optimization ─────────────────────────────────────────────────────

export type OptimizationStatus = ComputeJobLifecycleStatus;

export interface OptimizationParamRange {
  param: string;
  min: number;
  max: number;
  step: number;
}

export interface OptunaPrunerConfig {
  type: 'median' | 'percentile' | 'successive_halving' | 'none';
  warmupSteps: number;
  minCompletedTrials: number;
  percentile?: number;
}

export interface OptunaAdapterRequest {
  storageBackend: 'postgres_rdbstorage';
  studyName: string;
  direction: 'maximize' | 'minimize';
  objectiveName: ResearchObjectiveMetrics['objectiveName'];
  pruner: OptunaPrunerConfig;
  requestedAt: string;
}

export interface OptunaAdapterStatus {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'unavailable' | 'skipped';
  adapter: 'python_optuna';
  checkedAt?: string;
  reason?: string;
  runtime?: {
    pythonExecutable?: string;
    optunaVersion?: string;
    dashboardSupported?: boolean;
  };
}

export interface ExperimentTrialWindowResult {
  windowIndex: number;
  train: ResearchWindowRange;
  test: ResearchWindowRange;
  metrics: ResearchObjectiveMetrics;
  rejectionStats: ResearchRejectionStats;
  summary: BacktestRunSummary;
}

export type ExperimentTrialStatus = 'queued' | 'running' | 'completed' | 'failed' | 'pruned' | 'skipped';

export interface ExperimentTrial {
  schemaVersion: 'experiment_trial_v1';
  id: string;
  experimentId: string;
  optimizationResultId?: string;
  sourceRunId?: string;
  status: ExperimentTrialStatus;
  trialNumber: number;
  parameterValues: Partial<TradingRulesSettings>;
  rulesSnapshot: TradingRulesSettings;
  replayAssumptions: ResearchReplayAssumptions;
  coverage: ResearchCoverage;
  objectiveMetrics?: ResearchObjectiveMetrics;
  rejectionStats?: ResearchRejectionStats;
  summary?: BacktestRunSummary;
  bySymbol?: BacktestRunSymbolStats[];
  tradeBreakdown?: BacktestTradeBreakdownItem[];
  deltaReport?: BacktestLiveDeltaReport;
  quantStatsReport?: QuantStatsReportRecord;
  optunaRequest?: OptunaAdapterRequest;
  optunaStatus?: OptunaAdapterStatus;
  prunerDecision?: {
    status: 'kept' | 'early_pruned';
    reason?: string;
    decidedAt?: string;
    afterWindowIndex?: number;
  };
  windowResults?: ExperimentTrialWindowResult[];
  engineVersion: string;
  engineCommit: string;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  error?: string;
}

export interface ExperimentAcceptanceCriteria {
  minTrades?: number;
  minExpectancyUsd?: number;
  minWinRatePct?: number;
  maxDrawdownPct?: number;
  maxOutOfSampleWindowsWithNegativePnl?: number;
}

export interface Experiment {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'promoted';
  name: string;
  sourceRunId?: string;
  optimizationResultId?: string;
  rulesSnapshot: TradingRulesSettings;
  replayAssumptions: ResearchReplayAssumptions;
  schedule: RollingWindowSchedule;
  coverage: ResearchCoverage;
  objectiveName: ResearchObjectiveMetrics['objectiveName'];
  acceptanceCriteria: ExperimentAcceptanceCriteria;
  trialIds: string[];
  candidateTrialId?: string;
  championConfigId?: string;
  engineVersion: string;
  engineCommit: string;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  requestedBy?: string;
  error?: string;
}

export interface ChampionEvidenceReference {
  type: 'experiment' | 'trial' | 'backtest_run' | 'optimization_result' | 'report';
  id: string;
}

export interface ChampionConfig {
  id: string;
  status: 'candidate' | 'active' | 'replaced' | 'rolled_back' | 'rejected';
  experimentId: string;
  trialId: string;
  rulesSnapshot: TradingRulesSettings;
  replayAssumptions: ResearchReplayAssumptions;
  objectiveMetrics: ResearchObjectiveMetrics;
  deltaReport?: BacktestLiveDeltaReport;
  acceptanceCriteria: ExperimentAcceptanceCriteria;
  acceptancePassed: boolean;
  evidence: ChampionEvidenceReference[];
  engineVersion: string;
  engineCommit: string;
  createdAt: string;
  promotedAt?: string;
  promotedBy?: string;
  replacedChampionId?: string;
  replacedByChampionId?: string;
  rollbackOfChampionId?: string;
  notes?: string[];
}

export interface OptimizationResult {
  id: string;
  status: OptimizationStatus;
  sourceRunId: string;
  experimentId?: string;
  symbol: string;
  biasMode: BacktestBiasMode;
  startTimeMs: number;
  endTimeMs: number;
  baseRulesSnapshot: TradingRulesSettings;
  paramRanges: OptimizationParamRange[];
  rollingWindowSchedule?: RollingWindowSchedule;
  replayAssumptions?: ResearchReplayAssumptions;
  acceptanceCriteria?: ExperimentAcceptanceCriteria;
  objectiveName?: ResearchObjectiveMetrics['objectiveName'];
  optunaRequest?: OptunaAdapterRequest;
  optunaStatus?: OptunaAdapterStatus;
  quantStatsReport?: QuantStatsReportRecord;
  trialIds?: string[];
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  workerPid?: number;
  workerHeartbeatAt?: string;
  progress?: ComputeJobProgress;
  searchSpaceCandidates: number;
  totalCandidates: number;
  evaluatedCandidates: number;
  prunedCandidates?: number;
  bestParams?: Partial<TradingRulesSettings>;
  bestSummary?: BacktestRunSummary;
  bestBySymbol?: BacktestRunSymbolStats[];
  bestTrialId?: string;
  bestObjectiveMetrics?: ResearchObjectiveMetrics;
  error?: string;
  engineVersion: string;
  engineCommit: string;
}

export interface OptimizationCreateRequest {
  sourceRunId: string;
  paramRanges: OptimizationParamRange[];
}

export interface OptimizationResponse {
  ok: boolean;
  optimization: OptimizationResult;
}

export interface OptimizationListResponse {
  ok: boolean;
  optimizations: OptimizationResult[];
}

export interface OptimizationStatusResponse {
  ok: boolean;
  optimization: OptimizationResult;
  blockedByBacktestId?: string | null;
  blockedByBacktestSymbol?: string | null;
  blockedByBacktestStatus?: string | null;
}
