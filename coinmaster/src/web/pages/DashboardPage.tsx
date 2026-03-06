import { useEffect, useMemo, useRef, useState } from 'react';
import type { Bias, DashboardBiasControl, DashboardResponse, LivePosition } from '../../shared/dto.js';
import { postBias, getDashboard, confirmPendingConfirmation, rejectPendingConfirmation, friendlyCodeMessage, friendlyErrorMessage } from '../lib/api';
import { formatDate, formatMoney, formatNumber } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';
import { PositionLevelsPanel } from '../components/PositionLevelsPanel';
import { useDialog } from '../components/DialogProvider';

type PnlPeriod = 'daily' | 'weekly' | 'monthly';

const PNL_CYCLE: PnlPeriod[] = ['daily', 'weekly', 'monthly'];

const PNL_LABEL: Record<PnlPeriod, string> = {
  daily: 'Daily P&L',
  weekly: 'Weekly P&L',
  monthly: 'Monthly P&L',
};

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const dialog = useDialog();
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<LivePosition | null>(null);
  const [pnlPeriod, setPnlPeriod] = useState<PnlPeriod>('daily');
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [biasActionKey, setBiasActionKey] = useState<string | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    const next = await getDashboard();
    setData(next);
    return next;
  }

  useEffect(() => {
    refresh();
    refreshTimer.current = setInterval(refresh, 5000);
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
  }, []);

  async function sendGlobalBias(bias: Bias) {
    const globalSymbol = data?.latestTick?.symbol || 'BTC';
    setIsLoading(true);
    setBiasActionKey(`global:${bias}`);
    try {
      await postBias({ symbol: globalSymbol, bias });
      await refresh();
    } finally {
      setIsLoading(false);
      setBiasActionKey(null);
    }
  }

  async function sendAssetBias(control: DashboardBiasControl, bias: Bias) {
    const key = `${control.symbol}:${bias}`;
    const globalSymbol = data?.latestTick?.symbol || 'BTC';
    setIsLoading(true);
    setBiasActionKey(key);
    try {
      const target = control.mode === 'global' ? globalSymbol : control.symbol;
      await postBias({ symbol: target, bias });
      await refresh();
    } finally {
      setIsLoading(false);
      setBiasActionKey(null);
    }
  }

  function cyclePnlPeriod() {
    setPnlPeriod(prev => {
      const idx = PNL_CYCLE.indexOf(prev);
      return PNL_CYCLE[(idx + 1) % PNL_CYCLE.length];
    });
  }

  async function handleConfirmPending(row: LivePosition) {
    setPendingActionId(row.id);
    try {
      const result = await confirmPendingConfirmation(row.id);
      if (!result.ok) {
        throw new Error(friendlyCodeMessage(result.error || 'confirm_failed', 'Could not confirm this signal.'));
      }
      await refresh();
    } catch (error) {
      await dialog.alert({
        title: 'Confirm failed',
        message: friendlyErrorMessage(error, 'Could not confirm this signal. Please try again.'),
        confirmText: 'OK',
      });
    } finally {
      setPendingActionId(null);
    }
  }

  async function handleRejectPending(row: LivePosition) {
    setPendingActionId(row.id);
    try {
      const result = await rejectPendingConfirmation(row.id);
      if (!result.ok) {
        throw new Error(friendlyCodeMessage(result.error || 'reject_failed', 'Could not reject this signal.'));
      }
      await refresh();
    } catch (error) {
      await dialog.alert({
        title: 'Reject failed',
        message: friendlyErrorMessage(error, 'Could not reject this signal. Please try again.'),
        confirmText: 'OK',
      });
    } finally {
      setPendingActionId(null);
    }
  }

  const metrics = useMemo(() => {
    if (!data) return null;
    return {
      liveEquity: data.live.account?.equityUsd,
      liveAvailable: data.live.account?.availableUsd,
      liveUsed: data.live.account?.usedMarginUsd,
      liveOpenPnl: data.live.openPositions.reduce((sum, p) => sum + (p.unrealizedPnl ?? 0), 0),
    };
  }, [data]);

  function getPnlValue(): number {
    if (!data) return 0;
    switch (pnlPeriod) {
      case 'daily':   return data.live.pnl.dailyNetUsd;
      case 'weekly':  return data.live.pnl.weeklyNetUsd;
      case 'monthly': return data.live.pnl.monthlyNetUsd;
    }
  }

  if (!data || !metrics) {
    return <p className="muted">Loading live terminal…</p>;
  }

  const pnlValue = getPnlValue();
  const pnlLabel = PNL_LABEL[pnlPeriod];

  const renderTakeProfits = (row: LivePosition) => {
    const levels = (Array.isArray(row.takeProfits) && row.takeProfits.length > 0
      ? row.takeProfits
      : (row.takeProfit !== undefined ? [row.takeProfit] : [])
    ).slice(0, 3);

    if (!levels.length) return '—';

    return (
      <div style={{ display: 'grid', gap: '0.12rem' }}>
        {levels.map((tp, idx) => (
          <div key={`tp-${row.id}-${idx}`}>TP{idx + 1}: {formatNumber(tp)}</div>
        ))}
      </div>
    );
  };

  return (
    <main className="terminal-layout">
      <section className="layout-grid layout-grid--terminal">
        {/* ── Account overview ────────────────────────────────── */}
        <Card
          title="Account overview (Hyperliquid)"
          className="terminal-card"
          actions={
            <Badge tone={data.live.connected ? 'success' : 'danger'}>
              {data.live.connected ? 'CONNECTED' : 'DISCONNECTED'}
            </Badge>
          }
        >
          {/* Row 1: core balances */}
          <div className="stats-grid" style={{ marginBottom: '0.75rem' }}>
            <Stat
              label="Equity"
              value={metrics.liveEquity !== undefined ? formatMoney(metrics.liveEquity) : '—'}
              tone="default"
            />
            <Stat
              label="Available"
              value={metrics.liveAvailable !== undefined ? formatMoney(metrics.liveAvailable) : '—'}
              tone="default"
            />
            <Stat
              label="Used margin"
              value={metrics.liveUsed !== undefined ? formatMoney(metrics.liveUsed) : '—'}
              tone="default"
            />
          </div>

          {/* Row 2: activity counts */}
          <div className="stats-grid" style={{ marginBottom: '0.75rem' }}>
            <Stat label="Open orders"    value={String(data.live.openOrders)} />
            <Stat label="Open positions" value={String(data.live.openPositions.length)} />
          </div>

          {/* Row 3: P&L — click anywhere to cycle Daily → Weekly → Monthly */}
          <div
            className="stats-grid"
            style={{ cursor: 'pointer', userSelect: 'none' }}
            onClick={cyclePnlPeriod}
            title="Click to cycle: Daily → Weekly → Monthly"
          >
            <Stat
              label={pnlLabel}
              value={formatMoney(pnlValue)}
              tone={pnlValue >= 0 ? 'success' : 'danger'}
            />
            <Stat
              label="Unrealized P&L"
              value={data.live.openPositions.length ? formatMoney(metrics.liveOpenPnl) : '—'}
              tone={metrics.liveOpenPnl >= 0 ? 'success' : 'danger'}
            />
          </div>

          <p className="muted stat-note" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
            Last update: {data.latestTick ? formatDate(data.latestTick.timestamp) : '—'}
            {data.live.error ? ` • Error: ${data.live.error}` : ''}
          </p>
        </Card>

        {/* ── Execution controls ───────────────────────────────── */}
        <Card title="Execution controls" className="terminal-card terminal-card--narrow">
          <p className="stack-row" style={{ marginBottom: '0.5rem' }}>
            Global bias:
            <Badge tone={data.globalBias === 'off' ? 'neutral' : data.globalBias === 'long' ? 'success' : 'danger'}>
              {data.globalBias.toUpperCase()}
            </Badge>
          </p>

          <div className="bias-buttons" style={{ marginBottom: '0.6rem' }}>
            <Button onClick={() => sendGlobalBias('long')} disabled={isLoading} fullWidth>
              {biasActionKey === 'global:long' ? 'Applying…' : 'Global Long'}
            </Button>
            <Button onClick={() => sendGlobalBias('short')} variant="danger" disabled={isLoading} fullWidth>
              {biasActionKey === 'global:short' ? 'Applying…' : 'Global Short'}
            </Button>
            <Button onClick={() => sendGlobalBias('off')} variant="secondary" disabled={isLoading} fullWidth>
              {biasActionKey === 'global:off' ? 'Applying…' : 'Global OFF'}
            </Button>
          </div>

          <p className="muted stat-note" style={{ marginBottom: '0.7rem' }}>
            Assets with <strong>mode=global</strong> follow this shared bias. Assets with <strong>mode=custom</strong> use their own bias below.
          </p>

          <div style={{ display: 'grid', gap: 10 }}>
            {data.biasControls.length === 0 ? (
              <p className="muted">No enabled trading assets configured yet.</p>
            ) : data.biasControls.map((control) => (
              <div
                key={`bias-control-${control.symbol}`}
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem',
                  background: 'var(--surface-2, rgba(148,163,184,0.08))',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                  <strong>{control.symbol}</strong>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <Badge tone="neutral">{control.assetClass}</Badge>
                    <Badge tone="neutral">{control.mode}</Badge>
                    <Badge tone={control.bias === 'off' ? 'neutral' : control.bias === 'long' ? 'success' : 'danger'}>{control.bias}</Badge>
                  </div>
                </div>

                <div className="bias-buttons">
                  <Button
                    onClick={() => sendAssetBias(control, 'long')}
                    disabled={isLoading}
                    fullWidth
                  >
                    {biasActionKey === `${control.symbol}:long` ? 'Applying…' : 'Long'}
                  </Button>
                  <Button
                    onClick={() => sendAssetBias(control, 'short')}
                    variant="danger"
                    disabled={isLoading}
                    fullWidth
                  >
                    {biasActionKey === `${control.symbol}:short` ? 'Applying…' : 'Short'}
                  </Button>
                  <Button
                    onClick={() => sendAssetBias(control, 'off')}
                    variant="secondary"
                    disabled={isLoading}
                    fullWidth
                  >
                    {biasActionKey === `${control.symbol}:off` ? 'Applying…' : 'OFF'}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* ── Live open positions ──────────────────────────────────── */}
      <Card title="Live open positions" className="full-width terminal-card">
        <DataTable<LivePosition>
          rows={data.live.openPositions}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => {
            const dealValue = row.dealValue !== undefined ? formatMoney(row.dealValue) : '—';
            const lev = row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—';
            return `Deal: ${dealValue} • Lev: ${lev}`;
          }}
          mobileActions={(row) => (
            <Button variant="secondary" onClick={() => setSelectedPosition(row)}>
              Chart
            </Button>
          )}
          emptyText={data.live.connected ? 'No open live positions on exchange.' : 'Live account is not connected yet.'}
          columns={[
            { key: 'symbol',  header: 'Symbol',     render: (row) => row.symbol },
            { key: 'side',    header: 'Side',        render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
            { key: 'entry',   header: 'Entry',       render: (row) => (row.entryPrice !== undefined ? formatNumber(row.entryPrice) : '—') },
            { key: 'coins',   header: 'Size',  render: (row) => formatNumber(row.size) },
            { key: 'deal',    header: 'Deal value',  render: (row) => (row.dealValue !== undefined ? formatMoney(row.dealValue) : '—') },
            { key: 'lev',     header: 'Leverage',    render: (row) => (row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—') },
            { key: 'sl',      header: 'Stop loss',   render: (row) => (row.stopLoss !== undefined ? formatNumber(row.stopLoss) : '—') },
            { key: 'tp',      header: 'Take profit', render: (row) => renderTakeProfits(row) },
            { key: 'openedAt',header: 'Opened at',   render: (row) => (row.openedAt ? formatDate(row.openedAt) : '—') },
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

      {/* ── Positions to confirm ─────────────────────────────────── */}
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
              Confirm execution to place the position. TP/SL orders will be attached right after confirmation.
            </p>
            <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.85rem' }}>
              If Telegram alerts are configured, a notification is sent for each pending confirmation. After approval, the position appears in Live open positions.
            </p>
            <a
              href="https://t.me/your-bot"
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-block', marginTop: '0.5rem', color: 'var(--accent, #3b82f6)', fontWeight: 500 }}
            >
              Open Telegram &rarr;
            </a>
          </div>
        )}
        <p className="muted stat-note" style={{ marginBottom: '0.75rem' }}>
          Positions listed below are waiting for manual approval before being executed on the exchange.
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
              mobileActions={(row) => (
                <div className="actions-row">
                  <Button variant="primary" onClick={() => handleConfirmPending(row)} disabled={pendingActionId === row.id}>Confirm</Button>
                  <Button variant="danger" onClick={() => handleRejectPending(row)} disabled={pendingActionId === row.id}>Reject</Button>
                </div>
              )}
              emptyText="No positions awaiting confirmation."
              columns={[
                { key: 'symbol', header: 'Symbol',     render: (row) => row.symbol },
                { key: 'side',   header: 'Side',        render: (row) => <Badge tone={row.side === 'long' ? 'success' : 'danger'}>{row.side}</Badge> },
                { key: 'entry',  header: 'Entry',       render: (row) => (row.entryPrice !== undefined ? formatNumber(row.entryPrice) : '—') },
                { key: 'coins',  header: 'Size',  render: (row) => formatNumber(row.size) },
                { key: 'deal',   header: 'Deal value',  render: (row) => (row.dealValue !== undefined ? formatMoney(row.dealValue) : '—') },
                { key: 'lev',    header: 'Leverage',    render: (row) => (row.leverage !== undefined ? `${formatNumber(row.leverage)}x` : '—') },
                { key: 'status', header: 'Status',      render: () => <span className="muted">awaiting confirmation</span> },
                {
                  key: 'actions',
                  header: 'Actions',
                  render: (row) => (
                    <div className="actions-row">
                      <Button variant="primary" onClick={() => handleConfirmPending(row)} disabled={pendingActionId === row.id}>Confirm</Button>
                      <Button variant="danger" onClick={() => handleRejectPending(row)} disabled={pendingActionId === row.id}>Reject</Button>
                    </div>
                  )
                },
              ]}
            />
          </>
        )}
      </Card>

      {/* ── Position chart / SL/TP panel ─────────────────────────── */}
      {selectedPosition ? (
        <div className="position-modal-overlay" role="dialog" aria-modal="true" aria-label="Position chart">
          <div className="position-modal-sheet">
            <Card className="full-width terminal-card">
              <PositionLevelsPanel
                position={selectedPosition}
                onClose={() => setSelectedPosition(null)}
                onApplied={async () => {
                  const next = await refresh();
                  setSelectedPosition((current) => {
                    if (!current) return current;
                    const updated = next.live.openPositions.find((p) => p.symbol === current.symbol && p.side === current.side);
                    return updated ?? current;
                  });
                }}
              />
            </Card>
          </div>
        </div>
      ) : null}
    </main>
  );
}
