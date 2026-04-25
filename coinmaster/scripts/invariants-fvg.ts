/**
 * Invariant tests for fvgEvaluator.ts
 */

import {
  detectStructureBreak,
  detectFvgZones,
  computeRetraceTrigger,
  isFvgRetracedToLevel,
  evaluateFvg,
  type FvgZone,
  type FvgQualificationSettings,
} from '../src/core/fvgEvaluator.js';
import type { Candle } from '../src/exchange/types.js';

let passed = 0;
let failed = 0;

function assert(condition: boolean, message: string): void {
  if (condition) {
    console.log(`  ✓ ${message}`);
    passed++;
  } else {
    console.error(`  ✗ ${message}`);
    failed++;
  }
}

function makeCandle(open: number, high: number, low: number, close: number, ts = '2026-01-01T00:00:00Z'): Candle {
  return { timestamp: ts, open, high, low, close, volume: 0 };
}

function makeCandles(count: number, base = 100): Candle[] {
  return Array.from({ length: count }, (_, i) =>
    makeCandle(base, base + 1, base - 1, base, `2026-01-01T${String(i).padStart(2, '0')}:00:00Z`),
  );
}

function baseQualification(overrides: Partial<FvgQualificationSettings> = {}): FvgQualificationSettings {
  return {
    minWidthPct: 0,
    requireSweep: false,
    sweepLookbackCandles: 20,
    requireFirstTouch: false,
    maxZoneAgeCandles: 12,
    requireConfirmation: false,
    confirmationTimeframes: ['15m'],
    ...overrides,
  };
}

console.log('\n════════════════════════════════════════════════════════════');
console.log('  FVG Evaluator Invariants');
console.log('════════════════════════════════════════════════════════════\n');

console.log('── Case 1: Structure break detection ──');
{
  const flat = makeCandles(25, 100);
  assert(detectStructureBreak(flat, 20) === null, 'flat market → no structure break');

  const bullish = makeCandles(25, 100);
  bullish[bullish.length - 2] = makeCandle(100, 115, 99, 114);
  assert(detectStructureBreak(bullish, 20) === 'bullish', 'close above swing high → bullish break');

  const bearish = makeCandles(25, 100);
  bearish[bearish.length - 2] = makeCandle(100, 101, 85, 86);
  assert(detectStructureBreak(bearish, 20) === 'bearish', 'close below swing low → bearish break');

  assert(detectStructureBreak(makeCandles(3, 100), 20) === null, 'too few candles → null');
}

console.log('\n── Case 2: Bullish FVG detection ──');
{
  const candles: Candle[] = [
    makeCandle(100, 102, 99, 101, '2026-01-01T00:00:00Z'),
    makeCandle(101, 106, 100, 104, '2026-01-01T01:00:00Z'),
    makeCandle(104, 110, 105, 108, '2026-01-01T02:00:00Z'),
    makeCandle(108, 112, 107, 110, '2026-01-01T03:00:00Z'),
  ];
  const zones = detectFvgZones(candles, '1h', 10);
  const bz = zones.find(z => z.direction === 'bullish');
  assert(zones.length >= 1, 'bullish FVG detected');
  assert(bz !== undefined, 'bullish zone exists');
  if (bz) {
    assert(Math.abs(bz.bottom - 102) < 0.01, `bullish bottom = 102 (got ${bz.bottom})`);
    assert(Math.abs(bz.top - 105) < 0.01, `bullish top = 105 (got ${bz.top})`);
  }
}

console.log('\n── Case 2.1: Latest closed candle is eligible ──');
{
  const candles: Candle[] = [
    makeCandle(100, 102, 99, 101, '2026-01-01T00:00:00Z'),
    makeCandle(101, 106, 100, 104, '2026-01-01T01:00:00Z'),
    makeCandle(104, 110, 105, 108, '2026-01-01T02:00:00Z'),
  ];
  const zones = detectFvgZones(candles, '1h', 10);
  assert(zones.some(z => z.direction === 'bullish' && z.candleTimestamp === '2026-01-01T02:00:00Z'), 'latest provided closed candle can complete FVG zone');
}

console.log('\n── Case 3: Retrace + qualification flow ──');
{
  const candles: Candle[] = [
    ...makeCandles(22, 100),
    makeCandle(100, 102, 98, 99, '2026-01-01T22:00:00Z'),
    makeCandle(99, 111, 95, 110, '2026-01-01T23:00:00Z'),
    makeCandle(110, 116, 106, 114, '2026-01-02T00:00:00Z'),
    makeCandle(114, 115, 113, 114, '2026-01-02T01:00:00Z'),
  ];
  const signal = evaluateFvg(candles, '1h', {
    currentPrice: 104,
    retracePct: 50,
    qualification: baseQualification({ requireSweep: true }),
    lookback: 10,
    currentTimeMs: Date.parse('2026-01-02T01:30:00Z'),
  });
  assert(signal.detected === true, 'qualified bullish FVG signal detected');
  assert(signal.reason.includes('sweep'), 'reason includes sweep coverage');
}

console.log('\n── Case 4: First-touch filter rejects mitigated zone ──');
{
  const candles: Candle[] = [
    ...makeCandles(22, 100),
    makeCandle(100, 102, 98, 99, '2026-01-01T22:00:00Z'),
    makeCandle(99, 111, 95, 110, '2026-01-01T23:00:00Z'),
    makeCandle(110, 116, 106, 114, '2026-01-02T00:00:00Z'),
    makeCandle(114, 115, 103, 104, '2026-01-02T01:00:00Z'),
    makeCandle(104, 105, 103, 104, '2026-01-02T02:00:00Z'),
  ];
  const signal = evaluateFvg(candles, '1h', {
    currentPrice: 104,
    retracePct: 50,
    qualification: baseQualification({ requireFirstTouch: true }),
    lookback: 10,
    currentTimeMs: Date.parse('2026-01-02T02:30:00Z'),
  });
  assert(signal.detected === false, 'mitigated zone rejected when first-touch required');
  assert(signal.reason.includes('already_mitigated') || signal.reason.includes('first_touch'), 'reason covers mitigation rejection');
}

console.log('\n── Case 5: Confirmation required ──');
{
  const htfCandles: Candle[] = [
    ...makeCandles(22, 100),
    makeCandle(100, 102, 98, 99, '2026-01-01T22:00:00Z'),
    makeCandle(99, 111, 95, 110, '2026-01-01T23:00:00Z'),
    makeCandle(110, 116, 106, 114, '2026-01-02T00:00:00Z'),
    makeCandle(114, 115, 103, 104, '2026-01-02T01:00:00Z'),
    makeCandle(104, 105, 103, 104, '2026-01-02T02:00:00Z'),
  ];
  const ltfCandles: Candle[] = [
    makeCandle(105, 106, 104, 105, '2026-01-02T01:05:00Z'),
    makeCandle(105, 106, 104, 104.5, '2026-01-02T01:20:00Z'),
    makeCandle(104.5, 105, 98, 99, '2026-01-02T01:35:00Z'),
    makeCandle(99, 108, 98, 107, '2026-01-02T01:50:00Z'),
    makeCandle(107, 109, 106, 108, '2026-01-02T02:05:00Z'),
    makeCandle(108, 110, 107, 109, '2026-01-02T02:20:00Z'),
    makeCandle(109, 111, 108, 110, '2026-01-02T02:35:00Z'),
  ];
  const signal = evaluateFvg(htfCandles, '1h', {
    currentPrice: 104,
    retracePct: 50,
    qualification: baseQualification({ requireConfirmation: true, confirmationTimeframes: ['15m'] }),
    lookback: 10,
    currentTimeMs: Date.parse('2026-01-02T02:40:00Z'),
    lowerTfCandles: { '15m': ltfCandles },
  });
  assert(signal.detected === true, 'confirmation allows qualified entry');
  assert(signal.confirmationTimeframe === '15m', 'confirmation TF reported');
}

console.log('\n── Case 6: Trigger helpers ──');
{
  const bullishZone: FvgZone = { direction: 'bullish', top: 110, bottom: 100, midpoint: 105, width: 10, widthPct: 9.52, candleTimestamp: '', timeframe: '1h' };
  const bearishZone: FvgZone = { direction: 'bearish', top: 110, bottom: 100, midpoint: 105, width: 10, widthPct: 9.52, candleTimestamp: '', timeframe: '4h' };
  assert(Math.abs(computeRetraceTrigger(bullishZone, 50) - 105) < 0.01, 'bullish trigger midpoint');
  assert(isFvgRetracedToLevel(bullishZone, 104, 50) === true, 'bullish retrace detected');
  assert(isFvgRetracedToLevel(bearishZone, 106, 50) === true, 'bearish retrace detected');
}

console.log('\n════════════════════════════════════════════════════════════');
console.log(`  TOTAL: ${passed + failed}  |  PASSED: ${passed}  |  FAILED: ${failed}`);
console.log('════════════════════════════════════════════════════════════\n');

if (failed > 0) process.exit(1);
