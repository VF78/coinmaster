import type { EngineSnapshot } from '../../snapshot.js';
import { ActionType, RuleTier, type Condition, type ConditionResult, type Rule } from '../../types.js';

/**
 * Fires when request.symbol is not present and enabled in tradingRules.coins.
 *
 * Required snapshot fields:
 *   - request.symbol:     the symbol being requested
 *   - tradingRules.coins: list of configured coins with enabled flags
 */
export const symbolAllowlistCondition: Condition<EngineSnapshot> = {
  id: 'risk.symbol-allowlist.not-permitted',
  evaluate(snapshot: EngineSnapshot): ConditionResult {
    const symbol = snapshot.request?.symbol;
    const coins = snapshot.tradingRules?.coins;

    if (!symbol) {
      return { met: false, detail: { reason: 'no_symbol_in_request' } };
    }

    if (!coins) {
      return { met: false, detail: { reason: 'rules_unavailable' } };
    }

    const allowed = coins.filter((c) => c.enabled).map((c) => c.symbol);
    const permitted = allowed.includes(symbol);

    return {
      met: !permitted,
      detail: { symbol, allowedSymbols: allowed },
    };
  },
};

export function makeSymbolAllowlistRule(overrides?: Partial<Pick<Rule<EngineSnapshot>, 'id' | 'cooldownMs' | 'allowedSources' | 'enabled'>>): Rule<EngineSnapshot> {
  return {
    id: overrides?.id ?? 'risk.symbol-allowlist',
    tier: RuleTier.RISK,
    conditions: [symbolAllowlistCondition],
    action: {
      type: ActionType.BLOCK_REQUEST,
      idempotencyKeyTemplate: 'risk.symbol-allowlist:${timestamp}',
      params: { reason: 'symbol_not_enabled' },
    },
    cooldownMs: overrides?.cooldownMs,
    allowedSources: overrides?.allowedSources ?? ['REQUEST'],
    enabled: overrides?.enabled ?? true,
  };
}
