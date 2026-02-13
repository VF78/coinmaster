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
  openedAt: string;
  closedAt?: string;
  status: PositionStatus;
  pnl: number;
  source: 'manual' | 'sim';
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

export interface DashboardResponse {
  activePositions: Position[];
  latestBias: Bias;
  stats: Stats;
  latestTick: MarketTick | null;
}

export interface HistoryResponse {
  closedPositions: Position[];
  logs: TradeLog[];
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
