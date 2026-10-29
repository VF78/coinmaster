import { useEffect, useState } from 'react';
import { ExecutionModeSettings } from '../components/ExecutionModeSettings';
import { StrategyEntryControls } from '../components/StrategyEntryControls';
import { DashboardMarketChart } from '../components/DashboardMarketChart';
import { DashboardConnectionIdentity } from '../components/DashboardConnectionIdentity';
import { SettingsConnections } from '../components/SettingsConnections';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';
import { selectedMode, selectedModeLabel, cancelRun, commandHlStagegDepositProtection, commandHlStagegEntries, createRun, getConfigurations, getDefaultConfiguration, getHlStagegControls, getHlStagegEquityChanges, getHlStagegFills, getHlStagegProjection, getHlStagegStrategy, getResearchCapabilities, getResearchCatalog, getRuns, saveConfiguration, type HlNativeEquityChanges, type HlStagegControls, type HlStagegFillHistory, type HlStagegProjection, type HlStagegStrategy, type ResearchCapabilities, type ResearchCatalogEntry, type Run, type StrategyConfig, type StrategyConfiguration } from '../lib/nautilusApi';
import { accountFigures, dashboardState, fundingLabel, formatUtcTimestamp, protectionIsFresh, protectionIsVerified } from '../lib/accountPresentation';
import { positionPresentation, TRADER_MARKETS } from '../lib/traderPresentation';
import { parseFiniteNumberFields, strategyDraftError } from '../lib/strategyDraftValidation';
import { controlAvailabilityLabel, humanizeBlocker, humanizeResearchCode, isAdvancedStrategySetting, nativeFillActionLabel, unavailableTradeHistoryLabel, strategyRunnerLabel, strategySettingLabel, strategySettingValue } from '../lib/traderLabels';

import { verifiedControlReadback } from '../lib/controlReadback';
import { effectiveLeverage, researchMetric, traderMoney, projectionCurrency, nativeMoney, traderNumber, traderPercent } from '../lib/traderFormatting';

type NumberKey = 'ema_period' | 'beta_days' | 'relative_days' | 'z_history_days' | 'wave_history_days' | 'wave_min_count' | 'btc_notional_multiplier' | 'max_gross_to_active' | 'sol_exit_half_z' | 'sol_exit_all_z' | 'sol_max_holding_days' | 'btc_close_trail_fraction';
type ArrayKey = 'wave_quantiles' | 'btc_tp_fractions_initial_qty' | 'sol_size_multipliers_H' | 'sol_entry_z';

function tone(status: string): 'success' | 'danger' | 'neutral' { return status === 'COMPLETED' ? 'success' : status === 'BLOCKED' || status === 'CANCELED' ? 'danger' : 'neutral'; }
const PARAMETER_LABELS: Record<string, string> = {
  ema_period: 'EMA window (bars)', beta_days: 'Beta lookback (days)', relative_days: 'Relative-value lookback (days)',
  z_history_days: 'Z-score history (days)', wave_history_days: 'Wave history (days)', wave_min_count: 'Minimum wave count',
  wave_quantiles: 'Wave percentile thresholds', btc_notional_multiplier: 'BTC size multiplier (×)',
  btc_close_trail_fraction: 'BTC trailing close threshold (%)', btc_tp_fractions_initial_qty: 'BTC take-profit fractions',
  sol_size_multipliers_H: 'SOL add-size multipliers', sol_entry_z: 'SOL entry z-score thresholds (σ)',
  sol_exit_half_z: 'SOL half-exit z-score (σ)', sol_exit_all_z: 'SOL full-exit z-score (σ)',
  sol_max_holding_days: 'SOL maximum holding (days)', max_gross_to_active: 'Maximum gross / active capital (×)',
};
function title(key: string) { return PARAMETER_LABELS[key] ?? strategySettingLabel(key); }
function displaySetting(key: string, value: unknown) { return strategySettingValue(key, value); }

function NumberArrayField({ label, value, onCommit, onValidity }: { label: string; value: number[]; onCommit: (next: number[]) => void; onValidity: (valid: boolean) => void }) {
  const serialized = value.map(String);
  const [draft, setDraft] = useState(serialized);
  const [invalid, setInvalid] = useState(false);
  useEffect(() => { setDraft(serialized); setInvalid(false); }, [value.join(',')]);
  function change(index: number, next: string) {
    const updated = draft.map((field, fieldIndex) => fieldIndex === index ? next : field);
    setDraft(updated); const parsed = parseFiniteNumberFields(updated);
    setInvalid(!parsed); onValidity(Boolean(parsed)); if (parsed) onCommit(parsed);
  }
  function commit() {
    const parsed = parseFiniteNumberFields(draft);
    if (!parsed || parsed.length !== value.length) { setInvalid(true); return; }
    setInvalid(false); onCommit(parsed);
  }
  return <fieldset className="rules-field rules-array-field" aria-invalid={invalid || undefined}>
    <legend>{label}</legend><div className="rules-array-fields">{draft.map((field, index) => <label key={index}>
      <span className="sr-only">{label}, value {index + 1}</span><input aria-label={`${label}, value ${index + 1}`} aria-invalid={invalid || undefined} type="number" step="any" value={field} onChange={(event) => change(index, event.target.value)} onBlur={commit} />
    </label>)}</div>{invalid ? <span className="field-error" role="alert">Enter a number in every field.</span> : null}
  </fieldset>;
}

export function StrategyPage() {
  const [invalidArrays, setInvalidArrays] = useState<Record<string, boolean>>({});
  const [strategy, setStrategy] = useState<HlStagegStrategy | null>(null); const [config, setConfig] = useState<StrategyConfig | null>(null); const [drafts, setDrafts] = useState<StrategyConfiguration[]>([]); const [saved, setSaved] = useState<StrategyConfiguration | null>(null); const [message, setMessage] = useState(''); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false);
  async function load() { setLoading(true); setMessage(''); const [sealed, stored, template] = await Promise.allSettled([getHlStagegStrategy(), getConfigurations(), getDefaultConfiguration()]); if (sealed.status === 'fulfilled') setStrategy(sealed.value); if (stored.status === 'fulfilled') { setDrafts(stored.value); const selected = stored.value.find((item) => item.id === window.localStorage.getItem('coinmaster-selected-config')) ?? stored.value[0]; if (selected) { setSaved(selected); setConfig(selected.config); } } if (template.status === 'fulfilled') setConfig((current) => current ?? template.value.config); const failure = [sealed, stored, template].find((result) => result.status === 'rejected'); if (failure?.status === 'rejected') setMessage(failure.reason instanceof Error ? failure.reason.message : 'Unable to load the Strategy page.'); setLoading(false); }
  useEffect(() => { void load(); }, []);
  function updateNumber(key: NumberKey, value: string) { setConfig((item) => item ? { ...item, [key]: key === 'btc_close_trail_fraction' ? (value === '' ? NaN : Number(value) / 100) : (value === '' ? NaN : Number(value)) } : item); }
  function updateArray(key: ArrayKey, value: number[]) { setConfig((item) => item ? { ...item, [key]: value } : item); }
  async function save() { if (!config || saving || draftError) return; if (!Number.isFinite(Number(config.initial_total_usdt)) || Number(config.initial_total_usdt) <= 0) { setMessage('Research draft validation failed: initial total must be a positive number.'); return; } setSaving(true); setMessage('Saving research draft…'); try { const next = await saveConfiguration(config); const refreshed = await getConfigurations(); const persisted = refreshed.find((item) => item.id === next.id); if (!persisted) throw new Error('Saved draft could not be read back.'); setDrafts(refreshed); setSaved(persisted); setConfig(persisted.config); window.localStorage.setItem('coinmaster-selected-config', persisted.id); setMessage(`Research draft saved and read back: ${formatUtcTimestamp(persisted.created_at)}.`); } catch (error) { setMessage(error instanceof Error ? error.message : 'Research draft save failed.'); } finally { setSaving(false); } }
  const draftError = Object.values(invalidArrays).some(Boolean) ? 'Enter a finite number in every array field.' : config ? strategyDraftError(config) : null;
  const draftDirty = Boolean(Object.values(invalidArrays).some(Boolean) || config && (!saved || JSON.stringify(config) !== JSON.stringify(saved.config)));
  const runningMatch = strategy?.running_state === 'RUNNING_MATCH';
  const sourceChecked = strategy?.source_state === 'SEALED_CONFIGURATION_CHECKED';
  const runningParameters = Object.entries(strategy?.candidate ?? {}).map(([parameter, value]) => ({ id: parameter, parameter, value }));
  const visibleRunningParameters = runningParameters.filter((row) => !isAdvancedStrategySetting(row.parameter));
  const advancedRunningParameters = runningParameters.filter((row) => isAdvancedStrategySetting(row.parameter));
  const strategyGroups = [
    ['BTC sizing and exits', visibleRunningParameters.filter((row) => row.parameter.startsWith('btc_'))],
    ['SOL sizing and exits', visibleRunningParameters.filter((row) => row.parameter.startsWith('sol_'))],
    ['Signal and safety settings', visibleRunningParameters.filter((row) => !row.parameter.startsWith('btc_') && !row.parameter.startsWith('sol_'))],
  ] as const;
  return <main className="terminal-layout nautilus-strategy-workspace">
    <Card className="trader-hero strategy-hero" title={loading ? 'Loading strategy…' : runningMatch ? 'Running strategy' : sourceChecked ? 'Approved strategy' : 'Strategy unavailable'} actions={<Badge tone={loading ? 'neutral' : runningMatch ? 'success' : 'danger'}>{strategyRunnerLabel(strategy?.running_state ?? (loading ? 'LOADING' : 'NOT_CONFIRMED'))}</Badge>}>
      <p className="trader-hero__lead">{loading ? 'Loading approved strategy settings…' : runningMatch ? 'The worker is running the sealed BTC / SOL strategy shown below.' : sourceChecked ? 'The approved settings were read successfully, but the worker match is not confirmed.' : 'The strategy source could not be confirmed. No running settings are implied.'}</p>
      <div className="stats-grid"><Stat label="Strategy" value={strategy?.candidate && Object.keys(strategy.candidate).length ? (selectedMode === 'live' ? 'BTC / SOL Wave Overlay · V3+DP50' : 'BTC / SOL Wave Overlay · V0') : loading ? 'Loading…' : 'Unavailable'} /><Stat label="Execution" value={selectedMode === 'live' ? 'Live · Mainnet' : 'Local Sandbox'} /><Stat label="Market data" value="Hyperliquid public" /></div>
      <p className="trader-note">Strategy changes require a reviewed version and approved rollout. Save a draft below to compare it in Backtest.</p>
    </Card>
    <p className="trader-note">{strategy?.capital_assumption}</p><StrategyEntryControls />
    <section className="strategy-settings-grid">{strategyGroups.map(([group, rows]) => <Card className="strategy-settings-card" key={group} title={group} actions={<Badge tone={runningMatch ? 'success' : 'neutral'}>{loading ? 'Loading' : runningMatch ? 'Confirmed' : 'Unconfirmed'}</Badge>}>
      {rows.length ? <dl className="strategy-setting-list">{rows.map((row) => <div className="strategy-setting-row" key={row.parameter}><dt>{title(row.parameter)}</dt><dd>{displaySetting(row.parameter, row.value)}</dd></div>)}</dl> : <p className="runtime-empty-note">{loading ? 'Loading approved settings…' : 'No approved settings are available.'}</p>}
    </Card>)}</section>
    {advancedRunningParameters.length ? <details className="nautilus-diagnostics"><summary>Advanced strategy rules</summary><dl className="strategy-setting-list">{advancedRunningParameters.map((row) => <div className="strategy-setting-row" key={row.parameter}><dt>{title(row.parameter)}</dt><dd>{displaySetting(row.parameter, row.value)}</dd></div>)}</dl></details> : null}
    <details className="nautilus-diagnostics strategy-research-drafts"><summary>Research drafts · saved separately from the running strategy</summary><div className="research-drafts-card">
      <p className="trader-hero__lead">Draft parameters are saved for research only. The running strategy above remains unchanged.</p>
      <label className="rules-field"><span>Read-back saved draft</span><select value={saved?.id ?? ''} onChange={(event) => { const next = drafts.find((item) => item.id === event.target.value) ?? null; setSaved(next); setConfig(next?.config ?? config); if (next) window.localStorage.setItem('coinmaster-selected-config', next.id); }}>{drafts.map((item) => <option key={item.id} value={item.id}>Saved draft · {formatUtcTimestamp(item.created_at)}</option>)}</select></label>
      <div className="nautilus-strategy-grid">
        <section className="nautilus-strategy-group"><h3>BTC sizing and exits</h3><p className="muted">Research draft; sealed running parameters stay above.</p><div className="rules-form-grid">
        {(['ema_period', 'btc_notional_multiplier', 'btc_close_trail_fraction'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" step="any" value={config?.[key] == null || !Number.isFinite(config[key]) ? '' : String(String(key) === 'btc_close_trail_fraction' ? Number(config[key]) * 100 : config[key])} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <NumberArrayField label="BTC take-profit size fractions (0–1)" value={config.btc_tp_fractions_initial_qty} onCommit={(next) => updateArray('btc_tp_fractions_initial_qty', next)} onValidity={(valid) => setInvalidArrays((current) => ({ ...current, btc_tp_fractions_initial_qty: !valid }))} /> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>SOL sizing and exits</h3><p className="muted">Entry thresholds, add sizes and staged exits.</p><div className="rules-form-grid">
        {(['sol_exit_half_z', 'sol_exit_all_z', 'sol_max_holding_days'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" step="any" value={config?.[key] == null || !Number.isFinite(config[key]) ? '' : String(String(key) === 'btc_close_trail_fraction' ? Number(config[key]) * 100 : config[key])} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <><NumberArrayField label="SOL add-size multipliers (×)" value={config.sol_size_multipliers_H} onCommit={(next) => updateArray('sol_size_multipliers_H', next)} onValidity={(valid) => setInvalidArrays((current) => ({ ...current, sol_size_multipliers_H: !valid }))} /><NumberArrayField label="SOL entry thresholds (σ)" value={config.sol_entry_z} onCommit={(next) => updateArray('sol_entry_z', next)} onValidity={(valid) => setInvalidArrays((current) => ({ ...current, sol_entry_z: !valid }))} /></> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>Signal windows</h3><p className="muted">Feature history and wave thresholds.</p><div className="rules-form-grid">
        {(['beta_days', 'relative_days', 'z_history_days', 'wave_history_days', 'wave_min_count'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" step="any" value={config?.[key] == null || !Number.isFinite(config[key]) ? '' : String(String(key) === 'btc_close_trail_fraction' ? Number(config[key]) * 100 : config[key])} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <><NumberArrayField label="Wave thresholds (0–1)" value={config.wave_quantiles} onCommit={(next) => updateArray('wave_quantiles', next)} onValidity={(valid) => setInvalidArrays((current) => ({ ...current, wave_quantiles: !valid }))} /></> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>Capital and constraints</h3><p className="muted">Fixed v0 controls are visible but cannot be edited.</p><div className="rules-form-grid">
        <label className="rules-field"><span>Initial TOTAL (template constraint)</span><input disabled value={config?.initial_total_usdt ?? ''} /></label>
        <label className="rules-field"><span>Initial active fraction (template constraint)</span><input disabled type="number" value={String(config?.initial_active_fraction ?? '')} /></label>
        <label className="rules-field"><span>Research venue</span><select value={config?.venue ?? ''} onChange={(event) => setConfig((item) => item ? { ...item, venue: (event.target.value || null) as StrategyConfig['venue'] } : item)}><option value="">Unselected</option><option value="bybit">Bybit</option><option value="hyperliquid">Hyperliquid</option></select></label>
        {(['max_gross_to_active'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" step="any" value={config?.[key] == null || !Number.isFinite(config[key]) ? '' : String(String(key) === 'btc_close_trail_fraction' ? Number(config[key]) * 100 : config[key])} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        <label className="rules-field"><span>Maximum parent order notional</span><input type="number" step="any" value={config?.max_parent_notional ?? ''} onChange={(event) => setConfig((item) => item ? { ...item, max_parent_notional: event.target.value } : item)} /></label>
        <label className="rules-field"><span>Include zero waves (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.include_zero_waves)} /></label>
        <label className="rules-field"><span>Freeze sigma on first SOL fill (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.freeze_sigma_on_first_sol_fill)} /></label>
        <label className="rules-field"><span>Insufficient margin (v0 fixed)</span><select disabled value={config?.insufficient_margin ?? 'reject'}><option value="reject">reject</option></select></label>
        </div></section>
      </div>
      <p className="muted">Template constraints remain fixed until a separately scoped native implementation. Server validation is authoritative for research-draft saves.</p>
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!config || saving || Boolean(draftError)} onClick={() => void save()}>{saving ? 'Saving…' : 'Save research draft'}</Button>{saved ? <Badge tone={draftDirty ? 'neutral' : 'success'}>{draftDirty ? 'Unsaved changes' : 'Saved draft read back'}</Badge> : null}</div>{draftError ? <p className="field-error" role="alert">{draftError}</p> : null}{message && !draftDirty ? <p className="muted">{message}</p> : null}
    </div></details>
  </main>;
}

export function ResearchPage() {
  const [config, setConfig] = useState<StrategyConfiguration | null>(null);
  const [configs, setConfigs] = useState<StrategyConfiguration[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [catalog, setCatalog] = useState<ResearchCatalogEntry[]>([]);
  const [capabilities, setCapabilities] = useState<ResearchCapabilities | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [period, setPeriod] = useState<'bounded' | 'full'>('bounded');
  const [startDate, setStartDate] = useState('2026-08-25');
  const [endDate, setEndDate] = useState('2026-09-01');
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  async function load() {
    const [runResult, catalogResult, configResult] = await Promise.allSettled([
      getRuns(), getResearchCatalog(), getConfigurations(),
    ]);
    if (runResult.status === 'fulfilled') {
      setRuns(runResult.value);
      setSelectedRunId((selected) => selected && runResult.value.some((item) => item.id === selected) ? selected : runResult.value[0]?.id ?? null);
    }
    if (catalogResult.status === 'fulfilled') setCatalog(catalogResult.value);
    if (configResult.status === 'fulfilled') {
      setConfigs(configResult.value);
      setConfig(configResult.value.find((item) => item.id === window.localStorage.getItem('coinmaster-selected-config')) ?? configResult.value[0] ?? null);
    }
    const selectedConfig = configResult.status === 'fulfilled' ? configResult.value.find((item) => item.id === window.localStorage.getItem('coinmaster-selected-config')) ?? configResult.value[0] : config;
    const capabilityResult = await Promise.allSettled([getResearchCapabilities(selectedConfig?.id)]).then(([result]) => result);
    if (capabilityResult.status === 'fulfilled') setCapabilities(capabilityResult.value);
    const failed = [runResult, catalogResult, configResult, capabilityResult].find((result) => result.status === 'rejected');
    if (failed?.status === 'rejected') setMessage(failed.reason instanceof Error ? failed.reason.message : 'Unable to load native research status.');
    setLoading(false);
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!runs.some((item) => ['STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'QUEUED'].includes(item.status))) return;
    const timer = window.setInterval(() => { void load(); }, 3000);
    return () => window.clearInterval(timer);
  }, [runs]);

  async function ensureConfig() {
    if (config) return config;
    const template = await getDefaultConfiguration();
    const saved = await saveConfiguration(template.config);
    setConfigs((items) => [saved, ...items]);
    setConfig(saved);
    return saved;
  }

  async function startBaseline() {
    if (starting || !baselineReady || !intervalValid) return;
    setStarting(true); setMessage('Creating verified native baseline job…');
    try {
      const saved = await ensureConfig();
      const run = await createRun(saved.id, 'research', 'native_baseline', undefined, period === 'bounded' ? { start: startDate, end_exclusive: endDate } : undefined);
      const readBack = await getRuns();
      const persisted = readBack.find((item) => item.id === run.id);
      if (!persisted) throw new Error('Native job was accepted but could not be read back.');
      setRuns(readBack); setSelectedRunId(persisted.id);
      setMessage(persisted.status === 'BLOCKED' ? persisted.evidence.map(humanizeBlocker).join(' ') : 'Native baseline job accepted and read back.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to start native baseline job.');
    } finally { setStarting(false); void load(); }
  }

  async function startOptimizer() {
    if (starting || capabilities?.optimizer_state !== 'READY' || !config || activeRun) return;
    setStarting(true); setMessage('Starting bounded native optimizer…');
    try {
      const run = await createRun(config.id, 'research', 'native_optimizer', capabilities.optimizer_search);
      const readBack = await getRuns();
      const persisted = readBack.find((item) => item.id === run.id);
      if (!persisted) throw new Error('Optimizer job was accepted but could not be read back.');
      setRuns(readBack); setSelectedRunId(persisted.id);
      setMessage(persisted.status === 'BLOCKED' ? persisted.evidence.join(' · ') : 'Native optimizer job accepted and read back.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Unable to start optimizer.'); }
    finally { setStarting(false); void load(); }
  }

  async function cancelOwned(id: string) {
    if (cancellingId) return;
    setCancellingId(id); setMessage('Requesting native job cancellation…');
    try {
      await cancelRun(id);
      const readBack = await getRuns();
      const persisted = readBack.find((item) => item.id === id);
      if (!persisted || !['CANCEL_REQUESTED', 'CANCELED', 'COMPLETED', 'FAILED', 'BLOCKED'].includes(persisted.status)) throw new Error('Cancellation was not confirmed by read-back.');
      setRuns(readBack); setMessage(`Job read back as ${persisted.status}.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Unable to verify cancellation.'); }
    finally { setCancellingId(null); }
  }

  const selectedRun = runs.find((item) => item.id === selectedRunId) ?? null;
  const runTitle = (run: Run) => run.command_name === 'native_optimizer' ? 'Parameter search' : run.command_name === 'native_baseline' ? 'Historical baseline' : humanizeResearchCode(run.kind);
  const activeRun = runs.find((item) => ['STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'QUEUED'].includes(item.status));
  const terminalTotal = selectedRun?.report?.summary && typeof selectedRun.report.summary === 'object'
    ? (selectedRun.report.summary as { terminal_total?: string }).terminal_total
    : selectedRun?.report?.terminal_total;
  const baselineReady = capabilities?.baseline_state === 'READY';
  const days = (Date.parse(endDate + 'T00:00:00Z') - Date.parse(startDate + 'T00:00:00Z')) / 86_400_000;
  const intervalValid = period === 'full' || Number.isInteger(days) && days >= 1 && days <= 7 && startDate >= '2024-09-01' && endDate <= '2026-09-01';
  const metrics = selectedRun?.report;
  const venue = config?.config.venue === 'hyperliquid' ? 'Hyperliquid' : config?.config.venue === 'bybit' ? 'Bybit' : 'Unselected';
  const optimizerReady = capabilities?.optimizer_state === 'READY';
  const optimizerSearch = capabilities?.optimizer_search as { axis: string; values: string[]; max_variants: number } | undefined;
  const top20 = Array.isArray(selectedRun?.report?.top20) ? selectedRun.report.top20 as { candidate_id: string; candidate_sha256: string; terminal_active: string; terminal_reserve: string; terminal_total: string; roi: string; drawdown_percent: string; liquidations: number; maker_fees: string; taker_fees: string; funding: { count?: number; signed_amount?: string }; fills: number; limitations: string[]; artifact_sha256: string; classification: string }[] : [];
  return <main className="terminal-layout nautilus-research-workspace">
    <Card className="trader-hero research-hero" title="Research workspace" actions={<Badge tone={baselineReady ? 'success' : 'danger'}>{humanizeResearchCode(capabilities?.baseline_state ?? (loading ? 'LOADING' : 'BLOCKED'))}</Badge>}>
      <p className="trader-hero__lead">Run a bounded backtest using the selected saved configuration. It never changes the running strategy.</p>
      <div className="rules-form-grid">
        <label className="rules-field"><span>Strategy version / saved draft</span><select value={config?.id ?? ''} onChange={(event) => { const next = configs.find((item) => item.id === event.target.value) ?? null; setConfig(next); setCapabilities(null); if (next) { window.localStorage.setItem('coinmaster-selected-config', next.id); void getResearchCapabilities(next.id).then(setCapabilities).catch((error: Error) => setMessage(error.message)); } }}>{configs.map((item) => <option key={item.id} value={item.id}>Saved draft · {formatUtcTimestamp(item.created_at)}</option>)}</select></label>
        <label className="rules-field"><span>Test period</span><select value={period} onChange={(event) => setPeriod(event.target.value as 'bounded' | 'full')}><option value="bounded">Custom range · up to 7 days</option><option value="full">Full verified history · 24 months</option></select></label>
        <label className="rules-field"><span>Start date (UTC)</span><input aria-label="Backtest start date" type="date" min="2024-09-01" max="2026-08-31" disabled={period === 'full'} value={period === 'full' ? '2024-09-01' : startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        <label className="rules-field"><span>End date · exclusive (UTC)</span><input aria-label="Backtest end date" type="date" min="2024-09-02" max="2026-09-01" disabled={period === 'full'} value={period === 'full' ? '2026-09-01' : endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
        <label className="rules-field"><span>Venue / verified dataset</span><input readOnly value={venue + ' · 1-minute historical data'} /></label>
        <label className="rules-field"><span>Starting capital · native fixed seed</span><input readOnly value="10,000 USDT" /></label>
        <label className="rules-field"><span>Ranking objective</span><input disabled value={capabilities?.baseline_objective ?? 'TOTAL only'} /></label>
      </div>
      <p className="muted">The native runner checks the saved strategy and verified dataset. Custom periods accept 1–7 days within the available history; capital is fixed by this native runner.</p>{!intervalValid ? <p className="field-error" role="alert">Choose a range of 1–7 days between 1 September 2024 and 1 September 2026.</p> : null}
      {capabilities?.baseline_blockers.length ? <><p className="muted">Baseline blocked: {capabilities.baseline_blockers.map(humanizeBlocker).join(' ')}</p></> : null}
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!baselineReady || !intervalValid || starting || Boolean(activeRun)} onClick={() => void startBaseline()}>{starting ? 'Starting…' : activeRun ? 'Research running…' : period === 'bounded' ? 'Run backtest' : 'Run full history'}</Button><Button variant="secondary" onClick={() => void load()}>Refresh status</Button></div>
    </Card>
    <Card className="research-action-card" title="Compare strategy variants" actions={<Badge tone={optimizerReady ? 'success' : 'danger'}>{optimizerReady ? 'Ready' : humanizeResearchCode(capabilities?.optimizer_state ?? 'BLOCKED')}</Badge>}>
      <p className="muted">One axis: {optimizerSearch ? strategySettingLabel(optimizerSearch.axis) : 'BTC size'} = {optimizerSearch?.values.join(', ') ?? '—'} · up to {optimizerSearch?.max_variants ?? '—'} variants · rank by terminal total. Backtest evidence only.</p>
      {capabilities?.optimizer_blockers.length ? <><p className="muted">Research is blocked: {capabilities.optimizer_blockers.map(humanizeBlocker).join(' ')}</p></> : null}
      <Button variant="primary" disabled={!optimizerReady || !config || starting || Boolean(activeRun)} onClick={() => void startOptimizer()}>{starting ? 'Starting…' : activeRun ? 'Research busy…' : 'Optimize terminal total'}</Button>
    </Card>
    <Card className="research-result-card" title="Selected result" actions={selectedRun ? <Badge tone={tone(selectedRun.status)}>{humanizeResearchCode(selectedRun.status)}{selectedRun.progress == null ? '' : ' · ' + selectedRun.progress + '%'}</Badge> : <Badge tone="neutral">No run selected</Badge>}>
      <p className="muted">{activeRun ? "Backtest is running; progress refreshes automatically." : selectedRun ? "Showing the selected run." : "No run selected."}</p>
      <div className="stats-grid"><Stat label="Terminal TOTAL" value={traderMoney(terminalTotal, 'USDT')} /><Stat label="ROI" value={traderPercent(researchMetric(metrics, 'roi'))} /><Stat label="Max drawdown" value={traderPercent(researchMetric(metrics, 'max_drawdown_percent'))} /><Stat label="Active capital" value={traderMoney(researchMetric(metrics, 'terminal_active'), 'USDT')} /><Stat label="Reserve" value={traderMoney(researchMetric(metrics, 'terminal_reserve'), 'USDT')} /><Stat label="Executed fills" value={traderNumber(researchMetric(metrics, 'fills'), 0)} /></div>
      <p className="trader-note">Trading fees: {traderMoney(researchMetric(metrics, 'native_fees'), 'USDT')} · Funding: {traderMoney((researchMetric(metrics, 'funding') as { signed_amount?: unknown } | undefined)?.signed_amount, 'USDT')} · Liquidations: {traderNumber(researchMetric(metrics, 'liquidation_count'), 0)}.</p>
      {selectedRun?.status === 'COMPLETED' && Number(researchMetric(metrics, 'fills')) === 0 ? <p className="trader-note">No trades executed in this run.</p> : null}
      <p className="trader-note">Historical simulation. Venue fees, intraminute execution and funding settlement are not fully validated; these results do not predict the running trader.</p>
      {selectedRun?.evidence.length ? <p className="muted">{selectedRun.evidence.map(humanizeBlocker).join(' ')}</p> : null}
      {top20.length ? <><h3 className="nautilus-subheading">TOP {top20.length} · terminal TOTAL comparison</h3><DataTable rows={top20.map((row) => ({ ...row, classification: humanizeResearchCode(row.classification), id: row.candidate_id }))} emptyText="No ranked candidates." mobileTitle={(row) => row.candidate_id} columns={[{ key: 'candidate', header: 'Candidate', render: (row) => row.candidate_id }, { key: 'total', header: 'TOTAL / ACTIVE / RESERVE', render: (row) => `${row.terminal_total} / ${row.terminal_active} / ${row.terminal_reserve}` }, { key: 'risk', header: 'ROI / DD / liq', render: (row) => `${row.roi} / ${row.drawdown_percent} / ${row.liquidations}` }, { key: 'costs', header: 'Fills / maker / taker / funding', render: (row) => `${row.fills} / ${row.maker_fees} / ${row.taker_fees} / ${row.funding?.signed_amount ?? '—'}` }, { key: 'proof', header: 'Classification / limits', render: (row) => `${row.classification} · ${row.limitations.join('; ')}` }]} /></> : <p className="muted">This run has no parameter comparison.</p>}
      {selectedRun && ['STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'QUEUED'].includes(selectedRun.status) ? <Button variant="danger" disabled={Boolean(cancellingId)} onClick={() => void cancelOwned(selectedRun.id)}>{cancellingId === selectedRun.id ? 'Cancelling…' : 'Cancel owned job'}</Button> : null}
    </Card>
    <Card title="Run history" actions={<Badge tone="neutral">Terminal total</Badge>}><DataTable rows={runs.map((run) => ({ ...run, id: run.id }))} emptyText="No research runs yet." mobileTitle={(run) => runTitle(run)} columns={[{ key: 'run', header: 'Run', render: (run) => <Button variant="secondary" onClick={() => setSelectedRunId(run.id)}>{runTitle(run)} · {formatUtcTimestamp(run.created_at)}</Button> }, { key: 'status', header: 'Status / progress', render: (run) => <Badge tone={tone(run.status)}>{humanizeResearchCode(run.status)}{run.progress === null || run.progress === undefined ? '' : ` · ${run.progress}%`}</Badge> }, { key: 'total', header: 'Terminal TOTAL', render: (run) => traderMoney(researchMetric(run.report, 'terminal_total'), 'USDT') }]} /></Card>
    <Card title="Latest V0 / V1 comparison" actions={<Badge tone="neutral">Archived native results</Badge>}>
      <p className="trader-note">Same data, V0 versus the fee-floor experiment. V0 has the higher terminal TOTAL. G4 used earlier code and is shown as historical context. All three are diagnostic Bybit simulations.</p>
      <DataTable rows={catalog.filter((item) => item.kind === 'current-comparison')} emptyText="Current comparison summary unavailable." mobileTitle={(item) => item.title} columns={[{ key: 'version', header: 'Version', render: (item) => item.title }, { key: 'total', header: 'Terminal TOTAL', render: (item) => traderMoney(item.settled_total, 'USDT') }, { key: 'roi', header: 'ROI', render: (item) => traderPercent(item.roi) }, { key: 'dd', header: 'Drawdown', render: (item) => traderPercent(item.drawdown_percent) }, { key: 'fills', header: 'Fills', render: (item) => traderNumber(item.fills, 0) }, { key: 'fees', header: 'Trading fees', render: (item) => traderMoney(item.fees, 'USDT') }]} />
      <p className="trader-note">Funding cash amount is unavailable in these artifacts. Historical execution and funding limits prevent a live performance claim.</p>
    </Card>
    <details className="nautilus-diagnostics"><summary>Earlier research evidence</summary><Card title="Historical research archive" actions={<Badge tone="neutral">Evidence</Badge>}><DataTable rows={catalog.filter((item) => item.kind !== 'current-comparison').map((item) => ({ ...item, id: item.id }))} emptyText="No catalog evidence." mobileTitle={(item) => item.title} columns={[{ key: 'evidence', header: 'Evidence', render: (item) => item.title }, { key: 'class', header: 'Class', render: (item) => <Badge tone={item.liquidations ? 'danger' : 'neutral'}>{humanizeResearchCode(item.classification)}</Badge> }, { key: 'total', header: 'TOTAL', render: (item) => traderNumber(item.settled_total) }, { key: 'artifact', header: 'Artifact', render: (item) => humanizeResearchCode(item.artifact_state) }]} /></Card></details>
    {message ? <p className="muted">{message}</p> : null}
  </main>;
}

export function RuntimePage() {
  const [state, setState] = useState<HlStagegProjection | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [activityTab, setActivityTab] = useState<'exposure' | 'executions'>('exposure');
  const [equityChanges, setEquityChanges] = useState<HlNativeEquityChanges | null>(null);
  const [fillHistory, setFillHistory] = useState<HlStagegFillHistory | null>(null);
  const [fillHistoryUnavailable, setFillHistoryUnavailable] = useState(false);
  const [fillHistoryHasMore, setFillHistoryHasMore] = useState(false);
  const load = () => void getHlStagegProjection().then((projection) => {
    setState(projection); setMessage('');
  }).catch((error: unknown) => {
    setState(null); setMessage(error instanceof Error ? error.message : `${selectedModeLabel} projection unavailable.`);
  }).finally(() => setLoading(false));
  useEffect(() => { load(); const timer = window.setInterval(load, 5000); return () => window.clearInterval(timer); }, []);
  useEffect(() => { let active = true; const refresh = () => void getHlStagegEquityChanges().then((data) => { if (active) setEquityChanges(data); }).catch(() => { if (active) setEquityChanges(null); }); refresh(); const timer = window.setInterval(refresh, 60_000); return () => { active = false; window.clearInterval(timer); }; }, []);
  useEffect(() => {
    let active = true;
    const refreshFills = () => void getHlStagegFills(0, 100).then((data) => {
      if (active) {
        setFillHistory((current) => {
          if (!current || current.run_epoch !== data.run_epoch) return data;
          const retained = current.fills.filter((fill) => fill.cursor > data.next_cursor);
          return { ...data, fills: [...data.fills, ...retained], next_cursor: Math.max(data.next_cursor, current.next_cursor) };
        });
        setFillHistoryHasMore(data.fills.length === 100);
        setFillHistoryUnavailable(false);
      }
    }).catch(() => { if (active) { setFillHistory(null); setFillHistoryUnavailable(true); } });
    refreshFills();
    const timer = window.setInterval(refreshFills, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const loadMoreFills = () => {
    if (!fillHistory || !fillHistoryHasMore || !state?.run_epoch || fillHistory.run_epoch !== state.run_epoch) return;
    void getHlStagegFills(fillHistory.next_cursor, 100).then((data) => {
      setFillHistory((current) => current ? {
        ...current, fills: [...current.fills, ...data.fills],
        next_cursor: Math.max(current.next_cursor, data.next_cursor),
        historical_id_only_count: data.historical_id_only_count,
      } : data);
      setFillHistoryHasMore(data.fills.length === 100);
    }).catch(() => setFillHistoryUnavailable(true));
  };
  const runtimeStatus = dashboardState(state);
  const runtimeHealthy = state?.projection_state === 'READY' && state?.recovery_required !== true && state.process_state !== 'DATA_STALE/PAUSED' && state.process_state !== 'WORKER_DISCONNECTED';
  const entryGateMessage = loading && !state ? 'Loading strategy status' : state?.recovery_required === true
    ? 'New entries are blocked pending recovery'
    : state?.projection_state !== 'READY'
    ? 'Entry approval unavailable'
    : state.gates.attachable === false
      ? `New ${selectedModeLabel} entries blocked`
      : state.gates.attachable !== true
        ? 'Entry approval unknown'
        : state.entry_control.state === 'PAUSED'
          ? `New ${selectedModeLabel} entries paused`
          : runtimeHealthy
            ? 'Waiting for a strategy decision'
            : 'New entries blocked while the worker or market data is unhealthy';
    const positionRows = (state?.positions ?? []).map((position) => ({ ...position, id: position.instrument_id, mark: state?.feeds[position.instrument_id]?.mark ?? null }));
  const orderRows = (state?.orders ?? []).map((order) => ({ ...order, id: order.client_order_id }));
  const age = (value: number | null | undefined) => value === null || value === undefined ? 'Unavailable' : `${(value / 1_000_000_000).toFixed(1)}s`;
  const projectionReady = state?.projection_state === 'READY';
  const accountIsUnknown = !projectionReady || state.account.status === 'UNAVAILABLE' || state.recovery_required === true;
  const figures = accountIsUnknown ? [] : accountFigures(state);
  const positionSummary = state?.recovery_required === true
    ? positionRows.length ? String(positionRows.length) + " stored" : "Unreconciled"
    : projectionReady
      ? positionRows.length ? String(positionRows.length) + " open" : runtimeStatus.canAssertFlat ? "Flat" : "Unverified"
      : "Unavailable";
  const protection = state?.deposit_protection;
  const protectionVerified = protectionIsVerified(state);
  const protectionFresh = protectionIsFresh(state);
  const protectionArmed = protectionFresh && protection?.state === 'ARMED';
  const fillHistoryMatchesRun = Boolean(state?.run_epoch && fillHistory?.run_epoch === state.run_epoch);
  return <main className="terminal-layout nautilus-runtime-workspace">
    <DashboardConnectionIdentity />
    {selectedMode === 'live' && state?.projection_state !== 'READY' ? <Card title="Live is inactive or unavailable"><p className="trader-hero__lead">No current Live account snapshot is available.</p><p className="trader-note">Review the approved profile in Strategy. Activation requires separate approval for the exact release, account and profile. Account values appear after native read-back.</p><Button disabled title="Separate Live order approval is required">Activate Live</Button></Card> : null}
    <Card className="trader-hero runtime-hero" title="Account overview" actions={<Badge tone={loading && !state ? 'neutral' : runtimeStatus.tone}>{loading && !state ? 'Loading' : humanizeResearchCode(runtimeStatus.label)}</Badge>}>
      <div className="runtime-hero__heading"><div><p className="trader-note">{entryGateMessage}.</p><p className="runtime-snapshot-time">{selectedModeLabel} snapshot · {state?.observed_at_ns ? formatUtcTimestamp(new Date(state.observed_at_ns / 1_000_000).toISOString()) : 'time unavailable'}</p></div><Button variant="secondary" onClick={load}>Refresh</Button></div>
      <div className="runtime-account-grid runtime-account-grid--compact runtime-priority-grid">
        <Stat label="Equity" value={accountIsUnknown ? loading ? "Loading…" : "Unavailable" : figures.find((figure) => figure.label === "Marked equity")?.value ?? "Unavailable"} />
        <Stat label="Available cash" value={accountIsUnknown ? loading ? "Loading…" : "Unavailable" : figures.find((figure) => figure.label === "Available cash")?.value ?? "Unavailable"} />
        <Stat label="Realized P&L · net fees" value={accountIsUnknown ? loading ? "Loading…" : "Unavailable" : figures.find((figure) => figure.label === "Realized PnL after fees")?.value ?? "Unavailable"} />
        <Stat label="Unrealized P&L" value={accountIsUnknown ? loading ? "Loading…" : "Unavailable" : figures.find((figure) => figure.label === "Unrealized PnL")?.value ?? "Unavailable"} />
        {selectedMode === 'live' ? <Stat label="Posted funding" value={nativeMoney(state?.account.funding, projectionCurrency(state) && state?.account.funding_currency)} /> : null}
        <Stat label="Trading fees" value={accountIsUnknown ? loading ? "Loading…" : "Unavailable" : traderMoney(state?.account.fees, projectionCurrency(state))} />
        <Stat label="Effective leverage" value={effectiveLeverage(state)} />
      </div>
      <p className="account-capital-caption">{selectedMode === 'live' ? 'Live account ·' : 'Virtual starting capital: 10,000 USDC ·'} {projectionReady ? positionSummary + ' · ' + orderRows.length + ' working orders' : loading ? 'Loading exposure…' : 'Exposure unavailable'}</p>
      {accountIsUnknown ? null : <details className="nautilus-diagnostics runtime-account-details"><summary>Margin, P&amp;L and account details</summary>
        <div className="runtime-account-secondary" aria-label="Current margin and profit and loss">
          <Stat label="Initial margin" value={traderMoney(state?.account.im, projectionCurrency(state))} /><Stat label="Effective leverage" value={effectiveLeverage(state)} />
          <Stat label="Maintenance margin" value={traderMoney(state?.account.mm, projectionCurrency(state))} />
          <Stat label="Realized P&amp;L · net fees" value={figures.find((figure) => figure.label === "Realized PnL after fees")?.value ?? "Unavailable"} />
          <Stat label="Unrealized P&amp;L" value={figures.find((figure) => figure.label === "Unrealized PnL")?.value ?? "Unavailable"} />
        </div>
        <div className="runtime-account-grid runtime-account-grid--compact runtime-account-details__other">{figures.filter((figure) => !["Marked equity", "Available cash", "Realized PnL after fees", "Unrealized PnL"].includes(figure.label)).map((figure) => <Stat key={figure.label} label={figure.label} value={figure.value} />)}</div>
      </details>}
      {accountIsUnknown && !loading ? <div className="runtime-empty-note account-unavailable"><strong>Account valuation unavailable</strong><span>{runtimeStatus.detail}</span></div> : null}
      {state?.account.mark_state === 'STALE_OR_MISSING' ? <p className="runtime-empty-note">Mark is stale or missing. Marked equity and unrealized P&amp;L are not current.</p> : null}
      {state?.account.status === 'PARTIAL' ? <p className="runtime-empty-note">Account read is partial. Missing account fields remain unavailable.</p> : null}
    </Card>
    {selectedMode === 'live' && state?.account.funding_reason ? <p className="trader-note">Funding: {humanizeBlocker(state.account.funding_reason)}. Posted funding is already included in reported equity.</p> : null}
    <DashboardMarketChart projection={state} history={fillHistoryMatchesRun ? fillHistory : null} equity={equityChanges} />
    <div className="trader-activity-tabs" role="tablist" aria-label="Trading activity">
      <button type="button" id="exposure-tab" role="tab" aria-selected={activityTab === 'exposure'} aria-controls="exposure-panel" onClick={() => setActivityTab('exposure')}>Positions &amp; orders</button>
      <button type="button" id="executions-tab" role="tab" aria-selected={activityTab === 'executions'} aria-controls="executions-panel" onClick={() => setActivityTab('executions')}>Executions</button>
    </div>
    <section id="exposure-panel" role="tabpanel" aria-labelledby="exposure-tab" hidden={activityTab !== 'exposure'} className="trader-market-grid" aria-label="BTC and SOL Markets">
      {TRADER_MARKETS.map(({ symbol, instrumentId }) => {
        const feed = state?.feeds[instrumentId];
        const fresh = feed?.state === 'READY' && feed.mark_age_ns != null && feed.mark_age_ns >= 0 && feed.mark_age_ns <= 15_000_000_000;
        const position = positionPresentation(state, instrumentId);
        const linkedOrders = orderRows.filter((order) => order.instrument_id === instrumentId);
        return <Card key={instrumentId} className="trader-market-card" title={symbol + "/USDC"} actions={<Badge tone={loading && !state ? 'neutral' : fresh ? 'success' : 'danger'}>{loading && !state ? 'Loading' : fresh ? 'Live' : feed?.state === 'READY' ? 'Stale' : humanizeResearchCode(feed?.state ?? 'UNAVAILABLE')}</Badge>}>
          <div className="trader-market-price">
            <span>{fresh ? 'Mark' : 'Previous mark'}</span>
            <strong>{loading && !state ? 'Loading…' : nativeMoney(feed?.mark, projectionCurrency(state))}</strong>
            <small>{fresh ? `Mark age ${age(feed?.mark_age_ns)}` : feed?.mark ? `Stale · ${age(feed.mark_age_ns)}` : 'Mark unavailable'}</small>
          </div>
          <div className="trader-market-exposure">
            <div className="trader-market-exposure__heading"><span>{selectedModeLabel} position</span><Badge tone={position.state === 'OPEN' ? 'success' : position.state === 'FLAT' ? 'neutral' : 'danger'}>{position.state === 'OPEN' ? 'Open' : position.state === 'FLAT' ? 'Flat' : loading && !state ? 'Loading' : 'Unconfirmed'}</Badge></div>
            {position.state === 'OPEN' ? <div className="trader-market-exposure__value"><strong className={position.side === 'LONG' ? 'up' : 'down'}>{position.side}</strong><span>{traderNumber(Math.abs(Number(position.quantity)), 5)} {symbol}</span></div> : position.state === 'FLAT' ? <p>Confirmed flat · 0 position size</p> : <p>{loading ? 'Loading position…' : state?.recovery_required ? 'Position ownership requires recovery.' : 'Position status unavailable.'}</p>}
          </div>
          {position.state === 'OPEN' ? <dl className="position-price-details"><div><dt>Average entry</dt><dd>{nativeMoney(positionRows.find((row) => row.instrument_id === instrumentId)?.average_entry_price, projectionCurrency(state))}</dd></div><div><dt>Current mark</dt><dd>{fresh ? nativeMoney(feed?.mark, projectionCurrency(state)) : 'Stale · unavailable'}</dd></div></dl> : null}
          <div className="trader-market-orders">
            <div className="trader-market-orders__heading"><span>{state?.recovery_required ? 'Stored orders' : 'Working orders'}</span><span>{state?.projection_state === 'READY' ? linkedOrders.length : 'Unavailable'}</span></div>
            {linkedOrders.length ? linkedOrders.map((order) => <div className="trader-market-order" key={order.client_order_id}>
              <span>{order.reduce_only === true ? 'Take-profit / reduction' : 'Working order'}{order.side ? ` · ${order.side}` : ''}</span>
              <strong>{nativeMoney(order.price, projectionCurrency(state))}</strong>
              <small>{humanizeResearchCode(order.status ?? 'UNAVAILABLE')} · {humanizeResearchCode(order.order_type ?? 'UNAVAILABLE')} · remaining {order.leaves_quantity ?? order.quantity ?? 'Unavailable'}</small>
            </div>) : <p>{state?.recovery_required ? 'Stored order ownership is not reconciled.' : runtimeStatus.canAssertFlat ? 'No working orders.' : 'Order state unavailable.'}</p>}
          </div>
        </Card>;
      })}
    </section>
    {(() => {
      const knownInstruments = new Set<string>(TRADER_MARKETS.map((market) => market.instrumentId));
      const otherPositions = positionRows.filter((position) => !knownInstruments.has(position.instrument_id));
      const otherOrders = orderRows.filter((order) => !order.instrument_id || !knownInstruments.has(order.instrument_id));
      if (!otherPositions.length && !otherOrders.length) return null;
      return <Card title="Other positions and orders" actions={<Badge tone="danger">Review</Badge>}>
        <DataTable rows={otherPositions.map((row) => ({ ...row, id: row.instrument_id }))} emptyText="No additional position rows." mobileTitle={(row) => row.instrument_id} columns={[{ key: 'instrument', header: 'Market', render: (row) => row.instrument_id }, { key: 'quantity', header: 'Position size', render: (row) => row.signed_quantity }, { key: 'mark', header: 'Reference mark', render: (row) => row.mark ?? 'Unavailable' }]} />
        <DataTable rows={otherOrders} emptyText="No additional order rows." mobileTitle={(row) => row.instrument_id ?? 'Other market order'} mobileSubtitle={(row) => humanizeResearchCode(row.status ?? 'UNAVAILABLE')} columns={[{ key: 'instrument', header: 'Market', render: (row) => row.instrument_id ?? 'Unavailable' }, { key: 'order', header: 'Order', render: (row) => row.reduce_only === true ? 'Reduce only' : 'Working order' }, { key: 'status', header: 'Status', render: (row) => humanizeResearchCode(row.status ?? 'UNAVAILABLE') }, { key: 'price', header: 'Price', render: (row) => row.price ?? 'Unavailable' }, { key: 'leaves', header: 'Leaves', render: (row) => row.leaves_quantity ?? row.quantity ?? 'Unavailable' }]} />
      </Card>;
    })()}
    <div id="executions-panel" role="tabpanel" aria-labelledby="executions-tab" hidden={activityTab !== 'executions'}><Card title="Recent executions">
      {!fillHistoryMatchesRun
        ? <p className="runtime-empty-note">{fillHistoryUnavailable ? 'Detailed fill history is unavailable.' : !state?.run_epoch ? 'Fill history is hidden until the current workspace is confirmed.' : 'History is refreshing after restart; earlier rows are hidden.'}</p>
        : !fillHistory?.detail_store_available
        ? <p className="runtime-empty-note">{unavailableTradeHistoryLabel(fillHistory?.historical_id_only_count)}</p>
        : <>
          {fillHistory.historical_id_only_count > 0 ? <p className="muted">{fillHistory.historical_id_only_count} older execution record{fillHistory.historical_id_only_count === 1 ? ' has' : 's have'} no saved trade details.</p> : null}
          <DataTable rows={fillHistory.fills.slice().sort((a, b) => b.cursor - a.cursor).map((fill) => ({ ...fill, id: String(fill.cursor) }))} emptyText="No detailed executions recorded yet." mobileTitle={(fill) => `${fill.instrument_id.startsWith('BTC-') ? 'BTC/USDC' : fill.instrument_id.startsWith('SOL-') ? 'SOL/USDC' : 'Other market'} · ${nativeFillActionLabel(fill.action)}`} mobileSubtitle={(fill) => (fill.order_side ?? 'Side unavailable') + ' · ' + fill.quantity + ' @ ' + fill.price} columns={[
            { key: 'action', header: 'Type', render: (fill) => nativeFillActionLabel(fill.action) },
            { key: 'time', header: 'Time (UTC)', render: (fill) => fill.ts_event_ns == null ? 'Unavailable' : formatUtcTimestamp(new Date(fill.ts_event_ns / 1000000).toISOString()) },
            { key: 'market', header: 'Market', render: (fill) => fill.instrument_id.startsWith('BTC-') ? 'BTC/USDC' : fill.instrument_id.startsWith('SOL-') ? 'SOL/USDC' : 'Other market' },
            { key: 'side', header: 'Side', render: (fill) => fill.order_side ?? 'Unavailable' },
            { key: 'quantity', header: 'Quantity', render: (fill) => traderNumber(fill.quantity, 5) },
            { key: 'price', header: 'Price', render: (fill) => nativeMoney(fill.price, projectionCurrency(state)) },
            { key: 'fee', header: 'Fee', render: (fill) => fill.commission_amount == null ? 'Unavailable' : nativeMoney(fill.commission_amount, fill.commission_currency) },
          ]} />
          {fillHistoryHasMore ? <Button variant="secondary" onClick={loadMoreFills}>Load more fills</Button> : null}
        </>}
    </Card></div>
    {selectedMode === 'live' && state?.c1 ? <Card title="Capital control"><p className="trader-note">{humanizeResearchCode(state.c1.state)}{state.c1.reason ? ' · ' + humanizeBlocker(state.c1.reason) : ''}</p><div className="runtime-account-grid runtime-account-grid--compact"><Stat label="Reported equity E" value={nativeMoney(state.c1.E, projectionCurrency(state) && state.c1.currency)} /><Stat label="High-water equity H" value={nativeMoney(state.c1.H, projectionCurrency(state) && state.c1.currency)} /><Stat label="Cushion" value={nativeMoney(state.c1.cushion, projectionCurrency(state) && state.c1.currency)} /><Stat label="Drawdown" value={traderPercent(projectionCurrency(state) && state.c1.currency === "USDC" ? state.c1.DD : null)} /></div></Card> : null}
    <Card title="Drawdown protection" actions={<Badge tone={loading && !state ? "neutral" : protectionArmed ? "success" : "danger"}>{protectionArmed ? "Protected" : loading ? "Loading…" : state?.recovery_required ? "Unverified" : protectionVerified ? "Stale" : "Not set"}</Badge>}>
      {protectionFresh ? <><p className="trader-note">Retained equity floor: <strong>{traderNumber(100 - (protection?.drawdown_limit_percent ?? 100), 0)}%</strong> · Maximum drawdown: <strong>{String(protection?.drawdown_limit_percent)}%</strong></p><details className="nautilus-diagnostics"><summary>Protection basis and sample time</summary><div className="runtime-account-grid runtime-account-grid--compact"><Stat label="Protection equity" value={nativeMoney(protection?.equity, protection?.currency)} /><Stat label="High-water equity" value={nativeMoney(protection?.high_water_equity, protection?.currency)} /><Stat label="Threshold" value={nativeMoney(protection?.threshold_equity, protection?.currency)} /><Stat label="Last daily close" value={formatUtcTimestamp(protection?.last_daily_close_utc)} /><Stat label="Observed" value={protection?.observed_at_ns ? formatUtcTimestamp(new Date(protection.observed_at_ns / 1_000_000).toISOString()) : "Unavailable"} /></div></details></> : <p className="runtime-empty-note">{state?.recovery_required ? "Protection baseline is unverified while recovery is required. Displayed values are withheld until the native account is recovered." : protectionVerified ? "Protection read is stale. Values are withheld until a fresh worker read is available." : loading ? "Loading drawdown protection…" : "Protection is not armed."}</p>}
    </Card>
    {state?.warnings.filter((warning) => warning !== 'FLAT_RESTART').length ? <div className="runtime-warning-list" role="status"><strong>Worker notice</strong><ul>{state.warnings.filter((warning) => warning !== 'FLAT_RESTART').map((warning, index) => <li key={index}>{humanizeBlocker(warning)}</li>)}</ul></div> : null}

    {message ? <p role="alert">Runtime account data is unavailable. Refresh to retry.</p> : null}
  </main>;
}

export function WorkspaceSettingsPage() {
  const [state, setState] = useState<HlStagegProjection | null>(null);
  const [controls, setControls] = useState<HlStagegControls | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [commandInFlight, setCommandInFlight] = useState<string | null>(null);
  const [protectionDraft, setProtectionDraft] = useState('50');
  async function refresh() {
    setLoading(true);
    const [projection, capabilities] = await Promise.allSettled([getHlStagegProjection(), getHlStagegControls()]);
    setState(projection.status === 'fulfilled' ? projection.value : null);
    if (projection.status === 'fulfilled') setProtectionDraft(String(projection.value.deposit_protection?.drawdown_limit_percent ?? 50));
    setControls(capabilities.status === 'fulfilled' ? capabilities.value : null);
    const failed = [projection, capabilities].find((result) => result.status === 'rejected');
    setMessage(failed?.status === 'rejected' ? String(failed.reason) : '');
    setLoading(false);
    return projection.status === 'fulfilled' ? projection.value : null;
  }
  useEffect(() => { void refresh(); }, []);
  const protection = state?.deposit_protection;
  const pausedAndFlat = (selectedMode !== 'live' || state?.real_order_approval === true && state?.live_order_capability === true) && state?.projection_state === 'READY'
    && state.recovery_required !== true
    && state.entry_control.state === 'PAUSED'
    && state.positions.every((position) => Number(position.signed_quantity) === 0)
    && state.orders.length === 0;
  const percent = Number(protectionDraft);
  const protectionVerified = protectionIsVerified(state);
  const protectionFresh = Boolean(protectionVerified && protection?.observed_at_ns && Date.now() * 1_000_000 - protection.observed_at_ns <= 15_000_000_000);
  const controlsAllowed = state?.recovery_required !== true;
  async function saveProtection() {
    if (commandInFlight || !Number.isInteger(percent) || percent < 1 || percent > 99 || !pausedAndFlat) return;
    setCommandInFlight('set-deposit-protection'); setMessage('Saving deposit protection…');
    try {
      const result = await commandHlStagegDepositProtection('set-deposit-protection', crypto.randomUUID(), percent);
      const fresh = await refresh();
      if (!verifiedControlReadback(state, fresh) || fresh?.deposit_protection?.drawdown_limit_percent !== percent || result.status !== 'APPLIED' || result.deposit_protection.drawdown_limit_percent !== percent) throw new Error('Deposit protection read-back mismatch.');
      setMessage('Deposit protection saved and read back.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Deposit protection save failed.'); }
    finally { setCommandInFlight(null); }
  }
  async function resetProtection() {
    if (commandInFlight || !pausedAndFlat || protection?.equity == null) return;
    if (!window.confirm('Set a new deposit protection baseline from current equity? The worker remains paused; resume is a separate action.')) return;
    setCommandInFlight('reset-deposit-protection'); setMessage('Resetting deposit protection baseline…');
    try {
      const result = await commandHlStagegDepositProtection('reset-deposit-protection', crypto.randomUUID());
      const fresh = await refresh();
      if (!verifiedControlReadback(state, fresh) || !protectionIsFresh(fresh) || fresh?.deposit_protection?.state !== 'ARMED' || result.status !== 'APPLIED') throw new Error('Deposit protection reset was not confirmed.');
      setMessage('New baseline applied and read back. The worker remains paused.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Deposit protection reset failed.'); }
    finally { setCommandInFlight(null); }
  }
  async function commandEntries(command: 'pause-new-entries' | 'resume-new-entries') {
    if (commandInFlight) return;
    setCommandInFlight(command); setMessage('Updating entry controls…');
    try {
      const result = await commandHlStagegEntries(command, crypto.randomUUID());
      const fresh = await refresh();
      if (!verifiedControlReadback(state, fresh, result.entry_control)) throw new Error('Entry control was accepted but fresh worker confirmation is unavailable. Refresh status before retrying.');
      setMessage(`${result.command === 'pause-new-entries' ? 'New entries paused' : 'New entries resumed'} (${result.status.toLowerCase()} and read back).`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Entry control update failed.'); }
    finally { setCommandInFlight(null); }
  }
  return <main className="terminal-layout">
    <ExecutionModeSettings />
    <Card title={`${selectedModeLabel} account`} actions={<Badge tone={state?.projection_state === 'READY' ? 'success' : 'danger'}>{loading ? 'Connecting' : state?.projection_state === 'READY' ? 'Connected' : state?.projection_state === 'STALE' ? 'Stale' : 'Unavailable'}</Badge>}>
      <div className="settings-sandbox-summary"><span>Execution mode</span><strong>{selectedMode === 'live' ? 'Live · separate order approval required' : 'Sandbox · order routing off'}</strong><Button variant="secondary" onClick={() => void refresh()}>Refresh</Button></div>
      <details className="settings-sandbox-details"><summary>Funding and account notes</summary><p>{selectedMode === 'live' ? 'Account values come from the native exchange account.' : 'Observed funding is reference only and is not credited to Sandbox cash.'} {fundingLabel(state)}.</p></details>
    </Card>
    <SettingsConnections />
    {selectedMode === 'live' && state?.c1 ? <Card title="Capital control"><p className="trader-note">{humanizeResearchCode(state.c1.state)}{state.c1.reason ? ' · ' + humanizeBlocker(state.c1.reason) : ''}</p><div className="runtime-account-grid runtime-account-grid--compact"><Stat label="Reported equity E" value={nativeMoney(state.c1.E, projectionCurrency(state) && state.c1.currency)} /><Stat label="High-water equity H" value={nativeMoney(state.c1.H, projectionCurrency(state) && state.c1.currency)} /><Stat label="Cushion" value={nativeMoney(state.c1.cushion, projectionCurrency(state) && state.c1.currency)} /><Stat label="Drawdown" value={traderPercent(projectionCurrency(state) && state.c1.currency === "USDC" ? state.c1.DD : null)} /></div></Card> : null}
    <Card title="Drawdown protection" actions={<Badge tone={loading && !state ? "neutral" : protectionFresh ? "success" : "danger"}>{protectionFresh ? "Protected" : loading ? "Loading…" : state?.recovery_required ? "Unverified" : protectionVerified ? "Stale" : "Not set"}</Badge>}>
      {state?.recovery_required ? <p className="runtime-empty-note">Recovery is required. Protection values are withheld and settings remain read-only until account ownership is restored.</p> : <>
      <p className="muted">Changes require a paused worker and confirmed flat exposure.</p>
      <div className="rules-form-grid">
        <label className="rules-field"><span>Allowed drawdown, %</span><input aria-label="Allowed drawdown, %" type="number" min={1} max={99} step={1} value={protectionDraft} onChange={(event) => setProtectionDraft(event.target.value)} /></label>
        <div className="rules-btn-group rules-btn-group--mb"><Button variant="secondary" disabled={!pausedAndFlat || !Number.isInteger(percent) || percent < 1 || percent > 99 || commandInFlight !== null} onClick={() => void saveProtection()}>{commandInFlight === 'set-deposit-protection' ? 'Saving…' : 'Save'}</Button><Button variant="danger" disabled={!pausedAndFlat || protection?.equity == null || commandInFlight !== null} onClick={() => void resetProtection()}>{commandInFlight === 'reset-deposit-protection' ? 'Resetting…' : 'Set new baseline'}</Button></div>
      </div>
      {protectionFresh ? <p className="muted">Protection is {protection?.state?.toLowerCase() ?? 'unavailable'} · Equity {nativeMoney(protection?.equity, protection?.currency)} · High-water {nativeMoney(protection?.high_water_equity, protection?.currency)} · Limit threshold {nativeMoney(protection?.threshold_equity, protection?.currency)}.</p> : <p className="runtime-empty-note">Protection values are stale or unverified and are withheld.</p>}
      </>}
    </Card>
    <Card title="Entry controls" actions={<Badge tone={controls?.pause.enabled && controlsAllowed ? 'success' : 'danger'}>{controlAvailabilityLabel(controls?.pause.enabled && controlsAllowed, state?.recovery_required)}</Badge>}>
      <p className="muted">Pause and resume govern entry submission. Strategy eligibility is shown separately below.</p>
      <p className="muted"><strong>New-entry eligibility:</strong> {state?.recovery_required ? 'Blocked while recovery is required' : state?.projection_state !== 'READY' ? 'Unknown · worker status is not ready' : state?.gates.attachable === false ? 'Blocked by the native strategy gate' : state?.gates.attachable === true && state.entry_control.state === 'PAUSED' ? 'Blocked · entries are paused' : state?.gates.attachable === true ? 'Eligible for strategy evaluation' : 'Unknown · native gate status unavailable'}.</p>
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="secondary" disabled={!controlsAllowed || !controls?.pause.enabled || commandInFlight !== null} title={controls?.pause.blocker ? humanizeBlocker(controls.pause.blocker) : 'Available'} onClick={() => void commandEntries('pause-new-entries')}>{commandInFlight === 'pause-new-entries' ? 'Pausing…' : 'Pause new entries'}</Button><Button variant="secondary" disabled={!controlsAllowed || !controls?.resume.enabled || commandInFlight !== null} title={controls?.resume.blocker ? humanizeBlocker(controls.resume.blocker) : 'Available'} onClick={() => void commandEntries('resume-new-entries')}>{commandInFlight === 'resume-new-entries' ? 'Resuming…' : 'Resume new entries'}</Button><Button variant="danger" disabled title={controls?.flatten.blocker ? humanizeBlocker(controls.flatten.blocker) : 'Unavailable'}>Flatten virtual exposure</Button></div>
      <details className="nautilus-diagnostics"><summary>Control availability</summary><p className="muted">Pause: {controls?.pause.blocker ? humanizeBlocker(controls.pause.blocker) : 'Available'} · Resume: {controls?.resume.blocker ? humanizeBlocker(controls.resume.blocker) : 'Available'} · Flattening: unavailable.</p></details>
    </Card>
    {message ? <p role="alert">{message}</p> : null}
  </main>;
}
