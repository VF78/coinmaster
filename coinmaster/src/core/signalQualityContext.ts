/**
 * signalQualityContext.ts
 *
 * Deterministic signal-quality helpers that the live Trading Rules monitors and
 * the canonical backtest engine share. The module owns the "context" filters
 * that statistically separate "pattern on noise" from "pattern in regime":
 *
 *   - EMA / ATR / ADX (Wilder's smoothing) calculated in TypeScript so the
 *     live decision path stays free of TA-Lib / Python.
 *   - Higher-timeframe regime direction from EMA slope plus ADX/ATR.
 *   - Engulfing / FVG impulse displacement quality (body or range vs ATR,
 *     close in upper/lower quartile of the candle range).
 *   - Expected reward-to-risk for an entry given the configured TP/SL plan.
 *
 * The functions are pure, take only `Candle[]` plus numeric thresholds, and
 * return either a number, a small struct, or an `evaluateEntryQuality` verdict.
 * No exchange calls, no logging, no side effects — safe to call from monitors,
 * tests, or backtest workers.
 */
import type { Candle } from '../exchange/types.js';
import type { TradeSide, TradingRulesTimeframe } from '../shared/dto.js';

// ─── EMA / ATR / ADX ──────────────────────────────────────────────────

/**
 * Exponential Moving Average. Returns the EMA *series* (one value per input).
 * Seed is the simple average of the first `period` values; values before seed
 * are filled with `NaN` so callers can detect insufficient data.
 */
export function computeEma(values: number[], period: number): number[] {
  const out: number[] = new Array(values.length).fill(Number.NaN);
  if (period <= 0 || values.length < period) return out;
  const k = 2 / (period + 1);
  let seed = 0;
  for (let i = 0; i < period; i++) seed += values[i];
  out[period - 1] = seed / period;
  for (let i = period; i < values.length; i++) {
    out[i] = values[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

function trueRange(prev: Candle, curr: Candle): number {
  const a = curr.high - curr.low;
  const b = Math.abs(curr.high - prev.close);
  const c = Math.abs(curr.low - prev.close);
  return Math.max(a, b, c);
}

/**
 * Average True Range using Wilder's smoothing. Returns one value per candle;
 * indexes [0..period-1] are NaN because the seed needs `period` true-ranges.
 */
export function computeAtr(candles: Candle[], period: number): number[] {
  const out: number[] = new Array(candles.length).fill(Number.NaN);
  if (period <= 0 || candles.length < period + 1) return out;

  const trs: number[] = new Array(candles.length).fill(Number.NaN);
  for (let i = 1; i < candles.length; i++) trs[i] = trueRange(candles[i - 1], candles[i]);

  let seed = 0;
  for (let i = 1; i <= period; i++) seed += trs[i];
  out[period] = seed / period;
  for (let i = period + 1; i < candles.length; i++) {
    out[i] = (out[i - 1] * (period - 1) + trs[i]) / period;
  }
  return out;
}

/**
 * Average Directional Index using Wilder's smoothing. Returns the ADX series;
 * the first `2*period` values are NaN (period for the +DI/-DI smoothing, then
 * another period for the ADX seed average).
 */
export function computeAdx(candles: Candle[], period: number): number[] {
  const out: number[] = new Array(candles.length).fill(Number.NaN);
  if (period <= 0 || candles.length < period * 2) return out;

  const tr: number[] = new Array(candles.length).fill(0);
  const plusDm: number[] = new Array(candles.length).fill(0);
  const minusDm: number[] = new Array(candles.length).fill(0);

  for (let i = 1; i < candles.length; i++) {
    const prev = candles[i - 1];
    const curr = candles[i];
    tr[i] = trueRange(prev, curr);
    const upMove = curr.high - prev.high;
    const downMove = prev.low - curr.low;
    plusDm[i] = upMove > downMove && upMove > 0 ? upMove : 0;
    minusDm[i] = downMove > upMove && downMove > 0 ? downMove : 0;
  }

  // Smoothed accumulators (Wilder)
  let trSum = 0;
  let plusSum = 0;
  let minusSum = 0;
  for (let i = 1; i <= period; i++) {
    trSum += tr[i];
    plusSum += plusDm[i];
    minusSum += minusDm[i];
  }

  const dx: number[] = new Array(candles.length).fill(Number.NaN);
  const computeDx = (plus: number, minus: number, trVal: number): number => {
    if (trVal <= 0) return 0;
    const plusDi = (100 * plus) / trVal;
    const minusDi = (100 * minus) / trVal;
    const denom = plusDi + minusDi;
    if (denom <= 0) return 0;
    return (100 * Math.abs(plusDi - minusDi)) / denom;
  };

  dx[period] = computeDx(plusSum, minusSum, trSum);
  for (let i = period + 1; i < candles.length; i++) {
    trSum = trSum - trSum / period + tr[i];
    plusSum = plusSum - plusSum / period + plusDm[i];
    minusSum = minusSum - minusSum / period + minusDm[i];
    dx[i] = computeDx(plusSum, minusSum, trSum);
  }

  // Seed ADX with a simple average of the first `period` DX values.
  // With 0-based candle indexes, the first ADX value lands at 2*period-1.
  const adxSeedEnd = period * 2 - 1;
  if (adxSeedEnd >= candles.length) return out;
  let adxSeed = 0;
  for (let i = period; i <= adxSeedEnd; i++) adxSeed += dx[i];
  out[adxSeedEnd] = adxSeed / period;
  for (let i = adxSeedEnd + 1; i < candles.length; i++) {
    out[i] = (out[i - 1] * (period - 1) + dx[i]) / period;
  }
  return out;
}

// ─── Regime direction ─────────────────────────────────────────────────

export type RegimeDirection = 'long' | 'short' | 'neutral';

export interface RegimeAssessment {
  direction: RegimeDirection;
  emaFast: number;
  emaSlow: number;
  emaSlope: number;
  adx: number;
  atr: number;
  hasEnoughData: boolean;
}

/**
 * Classify the higher-timeframe regime using a fast/slow EMA crossover plus an
 * ADX strength gate. `neutral` is returned when:
 *   - data is too short, or
 *   - ADX is below `adxMin` (chop), or
 *   - the slow EMA slope is flat.
 */
export function assessRegime(
  candles: Candle[],
  opts: { fastPeriod?: number; slowPeriod?: number; adxPeriod?: number; adxMin: number } & Record<string, unknown>,
): RegimeAssessment {
  const fastPeriod = Math.max(2, Math.round(Number(opts.fastPeriod ?? 21)));
  const slowPeriod = Math.max(fastPeriod + 1, Math.round(Number(opts.slowPeriod ?? 55)));
  const adxPeriod = Math.max(2, Math.round(Number(opts.adxPeriod ?? 14)));
  const adxMin = Number(opts.adxMin ?? 0);

  const closes = candles.map((c) => c.close);
  const emaFast = computeEma(closes, fastPeriod);
  const emaSlow = computeEma(closes, slowPeriod);
  const adx = computeAdx(candles, adxPeriod);
  const atr = computeAtr(candles, adxPeriod);

  const last = candles.length - 1;
  if (last < slowPeriod || last < adxPeriod * 2 - 1) {
    return {
      direction: 'neutral',
      emaFast: Number.NaN,
      emaSlow: Number.NaN,
      emaSlope: Number.NaN,
      adx: Number.NaN,
      atr: Number.NaN,
      hasEnoughData: false,
    };
  }

  const fast = emaFast[last];
  const slow = emaSlow[last];
  const slowPrev = emaSlow[Math.max(0, last - 3)];
  const slope = Number.isFinite(slowPrev) ? slow - slowPrev : 0;
  const adxVal = adx[last];
  const atrVal = atr[last];

  if (!Number.isFinite(fast) || !Number.isFinite(slow) || !Number.isFinite(adxVal)) {
    return {
      direction: 'neutral',
      emaFast: fast,
      emaSlow: slow,
      emaSlope: slope,
      adx: adxVal,
      atr: atrVal,
      hasEnoughData: false,
    };
  }

  let direction: RegimeDirection = 'neutral';
  if (adxVal >= adxMin) {
    if (fast > slow && slope >= 0) direction = 'long';
    else if (fast < slow && slope <= 0) direction = 'short';
  }

  return {
    direction,
    emaFast: fast,
    emaSlow: slow,
    emaSlope: slope,
    adx: adxVal,
    atr: atrVal,
    hasEnoughData: true,
  };
}

// ─── Displacement quality ─────────────────────────────────────────────

export interface DisplacementMetrics {
  body: number;
  range: number;
  bodyAtrRatio: number;
  closePosition: number; // 0..1 along the candle range
  meetsBody: boolean;
  meetsClose: boolean;
}

/**
 * Score a single candle's displacement quality for an entry candidate.
 *
 * `minImpulseAtr` is the required body / ATR ratio (e.g. 0.5 means the body
 * must be at least 50% of ATR). `requireQuartile` enforces the close to sit in
 * the upper quartile for long signals or the lower quartile for short signals.
 */
export function evaluateDisplacement(
  candle: Candle,
  atr: number,
  side: TradeSide,
  minImpulseAtr: number,
  requireQuartile: boolean = true,
): DisplacementMetrics {
  const body = Math.abs(candle.close - candle.open);
  const range = Math.max(0, candle.high - candle.low);
  const safeAtr = Number.isFinite(atr) && atr > 0 ? atr : 0;
  const bodyAtrRatio = safeAtr > 0 ? body / safeAtr : 0;
  const closePosition = range > 0 ? (candle.close - candle.low) / range : 0.5;

  const meetsBody = safeAtr > 0 ? bodyAtrRatio >= Math.max(0, minImpulseAtr) : true;

  let meetsClose = true;
  if (requireQuartile) {
    meetsClose = side === 'long' ? closePosition >= 0.75 : closePosition <= 0.25;
  }

  return { body, range, bodyAtrRatio, closePosition, meetsBody, meetsClose };
}

/**
 * Score the displacement of an FVG impulse: the imbalance candle (c1) plus its
 * neighbours together must cover at least `minImpulseAtr * ATR` of range.
 */
export function evaluateImpulseDisplacement(
  c0: Candle,
  c1: Candle,
  c2: Candle,
  atr: number,
  side: TradeSide,
  minImpulseAtr: number,
): DisplacementMetrics {
  const range = Math.max(c0.high, c1.high, c2.high) - Math.min(c0.low, c1.low, c2.low);
  const body = Math.abs(c2.close - c0.open);
  const safeAtr = Number.isFinite(atr) && atr > 0 ? atr : 0;
  const bodyAtrRatio = safeAtr > 0 ? body / safeAtr : 0;
  const closePosition = range > 0
    ? (c2.close - Math.min(c0.low, c1.low, c2.low)) / range
    : 0.5;

  const meetsBody = safeAtr > 0 ? bodyAtrRatio >= Math.max(0, minImpulseAtr) : true;
  const meetsClose = side === 'long' ? closePosition >= 0.6 : closePosition <= 0.4;

  return { body, range, bodyAtrRatio, closePosition, meetsBody, meetsClose };
}

// ─── Expected RR ──────────────────────────────────────────────────────

/**
 * Expected reward-to-risk = average TP distance / SL distance. Returns 0 if
 * the inputs are degenerate (zero risk or no targets).
 */
export function expectedRewardToRisk(
  entry: number,
  stopLoss: number,
  takeProfits: number[],
  side: TradeSide,
): number {
  if (!Number.isFinite(entry) || !Number.isFinite(stopLoss)) return 0;
  const risk = side === 'long' ? entry - stopLoss : stopLoss - entry;
  if (risk <= 0) return 0;

  const tps = (takeProfits ?? []).filter((tp) => Number.isFinite(tp));
  if (tps.length === 0) return 0;

  let rewardSum = 0;
  let count = 0;
  for (const tp of tps) {
    const reward = side === 'long' ? tp - entry : entry - tp;
    if (reward <= 0) continue;
    rewardSum += reward;
    count += 1;
  }
  if (count === 0) return 0;
  return rewardSum / count / risk;
}

// ─── Combined gate ────────────────────────────────────────────────────

export type SignalQualityRejectCode =
  | 'regime_data_insufficient'
  | 'regime_blocks_long'
  | 'regime_blocks_short'
  | 'regime_neutral'
  | 'adx_below_min'
  | 'displacement_body_below_atr'
  | 'displacement_close_outside_quartile'
  | 'expected_rr_below_min'
  | 'event_lockout_active';

export interface SignalQualityVerdict {
  ok: boolean;
  reasonCode?: SignalQualityRejectCode;
  reason?: string;
  details: {
    regime?: RegimeAssessment;
    displacement?: DisplacementMetrics;
    expectedRr?: number;
  };
}

export interface SignalQualityInput {
  side: TradeSide;
  /** Higher-timeframe candles used for the regime filter. Pass closed candles only. */
  regimeCandles: Candle[];
  regimeTf: TradingRulesTimeframe;
  /**
   * Candles for the entry timeframe (closed only). The most recent one is the
   * displacement candidate — for engulfing this is the engulfing candle, for
   * FVG this is the imbalance candle (`c1`).
   */
  entryCandles: Candle[];
  /** Optional explicit triple for FVG impulse evaluation (c0, c1, c2). */
  impulseTriple?: { c0: Candle; c1: Candle; c2: Candle };
  entry: number;
  stopLoss: number;
  takeProfits: number[];
  thresholds: {
    adxMin: number;
    minImpulseAtr: number;
    /** Optional minimum expected reward/risk. Omit or set <=0 to disable. */
    minExpectedRr?: number;
    requireQuartile?: boolean;
  };
  eventLockout?: { active: boolean; reason?: string };
}

/**
 * Runs every available filter in a deterministic order and returns the first
 * failing reason code, or `{ ok: true }` if the candidate is good enough to
 * hand off to execution.
 */
export function evaluateSignalQuality(input: SignalQualityInput): SignalQualityVerdict {
  if (input.eventLockout?.active) {
    return {
      ok: false,
      reasonCode: 'event_lockout_active',
      reason: input.eventLockout.reason ?? 'event_lockout_active',
      details: {},
    };
  }

  const regime = assessRegime(input.regimeCandles, {
    adxMin: input.thresholds.adxMin,
  });

  if (!regime.hasEnoughData) {
    return {
      ok: false,
      reasonCode: 'regime_data_insufficient',
      reason: `regime_data_insufficient_${input.regimeTf}`,
      details: { regime },
    };
  }

  if (Number.isFinite(regime.adx) && regime.adx < input.thresholds.adxMin) {
    return {
      ok: false,
      reasonCode: 'adx_below_min',
      reason: `adx_${regime.adx.toFixed(1)}_below_${input.thresholds.adxMin}`,
      details: { regime },
    };
  }

  if (regime.direction === 'neutral') {
    return {
      ok: false,
      reasonCode: 'regime_neutral',
      reason: `regime_neutral_${input.regimeTf}`,
      details: { regime },
    };
  }

  if (input.side === 'long' && regime.direction !== 'long') {
    return {
      ok: false,
      reasonCode: 'regime_blocks_long',
      reason: `regime_${regime.direction}_blocks_long`,
      details: { regime },
    };
  }
  if (input.side === 'short' && regime.direction !== 'short') {
    return {
      ok: false,
      reasonCode: 'regime_blocks_short',
      reason: `regime_${regime.direction}_blocks_short`,
      details: { regime },
    };
  }

  // Displacement quality on the entry timeframe
  const atrSeries = computeAtr(input.entryCandles, 14);
  const atr = atrSeries[atrSeries.length - 1];
  let displacement: DisplacementMetrics | undefined;

  if (input.impulseTriple) {
    displacement = evaluateImpulseDisplacement(
      input.impulseTriple.c0,
      input.impulseTriple.c1,
      input.impulseTriple.c2,
      atr,
      input.side,
      input.thresholds.minImpulseAtr,
    );
  } else if (input.entryCandles.length >= 1) {
    const candle = input.entryCandles[input.entryCandles.length - 1];
    displacement = evaluateDisplacement(
      candle,
      atr,
      input.side,
      input.thresholds.minImpulseAtr,
      input.thresholds.requireQuartile ?? true,
    );
  }

  if (displacement && !displacement.meetsBody) {
    return {
      ok: false,
      reasonCode: 'displacement_body_below_atr',
      reason: `body_atr_${displacement.bodyAtrRatio.toFixed(2)}_below_${input.thresholds.minImpulseAtr}`,
      details: { regime, displacement },
    };
  }

  if (displacement && !displacement.meetsClose) {
    return {
      ok: false,
      reasonCode: 'displacement_close_outside_quartile',
      reason: `close_pos_${displacement.closePosition.toFixed(2)}_${input.side}`,
      details: { regime, displacement },
    };
  }

  const rr = expectedRewardToRisk(input.entry, input.stopLoss, input.takeProfits, input.side);
  const minExpectedRr = Number(input.thresholds.minExpectedRr ?? 0);
  if (Number.isFinite(minExpectedRr) && minExpectedRr > 0 && rr < minExpectedRr) {
    return {
      ok: false,
      reasonCode: 'expected_rr_below_min',
      reason: `expected_rr_${rr.toFixed(2)}_below_${minExpectedRr}`,
      details: { regime, displacement, expectedRr: rr },
    };
  }

  return {
    ok: true,
    details: { regime, displacement, expectedRr: rr },
  };
}
