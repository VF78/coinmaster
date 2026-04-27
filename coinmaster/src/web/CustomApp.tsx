import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { TradingRulesPage } from './pages/TradingRulesPage';
import { useDialog } from './components/DialogProvider';
import { Card } from './components/Card';
import { Badge } from './components/Badge';
import { Button } from './components/Button';
import { getAlphaRadarIdeas, getAlphaRadarSettings, getFreqtradeRadarPolicy, getRadarRuntimeSettings, refreshFreqtradeRadarPolicy, saveAlphaRadarSettings, saveRadarRuntimeSettings, type FreqtradeRadarPolicyResponse, type FreqtradeRadarPolicyScope } from './lib/api';

 type PageKey = 'trading-rules' | 'radar' | 'backtest';

const SECTIONS: Array<{ key: PageKey; label: string }> = [
  { key: 'trading-rules', label: 'Trading Rules' },
  { key: 'radar', label: 'Radar' },
  { key: 'backtest', label: 'Backtest' },
];

function radarTone(scope?: FreqtradeRadarPolicyScope): 'success' | 'danger' | 'neutral' {
  if (!scope) return 'neutral';
  if (scope.mode === 'off' || scope.lock_new_entries || scope.risk_multiplier <= 0) return 'danger';
  if (scope.risk_multiplier < 1 || scope.mode !== 'both') return 'neutral';
  return 'success';
}

function statusIcon(ok: boolean | undefined) {
  return ok ? '🟢' : '🔴';
}

function sourceIcon(source: string) {
  const text = source.toLowerCase();
  if (text.includes('telegram')) return '✈️';
  if (text.includes('reddit')) return '👽';
  if (text.includes('bluesky')) return '🦋';
  if (text.includes('market')) return '📈';
  if (text.includes('rss') || text.includes('news')) return '📰';
  if (text.includes('macro')) return '🌍';
  return '🔌';
}

function pairAsset(pair: string) {
  return pair.split('/', 1)[0].replace('-', ':');
}

function formatTimestamp(value?: string) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : value;
}

function compactText(value: string | undefined, max = 110): string {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim();
  if (!text) return '—';
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

type FunnelDetailKey = 'candidates' | 'policy' | 'engine';

function RadarPolicyPage() {
  const [payload, setPayload] = useState<FreqtradeRadarPolicyResponse | null>(null);
  const [ideasPayload, setIdeasPayload] = useState<Awaited<ReturnType<typeof getAlphaRadarIdeas>> | null>(null);
  const [alphaSettings, setAlphaSettings] = useState<Awaited<ReturnType<typeof getAlphaRadarSettings>>['settings'] | null>(null);
  const [radarRuntime, setRadarRuntime] = useState<Awaited<ReturnType<typeof getRadarRuntimeSettings>>['runtime'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<FunnelDetailKey | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [policyResult, ideasResult, alphaResult, runtimeResult] = await Promise.all([
        getFreqtradeRadarPolicy(),
        getAlphaRadarIdeas().catch(() => null),
        getAlphaRadarSettings().catch(() => null),
        getRadarRuntimeSettings().catch(() => null),
      ]);
      setPayload(policyResult);
      setIdeasPayload(ideasResult);
      if (alphaResult?.settings) setAlphaSettings(alphaResult.settings);
      if (runtimeResult?.runtime) setRadarRuntime(runtimeResult.runtime);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  async function refresh() {
    try {
      const result = await refreshFreqtradeRadarPolicy();
      setPayload({ ok: true, enabled: result.enabled, radarEnabled: result.radarEnabled, path: result.path, generated: result.policy, disk: result.policy });
      setIdeasPayload(await getAlphaRadarIdeas().catch(() => null));
      setMessage('Radar refreshed.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function toggleRadar() {
    if (!alphaSettings || !radarRuntime) return;
    const nextEnabled = !(alphaSettings.enabled && radarRuntime.enabled);
    setBusy('radar');
    try {
      const [alphaResult, runtimeResult] = await Promise.all([
        saveAlphaRadarSettings({ ...alphaSettings, enabled: nextEnabled }),
        saveRadarRuntimeSettings({ enabled: nextEnabled }),
      ]);
      setAlphaSettings(alphaResult.settings);
      setRadarRuntime(runtimeResult.runtime);
      await refresh();
      setMessage(nextEnabled ? 'Radar enabled.' : 'Radar disabled.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  }

  async function toggleAutoConfirm() {
    if (!radarRuntime) return;
    setBusy('confirm');
    try {
      const result = await saveRadarRuntimeSettings({ autoConfirm: !radarRuntime.autoConfirm });
      setRadarRuntime(result.runtime);
      await refresh();
      setMessage(result.runtime.autoConfirm ? 'Radar block enforcement enabled.' : 'Radar observe-only mode enabled.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { void load(); }, 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const policy = payload?.disk ?? payload?.generated;
  const pairs = Object.entries(policy?.pairs ?? {});
  const diagnostics = policy?.diagnostics ?? {};
  const summary = ideasPayload?.marketSummary;
  const radarEnabled = Boolean((payload?.radarEnabled ?? policy?.global.enabled) && alphaSettings?.enabled !== false && radarRuntime?.enabled !== false);
  const engineConnected = Boolean(payload?.enabled && policy && policy.global.enabled && !payload?.diskError);
  const connectors = ideasPayload?.connectorRuntimes ?? [];
  const connectorProblems = connectors.filter((item) => item.enabled && item.state.lastSyncStatus === 'error').length;
  const sourceHealth = (summary?.sourceHealth ?? []).slice(0, 8);
  const monitoredAssets = pairs.length > 0 ? pairs.map(([pair]) => pairAsset(pair)) : [];
  const candidateIdeas = (ideasPayload?.ideas ?? []).filter((item) => item.verdict !== 'cash');
  const funnelSteps: Array<{ icon: string; label: string; value: number; hint: string; detail?: FunnelDetailKey }> = [
    { icon: '📡', label: 'Collected', value: (summary?.evidenceBundles ?? 0) + (summary?.dedupeSuppressed ?? 0), hint: 'Raw items' },
    { icon: '🧹', label: 'Deduped', value: summary?.dedupeSuppressed ?? 0, hint: 'Noise removed' },
    { icon: '🧩', label: 'Evidence', value: summary?.evidenceBundles ?? 0, hint: 'Useful clusters' },
    { icon: '🎯', label: 'Candidates', value: summary?.signalCandidates ?? candidateIdeas.length, hint: 'Click for list', detail: 'candidates' },
    { icon: '🧠', label: 'Policy', value: summary?.activeRadarContextPolicies ?? pairs.length, hint: 'Click for rules', detail: 'policy' },
    { icon: '⚙️', label: 'Engine', value: pairs.length, hint: 'Click for sent', detail: 'engine' },
  ];

  let detailTitle = '';
  let detailBody: ReactNode = null;
  if (activeDetail === 'candidates') {
    detailTitle = '🎯 Candidates';
    detailBody = candidateIdeas.length ? (
      <div className="radar-modal-grid">
        {candidateIdeas.map((idea) => (
          <article className="radar-modal-card" key={idea.id}>
            <div className="radar-signal-pair"><strong>{idea.symbol ?? 'Market'} {idea.direction ? idea.direction.toUpperCase() : ''}</strong><Badge tone={idea.actionability.actionable ? 'success' : 'neutral'}>{idea.verdict}</Badge></div>
            <div className="radar-score-ring">{Math.round(idea.score * 100)}<span>/100</span></div>
            <p>{compactText(idea.title, 90)}</p>
            <p className="muted">{compactText(idea.actionability.summary, 130)}</p>
            {idea.actionability.blockers.length ? <p className="muted">Blocked by: {idea.actionability.blockers.slice(0, 2).join(' · ')}</p> : null}
            <details><summary>Why now?</summary><p className="muted">{idea.whyNow.slice(0, 4).join(' · ')}</p></details>
          </article>
        ))}
      </div>
    ) : <p className="muted">No active candidates right now.</p>;
  } else if (activeDetail === 'policy') {
    detailTitle = '🧠 Policy decisions';
    detailBody = (
      <div className="radar-modal-grid">
        <article className="radar-modal-card">
          <div className="radar-signal-pair"><strong>Global guard</strong><Badge tone={radarTone(policy?.global)}>{policy?.global.mode ?? 'both'}</Badge></div>
          <p>Risk ×{policy?.global.risk_multiplier ?? 1}</p>
          <p className="muted">{policy?.global.reason ?? 'neutral'}</p>
        </article>
        {pairs.map(([pair, scope]) => (
          <article className="radar-modal-card" key={pair}>
            <div className="radar-signal-pair"><strong>{pairAsset(pair)}</strong><Badge tone={radarTone(scope)}>{scope.mode}</Badge></div>
            <div className="radar-risk-meter"><span style={{ width: `${Math.round(Math.max(0, Math.min(1, scope.risk_multiplier)) * 100)}%` }} /></div>
            <p>Risk ×{scope.risk_multiplier}</p>
            <p className="muted">{scope.reason.replaceAll('_', ' ')}</p>
            <p className="muted">Priority: {scope.priority_score ?? 'n/a'} · Candidate: {scope.signal_candidate_id ?? 'n/a'}</p>
          </article>
        ))}
      </div>
    );
  } else if (activeDetail === 'engine') {
    detailTitle = '⚙️ Sent to Freqtrade';
    detailBody = pairs.length ? (
      <div className="radar-modal-grid">
        {pairs.map(([pair, scope]) => (
          <article className="radar-modal-card radar-modal-card--engine" key={pair}>
            <div className="radar-signal-pair"><strong>{pair}</strong><Badge tone={radarTone(scope)}>{scope.mode}</Badge></div>
            <p className="radar-engine-line">✅ Strategy receives: {scope.mode} · risk ×{scope.risk_multiplier}</p>
            <p className="muted">Policy file: {payload?.path ?? 'radar_policy.json'}</p>
            <p className="muted">Valid until: {formatTimestamp(policy?.valid_until)}</p>
            <p className="muted">Evidence: {scope.evidence_ids?.join(', ') || 'n/a'}</p>
          </article>
        ))}
      </div>
    ) : <p className="muted">Nothing is being sent to Freqtrade now. Radar is neutral.</p>;
  }

  return (
    <main className="radar-ux-page">
      {message ? <div className="radar-ux-toast">{message}</div> : null}
      {loading && !policy ? <p className="muted">Loading Radar…</p> : null}

      <Card
        title="1. Radar status"
        className="terminal-card radar-ux-card"
        actions={<Badge tone={radarEnabled ? 'success' : 'danger'}>{radarEnabled ? 'ON' : 'OFF'}</Badge>}
      >
        <div className="radar-status-hero">
          <div className={radarEnabled ? 'radar-status-orb radar-status-orb--on' : 'radar-status-orb radar-status-orb--off'}>{radarEnabled ? '🟢' : '⏸️'}</div>
          <div>
            <h2>{radarEnabled ? 'Radar is watching the market' : 'Radar is paused'}</h2>
            <p className="muted">{engineConnected ? 'Policy stream to Freqtrade is healthy.' : 'No active policy stream is reaching Freqtrade.'}</p>
          </div>
        </div>

        <div className="radar-big-grid">
          <div className="radar-big-tile">
            <span className="radar-big-icon">{statusIcon(radarEnabled)}</span>
            <strong>Observation</strong>
            <p>{radarEnabled ? 'Working' : 'Stopped'}</p>
          </div>
          <div className="radar-big-tile">
            <span className="radar-big-icon">{statusIcon(engineConnected)}</span>
            <strong>Freqtrade link</strong>
            <p>{engineConnected ? 'Sending policy' : 'Neutral / disabled'}</p>
          </div>
          <div className="radar-big-tile">
            <span className="radar-big-icon">🔌</span>
            <strong>Sources</strong>
            <p>{connectors.filter((item) => item.enabled).length} on · {connectorProblems} down</p>
          </div>
          <div className="radar-big-tile">
            <span className="radar-big-icon">🪙</span>
            <strong>Trading assets</strong>
            <p>{monitoredAssets.length ? monitoredAssets.join(' · ') : 'No active overrides'}</p>
          </div>
        </div>

        <details className="radar-details">
          <summary>Show source and asset details</summary>
          <div className="radar-source-grid">
            {connectors.length ? connectors.map((item) => (
              <div className="radar-source-pill" key={item.type}>
                <span>{sourceIcon(item.type)}</span>
                <strong>{item.sourceLabel ?? item.type}</strong>
                <Badge tone={!item.enabled ? 'neutral' : item.state.lastSyncStatus === 'error' ? 'danger' : item.state.lastSyncStatus === 'success' ? 'success' : 'neutral'}>
                  {!item.enabled ? 'off' : item.state.lastSyncStatus}
                </Badge>
              </div>
            )) : <p className="muted">No connector runtime data yet.</p>}
          </div>
          <div className="radar-chip-grid">
            {sourceHealth.map((source) => (
              <span className={`radar-chip ${source.status === 'fresh' ? 'radar-chip--success' : source.status === 'stale' ? 'radar-chip--danger' : 'radar-chip--muted'}`} key={source.source}>
                {sourceIcon(source.source)} {source.source}: {source.status}
              </span>
            ))}
            {monitoredAssets.map((asset) => <span className="radar-chip" key={asset}>🪙 {asset}</span>)}
          </div>
        </details>
      </Card>

      <Card title="2. Live feed" className="terminal-card radar-ux-card">
        <div className="radar-funnel">
          {funnelSteps.map((step, index) => {
            const content = (
              <>
                <div className="radar-funnel-icon">{step.icon}</div>
                <div className="radar-funnel-value">{step.value}</div>
                <strong>{step.label}</strong>
                <span>{step.hint}</span>
                {index < funnelSteps.length - 1 ? <div className="radar-funnel-arrow">→</div> : null}
              </>
            );
            return step.detail ? (
              <button type="button" className="radar-funnel-step radar-funnel-step--clickable" key={step.label} onClick={() => setActiveDetail(step.detail ?? null)}>
                {content}
              </button>
            ) : (
              <div className="radar-funnel-step" key={step.label}>{content}</div>
            );
          })}
        </div>

        <section className="radar-engine-signals">
          <div className="radar-simple-section__header">
            <h3>Now translated to trading engine</h3>
            <Badge tone={pairs.length ? 'success' : 'neutral'}>{pairs.length} active</Badge>
          </div>
          {pairs.length ? (
            <div className="radar-signal-grid">
              {pairs.map(([pair, scope]) => (
                <article className="radar-signal-card" key={pair}>
                  <div className="radar-signal-pair"><span>🪙</span><strong>{pairAsset(pair)}</strong><Badge tone={radarTone(scope)}>{scope.mode}</Badge></div>
                  <div className="radar-risk-meter"><span style={{ width: `${Math.round(Math.max(0, Math.min(1, scope.risk_multiplier)) * 100)}%` }} /></div>
                  <p>Risk ×{scope.risk_multiplier} · {scope.reason.replaceAll('_', ' ')}</p>
                  <details>
                    <summary>Why?</summary>
                    <p className="muted">Candidate: {scope.signal_candidate_id ?? 'n/a'}</p>
                    <p className="muted">Evidence: {scope.evidence_ids?.join(', ') || 'n/a'}</p>
                    <p className="muted">Reason codes: {scope.reason_codes?.join(', ') || 'context_policy'}</p>
                  </details>
                </article>
              ))}
            </div>
          ) : <p className="muted">Radar is neutral now: no pair-specific signal is being sent to Freqtrade.</p>}
        </section>

        <details className="radar-details">
          <summary>Show funnel diagnostics</summary>
          <div className="radar-chip-grid">
            <span className="radar-chip radar-chip--muted">ignored neutral: {diagnostics.ignored_neutral_policies ?? 0}</span>
            <span className="radar-chip radar-chip--muted">expired: {diagnostics.ignored_expired_policies ?? summary?.expiredRadarContextPolicies ?? 0}</span>
            <span className="radar-chip radar-chip--muted">locked: {summary?.lockedRadarContextPolicies ?? 0}</span>
            <span className="radar-chip radar-chip--muted">policy accepted: {summary?.policyAcceptedEntries ?? 0}</span>
            <span className="radar-chip radar-chip--muted">policy blocked: {summary?.policyBlockedEntries ?? 0}</span>
          </div>
        </details>
      </Card>



      {activeDetail ? (
        <div className="radar-modal-overlay" role="dialog" aria-modal="true" aria-label={detailTitle} onClick={() => setActiveDetail(null)}>
          <div className="radar-modal" onClick={(event) => event.stopPropagation()}>
            <div className="radar-modal-header">
              <h2>{detailTitle}</h2>
              <button type="button" className="bt-report-close" onClick={() => setActiveDetail(null)}>×</button>
            </div>
            {detailBody}
          </div>
        </div>
      ) : null}

      <Card title="3. Settings" className="terminal-card radar-ux-card">
        <div className="radar-settings-grid">
          <section className="radar-setting-block">
            <div>
              <h3>Radar master switch</h3>
              <p className="muted">One switch for observation + Freqtrade policy handoff.</p>
            </div>
            <Button variant={radarEnabled ? 'danger' : 'primary'} onClick={() => { void toggleRadar(); }} disabled={busy !== null || !alphaSettings || !radarRuntime} fullWidth>
              {radarEnabled ? 'Turn Radar off' : 'Turn Radar on'}
            </Button>
          </section>

          <section className="radar-setting-block">
            <div>
              <h3>Radar enforcement</h3>
              <p className="muted">Observe-only keeps Radar context visible but does not hard-block Freqtrade dry-run entries. Enforce allows Radar hard blocks.</p>
            </div>
            <Button variant={radarRuntime?.autoConfirm ? 'danger' : 'secondary'} onClick={() => { void toggleAutoConfirm(); }} disabled={busy !== null || !radarRuntime} fullWidth>
              {radarRuntime?.autoConfirm ? 'Enforce Radar blocks' : 'Observe only / no hard blocks'}
            </Button>
          </section>

          <section className="radar-setting-block">
            <div>
              <h3>Snapshot</h3>
              <p className="muted">Updated {formatTimestamp(policy?.updated_at)} · valid until {formatTimestamp(policy?.valid_until)}</p>
            </div>
            <Button variant="secondary" onClick={() => { void refresh(); }} disabled={busy !== null} fullWidth>Refresh now</Button>
          </section>
        </div>
      </Card>
    </main>
  );
}

function BacktestPlaceholderPage() {
  return (
    <main className="terminal-layout">
      <Card title="Backtest" actions={<Badge tone="neutral">empty</Badge>}>
        <p className="muted">
          Backtest workspace is reserved for the next stage. Freqtrade remains the native backtesting and hyperopt engine.
        </p>
      </Card>
    </main>
  );
}

export function CustomApp() {
  const [page, setPage] = useState<PageKey>('trading-rules');
  const [tradingRulesDirty, setTradingRulesDirty] = useState(false);
  const tradingRulesSaveRef = useRef<(() => Promise<boolean>) | null>(null);
  const dialog = useDialog();

  const pageTitle = useMemo(() => {
    const section = SECTIONS.find((s) => s.key === page);
    return `Coinmaster24 Custom · ${section?.label ?? 'Trading Rules'}`;
  }, [page]);

  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  async function handleNavigate(nextPage: PageKey) {
    if (nextPage === page) return;

    if (page === 'trading-rules' && tradingRulesDirty) {
      const shouldSave = await dialog.confirm({
        title: 'Unsaved Trading Rules',
        message: 'Apply Trading Rules changes before leaving this page?',
        confirmText: 'Apply Trading Rules',
        cancelText: "Don't apply",
      });

      if (shouldSave) {
        const ok = await tradingRulesSaveRef.current?.();
        if (!ok) return;
      }

      setTradingRulesDirty(false);
    }

    setPage(nextPage);
  }

  return (
    <div className="app-shell custom-app-shell">
      <header className="app-topbar">
        <h1>Coinmaster24 Custom</h1>
        <p className="muted custom-app-subtitle">Operator companion for native Freqtrade Stage 1</p>
      </header>

      <div className="app-layout">
        <aside className="sidebar" aria-label="Custom sections">
          <nav className="sidebar-nav">
            <ul className="sidebar-nav__list">
              {SECTIONS.map((section) => (
                <li key={section.key}>
                  <button
                    type="button"
                    className={page === section.key ? 'sidebar-nav__item sidebar-nav__item--active' : 'sidebar-nav__item'}
                    onClick={() => { void handleNavigate(section.key); }}
                  >
                    {section.label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <section className="app-content">
          {page === 'trading-rules' ? (
            <TradingRulesPage
              onDirtyChange={setTradingRulesDirty}
              onRegisterSaveHandler={(handler) => {
                tradingRulesSaveRef.current = handler;
              }}
            />
          ) : null}
          {page === 'radar' ? <RadarPolicyPage /> : null}
          {page === 'backtest' ? <BacktestPlaceholderPage /> : null}
        </section>
      </div>
    </div>
  );
}
