import { useEffect, useState } from 'react';
import type { Bias, DashboardResponse, Position } from '../../shared/dto.js';
import { postBias, postTick, getDashboard } from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [price, setPrice] = useState('43000');
  const [isLoading, setIsLoading] = useState(false);

  async function refresh() {
    const next = await getDashboard();
    setData(next);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function sendBias(bias: Bias) {
    setIsLoading(true);
    try {
      await postBias({ symbol: 'BTC', bias });
      await refresh();
    } finally {
      setIsLoading(false);
    }
  }

  async function simulateTick() {
    setIsLoading(true);
    try {
      await postTick({ symbol: 'BTC', price: Number(price) });
      await refresh();
    } finally {
      setIsLoading(false);
    }
  }

  if (!data) {
    return <p className="muted">Loading dashboard…</p>;
  }

  const pnlTone = data.stats.openPnl >= 0 ? 'success' : 'danger';

  return (
    <main className="layout-grid">
      <Card title="Performance overview">
        <div className="stats-grid">
          <Stat label="Closed trades" value={String(data.stats.totalTrades)} />
          <Stat label="Win rate" value={`${formatNumber(data.stats.winRate)}%`} />
          <Stat label="Realized PnL" value={formatMoney(data.stats.realizedPnl)} tone={data.stats.realizedPnl >= 0 ? 'success' : 'danger'} />
          <Stat label="Open PnL" value={formatMoney(data.stats.openPnl)} tone={pnlTone} />
        </div>
      </Card>

      <Card title="Manual bias control (BTC)">
        <p className="stack-row">
          Current signal: <Badge tone={data.latestBias === 'off' ? 'neutral' : data.latestBias === 'long' ? 'success' : 'danger'}>{data.latestBias.toUpperCase()}</Badge>
        </p>
        <div className="actions-row">
          <Button onClick={() => sendBias('long')} disabled={isLoading}>BTC Long</Button>
          <Button onClick={() => sendBias('short')} variant="danger" disabled={isLoading}>BTC Short</Button>
          <Button onClick={() => sendBias('off')} variant="secondary" disabled={isLoading}>BTC Off</Button>
        </div>
      </Card>

      <Card title="Simulation tick">
        <div className="field-row">
          <label htmlFor="price-input">BTC mark price</label>
          <input
            id="price-input"
            inputMode="decimal"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            placeholder="43000"
          />
        </div>
        <div className="actions-row">
          <Button onClick={simulateTick} disabled={isLoading}>Run tick</Button>
          <Button onClick={refresh} variant="secondary" disabled={isLoading}>Refresh</Button>
        </div>
      </Card>

      <Card title="Active positions" className="full-width">
        <DataTable<Position>
          rows={data.activePositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => `Source: ${row.source}`}
          emptyText="No open positions. Use controls above to submit a bias and run ticks."
          columns={[
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'entry', header: 'Entry', render: (row) => formatNumber(row.entryPrice) },
            { key: 'sl', header: 'Stop loss', render: (row) => formatNumber(row.stopLoss) },
            { key: 'tp', header: 'Take profit', render: (row) => formatNumber(row.takeProfit) },
            {
              key: 'pnl',
              header: 'PnL',
              render: (row) => <span className={row.pnl >= 0 ? 'up' : 'down'}>{formatMoney(row.pnl)}</span>
            },
            { key: 'source', header: 'Source', render: (row) => row.source }
          ]}
        />
      </Card>
    </main>
  );
}
