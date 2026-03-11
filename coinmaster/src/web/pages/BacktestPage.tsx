import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import type {
  BacktestRun,
  TradingRulesSettings,
  TradingRulesTimeframe,
} from '../../shared/dto.js';
import { normalizeTradingRules } from '../../shared/tradingRules.js';
import {
  createBacktestRun,
  friendlyErrorMessage,
  getBacktestRun,
  getBacktestRuns,
  getTradingRuleSymbols,
  getTradingRules,
  requestBacktestAiAnalysis,
} from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';

// ─── Constants ────────────────────────────────────────────────────────

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];
const POLL_INTERVAL_MS = 3_000;

function toLocalDateStr(ms: number): string {
  const d = new Date(ms);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function fromLocalDateStr(s: string): number {
  const parts = s.split('-').map(Number);
  return new Date(parts[0], parts[1] - 1, parts[2]).getTime();
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

// ─── Component ────────────────────────────────────────────────────────

export function BacktestPage() {
  // Load state
  const [symbols, setSymbols] = useState<string[]>([]);
  const [rules, setRules] = useState<TradingRulesSettings | null>(null);
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [symbol, setSymbol] = useState('BTC');
  const [startDate, setStartDate] = useState(() => toLocalDateStr(Date.now() - 30 * 86400_000));
  const [endDate, setEndDate] = useState(() => toLocalDateStr(Date.now()));

  // Rules overrides (subset)
  const [entryTfs, setEntryTfs] = useState<TradingRulesTimeframe[]>(['15m', '1h', '4h']);
  const [exitTfs, setExitTfs] = useState<TradingRulesTimeframe[]>(['1h', '4h']);
  const [lookback, setLookback] = useState(30);
  const [fvgRetrace, setFvgRetrace] = useState(50);
  const [fvgMinWidth, setFvgMinWidth] = useState(0.3);
  const [maxLeverage, setMaxLeverage] = useState(10);
  const [tpLevels, setTpLevels] = useState<number[]>([1, 2, 3]);
  const [slPct, setSlPct] = useState(1);
  const [exitClosePct, setExitClosePct] = useState(50);

  // Run state
  const [submitting, setSubmitting] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [analysisBusyRunId, setAnalysisBusyRunId] = useState<string | null>(null);
  const [reportRun, setReportRun] = useState<BacktestRun | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── Load initial data ──────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [rulesRes, symbolsRes, runsRes] = await Promise.all([
          getTradingRules(),
          getTradingRuleSymbols(),
          getBacktestRuns(),
        ]);
        if (cancelled) return;

        const r = normalizeTradingRules(rulesRes.rules);
        setRules(r);
        setSymbols(symbolsRes.symbols ?? []);
        setRuns(runsRes.runs ?? []);

        // Pre-fill from current rules
        setEntryTfs(r.entryTimeframes?.length ? r.entryTimeframes : ['15m']);
        setExitTfs(r.emergencyExitTimeframes?.length ? r.emergencyExitTimeframes : ['1h']);
        setLookback(r.engulfingLookbackCandles ?? 30);
        setFvgRetrace(r.fvgRetrace ?? 50);
        setFvgMinWidth(r.fvgMinWidthPct ?? 0.3);
        setMaxLeverage(r.maxLeverage ?? 10);
        setTpLevels(r.tpLevels?.length ? [...r.tpLevels] : [6]);
        setSlPct(r.slPct ?? 2);
        setExitClosePct(r.exitClosePct ?? 50);

        // Default symbol from first enabled coin
        const firstEnabled = r.coins.find((c) => c.enabled);
        if (firstEnabled) setSymbol(firstEnabled.symbol);
      } catch (err) {
        if (!cancelled) setError(friendlyErrorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  // ─── Poll active run / pending AI analysis ─────────────────────────
  useEffect(() => {
    const hasPendingAi = runs.some((run) => run.aiAnalysis?.status === 'pending');
    const shouldPoll = Boolean(activeRunId) || hasPendingAi;

    if (!shouldPoll) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }

    async function poll() {
      try {
        const listRes = await getBacktestRuns();
        const nextRuns = listRes.runs ?? [];
        setRuns(nextRuns);

        if (activeRunId) {
          const active = nextRuns.find((run) => run.id === activeRunId);
          if (active && (active.status === 'completed' || active.status === 'failed')) {
            setActiveRunId(null);
            setSelectedRun(active);
          }
        }

        if (selectedRun) {
          const refreshedSelected = nextRuns.find((run) => run.id === selectedRun.id);
          if (refreshedSelected) setSelectedRun(refreshedSelected);
        }
      } catch {
        // ignore poll errors
      }
    }

    void poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [activeRunId, runs, selectedRun]);

  // ─── Submit ─────────────────────────────────────────────────────────
  const handleRun = useCallback(async () => {
    if (submitting || activeRunId) return;
    setSubmitting(true);
    setError(null);
    try {
      const startMs = fromLocalDateStr(startDate);
      const endMs = fromLocalDateStr(endDate) + 86400_000 - 1; // end of day

      const rulesSnapshot: TradingRulesSettings = normalizeTradingRules({
        ...(rules ?? {}),
        coins: [{ symbol, enabled: true, pct: 100 }],
        entryTimeframes: entryTfs,
        emergencyExitTimeframes: exitTfs,
        engulfingLookbackCandles: lookback,
        fvgRetrace,
        fvgMinWidthPct: fvgMinWidth,
        maxLeverage,
        tpLevels,
        slPct,
        exitClosePct,
        autoConfirm: false,
      });

      const res = await createBacktestRun({
        symbol,
        startTimeMs: startMs,
        endTimeMs: endMs,
        rules: rulesSnapshot,
      });

      setActiveRunId(res.run.id);
      setSelectedRun(res.run);
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }, [submitting, activeRunId, startDate, endDate, rules, symbol, entryTfs, exitTfs, lookback, fvgRetrace, fvgMinWidth, maxLeverage, tpLevels, slPct, exitClosePct]);

  const handleAiClick = useCallback(async (run: BacktestRun) => {
    if (run.aiAnalysis?.status === 'completed' && run.aiAnalysis?.report) {
      setReportRun(run);
      return;
    }
    if (run.aiAnalysis?.status === 'pending' || analysisBusyRunId) return;

    setAnalysisBusyRunId(run.id);
    setError(null);
    try {
      const res = await requestBacktestAiAnalysis(run.id);
      setRuns((prev) => prev.map((item) => item.id === res.run.id ? res.run : item));
      if (selectedRun?.id === res.run.id) setSelectedRun(res.run);
    } catch (err) {
      setError(friendlyErrorMessage(err, 'Could not request AI analysis.'));
    } finally {
      setAnalysisBusyRunId(null);
    }
  }, [analysisBusyRunId, selectedRun]);

  // ─── TF toggle helpers ─────────────────────────────────────────────
  function toggleTf(current: TradingRulesTimeframe[], tf: TradingRulesTimeframe, setter: (v: TradingRulesTimeframe[]) => void) {
    if (current.includes(tf)) {
      if (current.length <= 1) return; // keep at least one
      setter(current.filter((t) => t !== tf));
    } else {
      setter([...current, tf]);
    }
  }

  // ─── TP level helpers ──────────────────────────────────────────────
  function setTpLevel(index: number, value: number) {
    const next = [...tpLevels];
    next[index] = clamp(value, 0.1, 100);
    setTpLevels(next);
  }
  function addTpLevel() {
    if (tpLevels.length >= 3) return;
    const last = tpLevels[tpLevels.length - 1] ?? 3;
    setTpLevels([...tpLevels, clamp(last + 2, 0.1, 100)]);
  }
  function removeTpLevel(index: number) {
    if (tpLevels.length <= 1) return;
    setTpLevels(tpLevels.filter((_, i) => i !== index));
  }

  if (loading) return <div className="page-loading">Loading...</div>;

  const isRunning = !!activeRunId;

  return (
    <div className="backtest-page">
      <h2>Backtest</h2>

      {error && <div className="alert alert--error">{error}</div>}

      {/* ─── Configuration form ────────────────────────────────── */}
      <Card title="Backtest Configuration">
        <div className="bt-form">
          <div className="bt-form__row">
            <label>Symbol</label>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} disabled={isRunning}>
              {symbols.length > 0
                ? symbols.map((s) => <option key={s} value={s}>{s}</option>)
                : <option value={symbol}>{symbol}</option>
              }
            </select>
          </div>

          <div className="bt-form__row bt-form__row--dates">
            <div>
              <label>Start Date</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={isRunning} />
            </div>
            <div>
              <label>End Date</label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={isRunning} />
            </div>
          </div>

          <div className="bt-form__row">
            <label>Entry Timeframes</label>
            <div className="bt-tf-group">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  className={entryTfs.includes(tf) ? 'bt-tf-btn bt-tf-btn--active' : 'bt-tf-btn'}
                  onClick={() => toggleTf(entryTfs, tf, setEntryTfs)}
                  disabled={isRunning}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          <div className="bt-form__row">
            <label>Emergency Exit TFs</label>
            <div className="bt-tf-group">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  className={exitTfs.includes(tf) ? 'bt-tf-btn bt-tf-btn--active' : 'bt-tf-btn'}
                  onClick={() => toggleTf(exitTfs, tf, setExitTfs)}
                  disabled={isRunning}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          <div className="bt-form__row">
            <label>Lookback (candles)</label>
            <input type="number" value={lookback} min={5} max={100} onChange={(e) => setLookback(clamp(Number(e.target.value), 5, 100))} disabled={isRunning} />
          </div>

          <div className="bt-form__row">
            <label>FVG Retrace %</label>
            <input type="number" value={fvgRetrace} min={10} max={90} onChange={(e) => setFvgRetrace(clamp(Number(e.target.value), 10, 90))} disabled={isRunning} />
          </div>

          <div className="bt-form__row">
            <label>FVG Min Width %</label>
            <input type="number" value={fvgMinWidth} min={0} max={10} step={0.1} onChange={(e) => setFvgMinWidth(clamp(Number(e.target.value), 0, 10))} disabled={isRunning} />
          </div>

          <div className="bt-form__row">
            <label>Max Leverage</label>
            <input type="number" value={maxLeverage} min={1} max={100} onChange={(e) => setMaxLeverage(clamp(Number(e.target.value), 1, 100))} disabled={isRunning} />
          </div>

          <div className="bt-form__row">
            <label>Take Profit Levels (%)</label>
            <div className="bt-tp-group">
              {tpLevels.map((tp, i) => (
                <div key={i} className="bt-tp-row">
                  <span className="bt-tp-label">TP{i + 1}</span>
                  <input
                    type="number"
                    value={tp}
                    min={0.1}
                    max={100}
                    step={0.5}
                    onChange={(e) => setTpLevel(i, Number(e.target.value))}
                    disabled={isRunning}
                  />
                  {tpLevels.length > 1 && (
                    <button type="button" className="bt-tp-remove" onClick={() => removeTpLevel(i)} disabled={isRunning}>×</button>
                  )}
                </div>
              ))}
              {tpLevels.length < 3 && (
                <button type="button" className="bt-tp-add" onClick={addTpLevel} disabled={isRunning}>+ Add TP level</button>
              )}
            </div>
          </div>

          <div className="bt-form__row">
            <label>Stop Loss %</label>
            <input type="number" value={slPct} min={0.1} max={50} step={0.5} onChange={(e) => setSlPct(clamp(Number(e.target.value), 0.1, 50))} disabled={isRunning} />
          </div>

          <div className="bt-form__row">
            <label>Emergency Exit Close %</label>
            <input type="number" value={exitClosePct} min={0} max={100} onChange={(e) => setExitClosePct(clamp(Number(e.target.value), 0, 100))} disabled={isRunning} />
          </div>

          <div className="bt-form__actions">
            <Button onClick={handleRun} disabled={isRunning || submitting}>
              {isRunning ? 'Running…' : submitting ? 'Submitting…' : 'Run Backtest'}
            </Button>
          </div>
        </div>
      </Card>

      {/* ─── Active / Selected run result ─────────────────────── */}
      {selectedRun && (
        <Card title={`Result: ${selectedRun.symbol} — ${selectedRun.status}`}>
          {selectedRun.status === 'running' || selectedRun.status === 'queued' ? (
            <div className="bt-running">
              <Badge tone="neutral">{selectedRun.status}</Badge>
              <p>Backtest is running, please wait…</p>
            </div>
          ) : selectedRun.status === 'failed' ? (
            <div className="bt-failed">
              <Badge tone="danger">failed</Badge>
              <p>{selectedRun.error || 'Unknown error'}</p>
            </div>
          ) : selectedRun.summary ? (
            <div className="bt-result">
              <div className="bt-result__grid">
                <div className="bt-stat">
                  <span className="bt-stat__label">Net P&L</span>
                  <span className={`bt-stat__value ${selectedRun.summary.netPnlUsd >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}`}>
                    {formatMoney(selectedRun.summary.netPnlUsd)}
                  </span>
                </div>
                <div className="bt-stat">
                  <span className="bt-stat__label">ROI</span>
                  <span className={`bt-stat__value ${selectedRun.summary.roiPct >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}`}>
                    {formatNumber(selectedRun.summary.roiPct)}%
                  </span>
                </div>
                <div className="bt-stat">
                  <span className="bt-stat__label">Win Rate</span>
                  <span className="bt-stat__value">{formatNumber(selectedRun.summary.winRatePct)}%</span>
                </div>
                <div className="bt-stat">
                  <span className="bt-stat__label">Total Trades</span>
                  <span className="bt-stat__value">{selectedRun.summary.totalTrades}</span>
                </div>
                <div className="bt-stat">
                  <span className="bt-stat__label">Max Drawdown</span>
                  <span className="bt-stat__value bt-stat__value--negative">{formatNumber(selectedRun.summary.maxDrawdownPct)}%</span>
                </div>
              </div>

              {selectedRun.bySymbol?.length > 0 && (
                <div className="bt-symbol-stats">
                  <h4>Per-Symbol Breakdown</h4>
                  {selectedRun.bySymbol.map((ss) => (
                    <div key={ss.symbol} className="bt-symbol-row">
                      <strong>{ss.symbol}</strong>
                      <span>W:{ss.wins} L:{ss.losses}</span>
                      <span>SL:{ss.slCount}</span>
                      <span>TP1:{ss.tp1Count} TP2:{ss.tp2Count} TP3:{ss.tp3Count}</span>
                      <span>Exit:{ss.emergencyExitCount}</span>
                      <span className={ss.netPnlUsd >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}>
                        {formatMoney(ss.netPnlUsd)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {selectedRun.artifacts && (
                <div className="bt-artifacts">
                  <small>
                    {selectedRun.artifacts.tradeCount} trade events · {selectedRun.artifacts.equityCurvePoints} equity points · Engine: {selectedRun.engineVersion}/{selectedRun.engineCommit?.slice(0, 8)}
                  </small>
                </div>
              )}
            </div>
          ) : null}
        </Card>
      )}

      {/* ─── Run history ──────────────────────────────────────── */}
      {runs.length > 0 && (
        <Card title="Run History">
          <div className="bt-history">
            {runs.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`bt-history__item ${selectedRun?.id === r.id ? 'bt-history__item--selected' : ''}`}
                onClick={() => setSelectedRun(r)}
              >
                <span className="bt-history__symbol">{r.symbol}</span>
                <span className="bt-history__dates">
                  {toLocalDateStr(r.startTimeMs)} → {toLocalDateStr(r.endTimeMs)}
                </span>
                <Badge tone={r.status === 'completed' ? 'success' : r.status === 'failed' ? 'danger' : 'neutral'}>
                  {r.status}
                </Badge>
                {r.summary && (
                  <span className={r.summary.netPnlUsd >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}>
                    {formatMoney(r.summary.netPnlUsd)} ({formatNumber(r.summary.roiPct)}%)
                  </span>
                )}
                <button
                  type="button"
                  className={`bt-ai-btn bt-ai-btn--${r.aiAnalysis?.status ?? 'idle'}`}
                  title={r.aiAnalysis?.status === 'completed' ? 'Open saved AI report' : r.aiAnalysis?.status === 'pending' ? 'AI analysis is running' : 'Generate AI analysis'}
                  onClick={(event) => {
                    event.stopPropagation();
                    void handleAiClick(r);
                  }}
                  disabled={analysisBusyRunId === r.id || r.aiAnalysis?.status === 'pending' || r.status !== 'completed'}
                >
                  {analysisBusyRunId === r.id ? '…' : r.aiAnalysis?.status === 'completed' ? '🤖' : r.aiAnalysis?.status === 'pending' ? '⏳' : 'AI'}
                </button>
              </button>
            ))}
          </div>
        </Card>
      )}

      {reportRun?.aiAnalysis?.report ? (
        <div className="bt-report-overlay" onClick={() => setReportRun(null)}>
          <div className="bt-report-modal" onClick={(event) => event.stopPropagation()}>
            <div className="bt-report-modal__header">
              <div>
                <h3>AI Analysis — {reportRun.symbol}</h3>
                <div className="bt-report-modal__meta">
                  {reportRun.aiAnalysis.model ? `${reportRun.aiAnalysis.model} • ` : ''}
                  {reportRun.aiAnalysis.completedAt ?? reportRun.aiAnalysis.requestedAt}
                </div>
              </div>
              <button type="button" className="bt-report-close" onClick={() => setReportRun(null)}>×</button>
            </div>

            {reportRun.aiAnalysis.summary ? (
              <div className="bt-report-section">
                <h4>Summary</h4>
                <p>{reportRun.aiAnalysis.summary}</p>
              </div>
            ) : null}

            {reportRun.aiAnalysis.recommendations?.length ? (
              <div className="bt-report-section">
                <h4>Recommendations</h4>
                <ul>
                  {reportRun.aiAnalysis.recommendations.map((item, index) => <li key={index}>{item}</li>)}
                </ul>
              </div>
            ) : null}

            <div className="bt-report-section">
              <h4>Saved Report</h4>
              <pre className="bt-report-pre">{reportRun.aiAnalysis.report}</pre>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
