export type Bias = 'long' | 'short' | 'off';
export type TradeSide = 'long' | 'short';
export type PositionStatus = 'open' | 'closed';
export type StatsPeriod = 'week' | 'month';

export type TradingRulesTimeframe = '5m' | '15m' | '1h' | '4h';
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
}

export interface RiskGateAuditEntry {
  timestamp: string;
  gate: 'daily_dd' | 'leverage_cap' | 'auth' | 'symbol_allowlist' | 'allocation_cap' | 'allocation_sizing' | 'tp_sl_defaults' | 'market_data' | 'multi_tf_engulfing' | 'engulfing_entry_signal' | 'engulfing_emergency_exit' | 'fvg_entry_signal' | 'radar_entry_signal' | 'tp_fill_monitor' | 'partial_close' | 'break_even_sl_after_partial';
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
  createdAt: string;
}

export type RadarSignalStatus = 'pending_confirmation' | 'auto_order_placed' | 'rejected' | 'ignored';

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
  error?: string;
  duplicateOf?: string;
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

export interface RadarSignalsResponse {
  ok: boolean;
  signals: RadarSignalRecord[];
  summary: {
    total: number;
    pendingConfirmation: number;
    autoOrderPlaced: number;
    rejected: number;
    ignored: number;
    bySource: Array<{ source: string; count: number }>;
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

export interface BacktestRunSummary {
  totalTrades: number;
  winRatePct: number;
  realizedPnlUsd: number;
  openPnlUsd: number;
  netPnlUsd: number;
  roiPct: number;
  maxDrawdownPct: number;
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

export interface BacktestRun {
  id: string;
  status: BacktestRunStatus;
  symbol: string;
  biasMode: BacktestBiasMode;
  startedAt?: string;
  finishedAt?: string;
  createdAt: string;
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
  rulesSnapshot: TradingRulesSettings;
  summary?: BacktestRunSummary;
  bySymbol: BacktestRunSymbolStats[];
  aiAnalysis: BacktestRunAiAnalysis;
  artifacts?: {
    eventCount?: number;
    tradeCount?: number;
    equityCurvePoints?: number;
  };
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

export type OptimizationStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface OptimizationParamRange {
  param: string;
  min: number;
  max: number;
  step: number;
}

export interface OptimizationResult {
  id: string;
  status: OptimizationStatus;
  sourceRunId: string;
  symbol: string;
  biasMode: BacktestBiasMode;
  startTimeMs: number;
  endTimeMs: number;
  baseRulesSnapshot: TradingRulesSettings;
  paramRanges: OptimizationParamRange[];
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  workerPid?: number;
  workerHeartbeatAt?: string;
  searchSpaceCandidates: number;
  totalCandidates: number;
  evaluatedCandidates: number;
  bestParams?: Partial<TradingRulesSettings>;
  bestSummary?: BacktestRunSummary;
  bestBySymbol?: BacktestRunSymbolStats[];
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
