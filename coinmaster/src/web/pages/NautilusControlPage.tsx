import { useEffect, useState } from 'react';
import { DashboardMarketChart } from '../components/DashboardMarketChart';
import { DashboardConnectionIdentity } from '../components/DashboardConnectionIdentity';
import { SettingsConnections } from '../components/SettingsConnections';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';
import { cancelRun, commandHlStagegDepositProtection, commandHlStagegEntries, createRun, getConfigurations, getDefaultConfiguration, getHlStagegControls, getHlStagegEquityChanges, getHlStagegFills, getHlStagegProjection, getHlStagegStrategy, getResearchCapabilities, getResearchCatalog, getRuns, saveConfiguration, type HlNativeEquityChanges, type HlStagegControls, type HlStagegFillHistory, type HlStagegProjection, type HlStagegStrategy, type ResearchCapabilities, type ResearchCatalogEntry, type Run, type StrategyConfig, type StrategyConfiguration } from '../lib/nautilusApi';
import { accountFigures, dashboardState, fundingLabel, formatUtcTimestamp, protectionIsFresh, protectionIsVerified } from '../lib/accountPresentation';
import { positionPresentation, TRADER_MARKETS } from '../lib/traderPresentation';
import { parseFiniteNumberFields } from '../lib/strategyDraftValidation';
import { controlAvailabilityLabel, humanizeBlocker, humanizeResearchCode, isAdvancedStrategySetting, nativeFillActionLabel, unavailableTradeHistoryLabel, strategyRunnerLabel, strategySettingLabel, strategySettingValue } from '../lib/traderLabels';

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

function NumberArrayField({ label, value, onCommit }: { label: string; value: number[]; onCommit: (next: number[]) => void }) {
  const serialized = value.map(String);
  const [draft, setDraft] = useState(serialized);
  const [invalid, setInvalid] = useState(false);
  useEffect(() => { setDraft(serialized); setInvalid(false); }, [value.join(',')]);
  function change(index: number, next: string) { setDraft((current) => current.map((field, fieldIndex) => fieldIndex === index ? next : field)); }
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
  const [strategy, setStrategy] = useState<HlStagegStrategy | null>(null); const [config, setConfig] = useState<StrategyConfig | null>(null); const [drafts, setDrafts] = useState<StrategyConfiguration[]>([]); const [saved, setSaved] = useState<StrategyConfiguration | null>(null); const [message, setMessage] = useState(''); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false);
  async function load() { setLoading(true); setMessage(''); const [sealed, stored, template] = await Promise.allSettled([getHlStagegStrategy(), getConfigurations(), getDefaultConfiguration()]); if (sealed.status === 'fulfilled') setStrategy(sealed.value); if (stored.status === 'fulfilled') { setDrafts(stored.value); const selected = stored.value.find((item) => item.id === window.localStorage.getItem('coinmaster-selected-config')) ?? stored.value[0]; if (selected) { setSaved(selected); setConfig(selected.config); } } if (template.status === 'fulfilled') setConfig((current) => current ?? template.value.config); const failure = [sealed, stored, template].find((result) => result.status === 'rejected'); if (failure?.status === 'rejected') setMessage(failure.reason instanceof Error ? failure.reason.message : 'Unable to load the Strategy page.'); setLoading(false); }
  useEffect(() => { void load(); }, []);
  function updateNumber(key: NumberKey, value: string) { if (value !== '') setConfig((item) => item ? { ...item, [key]: Number(value) } : item); }
  function updateArray(key: ArrayKey, value: number[]) { setConfig((item) => item ? { ...item, [key]: value } : item); }
  async function save() { if (!config || saving) return; if (!Number.isFinite(Number(config.initial_total_usdt)) || Number(config.initial_total_usdt) <= 0) { setMessage('Research draft validation failed: initial total must be a positive number.'); return; } setSaving(true); setMessage('Saving research draft…'); try { const next = await saveConfiguration(config); const refreshed = await getConfigurations(); const persisted = refreshed.find((item) => item.id === next.id); if (!persisted) throw new Error('Saved draft could not be read back.'); setDrafts(refreshed); setSaved(persisted); setConfig(persisted.config); window.localStorage.setItem('coinmaster-selected-config', persisted.id); setMessage(`Research draft saved and read back: ${formatUtcTimestamp(persisted.created_at)}.`); } catch (error) { setMessage(error instanceof Error ? error.message : 'Research draft save failed.'); } finally { setSaving(false); } }
  const runningMatch = strategy?.running_state === 'RUNNING_MATCH';
  const sourceChecked = strategy?.source_state === 'SEALED_SOURCE_CHECKED';
  const runningParameters = Object.entries(strategy?.candidate ?? {}).map(([parameter, value]) => ({ id: parameter, parameter, value }));
  const visibleRunningParameters = runningParameters.filter((row) => !isAdvancedStrategySetting(row.parameter));
  const advancedRunningParameters = runningParameters.filter((row) => isAdvancedStrategySetting(row.parameter));
  const strategyGroups = [
    ['BTC sizing and exits', visibleRunningParameters.filter((row) => row.parameter.startsWith('btc_'))],
    ['SOL sizing and exits', visibleRunningParameters.filter((row) => row.parameter.startsWith('sol_'))],
    ['Signal and safety settings', visibleRunningParameters.filter((row) => !row.parameter.startsWith('btc_') && !row.parameter.startsWith('sol_'))],
  ] as const;
  return <main className="terminal-layout nautilus-strategy-workspace">
    <Card className="trader-hero strategy-hero" title={runningMatch ? 'Running strategy' : sourceChecked ? 'Sealed strategy' : 'Strategy source unavailable'} actions={<Badge tone={runningMatch ? 'success' : 'danger'}>{strategyRunnerLabel(strategy?.running_state ?? (loading ? 'LOADING' : 'NOT_CONFIRMED'))}</Badge>}>
      <p className="trader-hero__lead">{runningMatch ? 'The worker is running the sealed BTC / SOL strategy shown below.' : sourceChecked ? 'The sealed strategy was read successfully, but the worker match is not confirmed.' : 'The strategy source could not be confirmed. No running settings are implied.'}</p>
      <div className="stats-grid"><Stat label="Strategy" value={strategy?.strategy_id ?? 'Unavailable'} /><Stat label="Execution" value="Local Sandbox" /><Stat label="Market data" value="Hyperliquid public" /><Stat label="Apply to running strategy" value="Unavailable" /></div>
      <p className="trader-note">Running settings are read-only. A research draft never changes the active trader.</p>
    </Card>
    <section className="strategy-settings-grid">{strategyGroups.map(([group, rows]) => <Card className="strategy-settings-card" key={group} title={group} actions={<Badge tone={runningMatch ? 'success' : 'neutral'}>{runningMatch ? 'Confirmed' : 'Unconfirmed'}</Badge>}>
      {rows.length ? <dl className="strategy-setting-list">{rows.map((row) => <div className="strategy-setting-row" key={row.parameter}><dt>{title(row.parameter)}</dt><dd>{displaySetting(row.parameter, row.value)}</dd></div>)}</dl> : <p className="runtime-empty-note">No sealed settings are available.</p>}
    </Card>)}</section>
    {advancedRunningParameters.length ? <details className="nautilus-diagnostics"><summary>Advanced strategy rules</summary><dl className="strategy-setting-list">{advancedRunningParameters.map((row) => <div className="strategy-setting-row" key={row.parameter}><dt>{title(row.parameter)}</dt><dd>{displaySetting(row.parameter, row.value)}</dd></div>)}</dl></details> : null}
    <details className="nautilus-diagnostics strategy-research-drafts"><summary>Research drafts · saved separately from the running strategy</summary><div className="research-drafts-card">
      <p className="trader-hero__lead">Draft parameters are saved for research only. The running strategy above remains unchanged.</p>
      <label className="rules-field"><span>Read-back saved draft</span><select value={saved?.id ?? ''} onChange={(event) => { const next = drafts.find((item) => item.id === event.target.value) ?? null; setSaved(next); setConfig(next?.config ?? config); if (next) window.localStorage.setItem('coinmaster-selected-config', next.id); }}>{drafts.map((item) => <option key={item.id} value={item.id}>Saved draft · {formatUtcTimestamp(item.created_at)}</option>)}</select></label>
      <div className="nautilus-strategy-grid">
        <section className="nautilus-strategy-group"><h3>BTC sizing and exits</h3><p className="muted">Research draft; sealed running parameters stay above.</p><div className="rules-form-grid">
        {(['ema_period', 'btc_notional_multiplier', 'btc_close_trail_fraction'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <NumberArrayField label="BTC TP fractions / initial qty" value={config.btc_tp_fractions_initial_qty} onCommit={(next) => updateArray('btc_tp_fractions_initial_qty', next)} /> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>SOL sizing and exits</h3><p className="muted">Entry thresholds, add sizes and staged exits.</p><div className="rules-form-grid">
        {(['sol_exit_half_z', 'sol_exit_all_z', 'sol_max_holding_days'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <><NumberArrayField label="SOL multipliers H" value={config.sol_size_multipliers_H} onCommit={(next) => updateArray('sol_size_multipliers_H', next)} /><NumberArrayField label="SOL entry z" value={config.sol_entry_z} onCommit={(next) => updateArray('sol_entry_z', next)} /></> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>Signal windows</h3><p className="muted">Feature history and wave thresholds.</p><div className="rules-form-grid">
        {(['beta_days', 'relative_days', 'z_history_days', 'wave_history_days', 'wave_min_count'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <><NumberArrayField label="Wave quantiles" value={config.wave_quantiles} onCommit={(next) => updateArray('wave_quantiles', next)} /></> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>Capital and constraints</h3><p className="muted">Fixed v0 controls are visible but cannot be edited.</p><div className="rules-form-grid">
        <label className="rules-field"><span>Initial TOTAL (template constraint)</span><input disabled value={config?.initial_total_usdt ?? ''} /></label>
        <label className="rules-field"><span>Initial active fraction (template constraint)</span><input disabled type="number" value={String(config?.initial_active_fraction ?? '')} /></label>
        <label className="rules-field"><span>Research venue</span><select value={config?.venue ?? ''} onChange={(event) => setConfig((item) => item ? { ...item, venue: (event.target.value || null) as StrategyConfig['venue'] } : item)}><option value="">Unselected</option><option value="bybit">Bybit</option><option value="hyperliquid">Hyperliquid</option></select></label>
        {(['max_gross_to_active'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        <label className="rules-field"><span>Maximum parent order notional</span><input type="number" step="any" value={config?.max_parent_notional ?? ''} onChange={(event) => setConfig((item) => item ? { ...item, max_parent_notional: event.target.value } : item)} /></label>
        <label className="rules-field"><span>Include zero waves (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.include_zero_waves)} /></label>
        <label className="rules-field"><span>Freeze sigma on first SOL fill (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.freeze_sigma_on_first_sol_fill)} /></label>
        <label className="rules-field"><span>Insufficient margin (v0 fixed)</span><select disabled value={config?.insufficient_margin ?? 'reject'}><option value="reject">reject</option></select></label>
        </div></section>
      </div>
      <p className="muted">Template constraints remain fixed until a separately scoped native implementation. Server validation is authoritative for research-draft saves.</p>
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!config || saving} onClick={() => void save()}>{saving ? 'Saving…' : 'Save research draft'}</Button>{saved ? <Badge tone="success">Saved draft read back</Badge> : null}</div>{message ? <p className="muted">{message}</p> : null}
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
    if (starting || capabilities?.baseline_state !== 'READY') return;
    setStarting(true); setMessage('Creating verified native baseline job…');
    try {
      const saved = await ensureConfig();
      const run = await createRun(saved.id, 'research', 'native_baseline');
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
  const optimizerReady = capabilities?.optimizer_state === 'READY';
  const optimizerSearch = capabilities?.optimizer_search as { axis: string; values: string[]; max_variants: number } | undefined;
  const top20 = Array.isArray(selectedRun?.report?.top20) ? selectedRun.report.top20 as { candidate_id: string; candidate_sha256: string; terminal_active: string; terminal_reserve: string; terminal_total: string; roi: string; drawdown_percent: string; liquidations: number; maker_fees: string; taker_fees: string; funding: { count?: number; signed_amount?: string }; fills: number; limitations: string[]; artifact_sha256: string; classification: string }[] : [];
  return <main className="terminal-layout nautilus-research-workspace">
    <Card className="trader-hero research-hero" title="Research workspace" actions={<Badge tone={baselineReady ? 'success' : 'danger'}>{humanizeResearchCode(capabilities?.baseline_state ?? (loading ? 'LOADING' : 'BLOCKED'))}</Badge>}>
      <p className="trader-hero__lead">Run a bounded backtest using the selected saved configuration. It never changes the running strategy.</p>
      <div className="rules-form-grid">
        <label className="rules-field"><span>Immutable configuration</span><select value={config?.id ?? ''} onChange={(event) => { const next = configs.find((item) => item.id === event.target.value) ?? null; setConfig(next); setCapabilities(null); if (next) { window.localStorage.setItem('coinmaster-selected-config', next.id); void getResearchCapabilities(next.id).then(setCapabilities).catch((error: Error) => setMessage(error.message)); } }}>{configs.map((item) => <option key={item.id} value={item.id}>Saved draft · {formatUtcTimestamp(item.created_at)}</option>)}</select></label>
        <label className="rules-field"><span>Start date</span><input disabled value={capabilities?.baseline_start ? formatUtcTimestamp(capabilities.baseline_start) : 'Unavailable'} /></label>
        <label className="rules-field"><span>End date (exclusive)</span><input disabled value={capabilities?.baseline_end_exclusive ? formatUtcTimestamp(capabilities.baseline_end_exclusive) : 'Unavailable'} /></label>
        <label className="rules-field"><span>Ranking objective</span><input disabled value={capabilities?.baseline_objective ?? 'TOTAL only'} /></label>
      </div>
      <p className="muted">Configuration and data coverage are checked before each run.</p>
      {capabilities?.baseline_blockers.length ? <><p className="muted">Baseline blocked: {capabilities.baseline_blockers.map(humanizeBlocker).join(' ')}</p></> : null}
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!baselineReady || starting || Boolean(activeRun)} onClick={() => void startBaseline()}>{starting ? 'Starting…' : activeRun ? 'Research running…' : 'Run historical baseline'}</Button><Button variant="secondary" onClick={() => void load()}>Refresh status</Button></div>
    </Card>
    <Card className="research-action-card" title="Bounded parameter search" actions={<Badge tone={optimizerReady ? 'success' : 'danger'}>{optimizerReady ? 'Ready' : humanizeResearchCode(capabilities?.optimizer_state ?? 'BLOCKED')}</Badge>}>
      <p className="muted">One axis: {optimizerSearch ? strategySettingLabel(optimizerSearch.axis) : 'BTC size'} = {optimizerSearch?.values.join(', ') ?? '—'} · up to {optimizerSearch?.max_variants ?? '—'} variants · rank by terminal total. Backtest evidence only.</p>
      {capabilities?.optimizer_blockers.length ? <><p className="muted">Research is blocked: {capabilities.optimizer_blockers.map(humanizeBlocker).join(' ')}</p></> : null}
      <Button variant="primary" disabled={!optimizerReady || !config || starting || Boolean(activeRun)} onClick={() => void startOptimizer()}>{starting ? 'Starting…' : activeRun ? 'Research busy…' : 'Optimize terminal total'}</Button>
    </Card>
    <Card className="research-result-card" title="Selected result" actions={selectedRun ? <Badge tone={tone(selectedRun.status)}>{humanizeResearchCode(selectedRun.status)}{selectedRun.progress == null ? '' : ' · ' + selectedRun.progress + '%'}</Badge> : <Badge tone="neutral">No run selected</Badge>}>
      <p className="muted">{activeRun ? "Backtest is running; progress refreshes automatically." : selectedRun ? "Showing the selected run." : "No run selected."}</p>
      <div className="stats-grid"><Stat label="Terminal TOTAL" value={String(terminalTotal ?? '—')} /><Stat label="Active" value={String(selectedRun?.report?.terminal_active ?? '—')} /><Stat label="Reserve" value={String(selectedRun?.report?.terminal_reserve ?? '—')} /><Stat label="ROI" value={String((selectedRun?.report?.summary as { roi?: string } | undefined)?.roi ?? '—')} /><Stat label="Max drawdown" value={String((selectedRun?.report?.summary as { max_drawdown_percent?: string } | undefined)?.max_drawdown_percent ?? '—')} /><Stat label="Recorded fills" value={String(selectedRun?.report?.fills ?? '—')} /></div>
      <p className="muted">Backtest evidence · fees: {String(selectedRun?.report?.native_fees ?? '—')} · liquidations: {String(selectedRun?.report?.liquidation_count ?? '—')}.</p>
      {selectedRun?.evidence.length ? <p className="muted">{selectedRun.evidence.map(humanizeBlocker).join(' ')}</p> : null}
      {top20.length ? <><h3 className="nautilus-subheading">TOP {top20.length} · terminal TOTAL comparison</h3><DataTable rows={top20.map((row) => ({ ...row, classification: humanizeResearchCode(row.classification), id: row.candidate_id }))} emptyText="No ranked candidates." mobileTitle={(row) => row.candidate_id} columns={[{ key: 'candidate', header: 'Candidate', render: (row) => row.candidate_id }, { key: 'total', header: 'TOTAL / ACTIVE / RESERVE', render: (row) => `${row.terminal_total} / ${row.terminal_active} / ${row.terminal_reserve}` }, { key: 'risk', header: 'ROI / DD / liq', render: (row) => `${row.roi} / ${row.drawdown_percent} / ${row.liquidations}` }, { key: 'costs', header: 'Fills / maker / taker / funding', render: (row) => `${row.fills} / ${row.maker_fees} / ${row.taker_fees} / ${row.funding?.signed_amount ?? '—'}` }, { key: 'proof', header: 'Classification / limits', render: (row) => `${row.classification} · ${row.limitations.join('; ')}` }]} /></> : <p className="muted">No TOP-20 comparison for this run. A completed optimizer publishes candidates here.</p>}
      {selectedRun && ['STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'QUEUED'].includes(selectedRun.status) ? <Button variant="danger" disabled={Boolean(cancellingId)} onClick={() => void cancelOwned(selectedRun.id)}>{cancellingId === selectedRun.id ? 'Cancelling…' : 'Cancel owned job'}</Button> : null}
    </Card>
    <Card title="Run history" actions={<Badge tone="neutral">Terminal total</Badge>}><DataTable rows={runs.map((run) => ({ ...run, id: run.id }))} emptyText="No research runs yet." mobileTitle={(run) => runTitle(run)} columns={[{ key: 'run', header: 'Run', render: (run) => <Button variant="secondary" onClick={() => setSelectedRunId(run.id)}>{runTitle(run)} · {formatUtcTimestamp(run.created_at)}</Button> }, { key: 'status', header: 'Status / progress', render: (run) => <Badge tone={tone(run.status)}>{humanizeResearchCode(run.status)}{run.progress === null || run.progress === undefined ? '' : ` · ${run.progress}%`}</Badge> }, { key: 'total', header: 'Terminal TOTAL', render: (run) => String((run.report?.summary as { terminal_total?: string } | undefined)?.terminal_total ?? run.report?.terminal_total ?? '—') }]} /></Card>
    <Card title="Verified historical evidence" actions={<Badge tone="neutral">Evidence</Badge>}><DataTable rows={catalog.map((item) => ({ ...item, id: item.id }))} emptyText="No catalog evidence." mobileTitle={(item) => item.title} columns={[{ key: 'evidence', header: 'Evidence', render: (item) => item.title }, { key: 'class', header: 'Class', render: (item) => <Badge tone={item.liquidations ? 'danger' : 'neutral'}>{humanizeResearchCode(item.classification)}</Badge> }, { key: 'total', header: 'TOTAL', render: (item) => item.settled_total }, { key: 'artifact', header: 'Artifact', render: (item) => humanizeResearchCode(item.artifact_state) }]} /></Card>
    {message ? <p className="muted">{message}</p> : null}
  </main>;
}

export function RuntimePage() {
  const [state, setState] = useState<HlStagegProjection | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [equityChanges, setEquityChanges] = useState<HlNativeEquityChanges | null>(null);
  const [fillHistory, setFillHistory] = useState<HlStagegFillHistory | null>(null);
  const [fillHistoryUnavailable, setFillHistoryUnavailable] = useState(false);
  const [fillHistoryHasMore, setFillHistoryHasMore] = useState(false);
  const load = () => void getHlStagegProjection().then((projection) => {
    setState(projection); setMessage('');
  }).catch((error: unknown) => {
    setState(null); setMessage(error instanceof Error ? error.message : 'Sandbox projection unavailable.');
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
  const entryGateMessage = state?.recovery_required === true
    ? 'New entries are blocked pending recovery'
    : state?.projection_state !== 'READY'
    ? 'Entry approval unavailable'
    : state.gates.attachable === false
      ? 'New Sandbox entries blocked'
      : state.gates.attachable !== true
        ? 'Entry approval unknown'
        : state.entry_control.state === 'PAUSED'
          ? 'New Sandbox entries paused'
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
    <Card className="trader-hero runtime-hero" title="Account overview" actions={<Badge tone={runtimeStatus.tone}>{loading && !state ? 'Loading' : humanizeResearchCode(runtimeStatus.label)}</Badge>}>
      <div className="runtime-hero__heading"><div><p className="trader-note">{entryGateMessage}.</p><p className="runtime-snapshot-time">Sandbox snapshot · {state?.observed_at_ns ? formatUtcTimestamp(new Date(state.observed_at_ns / 1_000_000).toISOString()) : 'time unavailable'}</p></div><Button variant="secondary" onClick={load}>Refresh</Button></div>
      <div className="runtime-account-grid runtime-account-grid--compact runtime-priority-grid">
        <Stat label="Equity" value={accountIsUnknown ? "Unavailable" : figures.find((figure) => figure.label === "Marked equity")?.value ?? "Unavailable"} />
        <Stat label="Available cash" value={accountIsUnknown ? "Unavailable" : figures.find((figure) => figure.label === "Available cash")?.value ?? "Unavailable"} />
        <Stat label={state?.recovery_required === true ? "Stored positions" : "Open positions"} value={positionSummary} />
        <Stat label={state?.recovery_required === true ? "Stored orders" : "Working orders"} value={projectionReady ? String(orderRows.length) : "Unavailable"} />
      </div>
      {accountIsUnknown ? null : <details className="nautilus-diagnostics runtime-account-details"><summary>Margin, P&amp;L and account details</summary>
        <div className="runtime-account-secondary" aria-label="Current margin and profit and loss">
          <Stat label="Initial margin" value={state?.account.im ?? "Unavailable"} />
          <Stat label="Maintenance margin" value={state?.account.mm ?? "Unavailable"} />
          <Stat label="Realized P&amp;L · net fees" value={figures.find((figure) => figure.label === "Realized PnL after fees")?.value ?? "Unavailable"} />
          <Stat label="Unrealized P&amp;L" value={figures.find((figure) => figure.label === "Unrealized PnL")?.value ?? "Unavailable"} />
        </div>
        <div className="runtime-account-grid runtime-account-grid--compact runtime-account-details__other">{figures.filter((figure) => !["Marked equity", "Available cash", "Realized PnL after fees", "Unrealized PnL"].includes(figure.label)).map((figure) => <Stat key={figure.label} label={figure.label} value={figure.value} />)}</div>
      </details>}
      {accountIsUnknown ? <div className="runtime-empty-note account-unavailable"><strong>Account valuation unavailable</strong><span>{runtimeStatus.detail}</span></div> : null}
      {state?.account.mark_state === 'STALE_OR_MISSING' ? <p className="runtime-empty-note">Mark is stale or missing. Marked equity and unrealized P&amp;L are not current.</p> : null}
      {state?.account.status === 'PARTIAL' ? <p className="runtime-empty-note">Account read is partial. Missing account fields remain unavailable.</p> : null}
    </Card>
    <DashboardMarketChart projection={state} history={fillHistoryMatchesRun ? fillHistory : null} equity={equityChanges} />
    <section className="trader-market-grid" aria-label="BTC and SOL Markets">
      {TRADER_MARKETS.map(({ symbol, instrumentId }) => {
        const feed = state?.feeds[instrumentId];
        const fresh = feed?.state === 'READY' && feed.mark_age_ns != null && feed.mark_age_ns >= 0 && feed.mark_age_ns <= 15_000_000_000;
        const position = positionPresentation(state, instrumentId);
        const linkedOrders = orderRows.filter((order) => order.instrument_id === instrumentId);
        return <Card key={instrumentId} className="trader-market-card" title={symbol} actions={<Badge tone={fresh ? 'success' : 'danger'}>{fresh ? 'Live' : feed?.state === 'READY' ? 'Stale' : humanizeResearchCode(feed?.state ?? 'UNAVAILABLE')}</Badge>}>
          <div className="trader-market-price">
            <span>{fresh ? 'Mark' : 'Previous mark'}</span>
            <strong>{feed?.mark ?? 'Unavailable'}</strong>
            <small>{fresh ? `Mark age ${age(feed?.mark_age_ns)}` : feed?.mark ? `Stale · ${age(feed.mark_age_ns)}` : 'Mark unavailable'}</small>
          </div>
          <div className="trader-market-exposure">
            <div className="trader-market-exposure__heading"><span>Sandbox position</span><Badge tone={position.state === 'OPEN' ? 'success' : position.state === 'FLAT' ? 'neutral' : 'danger'}>{position.state === 'OPEN' ? 'Open' : position.state === 'FLAT' ? 'Flat' : 'Unconfirmed'}</Badge></div>
            {position.state === 'OPEN' ? <div className="trader-market-exposure__value"><strong className={position.side === 'LONG' ? 'up' : 'down'}>{position.side}</strong><span>{position.quantity}</span></div> : position.state === 'FLAT' ? <p>Confirmed flat · 0 position size</p> : <p>Position state unavailable until native recovery is confirmed.</p>}
          </div>
          <div className="trader-market-orders">
            <div className="trader-market-orders__heading"><span>{state?.recovery_required ? 'Stored orders' : 'Working orders'}</span><span>{state?.projection_state === 'READY' ? linkedOrders.length : 'Unavailable'}</span></div>
            {linkedOrders.length ? linkedOrders.map((order) => <div className="trader-market-order" key={order.client_order_id}>
              <span>{order.reduce_only === true ? 'Reduce-only' : 'Working order'}{order.side ? ` · ${order.side}` : ''}</span>
              <strong>{order.price ?? 'Price unavailable'}</strong>
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
    <Card title="Recent trades">
      {!fillHistoryMatchesRun
        ? <p className="runtime-empty-note">{fillHistoryUnavailable ? 'Detailed fill history is unavailable.' : !state?.run_epoch ? 'Fill history is hidden until the current workspace is confirmed.' : 'History is refreshing after restart; earlier rows are hidden.'}</p>
        : !fillHistory?.detail_store_available
        ? <p className="runtime-empty-note">{unavailableTradeHistoryLabel(fillHistory?.historical_id_only_count)}</p>
        : <>
          {fillHistory.historical_id_only_count > 0 ? <p className="muted">{fillHistory.historical_id_only_count} older execution record{fillHistory.historical_id_only_count === 1 ? ' has' : 's have'} no saved trade details.</p> : null}
          <DataTable rows={fillHistory.fills.map((fill) => ({ ...fill, id: String(fill.cursor) }))} emptyText="No detailed executions recorded yet." mobileTitle={(fill) => `${fill.instrument_id.startsWith('BTC-') ? 'BTC' : fill.instrument_id.startsWith('SOL-') ? 'SOL' : 'Other market'} · ${nativeFillActionLabel(fill.action)}`} mobileSubtitle={(fill) => (fill.order_side ?? 'Side unavailable') + ' · ' + fill.quantity + ' @ ' + fill.price} columns={[
            { key: 'action', header: 'Type', render: (fill) => nativeFillActionLabel(fill.action) },
            { key: 'time', header: 'Time (UTC)', render: (fill) => fill.ts_event_ns == null ? 'Unavailable' : formatUtcTimestamp(new Date(fill.ts_event_ns / 1000000).toISOString()) },
            { key: 'market', header: 'Market', render: (fill) => fill.instrument_id.startsWith('BTC-') ? 'BTC' : fill.instrument_id.startsWith('SOL-') ? 'SOL' : 'Other market' },
            { key: 'side', header: 'Side', render: (fill) => fill.order_side ?? 'Unavailable' },
            { key: 'quantity', header: 'Quantity', render: (fill) => fill.quantity },
            { key: 'price', header: 'Price', render: (fill) => fill.price },
            { key: 'fee', header: 'Fee', render: (fill) => fill.commission_amount == null ? 'Unavailable' : (fill.commission_amount + ' ' + (fill.commission_currency ?? '')).trim() },
          ]} />
          {fillHistoryHasMore ? <Button variant="secondary" onClick={loadMoreFills}>Load more fills</Button> : null}
        </>}
    </Card>
    <Card title="Drawdown protection" actions={<Badge tone={protectionArmed ? "success" : "danger"}>{protectionArmed ? "Protected" : state?.recovery_required ? "Unverified" : protectionVerified ? "Stale" : "Not set"}</Badge>}>
      {protectionFresh ? <><p className="trader-note">Maximum drawdown limit: <strong>{String(protection?.drawdown_limit_percent)}%</strong></p><details className="nautilus-diagnostics"><summary>Protection basis and sample time</summary><div className="runtime-account-grid runtime-account-grid--compact"><Stat label="Protection equity" value={protection?.equity ?? "Unavailable"} /><Stat label="High-water equity" value={protection?.high_water_equity ?? "Unavailable"} /><Stat label="Threshold" value={protection?.threshold_equity ?? "Unavailable"} /><Stat label="Last daily close" value={formatUtcTimestamp(protection?.last_daily_close_utc)} /><Stat label="Observed" value={protection?.observed_at_ns ? formatUtcTimestamp(new Date(protection.observed_at_ns / 1_000_000).toISOString()) : "Unavailable"} /></div></details></> : <p className="runtime-empty-note">{state?.recovery_required ? "Protection baseline is unverified while recovery is required. Displayed values are withheld until the native account is recovered." : protectionVerified ? "Protection read is stale. Values are withheld until a fresh worker read is available." : "Protection is not armed."}</p>}
    </Card>
    {state?.warnings.length ? <div className="runtime-warning-list" role="status"><strong>Worker notice</strong><ul>{state.warnings.map((warning, index) => <li key={index}>{humanizeBlocker(warning)}</li>)}</ul></div> : null}

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
  }
  useEffect(() => { void refresh(); }, []);
  const protection = state?.deposit_protection;
  const pausedAndFlat = state?.projection_state === 'READY'
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
      await refresh();
      if (result.status !== 'APPLIED' || result.deposit_protection.drawdown_limit_percent !== percent) throw new Error('Deposit protection read-back mismatch.');
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
      await refresh();
      if (result.status !== 'APPLIED') throw new Error('Deposit protection reset was not confirmed.');
      setMessage('New baseline applied and read back. The worker remains paused.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Deposit protection reset failed.'); }
    finally { setCommandInFlight(null); }
  }
  async function commandEntries(command: 'pause-new-entries' | 'resume-new-entries') {
    if (commandInFlight) return;
    setCommandInFlight(command); setMessage('Updating entry controls…');
    try {
      const result = await commandHlStagegEntries(command, crypto.randomUUID());
      await refresh();
      setMessage(`${result.command === 'pause-new-entries' ? 'New entries paused' : 'New entries resumed'} (${result.status.toLowerCase()} and read back).`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Entry control update failed.'); }
    finally { setCommandInFlight(null); }
  }
  return <main className="terminal-layout">
    <Card title="Sandbox connection" actions={<Badge tone={state?.projection_state === 'READY' ? 'success' : 'danger'}>{loading ? 'Connecting' : state?.projection_state === 'READY' ? 'Connected' : state?.projection_state === 'STALE' ? 'Stale' : 'Unavailable'}</Badge>}>
      <p className="muted">Order routing is off. Funding is observed for reference and is not credited to Sandbox cash. {fundingLabel(state)}.</p>
      <Button variant="secondary" onClick={() => void refresh()}>Refresh status</Button>
    </Card>
    <SettingsConnections />
    <Card title="Drawdown protection" actions={<Badge tone={protectionFresh ? "success" : "danger"}>{protectionFresh ? "Protected" : state?.recovery_required ? "Unverified" : protectionVerified ? "Stale" : "Not set"}</Badge>}>
      {state?.recovery_required ? <p className="runtime-empty-note">Recovery is required. Protection values are withheld and settings remain read-only until account ownership is restored.</p> : <>
      <p className="muted">Changes require a paused worker and confirmed flat exposure.</p>
      <div className="rules-form-grid">
        <label className="rules-field"><span>Allowed drawdown, %</span><input aria-label="Allowed drawdown, %" type="number" min={1} max={99} step={1} value={protectionDraft} onChange={(event) => setProtectionDraft(event.target.value)} /></label>
        <div className="rules-btn-group rules-btn-group--mb"><Button variant="secondary" disabled={!pausedAndFlat || !Number.isInteger(percent) || percent < 1 || percent > 99 || commandInFlight !== null} onClick={() => void saveProtection()}>{commandInFlight === 'set-deposit-protection' ? 'Saving…' : 'Save'}</Button><Button variant="danger" disabled={!pausedAndFlat || protection?.equity == null || commandInFlight !== null} onClick={() => void resetProtection()}>{commandInFlight === 'reset-deposit-protection' ? 'Resetting…' : 'Set new baseline'}</Button></div>
      </div>
      {protectionFresh ? <p className="muted">Protection is {protection?.state?.toLowerCase() ?? 'unavailable'} · Equity {protection?.equity ?? 'Unavailable'} · High-water {protection?.high_water_equity ?? 'Unavailable'} · Limit threshold {protection?.threshold_equity ?? 'Unavailable'}.</p> : <p className="runtime-empty-note">Protection values are stale or unverified and are withheld.</p>}
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
