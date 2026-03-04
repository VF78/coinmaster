/**
 * invariants-engulfing.ts
 *
 * Deterministic verification of the body-only engulfing evaluator and
 * low/high breakout-window logic.
 *
 * No server, no exchange, no DB — tests pure functions only.
 *
 * Cases:
 *   1. Bullish body-only engulfing detection (green candle wraps previous body)
 *   2. Bearish body-only engulfing detection (red candle wraps previous body)
 *   3. Body-only: no detection when bodies don't fully wrap
 *   4. Low breakout with configurable lookback
 *   5. High breakout with configurable lookback
 *   6. No breakout when within range
 *   7. Combined: bullish engulfing + low breakout → signal detected
 *   8. Combined: bearish engulfing + high breakout → signal detected
 *   9. Insufficient candles → no signal
 *  10. Multi-TF: entry + exit across multiple timeframes
 *  11. Lookback window respects user-configurable N
 *
 * Exit code: 0 = all pass, 1 = failures found.
 *
 * Usage:
 *   npx tsx scripts/invariants-engulfing.ts
 *   # or
 *   npm run invariants:engulfing
 */

import type { Candle } from '../src/exchange/types.js';
import type { TradingRulesTimeframe } from '../src/shared/dto.js';
import {
  bodyTop,
  bodyBottom,
  isBullishEngulfingBody,
  isBearishEngulfingBody,
  isLowBreakout,
  isHighBreakout,
  evaluateTimeframe,
  evaluateMultiTf,
  type EngulfingEvaluatorOptions,
} from '../src/core/engulfingEvaluator.js';

// ─── Test harness ────────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string): void {
  if (condition) {
    passed++;
    console.log(`  ✓ ${label}`);
  } else {
    failed++;
    console.error(`  ✗ FAIL: ${label}`);
  }
}

// ─── Candle factory helper ──────────────────────────────────────────

function candle(o: number, h: number, l: number, c: number, ts = '2025-01-01T00:00:00Z'): Candle {
  return { open: o, high: h, low: l, close: c, volume: 1, timestamp: ts };
}

// ═════════════════════════════════════════════════════════════════════
// CASE 1: Bullish body-only engulfing
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 1: Bullish body-only engulfing ──');
{
  // Previous: red candle (open=105, close=100 → body 100-105)
  // Current:  green candle (open=99, close=106 → body 99-106) — wraps previous
  const prev = candle(105, 107, 98, 100);
  const curr = candle(99, 108, 97, 106);

  assert(isBullishEngulfingBody(prev, curr) === true, 'green candle wraps red candle body');
  assert(isBearishEngulfingBody(prev, curr) === false, 'not bearish');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 2: Bearish body-only engulfing
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 2: Bearish body-only engulfing ──');
{
  // Previous: green candle (open=100, close=105 → body 100-105)
  // Current:  red candle (open=107, close=98 → body 98-107) — wraps previous
  const prev = candle(100, 106, 99, 105);
  const curr = candle(107, 109, 97, 98);

  assert(isBearishEngulfingBody(prev, curr) === true, 'red candle wraps green candle body');
  assert(isBullishEngulfingBody(prev, curr) === false, 'not bullish');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 3: No engulfing when bodies don't fully wrap
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 3: No engulfing — bodies partially overlap ──');
{
  // Previous: body 100-105
  // Current:  green but body 101-106 — bottom doesn't reach 100
  const prev = candle(105, 107, 98, 100);
  const curr = candle(101, 108, 97, 106);

  assert(isBullishEngulfingBody(prev, curr) === false, 'body bottom 101 > prev body bottom 100');
}
{
  // Previous: body 100-105
  // Current:  green but body 99-104 — top doesn't reach 105
  const prev = candle(105, 107, 98, 100);
  const curr = candle(99, 108, 97, 104);

  assert(isBullishEngulfingBody(prev, curr) === false, 'body top 104 < prev body top 105');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 4: Low breakout with configurable lookback
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 4: Low breakout (low/high based) ──');
{
  // History of 5 candles with low=50 being the minimum
  const history = [
    candle(100, 110, 55, 105),
    candle(100, 110, 50, 105),
    candle(100, 110, 60, 105),
    candle(100, 110, 52, 105),
    candle(100, 110, 58, 105),
  ];

  // Swept candle low = 49 → below min(50)
  const swept = candle(100, 110, 49, 105);
  assert(isLowBreakout(history, swept) === true, 'low=49 < min(lows)=50 → breakout');

  // Swept candle low = 51 → NOT below min(50)
  const noBreak = candle(100, 110, 51, 105);
  assert(isLowBreakout(history, noBreak) === false, 'low=51 > min(lows)=50 → no breakout');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 5: High breakout
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 5: High breakout (low/high based) ──');
{
  const history = [
    candle(100, 110, 90, 105),
    candle(100, 115, 90, 105),
    candle(100, 108, 90, 105),
    candle(100, 112, 90, 105),
  ];

  // Swept candle high = 116 → above max(115)
  const swept = candle(100, 116, 90, 105);
  assert(isHighBreakout(history, swept) === true, 'high=116 > max(highs)=115 → breakout');

  // Swept candle high = 114 → NOT above max(115)
  const noBreak = candle(100, 114, 90, 105);
  assert(isHighBreakout(history, noBreak) === false, 'high=114 < max(highs)=115 → no breakout');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 6: No breakout when within range
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 6: No breakout when within historical range ──');
{
  const history = [
    candle(100, 120, 80, 105),
    candle(100, 115, 85, 105),
  ];

  const swept = candle(100, 118, 82, 105);
  assert(isLowBreakout(history, swept) === false, 'low 82 within 80..85 range');
  assert(isHighBreakout(history, swept) === false, 'high 118 within 115..120 range');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 6.1: Pair-extreme breakout (OR across prev+curr extremes)
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 6.1: Pair-extreme breakout across engulfing pair ──');
{
  const history = [
    candle(100, 120, 90, 110),
    candle(100, 118, 91, 109),
    candle(100, 119, 92, 108),
  ];

  // prev itself does not break low/high, but curr does.
  const prev = candle(105, 117, 93, 106);
  const currLowBreak = candle(104, 116, 89, 110);
  const currHighBreak = candle(104, 121, 93, 100);

  assert(isLowBreakout(history, prev, currLowBreak) === true, 'pair low uses min(prev.low, curr.low)');
  assert(isHighBreakout(history, prev, currHighBreak) === true, 'pair high uses max(prev.high, curr.high)');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 7: Combined bullish engulfing + low breakout → signal
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 7: evaluateTimeframe — bullish signal ──');
{
  const lookback = 3;
  // Build: 3 history candles + 1 swept + 1 engulf = 5 candles minimum
  const candles: Candle[] = [
    candle(100, 110, 90, 105),   // history[0]
    candle(100, 108, 92, 105),   // history[1]
    candle(100, 112, 91, 105),   // history[2]
    candle(100, 105, 88, 95),    // swept: low=88 < min(90,92,91)=90 ✓
    candle(94, 106, 93, 106),    // engulf: green, body 94-106 wraps swept body min(100,95)=95..max(100,95)=100 ✓
  ];

  const sig = evaluateTimeframe(candles, '15m', lookback);
  assert(sig.detected === true, 'bullish signal detected');
  assert(sig.direction === 'bullish', 'direction is bullish');
  assert(sig.timeframe === '15m', 'timeframe is 15m');
  assert(sig.reason.includes('bullish_body_engulf'), 'reason includes bullish_body_engulf');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 8: Combined bearish engulfing + high breakout → signal
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 8: evaluateTimeframe — bearish signal ──');
{
  const lookback = 3;
  const candles: Candle[] = [
    candle(100, 110, 90, 105),   // history[0]
    candle(100, 108, 92, 105),   // history[1]
    candle(100, 109, 91, 105),   // history[2]
    candle(100, 111, 95, 108),   // swept: high=111 > max(110,108,109)=110 ✓
    candle(109, 110, 94, 94),    // engulf: red (close<open), body 94-109 wraps swept body min(100,108)=100..max(100,108)=108 ✓
  ];

  const sig = evaluateTimeframe(candles, '5m', lookback);
  assert(sig.detected === true, 'bearish signal detected');
  assert(sig.direction === 'bearish', 'direction is bearish');
  assert(sig.reason.includes('bearish_body_engulf'), 'reason includes bearish_body_engulf');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 9: Insufficient candles → no signal
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 9: Insufficient candles ──');
{
  const candles: Candle[] = [
    candle(100, 110, 90, 105),
    candle(100, 108, 92, 105),
  ];

  const sig = evaluateTimeframe(candles, '1h', 30);
  assert(sig.detected === false, 'no signal with only 2 candles (need 32)');
  assert(sig.reason.includes('insufficient_candles'), 'reason mentions insufficient candles');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 10: Multi-TF evaluation
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 10: Multi-TF evaluation ──');
{
  const lookback = 3;

  // 5m candles: has a bullish signal
  const candles5m: Candle[] = [
    candle(100, 110, 90, 105),
    candle(100, 108, 92, 105),
    candle(100, 112, 91, 105),
    candle(100, 105, 88, 95),    // low breakout
    candle(94, 106, 93, 106),    // bullish engulfing body
  ];

  // 15m candles: no signal (no breakout)
  const candles15m: Candle[] = [
    candle(100, 110, 90, 105),
    candle(100, 108, 92, 105),
    candle(100, 109, 91, 105),
    candle(100, 108, 92, 103),   // no breakout (high=108 <= max 110)
    candle(102, 106, 101, 106),  // green but no breakout on swept
  ];

  // 1h candles: insufficient
  const candles1h: Candle[] = [candle(100, 110, 90, 105)];

  const candlesByTf = new Map<TradingRulesTimeframe, Candle[]>();
  candlesByTf.set('5m', candles5m);
  candlesByTf.set('15m', candles15m);
  candlesByTf.set('1h', candles1h);

  const opts: EngulfingEvaluatorOptions = {
    lookbackCandles: lookback,
    entryTimeframes: ['5m', '15m'],
    emergencyExitTimeframes: ['1h'],
  };

  const result = evaluateMultiTf(candlesByTf, opts);

  assert(result.entry.length === 2, 'two entry signals evaluated');
  assert(result.exit.length === 1, 'one exit signal evaluated');
  assert(result.anyEntry === true, 'anyEntry is true (5m triggered)');
  assert(result.entry[0].detected === true, '5m entry detected');
  assert(result.entry[1].detected === false, '15m entry not detected');
  assert(result.anyExit === false, 'anyExit is false (1h insufficient)');
}

// ═════════════════════════════════════════════════════════════════════
// CASE 11: Lookback window configurability
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 11: Lookback window = 2 vs 5 ──');
{
  // With lookback=2, need 4 candles. Build a case where:
  // history(2): lows = [90, 92] → min = 90
  // swept: low = 89 → breakout with lookback=2
  // engulf: bullish body engulfing
  const candles4: Candle[] = [
    candle(100, 110, 90, 105),   // history for lookback=2
    candle(100, 108, 92, 105),   // history for lookback=2
    candle(100, 105, 89, 95),    // swept: low=89 < 90
    candle(94, 106, 93, 106),    // engulf: bullish
  ];

  const sig2 = evaluateTimeframe(candles4, '5m', 2);
  assert(sig2.detected === true, 'lookback=2: bullish signal with 4 candles');

  // Same 4 candles but lookback=5 → need 7 candles → insufficient
  const sig5 = evaluateTimeframe(candles4, '5m', 5);
  assert(sig5.detected === false, 'lookback=5: insufficient candles (have 4, need 7)');
  assert(sig5.reason.includes('insufficient_candles'), 'reason says insufficient');
}

// ─── Body helper edge cases ─────────────────────────────────────────

console.log('\n── Case 12: bodyTop/bodyBottom helpers ──');
{
  const green = candle(100, 110, 90, 105); // open=100, close=105
  assert(bodyTop(green) === 105, 'green bodyTop = close');
  assert(bodyBottom(green) === 100, 'green bodyBottom = open');

  const red = candle(105, 110, 90, 100); // open=105, close=100
  assert(bodyTop(red) === 105, 'red bodyTop = open');
  assert(bodyBottom(red) === 100, 'red bodyBottom = close');

  const doji = candle(100, 110, 90, 100); // open=close
  assert(bodyTop(doji) === 100, 'doji bodyTop = open = close');
  assert(bodyBottom(doji) === 100, 'doji bodyBottom = open = close');
}

// ─── Summary ─────────────────────────────────────────────────────────

console.log(`\n${'═'.repeat(60)}`);
console.log(`  TOTAL: ${passed + failed}  |  PASSED: ${passed}  |  FAILED: ${failed}`);
console.log(`${'═'.repeat(60)}\n`);

process.exit(failed > 0 ? 1 : 0);
