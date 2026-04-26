/**
 * optimizerWorker.ts
 *
 * Bounded parameter optimizer for backtest runs.
 * Generates candidate parameter sets from user-specified ranges, evaluates each
 * by running the backtest engine, and picks the best result by net PnL.
 *
 * Design constraints:
 *  - Uses the same canonical backtest engine (zero side-effects).
 *  - Bounded search: computes a finite grid from step sizes, capped at ~5000 candidates.
 *  - Runtime budgeting: yields to event loop between candidates to avoid starving the server.
 *  - Isolation: all state is local; only final result is written to persistence.
 *  - Blocks new backtests while running (reuses the same concurrency model).
 */

import { nanoid } from 'nanoid';
import logger from '../lib/logger.js';
import { getDb } from './db.js';
import { runBacktestEngine, type BacktestCandleSet } from './backtestEngine.js';
import { getBacktestEngineVersion } from './backtest.js';
import {
  computeCandleLoadWindow,
  createComputeJobProgress,
  getRequiredComputeTimeframes,
  markComputeJobCompleted,
  markComputeJobFailed,
  markComputeJobStarted,
  shouldPersistProgress,
  updateComputeJobProgress,
} from './computeJob.js';
import type {
  BacktestRun,
  BacktestRunSummary,
  BacktestRunSymbolStats,
  BacktestTradeBreakdownItem,
  Experiment,
  ExperimentTrial,
  ExperimentTrialWindowResult,
  OptimizationParamRange,
  OptimizationResult,
  TradingRulesSettings,
} from '../shared/dto.js';
import type { DBShape } from './types.js';
import type { BacktestCandleLoader } from './backtestWorker.js';
import type { CandleTimeframe } from '../exchange/types.js';
import {
  buildBacktestLiveDeltaReport,
  buildDefaultReplayAssumptions,
  buildRollingWindowSchedule,
  buildObjectiveMetrics,
  buildRejectionStats,
  createExperimentFromRun,
  createExperimentTrial,
  createOptunaRequest,
  createUnavailableQuantStatsReport,
  detectOptunaAvailability,
  ensureExperimentCollections,
  pickBestTrial,
  shouldEarlyPruneTrial,
  summarizeBacktestTradeBreakdown,
} from './experimentGovernance.js';

// ─── Constants ────────────────────────────────────────────────────────

const MAX_CANDIDATES = 5000;
const YIELD_EVERY_N = 5; // yield to event loop every N candidates
const YIELD_MS = 2; // ms to sleep on yield
const HEARTBEAT_PERSIST_MS = 10_000;
const OPTIMIZER_TRIAL_SAMPLE_EVERY = Math.max(1, Number(process.env.OPTIMIZER_TRIAL_SAMPLE_EVERY || 50));
const OPTIMIZER_MAX_PERSISTED_TRIALS_PER_RUN = Math.max(25, Number(process.env.OPTIMIZER_MAX_PERSISTED_TRIALS_PER_RUN || 250));
const INTEGER_PARAMS = new Set(['maxLeverage', 'engulfingLookbackCandles', 'timeStopBars', 'eventLockoutMinutes']);
const TIMEFRAME_PARAMS = new Set(['regimeTf']);

const TF_LABEL_TO_CANDLE_TF: Record<string, CandleTimeframe> = {
  '5m': '5m',
  '15m': '15m',
  '1h': '1h',
  '4h': '4h',
};

// ─── Concurrency guard ───────────────────────────────────────────────

let activeOptimizationId: string | null = null;

export function isOptimizationRunning(): boolean {
  return activeOptimizationId !== null;
}

export function getActiveOptimizationId(): string | null {
  return activeOptimizationId;
}

// ─── Helpers ─────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function round(v: number, decimals = 2): number {
  const f = 10 ** decimals;
  return Math.round(v * f) / f;
}

/**
 * Map a param name to its location in TradingRulesSettings.
 * Supports core Trading Rules / SignalQualityContext numeric knobs.
 */
function applyParamToRules(rules: TradingRulesSettings, param: string, value: number): void {
  if (TIMEFRAME_PARAMS.has(param)) {
    if (param === 'regimeTf') rules.regimeTf = value >= 4 ? '4h' : '1h';
    return;
  }
  const normalizedValue = INTEGER_PARAMS.has(param) ? Math.round(value) : value;
  if (param === 'slPct') rules.slPct = normalizedValue;
  else if (param === 'tpLevels[0]' || param === 'tp1Pct') {
    if (!rules.tpLevels) rules.tpLevels = [6];
    rules.tpLevels[0] = normalizedValue;
  } else if (param === 'tpLevels[1]' || param === 'tp2Pct') {
    if (!rules.tpLevels) rules.tpLevels = [6];
    if (rules.tpLevels.length < 2) rules.tpLevels.push(normalizedValue);
    else rules.tpLevels[1] = normalizedValue;
  } else if (param === 'tpLevels[2]' || param === 'tp3Pct') {
    if (!rules.tpLevels) rules.tpLevels = [6];
    while (rules.tpLevels.length < 3) rules.tpLevels.push(normalizedValue);
    rules.tpLevels[2] = normalizedValue;
  } else if (param === 'maxLeverage') rules.maxLeverage = normalizedValue;
  else if (param === 'engulfingLookbackCandles') rules.engulfingLookbackCandles = normalizedValue;
  else if (param === 'fvgRetrace') rules.fvgRetrace = normalizedValue;
  else if (param === 'fvgMinWidthPct') rules.fvgMinWidthPct = normalizedValue;
  else if (param === 'exitClosePct') rules.exitClosePct = normalizedValue;
  else if (param === 'dailyDrawdown') rules.dailyDrawdown = normalizedValue;
  else if (param === 'adxMin') rules.adxMin = normalizedValue;
  else if (param === 'minImpulseAtr') rules.minImpulseAtr = normalizedValue;
  else if (param === 'minExpectedRr') rules.minExpectedRr = normalizedValue;
  else if (param === 'timeStopBars') rules.timeStopBars = normalizedValue;
  else if (param === 'riskPerTradePct') rules.riskPerTradePct = normalizedValue;
  else if (param === 'eventLockoutMinutes') rules.eventLockoutMinutes = normalizedValue;
  else if (param === 'portfolioGrossCap') rules.portfolioGrossCap = normalizedValue;
}

function extractParamValue(rules: TradingRulesSettings, param: string): number | undefined {
  if (param === 'regimeTf') return rules.regimeTf === '4h' ? 4 : 1;
  if (param === 'slPct') return rules.slPct;
  if (param === 'tpLevels[0]' || param === 'tp1Pct') return rules.tpLevels?.[0];
  if (param === 'tpLevels[1]' || param === 'tp2Pct') return rules.tpLevels?.[1];
  if (param === 'tpLevels[2]' || param === 'tp3Pct') return rules.tpLevels?.[2];
  if (param === 'maxLeverage') return rules.maxLeverage;
  if (param === 'engulfingLookbackCandles') return rules.engulfingLookbackCandles;
  if (param === 'fvgRetrace') return rules.fvgRetrace;
  if (param === 'fvgMinWidthPct') return rules.fvgMinWidthPct;
  if (param === 'exitClosePct') return rules.exitClosePct;
  if (param === 'dailyDrawdown') return rules.dailyDrawdown;
  if (param === 'adxMin') return rules.adxMin;
  if (param === 'minImpulseAtr') return rules.minImpulseAtr;
  if (param === 'minExpectedRr') return rules.minExpectedRr;
  if (param === 'timeStopBars') return rules.timeStopBars;
  if (param === 'riskPerTradePct') return rules.riskPerTradePct;
  if (param === 'eventLockoutMinutes') return rules.eventLockoutMinutes;
  if (param === 'portfolioGrossCap') return rules.portfolioGrossCap;
  return undefined;
}

/**
 * Generate all grid points for a single param range.
 */
function generateSteps(range: OptimizationParamRange): number[] {
  const { min, max, step } = range;
  if (step <= 0 || min > max) return [min];
  const steps: number[] = [];
  for (let v = min; v <= max + step * 0.001; v += step) {
    steps.push(round(v, 4));
  }
  return steps;
}

/**
 * Generate cartesian product of all param ranges, capped at MAX_CANDIDATES.
 * If the full grid exceeds the cap, it samples uniformly.
 */
function generateCandidates(
  ranges: OptimizationParamRange[],
): { candidates: Array<Record<string, number>>; gridCandidates: number } {
  if (ranges.length === 0) return { candidates: [{}], gridCandidates: 1 };

  // Generate per-param step arrays
  const perParam = ranges.map((r) => ({
    param: r.param,
    values: generateSteps(r).map((v) => {
      if (TIMEFRAME_PARAMS.has(r.param)) return v >= 4 ? 4 : 1;
      return INTEGER_PARAMS.has(r.param) ? Math.round(v) : v;
    }),
  }));

  // Compute total grid size
  let totalGrid = 1;
  for (const pp of perParam) {
    totalGrid *= pp.values.length;
    if (totalGrid > MAX_CANDIDATES * 10) break; // overflow guard
  }

  if (totalGrid <= MAX_CANDIDATES) {
    // Full cartesian product
    let combos: Array<Record<string, number>> = [{}];
    for (const pp of perParam) {
      const next: Array<Record<string, number>> = [];
      for (const combo of combos) {
        for (const val of pp.values) {
          next.push({ ...combo, [pp.param]: val });
        }
      }
      combos = next;
    }
    return { candidates: combos, gridCandidates: perParam.reduce((acc, pp) => acc * new Set(pp.values).size, 1) };
  }

  // Sampled: stratified random sampling up to MAX_CANDIDATES
  const candidates: Array<Record<string, number>> = [];
  const seen = new Set<string>();
  let attempts = 0;
  while (candidates.length < MAX_CANDIDATES && attempts < MAX_CANDIDATES * 3) {
    attempts++;
    const combo: Record<string, number> = {};
    for (const pp of perParam) {
      const idx = Math.floor(Math.random() * pp.values.length);
      combo[pp.param] = pp.values[idx];
    }
    const key = JSON.stringify(combo);
    if (!seen.has(key)) {
      seen.add(key);
      candidates.push(combo);
    }
  }
  return { candidates, gridCandidates: perParam.reduce((acc, pp) => acc * new Set(pp.values).size, 1) };
}

function sliceCandleSetsForWindow(candleSets: BacktestCandleSet[], startTimeMs: number, endTimeMs: number): BacktestCandleSet[] {
  return candleSets.map((set) => ({
    ...set,
    candles: set.candles.filter((candle) => {
      const timeMs = Date.parse(candle.timestamp);
      return Number.isFinite(timeMs) && timeMs >= startTimeMs && timeMs <= endTimeMs;
    }),
  }));
}

function combineSummaries(summaries: BacktestRunSummary[]): BacktestRunSummary {
  const totalTrades = summaries.reduce((acc, summary) => acc + summary.totalTrades, 0);
  const netPnlUsd = round(summaries.reduce((acc, summary) => acc + summary.netPnlUsd, 0));
  const realizedPnlUsd = round(summaries.reduce((acc, summary) => acc + summary.realizedPnlUsd, 0));
  const openPnlUsd = round(summaries.reduce((acc, summary) => acc + summary.openPnlUsd, 0));
  const weightedWins = summaries.reduce((acc, summary) => acc + ((summary.winRatePct / 100) * summary.totalTrades), 0);
  const weightedWinRate = totalTrades > 0 ? round((weightedWins / totalTrades) * 100) : 0;
  const maxDrawdownPct = summaries.reduce((acc, summary) => Math.max(acc, summary.maxDrawdownPct), 0);
  return {
    totalTrades,
    winRatePct: weightedWinRate,
    realizedPnlUsd,
    openPnlUsd,
    netPnlUsd,
    roiPct: round(summaries.reduce((acc, summary) => acc + summary.roiPct, 0)),
    maxDrawdownPct: round(maxDrawdownPct),
    expectancyUsd: round(totalTrades > 0 ? netPnlUsd / totalTrades : 0),
  };
}

function combineBySymbol(windows: BacktestRunSymbolStats[][]): BacktestRunSymbolStats[] {
  const grouped = new Map<string, BacktestRunSymbolStats>();
  for (const rows of windows) {
    for (const row of rows) {
      const current = grouped.get(row.symbol) ?? {
        ...row,
        totalTrades: 0,
        wins: 0,
        losses: 0,
        realizedPnlUsd: 0,
        netPnlUsd: 0,
        slCount: 0,
        tp1Count: 0,
        tp2Count: 0,
        tp3Count: 0,
        emergencyExitCount: 0,
        rejectedSignals: 0,
      };
      current.totalTrades += row.totalTrades;
      current.wins += row.wins;
      current.losses += row.losses;
      current.realizedPnlUsd = round(current.realizedPnlUsd + row.realizedPnlUsd);
      current.netPnlUsd = round(current.netPnlUsd + row.netPnlUsd);
      current.slCount += row.slCount;
      current.tp1Count += row.tp1Count;
      current.tp2Count += row.tp2Count;
      current.tp3Count += row.tp3Count;
      current.emergencyExitCount += row.emergencyExitCount;
      current.rejectedSignals += row.rejectedSignals;
      grouped.set(row.symbol, current);
    }
  }
  return [...grouped.values()];
}

function combineTradeBreakdowns(windows: BacktestTradeBreakdownItem[][]): BacktestTradeBreakdownItem[] {
  const grouped = new Map<string, BacktestTradeBreakdownItem>();
  for (const rows of windows) {
    for (const row of rows) {
      const key = `${row.setup}|${row.timeframe}|${row.source}`;
      const current = grouped.get(key) ?? { ...row, tradeCount: 0, wins: 0, losses: 0, netPnlUsd: 0 };
      current.tradeCount += row.tradeCount;
      current.wins += row.wins;
      current.losses += row.losses;
      current.netPnlUsd = round(current.netPnlUsd + row.netPnlUsd);
      grouped.set(key, current);
    }
  }
  return [...grouped.values()];
}

function compactTrialForPersistence(trial: ExperimentTrial, full: boolean): ExperimentTrial {
  if (full) return trial;

  // Keep enough information for diagnostics and objective comparison, but avoid
  // persisting bulky per-candidate arrays for thousands of sampled trials.
  const compact: ExperimentTrial = {
    ...trial,
    bySymbol: undefined,
    tradeBreakdown: undefined,
    deltaReport: undefined,
    quantStatsReport: undefined,
    windowResults: trial.windowResults?.map((window) => ({
      windowIndex: window.windowIndex,
      train: window.train,
      test: window.test,
      metrics: window.metrics,
      rejectionStats: window.rejectionStats,
      summary: window.summary,
    })),
  };
  return compact;
}

function compactPersistedTrialsForOptimization(dbData: DBShape, experiment: Experiment, opt: OptimizationResult): void {
  const related = dbData.experimentTrials
    .filter((trial) => trial.experimentId === experiment.id || trial.optimizationResultId === opt.id);
  if (related.length <= OPTIMIZER_MAX_PERSISTED_TRIALS_PER_RUN) return;

  const keep = new Set<string>();
  if (opt.bestTrialId) keep.add(opt.bestTrialId);
  if (experiment.candidateTrialId) keep.add(experiment.candidateTrialId);

  const byNewest = [...related].sort((a, b) => {
    const at = Date.parse(a.finishedAt ?? a.startedAt ?? a.createdAt ?? '');
    const bt = Date.parse(b.finishedAt ?? b.startedAt ?? b.createdAt ?? '');
    return (Number.isFinite(bt) ? bt : 0) - (Number.isFinite(at) ? at : 0);
  });

  for (const trial of byNewest) {
    if (keep.size >= OPTIMIZER_MAX_PERSISTED_TRIALS_PER_RUN) break;
    keep.add(trial.id);
  }

  dbData.experimentTrials = dbData.experimentTrials.filter((trial) => (
    (trial.experimentId !== experiment.id && trial.optimizationResultId !== opt.id) || keep.has(trial.id)
  ));
  experiment.trialIds = (experiment.trialIds ?? []).filter((id) => keep.has(id));
  opt.trialIds = (opt.trialIds ?? []).filter((id) => keep.has(id));
}

function persistOptimizationTrial(params: {
  dbData: DBShape;
  experiment: Experiment;
  opt: OptimizationResult;
  trial: ExperimentTrial;
  full: boolean;
}): void {
  const row = compactTrialForPersistence(params.trial, params.full);
  const idx = params.dbData.experimentTrials.findIndex((item) => item.id === row.id);
  if (idx >= 0) params.dbData.experimentTrials[idx] = row;
  else params.dbData.experimentTrials.unshift(row);

  params.experiment.trialIds = [...new Set([...(params.experiment.trialIds ?? []), row.id])];
  params.opt.trialIds = [...new Set([...(params.opt.trialIds ?? []), row.id])];
  compactPersistedTrialsForOptimization(params.dbData, params.experiment, params.opt);
}

// ─── Main Optimization Worker ────────────────────────────────────────

export async function executeOptimization(
  optimizationId: string,
  candleLoader: BacktestCandleLoader,
  depositUsd: number,
): Promise<void> {
  if (activeOptimizationId) {
    throw new Error(`optimization_already_running:${activeOptimizationId}`);
  }

  const db = await getDb();
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  ensureExperimentCollections(db.data);
  const opt = db.data.optimizationResults.find((o) => o.id === optimizationId);
  if (!opt) {
    throw new Error(`optimization_not_found:${optimizationId}`);
  }
  if (opt.status !== 'queued') {
    throw new Error(`optimization_not_queued:${opt.status}`);
  }

  // Find the source backtest run to get its data ranges
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const sourceRun = db.data.backtestRuns.find((r) => r.id === opt.sourceRunId);
  if (!sourceRun) {
    throw new Error(`source_run_not_found:${opt.sourceRunId}`);
  }

  let experiment = opt.experimentId
    ? db.data.experiments.find((item) => item.id === opt.experimentId)
    : undefined;
  if (!experiment) {
    experiment = createExperimentFromRun({
      sourceRun,
      optimizationResultId: opt.id,
      requestedBy: 'optimizer_worker',
    });
    db.data.experiments.unshift(experiment);
    opt.experimentId = experiment.id;
  }

  activeOptimizationId = optimizationId;
  markComputeJobStarted(opt, {
    stage: 'loading_market_data',
    completed: 0,
    total: 1,
  });
  experiment.status = 'running';
  experiment.startedAt = experiment.startedAt ?? new Date().toISOString();
  opt.rollingWindowSchedule = opt.rollingWindowSchedule ?? experiment.schedule;
  opt.replayAssumptions = opt.replayAssumptions ?? sourceRun.replayAssumptions ?? buildDefaultReplayAssumptions();
  opt.acceptanceCriteria = opt.acceptanceCriteria ?? experiment.acceptanceCriteria;
  opt.objectiveName = opt.objectiveName ?? experiment.objectiveName;
  opt.optunaRequest = opt.optunaRequest ?? createOptunaRequest({
    experimentId: experiment.id,
    objectiveName: opt.objectiveName,
  });
  opt.optunaStatus = detectOptunaAvailability();
  opt.quantStatsReport = opt.quantStatsReport ?? createUnavailableQuantStatsReport('quantstats sidecar not available in optimizer worker');
  await db.write();
  let lastHeartbeatPersistMs = Date.now();

  try {
    const baseRules = opt.baseRulesSnapshot;
    const symbol = opt.symbol;
    const schedule = opt.rollingWindowSchedule ?? experiment.schedule;

    const requiredTfs = getRequiredComputeTimeframes(baseRules);

    // Load candles once (shared across all candidates)
    const candleSets: BacktestCandleSet[] = [];

    for (let tfIndex = 0; tfIndex < requiredTfs.length; tfIndex++) {
      const tf = requiredTfs[tfIndex];
      const candleTf = TF_LABEL_TO_CANDLE_TF[tf];
      if (!candleTf) continue;
      const window = computeCandleLoadWindow({
        timeframe: tf,
        startTimeMs: opt.startTimeMs,
        endTimeMs: opt.endTimeMs,
      });

      try {
        const candles = await candleLoader.getCandles({
          symbol,
          timeframe: candleTf,
          startTimeMs: window.startTimeMs,
          endTimeMs: window.endTimeMs,
        });
        candleSets.push({ symbol, timeframe: candleTf, candles });
        logger.info(
          { component: 'optimizer', optimizationId, symbol, tf: candleTf, candles: candles.length },
          'loaded candles for optimization',
        );
      } catch (err) {
        logger.warn(
          { component: 'optimizer', optimizationId, symbol, tf: candleTf, err },
          'failed to load candles for timeframe',
        );
      }

      updateComputeJobProgress(opt, {
        completed: tfIndex + 1,
        total: requiredTfs.length,
        stage: 'loading_market_data',
      });
      lastHeartbeatPersistMs = Date.now();
      await db.write().catch(() => {});
    }

    if (candleSets.length === 0) {
      throw new Error('no_candle_data_loaded');
    }

    // Generate candidates
    const { candidates, gridCandidates } = generateCandidates(opt.paramRanges);
    opt.searchSpaceCandidates = gridCandidates;
    opt.totalCandidates = candidates.length;
    opt.evaluatedCandidates = 0;
    opt.prunedCandidates = 0;
    opt.trialIds = Array.isArray(opt.trialIds) ? opt.trialIds : [];
    opt.progress = createComputeJobProgress(0, candidates.length, 'evaluating_candidates');
    await db.write();

    logger.info(
      { component: 'optimizer', optimizationId, symbol, candidates: candidates.length, gridCandidates },
      'starting optimization search',
    );

    let bestPnl = -Infinity;
    let bestSummary: BacktestRunSummary | undefined;
    let bestBySymbol: BacktestRunSymbolStats[] | undefined;
    let bestParamCombo: Record<string, number> | undefined;

    for (let i = 0; i < candidates.length; i++) {
      const combo = candidates[i];

      // Clone base rules and apply candidate params
      const candidateRules: TradingRulesSettings = JSON.parse(JSON.stringify(baseRules));
      for (const [param, value] of Object.entries(combo)) {
        applyParamToRules(candidateRules, param, value);
      }

      const trial = createExperimentTrial({
        experiment,
        optimizationResultId: opt.id,
        sourceRunId: sourceRun.id,
        trialNumber: i,
        parameterValues: combo,
        rulesSnapshot: candidateRules,
        engineVersion: opt.engineVersion,
        engineCommit: opt.engineCommit,
        optunaRequest: opt.optunaRequest,
        optunaStatus: opt.optunaStatus,
      });
      trial.status = 'running';
      trial.startedAt = new Date().toISOString();

      const windowResults: ExperimentTrialWindowResult[] = [];
      const summaryWindows: BacktestRunSummary[] = [];
      const bySymbolWindows: BacktestRunSymbolStats[][] = [];
      const breakdownWindows: BacktestTradeBreakdownItem[][] = [];
      let pruned = false;

      try {
        for (const window of schedule.windows) {
          const trialCandleSets = sliceCandleSetsForWindow(candleSets, window.train.startTimeMs, window.test.endTimeMs);
          const syntheticRun: BacktestRun = {
            id: `opt_${optimizationId}_${i}_${window.index}`,
            status: 'running',
            symbol,
            biasMode: opt.biasMode,
            createdAt: new Date().toISOString(),
            startTimeMs: window.test.startTimeMs,
            endTimeMs: window.test.endTimeMs,
            engineVersion: opt.engineVersion,
            engineCommit: opt.engineCommit,
            rulesSnapshot: candidateRules,
            bySymbol: [],
            aiAnalysis: { status: 'idle' },
            coverage: window.coverage,
            replayAssumptions: opt.replayAssumptions,
          };
          const result = runBacktestEngine({
            run: syntheticRun,
            candleSets: trialCandleSets,
            depositUsd,
          });
          const metrics = buildObjectiveMetrics(result.summary);
          const rejectionStats = buildRejectionStats(result.bySymbol);
          if (!metrics) {
            throw new Error('trial_metrics_unavailable');
          }
          windowResults.push({
            windowIndex: window.index,
            train: window.train,
            test: window.test,
            metrics,
            rejectionStats,
            summary: result.summary,
          });
          summaryWindows.push(result.summary);
          bySymbolWindows.push(result.bySymbol);
          breakdownWindows.push(summarizeBacktestTradeBreakdown(result.trades));

          const pruneDecision = shouldEarlyPruneTrial({
            acceptanceCriteria: experiment.acceptanceCriteria,
            windowResults,
          });
          if (pruneDecision.prune) {
            pruned = true;
            trial.status = 'pruned';
            trial.prunerDecision = {
              status: 'early_pruned',
              reason: pruneDecision.reason,
              decidedAt: new Date().toISOString(),
              afterWindowIndex: window.index,
            };
            opt.prunedCandidates = (opt.prunedCandidates ?? 0) + 1;
            break;
          }
        }

        if (!pruned) {
          const combinedSummary = combineSummaries(summaryWindows);
          const combinedBySymbol = combineBySymbol(bySymbolWindows);
          const combinedBreakdown = combineTradeBreakdowns(breakdownWindows);
          const objectiveMetrics = buildObjectiveMetrics(combinedSummary);

          trial.summary = combinedSummary;
          trial.bySymbol = combinedBySymbol;
          trial.tradeBreakdown = combinedBreakdown;
          trial.objectiveMetrics = objectiveMetrics;
          trial.rejectionStats = buildRejectionStats(combinedBySymbol);
          trial.deltaReport = buildBacktestLiveDeltaReport({
            coverage: experiment.coverage,
            backtestSummary: combinedSummary,
            tradeBreakdown: combinedBreakdown,
            livePositions: db.data.positions,
            executionIntents: db.data.executionIntents,
          });
          trial.windowResults = windowResults;
          trial.quantStatsReport = createUnavailableQuantStatsReport('quantstats sidecar not available in optimizer worker');
          trial.status = 'completed';
          trial.finishedAt = new Date().toISOString();
          trial.prunerDecision = { status: 'kept', decidedAt: trial.finishedAt };

          if ((objectiveMetrics?.objectiveValue ?? -Infinity) > bestPnl) {
            bestPnl = objectiveMetrics?.objectiveValue ?? -Infinity;
            bestSummary = combinedSummary;
            bestBySymbol = combinedBySymbol;
            bestParamCombo = combo;
            opt.bestTrialId = trial.id;
            opt.bestObjectiveMetrics = objectiveMetrics;
            experiment.candidateTrialId = trial.id;
            persistOptimizationTrial({ dbData: db.data, experiment, opt, trial, full: true });
          }
        } else {
          trial.windowResults = windowResults;
          trial.finishedAt = new Date().toISOString();
        }
      } catch (err) {
        // Skip failed candidates silently
        logger.debug(
          { component: 'optimizer', optimizationId, candidate: i, err },
          'candidate evaluation failed, skipping',
        );
        trial.status = 'failed';
        trial.error = err instanceof Error ? err.message : String(err);
        trial.finishedAt = new Date().toISOString();
      }

      const shouldPersistSample = (i + 1) % OPTIMIZER_TRIAL_SAMPLE_EVERY === 0 || i === candidates.length - 1;
      if (trial.id !== opt.bestTrialId && shouldPersistSample) {
        persistOptimizationTrial({ dbData: db.data, experiment, opt, trial, full: false });
      }

      opt.evaluatedCandidates = i + 1;
      updateComputeJobProgress(opt, {
        completed: opt.evaluatedCandidates,
        total: candidates.length,
        stage: 'evaluating_candidates',
      });

      // Yield to event loop periodically
      if ((i + 1) % YIELD_EVERY_N === 0) {
        await sleep(YIELD_MS);
      }

      if (shouldPersistProgress({
        completed: opt.evaluatedCandidates,
        total: candidates.length,
        forceEvery: 25,
      }) || Date.now() - lastHeartbeatPersistMs >= HEARTBEAT_PERSIST_MS) {
        lastHeartbeatPersistMs = Date.now();
        await db.write().catch(() => {});
      }
    }

    // Write best result
    if (bestParamCombo && bestSummary) {
      const bestRules: Partial<TradingRulesSettings> = {};
      for (const [param, value] of Object.entries(bestParamCombo)) {
        const fullRules = JSON.parse(JSON.stringify(baseRules)) as TradingRulesSettings;
        applyParamToRules(fullRules, param, value);
        // Store only optimized params back
        const currentVal = extractParamValue(fullRules, param);
        if (currentVal !== undefined) {
          applyParamToRules(bestRules as TradingRulesSettings, param, currentVal);
        }
      }

      // Build complete best rules for easy apply
      const completeBestRules = JSON.parse(JSON.stringify(baseRules)) as TradingRulesSettings;
      for (const [param, value] of Object.entries(bestParamCombo)) {
        applyParamToRules(completeBestRules, param, value);
      }

      opt.bestParams = completeBestRules;
      opt.bestSummary = bestSummary;
      opt.bestBySymbol = bestBySymbol;
    }

    const trialRows = db.data.experimentTrials.filter((item) => item.experimentId === experiment.id || item.optimizationResultId === opt.id);
    const bestTrial = pickBestTrial(trialRows);
    if (bestTrial) {
      experiment.candidateTrialId = bestTrial.id;
    }
    compactPersistedTrialsForOptimization(db.data, experiment, opt);
    experiment.status = 'completed';
    experiment.finishedAt = new Date().toISOString();

    markComputeJobCompleted(opt, {
      stage: 'completed',
      total: candidates.length,
    });

    logger.info(
      { component: 'optimizer', optimizationId, symbol, evaluated: opt.evaluatedCandidates, bestPnl: bestSummary?.netPnlUsd },
      'optimization completed',
    );
  } catch (err) {
    markComputeJobFailed(
      opt,
      err instanceof Error ? err.message : String(err),
      { stage: 'failed' },
    );

    logger.error(
      { component: 'optimizer', optimizationId, err: opt.error },
      'optimization failed',
    );
    experiment.status = 'failed';
    experiment.error = opt.error;
    experiment.finishedAt = new Date().toISOString();
  } finally {
    activeOptimizationId = null;
    await db.write().catch((writeErr) => {
      logger.error({ component: 'optimizer', optimizationId, err: writeErr }, 'failed to persist optimization result');
    });
  }
}

/**
 * Create a queued optimization result from a completed backtest run.
 */
export function createQueuedOptimization(input: {
  sourceRun: BacktestRun;
  paramRanges: OptimizationParamRange[];
}): OptimizationResult {
  const { sourceRun, paramRanges } = input;
  const engine = getBacktestEngineVersion();
  const rollingWindowSchedule = buildRollingWindowSchedule({
    symbol: sourceRun.symbol,
    rules: sourceRun.rulesSnapshot,
    startTimeMs: sourceRun.startTimeMs,
    endTimeMs: sourceRun.endTimeMs,
  });
  const replayAssumptions = sourceRun.replayAssumptions ?? buildDefaultReplayAssumptions();
  const experiment = createExperimentFromRun({
    sourceRun,
    requestedBy: 'owner',
  });
  const optunaRequest = createOptunaRequest({
    experimentId: experiment.id,
  });

  return {
    id: nanoid(),
    status: 'queued',
    sourceRunId: sourceRun.id,
    experimentId: experiment.id,
    symbol: sourceRun.symbol,
    biasMode: sourceRun.biasMode,
    startTimeMs: sourceRun.startTimeMs,
    endTimeMs: sourceRun.endTimeMs,
    baseRulesSnapshot: JSON.parse(JSON.stringify(sourceRun.rulesSnapshot)),
    paramRanges,
    rollingWindowSchedule,
    replayAssumptions,
    acceptanceCriteria: experiment.acceptanceCriteria,
    objectiveName: experiment.objectiveName,
    optunaRequest,
    optunaStatus: {
      status: 'pending',
      adapter: 'python_optuna',
      checkedAt: new Date().toISOString(),
    },
    quantStatsReport: createUnavailableQuantStatsReport('quantstats sidecar not requested yet'),
    trialIds: [],
    createdAt: new Date().toISOString(),
    progress: createComputeJobProgress(0, 0, 'queued'),
    searchSpaceCandidates: 0,
    totalCandidates: 0,
    evaluatedCandidates: 0,
    prunedCandidates: 0,
    engineVersion: engine.version,
    engineCommit: engine.commit,
  };
}
