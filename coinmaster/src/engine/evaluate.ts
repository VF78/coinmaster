import type { ConditionResult, Rule, RuleEngineSnapshot, TriggerSource } from './types.js';

export interface EvaluatedCondition {
  conditionId: string;
  result: ConditionResult;
}

export interface EvaluatedRule<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  rule: Rule<S>;
  source: TriggerSource;
  conditionResults: EvaluatedCondition[];
  allMet: boolean;
}

/**
 * Pure evaluation phase: no side-effects, only predicate checks.
 */
export function evaluateRules<S extends RuleEngineSnapshot>(
  rules: ReadonlyArray<Rule<S>>,
  snapshot: S,
): EvaluatedRule<S>[] {
  return rules
    .filter((rule) => rule.enabled)
    .filter((rule) => rule.allowedSources.includes(snapshot.source))
    .map((rule) => {
      const conditionResults: EvaluatedCondition[] = rule.conditions.map((condition) => ({
        conditionId: condition.id,
        result: condition.evaluate(snapshot),
      }));

      return {
        rule,
        source: snapshot.source,
        conditionResults,
        allMet: conditionResults.every((entry) => entry.result.met),
      };
    });
}
