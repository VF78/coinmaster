import { useEffect, useState } from 'react';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';
import { cancelRun, createRun, getConfigurations, getDefaultConfiguration, getHlStagegControls, getHlStagegProjection, getHlStagegStrategy, getResearchCapabilities, getResearchCatalog, getRuns, saveConfiguration, type HlStagegControls, type HlStagegProjection, type HlStagegStrategy, type ResearchCapabilities, type ResearchCatalogEntry, type Run, type StrategyConfig, type StrategyConfiguration } from '../lib/nautilusApi';

type NumberKey = 'ema_period' | 'beta_days' | 'relative_days' | 'z_history_days' | 'wave_history_days' | 'wave_min_count' | 'btc_notional_multiplier' | 'max_gross_to_active' | 'sol_exit_half_z' | 'sol_exit_all_z' | 'sol_max_holding_days' | 'btc_close_trail_fraction';
type ArrayKey = 'wave_quantiles' | 'btc_tp_fractions_initial_qty' | 'sol_size_multipliers_H' | 'sol_entry_z';

function tone(status: string): 'success' | 'danger' | 'neutral' { return status === 'COMPLETED' ? 'success' : status === 'BLOCKED' || status === 'CANCELED' ? 'danger' : 'neutral'; }
function title(key: string) { return key.replaceAll('_', ' '); }

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
  return <main className="terminal-layout">
    <Card title={runningMatch ? 'Running sealed Stage-G' : sourceChecked ? 'Local sealed configuration' : 'Sealed configuration unavailable'} actions={<Badge tone={runningMatch ? 'success' : 'danger'}>{strategy?.running_state ?? (loading ? 'LOADING' : 'NOT_CONFIRMED')}</Badge>}>
      <p className="muted">{runningMatch ? 'Fresh worker projection matches the local sealed hashes.' : sourceChecked ? 'Local sealed configuration; running not confirmed.' : 'Sealed configuration could not be loaded or verified; running not confirmed.'}</p>
      <p className="muted">Instance <code>hl-stageg-testnet</code> · {strategy?.strategy_id ?? 'UNKNOWN'} · native Sandbox using public MAINNET data.</p>
      <p className="muted">Candidate {strategy?.hashes.candidate_sha256 ?? 'UNKNOWN'} · strategy {strategy?.hashes.strategy_sha256 ?? 'UNKNOWN'} · policy {strategy?.hashes.execution_policy_sha256 ?? 'UNKNOWN'}</p>
      <DataTable rows={Object.entries(strategy?.candidate ?? {}).map(([parameter, value]) => ({ id: parameter, parameter, value }))} emptyText="No sealed candidate is available." mobileTitle={(row) => row.parameter} columns={[{ key: 'parameter', header: 'Sealed parameter', render: (row) => row.parameter }, { key: 'value', header: 'Value', render: (row) => row.value }]} />
    </Card>
    <Card title="Sandbox assumptions and unknown account facts" actions={<Badge tone="neutral">HONEST LIMITS</Badge>}><p className="muted">{strategy?.capital_assumption ?? 'UNKNOWN'} · {strategy?.research_comparison_assumption ?? 'UNKNOWN'}.</p><p className="muted">{strategy?.public_venue_profile ?? 'UNKNOWN'} Account margin: {strategy?.account_margin ?? 'UNKNOWN'} · account fee schedule: {strategy?.account_fee_schedule ?? 'UNKNOWN'} · funding: {strategy?.funding_treatment ?? 'UNKNOWN'}.</p></Card>
    <Card title="Promotion" actions={<Badge tone="danger">BLOCKED</Badge>}><p className="muted">Promotion is intentionally unavailable: {strategy?.promotion_reason ?? 'SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED'}. Saving a draft never mutates the running Nautilus instance.</p><Button variant="primary" disabled>Promote to running instance</Button></Card>
    <Card title="Research drafts" actions={<Badge tone="neutral">SEPARATE FROM RUNNER</Badge>}>
      <p className="muted">These are immutable local research records for later evaluation. They are not the sealed Stage-G candidate and do not alter <code>hl-stageg-testnet</code>.</p>
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
        <label className="rules-field"><span>Max parent notional</span><input value={config?.max_parent_notional ?? ''} onChange={(event) => setConfig((item) => item ? { ...item, max_parent_notional: event.target.value } : item)} /></label>
        <label className="rules-field"><span>Include zero waves (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.include_zero_waves)} /></label>
        <label className="rules-field"><span>Freeze sigma on first SOL fill (v0 fixed)</span><input disabled type="checkbox" checked={Boolean(config?.freeze_sigma_on_first_sol_fill)} /></label>
        <label className="rules-field"><span>Insufficient margin (v0 fixed)</span><select disabled value={config?.insufficient_margin ?? 'reject'}><option value="reject">reject</option></select></label>
        </div></section>
      </div>
      <p className="muted">Template constraints remain fixed until a separately scoped native implementation. Server validation is authoritative for research-draft saves.</p>
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!config || saving} onClick={() => void save()}>{saving ? 'Saving…' : 'Save research draft'}</Button>{saved ? <Badge tone="success">{saved.config_hash.slice(0, 12)}</Badge> : null}</div>{message ? <p className="muted">{message}</p> : null}
    </Card>
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
      setMessage(persisted.status === 'BLOCKED' ? persisted.evidence.join(' · ') : 'Native baseline job accepted and read back.');
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
  return <main className="terminal-layout">
    <Card title="Native baseline period" actions={<Badge tone={baselineReady ? 'success' : 'danger'}>{capabilities?.baseline_state ?? (loading ? 'LOADING' : 'BLOCKED')}</Badge>}>
      <div className="rules-form-grid">
        <label className="rules-field"><span>Immutable configuration</span><select value={config?.id ?? ''} onChange={(event) => { const next = configs.find((item) => item.id === event.target.value) ?? null; setConfig(next); setCapabilities(null); if (next) { window.localStorage.setItem('coinmaster-selected-config', next.id); void getResearchCapabilities(next.id).then(setCapabilities).catch((error: Error) => setMessage(error.message)); } }}>{configs.map((item) => <option key={item.id} value={item.id}>{item.config_hash.slice(0, 12)} · {item.created_at}</option>)}</select></label>
        <label className="rules-field"><span>Start date</span><input disabled value={capabilities?.baseline_start ?? 'UNKNOWN'} /></label>
        <label className="rules-field"><span>End date (exclusive)</span><input disabled value={capabilities?.baseline_end_exclusive ?? 'UNKNOWN'} /></label>
        <label className="rules-field"><span>Ranking objective</span><input disabled value={capabilities?.baseline_objective ?? 'TOTAL only'} /></label>
      </div>
      <p className="muted">The period is fixed by the verified native baseline contract. Its child validates the immutable configuration and 1m coverage again before work begins.</p>
      {capabilities?.baseline_blockers.length ? <p className="muted">Baseline blocked: {capabilities.baseline_blockers.join(' · ')}</p> : null}
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="primary" disabled={!baselineReady || starting || Boolean(activeRun)} onClick={() => void startBaseline()}>{starting ? 'Starting…' : activeRun ? 'Native job running…' : 'Run verified native baseline'}</Button><Button variant="secondary" onClick={() => void load()}>Refresh status</Button></div>
    </Card>
    <Card title="Bounded native optimizer" actions={<Badge tone={optimizerReady ? 'success' : 'danger'}>{capabilities?.optimizer_state ?? 'BLOCKED'}</Badge>}>
      <p className="muted">Sealed Stage-G source {optimizerSearch?.source_candidate_sha256.slice(0, 12) ?? 'UNKNOWN'} · verified 1m manifest {capabilities?.optimizer_source_manifest_sha256?.slice(0, 12) ?? 'UNKNOWN'}.</p>
      <p className="muted">One axis: {optimizerSearch?.axis ?? 'btc_notional_multiplier'} = {optimizerSearch?.values.join(', ') ?? '—'} · budget {optimizerSearch?.max_variants ?? '—'} native variants · ranking by terminal ACTIVE+RESERVE TOTAL. Diagnostic only; no promotion.</p>
      {capabilities?.optimizer_blockers.length ? <p className="muted">Blocked: {capabilities.optimizer_blockers.join(' · ')}</p> : null}
      <Button variant="primary" disabled={!optimizerReady || !config || starting || Boolean(activeRun)} onClick={() => void startOptimizer()}>{starting ? 'Starting…' : activeRun ? 'Worker busy…' : 'Optimize TOTAL only'}</Button>
    </Card>
    <Card title="Selected run · progress and result" actions={<Badge tone={selectedRun ? tone(selectedRun.status) : 'neutral'}>{selectedRun ? `${selectedRun.status}${selectedRun.progress === null || selectedRun.progress === undefined ? '' : ` · ${selectedRun.progress}%`}` : 'NO RUN SELECTED'}</Badge>}>
      <p className="muted">{activeRun ? `Active native job ${activeRun.id.slice(0, 8)} updates every three seconds.` : 'Choose a run from history to inspect its compact result.'}</p>
      <div className="stats-grid"><Stat label="Terminal TOTAL" value={String(terminalTotal ?? 'UNKNOWN')} /><Stat label="Active" value={String(selectedRun?.report?.terminal_active ?? 'UNKNOWN')} /><Stat label="Reserve" value={String(selectedRun?.report?.terminal_reserve ?? 'UNKNOWN')} /><Stat label="ROI" value={String((selectedRun?.report?.summary as { roi?: string } | undefined)?.roi ?? 'UNKNOWN')} /><Stat label="Max drawdown" value={String((selectedRun?.report?.summary as { max_drawdown_percent?: string } | undefined)?.max_drawdown_percent ?? 'UNKNOWN')} /><Stat label="Native fills" value={String(selectedRun?.report?.fills ?? 'UNKNOWN')} /></div>
      <p className="muted">Classification: {String(selectedRun?.report?.status ?? 'UNKNOWN')} · fees: {String(selectedRun?.report?.native_fees ?? 'UNKNOWN')} · liquidations: {String(selectedRun?.report?.liquidation_count ?? 'UNKNOWN')}. Diagnostic results are not live rankings.</p>
      {selectedRun?.evidence.length ? <p className="muted">Job evidence: {selectedRun.evidence.join(' · ')}</p> : null}
      {selectedRun?.command_name === 'native_optimizer' ? <p className="muted">Request {selectedRun.request_hash?.slice(0, 12) ?? '—'} · config {selectedRun.report?.request_config_hash?.toString().slice(0, 12) ?? '—'} · result {selectedRun.report?.artifact_sha256?.toString().slice(0, 12) ?? '—'} · classification {selectedRun.report?.status?.toString() ?? '—'}.</p> : null}
      {top20.length ? <><h3 className="nautilus-subheading">TOP {top20.length} · terminal TOTAL comparison</h3><DataTable rows={top20.map((row) => ({ ...row, id: row.candidate_id }))} emptyText="No ranked candidates." mobileTitle={(row) => row.candidate_id} columns={[{ key: 'candidate', header: 'Candidate', render: (row) => row.candidate_id }, { key: 'total', header: 'TOTAL / ACTIVE / RESERVE', render: (row) => `${row.terminal_total} / ${row.terminal_active} / ${row.terminal_reserve}` }, { key: 'risk', header: 'ROI / DD / liq', render: (row) => `${row.roi} / ${row.drawdown_percent} / ${row.liquidations}` }, { key: 'costs', header: 'Fills / maker / taker / funding', render: (row) => `${row.fills} / ${row.maker_fees} / ${row.taker_fees} / ${row.funding?.signed_amount ?? 'UNKNOWN'}` }, { key: 'proof', header: 'Evidence', render: (row) => `${row.classification} · ${row.artifact_sha256.slice(0, 12)} · ${row.limitations.join('; ')}` }]} /></> : <p className="muted">No TOP-20 comparison for this run. A completed optimizer publishes candidates here.</p>}
      {selectedRun && ['STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'QUEUED'].includes(selectedRun.status) ? <Button variant="danger" disabled={Boolean(cancellingId)} onClick={() => void cancelOwned(selectedRun.id)}>{cancellingId === selectedRun.id ? 'Cancelling…' : 'Cancel owned job'}</Button> : null}
      <p className="muted">The page displays compact status and result fields only; job artifacts remain hash-checked private evidence.</p>
    </Card>
    <Card title="Run history · select to compare" actions={<Badge tone="neutral">TOTAL ONLY</Badge>}><DataTable rows={runs.map((run) => ({ ...run, id: run.id }))} emptyText="No native research jobs yet." mobileTitle={(run) => `${run.command_name ?? run.kind} · ${run.id.slice(0, 8)}`} columns={[{ key: 'run', header: 'Run', render: (run) => <Button variant="secondary" onClick={() => setSelectedRunId(run.id)}>{run.command_name ?? run.kind} · {run.id.slice(0, 8)}</Button> }, { key: 'status', header: 'Status / progress', render: (run) => <Badge tone={tone(run.status)}>{run.status}{run.progress === null || run.progress === undefined ? '' : ` · ${run.progress}%`}</Badge> }, { key: 'total', header: 'Terminal TOTAL', render: (run) => String((run.report?.summary as { terminal_total?: string } | undefined)?.terminal_total ?? run.report?.terminal_total ?? '—') }, { key: 'evidence', header: 'Evidence', render: (run) => run.evidence.join(' · ') }]} /></Card>
    <Card title="Verified historical evidence" actions={<Badge tone="neutral">READ ONLY</Badge>}><p className="muted">Diagnostic evidence remains separate from native job history. It never substitutes for a newly launched calculation.</p><DataTable rows={catalog.map((item) => ({ ...item, id: item.id }))} emptyText="No catalog evidence." mobileTitle={(item) => item.title} columns={[{ key: 'evidence', header: 'Evidence', render: (item) => item.title }, { key: 'class', header: 'Class', render: (item) => <Badge tone={item.liquidations ? 'danger' : 'neutral'}>{item.classification}</Badge> }, { key: 'total', header: 'TOTAL', render: (item) => item.settled_total }, { key: 'artifact', header: 'Artifact', render: (item) => item.artifact_state }]} /></Card>
    {message ? <p className="muted">{message}</p> : null}
  </main>;
}

export function RuntimePage() {
  const [state, setState] = useState<HlStagegProjection | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const load = () => void getHlStagegProjection().then((projection) => {
    setState(projection); setMessage('');
  }).catch((error: unknown) => {
    setState(null); setMessage(error instanceof Error ? error.message : 'Sandbox projection unavailable.');
  }).finally(() => setLoading(false));
  useEffect(() => { load(); const timer = window.setInterval(load, 5000); return () => window.clearInterval(timer); }, []);
  const runtimeHealthy = state?.projection_state === 'READY' && state.process_state !== 'DATA_STALE/PAUSED' && state.process_state !== 'WORKER_DISCONNECTED';
  const toneForProjection = runtimeHealthy ? 'success' : 'danger';
  const eventRows = (state?.events ?? []).map((event) => ({ ...event, id: `${event.cursor}:${event.event_id}` }));
  const positionRows = (state?.positions ?? []).map((position) => ({ ...position, id: position.instrument_id }));
  const orderRows = (state?.orders ?? []).map((order) => ({ ...order, id: order.client_order_id }));
  const feedRows = Object.entries(state?.feeds ?? {}).map(([instrument_id, feed]) => ({ ...feed, instrument_id, id: instrument_id }));
  const age = (value: number | null | undefined) => value === null || value === undefined ? 'UNKNOWN' : `${(value / 1_000_000_000).toFixed(1)}s`;
  return <main className="terminal-layout">
    <Card title="Sandbox account and health" actions={<Badge tone={toneForProjection}>{state ? `${state.projection_state} · ${state.process_state}` : loading ? 'LOADING' : 'UNAVAILABLE'}</Badge>}>
      <p className="muted">Isolated instance: <code>hl-stageg-testnet</code> · public MAINNET data · local native Sandbox · read only. This is not <code>coinmaster-paper</code>.</p>
      <div className="stats-grid">
        <Stat label="Native cash" value={state?.account.native_cash ?? 'UNKNOWN'} />
        <Stat label="Equity" value={state?.account.equity ?? 'UNKNOWN'} />
        <Stat label="Free margin" value={state?.account.free_margin ?? 'UNKNOWN'} />
        <Stat label="Initial margin" value={state?.account.im ?? 'UNKNOWN'} />
        <Stat label="Maintenance margin" value={state?.account.mm ?? 'UNKNOWN'} />
        <Stat label="Selected leverage" value="UNKNOWN" />
      </div>
      <div className="rules-btn-group rules-btn-group--mb"><Button variant="secondary" onClick={load}>Refresh projection</Button></div>
      <p className="muted">Process: {state?.process_state ?? 'UNKNOWN'} · reconciliation: {state?.reconciliation ?? 'UNKNOWN'} · live order capability: false</p>
      <p className="muted">Candidate: {state?.hashes.candidate_sha256 ?? 'UNKNOWN'} · Strategy: {state?.hashes.strategy_sha256 ?? 'UNKNOWN'} · Policy: {state?.hashes.execution_policy_sha256 ?? 'UNKNOWN'}</p>
      <p className="muted">Warmup: {state?.warmup.state ?? 'UNKNOWN'} ({state?.warmup.rows ?? 'UNKNOWN'} rows) · funding: {state?.funding_state ?? 'UNPOSTED'}</p>
      <p className="muted">Account figures are UNKNOWN until the native worker supplies verified values. Future funding is UNPOSTED, never settled cash.</p>
    </Card>
    <Card title="Open positions and orders" actions={<Badge tone="neutral">SANDBOX</Badge>}><DataTable rows={positionRows} emptyText="No projected Sandbox positions." mobileTitle={(row) => row.instrument_id} columns={[{ key: 'instrument', header: 'Instrument', render: (row) => row.instrument_id }, { key: 'quantity', header: 'Quantity', render: (row) => row.signed_quantity }, { key: 'provenance', header: 'Provenance', render: (row) => row.provenance }]} /><DataTable rows={orderRows} emptyText="No projected Sandbox orders." mobileTitle={(row) => row.client_order_id} columns={[{ key: 'order', header: 'Client order', render: (row) => row.client_order_id }, { key: 'instrument', header: 'Instrument', render: (row) => row.instrument_id ?? 'UNKNOWN' }, { key: 'provenance', header: 'Provenance', render: (row) => row.provenance }]} /></Card>
    <Card title="Recent native activity" actions={<Badge tone="neutral">EVENT CURSOR</Badge>}><DataTable rows={eventRows} emptyText="No projected Sandbox events." mobileTitle={(row) => `${row.kind} · ${row.event_id}`} columns={[{ key: 'cursor', header: 'Cursor', render: (row) => row.cursor }, { key: 'kind', header: 'Kind', render: (row) => row.kind }, { key: 'event', header: 'Event', render: (row) => row.event_id }, { key: 'provenance', header: 'Provenance', render: (row) => row.provenance }]} /><p className="muted">Trade and fill detail: UNKNOWN. Event metadata is an audit cursor, not a claimed exchange fill or PnL history.</p></Card>
    <Card title="Public feed health" actions={<Badge tone="neutral">DIAGNOSTICS</Badge>}><DataTable rows={feedRows} emptyText="No public feed observations." mobileTitle={(row) => row.instrument_id} columns={[{ key: 'instrument', header: 'Instrument', render: (row) => row.instrument_id }, { key: 'state', header: 'State', render: (row) => row.state }, { key: 'mark', header: 'Mark', render: (row) => row.mark ?? 'UNKNOWN' }, { key: 'mark-age', header: 'Mark age', render: (row) => age(row.mark_age_ns) }, { key: 'funding', header: 'Funding', render: (row) => row.funding_rate ?? 'UNKNOWN' }, { key: 'funding-age', header: 'Funding age', render: (row) => age(row.funding_age_ns) }]} /></Card>
    <p className="muted">{state?.warnings.join(' · ') || message}</p>
  </main>;
}

export function WorkspaceSettingsPage() {
  const [state, setState] = useState<HlStagegProjection | null>(null);
  const [controls, setControls] = useState<HlStagegControls | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  async function refresh() {
    setLoading(true);
    const [projection, capabilities] = await Promise.allSettled([getHlStagegProjection(), getHlStagegControls()]);
    setState(projection.status === 'fulfilled' ? projection.value : null);
    setControls(capabilities.status === 'fulfilled' ? capabilities.value : null);
    const failed = [projection, capabilities].find((result) => result.status === 'rejected');
    setMessage(failed?.status === 'rejected' ? String(failed.reason) : '');
    setLoading(false);
  }
  useEffect(() => { void refresh(); }, []);
  return <main className="terminal-layout">
    <Card title="Workspace connection" actions={<Badge tone={state?.projection_state === 'READY' ? 'success' : 'danger'}>{loading ? 'LOADING' : state?.projection_state ?? 'UNAVAILABLE'}</Badge>}>
      <div className="stats-grid"><Stat label="Instance" value={state?.instance_id ?? 'hl-stageg-testnet'} /><Stat label="Execution" value="Native Sandbox" /><Stat label="Live orders" value="DISABLED" /></div>
      <p className="muted">Public Hyperliquid MAINNET prices and Bybit signal data feed the isolated virtual Stage-G instance. No exchange credential or wallet setting is used here.</p>
      <p className="muted">Observed at: {state?.observed_at_ns ? new Date(state.observed_at_ns / 1_000_000).toLocaleString() : 'UNKNOWN'} · Reconciliation: {state?.reconciliation ?? 'UNKNOWN'} · Funding: {state?.funding_state ?? 'UNPOSTED'}.</p>
      <Button variant="secondary" onClick={() => void refresh()}>Refresh connection</Button>
    </Card>
    <Card title="Native control permissions" actions={<Badge tone="danger">READ ONLY</Badge>}>
      <p className="muted">Pause: {controls?.pause.blocker ?? 'UNAVAILABLE'} · Resume: {controls?.resume.blocker ?? 'UNAVAILABLE'} · Flatten: {controls?.flatten.blocker ?? 'UNAVAILABLE'} · Promotion: {controls?.promotion.blocker ?? 'UNAVAILABLE'}.</p>
      <p className="muted">Controls require a separate native lifecycle gate. Research drafts and jobs never change the running trader.</p>
    </Card>
    <Card title="Data provenance"><p className="muted">Account cash, equity, free margin, leverage, position PnL and fee tier stay UNKNOWN until verified by a native Sandbox read model. Observed future funding is unposted, so no settlement cash is claimed.</p>{message ? <p role="alert">{message}</p> : null}</Card>
  </main>;
}
