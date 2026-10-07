export function parseFiniteNumberFields(fields: string[]): number[] | null {
  const trimmed = fields.map((field) => field.trim());
  if (trimmed.length === 0 || trimmed.some((field) => field === '')) return null;
  const values = trimmed.map(Number);
  return values.every(Number.isFinite) ? values : null;
}

import type { StrategyConfig } from './nautilusApi';

export function strategyDraftError(config: StrategyConfig): string | null {
  for (const key of ['ema_period', 'beta_days', 'relative_days', 'z_history_days', 'wave_history_days', 'wave_min_count', 'sol_max_holding_days'] as const) {
    if (!Number.isInteger(config[key]) || config[key] <= 0) return key.replaceAll('_', ' ') + ' must be a positive whole number.';
  }
  for (const key of ['btc_notional_multiplier', 'max_gross_to_active', 'initial_total_usdt', 'max_parent_notional'] as const) {
    if (!Number.isFinite(Number(config[key])) || Number(config[key]) <= 0) return key.replaceAll('_', ' ') + ' must be a positive number.';
  }
  for (const key of ['sol_exit_half_z', 'sol_exit_all_z', 'btc_close_trail_fraction'] as const) {
    if (!Number.isFinite(config[key]) || config[key] < 0) return key.replaceAll('_', ' ') + ' must be zero or greater.';
  }
  for (const key of ['wave_quantiles', 'sol_entry_z', 'btc_tp_fractions_initial_qty', 'sol_size_multipliers_H'] as const) {
    const values = config[key];
    if (values.length !== 3 || !values.every(Number.isFinite)) return key.replaceAll('_', ' ') + ' needs three finite numbers.';
    if ((key === 'wave_quantiles' || key === 'sol_entry_z') && values.some((value, index) => index > 0 && value < values[index - 1])) return key.replaceAll('_', ' ') + ' must be in ascending order.';
  }
  return null;
}
