/**
 * backtestWorker.ts
 *
 * Isolated backtest job runner. Loads historical candles, executes the canonical
 * backtest engine, and writes results back to persistence.
 *
 * Isolation guarantees:
 *  - No access to live order execution
 *  - No Telegram outbox writes
 *  - No live position / pending confirmation mutations
 *  - Only writes to backtestRuns[] in the shared persistence store
 */

import logger from '../lib/logger.js';
import { getDb } from './db.js';
import { runBacktestEngine, type BacktestCandleSet } from './backtestEngine.js';
import { getBacktestEngineVersion } from './backtest.js';
import {
  computeCandleLoadWindow,
  getRequiredComputeTimeframes,
  markComputeJobCompleted,
  markComputeJobFailed,
  markComputeJobStarted,
  updateComputeJobProgress,
} from './computeJob.js';
import type { BacktestRun } from '../shared/dto.js';
import type { CandleTimeframe } from '../exchange/types.js';
import {
  buildBacktestLiveDeltaReport,
  buildObjectiveMetrics,
  buildRejectionStats,
  createUnavailableQuantStatsReport,
  summarizeBacktestTradeBreakdown,
} from './experimentGovernance.js';

// ─── Types ────────────────────────────────────────────────────────────

export interface BacktestCandleLoader {
  getCandles(params: {
    symbol: string;
    timeframe: CandleTimeframe;
    startTimeMs: number;
    endTimeMs: number;
  }): Promise<import('../exchange/types.js').Candle[]>;
}

// ─── Constants ────────────────────────────────────────────────────────

const TF_LABEL_TO_CANDLE_TF: Record<string, CandleTimeframe> = {
  '5m': '5m',
  '15m': '15m',
  '1h': '1h',
  '4h': '4h',
};

// ─── Concurrency guard ───────────────────────────────────────────────

let activeRunId: string | null = null;

export function isBacktestRunning(): boolean {
  return activeRunId !== null;
}

export function getActiveBacktestRunId(): string | null {
  return activeRunId;
}

export function requireBacktestRun(runId: string, runs: BacktestRun[]): BacktestRun {
  const run = runs.find((item) => item.id === runId);
  if (!run) {
    throw new Error(`backtest_run_not_found:${runId}`);
  }
  return run;
}

export function mutateBacktestRun(
  db: Pick<Awaited<ReturnType<typeof getDb>>, 'data'>,
  runId: string,
  mutate: (run: BacktestRun) => void,
): BacktestRun {
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const run = requireBacktestRun(runId, db.data.backtestRuns);
  mutate(run);
  return run;
}

// ─── Worker ──────────────────────────────────────────────────────────

export async function executeBacktestRun(
  runId: string,
  candleLoader: BacktestCandleLoader,
  depositUsd: number,
): Promise<void> {
  if (activeRunId) {
    throw new Error(`backtest_already_running:${activeRunId}`);
  }

  const db = await getDb();
  db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
  const initialRun = requireBacktestRun(runId, db.data.backtestRuns);
  if (initialRun.status !== 'queued') {
    throw new Error(`backtest_run_not_queued:${initialRun.status}`);
  }

  activeRunId = runId;
  const engine = getBacktestEngineVersion();
  mutateBacktestRun(db, runId, (run) => {
    markComputeJobStarted(run, {
      stage: 'loading_market_data',
      completed: 0,
      total: 2,
    });
    run.engineVersion = engine.version;
    run.engineCommit = engine.commit;
  });
  await db.write();

  const rules = initialRun.rulesSnapshot;
  const symbol = initialRun.symbol;
  const startTimeMs = initialRun.startTimeMs;
  const endTimeMs = initialRun.endTimeMs;

  try {
    const requiredTfs = getRequiredComputeTimeframes(rules);

    // Load candles for all required timeframes
    const candleSets: BacktestCandleSet[] = [];

    for (const tf of requiredTfs) {
      const candleTf = TF_LABEL_TO_CANDLE_TF[tf];
      if (!candleTf) continue;
      const window = computeCandleLoadWindow({
        timeframe: tf,
        startTimeMs,
        endTimeMs,
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
          { component: 'backtest-worker', runId, symbol, tf: candleTf, candles: candles.length },
          'loaded candles for backtest',
        );
      } catch (err) {
        logger.warn(
          { component: 'backtest-worker', runId, symbol, tf: candleTf, err },
          'failed to load candles for timeframe',
        );
      }
    }

    if (candleSets.length === 0) {
      throw new Error('no_candle_data_loaded');
    }

    // Record market data coverage
    let minLoadedMs = Infinity;
    let maxLoadedMs = -Infinity;
    for (const cs of candleSets) {
      for (const c of cs.candles) {
        const ms = Date.parse(c.timestamp);
        if (ms < minLoadedMs) minLoadedMs = ms;
        if (ms > maxLoadedMs) maxLoadedMs = ms;
      }
    }
    mutateBacktestRun(db, runId, (run) => {
      run.marketDataCoverage = {
        requestedFromMs: startTimeMs,
        requestedToMs: endTimeMs,
        loadedFromMs: Number.isFinite(minLoadedMs) ? minLoadedMs : undefined,
        loadedToMs: Number.isFinite(maxLoadedMs) ? maxLoadedMs : undefined,
      };
      updateComputeJobProgress(run, {
        completed: 1,
        total: 2,
        stage: 'executing_backtest',
        heartbeat: false,
      });
    });

    // Run engine
    const result = runBacktestEngine({
      run: {
        ...initialRun,
        status: 'running',
        startedAt: initialRun.startedAt ?? new Date().toISOString(),
        engineVersion: engine.version,
        engineCommit: engine.commit,
        marketDataCoverage: {
          requestedFromMs: startTimeMs,
          requestedToMs: endTimeMs,
          loadedFromMs: Number.isFinite(minLoadedMs) ? minLoadedMs : undefined,
          loadedToMs: Number.isFinite(maxLoadedMs) ? maxLoadedMs : undefined,
        },
      },
      candleSets,
      depositUsd,
    });

    // Write results onto the latest snapshot object, not a stale pre-reload reference.
    mutateBacktestRun(db, runId, (run) => {
      run.summary = result.summary;
      run.bySymbol = result.bySymbol;
      run.objectiveMetrics = buildObjectiveMetrics(result.summary);
      run.rejectionStats = buildRejectionStats(result.bySymbol);
      run.deltaReport = buildBacktestLiveDeltaReport({
        coverage: run.coverage ?? {
          symbols: [run.symbol],
          timeframes: getRequiredComputeTimeframes(run.rulesSnapshot),
          window: {
            startTimeMs: run.startTimeMs,
            endTimeMs: run.endTimeMs,
          },
        },
        backtestSummary: result.summary,
        tradeBreakdown: summarizeBacktestTradeBreakdown(result.trades),
        livePositions: db.data.positions,
        executionIntents: db.data.executionIntents,
      });
      run.quantStatsReport = run.quantStatsReport ?? createUnavailableQuantStatsReport('quantstats sidecar not available in detached worker');
      run.artifacts = {
        tradeCount: result.trades.length,
        equityCurvePoints: result.equityCurve.length,
        eventCount: result.trades.length,
        tradeBreakdown: summarizeBacktestTradeBreakdown(result.trades),
      };
      markComputeJobCompleted(run, {
        stage: 'completed',
        total: 2,
      });
      run.aiAnalysis = run.aiAnalysis?.status === 'pending'
        ? run.aiAnalysis
        : { status: 'idle' };
    });

    logger.info(
      { component: 'backtest-worker', runId, symbol, trades: result.summary.totalTrades, pnl: result.summary.netPnlUsd },
      'backtest run completed',
    );
  } catch (err) {
    const error = err instanceof Error ? err.message : String(err);
    mutateBacktestRun(db, runId, (run) => {
      markComputeJobFailed(run, error, { stage: 'failed' });
    });

    logger.error(
      { component: 'backtest-worker', runId, err: error },
      'backtest run failed',
    );
  } finally {
    activeRunId = null;
    await db.write().catch((writeErr) => {
      logger.error({ component: 'backtest-worker', runId, err: writeErr }, 'failed to persist backtest result');
    });
  }
}
