import { useEffect, useState } from 'react';
import { ResearchPage, RuntimePage, StrategyPage, WorkspaceSettingsPage } from './pages/NautilusControlPage';
import { Badge } from './components/Badge';
import { Button } from './components/Button';
import { getGuiSession, logoutGuiSession } from './lib/nautilusApi';

type PageKey = 'dashboard' | 'strategy' | 'research' | 'settings';
const SECTIONS: Array<{ key: PageKey; label: string; short: string; group: string; icon: string }> = [
  { key: 'dashboard', label: 'Dashboard', short: 'Home', group: 'MONITOR', icon: '▦' },
  { key: 'strategy', label: 'Strategy', short: 'Strategy', group: 'TRADE', icon: '◈' },
  { key: 'research', label: 'Backtest / Optimization', short: 'Research', group: 'RESEARCH', icon: '▥' },
  { key: 'settings', label: 'Settings', short: 'Settings', group: 'SYSTEM', icon: '⚙' },
];

export function App() {
  const [page, setPage] = useState<PageKey>('dashboard');
  const [operator, setOperator] = useState('');
  const [sessionError, setSessionError] = useState('');
  const active = SECTIONS.find((section) => section.key === page) ?? SECTIONS[0];
  useEffect(() => { document.title = `Coinmaster24 · ${active.label}`; }, [active.label]);
  useEffect(() => { window.localStorage.removeItem('coinmaster-api-token'); void getGuiSession().then((session) => setOperator(session.username)).catch(() => {}); }, []);
  const groups = [...new Set(SECTIONS.map((section) => section.group))];
  return <div className="app-shell nautilus-app-shell">
    <header className="app-topbar nautilus-topbar">
      <div className="nautilus-brand"><span className="nautilus-brand__mark">C</span><div><h1>Coinmaster<span>24</span></h1><p>Native Sandbox workspace</p></div></div>
      <div className="nautilus-topbar__right"><Badge tone="neutral">HL MAINNET DATA</Badge><Badge tone="success">LOCAL SANDBOX</Badge><span className="nautilus-operator">{operator || 'operator'}</span><Button variant="secondary" onClick={() => { void logoutGuiSession().catch((error: unknown) => setSessionError(error instanceof Error ? error.message : 'Sign out failed.')); }}>Sign out</Button></div>
    </header>
    {sessionError ? <p role="alert" className="nautilus-alert">{sessionError}</p> : null}
    <div className="app-layout">
      <aside className="sidebar nautilus-sidebar" aria-label="Nautilus sections"><nav className="sidebar-nav">
        {groups.map((group) => <section className="sidebar-group" key={group} aria-label={group.toLowerCase()}><h2 className="sidebar-group__title">{group}</h2><ul className="sidebar-nav__list">{SECTIONS.filter((section) => section.group === group).map((section) => <li key={section.key}><button type="button" aria-current={page === section.key ? 'page' : undefined} className={page === section.key ? 'sidebar-nav__item sidebar-nav__item--active' : 'sidebar-nav__item'} onClick={() => setPage(section.key)}><span aria-hidden="true" className="nautilus-nav-icon">{section.icon}</span><span className="nautilus-nav-full">{section.label}</span><span className="nautilus-nav-short">{section.short}</span></button></li>)}</ul></section>)}
      </nav><div className="nautilus-sidebar__foot"><span className="nautilus-live-dot" />Sandbox only · no live orders</div></aside>
      <section className="app-content" aria-label={active.label}>
        <div className="nautilus-page-heading"><div><p className="nautilus-kicker">{active.group} / HL STAGE-G</p><h2>{active.label}</h2></div><p>BTC / SOL <span>·</span> Public data + virtual execution</p></div>
        {page === 'strategy' ? <StrategyPage /> : null}{page === 'research' ? <ResearchPage /> : null}{page === 'dashboard' ? <RuntimePage /> : null}{page === 'settings' ? <WorkspaceSettingsPage /> : null}
      </section>
    </div>
  </div>;
}
