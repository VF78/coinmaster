import { useEffect, useMemo, useState } from 'react';
import { ResearchPage, RuntimePage, StrategyPage } from './pages/NautilusControlPage';
import { Badge } from './components/Badge';

type PageKey = 'strategy' | 'research' | 'runtime';
const SECTIONS: Array<{ key: PageKey; label: string; group: string }> = [
  { key: 'runtime', label: 'Runtime', group: 'MONITORING' },
  { key: 'strategy', label: 'Strategy', group: 'WORKSPACE' },
  { key: 'research', label: 'Research', group: 'WORKSPACE' },
];
export function App() {
  const [page, setPage] = useState<PageKey>('runtime');
  const active = SECTIONS.find((section) => section.key === page) ?? SECTIONS[0];
  const pageTitle = useMemo(() => `Coinmaster24 · ${active.label}`, [active.label]);
  useEffect(() => { document.title = pageTitle; }, [pageTitle]);
  const groups = [...new Set(SECTIONS.map((section) => section.group))];
  return <div className="app-shell nautilus-app-shell">
    <header className="app-topbar nautilus-topbar"><div><h1>Coinmaster24</h1><p className="muted">Nautilus operator workspace · {active.label}</p></div><Badge tone="neutral">SANDBOX · READ ONLY</Badge></header>
    <div className="app-layout">
      <aside className="sidebar nautilus-sidebar" aria-label="Nautilus sections"><nav className="sidebar-nav">
        {groups.map((group) => <section className="sidebar-group" key={group} aria-label={group.toLowerCase()}><h2 className="sidebar-group__title">{group}</h2><ul className="sidebar-nav__list">{SECTIONS.filter((section) => section.group === group).map((section) => <li key={section.key}><button type="button" aria-current={page === section.key ? 'page' : undefined} className={page === section.key ? 'sidebar-nav__item sidebar-nav__item--active' : 'sidebar-nav__item'} onClick={() => setPage(section.key)}>{section.label}</button></li>)}</ul></section>)}
      </nav></aside>
      <section className="app-content">{page === 'strategy' ? <StrategyPage /> : null}{page === 'research' ? <ResearchPage /> : null}{page === 'runtime' ? <RuntimePage /> : null}</section>
    </div>
  </div>;
}
