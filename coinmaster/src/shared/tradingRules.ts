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
  fvgRetrace: 50,
  maxLeverage: 5,
  dailyDrawdown: 3,
  tpPct: 6,
  slPct: 2,
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
  base.fvgRetrace = clampNumber(raw.fvgRetrace, 10, 90, base.fvgRetrace);
  base.maxLeverage = clampNumber(raw.maxLeverage, 1, 50, base.maxLeverage);
  base.dailyDrawdown = clampNumber(raw.dailyDrawdown, 0, 100, base.dailyDrawdown);
  base.tpPct = clampNumber(raw.tpPct, 0, 1000, base.tpPct);
  base.slPct = clampNumber(raw.slPct, 0, 1000, base.slPct);
  base.autoConfirm = Boolean(raw.autoConfirm);

  return base;
}
