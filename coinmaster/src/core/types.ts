import type { AiMasterInsight, AiMasterQaItem, AlphaRadarObservation, AppSettings, BacktestRun, BiasCommand, DailyDDBaseline, MarketTick, OptimizationResult, PendingConfirmation, Position, RadarSignalRecord, RiskGateAuditEntry, TelegramOutboxItem, TradeEvent, TradeLog } from '../shared/dto.js';

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
  pendingConfirmations: PendingConfirmation[];
  telegramOutbox: TelegramOutboxItem[];
  aiMasterInsights: AiMasterInsight[];
  aiMasterQa: AiMasterQaItem[];
  backtestRuns: BacktestRun[];
  optimizationResults: OptimizationResult[];
  radarSignals: RadarSignalRecord[];
  alphaRadarObservations: AlphaRadarObservation[];
}
