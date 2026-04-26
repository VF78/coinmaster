/**
 * invariants-allocation-sizing.ts
 *
 * Deterministic verification of computeAllocationSize() — the pure function
 * that derives position size from equity, available margin, coin allocation %
 * and leverage.
 *
 * No server, no exchange, no DB — tests pure arithmetic only.
 *
 * Cases:
 *   1. Happy-path BTC sizing (equity=100, available=100, BTC 50%, lev 10)
 *   2. Sequential allocation: after BTC margin consumed, SOL sizing
 *   3. Low available margin → size clips to executable available-margin cap
 *   4. Disabled symbol → symbol_not_enabled
 *
 * Exit code: 0 = all pass, 1 = failures found.
 *
 * Usage:
 *   npx tsx scripts/invariants-allocation-sizing.ts
 *   # or
 *   npm run invariants:allocation-sizing
 */

import { normalizeTradingRules } from '../src/shared/tradingRules.js';
import type { TradingRulesSettings } from '../src/shared/dto.js';
import {
  computeAllocationSize,
  type EffectiveRules,
  type AllocationSizingOutcome,
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

function assertClose(actual: number, expected: number, label: string, eps = 0.01): void {
  assert(Math.abs(actual - expected) < eps, `${label} (got ${actual}, expected ${expected})`);
}

function assertError(outcome: AllocationSizingOutcome, reason: string, label: string): void {
  assert(!outcome.ok, `${label} — outcome.ok is false`);
  if (!outcome.ok) {
    assert(outcome.reason === reason, `${label} — reason="${outcome.reason}" expected="${reason}"`);
  }
}

// ─── Build mock EffectiveRules ───────────────────────────────────────

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

// ═════════════════════════════════════════════════════════════════════
// CASE 1: Happy-path BTC sizing
//   equity=100, available=100, BTC=50%, leverage=10
//   → margin = 100 * 0.50 = 50
//   → notional = 50 * 10 = 500
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 1: BTC happy-path sizing ──');

{
  const rules = makeRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50 },
      { symbol: 'ETH', enabled: true, pct: 30 },
      { symbol: 'SOL', enabled: true, pct: 20 },
    ],
    maxLeverage: 10,
  });

  const r = computeAllocationSize({
    symbol: 'BTC',
    price: 50000,
    equityUsd: 100,
    availableUsd: 100,
    rules,
  });

  assert(r.ok === true, 'outcome is ok');
  if (r.ok) {
    assertClose(r.marginUsd, 50, 'marginUsd = 50');
    assertClose(r.notionalUsd, 500, 'notionalUsd = 500');
    assert(r.effectiveLeverage === 10, 'effectiveLeverage = 10');
    assert(r.allocationPct === 50, 'allocationPct = 50');
    // size = 500 / 50000 = 0.01
    assertClose(r.size, 0.01, 'size = 0.01');
  }
}

// ═════════════════════════════════════════════════════════════════════
// CASE 2: Sequential allocation — after BTC margin consumed
//   equity=100, BTC consumed $50 margin → available=50
//   SOL=20%, leverage=10
//   → margin = 100 * 0.20 = 20  (available 50 >= 20 ✓)
//   → notional = 20 * 10 = 200
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 2: SOL after BTC — sequential allocation ──');

{
  const rules = makeRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50 },
      { symbol: 'ETH', enabled: true, pct: 30 },
      { symbol: 'SOL', enabled: true, pct: 20 },
    ],
    maxLeverage: 10,
  });

  const r = computeAllocationSize({
    symbol: 'SOL',
    price: 100,
    equityUsd: 100,
    availableUsd: 50, // after BTC consumed $50
    rules,
  });

  assert(r.ok === true, 'outcome is ok');
  if (r.ok) {
    assertClose(r.marginUsd, 20, 'marginUsd = 20');
    assertClose(r.notionalUsd, 200, 'notionalUsd = 200');
    assert(r.effectiveLeverage === 10, 'effectiveLeverage = 10');
    assert(r.allocationPct === 20, 'allocationPct = 20');
    // size = 200 / 100 = 2.0
    assertClose(r.size, 2.0, 'size = 2.0');
  }
}

// ═════════════════════════════════════════════════════════════════════
// CASE 3: Low available margin clips size instead of failing
//   equity=100, available=10, ETH=30%, leverage=10
//   → targetMargin = 30, but usable available margin = 9 (90% buffer)
//   → notional = 90, size = floor(90 / 3000, 6 decimals)
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 3: low available margin clips size ──');

{
  const rules = makeRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50 },
      { symbol: 'ETH', enabled: true, pct: 30 },
      { symbol: 'SOL', enabled: true, pct: 20 },
    ],
    maxLeverage: 10,
  });

  const r = computeAllocationSize({
    symbol: 'ETH',
    price: 3000,
    equityUsd: 100,
    availableUsd: 10, // need 30, only 10 available
    rules,
  });

  assert(r.ok === true, 'ETH low-margin outcome is ok');
  if (r.ok) {
    assertClose(r.marginUsd, 9, 'marginUsd clipped to usable available margin');
    assertClose(r.notionalUsd, 90, 'notionalUsd clipped to available margin * leverage');
    assertClose(r.size, 0.03, 'size clipped to executable quantity', 0.000001);
  }
}

// ═════════════════════════════════════════════════════════════════════
// CASE 4: Disabled symbol → symbol_not_enabled
// ═════════════════════════════════════════════════════════════════════

console.log('\n── Case 4: disabled symbol → symbol_not_enabled ──');

{
  const rules = makeRules({
    coins: [
      { symbol: 'BTC', enabled: true, pct: 50 },
      { symbol: 'ETH', enabled: false, pct: 30 },
      { symbol: 'SOL', enabled: true, pct: 20 },
    ],
    maxLeverage: 10,
  });

  // ETH disabled → symbol_not_enabled
  const r1 = computeAllocationSize({
    symbol: 'ETH',
    price: 3000,
    equityUsd: 100,
    availableUsd: 100,
    rules,
  });
  assertError(r1, 'symbol_not_enabled', 'ETH disabled');

  // Unknown symbol (DOGE) → also symbol_not_enabled
  const r2 = computeAllocationSize({
    symbol: 'DOGE',
    price: 0.15,
    equityUsd: 100,
    availableUsd: 100,
    rules,
  });
  assertError(r2, 'symbol_not_enabled', 'DOGE not in rules');

  // Env fallback (raw=null) → symbol_not_enabled
  const fb: EffectiveRules = {
    manualConfirmation: true,
    maxLeverage: 10,
    portfolioLeverageCap: 10,
    dailyDDLimitPct: 20,
    source: 'env_fallback',
    lastRefreshedAt: null,
    raw: null,
  };
  const r3 = computeAllocationSize({
    symbol: 'BTC',
    price: 50000,
    equityUsd: 100,
    availableUsd: 100,
    rules: fb,
  });
  assertError(r3, 'symbol_not_enabled', 'env_fallback → all symbols blocked');
}

// ─── Summary ─────────────────────────────────────────────────────────

console.log(`\n${'═'.repeat(60)}`);
console.log(`  TOTAL: ${passed + failed}  |  PASSED: ${passed}  |  FAILED: ${failed}`);
console.log(`${'═'.repeat(60)}\n`);

process.exit(failed > 0 ? 1 : 0);
