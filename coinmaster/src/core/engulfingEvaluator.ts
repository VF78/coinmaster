/**
 * engulfingEvaluator.ts
 *
 * Server-side multi-timeframe engulfing signal engine (body-only).
 *
 * Two pattern detectors:
 *   1. Body-only engulfing — current candle body fully engulfs previous candle body
 *   2. Low/High breakout — the "swept" candle's low or high exceeds the extremes
 *      of the previous N candles (configurable, default 30)
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
 * Low breakout: the swept candle's low is below the lowest low
 * of the previous N candles.
 */
export function isLowBreakout(history: Candle[], swept: Candle): boolean {
  if (history.length === 0) return false;
  const minLow = Math.min(...history.map((c) => c.low));
  return swept.low < minLow;
}

/**
 * High breakout: the swept candle's high is above the highest high
 * of the previous N candles.
 */
export function isHighBreakout(history: Candle[], swept: Candle): boolean {
  if (history.length === 0) return false;
  const maxHigh = Math.max(...history.map((c) => c.high));
  return swept.high > maxHigh;
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

  const engulf = candles[candles.length - 1];
  const swept = candles[candles.length - 2];
  const history = candles.slice(candles.length - 2 - lookback, candles.length - 2);

  const confidence = TF_CONFIDENCE[tf] ?? 0.7;

  // Bullish: low breakout on swept + bullish engulfing body
  if (isLowBreakout(history, swept) && isBullishEngulfingBody(swept, engulf)) {
    return {
      detected: true,
      direction: 'bullish',
      timeframe: tf,
      confidence,
      reason: `sweep${lookback}_low_then_bullish_body_engulf_${tf}`,
    };
  }

  // Bearish: high breakout on swept + bearish engulfing body
  if (isHighBreakout(history, swept) && isBearishEngulfingBody(swept, engulf)) {
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
    reason: `no_engulf_trigger_${tf}`,
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
