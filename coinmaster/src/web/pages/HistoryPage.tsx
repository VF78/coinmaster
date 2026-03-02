import { useEffect, useMemo, useState } from 'react';
import type { LiveFill, LiveHistoryResponse } from '../../shared/dto.js';
import { getLiveHistory } from '../lib/api';
import { formatDate, formatMoney, formatNumber } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';

const PAGE_SIZE = 15;

export function HistoryPage() {
  const [data, setData] = useState<LiveHistoryResponse | null>(null);
  const [page, setPage] = useState(1);

  async function refresh() {
    const next = await getLiveHistory();
    setData(next);
    setPage(1);
  }

  useEffect(() => {
    refresh();
  }, []);

  const paging = useMemo(() => {
    const fills = data?.fills ?? [];
    const total = fills.length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const safePage = Math.min(page, pages);
    const start = (safePage - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    return {
      rows: fills.slice(start, end),
      total,
      pages,
      page: safePage,
      from: total === 0 ? 0 : start + 1,
      to: Math.min(end, total),
    };
  }, [data, page]);

  if (!data) {
    return <p className="muted">Loading trade history…</p>;
  }

  return (
    <main className="terminal-layout">
      <Card
        title="Trade history (live exchange fills)"
        className="full-width terminal-card"
        actions={<Button variant="secondary" onClick={() => refresh()}>Refresh</Button>}
      >
        <DataTable<LiveFill>
          rows={paging.rows}
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

        <div className="history-paging">
          <span className="muted">Showing {paging.from}–{paging.to} of {paging.total}</span>
          <div className="actions-row">
            <Button variant="secondary" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={paging.page <= 1}>
              Prev
            </Button>
            <span className="muted">Page {paging.page} / {paging.pages}</span>
            <Button variant="secondary" onClick={() => setPage((p) => Math.min(paging.pages, p + 1))} disabled={paging.page >= paging.pages}>
              Next
            </Button>
          </div>
        </div>
      </Card>
    </main>
  );
}
