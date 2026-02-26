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
import { computePortfolioLeverage } from '../src/engine/snapshot.js';
import { ActionType, RuleTier, type Rule, type RuleEngineSnapshot, type TriggerSource } from '../src/engine/types.js';

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

console.log(`\nResult: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  process.exit(1);
}

process.exit(0);
