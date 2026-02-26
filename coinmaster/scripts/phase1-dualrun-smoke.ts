/**
 * phase1-dualrun-smoke.ts
 *
 * Phase-1 dual-run smoke test.
 *
 * Builds mocked snapshots + mocked legacy gate results + mocked engine
 * decisions, runs the full summarize/compare/format flow, and prints
 * concise PASS/FAIL diagnostics for each scenario.
 *
 * Exit 0 = all checks pass, 1 = any failure.
 *
 * Usage:
 *   npx tsx scripts/phase1-dualrun-smoke.ts
 *   npm run invariants:phase1-dualrun
 */

import { buildSnapshot } from '../src/engine/snapshot.js';
import {
  applyPreemption,
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

// ─── Smoke harness ────────────────────────────────────────────────────

let smokePassed = 0;
let smokeFailed = 0;

function check(condition: boolean, label: string): void {
  if (condition) {
    smokePassed++;
    console.log(`    PASS  ${label}`);
  } else {
    smokeFailed++;
    console.error(`    FAIL  ${label}`);
  }
}

const HR = '═'.repeat(62);

console.log(`\n${HR}`);
console.log('  Phase-1 Dual-Run Smoke Test');
console.log(HR);

// ─── Scenario A: Healthy state — both sides agree to allow ────────────

console.log('\n  [Scenario A] Healthy state — legacy=allow, engine=allow');
{
  const snap = buildSnapshot({
    symbol: 'BTC',
    equityUsd: 50_000,
    availableUsd: 40_000,
    dailyDDPct: 3,
    openPositionCount: 0,
    currentPrice: 95_000,
    side: 'long',
  });

  const decisions: EngineDecision[] = [
    riskResultToDecision(evalDailyDrawdownRule(snap, 20), snap.symbol),
    riskResultToDecision(evalEquityRule(snap), snap.symbol),
    { kind: 'ENTRY', action: 'allow', symbol: snap.symbol, reason: 'signal_ok' },
  ];

  const engineSummary = summarizeDecisions(decisions);
  const legacy = { blocked: false };
  const cmp = compareResults(legacy, engineSummary);

  check(!engineSummary.blocked, 'engine: healthy snapshot (DD=3%, equity ok) → allow');
  check(cmp.matches, 'legacy == engine → match');
  check(cmp.mismatches.length === 0, 'zero mismatches');
  console.log(`    ${formatCompareResult(cmp)}`);
}

// ─── Scenario B: DD exceeded — both block, ENTRY preempted ───────────

console.log('\n  [Scenario B] Daily drawdown exceeded — legacy=block, engine=block');
{
  const snap = buildSnapshot({
    symbol: 'ETH',
    equityUsd: 50_000,
    availableUsd: 30_000,
    dailyDDPct: 22,
    openPositionCount: 1,
    currentPrice: 3_200,
  });

  const rawDecisions: EngineDecision[] = [
    riskResultToDecision(evalDailyDrawdownRule(snap, 20), snap.symbol),
    { kind: 'ENTRY', action: 'allow', symbol: snap.symbol, reason: 'signal_ok' },
  ];

  const afterPreemption = applyPreemption(rawDecisions);
  const engineSummary = summarizeDecisions(rawDecisions);
  const legacy = { blocked: true, reason: 'daily_dd_exceeded' };
  const cmp = compareResults(legacy, engineSummary);

  check(engineSummary.blocked, 'engine: DD=22% exceeds limit 20% → block');
  check(engineSummary.reason === 'daily_dd_exceeded', 'engine reason = daily_dd_exceeded');
  check(
    afterPreemption.find((d) => d.kind === 'ENTRY')?.reason === 'preempted_by_risk',
    'ENTRY preempted by RISK (reason=preempted_by_risk)',
  );
  check(cmp.matches, 'legacy == engine → match');
  check(cmp.mismatches.length === 0, 'zero mismatches');
  console.log(`    ${formatCompareResult(cmp)}`);
}

// ─── Scenario C: Engine catches zero-equity, legacy misses it ─────────

console.log('\n  [Scenario C] Zero equity — legacy=allow (missed), engine=block (caught)');
{
  const snap = buildSnapshot({
    symbol: 'SOL',
    equityUsd: 0,          // zero equity — should block
    availableUsd: 0,
    dailyDDPct: 0,
    openPositionCount: 0,
    currentPrice: 150,
  });

  const decisions: EngineDecision[] = [
    riskResultToDecision(evalEquityRule(snap), snap.symbol),
    { kind: 'ENTRY', action: 'allow', symbol: snap.symbol, reason: 'signal_ok' },
  ];

  const engineSummary = summarizeDecisions(decisions);
  const legacy = { blocked: false };          // legacy hasn't caught this case yet
  const cmp = compareResults(legacy, engineSummary);

  check(engineSummary.blocked, 'engine: zero equity → block');
  check(engineSummary.reason === 'zero_or_invalid_equity', 'engine reason = zero_or_invalid_equity');
  check(!cmp.matches, 'mismatch detected (legacy=allow, engine=block)');
  check(cmp.mismatches.length >= 1, 'at least 1 mismatch field');
  check(cmp.mismatches.some((m) => m.field === 'blocked'), 'blocked field mismatch present');
  console.log(`    ${formatCompareResult(cmp)}`);
  console.log(`    [audit-only] mismatch fields: ${cmp.mismatches.map((m) => m.field).join(', ')}`);
}

// ─── Scenario D: EXIT preempts ENTRY — both agree block ───────────────

console.log('\n  [Scenario D] EXIT active — ENTRY preempted, both block');
{
  const decisions: EngineDecision[] = [
    { kind: 'EXIT',  action: 'block', symbol: 'BTC', reason: 'emergency_exit' },
    { kind: 'ENTRY', action: 'allow', symbol: 'BTC', reason: 'signal_ok' },
  ];

  const afterPreemption = applyPreemption(decisions);
  const engineSummary = summarizeDecisions(decisions);
  const legacy = { blocked: true, reason: 'emergency_exit' };
  const cmp = compareResults(legacy, engineSummary);

  const entryAfter = afterPreemption.find((d) => d.kind === 'ENTRY');
  check(entryAfter?.action === 'block', 'ENTRY suppressed by EXIT');
  check(entryAfter?.reason === 'preempted_by_exit', 'suppression reason = preempted_by_exit');
  check(engineSummary.blocked, 'engine summary → blocked');
  check(cmp.matches, 'legacy == engine → match');
  console.log(`    ${formatCompareResult(cmp)}`);
}

// ─── Summary ─────────────────────────────────────────────────────────

const overall = smokeFailed === 0 ? 'PASS' : 'FAIL';
console.log(`\n${HR}`);
console.log(
  `  Overall: ${overall}  |  Checks: ${smokePassed + smokeFailed}  |  Passed: ${smokePassed}  |  Failed: ${smokeFailed}`,
);
console.log(`${HR}\n`);

process.exit(smokeFailed > 0 ? 1 : 0);
