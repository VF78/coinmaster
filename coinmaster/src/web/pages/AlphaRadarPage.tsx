import { useEffect, useMemo, useRef, useState } from 'react';
import type {
  AlphaRadarIdea,
  AlphaRadarIdeasResponse,
  AlphaRadarLiveResponse,
  AlphaRadarSettings,
  AlphaRadarSnapshotResponse,
  RadarRuntimeSettings,
  RadarSignalVerdict,
  RadarSignalsResponse,
  TradingRulesSymbolsResponse,
} from '../../shared/dto.js';
import {
  friendlyErrorMessage,
  getAlphaRadarIdeas,
  getAlphaRadarLive,
  getAlphaRadarObservations,
  getAlphaRadarSettings,
  getRadarRuntimeSettings,
  getRadarSignals,
  getTradingRuleSymbols,
  saveAlphaRadarSettings,
  saveRadarRuntimeSettings,
} from '../lib/api';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { formatMoney } from '../lib/format';

const REFRESH_MS = 15_000;

function formatAge(value?: string): string {
  const parsed = value ? Date.parse(value) : Number.NaN;
  if (!Number.isFinite(parsed)) return '—';
  const seconds = Math.max(0, Math.round((Date.now() - parsed) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function compactText(value: string, max = 120): string {
  const text = value.replace(/\s+/g, ' ').trim();
  if (text.length <= max) return text;
  return `${text.slice(0, Math.max(0, max - 1)).trimEnd()}…`;
}

function toneFromVerdict(verdict: RadarSignalVerdict): 'success' | 'danger' | 'neutral' {
  if (verdict === 'actionable') return 'success';
  if (verdict === 'ignore') return 'danger';
  return 'neutral';
}

function toneFromHealth(status?: 'fresh' | 'stale' | 'inactive'): 'success' | 'danger' | 'neutral' {
  if (status === 'fresh') return 'success';
  if (status === 'stale') return 'danger';
  return 'neutral';
}

function toneFromIdea(verdict: AlphaRadarIdea['verdict']): 'success' | 'danger' | 'neutral' {
  if (verdict === 'idea') return 'success';
  if (verdict === 'cash') return 'danger';
  return 'neutral';
}

function toneFromSignalStatus(status: string): 'success' | 'danger' | 'neutral' {
  if (status === 'auto_order_placed') return 'success';
  if (status === 'rejected' || status === 'ignored') return 'danger';
  return 'neutral';
}

export function AlphaRadarPage() {
  const [alphaSettings, setAlphaSettings] = useState<AlphaRadarSettings | null>(null);
  const [handoffRuntime, setHandoffRuntime] = useState<RadarRuntimeSettings | null>(null);
  const [snapshot, setSnapshot] = useState<AlphaRadarSnapshotResponse | null>(null);
  const [live, setLive] = useState<AlphaRadarLiveResponse | null>(null);
  const [ideas, setIdeas] = useState<AlphaRadarIdea[]>([]);
  const [ideasPayload, setIdeasPayload] = useState<AlphaRadarIdeasResponse | null>(null);
  const [signals, setSignals] = useState<RadarSignalsResponse | null>(null);
  const [tradingSymbols, setTradingSymbols] = useState<TradingRulesSymbolsResponse | null>(null);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const refreshInFlightRef = useRef<Promise<void> | null>(null);

  async function refresh() {
    if (refreshInFlightRef.current) return refreshInFlightRef.current;
    const run = (async () => {
      const [
        alphaSettingsRes,
        handoffRuntimeRes,
        snapshotRes,
        liveRes,
        ideasRes,
        signalsRes,
        tradingSymbolsRes,
      ] = await Promise.all([
        getAlphaRadarSettings().catch(() => null),
        getRadarRuntimeSettings().catch(() => null),
        getAlphaRadarObservations(8, 'recent').catch(() => null),
        getAlphaRadarLive().catch(() => null),
        getAlphaRadarIdeas().catch(() => null),
        getRadarSignals(20).catch(() => null),
        getTradingRuleSymbols().catch(() => null),
      ]);

      if (alphaSettingsRes?.settings) setAlphaSettings(alphaSettingsRes.settings);
      if (handoffRuntimeRes?.runtime) setHandoffRuntime(handoffRuntimeRes.runtime);
      if (snapshotRes) setSnapshot(snapshotRes);
      if (liveRes) setLive(liveRes);
      if (ideasRes) {
        setIdeas(ideasRes.ideas);
        setIdeasPayload(ideasRes);
      }
      if (signalsRes) setSignals(signalsRes);
      if (tradingSymbolsRes) setTradingSymbols(tradingSymbolsRes);
      setIsLoading(false);
    })().catch((error) => {
      setIsLoading(false);
      setMessage(`Radar refresh failed: ${friendlyErrorMessage(error, 'Could not refresh Radar.')}`);
    });
    refreshInFlightRef.current = run.finally(() => {
      refreshInFlightRef.current = null;
    });
    return refreshInFlightRef.current;
  }

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, []);

  async function toggleRadar() {
    if (!alphaSettings || !handoffRuntime) return;
    const nextEnabled = !(alphaSettings.enabled && handoffRuntime.enabled);
    setBusyKey('radar-toggle');
    try {
      const [alphaResult, handoffResult] = await Promise.all([
        saveAlphaRadarSettings({ ...alphaSettings, enabled: nextEnabled }),
        saveRadarRuntimeSettings({ enabled: nextEnabled }),
      ]);
      setAlphaSettings(alphaResult.settings);
      setHandoffRuntime(handoffResult.runtime);
      setMessage(nextEnabled ? 'Radar enabled.' : 'Radar disabled.');
      await refresh();
    } catch (error) {
      setMessage(`Save failed: ${friendlyErrorMessage(error, 'Could not change Radar state.')}`);
    } finally {
      setBusyKey(null);
    }
  }

  async function toggleAutoConfirm() {
    if (!handoffRuntime) return;
    setBusyKey('auto-confirm');
    try {
      const result = await saveRadarRuntimeSettings({ autoConfirm: !handoffRuntime.autoConfirm });
      setHandoffRuntime(result.runtime);
      setMessage(result.runtime.autoConfirm ? 'Auto confirmation enabled.' : 'Manual confirmation enabled.');
      await refresh();
    } catch (error) {
      setMessage(`Save failed: ${friendlyErrorMessage(error, 'Could not change confirmation mode.')}`);
    } finally {
      setBusyKey(null);
    }
  }

  const radarEnabled = Boolean(alphaSettings?.enabled && handoffRuntime?.enabled);
  const collectors = live?.monitoring.collectors ?? [];
  const connectors = useMemo(
    () => Object.entries(alphaSettings?.connectors ?? {}).map(([key, value]) => ({ key, value })),
    [alphaSettings],
  );
  const trendItems = useMemo(() => (snapshot?.observations ?? []).slice(0, 3), [snapshot]);
  const activeIdeas = useMemo(() => ideas.filter((item) => item.verdict !== 'cash'), [ideas]);
  const liveIdeas = useMemo(() => activeIdeas.slice(0, 3), [activeIdeas]);
  const tradableSignals = useMemo(
    () => (signals?.signals ?? []).filter((item) => item.status === 'pending_confirmation' || item.status === 'auto_order_placed').slice(0, 4),
    [signals],
  );
  const handoffHistory = useMemo(() => (signals?.signals ?? []).slice(0, 6), [signals]);
  const topAssets = useMemo(() => (snapshot?.summary.topAssets ?? []).slice(0, 8), [snapshot]);
  const monitoringOnlyAssets = live?.monitoring.monitoringOnlyAssets ?? snapshot?.summary.monitoringOnlyAssets ?? [];
  const tradableAssets = tradingSymbols?.symbols ?? [];
  const sourceHealth = useMemo(() => (live?.monitoring.sourceHealth ?? []).slice(0, 4), [live]);
  const dedupedMergedCount = useMemo(() => {
    if (typeof ideasPayload?.marketSummary.dedupeSuppressed === 'number') {
      return ideasPayload.marketSummary.dedupeSuppressed;
    }
    const observationMerges = (snapshot?.observations ?? []).reduce((acc, item) => {
      const merged = Number(item.metadata?.dedupeMergedCount ?? 0);
      return acc + (Number.isFinite(merged) && merged > 0 ? merged : 0);
    }, 0);
    const duplicateSignals = (signals?.signals ?? []).filter((item) => item.duplicateOf || item.error === 'duplicate_signal').length;
    return observationMerges + duplicateSignals;
  }, [ideasPayload, signals, snapshot]);
  const handedOffCount = (signals?.summary.pendingConfirmation ?? 0) + (signals?.summary.autoOrderPlaced ?? 0);
  const rejectedHandoffCount = signals?.summary.rejected ?? 0;
  const activePolicyCount = ideasPayload?.marketSummary.activeRadarContextPolicies ?? 0;
  const lockedPolicyCount = ideasPayload?.marketSummary.lockedRadarContextPolicies ?? 0;
  const expiredPolicyCount = ideasPayload?.marketSummary.expiredRadarContextPolicies ?? 0;
  const policyBlockedEntries = ideasPayload?.marketSummary.policyBlockedEntries ?? 0;
  const policyAcceptedEntries = ideasPayload?.marketSummary.policyAcceptedEntries ?? 0;

  if (isLoading && !live && !snapshot && !signals) {
    return <p className="muted">Loading Radar…</p>;
  }

  return (
    <main className="terminal-layout radar-simple-page">
      <Card
        title="Radar status"
        className="terminal-card radar-simple-card"
        actions={<Badge tone={radarEnabled ? 'success' : 'danger'}>{radarEnabled ? 'LIVE' : 'OFF'}</Badge>}
      >
        <div className="radar-simple-stack">
          <div className="radar-simple-row">
            <div>
              <p className="muted radar-simple-label">Observation plane</p>
              <strong>{alphaSettings?.enabled ? 'Enabled' : 'Disabled'}</strong>
            </div>
            <div>
              <p className="muted radar-simple-label">Handoff</p>
              <strong>{handoffRuntime?.enabled ? 'Enabled' : 'Disabled'}</strong>
            </div>
            <div>
              <p className="muted radar-simple-label">Confirm mode</p>
              <strong>{handoffRuntime?.autoConfirm ? 'Auto' : 'Manual'}</strong>
            </div>
          </div>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Connectors</h3>
              <span className="muted">{connectors.length}</span>
            </div>
            <div className="radar-compact-list">
              {connectors.map(({ key, value }) => (
                <article key={key} className="radar-compact-item">
                  <div className="radar-compact-item__top">
                    <strong>{key}</strong>
                    <Badge tone={value.state?.status === 'connected' ? 'success' : value.enabled ? 'neutral' : 'danger'}>
                      {value.state?.status ?? (value.enabled ? 'enabled' : 'off')}
                    </Badge>
                  </div>
                  <p className="muted">{compactText(String(value.state?.message ?? value.state?.connectionLabel ?? value.sourceLabel ?? 'No connector note'), 88)}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Collectors</h3>
            </div>
            <div className="radar-compact-list radar-compact-list--tight">
              {collectors.map((collector) => (
                <article key={collector.plane} className="radar-inline-stat">
                  <div>
                    <strong>{collector.label}</strong>
                    <p className="muted">{collector.lastCompletedAt ? formatAge(collector.lastCompletedAt) : 'No completed run yet'}</p>
                  </div>
                  <Badge tone={collector.lastStatus === 'ok' ? 'success' : collector.lastStatus === 'error' ? 'danger' : 'neutral'}>
                    {collector.busy ? 'running' : (collector.lastStatus ?? 'idle')}
                  </Badge>
                </article>
              ))}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Tradable assets</h3>
              <span className="muted">{tradableAssets.length}</span>
            </div>
            <div className="radar-chip-grid">
              {tradableAssets.length ? tradableAssets.slice(0, 10).map((asset) => <span key={asset} className="radar-chip">{asset}</span>) : <span className="muted">No tradable assets configured.</span>}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Monitoring universe</h3>
              <span className="muted">{monitoringOnlyAssets.length}</span>
            </div>
            <div className="radar-chip-grid">
              {monitoringOnlyAssets.length ? monitoringOnlyAssets.slice(0, 10).map((asset) => <span key={asset} className="radar-chip radar-chip--muted">{asset}</span>) : <span className="muted">No monitoring-only assets.</span>}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Freshness</h3>
            </div>
            <div className="radar-compact-list radar-compact-list--tight">
              {sourceHealth.map((item) => (
                <article key={item.source} className="radar-inline-stat">
                  <div>
                    <strong>{compactText(item.source, 24)}</strong>
                    <p className="muted">{item.lastObservedAt ? formatAge(item.lastObservedAt) : '—'}</p>
                  </div>
                  <Badge tone={toneFromHealth(item.status)}>{item.status}</Badge>
                </article>
              ))}
            </div>
          </section>
        </div>
      </Card>

      <Card title="Live feed" className="terminal-card radar-simple-card radar-simple-card--feed">
        <div className="radar-simple-stack">
          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Trending now</h3>
              <span className="muted">{trendItems.length}</span>
            </div>
            <div className="radar-feed-list">
              {trendItems.length ? trendItems.map((item) => (
                <article key={item.id} className="radar-feed-item">
                  <div className="radar-feed-item__top">
                    <strong>{compactText(item.title, 76)}</strong>
                    <span className="muted">{formatAge(item.observedAt)}</span>
                  </div>
                  <p className="muted">{item.assetTags.slice(0, 4).join(', ') || item.source}</p>
                </article>
              )) : <p className="muted">No fresh trend items yet.</p>}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>In work</h3>
              <span className="muted">{activeIdeas.length}</span>
            </div>
            <div className="radar-feed-list">
              {liveIdeas.length ? liveIdeas.map((idea) => (
                <article key={idea.id} className="radar-feed-item">
                  <div className="radar-feed-item__top">
                    <div className="stack-row">
                      <strong>{idea.symbol ?? 'CASH'}</strong>
                      <Badge tone={toneFromIdea(idea.verdict)}>{idea.signalFamily}</Badge>
                    </div>
                    <span className="muted">{idea.score.toFixed(2)}</span>
                  </div>
                  <p>{compactText(idea.actionability.summary, 96)}</p>
                  <p className="muted">{idea.trigger ? `Trigger ${formatMoney(idea.trigger)}` : compactText(idea.whyNow[0] ?? idea.title, 96)}</p>
                </article>
              )) : <p className="muted">No active ideas yet.</p>}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Tradable now</h3>
              <span className="muted">{tradableSignals.length}</span>
            </div>
            <div className="radar-feed-list">
              {tradableSignals.length ? tradableSignals.map((signal) => (
                <article key={signal.id} className="radar-feed-item">
                  <div className="radar-feed-item__top">
                    <div className="stack-row">
                      <strong>{signal.symbol} {signal.side.toUpperCase()}</strong>
                      <Badge tone={signal.status === 'auto_order_placed' ? 'success' : 'neutral'}>{signal.status}</Badge>
                    </div>
                    <span className="muted">{formatAge(signal.updatedAt || signal.createdAt)}</span>
                  </div>
                  <p>{compactText(signal.reason, 96)}</p>
                  <p className="muted">{signal.source}</p>
                </article>
              )) : <p className="muted">No pending or confirmed handoff signals right now.</p>}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Funnel</h3>
              <span className="muted">source → handoff</span>
            </div>
            <div className="radar-simple-row radar-simple-row--compact radar-simple-row--funnel">
              <div>
                <p className="muted radar-simple-label">Collected</p>
                <strong>{snapshot?.summary.total ?? 0}</strong>
              </div>
              <div>
                <p className="muted radar-simple-label">Deduped</p>
                <strong>{dedupedMergedCount}</strong>
              </div>
              <div>
                <p className="muted radar-simple-label">Promoted</p>
                <strong>{ideasPayload?.marketSummary.signalCandidates ?? activeIdeas.length}</strong>
              </div>
              <div>
                <p className="muted radar-simple-label">Handed off</p>
                <strong>{handedOffCount}</strong>
              </div>
              <div>
                <p className="muted radar-simple-label">Rejected</p>
                <strong>{rejectedHandoffCount}</strong>
              </div>
            </div>

            <div className="radar-chip-grid">
              {typeof ideasPayload?.marketSummary.evidenceBundles === 'number' ? (
                <span className="radar-chip radar-chip--muted">Evidence {ideasPayload.marketSummary.evidenceBundles}</span>
              ) : null}
              {typeof ideasPayload?.marketSummary.radarContextPolicies === 'number' ? (
                <span className="radar-chip radar-chip--muted">Policies {ideasPayload.marketSummary.radarContextPolicies}</span>
              ) : null}
              <span className="radar-chip radar-chip--muted">Active policy {activePolicyCount}</span>
              <span className="radar-chip radar-chip--muted">Locked {lockedPolicyCount}</span>
              <span className="radar-chip radar-chip--muted">Expired {expiredPolicyCount}</span>
              <span className="radar-chip radar-chip--muted">Policy pass {policyAcceptedEntries}</span>
              <span className="radar-chip radar-chip--muted">Policy block {policyBlockedEntries}</span>
              {topAssets.length ? topAssets.map((item) => (
                <span key={item.asset} className="radar-chip">{item.asset} · {item.count}</span>
              )) : <span className="muted">No active asset concentration yet.</span>}
            </div>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Handoff history</h3>
              <span className="muted">{signals?.summary.total ?? 0}</span>
            </div>
            <div className="radar-feed-list">
              {handoffHistory.length ? handoffHistory.map((signal) => (
                <article key={signal.id} className="radar-feed-item">
                  <div className="radar-feed-item__top">
                    <div className="stack-row">
                      <strong>{signal.symbol} {signal.side.toUpperCase()}</strong>
                      <Badge tone={toneFromSignalStatus(signal.status)}>{signal.status}</Badge>
                    </div>
                    <span className="muted">{formatAge(signal.updatedAt || signal.createdAt)}</span>
                  </div>
                  <p>{compactText(signal.reason, 96)}</p>
                  <p className="muted">
                    {signal.error ? `Reason: ${signal.error}` : signal.orderId ? `Order ${signal.orderId}` : signal.pendingId ? `Pending ${signal.pendingId}` : signal.verdictReason ?? signal.source}
                  </p>
                </article>
              )) : <p className="muted">No handoff attempts yet.</p>}
            </div>
          </section>
        </div>
      </Card>

      <Card title="Settings" className="terminal-card radar-simple-card">
        <div className="radar-simple-stack">
          <section className="radar-setting-block">
            <div>
              <h3>Radar master switch</h3>
              <p className="muted">Single on/off control for monitoring + handoff.</p>
            </div>
            <Button
              variant={radarEnabled ? 'danger' : 'primary'}
              onClick={() => { void toggleRadar(); }}
              disabled={busyKey !== null || !alphaSettings || !handoffRuntime}
              fullWidth
            >
              {radarEnabled ? 'Turn radar off' : 'Turn radar on'}
            </Button>
          </section>

          <section className="radar-setting-block">
            <div>
              <h3>Deal confirmation</h3>
              <p className="muted">Choose automatic or manual confirmation for tradable handoff signals.</p>
            </div>
            <Button
              variant={handoffRuntime?.autoConfirm ? 'danger' : 'primary'}
              onClick={() => { void toggleAutoConfirm(); }}
              disabled={busyKey !== null || !handoffRuntime}
              fullWidth
            >
              {handoffRuntime?.autoConfirm ? 'Switch to manual confirmation' : 'Switch to auto confirmation'}
            </Button>
          </section>

          <section className="radar-simple-section">
            <div className="radar-simple-section__header">
              <h3>Current mode</h3>
            </div>
            <div className="radar-chip-grid">
              <span className={`radar-chip ${radarEnabled ? 'radar-chip--success' : 'radar-chip--danger'}`}>
                {radarEnabled ? 'Radar active' : 'Radar stopped'}
              </span>
              <span className={`radar-chip ${handoffRuntime?.autoConfirm ? 'radar-chip--success' : 'radar-chip--muted'}`}>
                {handoffRuntime?.autoConfirm ? 'Auto confirm' : 'Manual confirm'}
              </span>
              <span className="radar-chip radar-chip--muted">Refresh {Math.round(REFRESH_MS / 1000)}s</span>
            </div>
          </section>

          {message ? <p className="muted radar-note">{message}</p> : null}
        </div>
      </Card>
    </main>
  );
}
