import { useEffect, useState } from 'react';
import type { HistoryResponse, Position, StatsPeriod, TradeEvent, TradeLog } from '../../shared/dto.js';
import { getHistory } from '../lib/api';
import { formatDate, formatMoney, formatMoneyWithPercent, formatNumber } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';

export function HistoryPage() {
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [period, setPeriod] = useState<StatsPeriod>('week');

  async function refresh(selectedPeriod: StatsPeriod = period) {
    const next = await getHistory(selectedPeriod);
    setData(next);
  }

  useEffect(() => {
    refresh(period);
  }, [period]);

  if (!data) {
    return <p className="muted">Loading history…</p>;
  }

  return (
    <main className="layout-grid">
      <Card
        title="Trade statistics"
        actions={
          <div className="actions-row">
            <div className="period-switch" role="tablist" aria-label="History period">
              <button
                type="button"
                className={period === 'week' ? 'period-switch__btn period-switch__btn--active' : 'period-switch__btn'}
                onClick={() => setPeriod('week')}
              >
                Week
              </button>
              <button
                type="button"
                className={period === 'month' ? 'period-switch__btn period-switch__btn--active' : 'period-switch__btn'}
                onClick={() => setPeriod('month')}
              >
                Month
              </button>
            </div>
            <Button onClick={() => refresh()} variant="secondary">Refresh</Button>
          </div>
        }
      >
        <div className="stats-grid">
          <Stat label="Total trades" value={String(data.stats.totalTrades)} />
          <Stat label="Win rate" value={`${formatNumber(data.stats.winRate)}%`} />
          <Stat label="Avg PnL / trade" value={formatMoney(data.stats.avgPnl)} tone={data.stats.avgPnl >= 0 ? 'success' : 'danger'} />
          <Stat
            label="Realized PnL"
            value={formatMoneyWithPercent(data.stats.realizedPnl, data.stats.realizedPnlPct)}
            tone={data.stats.realizedPnl >= 0 ? 'success' : 'danger'}
          />
        </div>
      </Card>

      <Card title="Closed positions" className="full-width">
        <DataTable<Position>
          rows={data.closedPositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => `${formatDate(row.openedAt)} • Coins: ${formatNumber(row.size)}`}
          columns={[
            { key: 'openedAt', header: 'Opened', render: (row) => formatDate(row.openedAt) },
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'entry', header: 'Entry', render: (row) => formatNumber(row.entryPrice) },
            { key: 'coins', header: 'Coins', render: (row) => formatNumber(row.size) },
            { key: 'deal', header: 'Deal value', render: (row) => formatMoney(row.entryPrice * row.size) },
            { key: 'pnl', header: 'Close PnL', render: (row) => <span className={row.pnl >= 0 ? 'up' : 'down'}>{formatMoney(row.pnl)}</span> },
            { key: 'source', header: 'Source', render: (row) => row.source }
          ]}
        />
      </Card>

      <Card title="Trade event journal (append-only)" className="full-width">
        <DataTable<TradeEvent>
          rows={data.events}
          mobileTitle={(row) => `${row.type.toUpperCase()} • ${row.symbol}`}
          mobileSubtitle={(row) => `${formatDate(row.timestamp)} • seq ${row.seq}`}
          columns={[
            { key: 'seq', header: 'Seq', render: (row) => String(row.seq) },
            { key: 'timestamp', header: 'Timestamp', render: (row) => formatDate(row.timestamp) },
            { key: 'type', header: 'Event', render: (row) => row.type.toUpperCase() },
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'reason', header: 'Reason', render: (row) => row.reason ?? '—' },
            { key: 'corr', header: 'Correlation', render: (row) => row.correlationId.slice(0, 10) },
            {
              key: 'pnl',
              header: 'PnL',
              render: (row) => (typeof row.pnl === 'number' ? <span className={row.pnl >= 0 ? 'up' : 'down'}>{formatMoney(row.pnl)}</span> : '—')
            }
          ]}
        />
      </Card>

      <Card title="Legacy trade log" className="full-width">
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
