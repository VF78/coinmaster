import type { EngineSnapshot } from '../../snapshot.js';
import { ActionType, RuleTier, type Condition, type ConditionResult, type Rule } from '../../types.js';

/**
 * Fires when the requested position notional would exceed the per-symbol
 * allocation cap defined in tradingRules.coins[].pct.
 *
 * Required snapshot fields:
 *   - request.symbol: the target symbol
 *   - request.size:   position size in base asset
 *   - equity:         current equity (USD) used to derive max allocation
 *   - prices:         mid prices keyed by symbol
 *   - tradingRules.coins: per-symbol allocation config
 */
export const allocationCapCondition: Condition<EngineSnapshot> = {
  id: 'risk.allocation-cap.exceeded',
  evaluate(snapshot: EngineSnapshot): ConditionResult {
    const { request, equity, prices, tradingRules } = snapshot;
    const symbol = request?.symbol;
    const size = typeof request?.size === 'number' ? request.size : undefined;

    if (!symbol || size === undefined || equity === undefined || !prices || !tradingRules) {
      return { met: false, detail: { reason: 'missing_data' } };
    }

    const coin = tradingRules.coins.find((c) => c.symbol === symbol);
    if (!coin) {
      return { met: false, detail: { reason: 'coin_not_configured', symbol } };
    }

    const price = prices[symbol];
    if (!price) {
      return { met: false, detail: { reason: 'price_unavailable', symbol } };
    }

    const requestedNotional = size * price;
    const maxAllocationUsd = equity * (coin.pct / 100);

    return {
      met: requestedNotional > maxAllocationUsd,
      detail: {
        symbol,
        requestedNotional: +requestedNotional.toFixed(2),
        maxAllocationUsd: +maxAllocationUsd.toFixed(2),
        allocationPct: coin.pct,
        price,
        size,
      },
    };
  },
};

export function makeAllocationCapRule(overrides?: Partial<Pick<Rule<EngineSnapshot>, 'id' | 'cooldownMs' | 'allowedSources' | 'enabled'>>): Rule<EngineSnapshot> {
  return {
    id: overrides?.id ?? 'risk.allocation-cap',
    tier: RuleTier.RISK,
    conditions: [allocationCapCondition],
    action: {
      type: ActionType.BLOCK_REQUEST,
      idempotencyKeyTemplate: 'risk.allocation-cap:${timestamp}',
      params: { reason: 'allocation_limit_exceeded' },
    },
    cooldownMs: overrides?.cooldownMs,
    allowedSources: overrides?.allowedSources ?? ['REQUEST'],
    enabled: overrides?.enabled ?? true,
  };
}
