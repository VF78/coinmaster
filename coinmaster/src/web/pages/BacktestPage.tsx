import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { useDialog } from '../components/DialogProvider';
import type {
  BacktestBiasMode,
  BacktestRun,
  OptimizationParamRange,
  OptimizationResult,
  TradingRulesSettings,
  TradingRulesTimeframe,
} from '../../shared/dto.js';
import { cloneTradingRulesDefaults, inferAssetClassFromSymbol, normalizeTradingRules } from '../../shared/tradingRules.js';
import {
  createBacktestRun,
  friendlyErrorMessage,
  getBacktestRuns,
  getOptimizationResults,
  getOptimizationStatus,
  getTradingRuleSymbols,
  getTradingRules,
  startOptimization,
} from '../lib/api';
import { formatDate, formatMoney, formatNumber } from '../lib/format';

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];
const EXIT_CLOSE_PRESETS = [0, 25, 50, 75, 100];
const HISTORY_PAGE_SIZE = 15;
const POLL_INTERVAL_MS = 3_000;

type HistorySortMode = 'created-desc' | 'roi-desc';
type OptimizationSearchDepth = 'fast' | 'balanced' | 'deep';

const OPTIMIZATION_SEARCH_DEPTHS: Record<OptimizationSearchDepth, { label: string; divisor: number; hint: string }> = {
  fast: { label: 'Fast', divisor: 2, hint: 'Quicker grid, fewer candidate combinations.' },
  balanced: { label: 'Balanced', divisor: 4, hint: 'Default mode: good coverage without brute force.' },
  deep: { label: 'Deep', divisor: 8, hint: 'Denser grid, more candidates, still bounded.' },
};

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

interface OptimizationParamSpec {
  param: string;
  label: string;
  kind: 'int' | 'pct' | 'decimal';
  min: number;
  max: number;
}

const OPTIMIZATION_PARAM_SPECS: OptimizationParamSpec[] = [
  { param: 'slPct', label: 'SL %', kind: 'pct', min: 0.5, max: 25 },
  { param: 'tpLevels[0]', label: 'TP1 %', kind: 'pct', min: 0.5, max: 25 },
  { param: 'tpLevels[1]', label: 'TP2 %', kind: 'pct', min: 0.5, max: 35 },
  { param: 'tpLevels[2]', label: 'TP3 %', kind: 'pct', min: 0.5, max: 50 },
  { param: 'maxLeverage', label: 'Max leverage', kind: 'int', min: 1, max: 20 },
  { param: 'engulfingLookbackCandles', label: 'Lookback candles', kind: 'int', min: 5, max: 200 },
  { param: 'fvgRetrace', label: 'FVG retrace %', kind: 'pct', min: 10, max: 90 },
  { param: 'fvgMinWidthPct', label: 'FVG min width %', kind: 'decimal', min: 0, max: 2 },
  { param: 'exitClosePct', label: 'Exit close %', kind: 'pct', min: 0, max: 100 },
  { param: 'dailyDrawdown', label: 'Daily drawdown %', kind: 'pct', min: 0.5, max: 15 },
];

const OPTIMIZATION_INTEGER_PARAMS = new Set(['maxLeverage', 'engulfingLookbackCandles']);

function getRulesValue(rules: TradingRulesSettings, param: string): number {
  switch (param) {
    case 'slPct': return rules.slPct;
    case 'tpLevels[0]': return rules.tpLevels?.[0] ?? 6;
    case 'tpLevels[1]': return rules.tpLevels?.[1] ?? rules.tpLevels?.[0] ?? 9;
    case 'tpLevels[2]': return rules.tpLevels?.[2] ?? rules.tpLevels?.[1] ?? 12;
    case 'maxLeverage': return rules.maxLeverage;
    case 'engulfingLookbackCandles': return rules.engulfingLookbackCandles;
    case 'fvgRetrace': return rules.fvgRetrace;
    case 'fvgMinWidthPct': return rules.fvgMinWidthPct;
    case 'exitClosePct': return rules.exitClosePct;
    case 'dailyDrawdown': return rules.dailyDrawdown;
    default: return 0;
  }
}

function setRulesValue(rules: TradingRulesSettings, param: string, value: number) {
  switch (param) {
    case 'slPct': rules.slPct = value; break;
    case 'tpLevels[0]': rules.tpLevels = [value, rules.tpLevels?.[1] ?? value * 1.5, rules.tpLevels?.[2] ?? value * 2]; break;
    case 'tpLevels[1]': rules.tpLevels = [rules.tpLevels?.[0] ?? value / 1.5, value, rules.tpLevels?.[2] ?? value * 1.5]; break;
    case 'tpLevels[2]': rules.tpLevels = [rules.tpLevels?.[0] ?? value / 2, rules.tpLevels?.[1] ?? value / 1.5, value]; break;
    case 'maxLeverage': rules.maxLeverage = value; break;
    case 'engulfingLookbackCandles': rules.engulfingLookbackCandles = value; break;
    case 'fvgRetrace': rules.fvgRetrace = value; break;
    case 'fvgMinWidthPct': rules.fvgMinWidthPct = value; break;
    case 'exitClosePct': rules.exitClosePct = value; break;
    case 'dailyDrawdown': rules.dailyDrawdown = value; break;
  }
}

function autoOptimizationStep(kind: OptimizationParamSpec['kind'], min: number, max: number, depth: OptimizationSearchDepth): number {
  const span = Math.max(0, max - min);
  const raw = span / OPTIMIZATION_SEARCH_DEPTHS[depth].divisor || (kind === 'decimal' ? 0.1 : 1);
  if (kind === 'decimal') return Number(Math.max(0.1, raw).toFixed(2));
  return Math.max(1, Math.round(raw));
}

function normalizeOptimizationValue(param: string, value: number): number {
  return OPTIMIZATION_INTEGER_PARAMS.has(param) ? Math.round(value) : value;
}

function buildOptimizationDrafts(rules: TradingRulesSettings, depth: OptimizationSearchDepth = 'balanced') {
  return OPTIMIZATION_PARAM_SPECS.map((spec) => {
    const current = getRulesValue(rules, spec.param);
    const span = Math.max(0.0001, Math.abs(current) * 0.5 || (spec.max - spec.min) * 0.3);
    let min = clampNumber(current - span, spec.min, spec.max);
    let max = clampNumber(current + span, spec.min, spec.max);
    if (OPTIMIZATION_INTEGER_PARAMS.has(spec.param)) {
      min = Math.round(min);
      max = Math.round(max);
    }
    if (min === max) {
      min = spec.min;
      max = spec.max;
    }
    const step = autoOptimizationStep(spec.kind, min, max, depth);
    return { ...spec, enabled: ['slPct', 'tpLevels[0]', 'maxLeverage', 'engulfingLookbackCandles', 'fvgRetrace'].includes(spec.param), min, max, step: spec.kind === 'decimal' ? Number(step.toFixed(2)) : Math.max(1, Math.round(step)) };
  });
}

function estimateOptimizationCandidates(ranges: OptimizationParamRange[]) {
  return ranges.reduce((total, range) => {
    const count = Math.max(1, Math.floor((range.max - range.min) / range.step) + 1);
    return total * count;
  }, 1);
}

function formatOptimizationProgress(evaluated: number | null | undefined, total: number | null | undefined) {
  const safeEvaluated = Number.isFinite(evaluated as number) ? Math.max(0, Math.floor(Number(evaluated))) : 0;
  const safeTotal = Number.isFinite(total as number) ? Math.max(0, Math.floor(Number(total))) : 0;
  const pct = safeTotal > 0 ? Math.min(100, Math.round((safeEvaluated / safeTotal) * 100)) : 0;
  return { safeEvaluated, safeTotal, pct };
}

function formatRulesSnapshot(
  symbol: string,
  rules: TradingRulesSettings,
  startTimeMs: number,
  endTimeMs: number,
  biasMode?: BacktestBiasMode,
): Array<{ label: string; value: string }> {
  const coin = rules.coins[0];
  return [
    { label: 'Period', value: `${toLocalDateStr(startTimeMs)} → ${toLocalDateStr(endTimeMs)}` },
    { label: 'Bias', value: (biasMode ?? 'both').toUpperCase() },
    { label: 'Asset', value: coin?.symbol ?? symbol },
    { label: 'Asset class', value: coin?.assetClass ?? inferAssetClassFromSymbol(coin?.symbol ?? symbol) },
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
  const [optimizationResults, setOptimizationResults] = useState<OptimizationResult[]>([]);
  const [selectedOptimization, setSelectedOptimization] = useState<OptimizationResult | null>(null);
  const [optimizationModalRun, setOptimizationModalRun] = useState<BacktestRun | null>(null);
  const [optimizationDepth, setOptimizationDepth] = useState<OptimizationSearchDepth>('balanced');
  const [optimizationBlockedByBacktest, setOptimizationBlockedByBacktest] = useState<{ id: string; symbol: string; status: string } | null>(null);
  const [optimizationDrafts, setOptimizationDrafts] = useState<Array<ReturnType<typeof buildOptimizationDrafts>[number]>>([]);
  const [optimizationSubmitting, setOptimizationSubmitting] = useState(false);
  const [optimizationRunningId, setOptimizationRunningId] = useState<string | null>(null);
  const [optimizationInfo, setOptimizationInfo] = useState<string>('');
  const [historySort, setHistorySort] = useState<HistorySortMode>('created-desc');
  const [historyPage, setHistoryPage] = useState(1);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const selectedRunIdRef = useRef<string | null>(null);
  const selectedOptimizationIdRef = useRef<string | null>(null);
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

  const applyRulesSnapshotToForm = useCallback((rulesSnapshot: TradingRulesSettings, meta: { symbol: string; biasMode?: BacktestBiasMode; startTimeMs: number; endTimeMs: number }) => {
    const rules = normalizeTradingRules(rulesSnapshot);
    const coin = rules.coins[0];
    const selection = selectionFromBiasMode(meta.biasMode);
    setSymbol(coin?.symbol ?? meta.symbol);
    setSymbolDraft(coin?.symbol ?? meta.symbol);
    setStartDate(toLocalDateStr(meta.startTimeMs));
    setEndDate(toLocalDateStr(meta.endTimeMs));
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

  const applyOptimizationToForm = useCallback((opt: OptimizationResult) => {
    const rules = normalizeTradingRules(opt.bestParams ?? opt.baseRulesSnapshot);
    applyRulesSnapshotToForm(rules, {
      symbol: opt.symbol,
      biasMode: opt.biasMode,
      startTimeMs: opt.startTimeMs,
      endTimeMs: opt.endTimeMs,
    });
  }, [applyRulesSnapshotToForm]);

  function openOptimizationModal(run: BacktestRun) {
    setOptimizationDepth('balanced');
    const drafts = buildOptimizationDrafts(run.rulesSnapshot, 'balanced');
    setOptimizationModalRun(run);
    setOptimizationDrafts(drafts);
    setOptimizationInfo('');
  }

  function updateOptimizationDraft(index: number, patch: Partial<(typeof optimizationDrafts)[number]>) {
    setOptimizationDrafts((prev) => prev.map((item, i) => {
      if (i !== index) return item;
      const next = { ...item, ...patch };
      if (OPTIMIZATION_INTEGER_PARAMS.has(next.param)) {
        next.min = Math.round(next.min);
        next.max = Math.round(next.max);
      }
      return next;
    }));
  }

  function applyOptimizationDepth(depth: OptimizationSearchDepth) {
    setOptimizationDepth(depth);
    setOptimizationInfo(`Search depth set to ${OPTIMIZATION_SEARCH_DEPTHS[depth].label.toLowerCase()}.`);
  }

  function toggleOptimizationDraft(index: number, enabled: boolean) {
    setOptimizationDrafts((prev) => prev.map((item, i) => (i === index ? { ...item, enabled } : item)));
  }

  function buildOptimizationRequestRanges() {
    return optimizationDrafts
      .filter((item) => item.enabled)
      .map((item) => {
        const min = normalizeOptimizationValue(item.param, Math.min(item.min, item.max));
        const max = normalizeOptimizationValue(item.param, Math.max(item.min, item.max));
        const step = normalizeOptimizationValue(item.param, autoOptimizationStep(item.kind, min, max, optimizationDepth));
        return { param: item.param, min, max, step } satisfies OptimizationParamRange;
      });
  }

  async function handleStartOptimization() {
    if (!optimizationModalRun || optimizationSubmitting || optimizationRunningId) return;
    const ranges = buildOptimizationRequestRanges();
    if (ranges.length === 0) {
      await dialog.alert({ title: 'Validation', message: 'Select at least one parameter to optimize.', confirmText: 'OK' });
      return;
    }

    setOptimizationSubmitting(true);
    setOptimizationInfo('Starting optimization…');
    try {
      const res = await startOptimization({
        sourceRunId: optimizationModalRun.id,
        paramRanges: ranges,
      });
      setOptimizationRunningId(res.optimization.id);
      setSelectedOptimization(res.optimization);
      setOptimizationResults((prev) => [res.optimization, ...prev.filter((item) => item.id !== res.optimization.id)]);
      setOptimizationInfo(`Optimization started: ${ranges.length} params, ${estimateOptimizationCandidates(ranges)} candidate grid.`);
      setOptimizationModalRun(null);
    } catch (err) {
      setOptimizationInfo(friendlyErrorMessage(err));
    } finally {
      setOptimizationSubmitting(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [rulesRes, symbolsRes, runsRes, optimizationsRes, optimizationStatusRes] = await Promise.all([
          getTradingRules(),
          getTradingRuleSymbols(),
          getBacktestRuns(),
          getOptimizationResults(),
          getOptimizationStatus(),
        ]);
        if (cancelled) return;

        const normalized = normalizeTradingRules(rulesRes.rules);
        setRulesBase(normalized);
        setAvailableSymbols(symbolsRes.symbols ?? []);
        setRuns(runsRes.runs ?? []);
        setOptimizationResults(optimizationsRes.optimizations ?? []);
        setOptimizationRunningId(optimizationStatusRes.running ? optimizationStatusRes.activeId : null);
        const activeOpt = optimizationStatusRes.activeOptimization ?? null;
        const fallbackOpt = optimizationsRes.optimizations?.find((item) => item.status === 'completed') ?? null;
        setSelectedOptimization(activeOpt ?? fallbackOpt);
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
    selectedOptimizationIdRef.current = selectedOptimization?.id ?? null;
  }, [selectedOptimization]);

  useEffect(() => {
    reportRunIdRef.current = reportRun?.id ?? null;
  }, [reportRun]);

  useEffect(() => {
    const shouldPoll = Boolean(activeRunId || optimizationRunningId);
    if (!shouldPoll) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }

    async function poll() {
      try {
        const [listRes, optStatusRes, optListRes] = await Promise.all([
          getBacktestRuns(),
          getOptimizationStatus(),
          getOptimizationResults(),
        ]);

        const nextRuns = listRes.runs ?? [];
        setRuns(nextRuns);
        setOptimizationResults(optListRes.optimizations ?? []);
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

        const nextOptimization = optStatusRes.activeOptimization ?? optListRes.optimizations?.find((item) => item.status === 'completed') ?? null;
        setOptimizationRunningId(optStatusRes.running ? optStatusRes.activeId : null);
        setOptimizationBlockedByBacktest(optStatusRes.blockedByBacktestId ? {
          id: optStatusRes.blockedByBacktestId,
          symbol: optStatusRes.blockedByBacktestSymbol ?? 'unknown',
          status: optStatusRes.blockedByBacktestStatus ?? 'running',
        } : null);
        if (nextOptimization) setSelectedOptimization(nextOptimization);

        const selectedOptimizationId = selectedOptimizationIdRef.current;
        if (selectedOptimizationId) {
          const nextSelectedOptimization = optListRes.optimizations?.find((item) => item.id === selectedOptimizationId) ?? (optStatusRes.activeOptimization?.id === selectedOptimizationId ? optStatusRes.activeOptimization : null);
          if (nextSelectedOptimization) setSelectedOptimization(nextSelectedOptimization);
        }
      } catch {
        // ignore transient poll errors
      }
    }

    void poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [activeRunId, optimizationRunningId]);

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
    if (saving || activeRunId || optimizationRunningId) return;

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
        <Button variant="primary" fullWidth onClick={() => { void handleRun(); }} disabled={saving || Boolean(activeRunId) || Boolean(optimizationRunningId)}>
          {saving ? 'Starting...' : activeRunId ? 'Backtest running...' : optimizationRunningId ? 'Optimization running...' : 'Run backtest'}
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
                  {formatRulesSnapshot(selectedRun.symbol, selectedRun.rulesSnapshot, selectedRun.startTimeMs, selectedRun.endTimeMs, selectedRun.biasMode).map((item) => (
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

      {selectedOptimization ? (
        <Card
          title={`Result: ${selectedOptimization.symbol} — optimized`}
          actions={(
            <div className="actions-row">
              <Badge tone={selectedOptimization.status === 'completed' ? 'success' : selectedOptimization.status === 'failed' ? 'danger' : 'neutral'}>
                {selectedOptimization.status}
              </Badge>
              {selectedOptimization.status === 'completed' ? (
                <Button variant="secondary" onClick={() => applyOptimizationToForm(selectedOptimization)}>Copy</Button>
              ) : null}
            </div>
          )}
        >
          {selectedOptimization.status === 'queued' || selectedOptimization.status === 'running' ? (
            <div className="bt-running">
              <span className="bt-spin" aria-hidden="true" />
              <Badge tone="neutral">optimizing</Badge>
              {(() => {
                const progress = formatOptimizationProgress(selectedOptimization.evaluatedCandidates, selectedOptimization.totalCandidates);
                const isQueued = selectedOptimization.status === 'queued' && progress.safeTotal === 0 && progress.safeEvaluated === 0;
                return (
                  <>
                    <p>
                      {isQueued
                        ? (optimizationBlockedByBacktest
                          ? `Optimization queued… waiting for ${optimizationBlockedByBacktest.symbol} backtest ${optimizationBlockedByBacktest.id.slice(0, 6)} to finish.`
                          : 'Optimization queued… preparing candidate grid.')
                        : 'Optimization is running…'}
                    </p>
                    <div className="bt-progress">
                      <div className="bt-progress__meta">
                        <span>
                          {progress.safeEvaluated} / {progress.safeTotal > 0 ? progress.safeTotal : '—'} candidates
                        </span>
                        <strong>{progress.safeTotal > 0 ? `${progress.pct}%` : 'pending'}</strong>
                      </div>
                      <div className="bt-progress__bar" aria-hidden="true">
                        <div className="bt-progress__bar-fill" style={{ width: `${progress.safeTotal > 0 ? progress.pct : 0}%` }} />
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>
          ) : selectedOptimization.status === 'failed' ? (
            <div className="bt-failed">
              <Badge tone="danger">failed</Badge>
              <p>{selectedOptimization.error || 'Unknown optimization error'}</p>
            </div>
          ) : selectedOptimization.bestSummary ? (
            <>
              <div className="bt-result__grid">
                <div className="bt-stat"><span className="bt-stat__label">Net P&L</span><span className={`bt-stat__value ${selectedOptimization.bestSummary.netPnlUsd >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}`}>{formatMoney(selectedOptimization.bestSummary.netPnlUsd)}</span></div>
                <div className="bt-stat"><span className="bt-stat__label">ROI</span><span className={`bt-stat__value ${selectedOptimization.bestSummary.roiPct >= 0 ? 'bt-stat__value--positive' : 'bt-stat__value--negative'}`}>{formatNumber(selectedOptimization.bestSummary.roiPct)}%</span></div>
                <div className="bt-stat"><span className="bt-stat__label">Win Rate</span><span className="bt-stat__value">{formatNumber(selectedOptimization.bestSummary.winRatePct)}%</span></div>
                <div className="bt-stat"><span className="bt-stat__label">Total Trades</span><span className="bt-stat__value">{selectedOptimization.bestSummary.totalTrades}</span></div>
                <div className="bt-stat"><span className="bt-stat__label">Max Drawdown</span><span className="bt-stat__value bt-stat__value--negative">{formatNumber(selectedOptimization.bestSummary.maxDrawdownPct)}%</span></div>
              </div>

              {selectedOptimization.bestBySymbol?.length ? (
                <div className="bt-symbol-stats">
                  <h4>Per-Symbol Breakdown</h4>
                  {selectedOptimization.bestBySymbol.map((row) => (
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
                <h4>Optimized settings</h4>
                <div className="bt-applied-settings__grid">
                  {formatRulesSnapshot(
                    selectedOptimization.symbol,
                    normalizeTradingRules(selectedOptimization.bestParams ?? selectedOptimization.baseRulesSnapshot),
                    selectedOptimization.startTimeMs,
                    selectedOptimization.endTimeMs,
                    selectedOptimization.biasMode,
                  ).map((item) => (
                    <div key={item.label} className="bt-applied-settings__item">
                      <span className="bt-applied-settings__label">{item.label}</span>
                      <span className="bt-applied-settings__value">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bt-artifacts">
                {(() => {
                  const gridCandidates = selectedOptimization.searchSpaceCandidates ?? estimateOptimizationCandidates(selectedOptimization.paramRanges);
                  return (
                    <small>{selectedOptimization.evaluatedCandidates} / {selectedOptimization.totalCandidates} candidates · Grid: {gridCandidates.toLocaleString()} variants</small>
                  );
                })()}
                <small>Analyzed period: {toLocalDateStr(selectedOptimization.startTimeMs)} → {toLocalDateStr(selectedOptimization.endTimeMs)} · Engine: {selectedOptimization.engineVersion}/{selectedOptimization.engineCommit?.slice(0, 8)}</small>
              </div>
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
              {run.status === 'completed' ? (
                <Button
                  type="button"
                  variant="secondary"
                  className="bt-opt-btn"
                  disabled={Boolean(activeRunId) || Boolean(optimizationRunningId) || optimizationSubmitting}
                  onClick={(event) => {
                    event.stopPropagation();
                    openOptimizationModal(run);
                  }}
                >
                  Optimize
                </Button>
              ) : null}
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

      {optimizationModalRun ? (
        <div className="bt-report-overlay" onClick={() => { if (!optimizationSubmitting) setOptimizationModalRun(null); }}>
          <div className="bt-opt-modal" onClick={(event) => event.stopPropagation()}>
            <div className="bt-report-modal__header">
              <div>
                <h3>Optimize {optimizationModalRun.symbol}</h3>
                <div className="bt-report-modal__meta">
                  Select parameters, set min/max bounds, and start a bounded search for the best backtest settings.
                </div>
              </div>
              <button type="button" className="bt-report-close" onClick={() => setOptimizationModalRun(null)} disabled={optimizationSubmitting}>×</button>
            </div>

            <div className="bt-opt-modal__summary">
              <span>Source run: {optimizationModalRun.symbol}</span>
              <span>{toLocalDateStr(optimizationModalRun.startTimeMs)} → {toLocalDateStr(optimizationModalRun.endTimeMs)}</span>
              <span>Bias: {optimizationModalRun.biasMode.toUpperCase()}</span>
            </div>

            <div className="bt-opt-depth">
              <span className="bt-opt-depth__label">Search depth</span>
              <div className="rules-segmented bt-opt-depth__buttons" role="tablist" aria-label="Optimization search depth">
                {(Object.keys(OPTIMIZATION_SEARCH_DEPTHS) as OptimizationSearchDepth[]).map((depth) => {
                  const meta = OPTIMIZATION_SEARCH_DEPTHS[depth];
                  const active = optimizationDepth === depth;
                  return (
                    <button
                      key={depth}
                      type="button"
                      className={`rules-segmented__btn ${active ? 'rules-segmented__btn--active' : ''}`}
                      onClick={() => applyOptimizationDepth(depth)}
                      disabled={optimizationSubmitting}
                      title={meta.hint}
                    >
                      {meta.label}
                    </button>
                  );
                })}
              </div>
              <p className="muted stat-note" style={{ margin: 0 }}>
                {OPTIMIZATION_SEARCH_DEPTHS[optimizationDepth].hint}
              </p>
            </div>

            <div className="bt-opt-modal__list">
              {optimizationDrafts.map((item, index) => (
                <div key={item.param} className={`bt-opt-row ${item.enabled ? 'bt-opt-row--active' : ''}`}>
                  <label className="bt-opt-row__toggle">
                    <input
                      type="checkbox"
                      checked={item.enabled}
                      disabled={optimizationSubmitting}
                      onChange={(e) => toggleOptimizationDraft(index, e.target.checked)}
                    />
                    <span>{item.label}</span>
                  </label>
                  <div className="bt-opt-row__inputs">
                    {(() => {
                      const spec = OPTIMIZATION_PARAM_SPECS[index];
                      return (
                        <>
                          <label>
                            <span>Min</span>
                            <input
                              type="number"
                              className="rules-input rules-input--sm"
                              value={item.min}
                              step={item.kind === 'decimal' ? 0.1 : 1}
                              min={spec.min}
                              max={spec.max}
                              disabled={optimizationSubmitting || !item.enabled}
                              onChange={(e) => updateOptimizationDraft(index, { min: Number(e.target.value) })}
                            />
                          </label>
                          <label>
                            <span>Max</span>
                            <input
                              type="number"
                              className="rules-input rules-input--sm"
                              value={item.max}
                              step={item.kind === 'decimal' ? 0.1 : 1}
                              min={spec.min}
                              max={spec.max}
                              disabled={optimizationSubmitting || !item.enabled}
                              onChange={(e) => updateOptimizationDraft(index, { max: Number(e.target.value) })}
                            />
                          </label>
                        </>
                      );
                    })()}
                  </div>
                  <div className="bt-opt-row__meta">
                    Auto step: <strong>{autoOptimizationStep(item.kind, Math.min(item.min, item.max), Math.max(item.min, item.max), optimizationDepth)}</strong>
                  </div>
                </div>
              ))}
            </div>

            <div className="bt-opt-modal__footer">
            <div className="bt-opt-modal__budget">
              {(() => {
                const ranges = buildOptimizationRequestRanges();
                const candidateCount = estimateOptimizationCandidates(ranges);
                  const capNote = candidateCount > 5000 ? ' (capped at 5,000 by the worker)' : '';
                  return <span>Estimated search size: <strong>{Math.min(candidateCount, 5000).toLocaleString()}</strong> candidates{capNote}</span>;
              })()}
              <span>Search is bounded and runs in a separate process so the main app stays responsive.</span>
            </div>
              <div className="actions-row">
                <Button variant="secondary" onClick={() => setOptimizationModalRun(null)} disabled={optimizationSubmitting}>Cancel</Button>
                <Button variant="primary" onClick={() => { void handleStartOptimization(); }} disabled={optimizationSubmitting || optimizationRunningId !== null}>
                  {optimizationSubmitting ? 'Starting…' : optimizationRunningId ? 'Optimization running…' : 'Start optimization'}
                </Button>
              </div>
            </div>

            {optimizationInfo ? <p className="stat-note muted" style={{ marginTop: 8 }}>{optimizationInfo}</p> : null}
          </div>
        </div>
      ) : null}

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
