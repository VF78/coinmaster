import { useEffect, useState } from 'react';
import { ResearchPage, RuntimePage, StrategyPage, WorkspaceSettingsPage } from './pages/NautilusControlPage';
import { Button } from './components/Button';
import { logoutGuiSession } from './lib/nautilusApi';

type PageKey = 'dashboard' | 'strategy' | 'research' | 'settings';
const SECTIONS: Array<{ key: PageKey; label: string; icon: string }> = [
  { key: 'dashboard', label: 'Dashboard', icon: '▦' },
  { key: 'strategy', label: 'Strategy', icon: '◈' },
  { key: 'research', label: 'Backtest', icon: '▥' },
  { key: 'settings', label: 'Settings', icon: '⚙' },
];

export function App() {
  const [page, setPage] = useState<PageKey>('dashboard');
  const [sessionError, setSessionError] = useState('');
  const active = SECTIONS.find((section) => section.key === page) ?? SECTIONS[0];
  useEffect(() => { document.title = `Coinmaster24 · ${active.label}`; }, [active.label]);
  useEffect(() => { window.localStorage.removeItem('coinmaster-api-token'); }, []);
  return <div className="app-shell nautilus-app-shell">
    <header className="app-topbar nautilus-topbar">
      <div className="nautilus-brand"><span className="nautilus-brand__mark">C</span><div><h1>Coinmaster<span>24</span></h1><p>BTC · SOL trading workspace</p></div></div>
      <div className="nautilus-topbar__right"><span className="nautilus-environment">Sandbox · live orders off</span><Button variant="secondary" onClick={() => { void logoutGuiSession().catch((error: unknown) => setSessionError(error instanceof Error ? error.message : 'Sign out failed.')); }}>Sign out</Button></div>
    </header>
    {sessionError ? <p role="alert" className="nautilus-alert">{sessionError}</p> : null}
    <div className="app-layout">
      <aside className="sidebar nautilus-sidebar" aria-label="Trading workspace"><nav className="sidebar-nav" aria-label="Main navigation"><ul className="sidebar-nav__list">
        {SECTIONS.map((section) => <li key={section.key}><button type="button" aria-current={page === section.key ? 'page' : undefined} className={page === section.key ? 'sidebar-nav__item sidebar-nav__item--active' : 'sidebar-nav__item'} onClick={() => setPage(section.key)}><span aria-hidden="true" className="nautilus-nav-icon">{section.icon}</span><span>{section.label}</span></button></li>)}
      </ul></nav></aside>
      <section className="app-content" aria-label={active.label}>
        <div className="nautilus-page-heading"><div><h2>{active.label}</h2></div><p>BTC / SOL <span>·</span> Public data + virtual execution</p></div>
        {page === 'strategy' ? <StrategyPage /> : null}{page === 'research' ? <ResearchPage /> : null}{page === 'dashboard' ? <RuntimePage /> : null}{page === 'settings' ? <WorkspaceSettingsPage /> : null}
      </section>
    </div>
  </div>;
}
