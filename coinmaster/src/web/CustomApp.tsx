import { useEffect, useMemo, useRef, useState } from 'react';
import { TradingRulesPage } from './pages/TradingRulesPage';
import { useDialog } from './components/DialogProvider';
import { Card } from './components/Card';
import { Badge } from './components/Badge';

 type PageKey = 'trading-rules' | 'radar' | 'backtest';

const SECTIONS: Array<{ key: PageKey; label: string }> = [
  { key: 'trading-rules', label: 'Trading Rules' },
  { key: 'radar', label: 'Radar' },
  { key: 'backtest', label: 'Backtest' },
];

function RadarPlaceholderPage() {
  return (
    <main className="terminal-layout radar-simple-page">
      <Card title="Radar" className="terminal-card radar-simple-card" actions={<Badge tone="neutral">Stage 2</Badge>}>
        <div className="radar-simple-stack">
          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Observation plane</h3>
              <Badge tone="neutral">offline</Badge>
            </div>
            <p className="muted">
              Radar UI placeholder is mounted here for the operator flow. The old Radar runtime is intentionally not connected in Stage 1.
            </p>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Planned controls</h3>
            </div>
            <div className="radar-chip-grid">
              <span className="radar-chip radar-chip--muted">context policy</span>
              <span className="radar-chip radar-chip--muted">entry locks</span>
              <span className="radar-chip radar-chip--muted">risk multiplier</span>
              <span className="radar-chip radar-chip--muted">direction mode</span>
              <span className="radar-chip radar-chip--muted">TTL / reason codes</span>
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
          {page === 'radar' ? <RadarPlaceholderPage /> : null}
          {page === 'backtest' ? <BacktestPlaceholderPage /> : null}
        </section>
      </div>
    </div>
  );
}
