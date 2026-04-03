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
import type {
  BacktestRun,
  BacktestRunSummary,
  BacktestRunSymbolStats,
  OptimizationParamRange,
  OptimizationResult,
  TradingRulesSettings,
} from '../shared/dto.js';
import type { BacktestCandleLoader } from './backtestWorker.js';
import type { CandleTimeframe } from '../exchange/types.js';

// ─── Constants ────────────────────────────────────────────────────────

const MAX_CANDIDATES = 5000;
const YIELD_EVERY_N = 5; // yield to event loop every N candidates
const YIELD_MS = 2; // ms to sleep on yield
const INTEGER_PARAMS = new Set(['maxLeverage', 'engulfingLookbackCandles']);

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
 * Supports: slPct, tpLevels[0], tpLevels[1], tpLevels[2], maxLeverage,
 * engulfingLookbackCandles, fvgRetrace, fvgMinWidthPct, exitClosePct, dailyDrawdown.
 */
function applyParamToRules(rules: TradingRulesSettings, param: string, value: number): void {
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
}

function extractParamValue(rules: TradingRulesSettings, param: string): number | undefined {
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
    values: generateSteps(r).map((v) => (INTEGER_PARAMS.has(r.param) ? Math.round(v) : v)),
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

  activeOptimizationId = optimizationId;
  opt.status = 'running';
  opt.startedAt = new Date().toISOString();
  await db.write();

  try {
    const baseRules = opt.baseRulesSnapshot;
    const symbol = opt.symbol;

    // Determine all required timeframes (same logic as backtestWorker)
    const requiredTfs = new Set<string>();
    for (const tf of baseRules.entryTimeframes ?? ['15m']) requiredTfs.add(tf);
    for (const tf of baseRules.emergencyExitTimeframes ?? ['1h']) requiredTfs.add(tf);
    requiredTfs.add('1h');
    requiredTfs.add('4h');

    // Load candles once (shared across all candidates)
    const candleSets: BacktestCandleSet[] = [];
    const extraPadding = 50;

    for (const tf of requiredTfs) {
      const candleTf = TF_LABEL_TO_CANDLE_TF[tf];
      if (!candleTf) continue;

      const tfMs = TF_MS[tf] ?? 900_000;
      const paddingMs = tfMs * extraPadding;

      try {
        const candles = await candleLoader.getCandles({
          symbol,
          timeframe: candleTf,
          startTimeMs: opt.startTimeMs - paddingMs,
          endTimeMs: opt.endTimeMs,
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
    }

    if (candleSets.length === 0) {
      throw new Error('no_candle_data_loaded');
    }

    // Generate candidates
    const { candidates, gridCandidates } = generateCandidates(opt.paramRanges);
    opt.searchSpaceCandidates = gridCandidates;
    opt.totalCandidates = candidates.length;
    opt.evaluatedCandidates = 0;
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

      // Build a synthetic BacktestRun for the engine
      const syntheticRun: BacktestRun = {
        id: `opt_${optimizationId}_${i}`,
        status: 'running',
        symbol,
        biasMode: opt.biasMode,
        createdAt: new Date().toISOString(),
        startTimeMs: opt.startTimeMs,
        endTimeMs: opt.endTimeMs,
        engineVersion: opt.engineVersion,
        engineCommit: opt.engineCommit,
        rulesSnapshot: candidateRules,
        bySymbol: [],
        aiAnalysis: { status: 'idle' },
      };

      try {
        const result = runBacktestEngine({
          run: syntheticRun,
          candleSets,
          depositUsd,
        });

        if (result.summary.netPnlUsd > bestPnl) {
          bestPnl = result.summary.netPnlUsd;
          bestSummary = result.summary;
          bestBySymbol = result.bySymbol;
          bestParamCombo = combo;
        }
      } catch (err) {
        // Skip failed candidates silently
        logger.debug(
          { component: 'optimizer', optimizationId, candidate: i, err },
          'candidate evaluation failed, skipping',
        );
      }

      opt.evaluatedCandidates = i + 1;

      // Yield to event loop periodically
      if ((i + 1) % YIELD_EVERY_N === 0) {
        await sleep(YIELD_MS);
      }

      // Progress save every 500 candidates
      if ((i + 1) % 500 === 0) {
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

    opt.status = 'completed';
    opt.finishedAt = new Date().toISOString();

    logger.info(
      { component: 'optimizer', optimizationId, symbol, evaluated: opt.evaluatedCandidates, bestPnl: bestSummary?.netPnlUsd },
      'optimization completed',
    );
  } catch (err) {
    opt.status = 'failed';
    opt.finishedAt = new Date().toISOString();
    opt.error = err instanceof Error ? err.message : String(err);

    logger.error(
      { component: 'optimizer', optimizationId, err: opt.error },
      'optimization failed',
    );
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

  return {
    id: nanoid(),
    status: 'queued',
    sourceRunId: sourceRun.id,
    symbol: sourceRun.symbol,
    biasMode: sourceRun.biasMode,
    startTimeMs: sourceRun.startTimeMs,
    endTimeMs: sourceRun.endTimeMs,
    baseRulesSnapshot: JSON.parse(JSON.stringify(sourceRun.rulesSnapshot)),
    paramRanges,
    createdAt: new Date().toISOString(),
    searchSpaceCandidates: 0,
    totalCandidates: 0,
    evaluatedCandidates: 0,
    engineVersion: engine.version,
    engineCommit: engine.commit,
  };
}
