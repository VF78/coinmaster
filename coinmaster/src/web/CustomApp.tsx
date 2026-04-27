import { useEffect, useMemo, useRef, useState } from 'react';
import { TradingRulesPage } from './pages/TradingRulesPage';
import { useDialog } from './components/DialogProvider';
import { Card } from './components/Card';
import { Badge } from './components/Badge';
import { Button } from './components/Button';
import { getFreqtradeRadarPolicy, refreshFreqtradeRadarPolicy, type FreqtradeRadarPolicyResponse, type FreqtradeRadarPolicyScope } from './lib/api';

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

function formatTimestamp(value?: string) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : value;
}

function RadarPolicyPage() {
  const [payload, setPayload] = useState<FreqtradeRadarPolicyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setPayload(await getFreqtradeRadarPolicy());
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
      setPayload({ ok: true, enabled: result.enabled, path: result.path, generated: result.policy, disk: result.policy });
      setMessage('Radar policy refreshed.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
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
  const global = policy?.global;

  return (
    <main className="terminal-layout radar-simple-page">
      <Card
        title="Freqtrade Radar policy"
        className="terminal-card radar-simple-card"
        actions={<Badge tone={payload?.enabled ? 'success' : 'neutral'}>{payload?.enabled ? 'producer on' : 'producer off'}</Badge>}
      >
        <div className="radar-simple-stack">
          {message ? <p className="muted">{message}</p> : null}
          {loading && !policy ? <p className="muted">Loading Radar policy…</p> : null}

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Policy snapshot</h3>
              <Button variant="secondary" onClick={() => { void refresh(); }}>Refresh</Button>
            </div>
            <div className="radar-simple-row">
              <div className="radar-inline-stat"><span className="muted radar-simple-label">Updated</span><strong>{formatTimestamp(policy?.updated_at)}</strong></div>
              <div className="radar-inline-stat"><span className="muted radar-simple-label">Valid until</span><strong>{formatTimestamp(policy?.valid_until)}</strong></div>
              <div className="radar-inline-stat"><span className="muted radar-simple-label">Path</span><strong>{payload?.path ?? '—'}</strong></div>
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Global guard</h3>
              <Badge tone={radarTone(global)}>{global?.mode ?? 'both'}</Badge>
            </div>
            <div className="radar-chip-grid">
              <span className="radar-chip">risk ×{global?.risk_multiplier ?? 1}</span>
              <span className={`radar-chip ${global?.lock_new_entries ? 'radar-chip--danger' : 'radar-chip--success'}`}>{global?.lock_new_entries ? 'entries locked' : 'entries open'}</span>
              <span className="radar-chip radar-chip--muted">{global?.reason ?? 'neutral'}</span>
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Pair decisions</h3>
              <Badge tone={pairs.length > 0 ? 'neutral' : 'success'}>{pairs.length} overrides</Badge>
            </div>
            {pairs.length === 0 ? (
              <p className="muted">No active pair overrides. Freqtrade strategy treats Radar as neutral.</p>
            ) : (
              <div className="radar-compact-list">
                {pairs.map(([pair, scope]) => (
                  <div className="radar-compact-item" key={pair}>
                    <div className="radar-compact-item__top">
                      <strong>{pair}</strong>
                      <Badge tone={radarTone(scope)}>{scope.mode}</Badge>
                    </div>
                    <p className="muted">risk ×{scope.risk_multiplier} · {scope.reason}</p>
                    {scope.reason_codes?.length ? <p className="muted">reasons: {scope.reason_codes.join(', ')}</p> : null}
                    {scope.signal_candidate_id ? <p className="muted">candidate: {scope.signal_candidate_id}</p> : null}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header"><h3>Diagnostics</h3></div>
            <div className="radar-chip-grid">
              {Object.entries(diagnostics).map(([key, value]) => (
                <span className="radar-chip radar-chip--muted" key={key}>{key}: {value}</span>
              ))}
              {payload?.diskError ? <span className="radar-chip radar-chip--danger">disk: {payload.diskError}</span> : null}
            </div>
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
