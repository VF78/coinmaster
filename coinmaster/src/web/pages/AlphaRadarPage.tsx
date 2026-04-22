import { useEffect, useMemo, useRef, useState } from 'react';
import type {
  RadarRuntimeSettings,
  RadarSignalCandidateGroup,
  RadarSignalVerdict,
  RadarSignalView,
  RadarSignalsResponse,
  TradingCoinAllocation,
  TradingRulesSettings,
} from '../../shared/dto.js';
import { getRadarRuntimeSettings, getRadarSignals, getTradingRules, saveRadarRuntimeSettings, friendlyErrorMessage } from '../lib/api';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';
import { Stat } from '../components/Stat';
import { formatDate, formatMoney, formatNumber } from '../lib/format';

const REFRESH_MS = 5_000;

function formatAge(value?: string): string {
  const parsed = value ? Date.parse(value) : Number.NaN;
  if (!Number.isFinite(parsed)) return '—';

  const seconds = Math.max(0, Math.round((Date.now() - parsed) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function statusTone(status: RadarSignalView['status']): 'success' | 'danger' | 'neutral' {
  if (status === 'auto_order_placed') return 'success';
  if (status === 'rejected') return 'danger';
  return 'neutral';
}

function verdictTone(verdict: RadarSignalVerdict): 'success' | 'danger' | 'neutral' {
  if (verdict === 'actionable') return 'success';
  if (verdict === 'ignore') return 'danger';
  return 'neutral';
}

function sideTone(side: 'buy' | 'sell'): 'success' | 'danger' {
  return side === 'buy' ? 'success' : 'danger';
}

function compactMeta(meta?: RadarSignalView['sourceMeta']): string {
  return [meta?.connector, meta?.kind, meta?.channel].filter(Boolean).join(' · ') || '—';
}

function countRows<T extends { id: string }>(rows: Array<T>): Array<T> {
  return rows;
}

export function AlphaRadarPage() {
  const [runtime, setRuntime] = useState<RadarRuntimeSettings | null>(null);
  const [rules, setRules] = useState<TradingRulesSettings | null>(null);
  const [signals, setSignals] = useState<RadarSignalsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const refreshInFlightRef = useRef<Promise<void> | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    if (refreshInFlightRef.current) return refreshInFlightRef.current;

    const run = (async () => {
      const [runtimeResp, rulesResp, signalsResp] = await Promise.all([
        getRadarRuntimeSettings().catch(() => null),
        getTradingRules().catch(() => null),
        getRadarSignals(200).catch(() => null),
      ]);

      if (runtimeResp?.runtime) setRuntime(runtimeResp.runtime);
      if (rulesResp?.rules) setRules(rulesResp.rules);
      if (signalsResp) setSignals(signalsResp);
      if (isLoading) setIsLoading(false);
    })().catch((error) => {
      if (isLoading) setIsLoading(false);
      setMessage(`Radar refresh failed: ${friendlyErrorMessage(error, 'Could not refresh Radar.')}`);
    });

    refreshInFlightRef.current = run.finally(() => {
      refreshInFlightRef.current = null;
    });

    return refreshInFlightRef.current;
  }

  useEffect(() => {
    void refresh();
    refreshTimerRef.current = setInterval(() => {
      void refresh();
    }, REFRESH_MS);
    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, []);

  async function updateRuntime(next: Partial<RadarRuntimeSettings>) {
    if (!runtime) return;
    setIsSaving(true);
    setMessage('Saving Radar runtime…');
    try {
      const result = await saveRadarRuntimeSettings(next);
      setRuntime(result.runtime);
      setMessage('Radar runtime saved.');
      await refresh();
    } catch (error) {
      setMessage(`Save failed: ${friendlyErrorMessage(error, 'Could not save Radar runtime.')}`);
    } finally {
      setIsSaving(false);
    }
  }

  const monitoredCoins = useMemo(() => (rules?.coins ?? []).filter((coin) => coin.enabled), [rules]);
  const signalGroups = signals?.summary.candidateGroups ?? [];
  const rawSignals = signals?.signals ?? [];
  const activeSignals = useMemo(
    () => rawSignals.filter((signal) => signal.status === 'pending_confirmation' || signal.status === 'auto_order_placed'),
    [rawSignals],
  );

  const monitoredRows = useMemo(() => {
    return monitoredCoins.map((coin: TradingCoinAllocation) => {
      const coinSignals = rawSignals.filter((signal) => signal.symbol === coin.symbol);
      const coinGroups = signalGroups.filter((group) => group.symbol === coin.symbol);
      const best = coinGroups.sort((a, b) => b.bestScore - a.bestScore || b.signalCount - a.signalCount)[0];
      return {
        id: coin.symbol,
        symbol: coin.symbol,
        assetClass: coin.assetClass ?? 'crypto',
        allocationPct: coin.pct,
        signalCount: coinSignals.length,
        bestScore: best?.bestScore,
        bestVerdict: best?.verdict,
        lastSeenAt: best?.lastSeenAt,
        sideMix: [...new Set(coinSignals.map((signal) => signal.side))].join(', ') || '—',
      };
    });
  }, [monitoredCoins, rawSignals, signalGroups]);

  const sourceRows = useMemo(() => countRows((signals?.summary.qualityBySource ?? []).map((row) => ({ id: row.source, ...row }))), [signals]);
  const connectorRows = useMemo(() => countRows((signals?.summary.qualityByConnector ?? []).map((row) => ({ id: row.connector, ...row }))), [signals]);

  const latestSignalRows = useMemo(() => rawSignals.slice(0, 20).map((row) => ({
    ...row,
    id: row.id,
  })), [rawSignals]);

  const runtimeEnabled = runtime?.enabled ?? false;
  const runtimeAutoConfirm = runtime?.autoConfirm ?? false;

  if (isLoading && !runtime && !rules && !signals) {
    return <p className="muted">Loading Alpha Radar…</p>;
  }

  return (
    <main className="terminal-layout radar-layout">
      <Card
        title="Alpha Radar runtime"
        className="terminal-card full-width"
        actions={
          <div className="actions-row">
            <Badge tone={runtimeEnabled ? 'success' : 'danger'}>{runtimeEnabled ? 'ENABLED' : 'PAUSED'}</Badge>
            <Badge tone={runtimeAutoConfirm ? 'success' : 'neutral'}>{runtimeAutoConfirm ? 'AUTO-CONFIRM' : 'MANUAL REVIEW'}</Badge>
          </div>
        }
      >
        <div className="stats-grid" style={{ marginBottom: '0.85rem' }}>
          <Stat label="Ingested signals" value={String(signals?.summary.total ?? 0)} />
          <Stat label="Active groups" value={String(signalGroups.length)} />
          <Stat label="Monitored assets" value={String(monitoredCoins.length)} />
          <Stat label="Pending handoff" value={String(activeSignals.length)} />
        </div>

        <p className="muted" style={{ marginBottom: '0.75rem' }}>
          Upstream-only Radar: signals enter through the shared handoff flow, monitored symbols come from Trading Rules, and auto-confirm here only affects Radar ingest.
        </p>

        <div className="actions-row" style={{ marginBottom: '0.6rem' }}>
          <Button
            variant={runtimeEnabled ? 'secondary' : 'primary'}
            onClick={() => { void updateRuntime({ enabled: !runtimeEnabled }); }}
            disabled={isSaving || !runtime}
          >
            {runtimeEnabled ? 'Pause Radar' : 'Resume Radar'}
          </Button>
          <Button
            variant={runtimeAutoConfirm ? 'danger' : 'primary'}
            onClick={() => { void updateRuntime({ autoConfirm: !runtimeAutoConfirm }); }}
            disabled={isSaving || !runtime}
          >
            {runtimeAutoConfirm ? 'Disable auto-confirm' : 'Enable auto-confirm'}
          </Button>
        </div>

        {message ? <p className="muted radar-note">{message}</p> : null}
        <p className="muted radar-note">
          Runtime defaults: enabled on, auto-confirm off. Dedup window: 5m. History cap: 500.
        </p>
      </Card>

      <div className="radar-grid">
        <Card title="Monitored assets" className="terminal-card">
          <DataTable
            rows={monitoredRows}
            mobileTitle={(row) => row.symbol}
            mobileSubtitle={(row) => `${row.assetClass} · ${row.signalCount} signal groups`}
            emptyText="No enabled assets in Trading Rules."
            columns={[
              { key: 'symbol', header: 'Symbol', render: (row) => <strong>{row.symbol}</strong> },
              { key: 'assetClass', header: 'Asset class', render: (row) => row.assetClass },
              { key: 'allocationPct', header: 'Allocation', render: (row) => `${formatNumber(row.allocationPct)}%` },
              { key: 'signalCount', header: 'Radar groups', render: (row) => row.signalCount ? String(row.signalCount) : '—' },
              { key: 'bestScore', header: 'Best score', render: (row) => row.bestScore !== undefined ? String(row.bestScore) : '—' },
              { key: 'bestVerdict', header: 'Best verdict', render: (row) => row.bestVerdict ? <Badge tone={verdictTone(row.bestVerdict)}>{row.bestVerdict}</Badge> : '—' },
              { key: 'lastSeenAt', header: 'Last seen', render: (row) => row.lastSeenAt ? formatAge(row.lastSeenAt) : '—' },
              { key: 'sideMix', header: 'Sides', render: (row) => row.sideMix },
            ]}
          />
        </Card>

        <Card title="Current signal groups" className="terminal-card">
          <DataTable
            rows={signalGroups.map((row) => ({ ...row, id: `${row.symbol}:${row.side}` }))}
            mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
            mobileSubtitle={(row) => row.verdictReason ?? '—'}
            emptyText="No signal groups yet."
            columns={[
              { key: 'symbol', header: 'Symbol', render: (row) => <strong>{row.symbol}</strong> },
              { key: 'side', header: 'Side', render: (row) => <Badge tone={sideTone(row.side)}>{row.side}</Badge> },
              { key: 'signalCount', header: 'Signals', render: (row) => String(row.signalCount) },
              { key: 'bestScore', header: 'Best score', render: (row) => String(row.bestScore) },
              { key: 'verdict', header: 'Verdict', render: (row) => <Badge tone={verdictTone(row.verdict)}>{row.verdictLabel}</Badge> },
              { key: 'sources', header: 'Sources', render: (row) => row.sources.join(', ') || '—' },
              { key: 'lastSeenAt', header: 'Last seen', render: (row) => row.lastSeenAt ? formatDate(row.lastSeenAt) : '—' },
            ]}
          />
        </Card>
      </div>

      <Card title="Live feed" className="terminal-card full-width">
        <div className="radar-feed-strip" aria-label="Recent Radar feed items">
          {latestSignalRows.slice(0, 5).map((row) => (
            <article
              key={row.id}
              className={`radar-feed-tile ${Date.now() - Date.parse(row.updatedAt || row.createdAt) <= 10 * 60_000 ? 'radar-feed-tile--fresh' : ''}`}
            >
              <span className="radar-feed-tile__dot" />
              <div className="radar-feed-tile__body">
                <div className="radar-feed-tile__top">
                  <strong>{row.symbol}</strong>
                  <Badge tone={statusTone(row.status)}>{row.status}</Badge>
                  <span className="muted">{formatAge(row.updatedAt || row.createdAt)}</span>
                </div>
                <p>{row.source} · {row.reason}</p>
              </div>
            </article>
          ))}
        </div>

        <DataTable
          rows={latestSignalRows}
          mobileTitle={(row) => `${row.symbol} ${row.side.toUpperCase()}`}
          mobileSubtitle={(row) => `${row.source} · ${row.verdictReason ?? '—'}`}
          emptyText="No signals have been ingested yet."
          columns={[
            { key: 'createdAt', header: 'Seen', render: (row) => <span className="radar-feed__seen">{formatAge(row.updatedAt || row.createdAt)}</span> },
            { key: 'symbol', header: 'Symbol', render: (row) => <strong>{row.symbol}</strong> },
            { key: 'side', header: 'Side', render: (row) => <Badge tone={sideTone(row.side)}>{row.side}</Badge> },
            { key: 'source', header: 'Source', render: (row) => row.source },
            { key: 'meta', header: 'Meta', render: (row) => <span className="muted">{compactMeta(row.sourceMeta)}</span> },
            { key: 'status', header: 'Status', render: (row) => <Badge tone={statusTone(row.status)}>{row.status}</Badge> },
            { key: 'verdict', header: 'Verdict', render: (row) => <Badge tone={verdictTone(row.verdict)}>{row.verdict}</Badge> },
            { key: 'score', header: 'Score', render: (row) => String(row.candidateScore) },
            { key: 'price', header: 'Price', render: (row) => formatMoney(row.price) },
            { key: 'reason', header: 'Reason', render: (row) => row.reason },
          ]}
        />
      </Card>

      <div className="radar-grid">
        <Card title="Top sources" className="terminal-card">
          <DataTable
            rows={sourceRows}
            mobileTitle={(row) => row.source}
            mobileSubtitle={(row) => `${row.total} signals`}
            emptyText="No source data yet."
            columns={[
              { key: 'source', header: 'Source', render: (row) => <strong>{row.source}</strong> },
              { key: 'count', header: 'Count', render: (row) => String(row.total) },
              { key: 'pendingConfirmation', header: 'Pending', render: (row) => String(row.pendingConfirmation) },
              { key: 'autoOrderPlaced', header: 'Auto', render: (row) => String(row.autoOrderPlaced) },
              { key: 'rejected', header: 'Rejected', render: (row) => String(row.rejected) },
              { key: 'ignored', header: 'Ignored', render: (row) => String(row.ignored) },
            ]}
          />
        </Card>

        <Card title="Top connectors" className="terminal-card">
          <DataTable
            rows={connectorRows}
            mobileTitle={(row) => row.connector}
            mobileSubtitle={(row) => `${row.total} signals`}
            emptyText="No connector data yet."
            columns={[
              { key: 'connector', header: 'Connector', render: (row) => <strong>{row.connector}</strong> },
              { key: 'count', header: 'Count', render: (row) => String(row.total) },
              { key: 'pendingConfirmation', header: 'Pending', render: (row) => String(row.pendingConfirmation) },
              { key: 'autoOrderPlaced', header: 'Auto', render: (row) => String(row.autoOrderPlaced) },
              { key: 'rejected', header: 'Rejected', render: (row) => String(row.rejected) },
              { key: 'ignored', header: 'Ignored', render: (row) => String(row.ignored) },
            ]}
          />
        </Card>
      </div>
    </main>
  );
}
