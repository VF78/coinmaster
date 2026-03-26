import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { useDialog } from '../components/DialogProvider';
import type {
  BacktestBiasMode,
  BacktestRun,
  TradingRulesSettings,
  TradingRulesTimeframe,
} from '../../shared/dto.js';
import { cloneTradingRulesDefaults, inferAssetClassFromSymbol, normalizeTradingRules } from '../../shared/tradingRules.js';
import {
  createBacktestRun,
  friendlyErrorMessage,
  getBacktestRuns,
  getTradingRuleSymbols,
  getTradingRules,
} from '../lib/api';
import { formatDate, formatMoney, formatNumber } from '../lib/format';

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];
const EXIT_CLOSE_PRESETS = [0, 25, 50, 75, 100];
const HISTORY_PAGE_SIZE = 15;
const POLL_INTERVAL_MS = 3_000;

type HistorySortMode = 'created-desc' | 'roi-desc';

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function normalizeAssetSymbol(value: string): string {
  const raw = String(value || '').trim();
  if (!raw) return '';

  if (raw.includes(':')) {
    const [namespaceRaw, symbolRaw] = raw.split(':', 2);
    const namespace = String(namespaceRaw || '').trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
    const symbol = String(symbolRaw || '').trim().toUpperCase().replace(/[^A-Z0-9_-]/g, '');
    if (!namespace || !symbol) return '';
    return `${namespace}:${symbol}`;
  }

  return raw.toUpperCase().replace(/[^A-Z0-9_-]/g, '');
}

function toLocalDateStr(ms: number): string {
  const d = new Date(ms);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function fromLocalDateStr(s: string): number {
  const [yyyy, mm, dd] = s.split('-').map(Number);
  return new Date(yyyy, (mm ?? 1) - 1, dd ?? 1).getTime();
}

function biasModeFromSelection(longEnabled: boolean, shortEnabled: boolean): BacktestBiasMode {
  if (longEnabled && shortEnabled) return 'both';
  return longEnabled ? 'long' : 'short';
}

function selectionFromBiasMode(biasMode: BacktestBiasMode | undefined): { longEnabled: boolean; shortEnabled: boolean } {
  switch (biasMode) {
    case 'long': return { longEnabled: true, shortEnabled: false };
    case 'short': return { longEnabled: false, shortEnabled: true };
    default: return { longEnabled: true, shortEnabled: true };
  }
}

function formatRulesSnapshot(run: BacktestRun): Array<{ label: string; value: string }> {
  const rules = run.rulesSnapshot;
  const coin = rules.coins[0];
  return [
    { label: 'Period', value: `${toLocalDateStr(run.startTimeMs)} → ${toLocalDateStr(run.endTimeMs)}` },
    { label: 'Bias', value: (run.biasMode ?? 'both').toUpperCase() },
    { label: 'Asset', value: coin?.symbol ?? run.symbol },
    { label: 'Asset class', value: coin?.assetClass ?? inferAssetClassFromSymbol(coin?.symbol ?? run.symbol) },
    { label: 'Entry timeframe', value: (rules.entryTimeframes ?? []).join(', ') || '—' },
    { label: 'Exit timeframe', value: (rules.emergencyExitTimeframes ?? []).join(', ') || '—' },
    { label: 'Lookback candles', value: String(rules.engulfingLookbackCandles ?? 30) },
    { label: 'FVG Retrace Level', value: `${rules.fvgRetrace ?? 50}%` },
    { label: 'FVG Min Width Filter', value: `${rules.fvgMinWidthPct ?? 0.3}%` },
    { label: 'Close size on exit signal', value: `${rules.exitClosePct ?? 50}%` },
    { label: 'Daily Drawdown Limit', value: `${rules.dailyDrawdown ?? 0}%` },
    { label: 'Max Leverage', value: `${rules.maxLeverage ?? 1}x` },
    { label: 'TP Levels', value: (rules.tpLevels ?? []).map((x) => `${x}%`).join(' / ') || `${rules.tpPct ?? 0}%` },
    { label: 'SL', value: `${rules.slPct ?? 0}%` },
  ];
}

interface StepperProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  decimals?: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}

function Stepper({ value, min, max, step = 1, unit = '', decimals = 0, onChange, disabled = false }: StepperProps) {
  const display = decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));

  function apply(nextRaw: number) {
    const clamped = clampNumber(nextRaw, min, max);
    onChange(+(clamped.toFixed(decimals + 2)));
  }

  return (
    <div className="rules-stepper" role="group" aria-label="Number stepper">
      <button type="button" className="rules-stepper__btn" disabled={disabled || value <= min} onClick={() => apply(value - step)}>−</button>
      <div className="rules-stepper__center">
        <input
          type="number"
          className="rules-stepper__input"
          value={display}
          min={min}
          max={max}
          step={step}
          inputMode="decimal"
          disabled={disabled}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === '') return;
            const parsed = Number(raw);
            if (!Number.isFinite(parsed)) return;
            apply(parsed);
          }}
          onBlur={(e) => {
            const parsed = Number(e.target.value);
            if (!Number.isFinite(parsed)) {
              apply(value);
              return;
            }
            apply(parsed);
          }}
        />
        {unit ? <span className="rules-stepper__unit">{unit}</span> : null}
      </div>
      <button type="button" className="rules-stepper__btn" disabled={disabled || value >= max} onClick={() => apply(value + step)}>+</button>
    </div>
  );
}

interface SegmentedProps<T extends string | number> {
  options: T[];
  value: T;
  format?: (v: T) => string;
  onChange: (v: T) => void;
}

function Segmented<T extends string | number>({ options, value, format, onChange }: SegmentedProps<T>) {
  return (
    <div className="rules-segmented" role="tablist" aria-label="Segmented control">
      {options.map((opt, i) => {
        const active = opt === value;
        return (
          <button key={i} type="button" className={`rules-segmented__btn ${active ? 'rules-segmented__btn--active' : ''}`} onClick={() => onChange(opt)}>
            {format ? format(opt) : String(opt)}
          </button>
        );
      })}
    </div>
  );
}

export function BacktestPage() {
  const defaults = cloneTradingRulesDefaults();
  const dialog = useDialog();

  const [availableSymbols, setAvailableSymbols] = useState<string[]>([]);
  const [rulesBase, setRulesBase] = useState<TradingRulesSettings>(defaults);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [symbol, setSymbol] = useState(defaults.coins[0]?.symbol ?? 'BTC');
  const [symbolDraft, setSymbolDraft] = useState(defaults.coins[0]?.symbol ?? 'BTC');
  const [startDate, setStartDate] = useState(() => toLocalDateStr(Date.now() - 30 * 86400_000));
  const [endDate, setEndDate] = useState(() => toLocalDateStr(Date.now()));
  const [longEnabled, setLongEnabled] = useState(true);
  const [shortEnabled, setShortEnabled] = useState(true);

  const [entryTimeframes, setEntryTimeframes] = useState<TradingRulesTimeframe[]>(defaults.entryTimeframes);
  const [emergencyExitTimeframes, setEmergencyExitTimeframes] = useState<TradingRulesTimeframe[]>(defaults.emergencyExitTimeframes);
  const [engulfingLookbackCandles, setEngulfingLookbackCandles] = useState(defaults.engulfingLookbackCandles);
  const [fvgRetrace, setFvgRetrace] = useState(defaults.fvgRetrace);
  const [fvgMinWidthPct, setFvgMinWidthPct] = useState(defaults.fvgMinWidthPct);
  const [maxLeverage, setMaxLeverage] = useState(defaults.maxLeverage);
  const [dailyDrawdown, setDailyDrawdown] = useState(defaults.dailyDrawdown);
  const [tpLevels, setTpLevels] = useState<number[]>(defaults.tpLevels);
  const [slPct, setSlPct] = useState(defaults.slPct);
  const [exitClosePct, setExitClosePct] = useState(defaults.exitClosePct);

  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [reportRun, setReportRun] = useState<BacktestRun | null>(null);
  const [historySort, setHistorySort] = useState<HistorySortMode>('created-desc');
  const [historyPage, setHistoryPage] = useState(1);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const selectedRunIdRef = useRef<string | null>(null);
  const reportRunIdRef = useRef<string | null>(null);

  const biasMode = useMemo(() => biasModeFromSelection(longEnabled, shortEnabled), [longEnabled, shortEnabled]);

  async function applySymbolDraft(): Promise<string | null> {
    const normalized = normalizeAssetSymbol(symbolDraft);
    if (!normalized) {
      await dialog.alert({ title: 'Validation', message: 'Enter a valid symbol first (example: BTC).', confirmText: 'OK' });
      return null;
    }
    if (availableSymbols.length > 0 && !availableSymbols.includes(normalized)) {
      await dialog.alert({ title: 'Validation', message: `${normalized} is not present in the exchange symbol catalog.`, confirmText: 'OK' });
      return null;
    }
    setSymbol(normalized);
    setSymbolDraft(normalized);
    return normalized;
  }

  const applyRunToForm = useCallback((run: BacktestRun) => {
    const rules = normalizeTradingRules(run.rulesSnapshot);
    const coin = rules.coins[0];
    const selection = selectionFromBiasMode(run.biasMode);
    setSymbol(coin?.symbol ?? run.symbol);
    setSymbolDraft(coin?.symbol ?? run.symbol);
    setStartDate(toLocalDateStr(run.startTimeMs));
    setEndDate(toLocalDateStr(run.endTimeMs));
    setLongEnabled(selection.longEnabled);
    setShortEnabled(selection.shortEnabled);
    setEntryTimeframes(rules.entryTimeframes?.length ? rules.entryTimeframes : defaults.entryTimeframes);
    setEmergencyExitTimeframes(rules.emergencyExitTimeframes?.length ? rules.emergencyExitTimeframes : defaults.emergencyExitTimeframes);
    setEngulfingLookbackCandles(rules.engulfingLookbackCandles ?? defaults.engulfingLookbackCandles);
    setFvgRetrace(rules.fvgRetrace ?? defaults.fvgRetrace);
    setFvgMinWidthPct(rules.fvgMinWidthPct ?? defaults.fvgMinWidthPct);
    setMaxLeverage(rules.maxLeverage ?? defaults.maxLeverage);
    setDailyDrawdown(rules.dailyDrawdown ?? defaults.dailyDrawdown);
    setTpLevels(rules.tpLevels?.length ? [...rules.tpLevels] : defaults.tpLevels);
    setSlPct(rules.slPct ?? defaults.slPct);
    setExitClosePct(rules.exitClosePct ?? defaults.exitClosePct);
  }, [defaults]);

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

        const normalized = normalizeTradingRules(rulesRes.rules);
        setRulesBase(normalized);
        setAvailableSymbols(symbolsRes.symbols ?? []);
        setRuns(runsRes.runs ?? []);
        setError(null);

        const firstEnabled = normalized.coins.find((coin) => coin.enabled) ?? normalized.coins[0];
        const seedSymbol = firstEnabled?.symbol ?? defaults.coins[0]?.symbol ?? 'BTC';
        setSymbol(seedSymbol);
        setSymbolDraft(seedSymbol);
        setEntryTimeframes(normalized.entryTimeframes?.length ? normalized.entryTimeframes : defaults.entryTimeframes);
        setEmergencyExitTimeframes(normalized.emergencyExitTimeframes?.length ? normalized.emergencyExitTimeframes : defaults.emergencyExitTimeframes);
        setEngulfingLookbackCandles(normalized.engulfingLookbackCandles ?? defaults.engulfingLookbackCandles);
        setFvgRetrace(normalized.fvgRetrace ?? defaults.fvgRetrace);
        setFvgMinWidthPct(normalized.fvgMinWidthPct ?? defaults.fvgMinWidthPct);
        setMaxLeverage(normalized.maxLeverage ?? defaults.maxLeverage);
        setDailyDrawdown(normalized.dailyDrawdown ?? defaults.dailyDrawdown);
        setTpLevels(normalized.tpLevels?.length ? [...normalized.tpLevels] : defaults.tpLevels);
        setSlPct(normalized.slPct ?? defaults.slPct);
        setExitClosePct(normalized.exitClosePct ?? defaults.exitClosePct);
      } catch (err) {
        if (!cancelled) setError(friendlyErrorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [defaults]);

  useEffect(() => {
    selectedRunIdRef.current = selectedRun?.id ?? null;
  }, [selectedRun]);

  useEffect(() => {
    reportRunIdRef.current = reportRun?.id ?? null;
  }, [reportRun]);

  useEffect(() => {
    const shouldPoll = Boolean(activeRunId);
    if (!shouldPoll) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }

    async function poll() {
      try {
        const listRes = await getBacktestRuns();
        const nextRuns = listRes.runs ?? [];
        setRuns(nextRuns);
        setError(null);
        if (activeRunId) {
          const active = nextRuns.find((item) => item.id === activeRunId);
          if (active && (active.status === 'completed' || active.status === 'failed')) {
            setActiveRunId(null);
            setSelectedRun(active);
          }
        }
        const selectedRunId = selectedRunIdRef.current;
        if (selectedRunId) {
          const nextSelected = nextRuns.find((item) => item.id === selectedRunId);
          if (nextSelected) setSelectedRun(nextSelected);
        }
        const reportRunId = reportRunIdRef.current;
        if (reportRunId) {
          const nextReport = nextRuns.find((item) => item.id === reportRunId);
          if (nextReport?.aiAnalysis?.report) setReportRun(nextReport);
        }
      } catch {
        // ignore transient poll errors
      }
    }

    void poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [activeRunId]);

  useEffect(() => {
    setHistoryPage(1);
  }, [historySort]);

  function toggleTf(
    timeframe: TradingRulesTimeframe,
    current: TradingRulesTimeframe[],
    set: (v: TradingRulesTimeframe[]) => void,
  ) {
    if (current.includes(timeframe)) {
      const next = current.filter((tf) => tf !== timeframe);
      if (next.length > 0) set(next);
    } else {
      set([...current, timeframe]);
    }
  }

  function addTpLevel() {
    if (tpLevels.length >= 3) return;
    const last = tpLevels[tpLevels.length - 1] ?? 6;
    setTpLevels((prev) => [...prev, clampNumber(Math.round(last * 1.5 * 2) / 2, 0.5, 100)]);
  }

  function removeTpLevel(idx: number) {
    if (tpLevels.length <= 1) return;
    setTpLevels((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateTpLevel(idx: number, value: number) {
    setTpLevels((prev) => prev.map((v, i) => (i === idx ? value : v)));
  }

  async function handleRun(): Promise<void> {
    if (saving || activeRunId) return;

    const normalizedSymbol = await applySymbolDraft();
    if (!normalizedSymbol) return;
    if (!longEnabled && !shortEnabled) {
      await dialog.alert({ title: 'Validation', message: 'Enable at least one bias direction: LONG and/or SHORT.', confirmText: 'OK' });
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const startTimeMs = fromLocalDateStr(startDate);
      const endTimeMs = fromLocalDateStr(endDate) + 86400_000 - 1;
      if (!Number.isFinite(startTimeMs) || !Number.isFinite(endTimeMs) || endTimeMs <= startTimeMs) {
        throw new Error('invalid_time_range');
      }

      const rulesSnapshot = normalizeTradingRules({
        ...rulesBase,
        coins: [{ symbol: normalizedSymbol, enabled: true, pct: 100, assetClass: inferAssetClassFromSymbol(normalizedSymbol) }],
        entryTimeframes,
        emergencyExitTimeframes,
        engulfingLookbackCandles,
        fvgRetrace,
        fvgMinWidthPct,
        maxLeverage,
        dailyDrawdown,
        tpLevels,
        slPct,
        exitClosePct,
        autoConfirm: false,
      });

      const res = await createBacktestRun({
        symbol: normalizedSymbol,
        biasMode,
        startTimeMs,
        endTimeMs,
        rules: rulesSnapshot,
      });

      setActiveRunId(res.run.id);
      setSelectedRun(res.run);
      setRuns((prev) => [res.run, ...prev]);
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }


  const sortedRuns = useMemo(() => {
    const next = [...runs];
    if (historySort === 'roi-desc') {
      next.sort((a, b) => (b.summary?.roiPct ?? Number.NEGATIVE_INFINITY) - (a.summary?.roiPct ?? Number.NEGATIVE_INFINITY));
      return next;
    }
    next.sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
    return next;
  }, [historySort, runs]);

  const historyPageCount = Math.max(1, Math.ceil(sortedRuns.length / HISTORY_PAGE_SIZE));
  const pagedRuns = useMemo(() => {
    const offset = (historyPage - 1) * HISTORY_PAGE_SIZE;
    return sortedRuns.slice(offset, offset + HISTORY_PAGE_SIZE);
  }, [historyPage, sortedRuns]);

  useEffect(() => {
    if (historyPage > historyPageCount) setHistoryPage(historyPageCount);
  }, [historyPage, historyPageCount]);

  if (loading) {
    return (
      <main className="terminal-layout">
        <Card title="Backtest" actions={<Badge tone="neutral">Loading</Badge>}>
          <p className="muted">Loading backtest settings and history...</p>
        </Card>
      </main>
    );
  }

  return (
    <main className="terminal-layout">
      {error ? <p className="stat-note" style={{ color: 'var(--danger, #ef4444)' }}>{error}</p> : null}

      <Card title="Execution controls" className="terminal-card terminal-card--narrow">
        <div className="exec-bias-list">
          <div className="exec-bias-row">
            <span className="exec-bias-label">Backtest bias</span>
            <div className="exec-bias-toggle">
              <Button
                variant="danger"
                className={`exec-bias-btn ${shortEnabled ? 'exec-bias-btn--active' : ''}`}
                onClick={() => {
                  if (shortEnabled && !longEnabled) return;
                  setShortEnabled((v) => !v);
                }}
              >
                SHORT
              </Button>
              <Button
                variant="primary"
                className={`exec-bias-btn ${longEnabled ? 'exec-bias-btn--active' : ''}`}
                onClick={() => {
                  if (longEnabled && !shortEnabled) return;
                  setLongEnabled((v) => !v);
                }}
              >
                LONG
              </Button>
            </div>
          </div>
        </div>
        <p className="stat-note muted" style={{ marginTop: 8 }}>
          Current mode: <strong>{biasMode.toUpperCase()}</strong>
          {biasMode === 'both' ? ' — backtest may open trades in both directions.' : biasMode === 'long' ? ' — long-only.' : ' — short-only.'}
        </p>
      </Card>

      <Card title="Backtest period" actions={<Badge tone="neutral">Range</Badge>}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, alignItems: 'center' }}>
          <div style={{ display: 'grid', gap: 6 }}>
            <span className="rules-label" style={{ margin: 0 }}>Start date</span>
            <input type="date" className="rules-input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div style={{ display: 'grid', gap: 6 }}>
            <span className="rules-label" style={{ margin: 0 }}>End date</span>
            <input type="date" className="rules-input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
        </div>
      </Card>

      <Card title="Coin Distribution" actions={<Badge tone="neutral">Single asset</Badge>}>
        <div className="rules-grid">
          <div className="rules-coin-row">
            <input
              type="text"
              value={symbolDraft}
              onChange={(e) => setSymbolDraft(normalizeAssetSymbol(e.target.value))}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void applySymbolDraft();
                }
              }}
              className="rules-input"
              style={{ width: 130, textTransform: 'uppercase' }}
              list="coinmaster-backtest-symbols"
              placeholder="SYMBOL"
            />
            <Button type="button" variant="secondary" className="rules-mini-btn" onClick={() => { void applySymbolDraft(); }}>Add</Button>
            <span className="muted" style={{ minWidth: 220, textAlign: 'center', fontSize: 12 }}>
              active backtest asset: <strong>{symbol}</strong> · {inferAssetClassFromSymbol(symbol)}
            </span>
          </div>
        </div>
        <datalist id="coinmaster-backtest-symbols">
          {availableSymbols.map((item) => <option key={item} value={item} />)}
        </datalist>
      </Card>

      <Card title="Entry / Exit Rules" actions={<Badge tone="neutral">Signals</Badge>}>
        <div className="rules-section">
          <p className="rules-label" style={{ marginBottom: 8 }}>
            Entry timeframe <span className="muted" style={{ fontWeight: 400 }}>(Bullish / Bearish Engulfing)</span>
          </p>
          <div className="rules-btn-group rules-btn-group--left">
            {TIMEFRAMES.map((tf) => (
              <Button key={tf} variant={entryTimeframes.includes(tf) ? 'primary' : 'secondary'} onClick={() => toggleTf(tf, entryTimeframes, setEntryTimeframes)}>
                {tf}
              </Button>
            ))}
          </div>
        </div>

        <div className="rules-section" style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '0.8rem', background: 'linear-gradient(180deg, var(--surface-2) 0%, #0f1c2e 100%)' }}>
          <p className="rules-label" style={{ marginBottom: 10 }}>Signal Sensitivity (Engulfing + FVG)</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, alignItems: 'center' }}>
            <div style={{ display: 'grid', gap: 6, justifyItems: 'start' }}>
              <span className="rules-label" style={{ margin: 0 }}>Lookback candles</span>
              <Stepper value={engulfingLookbackCandles} min={5} max={200} step={5} decimals={0} onChange={setEngulfingLookbackCandles} />
            </div>
            <div style={{ display: 'grid', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span className="rules-label" style={{ margin: 0 }}>FVG Retrace Level (1H/4H)</span>
                <div className="actions-row">
                  <input type="number" min={10} max={90} step={1} value={fvgRetrace} className="rules-input rules-input--sm" onChange={(e) => setFvgRetrace(clampNumber(Number(e.target.value), 10, 90))} />
                  <strong style={{ fontSize: 14 }}>{fvgRetrace}%</strong>
                </div>
              </div>
              <input type="range" min={10} max={90} value={fvgRetrace} onChange={(e) => setFvgRetrace(clampNumber(Number(e.target.value), 10, 90))} className="rules-range" style={{ width: '100%', marginTop: 0 }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted, #666)' }}><span>10%</span><span>50%</span><span>90%</span></div>
            </div>
            <div style={{ display: 'grid', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span className="rules-label" style={{ margin: 0 }}>FVG Min Width Filter</span>
                <div className="actions-row">
                  <input type="number" min={0} max={10} step={0.1} value={fvgMinWidthPct} className="rules-input rules-input--sm" onChange={(e) => setFvgMinWidthPct(clampNumber(Number(e.target.value), 0, 10))} />
                  <strong style={{ fontSize: 14 }}>{fvgMinWidthPct}%</strong>
                </div>
              </div>
              <input type="range" min={0} max={2} step={0.1} value={fvgMinWidthPct} onChange={(e) => setFvgMinWidthPct(clampNumber(Number(e.target.value), 0, 10))} className="rules-range" style={{ width: '100%', marginTop: 0 }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted, #666)' }}><span>0%</span><span>0.3%</span><span>2%</span></div>
            </div>
          </div>
        </div>

        <div className="rules-section">
          <p className="rules-label" style={{ marginBottom: 8 }}>
            Exit timeframe <span className="muted" style={{ fontWeight: 400 }}>(Opposite Engulfing)</span>
          </p>
          <div className="rules-btn-group rules-btn-group--left rules-btn-group--mb">
            {TIMEFRAMES.map((tf) => (
              <Button key={tf} variant={emergencyExitTimeframes.includes(tf) ? 'primary' : 'secondary'} onClick={() => toggleTf(tf, emergencyExitTimeframes, setEmergencyExitTimeframes)}>
                {tf}
              </Button>
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'center' }}>
            <span className="rules-label" style={{ margin: 0 }}>Close size on exit signal</span>
            <div className="actions-row" style={{ justifyContent: 'flex-end' }}>
              <Segmented options={EXIT_CLOSE_PRESETS} value={EXIT_CLOSE_PRESETS.includes(exitClosePct) ? exitClosePct : 50} format={(v) => `${v}%`} onChange={setExitClosePct} />
              <input type="number" min={0} max={100} step={1} value={exitClosePct} className="rules-input rules-input--sm" onChange={(e) => setExitClosePct(clampNumber(Number(e.target.value), 0, 100))} aria-label="Custom close size on exit signal" />
            </div>
          </div>
          <p className="stat-note muted" style={{ marginTop: 8, fontSize: 11 }}>
            {exitClosePct === 0 ? '0% disables emergency engulfing exit actions.' : exitClosePct < 100 ? `Partial close (${exitClosePct}%) moves SL to entry (break-even).` : '100% closes the full position.'}
          </p>
        </div>
      </Card>

      <Card title="Risk Management" actions={<Badge tone="danger">Risk</Badge>}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, alignItems: 'center' }}>
          <div style={{ display: 'grid', gap: 6, justifyItems: 'start' }}>
            <span className="rules-label" style={{ margin: 0 }}>Daily Drawdown Limit</span>
            <Stepper value={dailyDrawdown} min={0} max={100} step={0.5} unit="%" decimals={1} onChange={setDailyDrawdown} />
          </div>
          <div style={{ display: 'grid', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <span className="rules-label" style={{ margin: 0 }}>Max Leverage</span>
              <div className="actions-row">
                <input type="number" min={1} max={20} step={1} value={maxLeverage} className="rules-input rules-input--sm" onChange={(e) => setMaxLeverage(clampNumber(Number(e.target.value), 1, 20))} />
                <strong style={{ fontSize: 14 }}>{maxLeverage}x</strong>
              </div>
            </div>
            <input type="range" min={1} max={20} value={maxLeverage} onChange={(e) => setMaxLeverage(clampNumber(Number(e.target.value), 1, 20))} className="rules-range" style={{ marginTop: 0 }} />
          </div>
        </div>
        <p className="stat-note muted">Suggested: leverage ≤ 5x and drawdown ≤ 3% for conservative operation.</p>
      </Card>

      <Card title="Default TP / SL" actions={<Badge tone="success">Targets</Badge>}>
        <div className="rules-section rules-levels-grid">
          {tpLevels.map((tp, idx) => (
            <div key={idx} className="rules-level-row">
              <span className="rules-level-tag">TP{idx + 1}</span>
              <Stepper value={tp} min={0.5} max={100} step={0.5} unit="%" decimals={1} onChange={(v) => updateTpLevel(idx, v)} />
              {idx === 0 ? (tpLevels.length < 3 ? <Button type="button" variant="secondary" className="rules-mini-btn" onClick={addTpLevel}>+ TP</Button> : <span className="rules-mini-btn rules-mini-btn--ghost" />) : (
                <Button type="button" variant="danger" className="rules-mini-btn" onClick={() => removeTpLevel(idx)} title="Remove level">Remove</Button>
              )}
              {idx === 0 ? <span className="muted rules-level-hint">TP1 → move SL to entry</span> : <span className="rules-mini-btn rules-mini-btn--ghost" />}
            </div>
          ))}
          <div className="rules-level-row">
            <span className="rules-level-tag">SL</span>
            <Stepper value={slPct} min={0.5} max={100} step={0.5} unit="%" decimals={1} onChange={setSlPct} />
            <span className="rules-mini-btn rules-mini-btn--ghost" />
            <span className="rules-mini-btn rules-mini-btn--ghost" />
          </div>
        </div>
        <p className="stat-note muted">
          R:R → TP1: <strong>{slPct > 0 ? ((tpLevels[0] ?? 0) / slPct).toFixed(1) : '—'}:1</strong>
          {tpLevels.length > 1 ? <span> · TP2: <strong>{slPct > 0 ? ((tpLevels[1] ?? 0) / slPct).toFixed(1) : '—'}:1</strong></span> : null}
          {tpLevels.length > 2 ? <span> · TP3: <strong>{slPct > 0 ? ((tpLevels[2] ?? 0) / slPct).toFixed(1) : '—'}:1</strong></span> : null}
        </p>
      </Card>

      <div className="rules-apply-row">
        <Button variant="primary" fullWidth onClick={() => { void handleRun(); }} disabled={saving || Boolean(activeRunId)}>
          {saving ? 'Starting...' : activeRunId ? 'Backtest running...' : 'Run backtest'}
        </Button>
      </div>

      {selectedRun ? (
        <Card
          title={`Result: ${selectedRun.symbol} — ${selectedRun.status}`}
          actions={(
            <div className="actions-row">
              {selectedRun.aiAnalysis?.status === 'completed' && selectedRun.aiAnalysis?.report ? (
                <Button variant="secondary" onClick={() => setReportRun(selectedRun)}>Open AI report</Button>
              ) : null}
              <Button variant="secondary" onClick={() => applyRunToForm(selectedRun)}>Copy</Button>
            </div>
          )}
        >
          {selectedRun.status === 'queued' || selectedRun.status === 'running' ? (
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
            <>
              <div className="bt-result__grid">
                <div className="bt-stat"><span className="bt-stat__label">Net P&L</span><span className={`bt-stat__value ${selectedRun.summary.netPnlUsd >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}`}>{formatMoney(selectedRun.summary.netPnlUsd)}</span></div>
                <div className="bt-stat"><span className="bt-stat__label">ROI</span><span className={`bt-stat__value ${selectedRun.summary.roiPct >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}`}>{formatNumber(selectedRun.summary.roiPct)}%</span></div>
                <div className="bt-stat"><span className="bt-stat__label">Win Rate</span><span className="bt-stat__value">{formatNumber(selectedRun.summary.winRatePct)}%</span></div>
                <div className="bt-stat"><span className="bt-stat__label">Total Trades</span><span className="bt-stat__value">{selectedRun.summary.totalTrades}</span></div>
                <div className="bt-stat"><span className="bt-stat__label">Max Drawdown</span><span className="bt-stat__value bt-stat__value--negative">{formatNumber(selectedRun.summary.maxDrawdownPct)}%</span></div>
              </div>

              {selectedRun.bySymbol?.length > 0 ? (
                <div className="bt-symbol-stats">
                  <h4>Per-Symbol Breakdown</h4>
                  {selectedRun.bySymbol.map((row) => (
                    <div key={row.symbol} className="bt-symbol-row">
                      <strong>{row.symbol}</strong>
                      <span>W:{row.wins} L:{row.losses}</span>
                      <span>SL:{row.slCount}</span>
                      <span>TP1:{row.tp1Count} TP2:{row.tp2Count} TP3:{row.tp3Count}</span>
                      <span>Exit:{row.emergencyExitCount}</span>
                      <span className={row.netPnlUsd >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}>{formatMoney(row.netPnlUsd)}</span>
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="bt-applied-settings">
                <h4>Applied settings</h4>
                <div className="bt-applied-settings__grid">
                  {formatRulesSnapshot(selectedRun).map((item) => (
                    <div key={item.label} className="bt-applied-settings__item">
                      <span className="bt-applied-settings__label">{item.label}</span>
                      <span className="bt-applied-settings__value">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {selectedRun.artifacts ? (
                <div className="bt-artifacts">
                  <small>{selectedRun.artifacts.tradeCount} trade events · {selectedRun.artifacts.equityCurvePoints} equity points · Engine: {selectedRun.engineVersion}/{selectedRun.engineCommit?.slice(0, 8)}</small>
                </div>
              ) : null}
            </>
          ) : null}
        </Card>
      ) : null}

      <Card
        title="Run History"
        actions={(
          <div className="actions-row">
            <select className="rules-input rules-input--sm" value={historySort} onChange={(e) => setHistorySort(e.target.value as HistorySortMode)}>
              <option value="created-desc">Newest first</option>
              <option value="roi-desc">ROI % max → min</option>
            </select>
            <Badge tone="neutral">{runs.length} total</Badge>
          </div>
        )}
      >
        <div className="bt-history">
          {pagedRuns.length === 0 ? <p className="muted">No backtest runs yet.</p> : pagedRuns.map((run) => (
            <div
              key={run.id}
              role="button"
              tabIndex={0}
              className={`bt-history__item ${selectedRun?.id === run.id ? 'bt-history__item--selected' : ''}`}
              onClick={() => setSelectedRun(run)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setSelectedRun(run);
                }
              }}
            >
              <span className="bt-history__symbol">{run.symbol}</span>
              <span className="bt-history__dates">{toLocalDateStr(run.startTimeMs)} → {toLocalDateStr(run.endTimeMs)}</span>
              <Badge tone={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : 'neutral'}>{run.status}</Badge>
              {run.summary ? <span className={run.summary.netPnlUsd >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}>{formatMoney(run.summary.netPnlUsd)} ({formatNumber(run.summary.roiPct)}%)</span> : null}
              {run.aiAnalysis?.status === 'completed' && run.aiAnalysis?.report ? (
                <button
                  type="button"
                  className="bt-ai-btn bt-ai-btn--completed"
                  title="Open saved AI report"
                  onClick={(event) => { event.stopPropagation(); setReportRun(run); }}
                >
                  🤖
                </button>
              ) : null}
            </div>
          ))}
        </div>

        {historyPageCount > 1 ? (
          <div className="bt-pagination">
            <Button variant="secondary" onClick={() => setHistoryPage((p) => Math.max(1, p - 1))} disabled={historyPage <= 1}>Prev</Button>
            <span className="muted">Page {historyPage} / {historyPageCount}</span>
            <Button variant="secondary" onClick={() => setHistoryPage((p) => Math.min(historyPageCount, p + 1))} disabled={historyPage >= historyPageCount}>Next</Button>
          </div>
        ) : null}
      </Card>

      {reportRun?.aiAnalysis?.report ? (
        <div className="bt-report-overlay" onClick={() => setReportRun(null)}>
          <div className="bt-report-modal" onClick={(event) => event.stopPropagation()}>
            <div className="bt-report-modal__header">
              <div>
                <h3>AI Analysis — {reportRun.symbol}</h3>
                <div className="bt-report-modal__meta">
                  {reportRun.aiAnalysis.model ? `${reportRun.aiAnalysis.model} • ` : ''}{reportRun.aiAnalysis.completedAt ? formatDate(reportRun.aiAnalysis.completedAt) : 'saved report'}
                </div>
              </div>
              <button type="button" className="bt-report-close" onClick={() => setReportRun(null)}>×</button>
            </div>
            {reportRun.aiAnalysis.summary ? <div className="bt-report-section"><h4>Summary</h4><p>{reportRun.aiAnalysis.summary}</p></div> : null}
            {reportRun.aiAnalysis.recommendations?.length ? <div className="bt-report-section"><h4>Recommendations</h4><ul>{reportRun.aiAnalysis.recommendations.map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null}
            <div className="bt-report-section"><h4>Saved Report</h4><pre className="bt-report-pre">{reportRun.aiAnalysis.report}</pre></div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
