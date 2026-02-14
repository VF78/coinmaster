import { useEffect, useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { Button } from './components/Button';

export function App() {
  const [page, setPage] = useState<'dashboard' | 'history'>('dashboard');

  useEffect(() => {
    document.title = page === 'dashboard' ? 'CoinMaster Dashboard' : 'Trade History & Stats';
  }, [page]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">CoinMaster</p>
          <h1>Trading Control Panel</h1>
        </div>
        <nav aria-label="Main navigation" className="nav-tabs">
          <Button variant={page === 'dashboard' ? 'primary' : 'secondary'} onClick={() => setPage('dashboard')}>
            Dashboard
          </Button>
          <Button variant={page === 'history' ? 'primary' : 'secondary'} onClick={() => setPage('history')}>
            History / Stats
          </Button>
        </nav>
      </header>
      {page === 'dashboard' ? <DashboardPage /> : <HistoryPage />}
    </div>
  );
}
