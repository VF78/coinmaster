import type { AppSettings, BiasCommand, MarketTick, Position, Stats, TradeLog } from '../shared/dto.js';

export type {
  AppSettings,
  Bias,
  PositionStatus,
  Position,
  TradeLog,
  BiasCommand,
  MarketTick,
  Stats,
  StatsPeriod
} from '../shared/dto.js';

export interface DBShape {
  settings: AppSettings;
  positions: Position[];
  tradeLogs: TradeLog[];
  biasCommands: BiasCommand[];
  marketTicks: MarketTick[];
}
