export type Bias = 'long' | 'short' | 'off';

export type PositionStatus = 'open' | 'closed';

export interface Position {
  id: string;
  symbol: string;
  side: 'long' | 'short';
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
  side?: 'long' | 'short';
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

export interface Stats {
  totalTrades: number;
  winRate: number;
  realizedPnl: number;
  openPnl: number;
  avgPnl: number;
}

export interface DBShape {
  positions: Position[];
  tradeLogs: TradeLog[];
  biasCommands: BiasCommand[];
  marketTicks: { symbol: string; price: number; timestamp: string }[];
}
