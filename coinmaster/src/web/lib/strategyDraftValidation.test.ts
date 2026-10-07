import assert from 'node:assert/strict';
import test from 'node:test';
import { parseFiniteNumberFields } from './strategyDraftValidation';

test('numeric array drafts accept each finite entered value', () => {
  assert.deepEqual(parseFiniteNumberFields(['0.25', ' 1.5 ', '-2']), [0.25, 1.5, -2]);
});

test('numeric array drafts reject blanks and non-finite values without saving partial rows', () => {
  assert.equal(parseFiniteNumberFields(['0.25', '']), null);
  assert.equal(parseFiniteNumberFields(['0.25', 'NaN']), null);
  assert.equal(parseFiniteNumberFields([]), null);
});

import { strategyDraftError } from './strategyDraftValidation';
import type { StrategyConfig } from './nautilusApi';
const validDraft = { ema_period: 34, beta_days: 30, relative_days: 30, z_history_days: 30, wave_history_days: 30, wave_min_count: 3, sol_max_holding_days: 7, btc_notional_multiplier: 1, max_gross_to_active: 2, initial_total_usdt: '10000', max_parent_notional: '100', sol_exit_half_z: 0.5, sol_exit_all_z: 0.1, btc_close_trail_fraction: 0.01, wave_quantiles: [0.1, 0.3, 0.6], sol_entry_z: [1, 2, 3], btc_tp_fractions_initial_qty: [0.2, 0.2, 0.6], sol_size_multipliers_H: [1, 1, 1] } as StrategyConfig;
test('draft checks reject zero or fractional windows, invalid money and unordered thresholds', () => {
  assert.equal(strategyDraftError(validDraft), null);
  for (const patch of [{ ema_period: 0 }, { ema_period: 0.5 }, { ema_period: NaN }, { max_parent_notional: '' }, { wave_quantiles: [0.6, 0.3, 0.1] }]) assert.ok(strategyDraftError({ ...validDraft, ...patch }));
});
