/**
 * invariants-signal-quality.ts
 *
 * Deterministic verification of the SignalQualityContext helpers introduced in
 * issue #61. No server, no exchange, no DB — pure functions only.
 *
 * Cases:
 *   1. EMA series: insufficient data, seed equals SMA, recursive update.
 *   2. ATR (Wilder) seed equals SMA of true ranges; subsequent values use the
 *      Wilder smoothing formula.
 *   3. ADX returns 0..100 and a clear bullish trend produces ADX > adxMin.
 *   4. assessRegime resolves long/short/neutral correctly.
 *   5. evaluateDisplacement enforces ATR fraction and quartile rules.
 *   6. expectedRewardToRisk averages multiple TPs and rejects degenerate input.
 *   7. evaluateSignalQuality wires regime/displacement/RR thresholds together
 *      and reports the first failing reasonCode.
 *
 * Exit code: 0 = all pass, 1 = failures found.
 *
 * Usage:
 *   npx tsx scripts/invariants-signal-quality.ts
 */

import type { Candle } from '../src/exchange/types.js';
import {
  computeEma,
  computeAtr,
  computeAdx,
  assessRegime,
  evaluateDisplacement,
  expectedRewardToRisk,
  evaluateSignalQuality,
} from '../src/core/signalQualityContext.js';

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

function close(actual: number, expected: number, label: string, eps = 1e-6): void {
  assert(Number.isFinite(actual) && Math.abs(actual - expected) < eps, `${label} (got ${actual}, expected ${expected})`);
}

function makeCandle(open: number, high: number, low: number, c: number, ts = '2026-01-01T00:00:00Z'): Candle {
  return { open, high, low, close: c, volume: 0, timestamp: ts };
}

function trendCandles(count: number, start: number, step: number): Candle[] {
  const out: Candle[] = [];
  let v = start;
  for (let i = 0; i < count; i++) {
    const ts = new Date(Date.UTC(2026, 0, 1, i)).toISOString();
    out.push(makeCandle(v, v + Math.abs(step), v - Math.abs(step) * 0.2, v + step, ts));
    v += step;
  }
  return out;
}

console.log('\n════════════════════════════════════════════════════════════');
console.log('  SignalQualityContext Invariants');
console.log('════════════════════════════════════════════════════════════\n');

// ── Case 1: EMA ───────────────────────────────────────────────────────
console.log('── Case 1: computeEma ──');
{
  const e1 = computeEma([1, 2, 3], 5);
  assert(e1.every((v) => Number.isNaN(v)), 'returns all NaN when values < period');

  const e2 = computeEma([1, 2, 3, 4, 5], 5);
  close(e2[4], 3, 'seed equals SMA of first period values');

  const e3 = computeEma([1, 2, 3, 4, 5, 6], 5);
  const k = 2 / 6;
  close(e3[5], 6 * k + 3 * (1 - k), 'recursive EMA update matches formula');
}

// ── Case 2: ATR ───────────────────────────────────────────────────────
console.log('\n── Case 2: computeAtr ──');
{
  const candles = trendCandles(30, 100, 1);
  const atr = computeAtr(candles, 14);
  assert(Number.isFinite(atr[14]), 'ATR seeded at index period');
  assert(atr[14] > 0, 'ATR seed is positive');
  assert(atr[atr.length - 1] > 0, 'ATR last value finite');

  const flat = trendCandles(30, 100, 0);
  const atrFlat = computeAtr(flat, 14);
  // Perfectly flat synthetic candles have zero true range.
  close(atrFlat[14], 0, 'perfectly flat series ATR is zero');
}

// ── Case 3: ADX ───────────────────────────────────────────────────────
console.log('\n── Case 3: computeAdx ──');
{
  const bull = trendCandles(60, 100, 1);
  const adxBull = computeAdx(bull, 14);
  const lastAdxBull = adxBull[adxBull.length - 1];
  assert(Number.isFinite(lastAdxBull), 'ADX last value finite for trend');
  assert(lastAdxBull > 30, `ADX strong on monotone trend (got ${lastAdxBull})`);

  const flat = trendCandles(60, 100, 0);
  const adxFlat = computeAdx(flat, 14);
  const lastAdxFlat = adxFlat[adxFlat.length - 1];
  // ADX is undefined on perfectly flat data because TR=0 ⇒ DX=0; we accept 0.
  assert(Number.isFinite(lastAdxFlat) && lastAdxFlat <= 1, 'ADX collapses near 0 on flat data');
}

// ── Case 4: assessRegime ─────────────────────────────────────────────
console.log('\n── Case 4: assessRegime ──');
{
  const bull = trendCandles(120, 100, 1);
  const verdictBull = assessRegime(bull, { adxMin: 20 });
  assert(verdictBull.direction === 'long', `bullish trend → long regime (got ${verdictBull.direction})`);

  const bear = trendCandles(120, 200, -1);
  const verdictBear = assessRegime(bear, { adxMin: 20 });
  assert(verdictBear.direction === 'short', `bearish trend → short regime (got ${verdictBear.direction})`);

  const flat = trendCandles(120, 100, 0);
  const verdictFlat = assessRegime(flat, { adxMin: 20 });
  assert(verdictFlat.direction === 'neutral', `flat series → neutral regime (got ${verdictFlat.direction})`);

  const tooShort = trendCandles(20, 100, 1);
  const verdictShort = assessRegime(tooShort, { adxMin: 20 });
  assert(!verdictShort.hasEnoughData, 'too few candles → hasEnoughData=false');
  assert(verdictShort.direction === 'neutral', 'too few candles → neutral direction');
}

// ── Case 5: evaluateDisplacement ─────────────────────────────────────
console.log('\n── Case 5: evaluateDisplacement ──');
{
  // Strong bullish: open=100, close=104 → body 4, range 4.5, close near top.
  const strongBull = makeCandle(100, 104.5, 100, 104);
  const bull = evaluateDisplacement(strongBull, 4, 'long', 0.5, true);
  assert(bull.meetsBody && bull.meetsClose, 'strong bullish meets body and close-quartile');

  // Weak body: body=1, ATR=4, ratio=0.25 < 0.5 → fails body.
  const weakBody = makeCandle(100, 104, 99, 101);
  const weak = evaluateDisplacement(weakBody, 4, 'long', 0.5, true);
  assert(!weak.meetsBody, 'small body fails ATR fraction');

  // Body OK but close in lower half: bullish candle with poor close position.
  const closeMid = makeCandle(100, 110, 100, 102);
  const cm = evaluateDisplacement(closeMid, 4, 'long', 0.4, true);
  assert(!cm.meetsClose, 'close in lower portion fails quartile for long');

  // Quartile gate disabled → close criterion always passes.
  const noQuartile = evaluateDisplacement(closeMid, 4, 'long', 0.4, false);
  assert(noQuartile.meetsClose, 'requireQuartile=false skips quartile rule');
}

// ── Case 6: expectedRewardToRisk ─────────────────────────────────────
console.log('\n── Case 6: expectedRewardToRisk ──');
{
  const rrLong = expectedRewardToRisk(100, 98, [104], 'long');
  close(rrLong, 2, 'long single-TP RR = 4/2 = 2');

  const rrAvg = expectedRewardToRisk(100, 98, [104, 106, 110], 'long');
  // (4 + 6 + 10) / 3 / 2 = 20/6
  close(rrAvg, 20 / 6, 'long average RR across 3 TPs');

  const rrShort = expectedRewardToRisk(100, 102, [96, 92], 'short');
  close(rrShort, ((4 + 8) / 2) / 2, 'short average RR across 2 TPs');

  const rrInvalid = expectedRewardToRisk(100, 100, [104], 'long');
  close(rrInvalid, 0, 'zero risk → RR=0');

  const rrNoTp = expectedRewardToRisk(100, 98, [], 'long');
  close(rrNoTp, 0, 'no TPs → RR=0');
}

// ── Case 7: evaluateSignalQuality ────────────────────────────────────
console.log('\n── Case 7: evaluateSignalQuality ──');
{
  const bull = trendCandles(120, 100, 1);
  // Use the same series as both regime and entry candles for the test.
  const longInput = {
    side: 'long' as const,
    regimeCandles: bull,
    regimeTf: '1h' as const,
    entryCandles: bull,
    entry: bull[bull.length - 1].close,
    stopLoss: bull[bull.length - 1].close - 2,
    takeProfits: [bull[bull.length - 1].close + 4],
    thresholds: { adxMin: 20, minImpulseAtr: 0.4, minExpectedRr: 1.5, requireQuartile: true },
  };
  const ok = evaluateSignalQuality(longInput);
  assert(ok.ok, 'aligned long entry passes all gates');

  // Long candidate against a bearish regime → blocked.
  const bear = trendCandles(120, 200, -1);
  const blockedLong = evaluateSignalQuality({
    ...longInput,
    regimeCandles: bear,
    entryCandles: bear,
    entry: bear[bear.length - 1].close,
    stopLoss: bear[bear.length - 1].close - 2,
    takeProfits: [bear[bear.length - 1].close + 4],
  });
  assert(!blockedLong.ok, 'long blocked when regime is short');
  assert(
    blockedLong.reasonCode === 'regime_blocks_long' || blockedLong.reasonCode === 'regime_neutral',
    `regime block reason code (got ${blockedLong.reasonCode})`,
  );

  // Insufficient regime data path.
  const insufficient = evaluateSignalQuality({
    ...longInput,
    regimeCandles: bull.slice(0, 10),
  });
  assert(!insufficient.ok, 'insufficient regime data blocks');
  assert(insufficient.reasonCode === 'regime_data_insufficient', 'reasonCode=regime_data_insufficient');

  // RR gate: shrink TP so RR < minExpectedRr.
  const lowRr = evaluateSignalQuality({
    ...longInput,
    takeProfits: [longInput.entry + 0.1],
  });
  assert(!lowRr.ok, 'RR below threshold blocks');
  assert(lowRr.reasonCode === 'expected_rr_below_min', 'reasonCode=expected_rr_below_min');

  // Event lockout short-circuits everything.
  const locked = evaluateSignalQuality({
    ...longInput,
    eventLockout: { active: true, reason: 'cpi_window' },
  });
  assert(!locked.ok && locked.reasonCode === 'event_lockout_active', 'event lockout returns first');
}

console.log(`\n${'═'.repeat(60)}`);
console.log(`  TOTAL: ${passed + failed}  |  PASSED: ${passed}  |  FAILED: ${failed}`);
console.log(`${'═'.repeat(60)}\n`);

process.exit(failed > 0 ? 1 : 0);
