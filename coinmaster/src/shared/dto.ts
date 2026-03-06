export type Bias = 'long' | 'short' | 'off';
export type TradeSide = 'long' | 'short';
export type PositionStatus = 'open' | 'closed';
export type StatsPeriod = 'week' | 'month';

export type TradingRulesTimeframe = '5m' | '15m' | '1h' | '4h';
export type AssetClass = 'crypto' | 'commodity' | 'forex' | 'index' | 'other';
export type BiasMode = 'global' | 'symbol';

export interface BiasPolicySymbolOverride {
  mode: BiasMode;
  /** Optional pinned bias for this symbol. If omitted and mode=symbol, runtime reads symbol bias command; missing command => off. */
  bias?: Bias;
}

export interface BiasPolicySettings {
  classDefaults: Record<AssetClass, BiasMode>;
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
  updateOffset?: number;
}

export interface TelegramOutboxItem {
  id: string;
  category: 'manual_confirm' | 'trade_open' | 'tp' | 'sl' | 'analytics_daily' | 'system';
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

export interface AppSettings {
  depositUsd: number;
  tradingRules: TradingRulesSettings;
  telegramNotify?: TelegramNotifySettings;
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
  | 'position_closed';

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
  gate: 'daily_dd' | 'leverage_cap' | 'auth' | 'symbol_allowlist' | 'allocation_cap' | 'allocation_sizing' | 'tp_sl_defaults' | 'market_data' | 'multi_tf_engulfing' | 'engulfing_entry_signal' | 'engulfing_emergency_exit' | 'fvg_entry_signal' | 'tp_fill_monitor' | 'partial_close' | 'break_even_sl_after_partial';
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
  strategy: 'engulfing' | 'fvg';
  timeframe: TradingRulesTimeframe;
  reason: string;
  price: number;
  size: number;
  leverage: number;
  createdAt: string;
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
  openPositions: LivePosition[];
  pendingConfirmations: LivePosition[];
  error?: string;
}

export interface DashboardBiasControl {
  symbol: string;
  assetClass: AssetClass;
  mode: 'global' | 'custom';
  bias: Bias;
}

export interface DashboardResponse {
  latestBias: Bias;
  /** Current shared/global bias used by assets configured with mode=global. */
  globalBias: Bias;
  latestTick: MarketTick | null;
  live: LiveDashboardState;
  biasControls: DashboardBiasControl[];
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
  };
  error?: string;
}

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

export interface BiasPayload {
  symbol: string;
  bias: Bias;
}
