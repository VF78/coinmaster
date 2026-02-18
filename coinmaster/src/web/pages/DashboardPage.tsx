import { useEffect, useMemo, useState } from 'react';
import type { Bias, DashboardResponse, LivePosition } from '../../shared/dto.js';
import { postBias, getDashboard } from '../lib/api';
import { formatDate, formatMoney, formatNumber } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';
import { PositionLevelsPanel } from '../components/PositionLevelsPanel';
import { OrderConfirmModal, type OrderDraft } from '../components/OrderConfirmModal';

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<LivePosition | null>(null);
  const [orderDraft, setOrderDraft] = useState<OrderDraft | null>(null);

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

  const metrics = useMemo(() => {
    if (!data) return null;

    const liveEquity = data.live.account?.equityUsd;
    const liveAvailable = data.live.account?.availableUsd;
    const liveUsed = data.live.account?.usedMarginUsd;
    const liveOpenPnl = data.live.openPositions.reduce((sum, p) => sum + (p.unrealizedPnl ?? 0), 0);
    const totalExposure = data.live.openPositions.reduce((sum, p) => sum + (p.dealValue ?? 0), 0);

    return {
      liveEquity,
      liveAvailable,
      liveUsed,
      liveOpenPnl,
      totalExposure
    };
  }, [data]);

  if (!data || !metrics) {
    return <p className="muted">Loading live terminal…</p>;
  }

  return (
    <main className="terminal-layout">
      <section className="layout-grid layout-grid--terminal">
        <Card
          title="Account overview (real, Hyperliquid)"
          className="terminal-card"
          actions={<Button onClick={() => refresh()} variant="secondary" disabled={isLoading}>Refresh data</Button>}
        >
          <div className="stats-grid">
            <Stat label="Account equity" value={metrics.liveEquity !== undefined ? formatMoney(metrics.liveEquity) : '—'} tone="default" />
            <Stat label="Available to trade" value={metrics.liveAvailable !== undefined ? formatMoney(metrics.liveAvailable) : '—'} tone="default" />
            <Stat label="Used margin" value={metrics.liveUsed !== undefined ? formatMoney(metrics.liveUsed) : '—'} tone="default" />
            <Stat label="Open exposure" value={metrics.totalExposure > 0 ? formatMoney(metrics.totalExposure) : '—'} tone="default" />
            <Stat
              label="Weekly P&L"
              value={formatMoney(data.live.pnl.weeklyNetUsd)}
              tone={data.live.pnl.weeklyNetUsd >= 0 ? 'success' : 'danger'}
            />
            <Stat
              label="Monthly P&L"
              value={formatMoney(data.live.pnl.monthlyNetUsd)}
              tone={data.live.pnl.monthlyNetUsd >= 0 ? 'success' : 'danger'}
            />
            <Stat label="Open orders" value={String(data.live.openOrders)} />
            <Stat label="Open positions" value={String(data.live.openPositions.length)} />
            <Stat
              label="Open uPnL"
              value={data.live.openPositions.length ? formatMoney(metrics.liveOpenPnl) : '—'}
              tone={metrics.liveOpenPnl >= 0 ? 'success' : 'danger'}
            />
            <Stat label="BTC mark" value={data.latestTick ? formatMoney(data.latestTick.price) : '—'} />
          </div>
          <p className="muted stat-note">
            Status: <Badge tone={data.live.connected ? 'success' : 'danger'}>{data.live.connected ? 'CONNECTED' : 'DISCONNECTED'}</Badge>
            {' • '}Manual confirmation: <strong>{data.live.mode.manualConfirmation ? 'ON' : 'OFF'}</strong>
            {' • '}Limits: <strong>{formatNumber(data.live.mode.maxNotionalUsdc)} USDC</strong> / <strong>{formatNumber(data.live.mode.maxLeverage)}x</strong>
          </p>
          <p className="muted stat-note">
            Last market update: {data.latestTick ? formatDate(data.latestTick.timestamp) : '—'}
            {data.live.error ? ` • Live error: ${data.live.error}` : ''}
          </p>
        </Card>

        <Card title="Execution controls" className="terminal-card terminal-card--narrow">
          <p className="stack-row">
            Current signal:
            <Badge tone={data.latestBias === 'off' ? 'neutral' : data.latestBias === 'long' ? 'success' : 'danger'}>
              {data.latestBias.toUpperCase()}
            </Badge>
          </p>

          <div className="bias-buttons">
            <Button onClick={() => sendBias('long')} disabled={isLoading} fullWidth>Buy / Long</Button>
            <Button onClick={() => sendBias('short')} variant="danger" disabled={isLoading} fullWidth>Sell / Short</Button>
            <Button onClick={() => sendBias('off')} variant="secondary" disabled={isLoading} fullWidth>Pause (OFF)</Button>
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '1rem 0' }} />
          <p className="muted" style={{ marginBottom: '0.5rem' }}>Manual order (live exchange):</p>
          <div className="bias-buttons">
            <Button
              onClick={() => {
                const price = data?.latestTick?.price ?? 0;
                setOrderDraft({
                  symbol: 'BTC',
                  side: 'buy',
                  price,
                  size: 0.001,
                  leverage: 3,
                });
              }}
              disabled={!data?.live.connected}
              fullWidth
            >
              Place Order
            </Button>
          </div>
        </Card>
      </section>

      <Card title="Live open positions (exchange)" className="full-width terminal-card">
        <DataTable<LivePosition>
          rows={data.live.openPositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => {
            const dealValue = row.dealValue !== undefined ? formatMoney(row.dealValue) : '—';
            const lev = row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—';
            return `Deal: ${dealValue} • Lev: ${lev}`;
          }}
          emptyText={data.live.connected ? 'No open live positions on exchange.' : 'Live account is not connected yet.'}
          columns={[
            { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'entry', header: 'Entry', render: (row) => (row.entryPrice !== undefined ? formatNumber(row.entryPrice) : '—') },
            { key: 'coins', header: 'Size (BTC)', render: (row) => formatNumber(row.size) },
            { key: 'deal', header: 'Deal value', render: (row) => (row.dealValue !== undefined ? formatMoney(row.dealValue) : '—') },
            { key: 'lev', header: 'Leverage', render: (row) => (row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—') },
            { key: 'sl', header: 'Stop loss', render: (row) => (row.stopLoss !== undefined ? formatNumber(row.stopLoss) : '—') },
            { key: 'tp', header: 'Take profit', render: (row) => (row.takeProfit !== undefined ? formatNumber(row.takeProfit) : '—') },
            { key: 'openedAt', header: 'Opened at', render: (row) => (row.openedAt ? formatDate(row.openedAt) : '—') },
            {
              key: 'upnl',
              header: 'uPnL',
              render: (row) => (typeof row.unrealizedPnl === 'number'
                ? <span className={row.unrealizedPnl >= 0 ? 'up' : 'down'}>{formatMoney(row.unrealizedPnl)}</span>
                : '—')
            },
            {
              key: 'manage',
              header: 'Manage',
              render: (row) => (
                <Button variant="secondary" onClick={() => setSelectedPosition(row)}>
                  Chart + SL/TP
                </Button>
              )
            }
          ]}
        />
      </Card>

      {selectedPosition ? (
        <Card title="Position chart / risk levels" className="full-width terminal-card">
          <PositionLevelsPanel
            position={selectedPosition}
            onClose={() => setSelectedPosition(null)}
            onApplied={async () => {
              await refresh();
              setSelectedPosition(null);
            }}
          />
        </Card>
      ) : null}

      {orderDraft && (
        <OrderConfirmModal
          draft={orderDraft}
          onClose={() => setOrderDraft(null)}
          onSuccess={() => { refresh(); }}
        />
      )}
    </main>
  );
}
