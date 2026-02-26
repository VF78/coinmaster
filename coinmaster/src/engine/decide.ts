import type { DecisionAction, RuleEngineSnapshot, RuleTier, SuppressionReason, TriggerSource } from './types.js';
import { evaluateRules, type EvaluatedRule } from './evaluate.js';

export const SOURCE_PRIORITY: Record<TriggerSource, number> = {
  MANUAL: 3,
  REQUEST: 2,
  TICK: 1,
};

export interface RuleDecision<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  ruleId: string;
  tier: RuleTier;
  source: TriggerSource;
  action: DecisionAction;
  reason?: SuppressionReason;
  evaluated: EvaluatedRule<S>;
}

export interface DecideOptions {
  nowMs?: number;
  lastFiredAt?: Map<string, number>;
  sourcePriority?: Partial<Record<TriggerSource, number>>;
}

function mergedSourcePriority(override?: Partial<Record<TriggerSource, number>>): Record<TriggerSource, number> {
  return {
    TICK: override?.TICK ?? SOURCE_PRIORITY.TICK,
    REQUEST: override?.REQUEST ?? SOURCE_PRIORITY.REQUEST,
    MANUAL: override?.MANUAL ?? SOURCE_PRIORITY.MANUAL,
  };
}

/**
 * Deterministic decision phase with preemption and cooldown handling.
 */
export function decideRules<S extends RuleEngineSnapshot>(
  evaluatedRules: ReadonlyArray<EvaluatedRule<S>>,
  options?: DecideOptions,
): RuleDecision<S>[] {
  const nowMs = options?.nowMs ?? Date.now();
  const lastFiredAt = options?.lastFiredAt;
  const sourcePriority = mergedSourcePriority(options?.sourcePriority);

  const notMet: RuleDecision<S>[] = evaluatedRules
    .filter((item) => !item.allMet)
    .map((item) => ({
      ruleId: item.rule.id,
      tier: item.rule.tier,
      source: item.source,
      action: 'SUPPRESSED',
      reason: 'conditions_not_met',
      evaluated: item,
    }));

  const met = evaluatedRules
    .filter((item) => item.allMet)
    .slice()
    .sort((a, b) => {
      if (a.rule.tier !== b.rule.tier) return b.rule.tier - a.rule.tier;

      const sourceDiff = (sourcePriority[b.source] ?? 0) - (sourcePriority[a.source] ?? 0);
      if (sourceDiff !== 0) return sourceDiff;

      return a.rule.id.localeCompare(b.rule.id);
    });

  let blockBelowTier = Number.NEGATIVE_INFINITY;
  const decisions: RuleDecision<S>[] = [...notMet];

  for (const item of met) {
    if (item.rule.tier < blockBelowTier) {
      decisions.push({
        ruleId: item.rule.id,
        tier: item.rule.tier,
        source: item.source,
        action: 'SUPPRESSED',
        reason: 'preempted_by_higher_tier',
        evaluated: item,
      });
      continue;
    }

    const cooldownMs = item.rule.cooldownMs ?? 0;
    if (cooldownMs > 0 && lastFiredAt) {
      const last = lastFiredAt.get(item.rule.id);
      if (last !== undefined && nowMs - last < cooldownMs) {
        decisions.push({
          ruleId: item.rule.id,
          tier: item.rule.tier,
          source: item.source,
          action: 'SUPPRESSED',
          reason: 'cooldown',
          evaluated: item,
        });
        continue;
      }
    }

    decisions.push({
      ruleId: item.rule.id,
      tier: item.rule.tier,
      source: item.source,
      action: 'FIRE',
      evaluated: item,
    });

    if (lastFiredAt) {
      lastFiredAt.set(item.rule.id, nowMs);
    }

    if (item.rule.tier >= 300) {
      blockBelowTier = Math.max(blockBelowTier, 300);
      continue;
    }

    if (item.rule.tier >= 200) {
      blockBelowTier = Math.max(blockBelowTier, 200);
    }
  }

  return decisions
    .slice()
    .sort((a, b) => {
      if (a.action !== b.action) return a.action === 'FIRE' ? -1 : 1;
      if (a.tier !== b.tier) return b.tier - a.tier;

      const sourceDiff = (sourcePriority[b.source] ?? 0) - (sourcePriority[a.source] ?? 0);
      if (sourceDiff !== 0) return sourceDiff;

      return a.ruleId.localeCompare(b.ruleId);
    });
}

export function evaluateAndDecide<S extends RuleEngineSnapshot>(
  rules: ReadonlyArray<import('./types.js').Rule<S>>,
  snapshot: S,
  options?: DecideOptions,
): { evaluations: EvaluatedRule<S>[]; decisions: RuleDecision<S>[] } {
  const evaluations = evaluateRules(rules, snapshot);
  const decisions = decideRules(evaluations, options);
  return { evaluations, decisions };
}
