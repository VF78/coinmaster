import { useEffect, useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';

export function App() {
  const [page, setPage] = useState<'dashboard' | 'history'>('dashboard');

  useEffect(() => {
    document.title = page === 'dashboard' ? 'Paper Trading Dashboard' : 'Trade History & Stats';
  }, [page]);

  return (
    <div className="container">
      <header>
        <h1>Paper Trading Control Panel</h1>
        <nav>
          <button onClick={() => setPage('dashboard')} className={page === 'dashboard' ? 'active' : ''}>Dashboard</button>
          <button onClick={() => setPage('history')} className={page === 'history' ? 'active' : ''}>History / Stats</button>
        </nav>
      </header>
      {page === 'dashboard' ? <DashboardPage /> : <HistoryPage />}
    </div>
  );
}
