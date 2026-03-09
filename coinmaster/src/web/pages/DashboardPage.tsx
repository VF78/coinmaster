import { useEffect, useMemo, useRef, useState } from 'react';
import type { Bias, DashboardClassBiasControl, DashboardCustomBiasControl, DashboardResponse, LiveCandle, LivePosition } from '../../shared/dto.js';
import { postBias, getDashboard, getLiveCandles, getTradingRules, confirmPendingConfirmation, rejectPendingConfirmation, friendlyCodeMessage, friendlyErrorMessage } from '../lib/api';
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

const BIAS_OPTIONS: Bias[] = ['long', 'short', 'off'];

type FvgTf = '1h' | '4h';

type FvgStateRow = {
  id: string;
  timeframe: FvgTf;
  direction: 'bullish' | 'bearish';
  zoneBottom: number;
  zoneTop: number;
  triggerPrice: number;
  currentPrice: number;
  inRetraceZone: boolean;
  distanceToTriggerPct: number;
  candleTimestamp: string;
};

function detectFvgState(candles: LiveCandle[], timeframe: FvgTf, currentPrice: number, fvgRetracePct: number): FvgStateRow | null {
  if (!Array.isArray(candles) || candles.length < 4 || !Number.isFinite(currentPrice)) return null;

  const closed = candles.slice(0, -1);
  const lookback = 10;
  const start = Math.max(2, closed.length - lookback);

  type Zone = { direction: 'bullish' | 'bearish'; top: number; bottom: number; candleTimestamp: string };
  const zones: Zone[] = [];

  for (let i = start; i < closed.length; i++) {
    const c0 = closed[i - 2];
    const c2 = closed[i];

    if (c0.high < c2.low) {
      zones.push({ direction: 'bullish', top: c2.low, bottom: c0.high, candleTimestamp: c2.timestamp });
    }
    if (c0.low > c2.high) {
      zones.push({ direction: 'bearish', top: c0.low, bottom: c2.high, candleTimestamp: c2.timestamp });
    }
  }

  if (!zones.length) return null;
  const zone = zones[zones.length - 1];
  const range = zone.top - zone.bottom;
  const triggerPrice = zone.direction === 'bullish'
    ? zone.top - range * (fvgRetracePct / 100)
    : zone.bottom + range * (fvgRetracePct / 100);

  const inRetraceZone = zone.direction === 'bullish'
    ? currentPrice <= triggerPrice && currentPrice >= zone.bottom
    : currentPrice >= triggerPrice && currentPrice <= zone.top;

  const distanceToTriggerPct = Number.isFinite(triggerPrice) && triggerPrice > 0
    ? Number((((currentPrice - triggerPrice) / triggerPrice) * 100).toFixed(2))
    : 0;

  return {
    id: `fvg-${timeframe}`,
    timeframe,
    direction: zone.direction,
    zoneBottom: zone.bottom,
    zoneTop: zone.top,
    triggerPrice: Number(triggerPrice.toFixed(2)),
    currentPrice: Number(currentPrice.toFixed(2)),
    inRetraceZone,
    distanceToTriggerPct,
    candleTimestamp: zone.candleTimestamp,
  };
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const dialog = useDialog();
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<LivePosition | null>(null);
  const [pnlPeriod, setPnlPeriod] = useState<PnlPeriod>('daily');
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [biasActionKey, setBiasActionKey] = useState<string | null>(null);
  const [fvgRows, setFvgRows] = useState<FvgStateRow[]>([]);
  const [fvgRetrace, setFvgRetrace] = useState<number>(50);
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    const [next, rulesResp, c1h, c4h] = await Promise.all([
      getDashboard(),
      getTradingRules().catch(() => null),
      getLiveCandles('BTC', '1h', 140).catch(() => null),
      getLiveCandles('BTC', '4h', 140).catch(() => null),
    ]);

    setData(next);

    const retrace = Number(rulesResp?.rules?.fvgRetrace ?? 50);
    const normalizedRetrace = Number.isFinite(retrace) ? Math.max(10, Math.min(90, retrace)) : 50;
    setFvgRetrace(normalizedRetrace);

    const currentPrice = Number(next.latestTick?.price ?? c1h?.candles?.[c1h.candles.length - 1]?.close ?? NaN);
    const rows: FvgStateRow[] = [];
    if (c1h?.candles?.length) {
      const s = detectFvgState(c1h.candles, '1h', currentPrice, normalizedRetrace);
      if (s) rows.push(s);
    }
    if (c4h?.candles?.length) {
      const s = detectFvgState(c4h.candles, '4h', currentPrice, normalizedRetrace);
      if (s) rows.push(s);
    }
    setFvgRows(rows);

    return next;
  }

  useEffect(() => {
    refresh();
    refreshTimer.current = setInterval(refresh, 5000);
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
  }, []);

  async function sendClassBias(control: DashboardClassBiasControl, bias: Bias) {
    const key = `class:${control.assetClass}:${bias}`;
    setIsLoading(true);
    setBiasActionKey(key);
    try {
      await postBias({ targetType: 'class', assetClass: control.assetClass, bias });
      await refresh();
    } finally {
      setIsLoading(false);
      setBiasActionKey(null);
    }
  }

  async function sendCustomSymbolBias(control: DashboardCustomBiasControl, bias: Bias) {
    const key = `symbol:${control.symbol}:${bias}`;
    setIsLoading(true);
    setBiasActionKey(key);
    try {
      await postBias({ targetType: 'symbol', symbol: control.symbol, bias });
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

  function renderCompactBiasToggle(params: {
    current: Bias;
    loadingKeyPrefix: string;
    onSelect: (bias: Bias) => void;
  }) {
    return (
      <div className="exec-bias-toggle">
        {BIAS_OPTIONS.map((option) => {
          const active = params.current === option;
          const key = `${params.loadingKeyPrefix}:${option}`;
          return (
            <Button
              key={key}
              variant={option === 'short' ? 'danger' : option === 'long' ? 'primary' : 'secondary'}
              onClick={() => params.onSelect(option)}
              disabled={isLoading}
              className={`exec-bias-btn ${active ? 'exec-bias-btn--active' : ''} ${option === 'off' ? 'exec-bias-btn--off' : ''} ${biasActionKey === key ? 'exec-bias-btn--loading' : ''}`}
            >
              {option.toUpperCase()}
            </Button>
          );
        })}
      </div>
    );
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
          <div className="exec-bias-list">
            {data.classBiasControls.length === 0 && (
              <p className="muted">No asset classes available (no enabled assets).</p>
            )}

            {data.classBiasControls.map((control) => (
              <div
                key={`class-bias-${control.assetClass}`}
                className="exec-bias-row"
                title={control.symbols.join(', ')}
              >
                <span className="exec-bias-label" style={{ textTransform: 'capitalize' }}>{control.assetClass}</span>
                {renderCompactBiasToggle({
                  current: control.bias,
                  loadingKeyPrefix: `class:${control.assetClass}`,
                  onSelect: (bias) => { void sendClassBias(control, bias); },
                })}
              </div>
            ))}

            {data.customBiasControls.length > 0 && (
              <>
                <p className="muted" style={{ margin: '0.1rem 0 0', fontSize: 12 }}>Custom assets</p>
                {data.customBiasControls.map((control) => (
                  <div key={`custom-bias-${control.symbol}`} className="exec-bias-row">
                    <span className="exec-bias-label">{control.symbol}</span>
                    {renderCompactBiasToggle({
                      current: control.bias,
                      loadingKeyPrefix: `symbol:${control.symbol}`,
                      onSelect: (bias) => { void sendCustomSymbolBias(control, bias); },
                    })}
                  </div>
                ))}
              </>
            )}
          </div>
        </Card>

        <Card title="BTC FVG monitor" className="terminal-card full-width">
          <p className="muted stat-note" style={{ marginBottom: '0.45rem' }}>
            Retrace level: {fvgRetrace}% • Source: exchange candles (1h/4h)
          </p>
          <DataTable<FvgStateRow>
            rows={fvgRows}
            emptyText="No FVG zones detected in current lookback window."
            mobileTitle={(row) => `${row.timeframe.toUpperCase()} ${row.direction.toUpperCase()}`}
            mobileSubtitle={(row) => `Trigger ${formatNumber(row.triggerPrice)} • Dist ${row.distanceToTriggerPct}%`}
            columns={[
              { key: 'tf', header: 'TF', render: (row) => row.timeframe.toUpperCase() },
              { key: 'dir', header: 'Direction', render: (row) => <Badge tone={row.direction === 'bullish' ? 'success' : 'danger'}>{row.direction}</Badge> },
              { key: 'zone', header: 'Zone', render: (row) => `${formatNumber(row.zoneBottom)} - ${formatNumber(row.zoneTop)}` },
              { key: 'trigger', header: 'Trigger', render: (row) => formatNumber(row.triggerPrice) },
              { key: 'current', header: 'Current', render: (row) => formatNumber(row.currentPrice) },
              { key: 'dist', header: 'Dist to trigger', render: (row) => `${row.distanceToTriggerPct}%` },
              { key: 'state', header: 'State', render: (row) => <Badge tone={row.inRetraceZone ? 'success' : 'neutral'}>{row.inRetraceZone ? 'IN RETRACE ZONE' : 'WAITING'}</Badge> },
              { key: 'ts', header: 'Zone candle', render: (row) => formatDate(row.candleTimestamp) },
            ]}
          />
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
                const trigger = row.source ?? '—';
                return `Deal: ${dealValue} • Trigger: ${trigger}`;
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
                { key: 'trigger', header: 'Trigger',      render: (row) => <span className="muted">{row.source ?? '—'}</span> },
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
                    const updated = next.live.openPositions.find((p: LivePosition) => p.symbol === current.symbol && p.side === current.side);
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
