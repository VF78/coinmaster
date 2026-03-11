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
import type { BacktestRun, TradingRulesSettings, TradingRulesTimeframe } from '../shared/dto.js';
import type { CandleTimeframe } from '../exchange/types.js';

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

const TF_MS: Record<string, number> = {
  '5m': 5 * 60_000,
  '15m': 15 * 60_000,
  '1h': 60 * 60_000,
  '4h': 4 * 60 * 60_000,
};

// ─── Concurrency guard ───────────────────────────────────────────────

let activeRunId: string | null = null;

export function isBacktestRunning(): boolean {
  return activeRunId !== null;
}

export function getActiveBacktestRunId(): string | null {
  return activeRunId;
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
  const run = db.data.backtestRuns.find((r) => r.id === runId);
  if (!run) {
    throw new Error(`backtest_run_not_found:${runId}`);
  }
  if (run.status !== 'queued') {
    throw new Error(`backtest_run_not_queued:${run.status}`);
  }

  activeRunId = runId;
  run.status = 'running';
  run.startedAt = new Date().toISOString();
  const engine = getBacktestEngineVersion();
  run.engineVersion = engine.version;
  run.engineCommit = engine.commit;
  await db.write();

  try {
    const rules = run.rulesSnapshot;
    const symbol = run.symbol;

    // Determine all required timeframes
    const requiredTfs = new Set<string>();
    for (const tf of rules.entryTimeframes ?? ['15m']) requiredTfs.add(tf);
    for (const tf of rules.emergencyExitTimeframes ?? ['1h']) requiredTfs.add(tf);
    requiredTfs.add('1h'); // FVG always needs 1h
    requiredTfs.add('4h'); // FVG always needs 4h

    // Load candles for all required timeframes
    const candleSets: BacktestCandleSet[] = [];
    const extraPadding = 50; // extra candles before start for lookback

    for (const tf of requiredTfs) {
      const candleTf = TF_LABEL_TO_CANDLE_TF[tf];
      if (!candleTf) continue;

      const tfMs = TF_MS[tf] ?? 900_000;
      const paddingMs = tfMs * extraPadding;

      try {
        const candles = await candleLoader.getCandles({
          symbol,
          timeframe: candleTf,
          startTimeMs: run.startTimeMs - paddingMs,
          endTimeMs: run.endTimeMs,
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
    run.marketDataCoverage = {
      requestedFromMs: run.startTimeMs,
      requestedToMs: run.endTimeMs,
      loadedFromMs: Number.isFinite(minLoadedMs) ? minLoadedMs : undefined,
      loadedToMs: Number.isFinite(maxLoadedMs) ? maxLoadedMs : undefined,
    };

    // Run engine
    const result = runBacktestEngine({ run, candleSets, depositUsd });

    // Write results
    run.summary = result.summary;
    run.bySymbol = result.bySymbol;
    run.artifacts = {
      tradeCount: result.trades.length,
      equityCurvePoints: result.equityCurve.length,
      eventCount: result.trades.length,
    };
    run.status = 'completed';
    run.finishedAt = new Date().toISOString();
    run.aiAnalysis = { status: 'idle' };

    logger.info(
      { component: 'backtest-worker', runId, symbol, trades: result.summary.totalTrades, pnl: result.summary.netPnlUsd },
      'backtest run completed',
    );
  } catch (err) {
    run.status = 'failed';
    run.finishedAt = new Date().toISOString();
    run.error = err instanceof Error ? err.message : String(err);

    logger.error(
      { component: 'backtest-worker', runId, err: run.error },
      'backtest run failed',
    );
  } finally {
    activeRunId = null;
    await db.write().catch((writeErr) => {
      logger.error({ component: 'backtest-worker', runId, err: writeErr }, 'failed to persist backtest result');
    });
  }
}
