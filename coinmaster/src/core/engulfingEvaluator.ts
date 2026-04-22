/**
 * engulfingEvaluator.ts
 *
 * Server-side multi-timeframe engulfing signal engine (body-only).
 *
 * Two mandatory pattern detectors (both required):
 *   1. Body-only engulfing — current candle body fully engulfs previous candle body
 *   2. Pair-extreme sweep breakout — low/high extreme of the engulfing pair
 *      (previous + current candle) breaks the extremes of previous N candles
 *      (configurable, default 30)
 *
 * Supports arrays of timeframes (entryTimeframes[], emergencyExitTimeframes[])
 * from TradingRulesSettings.
 */

import type { Candle } from '../exchange/types.js';
import type { TradingRulesTimeframe } from '../shared/dto.js';

// ─── Types ────────────────────────────────────────────────────────────

export interface EngulfingSignal {
  detected: boolean;
  direction: 'bullish' | 'bearish' | null;
  timeframe: TradingRulesTimeframe;
  confidence: number;
  reason: string;
}

export interface MultiTfEngulfingResult {
  entry: EngulfingSignal[];
  exit: EngulfingSignal[];
  anyEntry: boolean;
  anyExit: boolean;
}

export interface EngulfingEvaluatorOptions {
  lookbackCandles: number;
  entryTimeframes: TradingRulesTimeframe[];
  emergencyExitTimeframes: TradingRulesTimeframe[];
}

// ─── Candle body helpers ──────────────────────────────────────────────

export function bodyTop(c: Candle): number {
  return Math.max(c.open, c.close);
}

export function bodyBottom(c: Candle): number {
  return Math.min(c.open, c.close);
}

/**
 * Body-only bullish engulfing:
 * Current candle's body fully wraps the previous candle's body,
 * AND current close > current open (green candle).
 */
export function isBullishEngulfingBody(prev: Candle, curr: Candle): boolean {
  if (curr.close <= curr.open) return false; // must be green
  return bodyBottom(curr) <= bodyBottom(prev) && bodyTop(curr) >= bodyTop(prev);
}

/**
 * Body-only bearish engulfing:
 * Current candle's body fully wraps the previous candle's body,
 * AND current close < current open (red candle).
 */
export function isBearishEngulfingBody(prev: Candle, curr: Candle): boolean {
  if (curr.close >= curr.open) return false; // must be red
  return bodyBottom(curr) <= bodyBottom(prev) && bodyTop(curr) >= bodyTop(prev);
}

/**
 * Pair low-breakout: the minimum low of the engulfing pair (prev + curr)
 * is below the lowest low of the previous N candles.
 */
export function isLowBreakout(history: Candle[], swept: Candle, curr?: Candle): boolean {
  if (history.length === 0) return false;
  const minLow = Math.min(...history.map((c) => c.low));
  const pairLow = curr ? Math.min(swept.low, curr.low) : swept.low;
  return pairLow < minLow;
}

/**
 * Pair high-breakout: the maximum high of the engulfing pair (prev + curr)
 * is above the highest high of the previous N candles.
 */
export function isHighBreakout(history: Candle[], swept: Candle, curr?: Candle): boolean {
  if (history.length === 0) return false;
  const maxHigh = Math.max(...history.map((c) => c.high));
  const pairHigh = curr ? Math.max(swept.high, curr.high) : swept.high;
  return pairHigh > maxHigh;
}

// ─── Confidence by timeframe ──────────────────────────────────────────

const TF_CONFIDENCE: Record<TradingRulesTimeframe, number> = {
  '5m': 0.95,
  '15m': 0.9,
  '1h': 0.85,
  '4h': 0.8,
};

// ─── Single-timeframe evaluator ───────────────────────────────────────

/**
 * Evaluate a single timeframe's candles for engulfing + breakout.
 *
 * Requires at least (lookback + 2) candles:
 *   - lookback candles for the history window
 *   - 1 "swept" candle (the one that may break out)
 *   - 1 "engulf" candle (the current closed candle)
 */
export function evaluateBodyEngulfingTimeframe(
  candles: Candle[],
  tf: TradingRulesTimeframe,
): EngulfingSignal {
  if (candles.length < 2) {
    return {
      detected: false,
      direction: null,
      timeframe: tf,
      confidence: 0.1,
      reason: `insufficient_candles_${candles.length}_need_2`,
    };
  }

  const curr = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const confidence = TF_CONFIDENCE[tf] ?? 0.7;
  const bullishBody = isBullishEngulfingBody(prev, curr);
  const bearishBody = isBearishEngulfingBody(prev, curr);

  if (bullishBody) {
    return {
      detected: true,
      direction: 'bullish',
      timeframe: tf,
      confidence,
      reason: `bullish_body_engulf_${tf}`,
    };
  }

  if (bearishBody) {
    return {
      detected: true,
      direction: 'bearish',
      timeframe: tf,
      confidence,
      reason: `bearish_body_engulf_${tf}`,
    };
  }

  return {
    detected: false,
    direction: null,
    timeframe: tf,
    confidence: 0.3,
    reason: `no_body_engulf_${tf}`,
  };
}

export function evaluateTimeframe(
  candles: Candle[],
  tf: TradingRulesTimeframe,
  lookback: number,
): EngulfingSignal {
  const minRequired = lookback + 2;

  if (candles.length < minRequired) {
    return {
      detected: false,
      direction: null,
      timeframe: tf,
      confidence: 0.1,
      reason: `insufficient_candles_${candles.length}_need_${minRequired}`,
    };
  }

  const curr = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const history = candles.slice(candles.length - 2 - lookback, candles.length - 2);

  const confidence = TF_CONFIDENCE[tf] ?? 0.7;
  const bullishBody = isBullishEngulfingBody(prev, curr);
  const bearishBody = isBearishEngulfingBody(prev, curr);
  const lowBreakout = isLowBreakout(history, prev, curr);
  const highBreakout = isHighBreakout(history, prev, curr);

  if (bullishBody && lowBreakout) {
    return {
      detected: true,
      direction: 'bullish',
      timeframe: tf,
      confidence,
      reason: `sweep${lookback}_low_then_bullish_body_engulf_${tf}`,
    };
  }

  if (bearishBody && highBreakout) {
    return {
      detected: true,
      direction: 'bearish',
      timeframe: tf,
      confidence,
      reason: `sweep${lookback}_high_then_bearish_body_engulf_${tf}`,
    };
  }

  return {
    detected: false,
    direction: null,
    timeframe: tf,
    confidence: 0.3,
    reason: `no_engulf_or_sweep_trigger_${tf}`,
  };
}

// ─── Multi-timeframe evaluator ────────────────────────────────────────

/**
 * Evaluate engulfing signals across multiple entry and exit timeframes.
 *
 * @param candlesByTf - Map from timeframe label to closed candles array
 * @param opts        - lookback + timeframe arrays from TradingRulesSettings
 */
export function evaluateMultiTf(
  candlesByTf: Map<TradingRulesTimeframe, Candle[]>,
  opts: EngulfingEvaluatorOptions,
): MultiTfEngulfingResult {
  const entry: EngulfingSignal[] = [];
  const exit: EngulfingSignal[] = [];

  for (const tf of opts.entryTimeframes) {
    const candles = candlesByTf.get(tf) ?? [];
    entry.push(evaluateTimeframe(candles, tf, opts.lookbackCandles));
  }

  for (const tf of opts.emergencyExitTimeframes) {
    const candles = candlesByTf.get(tf) ?? [];
    exit.push(evaluateTimeframe(candles, tf, opts.lookbackCandles));
  }

  return {
    entry,
    exit,
    anyEntry: entry.some((s) => s.detected),
    anyExit: exit.some((s) => s.detected),
  };
}
