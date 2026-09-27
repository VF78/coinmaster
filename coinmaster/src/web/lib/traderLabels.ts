const SETTING_LABELS: Record<string, string> = {
  sol_size_multipliers_h: 'SOL add-size multipliers',
  sol_size_multipliers_H: 'SOL add-size multipliers',
  sol_timeout_preempts_add: 'SOL timeout stops further additions',
  sol_late_entry_after_tp: 'Allow SOL re-entry after take-profit',
  sol_overlay_enabled: 'SOL overlay',
  episode_fixed_beta: 'Keep beta fixed during each episode',
  max_parent_notional: 'Maximum parent order notional',
  freeze_sigma_on_first_sol_fill: 'Freeze SOL signal level after first fill',
  include_zero_waves: 'Include zero-amplitude waves',
};

const ADVANCED_SETTINGS = new Set([
  'max_parent_notional',
  'sol_timeout_preempts_add',
  'sol_late_entry_after_tp',
  'sol_overlay_enabled',
  'episode_fixed_beta',
  'freeze_sigma_on_first_sol_fill',
  'include_zero_waves',
]);

const BLOCKER_LABELS: Record<string, string> = {
  MISSING_1M_MANIFEST: 'Verified 1-minute market data is not available.',
  CONFIG_NOT_SEALED_STAGE_G: 'The selected configuration does not match the sealed Stage-G strategy.',
  NO_IDEMPOTENT_NATIVE_FLATTEN_RECOVERY: 'Flattening is unavailable until native crash-safe recovery is supported.',
};

export function strategySettingLabel(key: string): string {
  return SETTING_LABELS[key] ?? key.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function strategySettingValue(key: string, value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Enabled' : 'Disabled';
  if (Array.isArray(value)) return value.join(' · ');
  if (key === 'btc_close_trail_fraction' && typeof value === 'number') return `${(value * 100).toFixed(2)}%`;
  if (key === 'max_parent_notional') {
    const numeric = typeof value === 'number' ? value : Number(value);
    if (Number.isFinite(numeric)) return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(numeric);
  }
  return String(value);
}

export function isAdvancedStrategySetting(key: string): boolean {
  return ADVANCED_SETTINGS.has(key);
}

export function humanizeBlocker(code: string): string {
  const normalized = code.trim();
  if (BLOCKER_LABELS[normalized]) return BLOCKER_LABELS[normalized];
  if (!normalized) return 'Status unavailable.';
  const words = normalized.replaceAll('_', ' ').replaceAll(':', ' · ').toLowerCase();
  return `${words.charAt(0).toUpperCase()}${words.slice(1)}`;
}

export function controlAvailabilityLabel(enabled: boolean | null | undefined, recoveryRequired: boolean | null | undefined): string {
  if (recoveryRequired === true) return 'Unavailable · recovery required';
  return enabled ? 'Pause / resume available' : 'Read-only';
}
