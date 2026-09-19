import { useEffect, useMemo, useState } from 'react';
import { ResearchPage, RuntimePage, StrategyPage } from './pages/NautilusControlPage';

type PageKey = 'strategy' | 'research' | 'runtime';
const SECTIONS: Array<{ key: PageKey; label: string }> = [
  { key: 'strategy', label: 'Strategy' }, { key: 'research', label: 'Research' }, { key: 'runtime', label: 'Runtime' },
];
export function App() {
  const [page, setPage] = useState<PageKey>('strategy');
  const pageTitle = useMemo(() => `Coinmaster24 · ${SECTIONS.find((s) => s.key === page)?.label ?? 'Strategy'}`, [page]);
  useEffect(() => { document.title = pageTitle; }, [pageTitle]);
  return <div className="app-shell"><header className="app-topbar"><h1>Coinmaster24</h1></header><div className="app-layout"><aside className="sidebar" aria-label="Sections"><nav className="sidebar-nav"><ul className="sidebar-nav__list">{SECTIONS.map((section) => <li key={section.key}><button type="button" className={page === section.key ? 'sidebar-nav__item sidebar-nav__item--active' : 'sidebar-nav__item'} onClick={() => setPage(section.key)}>{section.label}</button></li>)}</ul></nav></aside><section className="app-content">{page === 'strategy' ? <StrategyPage /> : null}{page === 'research' ? <ResearchPage /> : null}{page === 'runtime' ? <RuntimePage /> : null}</section></div></div>;
}
