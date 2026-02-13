import type { AppSettings, BiasCommand, MarketTick, Position, Stats, TradeEvent, TradeEventPayload, TradeEventSource, TradeEventType, TradeLog } from '../shared/dto.js';

export type {
  AppSettings,
  Bias,
  PositionStatus,
  Position,
  TradeLog,
  TradeEvent,
  TradeEventType,
  TradeEventSource,
  TradeEventPayload,
  BiasCommand,
  MarketTick,
  Stats,
  StatsPeriod
} from '../shared/dto.js';

export interface DBShape {
  settings: AppSettings;
  positions: Position[];
  tradeLogs: TradeLog[];
  tradeEvents: TradeEvent[];
  biasCommands: BiasCommand[];
  marketTicks: MarketTick[];
}
