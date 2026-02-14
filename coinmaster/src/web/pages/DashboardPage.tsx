import { useEffect, useState } from 'react';
import type { Bias, DashboardResponse, LivePosition, Position } from '../../shared/dto.js';
import { postBias, getDashboard } from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';
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

  async function refresh() {
    const next = await getDashboard('week');
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

  if (!data) {
    return <p className="muted">Loading dashboard…</p>;
  }

  const liveEquity = data.live.account?.equityUsd;
  const liveAvailable = data.live.account?.availableUsd;
  const liveUsed = liveEquity !== undefined && liveAvailable !== undefined ? liveEquity - liveAvailable : undefined;
  const liveOpenPnl = data.live.openPositions.reduce((sum, p) => sum + (p.unrealizedPnl ?? 0), 0);

  return (
    <main className="layout-grid">
      <Card
        title="Account overview (real, Hyperliquid)"
        actions={
          <div className="actions-row">
            <Badge tone={data.live.connected ? 'success' : 'danger'}>{data.live.connected ? 'CONNECTED' : 'DISCONNECTED'}</Badge>
            <Button onClick={() => refresh()} variant="secondary" disabled={isLoading}>Refresh</Button>
          </div>
        }
      >
        <div className="stats-grid">
          <Stat label="Account equity" value={liveEquity !== undefined ? formatMoney(liveEquity) : '—'} tone="default" />
          <Stat label="Available" value={liveAvailable !== undefined ? formatMoney(liveAvailable) : '—'} tone="default" />
          <Stat label="Used margin" value={liveUsed !== undefined ? formatMoney(liveUsed) : '—'} tone="default" />
          <Stat
            label="Open uPnL"
            value={data.live.openPositions.length ? formatMoney(liveOpenPnl) : '—'}
            tone={liveOpenPnl >= 0 ? 'success' : 'danger'}
          />
          <Stat label="Open orders" value={String(data.live.openOrders)} />
          <Stat label="Open positions" value={String(data.live.openPositions.length)} />
          <Stat label="BTC mark" value={data.latestTick ? formatMoney(data.latestTick.price) : '—'} />
        </div>
        <p className="muted stat-note">
          Manual confirmation: {data.live.mode.manualConfirmation ? 'ON' : 'OFF'}
          {' • '}Limits: {formatNumber(data.live.mode.maxNotionalUsdc)} USDC / {formatNumber(data.live.mode.maxLeverage)}x
          {data.live.error ? ` • Live error: ${data.live.error}` : ''}
        </p>
      </Card>

      <Card
        title="Manual bias control (BTC)"
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

      <Card title="Strategy positions (internal/paper state)" className="full-width">
        <DataTable<Position>
          rows={data.activePositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => `Coins: ${formatNumber(row.size)} • Deal: ${formatMoney(row.entryPrice * row.size)}`}
          emptyText="No open internal positions."
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
