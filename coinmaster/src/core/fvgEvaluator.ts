import type { Candle } from '../exchange/types.js';
import { evaluateTimeframe } from './engulfingEvaluator.js';
import type { FvgLowerTfConfirmation, FvgTimeframe, TradingRulesTimeframe } from '../shared/dto.js';

export type { FvgTimeframe } from '../shared/dto.js';

export interface FvgZone {
  direction: 'bullish' | 'bearish';
  top: number;
  bottom: number;
  midpoint: number;
  width: number;
  widthPct: number;
  candleTimestamp: string;
  timeframe: FvgTimeframe;
  completionIndex?: number;
}

export interface FvgQualificationSettings {
  minWidthPct: number;
  requireSweepDisplacement: boolean;
  sweepLookbackCandles: number;
  displacementMinBodyPct: number;
  requireFirstTouch: boolean;
  requireLowerTfConfirmation: boolean;
  lowerTfConfirmations: Record<FvgTimeframe, FvgLowerTfConfirmation>;
  engulfingLookbackCandles: number;
}

export interface FvgEvaluationOptions {
  currentPrice: number;
  currentTimeMs?: number;
  retracePct: number;
  lookback?: number;
  qualification: FvgQualificationSettings;
  lowerTfCandles?: Partial<Record<TradingRulesTimeframe, Candle[]>>;
}

export interface FvgSignal {
  detected: boolean;
  direction: 'bullish' | 'bearish' | null;
  zone: FvgZone | null;
  triggerPrice: number | null;
  currentPrice: number;
  timeframe: FvgTimeframe;
  reason: string;
  touchTimestamp?: string;
  lowerTfConfirmationTimeframe?: TradingRulesTimeframe;
}

export function detectStructureBreak(
  candles: Candle[],
  lookback: number = 20,
): 'bullish' | 'bearish' | null {
  if (candles.length < lookback + 1) return null;

  const history = candles.slice(0, -1);
  const last = history[history.length - 1];
  const window = history.slice(-lookback - 1, -1);

  if (window.length === 0) return null;

  const swingHigh = Math.max(...window.map((c) => c.high));
  const swingLow = Math.min(...window.map((c) => c.low));

  if (last.close > swingHigh) return 'bullish';
  if (last.close < swingLow) return 'bearish';
  return null;
}

export function detectFvgZones(
  candles: Candle[],
  timeframe: FvgTimeframe,
  lookback: number = 10,
  minWidthPct: number = 0,
): FvgZone[] {
  const zones: FvgZone[] = [];
  if (candles.length < 3) return zones;

  const closed = candles.slice(0, -1);
  const start = Math.max(2, closed.length - lookback);

  for (let i = start; i < closed.length; i++) {
    const c0 = closed[i - 2];
    const c2 = closed[i];

    if (c0.high < c2.low) {
      const bottom = c0.high;
      const top = c2.low;
      const width = top - bottom;
      const referencePrice = Math.max(Math.abs((top + bottom) / 2), Number.EPSILON);
      const widthPct = (width / referencePrice) * 100;
      if (widthPct >= minWidthPct) {
        zones.push({
          direction: 'bullish',
          top,
          bottom,
          midpoint: (top + bottom) / 2,
          width,
          widthPct,
          candleTimestamp: c2.timestamp,
          timeframe,
          completionIndex: i,
        });
      }
    }

    if (c0.low > c2.high) {
      const bottom = c2.high;
      const top = c0.low;
      const width = top - bottom;
      const referencePrice = Math.max(Math.abs((top + bottom) / 2), Number.EPSILON);
      const widthPct = (width / referencePrice) * 100;
      if (widthPct >= minWidthPct) {
        zones.push({
          direction: 'bearish',
          top,
          bottom,
          midpoint: (top + bottom) / 2,
          width,
          widthPct,
          candleTimestamp: c2.timestamp,
          timeframe,
          completionIndex: i,
        });
      }
    }
  }

  return zones;
}

export function computeRetraceTrigger(zone: FvgZone, fvgRetracePct: number): number {
  const range = zone.top - zone.bottom;
  if (zone.direction === 'bullish') {
    return zone.top - range * (fvgRetracePct / 100);
  }
  return zone.bottom + range * (fvgRetracePct / 100);
}

export function isFvgRetracedToLevel(
  zone: FvgZone,
  currentPrice: number,
  fvgRetracePct: number,
): boolean {
  const trigger = computeRetraceTrigger(zone, fvgRetracePct);
  if (zone.direction === 'bullish') {
    return currentPrice <= trigger && currentPrice >= zone.bottom;
  }
  return currentPrice >= trigger && currentPrice <= zone.top;
}

function candleTouchesZone(candle: Candle, zone: FvgZone): boolean {
  return candle.low <= zone.top && candle.high >= zone.bottom;
}

function bodyPct(candle: Candle): number {
  const range = Math.max(candle.high - candle.low, Number.EPSILON);
  return (Math.abs(candle.close - candle.open) / range) * 100;
}

function qualifiesSweepDisplacement(zone: FvgZone, candles: Candle[], settings: FvgQualificationSettings): boolean {
  const completionIndex = zone.completionIndex;
  if (!settings.requireSweepDisplacement) return true;
  if (completionIndex === undefined || completionIndex < 2) return false;

  const closed = candles.slice(0, -1);
  const c0 = closed[completionIndex - 2];
  const c1 = closed[completionIndex - 1];
  const c2 = closed[completionIndex];
  if (!c0 || !c1 || !c2) return false;

  const historyStart = Math.max(0, completionIndex - 2 - settings.sweepLookbackCandles);
  const history = closed.slice(historyStart, completionIndex - 2);
  if (history.length === 0) return false;

  const sweptLow = Math.min(c0.low, c1.low, c2.low) < Math.min(...history.map((c) => c.low));
  const sweptHigh = Math.max(c0.high, c1.high, c2.high) > Math.max(...history.map((c) => c.high));
  const displacementPct = Math.max(bodyPct(c1), bodyPct(c2));

  if (zone.direction === 'bullish') {
    return sweptLow
      && displacementPct >= settings.displacementMinBodyPct
      && c1.close > c1.open
      && c2.close >= c1.close;
  }

  return sweptHigh
    && displacementPct >= settings.displacementMinBodyPct
    && c1.close < c1.open
    && c2.close <= c1.close;
}

function findFirstTouch(zone: FvgZone, candles: Candle[], currentPrice: number, currentTimeMs?: number): string | null {
  const completionIndex = zone.completionIndex;
  if (completionIndex === undefined) return null;
  const closed = candles.slice(0, -1);
  for (let i = completionIndex + 1; i < closed.length; i++) {
    if (candleTouchesZone(closed[i], zone)) return closed[i].timestamp;
  }
  if (isFvgRetracedToLevel(zone, currentPrice, 100) || (currentPrice >= zone.bottom && currentPrice <= zone.top)) {
    return currentTimeMs ? new Date(currentTimeMs).toISOString() : null;
  }
  return null;
}

function qualifiesFirstTouch(zone: FvgZone, candles: Candle[], currentPrice: number, currentTimeMs?: number): { ok: boolean; touchTimestamp: string | null } {
  const touchTimestamp = findFirstTouch(zone, candles, currentPrice, currentTimeMs);
  if (!touchTimestamp) return { ok: true, touchTimestamp: null };
  if (!isFvgRetracedToLevel(zone, currentPrice, 100) && !(currentPrice >= zone.bottom && currentPrice <= zone.top)) {
    return { ok: false, touchTimestamp };
  }
  const closed = candles.slice(0, -1);
  const priorTouches = closed.filter((c) => Date.parse(c.timestamp) < Date.parse(touchTimestamp) && candleTouchesZone(c, zone));
  return { ok: priorTouches.length === 0, touchTimestamp };
}

function findLowerTfConfirmation(
  direction: 'bullish' | 'bearish',
  confirmationTf: TradingRulesTimeframe,
  lowerTfCandles: Candle[],
  touchTimestamp: string,
  lookback: number,
): string | null {
  const touchMs = Date.parse(touchTimestamp);
  for (let i = Math.max(0, lookback + 1); i < lowerTfCandles.length; i++) {
    const candle = lowerTfCandles[i];
    if (Date.parse(candle.timestamp) < touchMs) continue;
    const signal = evaluateTimeframe(lowerTfCandles.slice(0, i + 1), confirmationTf, lookback);
    if (!signal.detected || !signal.direction) continue;
    if ((direction === 'bullish' && signal.direction === 'bullish') || (direction === 'bearish' && signal.direction === 'bearish')) {
      return candle.timestamp;
    }
  }
  return null;
}

export function evaluateFvg(
  candles: Candle[],
  timeframe: FvgTimeframe,
  options: FvgEvaluationOptions,
): FvgSignal {
  const currentPrice = options.currentPrice;
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

  const lookback = options.lookback ?? 10;
  const structureBreak = detectStructureBreak(candles, 20);
  const allZones = detectFvgZones(candles, timeframe, lookback, options.qualification.minWidthPct);
  if (allZones.length === 0) {
    return noSignal(`no_fvg_zones_in_lookback_min_width_${options.qualification.minWidthPct}pct`);
  }

  const zones = structureBreak
    ? allZones.filter((z) => z.direction === structureBreak)
    : allZones;

  if (zones.length === 0) {
    return noSignal(`no_fvg_zones_matching_structure_break_${structureBreak}`);
  }

  for (const zone of [...zones].reverse()) {
    if (!qualifiesSweepDisplacement(zone, candles, options.qualification)) {
      continue;
    }
    if (!isFvgRetracedToLevel(zone, currentPrice, options.retracePct)) {
      continue;
    }

    let touchTimestamp: string | null = null;
    if (options.qualification.requireFirstTouch) {
      const firstTouch = qualifiesFirstTouch(zone, candles, currentPrice, options.currentTimeMs);
      if (!firstTouch.ok) continue;
      touchTimestamp = firstTouch.touchTimestamp;
    } else {
      touchTimestamp = findFirstTouch(zone, candles, currentPrice, options.currentTimeMs);
    }

    let lowerTfConfirmationTimeframe: TradingRulesTimeframe | undefined;
    if (options.qualification.requireLowerTfConfirmation) {
      const mapped = options.qualification.lowerTfConfirmations[timeframe];
      if (!mapped || mapped === 'off') {
        return noSignal(`lower_tf_confirmation_mapping_off_${timeframe}`);
      }
      const lowerTfCandles = options.lowerTfCandles?.[mapped];
      if (!lowerTfCandles?.length) {
        return noSignal(`lower_tf_confirmation_candles_missing_${timeframe}_${mapped}`);
      }
      if (!touchTimestamp) {
        return noSignal(`lower_tf_confirmation_touch_missing_${timeframe}`);
      }
      const confirmationTs = findLowerTfConfirmation(
        zone.direction,
        mapped,
        lowerTfCandles,
        touchTimestamp,
        options.qualification.engulfingLookbackCandles,
      );
      if (!confirmationTs) {
        continue;
      }
      lowerTfConfirmationTimeframe = mapped;
    }

    const triggerPrice = computeRetraceTrigger(zone, options.retracePct);
    return {
      detected: true,
      direction: zone.direction,
      zone,
      triggerPrice: +triggerPrice.toFixed(8),
      currentPrice,
      timeframe,
      reason: [
        `fvg_retrace_${options.retracePct}pct`,
        `minwidth_${options.qualification.minWidthPct}pct`,
        zone.direction,
        timeframe,
        structureBreak ? `bos_${structureBreak}` : null,
        options.qualification.requireSweepDisplacement ? 'sweep_displacement' : null,
        options.qualification.requireFirstTouch ? 'first_touch' : null,
        lowerTfConfirmationTimeframe ? `ltf_confirm_${lowerTfConfirmationTimeframe}` : null,
      ].filter(Boolean).join('_'),
      touchTimestamp: touchTimestamp ?? undefined,
      lowerTfConfirmationTimeframe,
    };
  }

  if (options.qualification.requireLowerTfConfirmation) {
    return noSignal('price_in_fvg_without_lower_tf_confirmation');
  }
  if (options.qualification.requireFirstTouch) {
    return noSignal('price_not_in_fvg_retrace_zone_or_zone_already_mitigated');
  }
  if (options.qualification.requireSweepDisplacement) {
    return noSignal('price_not_in_fvg_retrace_zone_or_sweep_displacement_missing');
  }
  return noSignal('price_not_in_fvg_retrace_zone');
}
