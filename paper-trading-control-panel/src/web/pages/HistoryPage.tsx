import { useEffect, useState } from 'react';

export function HistoryPage() {
  const [history, setHistory] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);

  async function refresh() {
    const res = await fetch('/api/history');
    const data = await res.json();
    setHistory(data.closedPositions);
    setLogs(data.logs);
    setStats(data.stats);
  }

  useEffect(() => { refresh(); }, []);

  return (
    <main>
      <section className="card">
        <h2>Trade Statistics</h2>
        {stats && <p>Total trades: {stats.totalTrades} | Win rate: {stats.winRate}% | Avg PnL/trade: {stats.avgPnl} | Realized PnL: {stats.realizedPnl}</p>}
        <button onClick={refresh}>Refresh</button>
      </section>

      <section className="card">
        <h2>Closed Positions</h2>
        <table>
          <thead>
            <tr><th>Opened</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Close PnL</th><th>Source</th></tr>
          </thead>
          <tbody>
            {history.map((p) => (
              <tr key={p.id}><td>{new Date(p.openedAt).toLocaleString()}</td><td>{p.symbol}</td><td>{p.side}</td><td>{p.entryPrice}</td><td className={p.pnl >= 0 ? 'up' : 'down'}>{p.pnl}</td><td>{p.source}</td></tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Audit Log (bias + trade events)</h2>
        <ul>
          {logs.map((log) => (
            <li key={log.id}>{new Date(log.timestamp).toLocaleString()} — {log.action.toUpperCase()} — {log.note ?? ''} {log.pnl ? `(pnl: ${log.pnl})` : ''}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
