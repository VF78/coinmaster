import type { AiMasterInsight, AiMasterQaItem, AlphaRadarObservation, AppSettings, BacktestRun, BiasCommand, ChampionConfig, DailyDDBaseline, EvidenceBundle, ExecutionIntent, Experiment, ExperimentTrial, MarketTick, OptimizationResult, PendingConfirmation, Position, RadarContextPolicy, RadarSignalRecord, RiskGateAuditEntry, SignalCandidate, TelegramOutboxItem, TradeEvent, TradeLog } from '../shared/dto.js';

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
  experiments: Experiment[];
  experimentTrials: ExperimentTrial[];
  championConfigs: ChampionConfig[];
  radarSignals: RadarSignalRecord[];
  alphaRadarObservations: AlphaRadarObservation[];
  evidenceBundles: EvidenceBundle[];
  signalCandidates: SignalCandidate[];
  radarContextPolicies: RadarContextPolicy[];
  executionIntents: ExecutionIntent[];
}
