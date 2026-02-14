import { useEffect, useState } from 'react';
import type { Bias, DashboardResponse, LivePosition, Position, StatsPeriod } from '../../shared/dto.js';
import { postBias, getDashboard } from '../lib/api';
import { formatDate, formatMoney, formatMoneyWithPercent, formatNumber, formatPercent } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';

function sourceLabel(source: Position['source']): string {
  if (source === 'sim') return 'paper(sim)';
  if (source === 'live') return 'live';
  return 'manual';
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [period, setPeriod] = useState<StatsPeriod>('week');

  async function refresh(selectedPeriod: StatsPeriod = period) {
    const next = await getDashboard(selectedPeriod);
    setData(next);
  }

  useEffect(() => {
    refresh(period);
  }, [period]);

  async function sendBias(bias: Bias) {
    setIsLoading(true);
    try {
      await postBias({ symbol: 'BTC', bias });
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
      <Card
        title="Performance overview"
        actions={
          <div className="period-switch" role="tablist" aria-label="Performance period">
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
        }
      >
        <div className="stats-grid">
          <Stat
            label="Equity"
            value={`${formatMoney(data.stats.equityUsd)} (${formatPercent(data.stats.equityPct)})`}
            tone={data.stats.equityPct >= 0 ? 'success' : 'danger'}
          />
          <Stat label="Closed trades" value={String(data.stats.totalTrades)} />
          <Stat label="Win rate" value={`${formatNumber(data.stats.winRate)}%`} />
          <Stat
            label="Realized PnL"
            value={formatMoneyWithPercent(data.stats.realizedPnl, data.stats.realizedPnlPct)}
            tone={data.stats.realizedPnl >= 0 ? 'success' : 'danger'}
          />
          <Stat
            label="Open PnL"
            value={formatMoneyWithPercent(data.stats.openPnl, data.stats.openPnlPct)}
            tone={pnlTone}
          />
          <Stat
            label="BTC price (live, 5m)"
            value={data.latestTick ? formatMoney(data.latestTick.price) : '—'}
          />
        </div>
        <p className="muted stat-note">
          {data.latestTick
            ? `Last update: ${formatDate(data.latestTick.timestamp)} • Auto refresh every 5 minutes`
            : 'Price feed pending…'}
        </p>
      </Card>

      <Card
        title="Live account (Hyperliquid)"
        actions={<Badge tone={data.live.connected ? 'success' : 'danger'}>{data.live.connected ? 'CONNECTED' : 'DISCONNECTED'}</Badge>}
      >
        <div className="stats-grid">
          <Stat
            label="Account equity"
            value={data.live.account?.equityUsd !== undefined ? formatMoney(data.live.account.equityUsd) : '—'}
            tone="default"
          />
          <Stat
            label="Available"
            value={data.live.account?.availableUsd !== undefined ? formatMoney(data.live.account.availableUsd) : '—'}
            tone="default"
          />
          <Stat label="Open orders" value={String(data.live.openOrders)} />
          <Stat label="Open positions" value={String(data.live.openPositions.length)} />
          <Stat label="Max notional" value={`${formatNumber(data.live.mode.maxNotionalUsdc)} USDC`} />
          <Stat label="Max leverage" value={`${formatNumber(data.live.mode.maxLeverage)}x`} />
        </div>
        <p className="muted stat-note">
          Manual confirmation: {data.live.mode.manualConfirmation ? 'ON' : 'OFF'}
          {data.live.error ? ` • Live error: ${data.live.error}` : ''}
        </p>
      </Card>

      <Card
        title="Manual bias control (BTC)"
        actions={<Button onClick={() => refresh()} variant="secondary" disabled={isLoading}>Refresh</Button>}
      >
        <p className="stack-row">
          Current signal:{' '}
          <Badge tone={data.latestBias === 'off' ? 'neutral' : data.latestBias === 'long' ? 'success' : 'danger'}>
            {data.latestBias.toUpperCase()}
          </Badge>
        </p>
        <div className="actions-row">
          <Button onClick={() => sendBias('long')} disabled={isLoading}>BTC Long</Button>
          <Button onClick={() => sendBias('short')} variant="danger" disabled={isLoading}>BTC Short</Button>
          <Button onClick={() => sendBias('off')} variant="secondary" disabled={isLoading}>BTC Off</Button>
        </div>
      </Card>

      <Card title="Live open positions (exchange)" className="full-width">
        <DataTable<LivePosition>
          rows={data.live.openPositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => `Coins: ${formatNumber(row.size)} • Lev: ${row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—'}`}
          emptyText={data.live.connected ? 'No open live positions on exchange.' : 'Live account is not connected yet.'}
          columns={[
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'entry', header: 'Entry', render: (row) => (row.entryPrice !== undefined ? formatNumber(row.entryPrice) : '—') },
            { key: 'coins', header: 'Coins', render: (row) => formatNumber(row.size) },
            { key: 'lev', header: 'Leverage', render: (row) => (row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—') },
            {
              key: 'upnl',
              header: 'uPnL',
              render: (row) => (typeof row.unrealizedPnl === 'number'
                ? <span className={row.unrealizedPnl >= 0 ? 'up' : 'down'}>{formatMoney(row.unrealizedPnl)}</span>
                : '—')
            }
          ]}
        />
      </Card>

      <Card title="Strategy positions (internal state)" className="full-width">
        <DataTable<Position>
          rows={data.activePositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => `Coins: ${formatNumber(row.size)} • Deal: ${formatMoney(row.entryPrice * row.size)}`}
          emptyText="No open internal positions. Set bias and wait for live price ticks."
          columns={[
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'entry', header: 'Entry', render: (row) => formatNumber(row.entryPrice) },
            { key: 'coins', header: 'Coins', render: (row) => formatNumber(row.size) },
            { key: 'deal', header: 'Deal value', render: (row) => formatMoney(row.entryPrice * row.size) },
            { key: 'lev', header: 'Leverage', render: (row) => (row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—') },
            { key: 'sl', header: 'Stop loss', render: (row) => formatNumber(row.stopLoss) },
            { key: 'tp', header: 'Take profit', render: (row) => formatNumber(row.takeProfit) },
            {
              key: 'pnl',
              header: 'PnL',
              render: (row) => <span className={row.pnl >= 0 ? 'up' : 'down'}>{formatMoney(row.pnl)}</span>
            },
            { key: 'source', header: 'Source', render: (row) => sourceLabel(row.source) }
          ]}
        />
      </Card>
    </main>
  );
}
