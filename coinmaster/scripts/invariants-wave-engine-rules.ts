import { DEFAULT_WAVE_ENGINE_RULES, cloneWaveEngineRulesDefaults, normalizeWaveEngineRules } from '../src/shared/tradingRulesV2.js';

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

function assertEqual<T>(actual: T, expected: T, label: string): void {
  assert(JSON.stringify(actual) === JSON.stringify(expected), `${label} (got ${JSON.stringify(actual)}, expected ${JSON.stringify(expected)})`);
}

console.log('\n── Invariant 1: defaults stay stable ──');
{
  const clone = cloneWaveEngineRulesDefaults();
  assertEqual(clone.directionTf, '4h', 'default directionTf = 4h');
  assertEqual(clone.entryTimeframes, ['5m', '15m', '1h'], 'default entryTimeframes preserved');
  assert(clone.waveEngine === 'atr_zigzag', 'default wave engine = ATR ZigZag');
  assert(clone.breakBasis === 'wick', 'default break basis = wick');
  assert(clone.flatExtremeLookbackHours === 100, 'default flat extreme lookback = 100h');
  assert(clone.pullbackRatio === 0.5, 'default pullback = 50%');
  assert(clone.bodyConfirmation === 'body_engulfing', 'body confirmation fixed');
  assert(clone.impulseSlBuffer === 0.0033, 'impulse SL buffer fixed');
  assert(clone.tp1MaxPct === 0.015, 'TP1 cap fixed');
}

console.log('\n── Invariant 2: clamps enforce Vladimir parameter ranges ──');
{
  const normalized = normalizeWaveEngineRules({
    waveEngine: 'pct_zigzag',
    breakBasis: 'close',
    entryTimeframes: ['1m', '1h', '1h', '15m'],
    atrMult: 99,
    pctMove: 0.5,
    flatExtremeLookbackHours: 999,
    pullbackRatio: 0.1,
    maxSlPct: 0.5,
    tp2Pct: 0.5,
    tp3Pct: 0.001,
    timeStopHours: 99,
  });

  assert(normalized.waveEngine === 'pct_zigzag', 'waveEngine accepts pct_zigzag');
  assert(normalized.breakBasis === 'close', 'breakBasis accepts close');
  assertEqual(normalized.entryTimeframes, ['1h', '15m'], 'entryTimeframes filtered and deduped');
  assert(normalized.atrMult === 4, 'atrMult clamped to 4');
  assert(normalized.pctMove === 0.05, 'pctMove clamped to 5%');
  assert(normalized.flatExtremeLookbackHours === 150, 'flat lookback clamped to 150h');
  assert(normalized.pullbackRatio === 0.4, 'pullback clamped to 40%');
  assert(normalized.maxSlPct === 0.04, 'max SL clamped to 4%');
  assert(normalized.tp2Pct === 0.04, 'TP2 clamped to 4%');
  assert(normalized.tp3Pct === 0.04, 'TP3 clamped to 4% lower bound');
  assert(normalized.timeStopHours === 16, 'time stop clamped to 16h');
}

console.log('\n── Invariant 3: optimization ranges normalize safely ──');
{
  const normalized = normalizeWaveEngineRules({
    optimization: {
      mode: 'native_validation',
      ranges: {
        pullbackRatio: { min: 0.8, max: 0.4, step: 0.2 },
        timeStopHours: { min: -1, max: 999, step: 100 },
      },
    },
  });

  assert(normalized.optimization.mode === 'native_validation', 'optimization mode accepted');
  assertEqual(normalized.optimization.ranges.pullbackRatio, { min: 0.4, max: 0.8, step: 0.2 }, 'pullback range sorted and clamped');
  assertEqual(normalized.optimization.ranges.timeStopHours, { min: 4, max: 16, step: 12 }, 'time stop range clamped');
}

console.log('\n── Invariant 4: symbol normalization dedupes and restores fallback ──');
{
  const normalized = normalizeWaveEngineRules({
    symbols: [
      { symbol: 'btc', enabled: true, pair: 'btc/usdc:usdc' },
      { symbol: 'BTC', enabled: false, pair: 'BTC/USDC:USDC' },
      { symbol: ' xyz:gold ', enabled: true },
      { symbol: '' },
    ],
  });

  assert(normalized.symbols.length === 2, 'duplicate and invalid symbols removed');
  assertEqual(normalized.symbols[0], { symbol: 'BTC', enabled: true, pair: 'BTC/USDC:USDC' }, 'BTC symbol normalized');
  assertEqual(normalized.symbols[1], { symbol: 'xyz:GOLD', enabled: true, pair: 'GOLD/USDC:USDC' }, 'namespaced symbol normalized');

  const fallback = normalizeWaveEngineRules({ symbols: [] });
  assertEqual(fallback.symbols, DEFAULT_WAVE_ENGINE_RULES.symbols, 'empty symbol list falls back to defaults');
}

console.log('\n── Invariant 5: normalization does not mutate inputs or defaults ──');
{
  const input = {
    entryTimeframes: ['5m', '5m', '15m'],
    symbols: [{ symbol: 'eth', enabled: true, pair: 'eth/usdc:usdc' }],
  };
  const originalInput = JSON.parse(JSON.stringify(input));
  const originalDefaults = JSON.parse(JSON.stringify(DEFAULT_WAVE_ENGINE_RULES));

  const normalized = normalizeWaveEngineRules(input);
  normalized.entryTimeframes.push('1h');
  normalized.symbols[0].symbol = 'MUTATED';
  normalized.optimization.ranges.pullbackRatio.min = 0.7;

  assertEqual(input, originalInput, 'input object not mutated');
  assertEqual(DEFAULT_WAVE_ENGINE_RULES, originalDefaults, 'module defaults not mutated');

  const freshClone = cloneWaveEngineRulesDefaults();
  assertEqual(freshClone.entryTimeframes, ['5m', '15m', '1h'], 'fresh clone unaffected by prior mutation');
  assertEqual(freshClone.symbols[0], { symbol: 'BTC', pair: 'BTC/USDC:USDC', enabled: true }, 'fresh clone symbol unaffected');
}

console.log(`\nWave Engine rules invariants: ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
