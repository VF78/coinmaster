import type { BiasCommand, MarketTick, Position, Stats, TradeLog } from '../shared/dto.js';

export type { Bias, PositionStatus, Position, TradeLog, BiasCommand, MarketTick, Stats } from '../shared/dto.js';

export interface DBShape {
  positions: Position[];
  tradeLogs: TradeLog[];
  biasCommands: BiasCommand[];
  marketTicks: MarketTick[];
}
