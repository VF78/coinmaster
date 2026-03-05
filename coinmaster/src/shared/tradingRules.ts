import type { TradingRulesSettings, TradingRulesTimeframe } from './dto.js';

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];
const DEFAULT_SYMBOLS = ['BTC', 'ETH', 'SOL'] as const;

export const DEFAULT_TRADING_RULES: TradingRulesSettings = {
  coins: [
    { symbol: 'BTC', enabled: true, pct: 50 },
    { symbol: 'ETH', enabled: true, pct: 30 },
    { symbol: 'SOL', enabled: true, pct: 20 }
  ],
  entryTf: '15m',
  exitTf: '1h',
  entryTimeframes: ['15m'],
  emergencyExitTimeframes: ['1h'],
  engulfingLookbackCandles: 30,
  fvgRetrace: 50,
  maxLeverage: 5,
  dailyDrawdown: 3,
  tpPct: 6,
  tpLevels: [6],
  slPct: 2,
  exitClosePct: 50,
  autoConfirm: false
};

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}

function normalizeTimeframe(value: unknown, fallback: TradingRulesTimeframe): TradingRulesTimeframe {
  const tf = String(value ?? '').toLowerCase();
  const matched = TIMEFRAMES.find((x) => x.toLowerCase() === tf);
  return matched ?? fallback;
}

function normalizeTimeframeArray(value: unknown, fallback: TradingRulesTimeframe[]): TradingRulesTimeframe[] {
  if (!Array.isArray(value) || value.length === 0) return [...fallback];
  const result: TradingRulesTimeframe[] = [];
  for (const item of value) {
    const tf = String(item ?? '').toLowerCase();
    const matched = TIMEFRAMES.find((x) => x.toLowerCase() === tf);
    if (matched && !result.includes(matched)) result.push(matched);
  }
  return result.length > 0 ? result : [...fallback];
}

export function cloneTradingRulesDefaults(): TradingRulesSettings {
  return JSON.parse(JSON.stringify(DEFAULT_TRADING_RULES)) as TradingRulesSettings;
}

export function normalizeTradingRules(input: unknown): TradingRulesSettings {
  const base = cloneTradingRulesDefaults();
  const raw = (input && typeof input === 'object') ? (input as Record<string, unknown>) : {};

  const coinsRaw = Array.isArray(raw.coins) ? raw.coins : [];
  const bySymbol = new Map<string, { enabled: boolean; pct: number }>();

  for (const row of coinsRaw) {
    if (!row || typeof row !== 'object') continue;
    const item = row as Record<string, unknown>;
    const symbol = String(item.symbol ?? '').toUpperCase();
    if (!DEFAULT_SYMBOLS.includes(symbol as (typeof DEFAULT_SYMBOLS)[number])) continue;
    bySymbol.set(symbol, {
      enabled: Boolean(item.enabled),
      pct: clampNumber(item.pct, 0, 100, 0)
    });
  }

  base.coins = DEFAULT_SYMBOLS.map((symbol) => {
    const value = bySymbol.get(symbol);
    if (!value) {
      const fallback = DEFAULT_TRADING_RULES.coins.find((c) => c.symbol === symbol)!;
      return { ...fallback };
    }
    return {
      symbol,
      enabled: value.enabled,
      pct: value.pct
    };
  });

  base.entryTf = normalizeTimeframe(raw.entryTf, base.entryTf);
  base.exitTf = normalizeTimeframe(raw.exitTf, base.exitTf);

  // ── Multi-timeframe arrays (back-compat: migrate from scalar if arrays absent) ──
  base.entryTimeframes = normalizeTimeframeArray(raw.entryTimeframes, [base.entryTf]);
  base.emergencyExitTimeframes = normalizeTimeframeArray(raw.emergencyExitTimeframes, [base.exitTf]);
  base.engulfingLookbackCandles = clampNumber(raw.engulfingLookbackCandles, 1, 500, base.engulfingLookbackCandles);

  // Keep scalar fields in sync with first element of array
  base.entryTf = base.entryTimeframes[0];
  base.exitTf = base.emergencyExitTimeframes[0];

  base.fvgRetrace = clampNumber(raw.fvgRetrace, 10, 90, base.fvgRetrace);
  base.maxLeverage = clampNumber(raw.maxLeverage, 1, 50, base.maxLeverage);
  base.dailyDrawdown = clampNumber(raw.dailyDrawdown, 0, 100, base.dailyDrawdown);
  base.slPct = clampNumber(raw.slPct, 0, 1000, base.slPct);
  base.exitClosePct = clampNumber(raw.exitClosePct, 0, 100, base.exitClosePct);

  // tpLevels: 1–3 values, each 0–1000, sorted ascending.
  // Back-compat: if tpLevels absent but tpPct present, migrate.
  if (Array.isArray(raw.tpLevels) && raw.tpLevels.length > 0) {
    const levels = (raw.tpLevels as unknown[])
      .slice(0, 3)
      .map((v) => clampNumber(v, 0, 1000, base.tpLevels[0]))
      .filter((v) => v > 0)
      .sort((a, b) => a - b);
    base.tpLevels = levels.length > 0 ? levels : [base.tpPct];
  } else {
    const legacy = clampNumber(raw.tpPct, 0, 1000, base.tpPct);
    base.tpLevels = [legacy > 0 ? legacy : base.tpPct];
  }
  // Keep scalar tpPct in sync with first TP level for back-compat
  base.tpPct = base.tpLevels[0];

  base.autoConfirm = Boolean(raw.autoConfirm);

  return base;
}
