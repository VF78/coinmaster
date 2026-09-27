import { useEffect, useState } from 'react';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';
import { cancelRun, commandHlStagegDepositProtection, commandHlStagegEntries, createRun, getConfigurations, getDefaultConfiguration, getHlStagegControls, getHlStagegFills, getHlStagegProjection, getHlStagegStrategy, getResearchCapabilities, getResearchCatalog, getRuns, saveConfiguration, type HlStagegControls, type HlStagegFillHistory, type HlStagegProjection, type HlStagegStrategy, type ResearchCapabilities, type ResearchCatalogEntry, type Run, type StrategyConfig, type StrategyConfiguration } from '../lib/nautilusApi';
import { accountFigures, dashboardState, fundingLabel, formatUtcTimestamp, protectionIsFresh, protectionIsVerified } from '../lib/accountPresentation';
import { appendSessionMarkSample, markSparklinePath, positionPresentation, TRADER_MARKETS, type MarkSample } from '../lib/traderPresentation';
import { controlAvailabilityLabel, humanizeBlocker, isAdvancedStrategySetting, strategySettingLabel, strategySettingValue } from '../lib/traderLabels';

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

function CsvNumberField({ label, value, onCommit }: { label: string; value: number[]; onCommit: (next: number[]) => void }) {
  const serialized = value.join(',');
  const [draft, setDraft] = useState(serialized);
  useEffect(() => setDraft(serialized), [serialized]);
  function commit() { const next = draft.split(',').map((part) => Number(part.trim())); if (next.length === 3 && next.every(Number.isFinite)) onCommit(next); }
  return <label className="rules-field"><span>{label} (CSV)</span><input value={draft} onChange={(event) => setDraft(event.target.value)} onBlur={commit} /></label>;
}

export function StrategyPage() {
  const [strategy, setStrategy] = useState<HlStagegStrategy | null>(null); const [config, setConfig] = useState<StrategyConfig | null>(null); const [drafts, setDrafts] = useState<StrategyConfiguration[]>([]); const [saved, setSaved] = useState<StrategyConfiguration | null>(null); const [message, setMessage] = useState(''); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false);
  async function load() { setLoading(true); setMessage(''); const [sealed, stored, template] = await Promise.allSettled([getHlStagegStrategy(), getConfigurations(), getDefaultConfiguration()]); if (sealed.status === 'fulfilled') setStrategy(sealed.value); if (stored.status === 'fulfilled') { setDrafts(stored.value); const selected = stored.value.find((item) => item.id === window.localStorage.getItem('coinmaster-selected-config')) ?? stored.value[0]; if (selected) { setSaved(selected); setConfig(selected.config); } } if (template.status === 'fulfilled') setConfig((current) => current ?? template.value.config); const failure = [sealed, stored, template].find((result) => result.status === 'rejected'); if (failure?.status === 'rejected') setMessage(failure.reason instanceof Error ? failure.reason.message : 'Unable to load the Strategy page.'); setLoading(false); }
  useEffect(() => { void load(); }, []);
  function updateNumber(key: NumberKey, value: string) { if (value !== '') setConfig((item) => item ? { ...item, [key]: Number(value) } : item); }
  function updateArray(key: ArrayKey, value: number[]) { setConfig((item) => item ? { ...item, [key]: value } : item); }
  async function save() { if (!config || saving) return; if (!Number.isFinite(Number(config.initial_total_usdt)) || Number(config.initial_total_usdt) <= 0) { setMessage('Research draft validation failed: initial total must be a positive number.'); return; } setSaving(true); setMessage('Saving research draft…'); try { const next = await saveConfiguration(config); const refreshed = await getConfigurations(); const persisted = refreshed.find((item) => item.id === next.id); if (!persisted) throw new Error('Saved draft could not be read back.'); setDrafts(refreshed); setSaved(persisted); setConfig(persisted.config); window.localStorage.setItem('coinmaster-selected-config', persisted.id); setMessage(`Research draft saved and read back: ${persisted.config_hash.slice(0, 12)}.`); } catch (error) { setMessage(error instanceof Error ? error.message : 'Research draft save failed.'); } finally { setSaving(false); } }
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
    <Card className="trader-hero strategy-hero" title={runningMatch ? 'Running strategy' : sourceChecked ? 'Sealed strategy' : 'Strategy source unavailable'} actions={<Badge tone={runningMatch ? 'success' : 'danger'}>{strategy?.running_state ?? (loading ? 'LOADING' : 'NOT_CONFIRMED')}</Badge>}>
      <p className="trader-hero__lead">{runningMatch ? 'The worker is running the sealed BTC / SOL strategy shown below.' : sourceChecked ? 'The sealed strategy was read successfully, but the worker match is not confirmed.' : 'The strategy source could not be confirmed. No running settings are implied.'}</p>
      <div className="stats-grid"><Stat label="Strategy" value={strategy?.strategy_id ?? 'Unavailable'} /><Stat label="Execution" value="Local Sandbox" /><Stat label="Market data" value="HL mainnet public" /><Stat label="Apply to dry run" value="Unavailable" /></div>
      <p className="trader-note">Running settings are read-only. A research draft never changes the active trader.</p>
    </Card>
    <section className="strategy-settings-grid">{strategyGroups.map(([group, rows]) => <Card className="strategy-settings-card" key={group} title={group} actions={<Badge tone="neutral">RUNNING</Badge>}><DataTable rows={rows} emptyText="No sealed settings available." mobileTitle={(row) => title(row.parameter)} columns={[{ key: 'parameter', header: 'Setting', render: (row) => title(row.parameter) }, { key: 'value', header: 'Running value', render: (row) => displaySetting(row.parameter, row.value) }]} /></Card>)}</section>
    {advancedRunningParameters.length ? <details className="nautilus-diagnostics"><summary>Advanced strategy rules</summary><DataTable rows={advancedRunningParameters} emptyText="No advanced rules." mobileTitle={(row) => title(row.parameter)} columns={[{ key: 'parameter', header: 'Rule', render: (row) => title(row.parameter) }, { key: 'value', header: 'Running value', render: (row) => displaySetting(row.parameter, row.value) }]} /></details> : null}
    <details className="nautilus-diagnostics"><summary>Strategy identity and account limits</summary><p className="muted">Candidate: {strategy?.hashes.candidate_sha256 ?? 'UNKNOWN'} · strategy: {strategy?.hashes.strategy_sha256 ?? 'UNKNOWN'} · policy: {strategy?.hashes.execution_policy_sha256 ?? 'UNKNOWN'}.</p><p className="muted">{strategy?.public_venue_profile ?? 'UNKNOWN'} Account margin: {strategy?.account_margin ?? 'UNKNOWN'} · account fee schedule: {strategy?.account_fee_schedule ?? 'UNKNOWN'} · funding: {strategy?.funding_treatment ?? 'UNKNOWN'}.</p></details>
    <Card className="trader-secondary-card" title="Strategy promotion" actions={<Badge tone="danger">UNAVAILABLE</Badge>}><p className="muted">The running strategy is read-only. Use Research for separate draft and backtest work.</p><Button variant="primary" disabled>Apply strategy</Button></Card>
    <details className="nautilus-diagnostics strategy-research-drafts"><summary>Research drafts / separate from running strategy</summary><Card className="research-drafts-card" title="Saved research draft">
      <p className="trader-hero__lead">Draft parameters are saved for research only. The running strategy above remains unchanged.</p>
      <label className="rules-field"><span>Read-back saved draft</span><select value={saved?.id ?? ''} onChange={(event) => { const next = drafts.find((item) => item.id === event.target.value) ?? null; setSaved(next); setConfig(next?.config ?? config); if (next) window.localStorage.setItem('coinmaster-selected-config', next.id); }}>{drafts.map((item) => <option key={item.id} value={item.id}>{item.config_hash.slice(0, 12)} · {item.created_at}</option>)}</select></label>
      <div className="nautilus-strategy-grid">
        <section className="nautilus-strategy-group"><h3>BTC sizing and exits</h3><p className="muted">Research draft; sealed running parameters stay above.</p><div className="rules-form-grid">
        {(['ema_period', 'btc_notional_multiplier', 'btc_close_trail_fraction'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <CsvNumberField label="BTC TP fractions / initial qty" value={config.btc_tp_fractions_initial_qty} onCommit={(next) => updateArray('btc_tp_fractions_initial_qty', next)} /> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>SOL sizing and exits</h3><p className="muted">Entry thresholds, add sizes and staged exits.</p><div className="rules-form-grid">
        {(['sol_exit_half_z', 'sol_exit_all_z', 'sol_max_holding_days'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <><CsvNumberField label="SOL multipliers H" value={config.sol_size_multipliers_H} onCommit={(next) => updateArray('sol_size_multipliers_H', next)} /><CsvNumberField label="SOL entry z" value={config.sol_entry_z} onCommit={(next) => updateArray('sol_entry_z', next)} /></> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>Signal windows</h3><p className="muted">Feature history and wave thresholds.</p><div className="rules-form-grid">
        {(['beta_days', 'relative_days', 'z_history_days', 'wave_history_days', 'wave_min_count'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        {config ? <><CsvNumberField label="Wave quantiles" value={config.wave_quantiles} onCommit={(next) => updateArray('wave_quantiles', next)} /></> : null}
        </div></section>
        <section className="nautilus-strategy-group"><h3>Capital and constraints</h3><p className="muted">Fixed v0 controls are visible but cannot be edited.</p><div className="rules-form-grid">
        <label className="rules-field"><span>Initial TOTAL (template constraint)</span><input disabled value={config?.initial_total_usdt ?? ''} /></label>
        <label className="rules-field"><span>Initial active fraction (template constraint)</span><input disabled type="number" value={String(config?.initial_active_fraction ?? '')} /></label>
        <label className="rules-field"><span>Research venue label only</span><select value={config?.venue ?? ''} onChange={(event) => setConfig((item) => item ? { ...item, venue: (event.target.value || null) as StrategyConfig['venue'] } : item)}><option value="">Unselected</option><option value="bybit">Bybit</option><option value="hyperliquid">Hyperliquid</option></select></label>
        {(['max_gross_to_active'] as const).map((key) => <label className="rules-field" key={key}><span>{title(key)}</span><input type="number" value={String(config?.[key] ?? '')} onChange={(event) => updateNumber(key, event.target.value)} /></label>)}
        <label className="rules-field"><span>Maximum parent order notional</span><input value={config?.max_parent_notional ?? ''} onChange={(event) => setConfig((item) => item ? { ...item, max_parent_notional: event.target.value } : item)} /></label>
        <label className="rules-field"><span>Include zero waves (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.include_zero_waves)} /></label>
        <label className="rules-field"><span>Freeze sigma on first SOL fill (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.freeze_sigma_on_first_sol_fill)} /></label>
        <label className="rules-field"><span>Insufficient margin (v0 fixed)</span><select disabled value={config?.insufficient_margin ?? 'reject'}><option value="reject">reject</option></select></label>
        </div></section>
      </div>
      <p className="muted">Template constraints remain fixed until a separately scoped native implementation. Server validation is authoritative for research-draft saves.</p>
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!config || saving} onClick={() => void save()}>{saving ? 'Saving…' : 'Save research draft'}</Button>{saved ? <Badge tone="success">{saved.config_hash.slice(0, 12)}</Badge> : null}</div>{message ? <p className="muted">{message}</p> : null}
    </Card></details>
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
  const activeRun = runs.find((item) => ['STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'QUEUED'].includes(item.status));
  const terminalTotal = selectedRun?.report?.summary && typeof selectedRun.report.summary === 'object'
    ? (selectedRun.report.summary as { terminal_total?: string }).terminal_total
    : selectedRun?.report?.terminal_total;
  const baselineReady = capabilities?.baseline_state === 'READY';
  const optimizerReady = capabilities?.optimizer_state === 'READY';
  const optimizerSearch = capabilities?.optimizer_search as { axis: string; values: string[]; max_variants: number; source_candidate_sha256: string } | undefined;
  const top20 = Array.isArray(selectedRun?.report?.top20) ? selectedRun.report.top20 as { candidate_id: string; candidate_sha256: string; terminal_active: string; terminal_reserve: string; terminal_total: string; roi: string; drawdown_percent: string; liquidations: number; maker_fees: string; taker_fees: string; funding: { count?: number; signed_amount?: string }; fills: number; limitations: string[]; artifact_sha256: string; classification: string }[] : [];
  return <main className="terminal-layout nautilus-research-workspace">
    <Card className="trader-hero research-hero" title="Research workspace" actions={<Badge tone={baselineReady ? 'success' : 'danger'}>{capabilities?.baseline_state ?? (loading ? 'LOADING' : 'BLOCKED')}</Badge>}>
      <p className="trader-hero__lead">Run a bounded historical calculation against an immutable saved configuration. Results are research evidence and never change the running trader.</p>
      <div className="rules-form-grid">
        <label className="rules-field"><span>Immutable configuration</span><select value={config?.id ?? ''} onChange={(event) => { const next = configs.find((item) => item.id === event.target.value) ?? null; setConfig(next); setCapabilities(null); if (next) { window.localStorage.setItem('coinmaster-selected-config', next.id); void getResearchCapabilities(next.id).then(setCapabilities).catch((error: Error) => setMessage(error.message)); } }}>{configs.map((item) => <option key={item.id} value={item.id}>{item.config_hash.slice(0, 12)} · {item.created_at}</option>)}</select></label>
        <label className="rules-field"><span>Start date</span><input disabled value={capabilities?.baseline_start ? formatUtcTimestamp(capabilities.baseline_start) : 'Unavailable'} /></label>
        <label className="rules-field"><span>End date (exclusive)</span><input disabled value={capabilities?.baseline_end_exclusive ? formatUtcTimestamp(capabilities.baseline_end_exclusive) : 'Unavailable'} /></label>
        <label className="rules-field"><span>Ranking objective</span><input disabled value={capabilities?.baseline_objective ?? 'TOTAL only'} /></label>
      </div>
      <p className="muted">The period is fixed by the verified native baseline contract. Its child validates the immutable configuration and 1m coverage again before work begins.</p>
      {capabilities?.baseline_blockers.length ? <><p className="muted">Baseline blocked: {capabilities.baseline_blockers.map(humanizeBlocker).join(' ')}</p><details className="nautilus-diagnostics"><summary>Technical blocker codes</summary><p className="muted">{capabilities.baseline_blockers.join(' · ')}</p></details></> : null}
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!baselineReady || starting || Boolean(activeRun)} onClick={() => void startBaseline()}>{starting ? 'Starting…' : activeRun ? 'Native job running…' : 'Run verified native baseline'}</Button><Button variant="secondary" onClick={() => void load()}>Refresh status</Button></div>
    </Card>
    <Card className="research-action-card" title="Bounded parameter search" actions={<Badge tone={optimizerReady ? 'success' : 'danger'}>{optimizerReady ? 'READY' : capabilities?.optimizer_state ?? 'BLOCKED'}</Badge>}>
      <p className="muted">One axis: {optimizerSearch?.axis ?? 'BTC size'} = {optimizerSearch?.values.join(', ') ?? '—'} · up to {optimizerSearch?.max_variants ?? '—'} native variants · rank by terminal TOTAL. Research evidence only.</p>
      <details className="nautilus-diagnostics"><summary>Source and manifest identity</summary><p className="muted">Sealed Stage-G source {optimizerSearch?.source_candidate_sha256 ?? 'UNKNOWN'} · verified 1m manifest {capabilities?.optimizer_source_manifest_sha256 ?? 'UNKNOWN'}.</p></details>
      {capabilities?.optimizer_blockers.length ? <><p className="muted">Research is blocked: {capabilities.optimizer_blockers.map(humanizeBlocker).join(' ')}</p><details className="nautilus-diagnostics"><summary>Technical blocker codes</summary><p className="muted">{capabilities.optimizer_blockers.join(' · ')}</p></details></> : null}
      <Button variant="primary" disabled={!optimizerReady || !config || starting || Boolean(activeRun)} onClick={() => void startOptimizer()}>{starting ? 'Starting…' : activeRun ? 'Worker busy…' : 'Optimize TOTAL only'}</Button>
    </Card>
    <Card className="research-result-card" title="Selected result" actions={<Badge tone={selectedRun ? tone(selectedRun.status) : 'neutral'}>{selectedRun ? `${selectedRun.status}${selectedRun.progress === null || selectedRun.progress === undefined ? '' : ` · ${selectedRun.progress}%`}` : 'NO RUN SELECTED'}</Badge>}>
      <p className="muted">{activeRun ? `Active native job ${activeRun.id.slice(0, 8)} updates every three seconds.` : 'Choose a run from history to inspect its compact result.'}</p>
      <div className="stats-grid"><Stat label="Terminal TOTAL" value={String(terminalTotal ?? '—')} /><Stat label="Active" value={String(selectedRun?.report?.terminal_active ?? '—')} /><Stat label="Reserve" value={String(selectedRun?.report?.terminal_reserve ?? '—')} /><Stat label="ROI" value={String((selectedRun?.report?.summary as { roi?: string } | undefined)?.roi ?? '—')} /><Stat label="Max drawdown" value={String((selectedRun?.report?.summary as { max_drawdown_percent?: string } | undefined)?.max_drawdown_percent ?? '—')} /><Stat label="Native fills" value={String(selectedRun?.report?.fills ?? '—')} /></div>
      <p className="muted">Classification: {String(selectedRun?.report?.status ?? '—')} · fees: {String(selectedRun?.report?.native_fees ?? '—')} · liquidations: {String(selectedRun?.report?.liquidation_count ?? '—')}. Diagnostic results are not live rankings.</p>
      {selectedRun?.evidence.length ? <><p className="muted">Job evidence: {selectedRun.evidence.map(humanizeBlocker).join(' ')}</p><details className="nautilus-diagnostics"><summary>Technical evidence codes</summary><p className="muted">{selectedRun.evidence.join(' · ')}</p></details></> : null}
      {selectedRun?.command_name === 'native_optimizer' ? <details className="nautilus-diagnostics"><summary>Research artifact identity</summary><p className="muted">Request {selectedRun.request_hash ?? 'UNKNOWN'} · config {selectedRun.report?.request_config_hash?.toString() ?? 'UNKNOWN'} · result {selectedRun.report?.artifact_sha256?.toString() ?? 'UNKNOWN'} · classification {selectedRun.report?.status?.toString() ?? 'UNKNOWN'}.</p></details> : null}
      {top20.length ? <><h3 className="nautilus-subheading">TOP {top20.length} · terminal TOTAL comparison</h3><DataTable rows={top20.map((row) => ({ ...row, id: row.candidate_id }))} emptyText="No ranked candidates." mobileTitle={(row) => row.candidate_id} columns={[{ key: 'candidate', header: 'Candidate', render: (row) => row.candidate_id }, { key: 'total', header: 'TOTAL / ACTIVE / RESERVE', render: (row) => `${row.terminal_total} / ${row.terminal_active} / ${row.terminal_reserve}` }, { key: 'risk', header: 'ROI / DD / liq', render: (row) => `${row.roi} / ${row.drawdown_percent} / ${row.liquidations}` }, { key: 'costs', header: 'Fills / maker / taker / funding', render: (row) => `${row.fills} / ${row.maker_fees} / ${row.taker_fees} / ${row.funding?.signed_amount ?? '—'}` }, { key: 'proof', header: 'Classification / limits', render: (row) => `${row.classification} · ${row.limitations.join('; ')}` }]} /></> : <p className="muted">No TOP-20 comparison for this run. A completed optimizer publishes candidates here.</p>}
      {selectedRun && ['STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'QUEUED'].includes(selectedRun.status) ? <Button variant="danger" disabled={Boolean(cancellingId)} onClick={() => void cancelOwned(selectedRun.id)}>{cancellingId === selectedRun.id ? 'Cancelling…' : 'Cancel owned job'}</Button> : null}
      <p className="muted">The page displays compact status and result fields only; job artifacts remain hash-checked private evidence.</p>
    </Card>
    <Card title="Run history · select to compare" actions={<Badge tone="neutral">TOTAL ONLY</Badge>}><DataTable rows={runs.map((run) => ({ ...run, id: run.id }))} emptyText="No native research jobs yet." mobileTitle={(run) => `${run.command_name ?? run.kind} · ${run.id.slice(0, 8)}`} columns={[{ key: 'run', header: 'Run', render: (run) => <Button variant="secondary" onClick={() => setSelectedRunId(run.id)}>{run.command_name ?? run.kind} · {run.id.slice(0, 8)}</Button> }, { key: 'status', header: 'Status / progress', render: (run) => <Badge tone={tone(run.status)}>{run.status}{run.progress === null || run.progress === undefined ? '' : ` · ${run.progress}%`}</Badge> }, { key: 'total', header: 'Terminal TOTAL', render: (run) => String((run.report?.summary as { terminal_total?: string } | undefined)?.terminal_total ?? run.report?.terminal_total ?? '—') }]} /></Card>
    <Card title="Verified historical evidence" actions={<Badge tone="neutral">READ ONLY</Badge>}><p className="muted">Diagnostic evidence remains separate from native job history. It never substitutes for a newly launched calculation.</p><DataTable rows={catalog.map((item) => ({ ...item, id: item.id }))} emptyText="No catalog evidence." mobileTitle={(item) => item.title} columns={[{ key: 'evidence', header: 'Evidence', render: (item) => item.title }, { key: 'class', header: 'Class', render: (item) => <Badge tone={item.liquidations ? 'danger' : 'neutral'}>{item.classification}</Badge> }, { key: 'total', header: 'TOTAL', render: (item) => item.settled_total }, { key: 'artifact', header: 'Artifact', render: (item) => item.artifact_state }]} /></Card>
    {message ? <p className="muted">{message}</p> : null}
  </main>;
}

export function RuntimePage() {
  const [state, setState] = useState<HlStagegProjection | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sessionMarks, setSessionMarks] = useState<Record<string, MarkSample[]>>({});
  const [fillHistory, setFillHistory] = useState<HlStagegFillHistory | null>(null);
  const [fillHistoryUnavailable, setFillHistoryUnavailable] = useState(false);
  const [fillHistoryHasMore, setFillHistoryHasMore] = useState(false);
  const load = () => void getHlStagegProjection().then((projection) => {
    setState(projection); setMessage('');
  }).catch((error: unknown) => {
    setState(null); setMessage(error instanceof Error ? error.message : 'Sandbox projection unavailable.');
  }).finally(() => setLoading(false));
  useEffect(() => { load(); const timer = window.setInterval(load, 5000); return () => window.clearInterval(timer); }, []);
  useEffect(() => {
    let active = true;
    const refreshFills = () => void getHlStagegFills(0, 100).then((data) => {
      if (active) {
        setFillHistory((current) => {
          const retained = current?.fills.filter((fill) => fill.cursor > data.next_cursor) ?? [];
          return { ...data, fills: [...data.fills, ...retained], next_cursor: Math.max(data.next_cursor, current?.next_cursor ?? 0) };
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
    if (!fillHistory || !fillHistoryHasMore) return;
    void getHlStagegFills(fillHistory.next_cursor, 100).then((data) => {
      setFillHistory((current) => current ? {
        ...current, fills: [...current.fills, ...data.fills],
        next_cursor: Math.max(current.next_cursor, data.next_cursor),
        historical_id_only_count: data.historical_id_only_count,
      } : data);
      setFillHistoryHasMore(data.fills.length === 100);
    }).catch(() => setFillHistoryUnavailable(true));
  };
  useEffect(() => {
    setSessionMarks((current) => Object.fromEntries(TRADER_MARKETS.map(({ instrumentId }) => [
      instrumentId, appendSessionMarkSample(current[instrumentId] ?? [], state, instrumentId),
    ])));
  }, [state]);
  const runtimeStatus = dashboardState(state);
  const runtimeHealthy = state?.projection_state === 'READY' && state?.recovery_required !== true && state.process_state !== 'DATA_STALE/PAUSED' && state.process_state !== 'WORKER_DISCONNECTED';
  const entryGateMessage = state?.recovery_required === true
    ? 'New entries are blocked pending recovery'
    : state?.projection_state !== 'READY'
    ? 'Native entry gate unavailable'
    : state.gates.attachable === false
      ? 'Native entry gate closed; new Sandbox entries are blocked'
      : state.gates.attachable !== true
        ? 'Native entry gate unknown'
        : state.entry_control.state === 'PAUSED'
          ? 'New Sandbox entries paused'
          : runtimeHealthy
            ? 'Native entry gate ready; awaiting a strategy decision'
            : 'New Sandbox entries blocked while process or feeds are unhealthy';
  const eventRows = (state?.events ?? []).map((event) => ({ ...event, id: `${event.cursor}:${event.event_id}` }));
  const positionRows = (state?.positions ?? []).map((position) => ({ ...position, id: position.instrument_id, mark: state?.feeds[position.instrument_id]?.mark ?? null }));
  const orderRows = (state?.orders ?? []).map((order) => ({ ...order, id: order.client_order_id }));
  const age = (value: number | null | undefined) => value === null || value === undefined ? 'UNKNOWN' : `${(value / 1_000_000_000).toFixed(1)}s`;
  const projectionReady = state?.projection_state === 'READY';
  const accountIsUnknown = !projectionReady || state.account.status === 'UNAVAILABLE' || state.recovery_required === true;
  const figures = accountIsUnknown ? [] : accountFigures(state);
  const activeExposure = runtimeStatus.exposure;
  const protection = state?.deposit_protection;
  const protectionVerified = protectionIsVerified(state);
  const protectionFresh = protectionIsFresh(state);
  const protectionArmed = protectionFresh && protection?.state === 'ARMED';
  return <main className="terminal-layout nautilus-runtime-workspace">
    <Card className="trader-hero runtime-hero" title="Account overview" actions={<Badge tone={runtimeStatus.tone}>{loading && !state ? "LOADING" : runtimeStatus.label}</Badge>}>
      <div className="runtime-hero__heading"><div><p className="trader-hero__lead">Local Sandbox execution for BTC and SOL. Live orders are disabled.</p><p className="trader-note">{entryGateMessage}. Live orders are disabled.</p></div><Button variant="secondary" onClick={load}>Refresh</Button></div>
      <div className="runtime-account-grid runtime-account-grid--compact">
        {figures.map((figure) => <Stat key={figure.label} label={figure.label} value={figure.value} />)}
        <Stat label="Open exposure" value={activeExposure} />
        <Stat label={state?.recovery_required === true ? "Stored orders" : "Working orders"} value={projectionReady ? String(orderRows.length) : "Unavailable"} />
      </div>
      {accountIsUnknown ? <div className="runtime-empty-note account-unavailable"><strong>Account valuation unavailable</strong><span>{runtimeStatus.detail}</span></div> : null}
      {state?.account.mark_state === 'STALE_OR_MISSING' ? <p className="runtime-empty-note">Mark is STALE_OR_MISSING. Marked equity and unrealized PnL are stale and are not presented as current.</p> : null}
      {state?.account.status === 'PARTIAL' ? <p className="runtime-empty-note">Account read is PARTIAL. Missing native fields remain UNKNOWN.</p> : null}
    </Card>
    <Card title="Drawdown protection" actions={<Badge tone={protectionArmed ? "success" : "danger"}>{protectionArmed ? "ARMED" : state?.recovery_required ? "UNVERIFIED" : protection?.state ?? "NOT ARMED"}</Badge>}>
      {protectionFresh ? <div className="runtime-account-grid"><Stat label="Drawdown limit" value={String(protection?.drawdown_limit_percent) + "%"} /><Stat label="Equity" value={protection?.equity ?? "Unavailable"} /><Stat label="High-water" value={protection?.high_water_equity ?? "Unavailable"} /><Stat label="Threshold" value={protection?.threshold_equity ?? "Unavailable"} /><Stat label="Daily close" value={formatUtcTimestamp(protection?.last_daily_close_utc)} /><Stat label="Observed" value={protection?.observed_at_ns ? formatUtcTimestamp(new Date(protection.observed_at_ns / 1_000_000).toISOString()) : "Unavailable"} /></div> : <p className="runtime-empty-note">{state?.recovery_required ? "Protection baseline is unverified while recovery is required. Displayed values are withheld until the native account is recovered." : protectionVerified ? "Protection read is stale. Values are withheld until a fresh worker read is available." : "Protection is not armed."}</p>}
    </Card>
    <section className="trader-market-grid" aria-label="BTC and SOL Markets">
      {TRADER_MARKETS.map(({ symbol, instrumentId }) => {
        const feed = state?.feeds[instrumentId];
        const fresh = feed?.state === 'READY' && feed.mark_age_ns != null && feed.mark_age_ns >= 0 && feed.mark_age_ns <= 15_000_000_000;
        const marks = sessionMarks[instrumentId] ?? [];
        const path = markSparklinePath(marks);
        const position = positionPresentation(state, instrumentId);
        const linkedOrders = orderRows.filter((order) => order.instrument_id === instrumentId);
        return <Card key={instrumentId} className="trader-market-card" title={symbol} actions={<Badge tone={fresh ? 'success' : 'danger'}>{fresh ? 'FEED READY' : feed?.state ?? 'FEED UNKNOWN'}</Badge>}>
          <div className="trader-market-price">
            <span>{fresh ? 'MARK' : 'LAST MARK'}</span>
            <strong>{feed?.mark ?? 'UNKNOWN'}</strong>
            <small>{fresh ? `Mark age ${age(feed?.mark_age_ns)}` : feed?.mark ? `Stale · ${age(feed.mark_age_ns)}` : 'Mark unavailable'}</small>
          </div>
          <div className="trader-session-chart">
            <div className="trader-session-chart__heading"><span>Browser-session mark samples</span><span>{marks.length ? `${marks.length} samples` : 'No samples'}</span></div>
            {path ? <svg viewBox="0 0 240 52" preserveAspectRatio="none" role="img" aria-label={`${symbol} browser-session mark samples`}><path d={path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg> : <p>{fresh ? 'Gathering a second fresh mark sample…' : 'Samples cleared while the mark feed is stale or unavailable.'}</p>}
            {marks.length > 1 ? <div className="trader-session-chart__range"><span>{new Date(marks[0].observedAtNs / 1_000_000).toLocaleTimeString()}</span><span>{new Date(marks.at(-1)!.observedAtNs / 1_000_000).toLocaleTimeString()}</span></div> : null}
          </div>
          <div className="trader-market-exposure">
            <div className="trader-market-exposure__heading"><span>Sandbox position</span><Badge tone={position.state === 'OPEN' ? 'success' : position.state === 'FLAT' ? 'neutral' : 'danger'}>{position.state}</Badge></div>
            {position.state === 'OPEN' ? <div className="trader-market-exposure__value"><strong className={position.side === 'LONG' ? 'up' : 'down'}>{position.side}</strong><span>{position.quantity}</span></div> : position.state === 'FLAT' ? <p>Confirmed flat · 0 position size</p> : <p>Position state unavailable until native recovery is confirmed.</p>}
          </div>
          <div className="trader-market-orders">
            <div className="trader-market-orders__heading"><span>{state?.recovery_required ? 'Stored orders' : 'Working orders'}</span><span>{state?.projection_state === 'READY' ? linkedOrders.length : 'UNKNOWN'}</span></div>
            {linkedOrders.length ? linkedOrders.map((order) => <div className="trader-market-order" key={order.client_order_id}>
              <span>{order.reduce_only === true ? 'REDUCE ONLY' : 'WORKING ORDER'}{order.side ? ` · ${order.side}` : ''}</span>
              <strong>{order.price ?? 'Price unavailable'}</strong>
              <small>{order.status ?? 'Status unavailable'} · {order.order_type ?? 'Type unavailable'} · leaves {order.leaves_quantity ?? order.quantity ?? 'Unavailable'}</small>
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
      return <Card title="Other stored exposure" actions={<Badge tone="danger">REVIEW</Badge>}>
        <DataTable rows={otherPositions.map((row) => ({ ...row, id: row.instrument_id }))} emptyText="No additional position rows." mobileTitle={(row) => row.instrument_id} columns={[{ key: 'instrument', header: 'Market', render: (row) => row.instrument_id }, { key: 'quantity', header: 'Position size', render: (row) => row.signed_quantity }, { key: 'mark', header: 'Reference mark', render: (row) => row.mark ?? 'UNKNOWN' }]} />
        <DataTable rows={otherOrders} emptyText="No additional order rows." mobileTitle={(row) => row.instrument_id ?? row.client_order_id} mobileSubtitle={(row) => row.status ?? 'Status unavailable'} columns={[{ key: 'instrument', header: 'Market', render: (row) => row.instrument_id ?? 'UNKNOWN' }, { key: 'order', header: 'Order', render: (row) => row.reduce_only === true ? 'Reduce only' : 'Working order' }, { key: 'status', header: 'Status', render: (row) => row.status ?? 'Unavailable' }, { key: 'price', header: 'Price', render: (row) => row.price ?? 'Unavailable' }, { key: 'leaves', header: 'Leaves', render: (row) => row.leaves_quantity ?? row.quantity ?? 'Unavailable' }]} />
      </Card>;
    })()}
    <Card title="Native fill history" actions={<Badge tone="neutral">READ ONLY</Badge>}>
      <p className="muted">Exact native fills recorded by the Stage-G journal. Fees and identifiers are shown only when present; no trade PnL or reconstructed round trips are inferred.</p>
      {fillHistoryUnavailable || !fillHistory?.detail_store_available
        ? <p className="runtime-empty-note">Fill details are unavailable from this worker journal. {fillHistory?.historical_id_only_count != null ? fillHistory.historical_id_only_count + ' historical fill event' + (fillHistory.historical_id_only_count === 1 ? ' has' : 's have') + ' IDs only; prices and quantities were not retained.' : 'History availability is unknown.'}</p>
        : <>
          {fillHistory.historical_id_only_count > 0 ? <p className="muted">{fillHistory.historical_id_only_count} older fill event{fillHistory.historical_id_only_count === 1 ? ' has' : 's have'} IDs only. Their trade details are unavailable and were not reconstructed.</p> : null}
          <DataTable rows={fillHistory.fills.map((fill) => ({ ...fill, id: String(fill.cursor) }))} emptyText="No detailed native fills recorded yet." mobileTitle={(fill) => fill.instrument_id} mobileSubtitle={(fill) => (fill.order_side ?? 'Side unavailable') + ' · ' + fill.quantity + ' @ ' + fill.price} columns={[
            { key: 'time', header: 'Time (UTC)', render: (fill) => fill.ts_event_ns == null ? 'Unavailable' : formatUtcTimestamp(new Date(fill.ts_event_ns / 1000000).toISOString()) },
            { key: 'market', header: 'Market', render: (fill) => fill.instrument_id },
            { key: 'side', header: 'Side', render: (fill) => fill.order_side ?? 'Unavailable' },
            { key: 'execution', header: 'Quantity / price', render: (fill) => fill.quantity + ' / ' + fill.price },
            { key: 'fee', header: 'Commission', render: (fill) => fill.commission_amount == null ? 'Unavailable' : (fill.commission_amount + ' ' + (fill.commission_currency ?? '')).trim() },
            { key: 'liquidity', header: 'Liquidity', render: (fill) => fill.liquidity_side ?? 'Unavailable' },
            { key: 'order', header: 'Order / episode', render: (fill) => (fill.client_order_id ?? fill.venue_order_id ?? 'Unavailable') + ' / ' + (fill.episode_id ?? 'Unavailable') },
          ]} />
          {fillHistoryHasMore ? <Button variant="secondary" onClick={loadMoreFills}>Load more fills</Button> : null}
        </>}
    </Card>
    <details className="nautilus-diagnostics"><summary>Diagnostics and source identity</summary><div className="terminal-layout"><p className="muted">Instance: <code>{state?.instance_id ?? 'hl-stageg-testnet'}</code> · reconciliation: {state?.reconciliation ?? 'UNKNOWN'} · warmup: {state?.warmup.state ?? 'UNKNOWN'} ({state?.warmup.rows ?? 'UNKNOWN'} rows).</p><p className="muted">Candidate: {state?.hashes.candidate_sha256 ?? 'UNKNOWN'} · strategy: {state?.hashes.strategy_sha256 ?? 'UNKNOWN'} · policy: {state?.hashes.execution_policy_sha256 ?? 'UNKNOWN'}.</p><p className="muted">Account: {state?.account.status ?? "UNAVAILABLE"} | initial margin: {state?.account.im ?? 'UNKNOWN'} · maintenance margin: {state?.account.mm ?? 'UNKNOWN'} · activity cursor: {state?.event_cursor ?? 'UNKNOWN'}.</p><p className="muted">Warnings: {state?.warnings.join(' · ') || 'NONE'} · API detail: {message || 'NONE'}.</p><p className="muted">The dashboard fill table uses only detailed native fill facts. Older ID-only events stay unavailable.</p><DataTable rows={eventRows} emptyText="No native activity recorded." mobileTitle={(row) => row.kind} columns={[{ key: 'cursor', header: 'Cursor', render: (row) => row.cursor }, { key: 'kind', header: 'Kind', render: (row) => row.kind }, { key: 'event', header: 'Event reference', render: (row) => row.event_id }]} /></div></details>
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
    setCommandInFlight(command); setMessage('Sending Stage-G entry control…');
    try {
      const result = await commandHlStagegEntries(command, crypto.randomUUID());
      await refresh();
      setMessage(`${result.command === 'pause-new-entries' ? 'New entries paused' : 'New entries resumed'} (${result.status.toLowerCase()} and read back).`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Stage-G entry control failed.'); }
    finally { setCommandInFlight(null); }
  }
  return <main className="terminal-layout">
    <Card title="Workspace connection" actions={<Badge tone={state?.projection_state === 'READY' ? 'success' : 'danger'}>{loading ? 'LOADING' : state?.projection_state ?? 'UNAVAILABLE'}</Badge>}>
      <div className="stats-grid"><Stat label="Instance" value={state?.instance_id ?? 'hl-stageg-testnet'} /><Stat label="Execution" value="Native Sandbox" /><Stat label="Live orders" value="DISABLED" /></div>

      <p className="muted">Funding treatment: {fundingLabel(state)}. It is not posted to Sandbox cash.</p>
      <Button variant="secondary" onClick={() => void refresh()}>Refresh connection</Button>
    </Card>
    <Card title="Drawdown protection" actions={<Badge tone={protectionFresh ? "success" : "danger"}>{protectionFresh ? "ARMED" : state?.recovery_required ? "UNVERIFIED" : protectionVerified ? "STALE" : "NOT ARMED"}</Badge>}>
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
      <p className="muted">Pause and resume control whether the worker may submit new Stage-G Sandbox entries. They do not confirm that the strategy currently permits an entry.</p>
      <p className="muted"><strong>New-entry eligibility:</strong> {state?.recovery_required ? 'Blocked while recovery is required' : state?.projection_state !== 'READY' ? 'Unknown · worker status is not ready' : state?.gates.attachable === false ? 'Blocked by the native strategy gate' : state?.gates.attachable === true && state.entry_control.state === 'PAUSED' ? 'Blocked · entries are paused' : state?.gates.attachable === true ? 'Eligible for strategy evaluation' : 'Unknown · native gate status unavailable'}.</p>
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="secondary" disabled={!controlsAllowed || !controls?.pause.enabled || commandInFlight !== null} title={controls?.pause.blocker ?? 'READY'} onClick={() => void commandEntries('pause-new-entries')}>{commandInFlight === 'pause-new-entries' ? 'Pausing…' : 'Pause new entries'}</Button><Button variant="secondary" disabled={!controlsAllowed || !controls?.resume.enabled || commandInFlight !== null} title={controls?.resume.blocker ?? 'READY'} onClick={() => void commandEntries('resume-new-entries')}>{commandInFlight === 'resume-new-entries' ? 'Resuming…' : 'Resume new entries'}</Button><Button variant="danger" disabled title={controls?.flatten.blocker ?? 'UNAVAILABLE'}>Flatten virtual exposure</Button></div>
      <details className="nautilus-diagnostics"><summary>Control readiness</summary><p className="muted">Pause: {controls?.pause.blocker ? humanizeBlocker(controls.pause.blocker) : 'Available'} · Resume: {controls?.resume.blocker ? humanizeBlocker(controls.resume.blocker) : 'Available'} · Flatten: {controls?.flatten.blocker ? humanizeBlocker(controls.flatten.blocker) : 'Unavailable'} · Promotion: {controls?.promotion.blocker ? humanizeBlocker(controls.promotion.blocker) : 'Unavailable'}.</p><details><summary>Technical blocker codes</summary><p className="muted">Pause: {controls?.pause.blocker ?? 'UNKNOWN'} · Resume: {controls?.resume.blocker ?? 'UNKNOWN'} · Flatten: {controls?.flatten.blocker ?? 'UNKNOWN'} · Promotion: {controls?.promotion.blocker ?? 'UNKNOWN'}.</p></details><p className="muted">Observed: {state?.observed_at_ns ? new Date(state.observed_at_ns / 1_000_000).toLocaleString() : 'Unavailable'} · Reconciliation: {state?.reconciliation ?? 'Unavailable'}.</p></details>
    </Card>
    {message ? <p role="alert">{message}</p> : null}
  </main>;
}
