import { useEffect, useState } from 'react';
import type { LiveFill, LiveHistoryResponse } from '../../shared/dto.js';
import { getLiveHistory } from '../lib/api';
import { formatDate, formatMoney, formatNumber } from '../lib/format';
import { Badge } from '../components/Badge';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';

export function HistoryPage() {
  const [data, setData] = useState<LiveHistoryResponse | null>(null);

  async function refresh() {
    const next = await getLiveHistory();
    setData(next);
  }

  useEffect(() => {
    refresh();
  }, []);

  if (!data) {
    return <p className="muted">Loading trade history…</p>;
  }

  return (
    <main className="terminal-layout">
      <Card title="Trade history (live exchange fills)" className="full-width terminal-card">
        <DataTable<LiveFill>
          rows={data.fills}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()} ${formatNumber(row.size)}`}
          mobileSubtitle={(row) => `${formatDate(row.timestamp)} • ${row.direction ?? 'fill'}`}
          emptyText="No live fills yet."
          columns={[
            { key: 'ts', header: 'Time', render: (row) => formatDate(row.timestamp) },
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'buy' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'dir', header: 'Direction', render: (row) => row.direction ?? '—' },
            { key: 'price', header: 'Price', render: (row) => formatNumber(row.price) },
            { key: 'size', header: 'Size', render: (row) => formatNumber(row.size) },
            { key: 'fee', header: 'Fee', render: (row) => (row.feeUsd !== undefined ? formatMoney(-Math.abs(row.feeUsd)) : '—') },
            {
              key: 'closedPnl',
              header: 'Closed PnL',
              render: (row) => (row.closedPnlUsd !== undefined
                ? <span className={row.closedPnlUsd >= 0 ? 'up' : 'down'}>{formatMoney(row.closedPnlUsd)}</span>
                : '—')
            }
          ]}
        />
      </Card>
    </main>
  );
}
