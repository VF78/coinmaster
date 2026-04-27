/**
 * invariants-trading-rules.ts
 *
 * Verification script for runtime trading-rules precedence invariants.
 * Tests pure logic without starting the server or touching exchange APIs.
 *
 * Invariants checked:
 *   1. Explicit TP/SL overrides runtime defaults
 *   2. Runtime defaults applied when explicit values missing
 *   3. Symbol disabled → blocked (isSymbolEnabled returns false)
 *   4. Whole-percent allocations normalize decimal 100% splits to visible/applied integers
 *   5. Allocation cap exceeded → maxNotionalForSymbol enforces cap
 *   6. riskPerTradePct caps auto-sizing by configured SL distance
 *   7. portfolioGrossCap caps aggregate gross exposure
 *   8. regimeTf is constrained to owner-approved HTF values (1h/4h)
 *   9. Backtest sizing mirrors live riskPerTradePct and portfolioGrossCap limits
 *   10. Trading bias policy normalizes default + per-symbol overrides
 *   11. Trading Rules visible-state rebuild preserves hidden fields
 *
 * Exit code: 0 = all pass, 1 = failures found.
 *
 * Usage:
 *   npx tsx scripts/invariants-trading-rules.ts
 *   # or
 *   npm run invariants:trading-rules
 */

import { normalizeTradingRules } from '../src/shared/tradingRules.js';
import type { TradingRulesSettings } from '../src/shared/dto.js';
import { computeSizeFromRules as computeBacktestSizeFromRules } from '../src/core/backtestEngine.js';
import {
  isSymbolEnabled,
  getCoinAllocation,
  maxNotionalForSymbol,
  computeAllocationSize,
  maxPortfolioGrossNotional,
  wouldExceedPortfolioGrossCap,
  type EffectiveRules,
} from '../src/server/runtimeRules.js';

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

function assertClose(actual: number, expected: number, label: string, eps = 1e-4): void {
  assert(Math.abs(actual - expected) < eps, `${label} (got ${actual}, expected ${expected})`);
}

// ─── Build mock EffectiveRules from TradingRulesSettings ─────────────

function makeRules(overrides?: Partial<TradingRulesSettings>): EffectiveRules {
  const raw = normalizeTradingRules({ ...overrides });
  return {
    manualConfirmation: !raw.autoConfirm,
    maxLeverage: raw.maxLeverage,
    portfolioLeverageCap: raw.maxLeverage,
    dailyDDLimitPct: raw.dailyDrawdown,
    source: 'runtime',
    lastRefreshedAt: new Date().toISOString(),
    raw,
  };
}

function envFallbackRules(): EffectiveRules {
  return {
    manualConfirmation: true,
    maxLeverage: 10,
    portfolioLeverageCap: 10,
    dailyDDLimitPct: 20,
    source: 'env_fallback',
    lastRefreshedAt: null,
    raw: null,
  };
}

// ─── Inline replica of resolveTpSlDefaults (pure, no server deps) ────
// Mirrors src/server/index.ts:1256-1290 exactly.

interface TpSlDefaults {
  stopLoss: number;
  takeProfit: number;
  applied: boolean;
  source: 'explicit' | 'runtime_defaults';
}

function resolveTpSlDefaults(
  rules: EffectiveRules,
  entryPrice: number,
  side: 'buy' | 'sell',
  requestSl: number | undefined,
  requestTp: number | undefined,
): TpSlDefaults | null {
  const hasSl = requestSl !== undefined && Number.isFinite(Number(requestSl)) && Number(requestSl) > 0;
  const hasTp = requestTp !== undefined && Number.isFinite(Number(requestTp)) && Number(requestTp) > 0;

  if (hasSl && hasTp) {
    return { stopLoss: Number(requestSl), takeProfit: Number(requestTp), applied: false, source: 'explicit' };
  }

  if (!rules.raw) return null;

  const tpPct = rules.raw.tpPct;
  const slPct = rules.raw.slPct;
  if (!tpPct || !slPct) return null;

  const isLong = side === 'buy';
  const defaultTp = isLong
    ? entryPrice * (1 + tpPct / 100)
    : entryPrice * (1 - tpPct / 100);
  const defaultSl = isLong
    ? entryPrice * (1 - slPct / 100)
    : entryPrice * (1 + slPct / 100);

  return {
    stopLoss: hasSl ? Number(requestSl) : Number(defaultSl.toFixed(8)),
    takeProfit: hasTp ? Number(requestTp) : Number(defaultTp.toFixed(8)),
    applied: true,
    source: 'runtime_defaults',
  };
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 1: Explicit TP/SL overrides defaults
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 1: explicit TP/SL overrides defaults ──');

{
  const rules = makeRules({ tpPct: 6, slPct: 2 });
  const entry = 50000;

  // Both explicit → use as-is, applied=false, source=explicit
  const r1 = resolveTpSlDefaults(rules, entry, 'buy', 49000, 55000);
  assert(r1 !== null, 'result is not null when both explicit');
  assert(r1!.applied === false, 'applied=false when both explicit');
  assert(r1!.source === 'explicit', 'source=explicit when both provided');
  assert(r1!.stopLoss === 49000, 'explicit SL preserved (49000)');
  assert(r1!.takeProfit === 55000, 'explicit TP preserved (55000)');

  // Partial explicit SL only → SL explicit, TP from defaults
  const r2 = resolveTpSlDefaults(rules, entry, 'buy', 49500, undefined);
  assert(r2 !== null, 'result not null with partial explicit (SL only)');
  assert(r2!.applied === true, 'applied=true when partial');
  assert(r2!.source === 'runtime_defaults', 'source=runtime_defaults when partial');
  assert(r2!.stopLoss === 49500, 'explicit SL preserved in partial');
  assertClose(r2!.takeProfit, entry * 1.06, 'TP auto-calculated from tpPct=6% (long)');

  // Partial explicit TP only → TP explicit, SL from defaults
  const r3 = resolveTpSlDefaults(rules, entry, 'sell', undefined, 47000);
  assert(r3 !== null, 'result not null with partial explicit (TP only, short)');
  assert(r3!.takeProfit === 47000, 'explicit TP preserved in partial (short)');
  assertClose(r3!.stopLoss, entry * 1.02, 'SL auto-calculated from slPct=2% (short)');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 2: Runtime defaults applied when explicit missing
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 2: runtime defaults applied when explicit missing ──');

{
  const rules = makeRules({ tpPct: 6, slPct: 2 });
  const entry = 100000;

  // Long: TP = entry * 1.06, SL = entry * 0.98
  const r1 = resolveTpSlDefaults(rules, entry, 'buy', undefined, undefined);
  assert(r1 !== null, 'defaults produced for long order');
  assert(r1!.applied === true, 'applied=true');
  assert(r1!.source === 'runtime_defaults', 'source=runtime_defaults');
  assertClose(r1!.takeProfit, 106000, 'long TP = entry * 1.06');
  assertClose(r1!.stopLoss, 98000, 'long SL = entry * 0.98');

  // Short: TP = entry * 0.94, SL = entry * 1.02
  const r2 = resolveTpSlDefaults(rules, entry, 'sell', undefined, undefined);
  assert(r2 !== null, 'defaults produced for short order');
  assertClose(r2!.takeProfit, 94000, 'short TP = entry * 0.94');
  assertClose(r2!.stopLoss, 102000, 'short SL = entry * 1.02');

  // Env fallback (no raw) → returns null (no defaults)
  const r3 = resolveTpSlDefaults(envFallbackRules(), entry, 'buy', undefined, undefined);
  assert(r3 === null, 'env_fallback → null (no TP/SL config)');

  // tpPct=0 or slPct=0 → returns null
  const rules0 = makeRules({ tpPct: 0, slPct: 0 });
  const r4 = resolveTpSlDefaults(rules0, entry, 'buy', undefined, undefined);
  assert(r4 === null, 'tpPct=0,slPct=0 → null (no auto-defaults)');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 3: Symbol disabled → blocked
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 3: symbol disabled → blocked ──');

{
  // Default rules: BTC, ETH, SOL all enabled
  const allEnabled = makeRules();
  assert(isSymbolEnabled(allEnabled, 'BTC'), 'BTC enabled by default');
  assert(isSymbolEnabled(allEnabled, 'ETH'), 'ETH enabled by default');
  assert(isSymbolEnabled(allEnabled, 'SOL'), 'SOL enabled by default');
  assert(isSymbolEnabled(allEnabled, 'btc'), 'case-insensitive match (btc → BTC)');

  // Disable SOL
  const solDisabled = makeRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50 },
      { symbol: 'ETH', enabled: true, pct: 30 },
      { symbol: 'SOL', enabled: false, pct: 20 },
    ],
  });
  assert(isSymbolEnabled(solDisabled, 'BTC'), 'BTC still enabled');
  assert(!isSymbolEnabled(solDisabled, 'SOL'), 'SOL disabled → blocked');

  // Unknown symbol → not in rules → blocked
  assert(!isSymbolEnabled(allEnabled, 'DOGE'), 'unknown symbol DOGE → blocked');

  // Dynamic custom symbol from exchange catalog should be supported
  const custom = makeRules({
    coins: [{ symbol: 'goldusdc', enabled: true, pct: 100 }],
  });
  assert(isSymbolEnabled(custom, 'GOLDUSDC'), 'dynamic symbol GOLDUSDC enabled when present in rules');
  assert(getCoinAllocation(custom, 'GOLDUSDC')?.pct === 100, 'custom symbol allocation preserved (100%)');

  // Namespaced symbols should be supported too (e.g. xyz:GOLD)
  const namespaced = makeRules({
    coins: [{ symbol: 'XYZ:gold', enabled: true, pct: 100 }],
  });
  assert(isSymbolEnabled(namespaced, 'xyz:GOLD'), 'namespaced symbol xyz:GOLD enabled');
  assert(getCoinAllocation(namespaced, 'xyz:GOLD')?.symbol === 'xyz:GOLD', 'namespaced symbol normalized to xyz:GOLD');

  // Env fallback (raw=null) → all symbols blocked
  const fb = envFallbackRules();
  assert(!isSymbolEnabled(fb, 'BTC'), 'env_fallback → BTC blocked (no coin config)');
  assert(!isSymbolEnabled(fb, 'ETH'), 'env_fallback → ETH blocked');

  // getCoinAllocation returns undefined for disabled/unknown
  assert(getCoinAllocation(solDisabled, 'SOL')?.enabled === false, 'getCoinAllocation(SOL).enabled is false');
  assert(getCoinAllocation(allEnabled, 'DOGE') === undefined, 'getCoinAllocation(DOGE) is undefined');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 4: Decimal allocation total → whole visible/applied percent
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 4: decimal allocation total → whole visible/applied percent ──');

{
  const normalized = normalizeTradingRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 33.3333 },
      { symbol: 'ETH', enabled: true, pct: 33.3333 },
      { symbol: 'HYPE', enabled: true, pct: 33.3334 },
    ],
  });
  const total = normalized.coins.filter((coin) => coin.enabled).reduce((sum, coin) => sum + coin.pct, 0);

  assert(normalized.coins.every((coin) => Number.isInteger(coin.pct)), 'allocation pct values are whole integers');
  assert(total === 100, 'integer allocation total remains 100%');
  assert(normalized.coins.map((coin) => coin.pct).join(',') === '34,33,33', 'rounding remainder is applied to the first active row');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 5: Allocation notional cap exceeded → blocked
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 5: allocation notional cap exceeded → blocked ──');

{
  const equityUsd = 100_000;

  // coins[].pct is margin allocation; notional cap includes leverage.
  // With 5x default leverage:
  // BTC 50% → $50k margin → max $250k notional
  // ETH 30% → $30k margin → max $150k notional
  // SOL 20% → $20k margin → max $100k notional
  const rules = makeRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50 },
      { symbol: 'ETH', enabled: true, pct: 30 },
      { symbol: 'SOL', enabled: true, pct: 20 },
    ],
  });

  assertClose(maxNotionalForSymbol(equityUsd, rules, 'BTC'), 250000, 'BTC cap = $250k');
  assertClose(maxNotionalForSymbol(equityUsd, rules, 'ETH'), 150000, 'ETH cap = $150k');
  assertClose(maxNotionalForSymbol(equityUsd, rules, 'SOL'), 100000, 'SOL cap = $100k');

  // Simulate: current exposure $240k + new order $15k = $255k > $250k cap → BLOCKED
  const btcCap = maxNotionalForSymbol(equityUsd, rules, 'BTC');
  const currentExposure = 240000;
  const newOrderNotional = 15000;
  assert(currentExposure + newOrderNotional > btcCap, 'total $255k > BTC cap $250k → BLOCKED');

  // Under cap: $240k + $8k = $248k ≤ $250k → allowed
  const smallOrder = 8000;
  assert(currentExposure + smallOrder <= btcCap, 'total $248k ≤ BTC cap $250k → allowed');

  // Disabled symbol → cap is 0
  const disabledRules = makeRules({
    coins: [
      { symbol: 'BTC', enabled: false, pct: 50 },
      { symbol: 'ETH', enabled: true, pct: 30 },
      { symbol: 'SOL', enabled: true, pct: 20 },
    ],
  });
  assert(maxNotionalForSymbol(equityUsd, disabledRules, 'BTC') === 0, 'disabled symbol → cap=0');

  // Zero/negative equity → cap is 0
  assert(maxNotionalForSymbol(0, rules, 'BTC') === 0, 'zero equity → cap=0');
  assert(maxNotionalForSymbol(-1000, rules, 'BTC') === 0, 'negative equity → cap=0');

  // Env fallback (raw=null) → cap is 0
  assert(maxNotionalForSymbol(equityUsd, envFallbackRules(), 'BTC') === 0, 'env_fallback → cap=0');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 5: riskPerTradePct caps auto-sizing
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 5: riskPerTradePct caps auto-sizing ──');

{
  const baseRules = makeRules({
    maxLeverage: 10,
    slPct: 2,
    riskPerTradePct: 0,
    coins: [{ symbol: 'BTC', enabled: true, pct: 50 }],
  });
  const riskRules = makeRules({
    maxLeverage: 10,
    slPct: 2,
    riskPerTradePct: 1,
    coins: [{ symbol: 'BTC', enabled: true, pct: 50 }],
  });

  const base = computeAllocationSize({ symbol: 'BTC', price: 50_000, equityUsd: 100_000, availableUsd: 100_000, rules: baseRules, sizeDecimals: 6 });
  const risk = computeAllocationSize({ symbol: 'BTC', price: 50_000, equityUsd: 100_000, availableUsd: 100_000, rules: riskRules, sizeDecimals: 6 });

  assertClose(maxNotionalForSymbol(100_000, baseRules, 'BTC'), 500_000, 'base symbol cap = equity * 50% * 10x');
  assertClose(maxNotionalForSymbol(100_000, riskRules, 'BTC'), 50_000, 'risk-capped symbol cap = 1% equity / 2% SL');
  assert(base.ok === true, 'base allocation sizing succeeds');
  assert(risk.ok === true, 'risk-capped sizing succeeds');
  if (base.ok && risk.ok) {
    assertClose(base.notionalUsd, 500_000, 'base allocation notional = equity * 50% * 10x');
    assertClose(risk.notionalUsd, 50_000, 'risk cap notional = 1% equity / 2% SL');
    assert(risk.size < base.size, 'risk-capped size is smaller than allocation size');
  }
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 6: portfolioGrossCap caps aggregate gross exposure
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 6: portfolioGrossCap caps aggregate gross exposure ──');

{
  const rules = makeRules({ portfolioGrossCap: 200 });
  assertClose(maxPortfolioGrossNotional(100_000, rules), 200_000, '200% gross cap on $100k equity = $200k');
  assert(!wouldExceedPortfolioGrossCap({ equityUsd: 100_000, rules, currentGrossNotional: 150_000, newOrderNotional: 40_000 }), '$190k ≤ $200k allowed');
  assert(wouldExceedPortfolioGrossCap({ equityUsd: 100_000, rules, currentGrossNotional: 150_000, newOrderNotional: 60_000 }), '$210k > $200k blocked');

  const disabled = makeRules({ portfolioGrossCap: 0 });
  assert(!Number.isFinite(maxPortfolioGrossNotional(100_000, disabled)), '0% gross cap disables aggregate cap');
  assert(!wouldExceedPortfolioGrossCap({ equityUsd: 100_000, rules: disabled, currentGrossNotional: 1_000_000, newOrderNotional: 1_000_000 }), 'disabled cap never blocks');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 7: regimeTf is constrained to HTF values
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 7: regimeTf constrained to 1h/4h ──');

{
  assert(normalizeTradingRules({ regimeTf: '1h' }).regimeTf === '1h', 'regimeTf accepts 1h');
  assert(normalizeTradingRules({ regimeTf: '4h' }).regimeTf === '4h', 'regimeTf accepts 4h');
  assert(normalizeTradingRules({ regimeTf: '5m' }).regimeTf === '1h', 'regimeTf rejects 5m and falls back to 1h');
  assert(normalizeTradingRules({ regimeTf: '15m' }).regimeTf === '1h', 'regimeTf rejects 15m and falls back to 1h');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 8: backtest sizing mirrors live risk caps
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 8: backtest sizing mirrors live risk caps ──');

{
  const base = normalizeTradingRules({
    maxLeverage: 10,
    slPct: 2,
    riskPerTradePct: 0,
    portfolioGrossCap: 0,
    coins: [{ symbol: 'BTC', enabled: true, pct: 50 }],
  });
  const riskCapped = normalizeTradingRules({
    maxLeverage: 10,
    slPct: 2,
    riskPerTradePct: 1,
    portfolioGrossCap: 0,
    coins: [{ symbol: 'BTC', enabled: true, pct: 50 }],
  });
  const grossBlocked = normalizeTradingRules({
    maxLeverage: 10,
    slPct: 2,
    riskPerTradePct: 0,
    portfolioGrossCap: 100,
    coins: [{ symbol: 'BTC', enabled: true, pct: 50 }],
  });

  const baseSize = computeBacktestSizeFromRules(50_000, 100_000, base, 'BTC');
  const riskSize = computeBacktestSizeFromRules(50_000, 100_000, riskCapped, 'BTC');
  const grossSize = computeBacktestSizeFromRules(50_000, 100_000, grossBlocked, 'BTC');

  assertClose(baseSize, 10, 'backtest base size = $500k notional / $50k price');
  assertClose(riskSize, 1, 'backtest risk cap size = $50k notional / $50k price');
  assert(riskSize < baseSize, 'backtest riskPerTradePct caps size below allocation model');
  assert(grossSize === 0, 'backtest portfolioGrossCap blocks oversized new entry instead of shrinking it');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 10: Trading bias policy normalizes default + symbol overrides
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 10: trading bias policy defaults and overrides ──');

{
  const normalized = normalizeTradingRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50, assetClass: 'crypto' },
      { symbol: 'ETH', enabled: true, pct: 25, assetClass: 'other' },
      { symbol: 'XRP', enabled: true, pct: 25, assetClass: 'other' },
      { symbol: 'DOGE', enabled: false, pct: 0, assetClass: 'other' },
    ],
    biasPolicy: {
      defaultBias: 'long',
      symbolOverrides: {
        BTC: { mode: 'symbol', bias: 'short' },
        ETH: { mode: 'symbol', bias: 'short' },
        XRP: { mode: 'symbol', bias: 'off' },
        DOGE: { mode: 'symbol', bias: 'short' },
      },
    },
  });

  assert(normalized.biasPolicy!.defaultBias === 'long', 'default trading bias is preserved');
  assert(normalized.biasPolicy!.symbolOverrides.BTC === undefined, 'crypto symbol override is pruned so the shared control is the only crypto bias');
  assert(normalized.biasPolicy!.symbolOverrides.ETH?.mode === 'symbol', 'enabled other override remains symbol-scoped');
  assert(normalized.biasPolicy!.symbolOverrides.ETH?.bias === 'short', 'enabled other symbol bias is preserved');
  assert(normalized.biasPolicy!.symbolOverrides.XRP?.bias === 'off', 'off symbol bias is preserved for enabled other assets');
  assert(normalized.biasPolicy!.symbolOverrides.DOGE === undefined, 'inactive other symbol override is pruned');
  assert(normalizeTradingRules({ biasPolicy: { defaultBias: 'invalid' as never, symbolOverrides: {} } }).biasPolicy!.defaultBias === 'both', 'invalid default bias falls back to both');
}

// ═══════════════════════════════════════════════════════════════════════
// INVARIANT 11: Visible-state rebuild preserves hidden fields
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 11: visible-state rebuild preserves hidden fields ──');

{
  const saved = normalizeTradingRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50, assetClass: 'crypto' },
      { symbol: 'ETH', enabled: true, pct: 50, assetClass: 'crypto' },
    ],
    emergencyExitTimeframes: ['4h'],
    exitClosePct: 0,
    eventLockoutEnabled: true,
    eventLockoutMinutes: 90,
  });

  const rebuiltFromVisibleState = normalizeTradingRules({
    ...saved,
    coins: saved.coins.filter((coin) => coin.enabled),
    entryTimeframes: saved.entryTimeframes,
    engulfingLookbackCandles: saved.engulfingLookbackCandles,
    fvgRetrace: saved.fvgRetrace,
    fvgMinWidthPct: saved.fvgMinWidthPct,
    fvgRequireSweep: saved.fvgRequireSweep,
    fvgSweepLookbackCandles: saved.fvgSweepLookbackCandles,
    fvgRequireFirstTouch: saved.fvgRequireFirstTouch,
    maxZoneAgeCandles: saved.maxZoneAgeCandles,
    fvgRequireConfirmation: saved.fvgRequireConfirmation,
    fvgConfirmationTimeframes: saved.fvgConfirmationTimeframes,
    maxLeverage: saved.maxLeverage,
    dailyDrawdown: saved.dailyDrawdown,
    tpPct: saved.tpLevels[0],
    tpLevels: saved.tpLevels,
    slPct: saved.slPct,
    regimeFilterEnabled: saved.regimeFilterEnabled,
    regimeTf: saved.regimeTf,
    adxEnabled: saved.adxEnabled,
    adxMin: saved.adxMin,
    minImpulseAtrEnabled: saved.minImpulseAtrEnabled,
    minImpulseAtr: saved.minImpulseAtr,
    timeStopEnabled: saved.timeStopEnabled,
    timeStopBars: saved.timeStopBars,
    riskPerTradeEnabled: saved.riskPerTradeEnabled,
    riskPerTradePct: saved.riskPerTradePct,
    portfolioGrossCapEnabled: saved.portfolioGrossCapEnabled,
    portfolioGrossCap: saved.portfolioGrossCap,
    biasPolicy: saved.biasPolicy,
  });

  assert(JSON.stringify(rebuiltFromVisibleState) === JSON.stringify(saved), 'rebuilding visible Trading Rules state does not create false dirty changes');
  assert(rebuiltFromVisibleState.emergencyExitTimeframes[0] === '4h', 'hidden emergency exit timeframe is preserved');
  assert(rebuiltFromVisibleState.exitClosePct === 0, 'hidden exit close pct is preserved');
  assert(rebuiltFromVisibleState.eventLockoutEnabled === true && rebuiltFromVisibleState.eventLockoutMinutes === 90, 'hidden event lockout settings are preserved');
}

// ─── Summary ─────────────────────────────────────────────────────────

console.log(`\n${'═'.repeat(60)}`);
console.log(`  TOTAL: ${passed + failed}  |  PASSED: ${passed}  |  FAILED: ${failed}`);
console.log(`${'═'.repeat(60)}\n`);

process.exit(failed > 0 ? 1 : 0);
