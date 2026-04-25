import { spawnSync } from 'node:child_process';
import { nanoid } from 'nanoid';
import type {
  BacktestLiveDeltaReport,
  BacktestRun,
  BacktestRunSummary,
  BacktestRunSymbolStats,
  BacktestTradeBreakdownItem,
  ChampionConfig,
  ExecutionIntent,
  Experiment,
  ExperimentAcceptanceCriteria,
  ExperimentTrial,
  ExperimentTrialWindowResult,
  OptunaAdapterRequest,
  OptunaAdapterStatus,
  OptunaPrunerConfig,
  Position,
  QuantStatsReportRecord,
  ResearchCoverage,
  ResearchObjectiveMetrics,
  ResearchReplayAssumptions,
  ResearchRejectionStats,
  RollingWindowSchedule,
  RollingWindowSlice,
  TradingRulesSettings,
  TradingRulesTimeframe,
} from '../shared/dto.js';
import type { DBShape } from './types.js';
import { getRequiredComputeTimeframes } from './computeJob.js';

interface BacktestTradeLike {
  positionId: string;
  action: 'open' | 'partial' | 'close';
  reason: string;
  pnl: number;
}

const DEFAULT_ACCEPTANCE: ExperimentAcceptanceCriteria = {
  minTrades: 10,
  minExpectancyUsd: 0,
  minWinRatePct: 0,
  maxDrawdownPct: 25,
  maxOutOfSampleWindowsWithNegativePnl: 0,
};

const DEFAULT_PRUNER: OptunaPrunerConfig = {
  type: 'median',
  warmupSteps: 1,
  minCompletedTrials: 3,
};

function round(value: number, decimals = 2): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function startOfUtcMonth(timeMs: number): number {
  const d = new Date(timeMs);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1, 0, 0, 0, 0);
}

function addUtcMonths(timeMs: number, months: number): number {
  const d = new Date(timeMs);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + months, d.getUTCDate(), d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds(), d.getUTCMilliseconds());
}

function buildCoverage(params: {
  symbol: string;
  rules: TradingRulesSettings;
  startTimeMs: number;
  endTimeMs: number;
}): ResearchCoverage {
  return {
    symbols: [params.symbol],
    timeframes: getRequiredComputeTimeframes(params.rules),
    window: {
      startTimeMs: params.startTimeMs,
      endTimeMs: params.endTimeMs,
    },
  };
}

function parseTradeReason(reason: string): { setup: string; timeframe: TradingRulesTimeframe; source: string } {
  const normalized = String(reason ?? '').trim().toLowerCase();
  if (normalized.startsWith('engulfing_entry_')) {
    const tf = normalized.slice('engulfing_entry_'.length) as TradingRulesTimeframe;
    return { setup: 'engulfing', timeframe: tf, source: 'backtest:engulfing' };
  }
  if (normalized.startsWith('fvg_entry_')) {
    const parts = normalized.split('_');
    const tf = (parts[2] ?? '1h') as TradingRulesTimeframe;
    return { setup: 'fvg', timeframe: tf, source: 'backtest:fvg' };
  }
  return { setup: normalized || 'unknown', timeframe: '15m', source: 'backtest:unknown' };
}

function computeLiveMaxDrawdownPct(positions: Position[]): number | undefined {
  if (positions.length === 0) return undefined;
  let equity = 0;
  let peak = 0;
  let maxDrawdown = 0;
  const ordered = [...positions]
    .filter((position) => position.source === 'live')
    .sort((a, b) => Date.parse(a.closedAt ?? a.openedAt) - Date.parse(b.closedAt ?? b.openedAt));
  for (const position of ordered) {
    equity += Number(position.pnl ?? 0);
    peak = Math.max(peak, equity);
    const drawdown = peak > 0 ? ((peak - equity) / peak) * 100 : 0;
    maxDrawdown = Math.max(maxDrawdown, drawdown);
  }
  return round(maxDrawdown);
}

export function ensureExperimentCollections(db: Pick<DBShape, 'experiments' | 'experimentTrials' | 'championConfigs'>): void {
  db.experiments = Array.isArray(db.experiments) ? db.experiments : [];
  db.experimentTrials = Array.isArray(db.experimentTrials) ? db.experimentTrials : [];
  db.championConfigs = Array.isArray(db.championConfigs) ? db.championConfigs : [];
}

export function buildRollingWindowSchedule(params: {
  symbol: string;
  rules: TradingRulesSettings;
  startTimeMs: number;
  endTimeMs: number;
  trainWindowMonths?: number;
  testWindowMonths?: number;
  walkForwardStepMonths?: number;
}): RollingWindowSchedule {
  const trainWindowMonths = Math.max(1, Math.round(params.trainWindowMonths ?? 3));
  const testWindowMonths = Math.max(1, Math.round(params.testWindowMonths ?? 1));
  const walkForwardStepMonths = Math.max(1, Math.round(params.walkForwardStepMonths ?? 1));
  const anchorTimeMs = startOfUtcMonth(params.startTimeMs);
  const hardEndMs = params.endTimeMs;
  const coverage = buildCoverage(params);
  const windows: RollingWindowSlice[] = [];

  let cursor = anchorTimeMs;
  let index = 0;

  while (true) {
    const trainStart = cursor;
    const trainEnd = addUtcMonths(trainStart, trainWindowMonths);
    const testEnd = addUtcMonths(trainEnd, testWindowMonths);
    if (testEnd > hardEndMs) break;
    windows.push({
      index,
      train: { startTimeMs: trainStart, endTimeMs: trainEnd },
      test: { startTimeMs: trainEnd, endTimeMs: testEnd },
      coverage: {
        ...coverage,
        window: {
          startTimeMs: trainStart,
          endTimeMs: testEnd,
        },
      },
    });
    index += 1;
    cursor = addUtcMonths(cursor, walkForwardStepMonths);
  }

  if (windows.length === 0) {
    windows.push({
      index: 0,
      train: {
        startTimeMs: params.startTimeMs,
        endTimeMs: params.startTimeMs,
      },
      test: {
        startTimeMs: params.startTimeMs,
        endTimeMs: params.endTimeMs,
      },
      coverage,
    });
  }

  return {
    anchorTimeMs,
    trainWindowMonths,
    testWindowMonths,
    walkForwardStepMonths,
    coverage,
    windows,
  };
}

export function buildDefaultReplayAssumptions(): ResearchReplayAssumptions {
  return {
    mode: 'snapshot_only',
    notes: [
      'backtest engine remains canonical',
      'optimizer sidecars do not own live execution state',
      'radar context policy is recorded as deterministic replay assumptions only',
    ],
    policySnapshots: [],
  };
}

export function summarizeBacktestTradeBreakdown(trades: BacktestTradeLike[]): BacktestTradeBreakdownItem[] {
  const positionOpenMeta = new Map<string, ReturnType<typeof parseTradeReason>>();
  const positionNetPnl = new Map<string, number>();

  for (const trade of trades) {
    if (trade.action === 'open') {
      positionOpenMeta.set(trade.positionId, parseTradeReason(trade.reason));
    }
    if (trade.action === 'partial' || trade.action === 'close') {
      positionNetPnl.set(trade.positionId, round((positionNetPnl.get(trade.positionId) ?? 0) + Number(trade.pnl ?? 0)));
    }
  }

  const grouped = new Map<string, BacktestTradeBreakdownItem>();
  for (const [positionId, meta] of positionOpenMeta.entries()) {
    const key = `${meta.setup}|${meta.timeframe}|${meta.source}`;
    const row = grouped.get(key) ?? {
      setup: meta.setup,
      timeframe: meta.timeframe,
      source: meta.source,
      tradeCount: 0,
      wins: 0,
      losses: 0,
      netPnlUsd: 0,
    };
    row.tradeCount += 1;
    const pnl = round(positionNetPnl.get(positionId) ?? 0);
    row.netPnlUsd = round(row.netPnlUsd + pnl);
    if (pnl > 0) row.wins += 1;
    else row.losses += 1;
    grouped.set(key, row);
  }

  return [...grouped.values()].sort((a, b) => a.setup.localeCompare(b.setup) || a.timeframe.localeCompare(b.timeframe));
}

export function buildObjectiveMetrics(summary?: BacktestRunSummary): ResearchObjectiveMetrics | undefined {
  if (!summary) return undefined;
  const expectancyUsd = round(summary.expectancyUsd ?? (summary.totalTrades > 0 ? summary.netPnlUsd / summary.totalTrades : 0));
  return {
    objectiveName: 'net_pnl_usd',
    objectiveValue: round(summary.netPnlUsd),
    totalTrades: summary.totalTrades,
    winRatePct: round(summary.winRatePct),
    expectancyUsd,
    netPnlUsd: round(summary.netPnlUsd),
    roiPct: round(summary.roiPct),
    maxDrawdownPct: round(summary.maxDrawdownPct),
  };
}

export function buildRejectionStats(bySymbol: BacktestRunSymbolStats[]): ResearchRejectionStats {
  const aggregate = bySymbol.reduce((acc, item) => {
    acc.totalRejectedSignals += item.rejectedSignals;
    acc.emergencyExitCount += item.emergencyExitCount;
    acc.stopLossCount += item.slCount;
    return acc;
  }, {
    totalRejectedSignals: 0,
    policyBlockedSignals: 0,
    sizingRejectedSignals: 0,
    riskRejectedSignals: 0,
    emergencyExitCount: 0,
    stopLossCount: 0,
  });

  return aggregate;
}

export function createUnavailableQuantStatsReport(reason: string): QuantStatsReportRecord {
  return {
    status: 'unavailable',
    adapter: 'python_quantstats',
    requestedAt: new Date().toISOString(),
    reason,
  };
}

export function createOptunaRequest(params: {
  experimentId: string;
  objectiveName?: ResearchObjectiveMetrics['objectiveName'];
  pruner?: Partial<OptunaPrunerConfig>;
}): OptunaAdapterRequest {
  return {
    storageBackend: 'postgres_rdbstorage',
    studyName: `coinmaster-exp-${params.experimentId}`,
    direction: 'maximize',
    objectiveName: params.objectiveName ?? 'net_pnl_usd',
    pruner: {
      ...DEFAULT_PRUNER,
      ...params.pruner,
    },
    requestedAt: new Date().toISOString(),
  };
}

export function detectOptunaAvailability(): OptunaAdapterStatus {
  const checkedAt = new Date().toISOString();
  try {
    const probe = spawnSync('python3', ['-c', 'import optuna; print(optuna.__version__)'], {
      encoding: 'utf8',
      timeout: 2_000,
    });
    if (probe.status === 0) {
      return {
        status: 'skipped',
        adapter: 'python_optuna',
        checkedAt,
        reason: 'optuna runtime detected; TS canonical worker recorded durable trial boundary without delegating execution',
        runtime: {
          pythonExecutable: 'python3',
          optunaVersion: String(probe.stdout ?? '').trim() || undefined,
          dashboardSupported: true,
        },
      };
    }
    return {
      status: 'unavailable',
      adapter: 'python_optuna',
      checkedAt,
      reason: String(probe.stderr ?? probe.stdout ?? '').trim() || 'optuna_not_installed',
      runtime: {
        pythonExecutable: 'python3',
      },
    };
  } catch (error) {
    return {
      status: 'unavailable',
      adapter: 'python_optuna',
      checkedAt,
      reason: error instanceof Error ? error.message : 'optuna_probe_failed',
      runtime: {
        pythonExecutable: 'python3',
      },
    };
  }
}

export function buildBacktestLiveDeltaReport(params: {
  coverage: ResearchCoverage;
  backtestSummary?: BacktestRunSummary;
  tradeBreakdown?: BacktestTradeBreakdownItem[];
  livePositions: Position[];
  executionIntents: ExecutionIntent[];
}): BacktestLiveDeltaReport {
  const notes: string[] = [];
  const livePositions = params.livePositions.filter((position) => {
    if (position.source !== 'live') return false;
    if (position.symbol.toUpperCase() !== params.coverage.symbols[0]?.toUpperCase()) return false;
    const timeMs = Date.parse(position.closedAt ?? position.openedAt);
    return Number.isFinite(timeMs)
      && timeMs >= params.coverage.window.startTimeMs
      && timeMs <= params.coverage.window.endTimeMs;
  });

  const realizedTradeCount = livePositions.filter((position) => position.status === 'closed').length;
  const realizedWins = livePositions.filter((position) => position.status === 'closed' && position.pnl > 0).length;
  const realizedWinRatePct = realizedTradeCount > 0 ? round((realizedWins / realizedTradeCount) * 100) : undefined;
  const realizedExpectancyUsd = realizedTradeCount > 0
    ? round(livePositions.filter((position) => position.status === 'closed').reduce((acc, position) => acc + position.pnl, 0) / realizedTradeCount)
    : undefined;
  const realizedMaxDrawdownPct = computeLiveMaxDrawdownPct(livePositions);

  if (livePositions.length === 0) {
    notes.push('no matching live positions were available for the experiment coverage window');
  }

  const intentBreakdownMap = new Map<string, { setup: string; timeframe?: TradingRulesTimeframe; source: string; realizedTrades: number }>();
  for (const intent of params.executionIntents) {
    const timeMs = Date.parse(intent.createdAt);
    if (!Number.isFinite(timeMs)) continue;
    if (timeMs < params.coverage.window.startTimeMs || timeMs > params.coverage.window.endTimeMs) continue;
    if (intent.symbol.toUpperCase() !== params.coverage.symbols[0]?.toUpperCase()) continue;
    const key = `${intent.strategy}|${intent.timeframe}|${intent.sourceLabel}`;
    const row = intentBreakdownMap.get(key) ?? {
      setup: intent.strategy,
      timeframe: intent.timeframe,
      source: intent.sourceLabel,
      realizedTrades: 0,
    };
    if (intent.status === 'auto_order_placed') {
      row.realizedTrades += 1;
    }
    intentBreakdownMap.set(key, row);
  }

  const expectedBreakdown = params.tradeBreakdown ?? [];
  const breakdown = expectedBreakdown.map((item) => {
    const row = [...intentBreakdownMap.values()].find((candidate) => candidate.setup === item.setup && candidate.timeframe === item.timeframe);
    return {
      setup: item.setup,
      timeframe: item.timeframe,
      source: row?.source ?? item.source,
      expectedTrades: item.tradeCount,
      realizedTrades: row?.realizedTrades ?? 0,
    };
  });

  return {
    status: livePositions.length > 0 ? 'available' : 'insufficient_data',
    expectedTradeCount: params.backtestSummary?.totalTrades ?? 0,
    realizedTradeCount,
    tradeCountDrift: realizedTradeCount - (params.backtestSummary?.totalTrades ?? 0),
    expectedWinRatePct: params.backtestSummary?.winRatePct,
    realizedWinRatePct,
    winRateDriftPct: realizedWinRatePct !== undefined && params.backtestSummary?.winRatePct !== undefined
      ? round(realizedWinRatePct - params.backtestSummary.winRatePct)
      : undefined,
    expectedExpectancyUsd: params.backtestSummary?.expectancyUsd,
    realizedExpectancyUsd,
    expectancyDriftUsd: realizedExpectancyUsd !== undefined && params.backtestSummary?.expectancyUsd !== undefined
      ? round(realizedExpectancyUsd - params.backtestSummary.expectancyUsd)
      : undefined,
    expectedMaxDrawdownPct: params.backtestSummary?.maxDrawdownPct,
    realizedMaxDrawdownPct,
    drawdownDriftPct: realizedMaxDrawdownPct !== undefined && params.backtestSummary?.maxDrawdownPct !== undefined
      ? round(realizedMaxDrawdownPct - params.backtestSummary.maxDrawdownPct)
      : undefined,
    breakdown,
    notes,
    generatedAt: new Date().toISOString(),
  };
}

export function createExperimentFromRun(params: {
  sourceRun: BacktestRun;
  optimizationResultId?: string;
  requestedBy?: string;
  acceptanceCriteria?: Partial<ExperimentAcceptanceCriteria>;
}): Experiment {
  const schedule = buildRollingWindowSchedule({
    symbol: params.sourceRun.symbol,
    rules: params.sourceRun.rulesSnapshot,
    startTimeMs: params.sourceRun.startTimeMs,
    endTimeMs: params.sourceRun.endTimeMs,
  });
  const replayAssumptions = params.sourceRun.replayAssumptions ?? buildDefaultReplayAssumptions();

  return {
    id: nanoid(),
    status: 'queued',
    name: `${params.sourceRun.symbol} ${new Date(params.sourceRun.startTimeMs).toISOString().slice(0, 10)}-${new Date(params.sourceRun.endTimeMs).toISOString().slice(0, 10)}`,
    sourceRunId: params.sourceRun.id,
    optimizationResultId: params.optimizationResultId,
    rulesSnapshot: JSON.parse(JSON.stringify(params.sourceRun.rulesSnapshot)),
    replayAssumptions,
    schedule,
    coverage: schedule.coverage,
    objectiveName: 'net_pnl_usd',
    acceptanceCriteria: {
      ...DEFAULT_ACCEPTANCE,
      ...params.acceptanceCriteria,
    },
    trialIds: [],
    engineVersion: params.sourceRun.engineVersion,
    engineCommit: params.sourceRun.engineCommit,
    createdAt: new Date().toISOString(),
    requestedBy: params.requestedBy,
  };
}

export function createExperimentTrial(params: {
  experiment: Experiment;
  optimizationResultId?: string;
  sourceRunId?: string;
  trialNumber: number;
  parameterValues: Partial<TradingRulesSettings>;
  rulesSnapshot: TradingRulesSettings;
  engineVersion: string;
  engineCommit: string;
  optunaRequest?: OptunaAdapterRequest;
  optunaStatus?: OptunaAdapterStatus;
}): ExperimentTrial {
  return {
    schemaVersion: 'experiment_trial_v1',
    id: nanoid(),
    experimentId: params.experiment.id,
    optimizationResultId: params.optimizationResultId,
    sourceRunId: params.sourceRunId,
    status: 'queued',
    trialNumber: params.trialNumber,
    parameterValues: params.parameterValues,
    rulesSnapshot: params.rulesSnapshot,
    replayAssumptions: params.experiment.replayAssumptions,
    coverage: params.experiment.coverage,
    engineVersion: params.engineVersion,
    engineCommit: params.engineCommit,
    createdAt: new Date().toISOString(),
    optunaRequest: params.optunaRequest,
    optunaStatus: params.optunaStatus,
  };
}

export function shouldEarlyPruneTrial(params: {
  acceptanceCriteria: ExperimentAcceptanceCriteria;
  windowResults: ExperimentTrialWindowResult[];
}): { prune: boolean; reason?: string } {
  const latest = params.windowResults[params.windowResults.length - 1];
  if (!latest) return { prune: false };
  if (params.acceptanceCriteria.minExpectancyUsd !== undefined && latest.metrics.expectancyUsd < params.acceptanceCriteria.minExpectancyUsd) {
    return { prune: true, reason: 'expectancy_below_acceptance' };
  }
  if (params.acceptanceCriteria.maxDrawdownPct !== undefined && latest.metrics.maxDrawdownPct > params.acceptanceCriteria.maxDrawdownPct) {
    return { prune: true, reason: 'drawdown_above_acceptance' };
  }
  return { prune: false };
}

export function pickBestTrial(trials: ExperimentTrial[]): ExperimentTrial | undefined {
  return [...trials]
    .filter((trial) => trial.status === 'completed' && trial.objectiveMetrics)
    .sort((a, b) => (b.objectiveMetrics?.objectiveValue ?? -Infinity) - (a.objectiveMetrics?.objectiveValue ?? -Infinity))[0];
}

export function evaluateChampionAcceptance(params: {
  trial: ExperimentTrial;
  experiment: Experiment;
}): { passed: boolean; notes: string[] } {
  const notes: string[] = [];
  const criteria = params.experiment.acceptanceCriteria;
  const metrics = params.trial.objectiveMetrics;
  const windows = params.trial.windowResults ?? [];
  const negativeWindowCount = windows.filter((window) => window.metrics.netPnlUsd < 0).length;

  if (!metrics) {
    notes.push('trial has no objective metrics');
    return { passed: false, notes };
  }
  if (criteria.minTrades !== undefined && metrics.totalTrades < criteria.minTrades) {
    notes.push(`minTrades failed: ${metrics.totalTrades} < ${criteria.minTrades}`);
  }
  if (criteria.minExpectancyUsd !== undefined && metrics.expectancyUsd < criteria.minExpectancyUsd) {
    notes.push(`minExpectancyUsd failed: ${metrics.expectancyUsd} < ${criteria.minExpectancyUsd}`);
  }
  if (criteria.minWinRatePct !== undefined && metrics.winRatePct < criteria.minWinRatePct) {
    notes.push(`minWinRatePct failed: ${metrics.winRatePct} < ${criteria.minWinRatePct}`);
  }
  if (criteria.maxDrawdownPct !== undefined && metrics.maxDrawdownPct > criteria.maxDrawdownPct) {
    notes.push(`maxDrawdownPct failed: ${metrics.maxDrawdownPct} > ${criteria.maxDrawdownPct}`);
  }
  if (criteria.maxOutOfSampleWindowsWithNegativePnl !== undefined && negativeWindowCount > criteria.maxOutOfSampleWindowsWithNegativePnl) {
    notes.push(`negative out-of-sample windows failed: ${negativeWindowCount} > ${criteria.maxOutOfSampleWindowsWithNegativePnl}`);
  }
  return {
    passed: notes.length === 0,
    notes,
  };
}

export function promoteChampionTrial(params: {
  db: DBShape;
  experiment: Experiment;
  trial: ExperimentTrial;
  promotedBy?: string;
}): ChampionConfig {
  ensureExperimentCollections(params.db);
  const activeChampion = params.db.championConfigs.find((item) => item.status === 'active');
  const acceptance = evaluateChampionAcceptance({ trial: params.trial, experiment: params.experiment });
  const now = new Date().toISOString();

  const champion: ChampionConfig = {
    id: nanoid(),
    status: acceptance.passed ? 'active' : 'rejected',
    experimentId: params.experiment.id,
    trialId: params.trial.id,
    rulesSnapshot: JSON.parse(JSON.stringify(params.trial.rulesSnapshot)),
    replayAssumptions: JSON.parse(JSON.stringify(params.trial.replayAssumptions)),
    objectiveMetrics: params.trial.objectiveMetrics ?? {
      objectiveName: 'net_pnl_usd',
      objectiveValue: 0,
      totalTrades: 0,
      winRatePct: 0,
      expectancyUsd: 0,
      netPnlUsd: 0,
      roiPct: 0,
      maxDrawdownPct: 0,
    },
    deltaReport: params.trial.deltaReport,
    acceptanceCriteria: params.experiment.acceptanceCriteria,
    acceptancePassed: acceptance.passed,
    evidence: [
      { type: 'experiment', id: params.experiment.id },
      { type: 'trial', id: params.trial.id },
      ...(params.experiment.sourceRunId ? [{ type: 'backtest_run' as const, id: params.experiment.sourceRunId }] : []),
      ...(params.experiment.optimizationResultId ? [{ type: 'optimization_result' as const, id: params.experiment.optimizationResultId }] : []),
    ],
    engineVersion: params.trial.engineVersion,
    engineCommit: params.trial.engineCommit,
    createdAt: now,
    promotedAt: acceptance.passed ? now : undefined,
    promotedBy: acceptance.passed ? params.promotedBy : undefined,
    replacedChampionId: activeChampion?.id,
    notes: acceptance.notes,
  };

  if (activeChampion && acceptance.passed) {
    activeChampion.status = 'replaced';
    activeChampion.replacedByChampionId = champion.id;
  }

  params.db.championConfigs.unshift(champion);
  params.experiment.candidateTrialId = params.trial.id;
  params.experiment.championConfigId = champion.id;
  params.experiment.status = acceptance.passed ? 'promoted' : params.experiment.status;

  return champion;
}
