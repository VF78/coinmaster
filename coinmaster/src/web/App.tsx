import { useEffect, useMemo, useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { SettingsPage } from './pages/SettingsPage';
import { TradingRulesPage } from './pages/TradingRulesPage';

type PageKey = 'dashboard' | 'history' | 'settings' | 'trading-rules';

const SECTIONS: Array<{ key: PageKey; label: string }> = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'trading-rules', label: 'Trading Rules' },
  { key: 'history', label: 'History' },
  { key: 'settings', label: 'Settings' }
];

export function App() {
  const [page, setPage] = useState<PageKey>('dashboard');

  const pageTitle = useMemo(() => {
    const section = SECTIONS.find((s) => s.key === page);
    return `Coinmaster24 · ${section?.label ?? 'Dashboard'}`;
  }, [page]);

  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <h1>Coinmaster24</h1>
      </header>

      <div className="app-layout">
        <aside className="sidebar" aria-label="Sections">
          <nav className="sidebar-nav">
            <ul className="sidebar-nav__list">
              {SECTIONS.map((section) => (
                <li key={section.key}>
                  <button
                    type="button"
                    className={page === section.key ? 'sidebar-nav__item sidebar-nav__item--active' : 'sidebar-nav__item'}
                    onClick={() => setPage(section.key)}
                  >
                    {section.label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <section className="app-content">
          {page === 'dashboard' ? <DashboardPage /> : null}
          {page === 'history' ? <HistoryPage /> : null}
          {page === 'trading-rules' ? <TradingRulesPage /> : null}
          {page === 'settings' ? <SettingsPage /> : null}
        </section>
      </div>
    </div>
  );
}
