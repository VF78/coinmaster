import { useEffect } from 'react';
import { DashboardPage } from './pages/DashboardPage';

const NAV_ITEMS = ['Trade', 'Portfolio', 'Vaults', 'History'];

export function App() {
  useEffect(() => {
    document.title = 'CoinMaster Dashboard';
  }, []);

  return (
    <div className="app-shell">
      <header className="terminal-header">
        <div className="terminal-brand">
          <span className="terminal-logo" aria-hidden="true">∿</span>
          <div>
            <p className="eyebrow">CoinMaster</p>
            <h1>BTC Trading Terminal</h1>
          </div>
        </div>

        <nav className="terminal-nav" aria-label="Primary">
          {NAV_ITEMS.map((item, index) => (
            <button
              key={item}
              type="button"
              className={index === 0 ? 'terminal-nav__item terminal-nav__item--active' : 'terminal-nav__item'}
              disabled={index !== 0}
            >
              {item}
            </button>
          ))}
        </nav>

        <div className="terminal-header__status">
          <span className="status-pill status-pill--live">Live</span>
          <span className="status-pill">Owner-only access</span>
        </div>
      </header>

      <DashboardPage />
    </div>
  );
}
