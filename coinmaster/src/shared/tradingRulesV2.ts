import type {
  WaveEngineBreakBasis,
  WaveEngineDirectionTimeframe,
  WaveEngineEntryTimeframe,
  WaveEngineNumericRange,
  WaveEngineOptimizationRanges,
  WaveEngineResearchMode,
  WaveEngineRulesSettings,
  WaveEngineSymbolSettings,
  WaveEngineType,
} from './dto.js';
import { normalizeRuleSymbol } from './tradingRules.js';

const WAVE_ENGINE_TYPES: WaveEngineType[] = ['atr_zigzag', 'pct_zigzag'];
const BREAK_BASIS_VALUES: WaveEngineBreakBasis[] = ['wick', 'close'];
const ENTRY_TIMEFRAMES: WaveEngineEntryTimeframe[] = ['5m', '15m', '1h'];
const RESEARCH_MODES: WaveEngineResearchMode[] = ['single', 'matrix', 'native_validation'];
const DIRECTION_TIMEFRAME: WaveEngineDirectionTimeframe = '4h';

const DEFAULT_SYMBOLS: WaveEngineSymbolSettings[] = [
  { symbol: 'BTC', pair: 'BTC/USDC:USDC', enabled: true },
  { symbol: 'ETH', pair: 'ETH/USDC:USDC', enabled: true },
  { symbol: 'HYPE', pair: 'HYPE/USDC:USDC', enabled: true },
];

export const WAVE_ENGINE_RANGE_LIMITS = {
  atrMult: { min: 1.5, max: 4, step: 0.25 },
  pctMove: { min: 0.02, max: 0.05, step: 0.005 },
  flatExtremeLookbackHours: { min: 60, max: 150, step: 10 },
  pullbackRatio: { min: 0.4, max: 0.8, step: 0.05 },
  maxSlPct: { min: 0.02, max: 0.04, step: 0.005 },
  tp2Pct: { min: 0.02, max: 0.04, step: 0.005 },
  tp3Pct: { min: 0.04, max: 0.08, step: 0.01 },
  timeStopHours: { min: 4, max: 16, step: 2 },
} satisfies WaveEngineOptimizationRanges;

export const DEFAULT_WAVE_ENGINE_RULES: WaveEngineRulesSettings = {
  enabled: false,
  symbols: DEFAULT_SYMBOLS.map((item) => ({ ...item })),
  directionTf: DIRECTION_TIMEFRAME,
  entryTimeframes: [...ENTRY_TIMEFRAMES],
  waveEngine: 'atr_zigzag',
  breakBasis: 'wick',
  atrMult: 2.5,
  pctMove: 0.03,
  flatExtremeLookbackHours: 100,
  pullbackRatio: 0.5,
  bodyConfirmation: 'body_engulfing',
  impulseSlBuffer: 0.0033,
  maxSlPct: 0.03,
  tp1MaxPct: 0.015,
  tp2Pct: 0.03,
  tp3Pct: 0.06,
  timeStopHours: 8,
  optimization: {
    mode: 'matrix',
    ranges: JSON.parse(JSON.stringify(WAVE_ENGINE_RANGE_LIMITS)) as WaveEngineOptimizationRanges,
  },
};

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}

function clampInteger(value: unknown, min: number, max: number, fallback: number): number {
  return Math.round(clampNumber(value, min, max, fallback));
}

function normalizeEnumValue<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  const raw = String(value ?? '').trim().toLowerCase();
  const matched = allowed.find((item) => item.toLowerCase() === raw);
  return matched ?? fallback;
}

function normalizeEntryTimeframes(value: unknown, fallback: WaveEngineEntryTimeframe[]): WaveEngineEntryTimeframe[] {
  if (!Array.isArray(value) || value.length === 0) return [...fallback];

  const result: WaveEngineEntryTimeframe[] = [];
  for (const item of value) {
    const raw = String(item ?? '').trim().toLowerCase();
    const normalized = ENTRY_TIMEFRAMES.find((timeframe) => timeframe.toLowerCase() === raw);
    if (normalized && !result.includes(normalized)) result.push(normalized);
  }

  return result.length > 0 ? result : [...fallback];
}

function normalizePair(value: unknown): string | undefined {
  const raw = String(value ?? '').trim().toUpperCase();
  return raw ? raw : undefined;
}

function defaultPairForSymbol(symbol: string): string {
  return `${symbol}/USDC:USDC`;
}

function normalizeSymbols(value: unknown, fallback: WaveEngineSymbolSettings[]): WaveEngineSymbolSettings[] {
  if (!Array.isArray(value) || value.length === 0) return fallback.map((item) => ({ ...item }));

  const result: WaveEngineSymbolSettings[] = [];
  const seen = new Set<string>();
  for (const item of value) {
    if (!item || typeof item !== 'object') continue;
    const row = item as Record<string, unknown>;
    const symbol = normalizeRuleSymbol(row.symbol);
    if (!symbol || seen.has(symbol)) continue;
    seen.add(symbol);
    const core = symbol.includes(':') ? symbol.split(':', 2)[1] : symbol;

    result.push({
      symbol,
      enabled: row.enabled !== false,
      pair: normalizePair(row.pair) ?? defaultPairForSymbol(core),
    });
  }

  return result.length > 0 ? result : fallback.map((item) => ({ ...item }));
}

function normalizeRange(value: unknown, limits: WaveEngineNumericRange): WaveEngineNumericRange {
  const raw = value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
  let min = clampNumber(raw.min, limits.min, limits.max, limits.min);
  let max = clampNumber(raw.max, limits.min, limits.max, limits.max);
  if (min > max) [min, max] = [max, min];
  const step = clampNumber(raw.step, limits.step, limits.max - limits.min || limits.step, limits.step);
  return { min, max, step };
}

function normalizeOptimization(value: unknown): WaveEngineRulesSettings['optimization'] {
  const raw = value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
  const rawRanges = raw.ranges && typeof raw.ranges === 'object' ? (raw.ranges as Record<string, unknown>) : {};

  return {
    mode: normalizeEnumValue(raw.mode, RESEARCH_MODES, DEFAULT_WAVE_ENGINE_RULES.optimization.mode),
    ranges: {
      atrMult: normalizeRange(rawRanges.atrMult, WAVE_ENGINE_RANGE_LIMITS.atrMult),
      pctMove: normalizeRange(rawRanges.pctMove, WAVE_ENGINE_RANGE_LIMITS.pctMove),
      flatExtremeLookbackHours: normalizeRange(rawRanges.flatExtremeLookbackHours, WAVE_ENGINE_RANGE_LIMITS.flatExtremeLookbackHours),
      pullbackRatio: normalizeRange(rawRanges.pullbackRatio, WAVE_ENGINE_RANGE_LIMITS.pullbackRatio),
      maxSlPct: normalizeRange(rawRanges.maxSlPct, WAVE_ENGINE_RANGE_LIMITS.maxSlPct),
      tp2Pct: normalizeRange(rawRanges.tp2Pct, WAVE_ENGINE_RANGE_LIMITS.tp2Pct),
      tp3Pct: normalizeRange(rawRanges.tp3Pct, WAVE_ENGINE_RANGE_LIMITS.tp3Pct),
      timeStopHours: normalizeRange(rawRanges.timeStopHours, WAVE_ENGINE_RANGE_LIMITS.timeStopHours),
    },
  };
}

export function cloneWaveEngineRulesDefaults(): WaveEngineRulesSettings {
  return JSON.parse(JSON.stringify(DEFAULT_WAVE_ENGINE_RULES)) as WaveEngineRulesSettings;
}

export function normalizeWaveEngineRules(input: unknown): WaveEngineRulesSettings {
  const base = cloneWaveEngineRulesDefaults();
  const raw = input && typeof input === 'object' ? (input as Record<string, unknown>) : {};

  base.enabled = raw.enabled === true;
  base.symbols = normalizeSymbols(raw.symbols, base.symbols);
  base.directionTf = DIRECTION_TIMEFRAME;
  base.entryTimeframes = normalizeEntryTimeframes(raw.entryTimeframes, base.entryTimeframes);
  base.waveEngine = normalizeEnumValue(raw.waveEngine, WAVE_ENGINE_TYPES, base.waveEngine);
  base.breakBasis = normalizeEnumValue(raw.breakBasis, BREAK_BASIS_VALUES, base.breakBasis);
  base.atrMult = clampNumber(raw.atrMult, WAVE_ENGINE_RANGE_LIMITS.atrMult.min, WAVE_ENGINE_RANGE_LIMITS.atrMult.max, base.atrMult);
  base.pctMove = clampNumber(raw.pctMove, WAVE_ENGINE_RANGE_LIMITS.pctMove.min, WAVE_ENGINE_RANGE_LIMITS.pctMove.max, base.pctMove);
  base.flatExtremeLookbackHours = clampInteger(raw.flatExtremeLookbackHours, WAVE_ENGINE_RANGE_LIMITS.flatExtremeLookbackHours.min, WAVE_ENGINE_RANGE_LIMITS.flatExtremeLookbackHours.max, base.flatExtremeLookbackHours);
  base.pullbackRatio = clampNumber(raw.pullbackRatio, WAVE_ENGINE_RANGE_LIMITS.pullbackRatio.min, WAVE_ENGINE_RANGE_LIMITS.pullbackRatio.max, base.pullbackRatio);
  base.bodyConfirmation = 'body_engulfing';
  base.impulseSlBuffer = 0.0033;
  base.maxSlPct = clampNumber(raw.maxSlPct, WAVE_ENGINE_RANGE_LIMITS.maxSlPct.min, WAVE_ENGINE_RANGE_LIMITS.maxSlPct.max, base.maxSlPct);
  base.tp1MaxPct = 0.015;
  base.tp2Pct = clampNumber(raw.tp2Pct, WAVE_ENGINE_RANGE_LIMITS.tp2Pct.min, WAVE_ENGINE_RANGE_LIMITS.tp2Pct.max, base.tp2Pct);
  base.tp3Pct = clampNumber(raw.tp3Pct, WAVE_ENGINE_RANGE_LIMITS.tp3Pct.min, WAVE_ENGINE_RANGE_LIMITS.tp3Pct.max, base.tp3Pct);
  base.timeStopHours = clampInteger(raw.timeStopHours, WAVE_ENGINE_RANGE_LIMITS.timeStopHours.min, WAVE_ENGINE_RANGE_LIMITS.timeStopHours.max, base.timeStopHours);
  base.optimization = normalizeOptimization(raw.optimization);

  return base;
}
