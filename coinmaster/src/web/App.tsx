import { useEffect } from 'react';
import { DashboardPage } from './pages/DashboardPage';

export function App() {
  useEffect(() => {
    document.title = 'CoinMaster Dashboard';
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">CoinMaster</p>
          <h1>Trading Control Panel</h1>
        </div>
      </header>
      <DashboardPage />
    </div>
  );
}
