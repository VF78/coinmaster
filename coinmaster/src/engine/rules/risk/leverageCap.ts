import type { EngineSnapshot } from '../../snapshot.js';
import { ActionType, RuleTier, type Condition, type ConditionResult, type Rule } from '../../types.js';

/**
 * Fires when portfolio leverage exceeds the configured maximum.
 *
 * Required snapshot fields:
 *   - portfolioLeverage: computed total notional / equity
 *   - tradingRules.maxLeverage: the cap (e.g. 5 = 5×)
 */
export const leverageCapCondition: Condition<EngineSnapshot> = {
  id: 'risk.leverage-cap.exceeded',
  evaluate(snapshot: EngineSnapshot): ConditionResult {
    const leverage = snapshot.portfolioLeverage;
    const maxLeverage = snapshot.tradingRules?.maxLeverage;

    if (leverage === undefined || maxLeverage === undefined) {
      return { met: false, detail: { reason: 'missing_data', leverage, maxLeverage } };
    }

    return {
      met: leverage > maxLeverage,
      detail: { leverage: +leverage.toFixed(4), maxLeverage },
    };
  },
};

export function makeLeverageCapRule(overrides?: Partial<Pick<Rule<EngineSnapshot>, 'id' | 'cooldownMs' | 'allowedSources' | 'enabled'>>): Rule<EngineSnapshot> {
  return {
    id: overrides?.id ?? 'risk.leverage-cap',
    tier: RuleTier.RISK,
    conditions: [leverageCapCondition],
    action: {
      type: ActionType.EMERGENCY_CLOSE,
      idempotencyKeyTemplate: 'risk.leverage-cap:${timestamp}',
      params: { reason: 'leverage_limit_exceeded' },
    },
    cooldownMs: overrides?.cooldownMs ?? 30_000,
    allowedSources: overrides?.allowedSources ?? ['TICK'],
    enabled: overrides?.enabled ?? true,
  };
}
