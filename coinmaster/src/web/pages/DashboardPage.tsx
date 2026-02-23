import { useEffect, useMemo, useRef, useState } from 'react';
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

type PnlPeriod = 'daily' | 'weekly' | 'monthly';

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<LivePosition | null>(null);
  const [orderDraft, setOrderDraft] = useState<OrderDraft | null>(null);
  const [pnlPeriod, setPnlPeriod] = useState<PnlPeriod>('daily');
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    const next = await getDashboard();
    setData(next);
  }

  useEffect(() => {
    refresh();
    refreshTimer.current = setInterval(refresh, 5000);
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
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

    return {
      liveEquity,
      liveAvailable,
      liveUsed,
      liveOpenPnl
    };
  }, [data]);

  function getPnlValue(): number {
    if (!data) return 0;
    switch (pnlPeriod) {
      case 'daily': return data.live.pnl.dailyNetUsd;
      case 'weekly': return data.live.pnl.weeklyNetUsd;
      case 'monthly': return data.live.pnl.monthlyNetUsd;
    }
  }

  function getPnlLabel(): string {
    switch (pnlPeriod) {
      case 'daily': return 'Daily P&L';
      case 'weekly': return 'Weekly P&L';
      case 'monthly': return 'Monthly P&L';
    }
  }

  if (!data || !metrics) {
    return <p className="muted">Loading live terminal…</p>;
  }

  const pnlValue = getPnlValue();

  return (
    <main className="terminal-layout">
      <section className="layout-grid layout-grid--terminal">
        <Card
          title="Account overview (Hyperliquid)"
          className="terminal-card"
          actions={
            <Badge tone={data.live.connected ? 'success' : 'danger'}>
              {data.live.connected ? 'CONNECTED' : 'DISCONNECTED'}
            </Badge>
          }
        >
          <div className="stats-grid">
            <Stat label="Equity" value={metrics.liveEquity !== undefined ? formatMoney(metrics.liveEquity) : '—'} tone="default" />
            <Stat label="Available" value={metrics.liveAvailable !== undefined ? formatMoney(metrics.liveAvailable) : '—'} tone="default" />
            <Stat label="Used margin" value={metrics.liveUsed !== undefined ? formatMoney(metrics.liveUsed) : '—'} tone="default" />
            <Stat
              label={getPnlLabel()}
              value={formatMoney(pnlValue)}
              tone={pnlValue >= 0 ? 'success' : 'danger'}
            />
            <Stat label="Open orders" value={String(data.live.openOrders)} />
            <Stat label="Open positions" value={String(data.live.openPositions.length)} />
            <Stat
              label="Unrealized P&L"
              value={data.live.openPositions.length ? formatMoney(metrics.liveOpenPnl) : '—'}
              tone={metrics.liveOpenPnl >= 0 ? 'success' : 'danger'}
            />
          </div>
          <p className="muted stat-note" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            P&amp;L period:{' '}
            {(['daily', 'weekly', 'monthly'] as PnlPeriod[]).map((p) => (
              <Button
                key={p}
                variant={pnlPeriod === p ? 'primary' : 'secondary'}
                onClick={() => setPnlPeriod(p)}
                style={{ padding: '0.15rem 0.5rem', fontSize: '0.8rem' }}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </Button>
            ))}
          </p>
          <p className="muted stat-note">
            Last update: {data.latestTick ? formatDate(data.latestTick.timestamp) : '—'}
            {data.live.error ? ` • Error: ${data.live.error}` : ''}
            {data.live.mode.manualConfirmation ? ' • Manual confirmation is active — new positions require approval before execution.' : ''}
          </p>
        </Card>

        <Card title="Execution controls" className="terminal-card terminal-card--narrow">
          <p className="muted stat-note" style={{ marginBottom: '0.75rem' }}>
            Manual confirmation: <strong>{data.live.mode.manualConfirmation ? 'ON' : 'OFF'}</strong>
            {' • '}Limits: <strong>30 USDC / {formatNumber(data.live.mode.maxLeverage)}x</strong>
          </p>

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

      <Card title="Live open positions" className="full-width terminal-card">
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

      <Card
        title="Positions to confirm"
        className="full-width terminal-card"
        actions={
          data.live.pendingConfirmations.length > 0
            ? <Badge tone="danger">{data.live.pendingConfirmations.length} PENDING</Badge>
            : undefined
        }
      >
        {data.live.pendingConfirmations.length > 0 && (
          <div style={{ background: 'var(--danger-bg, rgba(239,68,68,0.1))', border: '1px solid var(--danger, #ef4444)', borderRadius: '6px', padding: '0.75rem 1rem', marginBottom: '0.75rem' }}>
            <p style={{ margin: 0, fontWeight: 600 }}>
              <Badge tone="danger">ACTION REQUIRED</Badge>{' '}
              Подтвердите открытие — TP/SL установятся после подтверждения.
            </p>
            <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.85rem' }}>
              Telegram-бот отправит уведомление. После подтверждения позиция перейдёт в Live open positions.
            </p>
            <a
              href="https://t.me/your-bot"
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-block', marginTop: '0.5rem', color: 'var(--accent, #3b82f6)', fontWeight: 500 }}
            >
              Перейти к Telegram &rarr;
            </a>
          </div>
        )}
        <p className="muted stat-note" style={{ marginBottom: '0.75rem' }}>
          Positions listed below are waiting for manual approval before being executed on the exchange.
          You will also receive a Telegram notification when a new position requires confirmation.
        </p>
        {data.live.pendingConfirmations.length === 0 ? (
          <p className="muted">No positions awaiting confirmation.</p>
        ) : (
          <>
            <DataTable<LivePosition>
              rows={data.live.pendingConfirmations}
              mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
              mobileSubtitle={(row) => {
                const dealValue = row.dealValue !== undefined ? formatMoney(row.dealValue) : '—';
                return `Deal: ${dealValue}`;
              }}
              emptyText="No positions awaiting confirmation."
              columns={[
                { key: 'symbol', header: 'Symbol', render: (row) => row.symbol },
                { key: 'side', header: 'Side', render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
                { key: 'entry', header: 'Entry', render: (row) => (row.entryPrice !== undefined ? formatNumber(row.entryPrice) : '—') },
                { key: 'coins', header: 'Size (BTC)', render: (row) => formatNumber(row.size) },
                { key: 'deal', header: 'Deal value', render: (row) => (row.dealValue !== undefined ? formatMoney(row.dealValue) : '—') },
                { key: 'lev', header: 'Leverage', render: (row) => (row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—') },
                {
                  key: 'status',
                  header: 'Status',
                  render: () => <span className="muted">awaiting confirmation</span>
                },
              ]}
            />
            <div style={{ marginTop: '0.75rem' }}>
              <Button
                variant="primary"
                onClick={() => { console.log('[confirm] Opening confirmation dialog for pending positions'); alert('Confirmation dialog — placeholder'); }}
                fullWidth
              >
                Подтвердить сделку
              </Button>
            </div>
          </>
        )}
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
