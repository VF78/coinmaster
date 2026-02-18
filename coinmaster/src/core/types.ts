import type { AppSettings, BiasCommand, DailyDDBaseline, MarketTick, Position, RiskGateAuditEntry, TradeEvent, TradeLog } from '../shared/dto.js';

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
  StatsPeriod,
  DailyDDBaseline,
  RiskGateAuditEntry
} from '../shared/dto.js';

export interface DBShape {
  settings: AppSettings;
  positions: Position[];
  tradeLogs: TradeLog[];
  tradeEvents: TradeEvent[];
  biasCommands: BiasCommand[];
  marketTicks: MarketTick[];
  dailyDDBaselines: DailyDDBaseline[];
  riskGateAudit: RiskGateAuditEntry[];
}
