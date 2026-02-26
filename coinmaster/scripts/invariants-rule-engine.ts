/**
 * invariants-rule-engine.ts
 *
 * Invariant verification for the Phase-1 rule engine.
 * Tests pure functions only — no server, no DB, no exchange.
 *
 * Coverage:
 *   P1a  Snapshot builder — well-formed output, timestamp defaults.
 *   P1b  RISK rule evaluation — block/allow paths, reason + context.
 *   P1c  dualRunCompare basic — summarize, compare, format.
 *   P1d  Preemption ordering + mismatch detection depth:
 *        P1d-1  RISK preempts ENTRY (ordering + suppressionReason).
 *        P1d-2  EXIT preempts ENTRY (multiple entries suppressed).
 *        P1d-3  Mismatch detection ≥2 fields (blocked + reason).
 *        P1d-4  Negative control: legacy == engine → zero mismatches.
 *
 * Exit 0 = all pass, 1 = any failure.
 *
 * Usage:
 *   npx tsx scripts/invariants-rule-engine.ts
 *   npm run invariants:rule-engine
 */

import { buildSnapshot } from '../src/engine/snapshot.js';
import {
  applyPreemption,
  countSuppressedEntries,
  evalDailyDrawdownRule,
  evalEquityRule,
  riskResultToDecision,
} from '../src/engine/rules/risk/index.js';
import {
  compareResults,
  formatCompareResult,
  summarizeDecisions,
} from '../src/engine/dualRunCompare.js';
import type { EngineDecision } from '../src/engine/types.js';

// ─── Harness ──────────────────────────────────────────────────────────

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

// ═════════════════════════════════════════════════════════════════════
// P1a: Snapshot builder
// ═════════════════════════════════════════════════════════════════════

console.log('\n── P1a: Snapshot builder ──');

{
  const snap = buildSnapshot({
    symbol: 'BTC',
    equityUsd: 10_000,
    availableUsd: 8_000,
    dailyDDPct: 5,
    openPositionCount: 1,
    currentPrice: 50_000,
    side: 'long',
  });

  assert(snap.symbol === 'BTC', 'symbol preserved');
  assert(snap.equityUsd === 10_000, 'equityUsd preserved');
  assert(snap.availableUsd === 8_000, 'availableUsd preserved');
  assert(snap.dailyDDPct === 5, 'dailyDDPct preserved');
  assert(snap.openPositionCount === 1, 'openPositionCount preserved');
  assert(snap.currentPrice === 50_000, 'currentPrice preserved');
  assert(snap.side === 'long', 'side preserved');
  assert(typeof snap.timestamp === 'string' && snap.timestamp.length > 0, 'timestamp auto-populated');

  // Explicit timestamp is respected
  const ts = '2026-01-01T00:00:00.000Z';
  const snap2 = buildSnapshot({
    symbol: 'ETH',
    equityUsd: 5_000,
    availableUsd: 4_000,
    dailyDDPct: 0,
    openPositionCount: 0,
    currentPrice: 3_000,
    timestamp: ts,
  });
  assert(snap2.timestamp === ts, 'explicit timestamp preserved');

  // Optional side is undefined when not provided
  assert(snap2.side === undefined, 'side=undefined when not provided');
}

// ═════════════════════════════════════════════════════════════════════
// P1b: RISK rule evaluation
// ═════════════════════════════════════════════════════════════════════

console.log('\n── P1b: RISK rule evaluation ──');

{
  const snap = buildSnapshot({
    symbol: 'BTC',
    equityUsd: 10_000,
    availableUsd: 5_000,
    dailyDDPct: 5,
    openPositionCount: 0,
    currentPrice: 50_000,
  });

  // DD within limit → allow
  const r1 = evalDailyDrawdownRule(snap, 20);
  assert(r1.action === 'allow', 'DD 5% < limit 20% → allow');
  assert(r1.reason === 'dd_within_limit', 'DD allow reason = dd_within_limit');

  // DD at limit → block
  const r2 = evalDailyDrawdownRule({ ...snap, dailyDDPct: 20 }, 20);
  assert(r2.action === 'block', 'DD 20% at limit 20% → block');
  assert(r2.reason === 'daily_dd_exceeded', 'DD block reason = daily_dd_exceeded');
  assert(r2.context?.['actual'] === 20 && r2.context?.['limit'] === 20, 'DD context has actual + limit');

  // DD over limit → block
  const r3 = evalDailyDrawdownRule({ ...snap, dailyDDPct: 25 }, 20);
  assert(r3.action === 'block', 'DD 25% > limit 20% → block');

  // Equity guard: zero equity → block
  const r4 = evalEquityRule({ ...snap, equityUsd: 0 });
  assert(r4.action === 'block', 'zero equity → block');
  assert(r4.reason === 'zero_or_invalid_equity', 'equity block reason = zero_or_invalid_equity');

  // Equity guard: negative equity → block
  const r5 = evalEquityRule({ ...snap, equityUsd: -100 });
  assert(r5.action === 'block', 'negative equity → block');

  // Equity guard: valid equity → allow
  const r6 = evalEquityRule(snap);
  assert(r6.action === 'allow', 'valid equity → allow');
  assert(r6.reason === 'equity_ok', 'equity allow reason = equity_ok');

  // riskResultToDecision wraps into EngineDecision correctly
  const d = riskResultToDecision(r2, 'BTC');
  assert(d.kind === 'RISK', 'wrapped decision kind = RISK');
  assert(d.action === 'block', 'wrapped decision action = block');
  assert(d.symbol === 'BTC', 'wrapped decision symbol = BTC');
  assert(d.reason === 'daily_dd_exceeded', 'wrapped decision reason preserved');
}

// ═════════════════════════════════════════════════════════════════════
// P1c: dualRunCompare basic
// ═════════════════════════════════════════════════════════════════════

console.log('\n── P1c: dualRunCompare basic ──');

{
  const allowDecisions: EngineDecision[] = [
    { kind: 'ENTRY', action: 'allow', symbol: 'BTC', reason: 'signal_ok' },
  ];
  const blockDecisions: EngineDecision[] = [
    { kind: 'RISK', action: 'block', symbol: 'BTC', reason: 'daily_dd_exceeded' },
  ];

  // Allow decisions → summary.blocked=false
  const s1 = summarizeDecisions(allowDecisions);
  assert(s1.blocked === false, 'all-allow decisions → summary.blocked=false');
  assert(s1.reason === undefined, 'allow summary has no reason');

  // Block decision → summary.blocked=true
  const s2 = summarizeDecisions(blockDecisions);
  assert(s2.blocked === true, 'block decision → summary.blocked=true');
  assert(s2.reason === 'daily_dd_exceeded', 'block summary reason preserved');

  // Both agree allow → match
  const cr1 = compareResults({ blocked: false }, { blocked: false });
  assert(cr1.matches === true, 'legacy=allow engine=allow → match');
  assert(cr1.mismatches.length === 0, 'zero mismatches when fully matching');

  // Both agree block with same reason → match
  const cr2 = compareResults(
    { blocked: true, reason: 'daily_dd_exceeded' },
    { blocked: true, reason: 'daily_dd_exceeded' },
  );
  assert(cr2.matches === true, 'both block same reason → match');
  assert(cr2.mismatches.length === 0, 'zero mismatches when same reason');

  // Format: match result
  const fmt1 = formatCompareResult(cr1);
  assert(fmt1.includes('[dual-run]'), 'format output has [dual-run] prefix');
  assert(fmt1.includes('MATCH'), 'format match result contains MATCH');

  // Mismatch on blocked field
  const cr3 = compareResults({ blocked: true }, { blocked: false });
  assert(cr3.matches === false, 'legacy=blocked engine=allow → mismatch');
  assert(cr3.mismatches.some((m) => m.field === 'blocked'), 'mismatch on blocked field');

  // Format: mismatch result
  const fmt2 = formatCompareResult(cr3);
  assert(fmt2.includes('MISMATCH'), 'format mismatch result contains MISMATCH');
}

// ═════════════════════════════════════════════════════════════════════
// P1d-1: RISK preempts ENTRY in mixed decision set
// ═════════════════════════════════════════════════════════════════════

console.log('\n── P1d-1: RISK preempts ENTRY (mixed decision set) ──');

{
  const mixed: EngineDecision[] = [
    { kind: 'ENTRY', action: 'allow', symbol: 'BTC', reason: 'signal_ok' },
    { kind: 'RISK',  action: 'block', symbol: 'BTC', reason: 'daily_dd_exceeded' },
  ];

  const after = applyPreemption(mixed);

  // RISK decision is unchanged
  const riskD = after.find((d) => d.kind === 'RISK');
  assert(riskD?.action === 'block', 'RISK decision unchanged after preemption');
  assert(riskD?.reason === 'daily_dd_exceeded', 'RISK reason unchanged');

  // ENTRY was suppressed with correct reason
  const entryD = after.find((d) => d.kind === 'ENTRY');
  assert(entryD?.action === 'block', 'ENTRY suppressed when RISK blocks');
  assert(entryD?.reason === 'preempted_by_risk', 'ENTRY suppression reason = preempted_by_risk');

  // Suppression counter
  const suppressed = countSuppressedEntries(mixed, after);
  assert(suppressed === 1, 'countSuppressedEntries = 1');

  // summarizeDecisions applies preemption internally; RISK wins
  const summary = summarizeDecisions(mixed);
  assert(summary.blocked === true, 'mixed set with RISK block → summary.blocked=true');
  assert(summary.reason === 'daily_dd_exceeded', 'summary.reason = RISK reason (not preempted_by_risk)');

  // No preemption when no blocking decisions
  const allAllow: EngineDecision[] = [
    { kind: 'ENTRY', action: 'allow', symbol: 'BTC', reason: 'signal_ok' },
    { kind: 'RISK',  action: 'allow', symbol: 'BTC', reason: 'dd_within_limit' },
  ];
  const afterAllAllow = applyPreemption(allAllow);
  assert(afterAllAllow[0].action === 'allow', 'no preemption when no blocking decisions');
}

// ═════════════════════════════════════════════════════════════════════
// P1d-2: EXIT preempts ENTRY
// ═════════════════════════════════════════════════════════════════════

console.log('\n── P1d-2: EXIT preempts ENTRY ──');

{
  const mixed: EngineDecision[] = [
    { kind: 'ENTRY', action: 'allow', symbol: 'ETH', reason: 'signal_ok' },
    { kind: 'ENTRY', action: 'allow', symbol: 'ETH', reason: 'momentum_ok' },
    { kind: 'EXIT',  action: 'block', symbol: 'ETH', reason: 'emergency_exit' },
  ];

  const after = applyPreemption(mixed);

  // Both ENTRY decisions are suppressed
  const entryDecisions = after.filter((d) => d.kind === 'ENTRY');
  assert(entryDecisions.length === 2, 'two ENTRY decisions present');
  assert(entryDecisions.every((d) => d.action === 'block'), 'both ENTRY suppressed');
  assert(
    entryDecisions.every((d) => d.reason === 'preempted_by_exit'),
    'both suppressed with reason=preempted_by_exit',
  );

  // EXIT decision is unchanged
  const exitD = after.find((d) => d.kind === 'EXIT');
  assert(exitD?.action === 'block', 'EXIT decision unchanged');
  assert(exitD?.reason === 'emergency_exit', 'EXIT reason unchanged');

  // Suppression counter
  const suppressed = countSuppressedEntries(mixed, after);
  assert(suppressed === 2, 'countSuppressedEntries = 2 (both entries suppressed)');

  // RISK takes priority over EXIT when both block
  const riskWins: EngineDecision[] = [
    { kind: 'ENTRY', action: 'allow', symbol: 'ETH', reason: 'signal_ok' },
    { kind: 'EXIT',  action: 'block', symbol: 'ETH', reason: 'emergency_exit' },
    { kind: 'RISK',  action: 'block', symbol: 'ETH', reason: 'daily_dd_exceeded' },
  ];
  const afterRiskWins = applyPreemption(riskWins);
  const suppressedEntry = afterRiskWins.find((d) => d.kind === 'ENTRY');
  assert(
    suppressedEntry?.reason === 'preempted_by_risk',
    'RISK preemption reason wins over EXIT when both block',
  );
}

// ═════════════════════════════════════════════════════════════════════
// P1d-3: Mismatch detection — blocked + reason fields
// ═════════════════════════════════════════════════════════════════════

console.log('\n── P1d-3: Mismatch detection — blocked + reason fields ──');

{
  // Legacy says block(daily_dd_exceeded), engine says allow → 2-field mismatch
  const legacy = { blocked: true, reason: 'daily_dd_exceeded' };
  const engine: { blocked: boolean; reason: undefined } = { blocked: false, reason: undefined };

  const result = compareResults(legacy, engine);
  assert(result.matches === false, 'divergent results → matches=false');
  assert(result.mismatches.length >= 2, 'at least 2 mismatches detected');

  const blockedMismatch = result.mismatches.find((m) => m.field === 'blocked');
  assert(blockedMismatch !== undefined, 'blocked field mismatch present');
  assert(blockedMismatch?.legacy === true, 'blocked mismatch: legacy=true');
  assert(blockedMismatch?.engine === false, 'blocked mismatch: engine=false');

  const reasonMismatch = result.mismatches.find((m) => m.field === 'reason');
  assert(reasonMismatch !== undefined, 'reason field mismatch present');
  assert(reasonMismatch?.legacy === 'daily_dd_exceeded', 'reason mismatch: legacy=daily_dd_exceeded');
  assert(reasonMismatch?.engine === null, 'reason mismatch: engine=null (undefined → null)');

  // Format output references both field names
  const fmt = formatCompareResult(result);
  assert(fmt.includes('blocked'), 'format output mentions blocked field');
  assert(fmt.includes('reason'), 'format output mentions reason field');

  // Reason-only mismatch (blocked agrees, reason differs)
  const r2 = compareResults(
    { blocked: true, reason: 'leverage_cap' },
    { blocked: true, reason: 'daily_dd_exceeded' },
  );
  assert(r2.matches === false, 'reason-only mismatch → matches=false');
  assert(r2.mismatches.length === 1, 'exactly 1 mismatch (reason only)');
  assert(r2.mismatches[0].field === 'reason', 'the mismatched field is reason');
}

// ═════════════════════════════════════════════════════════════════════
// P1d-4: Negative control — legacy == engine → zero mismatches
// ═════════════════════════════════════════════════════════════════════

console.log('\n── P1d-4: Negative control — legacy == engine → zero mismatches ──');

{
  // Scenario A: both block with same reason
  const legacyA = { blocked: true, reason: 'leverage_cap_exceeded' };
  const engineDecisionsA: EngineDecision[] = [
    { kind: 'RISK', action: 'block', symbol: 'BTC', reason: 'leverage_cap_exceeded' },
  ];
  const engineSummaryA = summarizeDecisions(engineDecisionsA);
  const resultA = compareResults(legacyA, engineSummaryA);
  assert(resultA.matches === true, 'both block same reason → matches=true');
  assert(resultA.mismatches.length === 0, 'zero mismatches when identical (block)');

  // Scenario B: both allow
  const legacyB = { blocked: false };
  const engineDecisionsB: EngineDecision[] = [
    { kind: 'ENTRY', action: 'allow', symbol: 'ETH', reason: 'signal_ok' },
    { kind: 'RISK',  action: 'allow', symbol: 'ETH', reason: 'dd_within_limit' },
  ];
  const engineSummaryB = summarizeDecisions(engineDecisionsB);
  const resultB = compareResults(legacyB, engineSummaryB);
  assert(resultB.matches === true, 'both allow → matches=true');
  assert(resultB.mismatches.length === 0, 'zero mismatches when both allow');

  // Scenario C: mixed (RISK allows, ENTRY allows) → both sides agree allow
  const legacyC = { blocked: false };
  const engineDecisionsC: EngineDecision[] = [
    { kind: 'RISK',  action: 'allow', symbol: 'SOL', reason: 'equity_ok' },
    { kind: 'ENTRY', action: 'allow', symbol: 'SOL', reason: 'signal_ok' },
  ];
  const engineSummaryC = summarizeDecisions(engineDecisionsC);
  const resultC = compareResults(legacyC, engineSummaryC);
  assert(resultC.matches === true, 'mixed-allow set → zero mismatches');
}

// ─── Summary ─────────────────────────────────────────────────────────

console.log(`\n${'═'.repeat(60)}`);
console.log(`  TOTAL: ${passed + failed}  |  PASSED: ${passed}  |  FAILED: ${failed}`);
console.log(`${'═'.repeat(60)}\n`);

process.exit(failed > 0 ? 1 : 0);
