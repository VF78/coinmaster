import { Bias, MarketTick } from './types.js';

export interface StrategyContext {
  symbol: string;
  price: number;
  lastPrice?: number;
  bias: Bias;
  ticks: MarketTick[];
}

export interface StrategySignal {
  shouldOpen: boolean;
  side?: 'long' | 'short';
  confidence: number;
  reason: string;
}

interface Candle {
  bucket: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

function buildCandles(ticks: MarketTick[], timeframeMs: number): Candle[] {
  const byBucket = new Map<number, Candle>();
  for (const t of ticks) {
    const ts = Date.parse(t.timestamp);
    if (!Number.isFinite(ts)) continue;
    const bucket = Math.floor(ts / timeframeMs) * timeframeMs;
    const price = t.price;

    const c = byBucket.get(bucket);
    if (!c) {
      byBucket.set(bucket, { bucket, open: price, high: price, low: price, close: price });
      continue;
    }
    c.high = Math.max(c.high, price);
    c.low = Math.min(c.low, price);
    c.close = price;
  }

  const sorted = [...byBucket.values()].sort((a, b) => a.bucket - b.bucket);
  if (sorted.length <= 1) return [];
  // last candle may still be forming; trade only on closed candles
  return sorted.slice(0, -1);
}

function checkShortTrigger(candles: Candle[]): boolean {
  if (candles.length < 33) return false;

  const engulf = candles[candles.length - 1]; // current closed engulf candle
  const swept = candles[candles.length - 2]; // previous candle with sweep
  const history = candles.slice(candles.length - 32, candles.length - 2); // 30 candles before swept

  const maxHigh = Math.max(...history.map((c) => c.high));
  const localHighSwept = swept.high > maxHigh;

  const bearishEngulf = engulf.close < swept.open;

  return localHighSwept && bearishEngulf;
}

function checkLongTrigger(candles: Candle[]): boolean {
  if (candles.length < 33) return false;

  const engulf = candles[candles.length - 1];
  const swept = candles[candles.length - 2];
  const history = candles.slice(candles.length - 32, candles.length - 2);

  const minLow = Math.min(...history.map((c) => c.low));
  const localLowSwept = swept.low < minLow;

  const bullishEngulf = engulf.close > swept.open;

  return localLowSwept && bullishEngulf;
}

/**
 * Trigger logic fixed per user spec:
 * - Monitor 5m and 15m
 * - Short: local high sweep (high above highs of prior 30 candles on that TF)
 *   then next candle closes below previous candle open.
 * - Long: mirror logic.
 */
export class BacktestV1SignalAdapter {
  evaluate(ctx: StrategyContext): StrategySignal {
    if (ctx.bias === 'off') {
      return { shouldOpen: false, confidence: 0, reason: 'bias_off' };
    }

    const symbolTicks = ctx.ticks.filter((t) => t.symbol === ctx.symbol);
    if (symbolTicks.length < 40) {
      return { shouldOpen: false, confidence: 0.15, reason: 'insufficient_tick_history' };
    }

    const candles5m = buildCandles(symbolTicks, 5 * 60 * 1000);
    const candles15m = buildCandles(symbolTicks, 15 * 60 * 1000);

    if (ctx.bias === 'short') {
      if (checkShortTrigger(candles5m)) {
        return { shouldOpen: true, side: 'short', confidence: 0.95, reason: 'sweep30_high_then_bearish_engulf_5m' };
      }
      if (checkShortTrigger(candles15m)) {
        return { shouldOpen: true, side: 'short', confidence: 0.9, reason: 'sweep30_high_then_bearish_engulf_15m' };
      }
      return { shouldOpen: false, confidence: 0.4, reason: 'no_short_engulf_trigger' };
    }

    if (ctx.bias === 'long') {
      if (checkLongTrigger(candles5m)) {
        return { shouldOpen: true, side: 'long', confidence: 0.95, reason: 'sweep30_low_then_bullish_engulf_5m' };
      }
      if (checkLongTrigger(candles15m)) {
        return { shouldOpen: true, side: 'long', confidence: 0.9, reason: 'sweep30_low_then_bullish_engulf_15m' };
      }
      return { shouldOpen: false, confidence: 0.4, reason: 'no_long_engulf_trigger' };
    }

    return { shouldOpen: false, confidence: 0, reason: 'unknown_bias' };
  }
}
