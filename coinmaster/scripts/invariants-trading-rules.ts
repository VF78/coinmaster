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
 *   4. Allocation cap exceeded → maxNotionalForSymbol enforces cap
 *   5. riskPerTradePct caps auto-sizing by configured SL distance
 *   6. portfolioGrossCap caps aggregate gross exposure
 *   7. regimeTf is constrained to owner-approved HTF values (1h/4h)
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
// INVARIANT 4: Allocation cap exceeded → blocked
// ═══════════════════════════════════════════════════════════════════════

console.log('\n── Invariant 4: allocation cap exceeded → blocked ──');

{
  const equityUsd = 100_000;

  // BTC 50% → max $50k, ETH 30% → $30k, SOL 20% → $20k
  const rules = makeRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50 },
      { symbol: 'ETH', enabled: true, pct: 30 },
      { symbol: 'SOL', enabled: true, pct: 20 },
    ],
  });

  assertClose(maxNotionalForSymbol(equityUsd, rules, 'BTC'), 50000, 'BTC cap = $50k');
  assertClose(maxNotionalForSymbol(equityUsd, rules, 'ETH'), 30000, 'ETH cap = $30k');
  assertClose(maxNotionalForSymbol(equityUsd, rules, 'SOL'), 20000, 'SOL cap = $20k');

  // Simulate: current exposure $40k + new order $15k = $55k > $50k cap → BLOCKED
  const btcCap = maxNotionalForSymbol(equityUsd, rules, 'BTC');
  const currentExposure = 40000;
  const newOrderNotional = 15000;
  assert(currentExposure + newOrderNotional > btcCap, 'total $55k > BTC cap $50k → BLOCKED');

  // Under cap: $40k + $8k = $48k ≤ $50k → allowed
  const smallOrder = 8000;
  assert(currentExposure + smallOrder <= btcCap, 'total $48k ≤ BTC cap $50k → allowed');

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

// ─── Summary ─────────────────────────────────────────────────────────

console.log(`\n${'═'.repeat(60)}`);
console.log(`  TOTAL: ${passed + failed}  |  PASSED: ${passed}  |  FAILED: ${failed}`);
console.log(`${'═'.repeat(60)}\n`);

process.exit(failed > 0 ? 1 : 0);
