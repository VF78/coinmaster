import { useEffect, useState } from 'react';

type Position = {
  id: string;
  symbol: string;
  side: 'long' | 'short';
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  pnl: number;
  size: number;
  source: 'manual' | 'sim';
};

export function DashboardPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [latestBias, setLatestBias] = useState('off');
  const [stats, setStats] = useState<any>(null);
  const [price, setPrice] = useState('43000');

  async function refresh() {
    const res = await fetch('/api/dashboard');
    const data = await res.json();
    setPositions(data.activePositions);
    setLatestBias(data.latestBias);
    setStats(data.stats);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function sendBias(bias: 'long' | 'short' | 'off') {
    await fetch('/api/bias', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ symbol: 'BTC', bias })
    });
    await refresh();
  }

  async function simulateTick() {
    await fetch('/api/simulate/tick', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ symbol: 'BTC', price: Number(price) })
    });
    await refresh();
  }

  return (
    <main>
      <section className="card">
        <h2>Manual Bias Control (BTC)</h2>
        <p>Current bias: <strong>{latestBias}</strong></p>
        <div className="row">
          <button onClick={() => sendBias('long')}>BTC long</button>
          <button onClick={() => sendBias('short')}>BTC short</button>
          <button onClick={() => sendBias('off')}>BTC off</button>
        </div>
      </section>

      <section className="card">
        <h2>Simulation Tick</h2>
        <div className="row">
          <input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="BTC mark price" />
          <button onClick={simulateTick}>Run tick</button>
          <button onClick={refresh}>Refresh</button>
        </div>
      </section>

      <section className="card">
        <h2>Active Positions</h2>
        <table>
          <thead>
            <tr><th>Symbol</th><th>Side</th><th>Entry</th><th>SL</th><th>TP</th><th>PnL</th><th>Source</th></tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.id}>
                <td>{p.symbol}</td><td>{p.side}</td><td>{p.entryPrice}</td><td>{p.stopLoss}</td><td>{p.takeProfit}</td>
                <td className={p.pnl >= 0 ? 'up' : 'down'}>{p.pnl}</td><td>{p.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {stats && (
        <section className="card">
          <h2>Quick Stats</h2>
          <p>Total closed trades: {stats.totalTrades} | Win rate: {stats.winRate}% | Realized PnL: {stats.realizedPnl} | Open PnL: {stats.openPnl}</p>
        </section>
      )}
    </main>
  );
}
