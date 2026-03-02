/**
 * fvgEvaluator.ts
 *
 * Fair Value Gap (FVG) detection and retrace-trigger engine.
 *
 * FVG = 3-candle pattern where the middle candle leaves a price gap:
 *   Bullish FVG: candle[i-2].high < candle[i].low  → gap above c[i-2], below c[i]
 *   Bearish FVG: candle[i-2].low  > candle[i].high → gap below c[i-2], above c[i]
 *
 * Retrace entry trigger (fvgRetracePct):
 *   Bullish FVG: price falling into gap — fire when price <= zone.top - range*(pct/100)
 *   Bearish FVG: price rising into gap — fire when price >= zone.bottom + range*(pct/100)
 *
 * Structure break context:
 *   Filters FVG zones to only those aligned with recent price structure break
 *   (bullish BOS → only trade bullish FVGs; bearish BOS → only bearish FVGs).
 *   If no structure break detected, all FVG zones are eligible.
 *
 * Timeframe scope: 1H / 4H only (per spec).
 */

import type { Candle } from '../exchange/types.js';

// ─── Types ────────────────────────────────────────────────────────────

export type FvgTimeframe = '1h' | '4h';

export interface FvgZone {
  direction: 'bullish' | 'bearish';
  /** Upper boundary of the gap */
  top: number;
  /** Lower boundary of the gap */
  bottom: number;
  /** Midpoint of the gap */
  midpoint: number;
  /** ISO timestamp of the 3rd candle that completed the FVG */
  candleTimestamp: string;
  timeframe: FvgTimeframe;
}

export interface FvgSignal {
  detected: boolean;
  direction: 'bullish' | 'bearish' | null;
  zone: FvgZone | null;
  /** Exact price level that triggered the entry */
  triggerPrice: number | null;
  currentPrice: number;
  timeframe: FvgTimeframe;
  /** Human-readable reason string for audit */
  reason: string;
}

// ─── Structure Break ──────────────────────────────────────────────────

/**
 * Detect the most recent market structure break (BOS):
 *   'bullish' — last closed candle breaks above the swing high of the prior `lookback` candles
 *   'bearish' — last closed candle breaks below the swing low of the prior `lookback` candles
 *   null      — no confirmed break
 *
 * Requires at least (lookback + 1) candles.
 */
export function detectStructureBreak(
  candles: Candle[],
  lookback: number = 20,
): 'bullish' | 'bearish' | null {
  if (candles.length < lookback + 1) return null;

  const history = candles.slice(0, -1); // all but last (still-forming) candle
  const last = history[history.length - 1]; // last confirmed closed candle
  const window = history.slice(-lookback - 1, -1); // prior N candles

  if (window.length === 0) return null;

  const swingHigh = Math.max(...window.map((c) => c.high));
  const swingLow = Math.min(...window.map((c) => c.low));

  if (last.close > swingHigh) return 'bullish';
  if (last.close < swingLow) return 'bearish';
  return null;
}

// ─── FVG Detection ────────────────────────────────────────────────────

/**
 * Detect all Fair Value Gap zones within the last `lookback` candles.
 * Returns zones sorted oldest-first.
 */
export function detectFvgZones(
  candles: Candle[],
  timeframe: FvgTimeframe,
  lookback: number = 10,
): FvgZone[] {
  const zones: FvgZone[] = [];
  if (candles.length < 3) return zones;

  // Scan within lookback window (only closed candles — exclude last if forming)
  const closed = candles.slice(0, -1); // exclude last potentially-open candle
  const start = Math.max(2, closed.length - lookback);

  for (let i = start; i < closed.length; i++) {
    const c0 = closed[i - 2]; // first candle
    const c2 = closed[i];     // third candle

    // Bullish FVG: gap between high of c0 and low of c2
    if (c0.high < c2.low) {
      const bottom = c0.high;
      const top = c2.low;
      zones.push({
        direction: 'bullish',
        top,
        bottom,
        midpoint: (top + bottom) / 2,
        candleTimestamp: c2.timestamp,
        timeframe,
      });
    }

    // Bearish FVG: gap between low of c0 and high of c2
    if (c0.low > c2.high) {
      const bottom = c2.high;
      const top = c0.low;
      zones.push({
        direction: 'bearish',
        top,
        bottom,
        midpoint: (top + bottom) / 2,
        candleTimestamp: c2.timestamp,
        timeframe,
      });
    }
  }

  return zones;
}

// ─── Retrace Trigger ──────────────────────────────────────────────────

/**
 * Compute the price level at which a retrace triggers entry.
 *
 * fvgRetracePct = 50 → trigger at 50% into the gap from the gap edge:
 *   Bullish: price falling into gap → trigger = zone.top - range * (pct/100)
 *   Bearish: price rising into gap  → trigger = zone.bottom + range * (pct/100)
 */
export function computeRetraceTrigger(zone: FvgZone, fvgRetracePct: number): number {
  const range = zone.top - zone.bottom;
  if (zone.direction === 'bullish') {
    return zone.top - range * (fvgRetracePct / 100);
  }
  return zone.bottom + range * (fvgRetracePct / 100);
}

/**
 * Check if currentPrice has entered the retrace trigger zone.
 */
export function isFvgRetracedToLevel(
  zone: FvgZone,
  currentPrice: number,
  fvgRetracePct: number,
): boolean {
  const trigger = computeRetraceTrigger(zone, fvgRetracePct);
  if (zone.direction === 'bullish') {
    // Price must retrace DOWN to trigger level (price is below trigger)
    return currentPrice <= trigger && currentPrice >= zone.bottom;
  }
  // Price must retrace UP to trigger level (price is above trigger)
  return currentPrice >= trigger && currentPrice <= zone.top;
}

// ─── Top-level evaluator ──────────────────────────────────────────────

/**
 * Full FVG signal evaluation for a single timeframe.
 *
 * Steps:
 *  1. Detect structure break context (filters zone direction)
 *  2. Detect recent FVG zones within lookback window
 *  3. For each zone (newest first), check if currentPrice is in the retrace trigger zone
 *  4. Return first matching signal
 *
 * @param candles       Closed candles for the timeframe
 * @param timeframe     '1h' or '4h'
 * @param currentPrice  Latest mid price
 * @param fvgRetracePct Configured retrace level (10–90)
 * @param lookback      How many candles back to scan for FVG zones (default 10)
 */
export function evaluateFvg(
  candles: Candle[],
  timeframe: FvgTimeframe,
  currentPrice: number,
  fvgRetracePct: number,
  lookback: number = 10,
): FvgSignal {
  const noSignal = (reason: string): FvgSignal => ({
    detected: false,
    direction: null,
    zone: null,
    triggerPrice: null,
    currentPrice,
    timeframe,
    reason,
  });

  if (candles.length < 3) {
    return noSignal(`insufficient_candles_${candles.length}_need_3`);
  }

  // 1. Structure break context
  const structureBreak = detectStructureBreak(candles, 20);

  // 2. Detect FVG zones
  const allZones = detectFvgZones(candles, timeframe, lookback);
  if (allZones.length === 0) {
    return noSignal('no_fvg_zones_in_lookback');
  }

  // 3. Filter by structure break (if available)
  const zones = structureBreak
    ? allZones.filter((z) => z.direction === structureBreak)
    : allZones;

  if (zones.length === 0) {
    return noSignal(`no_fvg_zones_matching_structure_break_${structureBreak}`);
  }

  // 4. Check newest zone first
  for (const zone of [...zones].reverse()) {
    if (isFvgRetracedToLevel(zone, currentPrice, fvgRetracePct)) {
      const triggerPrice = computeRetraceTrigger(zone, fvgRetracePct);
      return {
        detected: true,
        direction: zone.direction,
        zone,
        triggerPrice: +triggerPrice.toFixed(8),
        currentPrice,
        timeframe,
        reason: `fvg_retrace_${fvgRetracePct}pct_${zone.direction}_${timeframe}${structureBreak ? `_bos_${structureBreak}` : ''}`,
      };
    }
  }

  return noSignal('price_not_in_fvg_retrace_zone');
}
