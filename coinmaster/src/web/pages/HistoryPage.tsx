import { useEffect, useState } from 'react';
import type { HistoryResponse, Position, TradeLog } from '../../shared/dto.js';
import { getHistory } from '../lib/api';
import { formatDate, formatMoney, formatNumber } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';

export function HistoryPage() {
  const [data, setData] = useState<HistoryResponse | null>(null);

  async function refresh() {
    const next = await getHistory();
    setData(next);
  }

  useEffect(() => {
    refresh();
  }, []);

  if (!data) {
    return <p className="muted">Loading history…</p>;
  }

  return (
    <main className="layout-grid">
      <Card
        title="Trade statistics"
        actions={<Button onClick={refresh} variant="secondary">Refresh</Button>}
      >
        <div className="stats-grid">
          <Stat label="Total trades" value={String(data.stats.totalTrades)} />
          <Stat label="Win rate" value={`${formatNumber(data.stats.winRate)}%`} />
          <Stat label="Avg PnL / trade" value={formatMoney(data.stats.avgPnl)} tone={data.stats.avgPnl >= 0 ? 'success' : 'danger'} />
          <Stat label="Realized PnL" value={formatMoney(data.stats.realizedPnl)} tone={data.stats.realizedPnl >= 0 ? 'success' : 'danger'} />
        </div>
      </Card>

      <Card title="Closed positions" className="full-width">
        <DataTable<Position>
          rows={data.closedPositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => formatDate(row.openedAt)}
          columns={[
            { key: 'openedAt', header: 'Opened', render: (row) => formatDate(row.openedAt) },
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'entry', header: 'Entry', render: (row) => formatNumber(row.entryPrice) },
            { key: 'pnl', header: 'Close PnL', render: (row) => <span className={row.pnl >= 0 ? 'up' : 'down'}>{formatMoney(row.pnl)}</span> },
            { key: 'source', header: 'Source', render: (row) => row.source }
          ]}
        />
      </Card>

      <Card title="Audit log" className="full-width">
        <DataTable<TradeLog>
          rows={data.logs}
          mobileTitle={(row) => `${row.action.toUpperCase()} • ${row.symbol}`}
          mobileSubtitle={(row) => formatDate(row.timestamp)}
          columns={[
            { key: 'timestamp', header: 'Timestamp', render: (row) => formatDate(row.timestamp) },
            { key: 'action', header: 'Action', render: (row) => row.action.toUpperCase() },
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'note', header: 'Note', render: (row) => row.note ?? '—' },
            {
              key: 'pnl',
              header: 'PnL',
              render: (row) => (typeof row.pnl === 'number' ? <span className={row.pnl >= 0 ? 'up' : 'down'}>{formatMoney(row.pnl)}</span> : '—')
            }
          ]}
        />
      </Card>
    </main>
  );
}
