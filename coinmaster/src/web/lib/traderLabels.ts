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
  if (typeof value === 'boolean' || value === 'true' || value === 'false') return value === true || value === 'true' ? 'Enabled' : 'Disabled';
  if (typeof value === 'string' && value.startsWith('[')) {
    try { const parsed: unknown = JSON.parse(value); if (Array.isArray(parsed)) return strategySettingValue(key, parsed); } catch { return 'Unavailable'; }
  }
  if (Array.isArray(value)) return value.map((item, index) => {
    const number = Number(item);
    const formatted = ['btc_tp_fractions_initial_qty', 'wave_quantiles'].includes(key) && Number.isFinite(number) ? Number((number * 100).toFixed(2)) + '%' : String(item);
    return 'Level ' + (index + 1) + ': ' + formatted;
  }).join(' · ');
  if (key === 'btc_close_trail_fraction' && (typeof value === 'number' || typeof value === 'string')) {
    const fraction = typeof value === 'number' ? value : value.trim() === '' ? Number.NaN : Number(value);
    if (Number.isFinite(fraction)) return `${(fraction * 100).toFixed(2)}%`;
  }
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


const RESEARCH_LABELS: Record<string, string> = {
  NOT_FAITHFUL_DIAGNOSTIC: "Diagnostic evidence · not suitable for live ranking",
  "VALIDATION_SEEN_NOT_OOS + NOT_FAITHFUL_DIAGNOSTIC": "Seen-data validation · not out-of-sample",
  "SEQUENTIAL_SEEN_DATA_VALIDATION_NOT_OOS + NOT_FAITHFUL_DIAGNOSTIC": "Sequential validation · not out-of-sample",
  LIQUIDATED_EARLY_CUTOFF: "Liquidated before the test period ended",
  ARTIFACT_BLOCKED_FOR_COMPARABLE_1M: "Comparable 1-minute data unavailable",
  ARTIFACT_NOT_LOCAL: "Artifact unavailable on this host",
  PUBLIC_FEEDS_READY: "Public market data ready",
  VERIFIED_COMMITTED_SUMMARY: "Verified archived summary",
  READY: "Ready",
  BLOCKED: "Blocked",
};

export function humanizeResearchCode(code: string): string {
  const normalized = code.trim();
  if (RESEARCH_LABELS[normalized]) return RESEARCH_LABELS[normalized];
  if (!normalized) return "Unavailable";
  return normalized.replaceAll("_", " ").replaceAll(":", " · ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}


export function strategyRunnerLabel(code: string | null | undefined): string {
  if (code === "RUNNING_MATCH") return "Match confirmed";
  if (code === "SEALED_SOURCE_CHECKED") return "Source checked · worker match unconfirmed";
  return humanizeResearchCode(code ?? "NOT_CONFIRMED");
}

export function researchResultContext(activeRunId: string | null | undefined, selectedRunId: string | null | undefined): string {
  if (activeRunId) return "Research is in progress; status refreshes automatically.";
  if (selectedRunId) return "Selected run results are shown below.";
  return "Choose a run from history to inspect its results.";
}


const FILL_ACTION_LABELS: Record<string, string> = {
  BTC_ENTRY: 'Entry',
  BTC_REDUCE: 'Exit',
  TP_PARTIAL: 'Partial TP',
  TAKE_PROFIT: 'TP',
  SOL_ADD: 'Add',
  SOL_HALF_EXIT: 'Partial exit',
  SOL_EXIT: 'Exit',
  MARKET_EXIT: 'Exit',
  FORCED_CLOSE: 'Exit',
  TERMINAL_CLOSE: 'Exit',
  LIQUIDATION_CLOSE: 'Liquidation',
  CLOSE_ALL: 'Exit',
};

export function nativeFillActionLabel(action: string | null | undefined): string {
  return action ? FILL_ACTION_LABELS[action] ?? 'Fill type unavailable' : 'Fill type unavailable';
}


export function unavailableTradeHistoryLabel(count: number | null | undefined): string {
  if (typeof count !== 'number' || !Number.isSafeInteger(count) || count < 0) return 'Detailed trade history is unavailable.';
  return `Detailed trade history is unavailable. ${count} older executions have no saved details.`;
}
