import type { EngineSnapshot } from '../../snapshot.js';
import { ActionType, RuleTier, type Condition, type ConditionResult, type Rule } from '../../types.js';

/** Default maximum tolerable market data age in milliseconds. */
export const DEFAULT_MAX_DATA_AGE_MS = 30_000;

/**
 * Fires when market data age exceeds the maximum tolerable staleness.
 *
 * Required snapshot fields:
 *   - marketDataAge: milliseconds since last successful price update
 *
 * Optional snapshot fields:
 *   - maxMarketDataAgeMs: override for the staleness threshold (defaults to DEFAULT_MAX_DATA_AGE_MS)
 */
export const staleDataCondition: Condition<EngineSnapshot> = {
  id: 'risk.stale-data.age-exceeded',
  evaluate(snapshot: EngineSnapshot): ConditionResult {
    const age = snapshot.marketDataAge;
    const maxAge =
      typeof snapshot['maxMarketDataAgeMs'] === 'number'
        ? snapshot['maxMarketDataAgeMs']
        : DEFAULT_MAX_DATA_AGE_MS;

    if (age === undefined) {
      return { met: false, detail: { reason: 'age_unavailable', maxAge } };
    }

    return {
      met: age > maxAge,
      detail: { ageMs: age, maxAgeMs: maxAge },
    };
  },
};

export function makeStaleDataRule(overrides?: Partial<Pick<Rule<EngineSnapshot>, 'id' | 'cooldownMs' | 'allowedSources' | 'enabled'>>): Rule<EngineSnapshot> {
  return {
    id: overrides?.id ?? 'risk.stale-data',
    tier: RuleTier.RISK,
    conditions: [staleDataCondition],
    action: {
      type: ActionType.BLOCK_REQUEST,
      idempotencyKeyTemplate: 'risk.stale-data:${timestamp}',
      params: { reason: 'stale_market_data' },
    },
    cooldownMs: overrides?.cooldownMs ?? 5_000,
    allowedSources: overrides?.allowedSources ?? ['TICK', 'REQUEST'],
    enabled: overrides?.enabled ?? true,
  };
}
