export type Bias = 'long' | 'short' | 'off';
export type TradeSide = 'long' | 'short';
export type PositionStatus = 'open' | 'closed';
export type StatsPeriod = 'week' | 'month';

export interface AppSettings {
  depositUsd: number;
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
}

export interface LivePosition {
  id: string;
  symbol: string;
  side: TradeSide;
  size: number;
  entryPrice?: number;
  leverage?: number;
  unrealizedPnl?: number;
}

export interface LiveDashboardState {
  connected: boolean;
  mode: {
    manualConfirmation: boolean;
    maxNotionalUsdc: number;
    maxLeverage: number;
  };
  account: LiveAccountSummary | null;
  openOrders: number;
  openPositions: LivePosition[];
  error?: string;
}

export interface DashboardResponse {
  activePositions: Position[];
  latestBias: Bias;
  stats: Stats;
  latestTick: MarketTick | null;
  live: LiveDashboardState;
}

export interface HistoryResponse {
  closedPositions: Position[];
  logs: TradeLog[];
  events: TradeEvent[];
  stats: Stats;
}

export interface BiasPayload {
  symbol: string;
  bias: Bias;
}

export interface SimulateTickPayload {
  symbol?: string;
  price: number;
}
