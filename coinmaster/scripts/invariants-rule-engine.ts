/**
 * Deterministic invariant checks for rule-engine decision policy.
 *
 * Cases:
 *  1) RISK suppresses ENTRY
 *  2) MANUAL beats REQUEST at same tier
 *  3) cooldown suppression
 */

import { decideRules, type RuleDecision } from '../src/engine/decide.js';
import type { EvaluatedRule } from '../src/engine/evaluate.js';
import { computePortfolioLeverage, type EngineSnapshot } from '../src/engine/snapshot.js';
import { ActionType, RuleTier, type Rule, type RuleEngineSnapshot, type TriggerSource } from '../src/engine/types.js';
import { dailyDrawdownCondition } from '../src/engine/rules/risk/dailyDrawdown.js';
import { leverageCapCondition } from '../src/engine/rules/risk/leverageCap.js';
import {
  compareLegacyVsEngine,
  formatDualRunMismatchLog,
  summarizeEngineRiskDecisions,
  type LegacyGateResult,
} from '../src/engine/dualRunCompare.js';

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string): void {
  if (condition) {
    passed += 1;
    console.log(`  ✓ ${label}`);
  } else {
    failed += 1;
    console.error(`  ✗ FAIL: ${label}`);
  }
}

function mkRule(id: string, tier: RuleTier, cooldownMs?: number): Rule {
  return {
    id,
    tier,
    cooldownMs,
    enabled: true,
    allowedSources: ['TICK', 'REQUEST', 'MANUAL'],
    conditions: [],
    action: {
      type: ActionType.LOG_ONLY,
      idempotencyKeyTemplate: `${id}:${'${timestamp}'}`,
      params: {},
    },
  };
}

function mkEval(rule: Rule, source: TriggerSource, allMet = true): EvaluatedRule {
  return {
    rule,
    source,
    allMet,
    conditionResults: [],
  };
}

function findDecision(decisions: RuleDecision[], ruleId: string): RuleDecision | undefined {
  return decisions.find((d) => d.ruleId === ruleId);
}

console.log('\n── Rule Engine Invariants ──');

// Case 1: RISK suppresses ENTRY
console.log('\nCase 1: RISK suppresses ENTRY');
{
  const risk = mkRule('risk.daily-drawdown', RuleTier.RISK);
  const entry = mkRule('entry.engulfing', RuleTier.ENTRY);

  const decisions = decideRules([mkEval(risk, 'TICK'), mkEval(entry, 'TICK')], {
    nowMs: 1_000_000,
    lastFiredAt: new Map(),
  });

  const riskDecision = findDecision(decisions, risk.id);
  const entryDecision = findDecision(decisions, entry.id);

  assert(riskDecision?.action === 'FIRE', 'risk rule fires');
  assert(entryDecision?.action === 'SUPPRESSED', 'entry rule suppressed');
  assert(entryDecision?.reason === 'preempted_by_higher_tier', 'entry suppression reason is preemption');
}

// Case 2: MANUAL beats REQUEST at same tier
console.log('\nCase 2: MANUAL beats REQUEST at same tier');
{
  const manual = mkRule('entry.manual', RuleTier.ENTRY);
  const request = mkRule('entry.request', RuleTier.ENTRY);

  const decisions = decideRules([
    mkEval(request, 'REQUEST'),
    mkEval(manual, 'MANUAL'),
  ], {
    nowMs: 2_000_000,
    lastFiredAt: new Map(),
  }).filter((d) => d.action === 'FIRE');

  assert(decisions.length === 2, 'both same-tier entry rules can fire');
  assert(decisions[0]?.source === 'MANUAL', 'manual source ordered before request source');
}

// Case 3: Cooldown suppression
console.log('\nCase 3: cooldown suppression');
{
  const cooldownRule = mkRule('risk.cooldown', RuleTier.RISK, 60_000);
  const cooldownState = new Map<string, number>([[cooldownRule.id, 10_000]]);

  const decisions = decideRules([mkEval(cooldownRule, 'TICK')], {
    nowMs: 20_000,
    lastFiredAt: cooldownState,
  });

  const decision = findDecision(decisions, cooldownRule.id);
  assert(decision?.action === 'SUPPRESSED', 'rule on cooldown is suppressed');
  assert(decision?.reason === 'cooldown', 'cooldown suppression reason is set');
}

// Case 4: computePortfolioLeverage
console.log('\nCase 4: computePortfolioLeverage');
{
  // empty positions → 0
  assert(computePortfolioLeverage([], 10_000) === 0, 'empty positions → 0');

  // equity zero → 0
  assert(
    computePortfolioLeverage([{ symbol: 'BTC', side: 'long', size: 1, markPrice: 50_000 }], 0) === 0,
    'equity zero → 0',
  );

  // normal: 1 BTC at markPrice 50000, equity 10000 → leverage 5
  const lev = computePortfolioLeverage(
    [{ symbol: 'BTC', side: 'long', size: 1, markPrice: 50_000 }],
    10_000,
  );
  assert(lev === 5, `normal leverage (1 BTC @ 50k / 10k equity) → 5 (got ${lev})`);
}

// Case 5: dailyDrawdown condition
console.log('\nCase 5: dailyDrawdown condition');
{
  function mkSnap(equity: number, startEquity: number, threshold: number): EngineSnapshot {
    return {
      timestamp: Date.now(),
      source: 'TICK',
      equity,
      dailyStartEquity: startEquity,
      tradingRules: {
        coins: [],
        entryTf: '15m',
        exitTf: '1h',
        entryTimeframes: ['15m'],
        emergencyExitTimeframes: ['1h'],
        engulfingLookbackCandles: 5,
        fvgRetrace: 0.5,
        maxLeverage: 5,
        dailyDrawdown: threshold,
        tpPct: 2,
        slPct: 1,
        autoConfirm: false,
      },
    };
  }

  // Below threshold: 2% drawdown on a 5% limit → not met
  const below = dailyDrawdownCondition.evaluate(mkSnap(9_800, 10_000, 5));
  assert(!below.met, 'dailyDrawdown not met when drawdown (2%) < threshold (5%)');

  // At/above threshold: 6% drawdown on a 5% limit → met
  const above = dailyDrawdownCondition.evaluate(mkSnap(9_400, 10_000, 5));
  assert(above.met, 'dailyDrawdown met when drawdown (6%) >= threshold (5%)');

  // Missing data → not met
  const missing = dailyDrawdownCondition.evaluate({ timestamp: Date.now(), source: 'TICK' });
  assert(!missing.met, 'dailyDrawdown not met when snapshot data missing');
}

// Case 6: leverageCap condition
console.log('\nCase 6: leverageCap condition');
{
  function mkLevSnap(leverage: number, maxLeverage: number): EngineSnapshot {
    return {
      timestamp: Date.now(),
      source: 'TICK',
      portfolioLeverage: leverage,
      tradingRules: {
        coins: [],
        entryTf: '15m',
        exitTf: '1h',
        entryTimeframes: ['15m'],
        emergencyExitTimeframes: ['1h'],
        engulfingLookbackCandles: 5,
        fvgRetrace: 0.5,
        maxLeverage,
        dailyDrawdown: 5,
        tpPct: 2,
        slPct: 1,
        autoConfirm: false,
      },
    };
  }

  // Under cap: 3× leverage, cap 5× → not met
  const under = leverageCapCondition.evaluate(mkLevSnap(3, 5));
  assert(!under.met, 'leverageCap not met when leverage (3) <= max (5)');

  // Over cap: 7× leverage, cap 5× → met
  const over = leverageCapCondition.evaluate(mkLevSnap(7, 5));
  assert(over.met, 'leverageCap met when leverage (7) > max (5)');

  // Missing data → not met
  const missing = leverageCapCondition.evaluate({ timestamp: Date.now(), source: 'TICK' });
  assert(!missing.met, 'leverageCap not met when snapshot data missing');
}

// Case 7: dual-run compare helpers
console.log('\nCase 7: dual-run compare helpers');
{
  // equal paths → no mismatch
  const legacyBlocked: LegacyGateResult = { allowed: false, reason: 'daily-drawdown' };
  const riskRule = mkRule('risk.daily-drawdown', RuleTier.RISK);
  const decisions = decideRules([mkEval(riskRule, 'TICK')], { nowMs: 5_000_000, lastFiredAt: new Map() });
  const summary = summarizeEngineRiskDecisions(decisions);
  const mismatches = compareLegacyVsEngine(legacyBlocked, summary);
  const payload = formatDualRunMismatchLog(legacyBlocked, summary, mismatches);

  assert(!payload.hasMismatch, 'no mismatch when legacy blocked and engine risk fired');
  assert(payload.mismatchCount === 0, 'mismatch count is 0 for equal paths');
  assert(summary.blocked, 'summarize: blocked true when risk rule fired');
  assert(summary.firedRiskRuleIds.includes('risk.daily-drawdown'), 'summarize: firedRiskRuleIds contains fired rule');

  // different paths → mismatch detected
  const legacyAllowed: LegacyGateResult = { allowed: true };
  const mismatchResult = compareLegacyVsEngine(legacyAllowed, summary);
  const mismatchPayload = formatDualRunMismatchLog(legacyAllowed, summary, mismatchResult);

  assert(mismatchPayload.hasMismatch, 'mismatch detected when legacy allowed but engine risk fired');
  assert(mismatchPayload.mismatchCount === 1, 'exactly one mismatch field reported');
  assert(mismatchPayload.mismatches[0]?.field === 'blocked', 'mismatch field is "blocked"');
}

// Case 8: RISK preempts ENTRY in mixed decision set
console.log('\nCase 8: RISK preempts ENTRY in mixed decision set');
{
  // TODO: construct a mixed evaluated-rule set containing at least one RISK-tier rule
  //       and at least one ENTRY-tier rule, both with allMet=true.
  // TODO: call decideRules() with the mixed set.
  // TODO: assert that every ENTRY-tier rule decision has action === 'SUPPRESSED'.
  // TODO: assert that every RISK-tier rule decision has action === 'FIRE'.
  // TODO: assert suppression reason for ENTRY rules is 'preempted_by_higher_tier'.
}

console.log(`\nResult: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  process.exit(1);
}

process.exit(0);
