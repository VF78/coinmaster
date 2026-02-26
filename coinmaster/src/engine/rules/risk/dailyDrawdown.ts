import type { EngineSnapshot } from '../../snapshot.js';
import { ActionType, RuleTier, type Condition, type ConditionResult, type Rule } from '../../types.js';

/**
 * Fires when the intraday equity drawdown exceeds the configured daily limit.
 *
 * Required snapshot fields:
 *   - equity: current account equity (USD)
 *   - dailyStartEquity: equity at start of trading day (set by snapshot builder)
 *   - tradingRules.dailyDrawdown: threshold in percent (e.g. 5 = 5%)
 */
export const dailyDrawdownCondition: Condition<EngineSnapshot> = {
  id: 'risk.daily-drawdown.threshold-exceeded',
  evaluate(snapshot: EngineSnapshot): ConditionResult {
    const equity = snapshot.equity;
    const startEquity = snapshot['dailyStartEquity'] as number | undefined;
    const threshold = snapshot.tradingRules?.dailyDrawdown;

    if (
      equity === undefined ||
      startEquity === undefined ||
      threshold === undefined ||
      startEquity <= 0
    ) {
      return { met: false, detail: { reason: 'missing_data', equity, startEquity, threshold } };
    }

    const drawdownPct = ((startEquity - equity) / startEquity) * 100;
    return {
      met: drawdownPct >= threshold,
      detail: { drawdownPct: +drawdownPct.toFixed(4), threshold, equity, startEquity },
    };
  },
};

export function makeDailyDrawdownRule(overrides?: Partial<Pick<Rule<EngineSnapshot>, 'id' | 'cooldownMs' | 'allowedSources' | 'enabled'>>): Rule<EngineSnapshot> {
  return {
    id: overrides?.id ?? 'risk.daily-drawdown',
    tier: RuleTier.RISK,
    conditions: [dailyDrawdownCondition],
    action: {
      type: ActionType.BLOCK_REQUEST,
      idempotencyKeyTemplate: 'risk.daily-drawdown:${timestamp}',
      params: { reason: 'daily_drawdown_limit_exceeded' },
    },
    cooldownMs: overrides?.cooldownMs ?? 60_000,
    allowedSources: overrides?.allowedSources ?? ['TICK', 'REQUEST'],
    enabled: overrides?.enabled ?? true,
  };
}
