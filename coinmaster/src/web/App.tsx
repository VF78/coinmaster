import { useEffect, useMemo, useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { SettingsPage } from './pages/SettingsPage';

type PageKey = 'dashboard' | 'history' | 'settings';

const SECTIONS: Array<{ key: PageKey; label: string }> = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'history', label: 'History' },
  { key: 'settings', label: 'Settings' }
];

export function App() {
  const [page, setPage] = useState<PageKey>('dashboard');

  const pageTitle = useMemo(() => {
    if (page === 'history') return 'Trading copilot · History';
    if (page === 'settings') return 'Trading copilot · Settings';
    return 'Trading copilot · Dashboard';
  }, [page]);

  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <h1>Trading copilot</h1>
      </header>

      <div className="app-layout">
        <aside className="sidebar" aria-label="Sections">
          <nav className="sidebar-nav">
            {SECTIONS.map((section) => (
              <button
                key={section.key}
                type="button"
                className={page === section.key ? 'sidebar-nav__item sidebar-nav__item--active' : 'sidebar-nav__item'}
                onClick={() => setPage(section.key)}
              >
                {section.label}
              </button>
            ))}
          </nav>
        </aside>

        <section className="app-content">
          {page === 'dashboard' ? <DashboardPage /> : null}
          {page === 'history' ? <HistoryPage /> : null}
          {page === 'settings' ? <SettingsPage /> : null}
        </section>
      </div>
    </div>
  );
}
