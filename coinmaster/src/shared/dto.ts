export type Bias = 'long' | 'short' | 'off';

export type TradeSide = 'long' | 'short';

export type PositionStatus = 'open' | 'closed';

export interface Position {
  id: string;
  symbol: string;
  side: TradeSide;
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  size: number;
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
  action: 'open' | 'close' | 'bias';
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
  totalTrades: number;
  winRate: number;
  realizedPnl: number;
  openPnl: number;
  avgPnl: number;
}

export interface DashboardResponse {
  activePositions: Position[];
  latestBias: Bias;
  stats: Stats;
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
