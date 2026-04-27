import type {
  AssetClass,
  BiasMode,
  BiasPolicySettings,
  TradingRulesSettings,
  TradingRulesTimeframe
} from './dto.js';

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];
const ASSET_CLASSES: AssetClass[] = ['crypto', 'commodity', 'forex', 'index', 'other'];

const DEFAULT_COINS = [
  { symbol: 'BTC', enabled: true, pct: 50, assetClass: 'crypto' as AssetClass },
  { symbol: 'ETH', enabled: true, pct: 30, assetClass: 'crypto' as AssetClass },
  { symbol: 'SOL', enabled: true, pct: 20, assetClass: 'crypto' as AssetClass },
] as const;

const DEFAULT_BIAS_POLICY: BiasPolicySettings = {
  symbolOverrides: {},
};

const SYMBOL_RE = /^(?:[A-Z0-9][A-Z0-9_-]{1,24}|[a-z0-9][a-z0-9_-]{0,15}:[A-Z0-9][A-Z0-9_-]{1,24})$/;
const FX_CODES = new Set(['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'NZD', 'CAD', 'SEK', 'NOK', 'CNH']);

export const DEFAULT_TRADING_RULES: TradingRulesSettings = {
  coins: DEFAULT_COINS.map((coin) => ({ ...coin })),
  entryTf: '15m',
  exitTf: '1h',
  entryTimeframes: ['15m'],
  emergencyExitTimeframes: ['1h'],
  engulfingLookbackCandles: 30,
  fvgRetrace: 50,
  fvgMinWidthPct: 0.3,
  fvgRequireSweep: false,
  fvgSweepLookbackCandles: 20,
  fvgRequireFirstTouch: false,
  maxZoneAgeCandles: 12,
  fvgRequireConfirmation: false,
  fvgConfirmationTimeframes: ['15m'],
  maxLeverage: 5,
  dailyDrawdown: 3,
  tpPct: 6,
  tpLevels: [6],
  slPct: 2,
  exitClosePct: 50,
  autoConfirm: false,
  biasPolicy: JSON.parse(JSON.stringify(DEFAULT_BIAS_POLICY)) as BiasPolicySettings,

  // ── Stage-1 SignalQualityContext / portfolio defaults (issue #61) ───
  // Conservative defaults that preserve current behaviour: thresholds set so
  // optional gates are permissive until the operator opts in via the UI.
  regimeTf: '1h',
  regimeFilterEnabled: true,
  adxEnabled: false,
  adxMin: 0,
  minImpulseAtrEnabled: false,
  minImpulseAtr: 0,
  timeStopEnabled: false,
  timeStopBars: 0,
  riskPerTradeEnabled: false,
  riskPerTradePct: 0,
  eventLockoutEnabled: false,
  eventLockoutMinutes: 0,
  portfolioGrossCapEnabled: true,
  portfolioGrossCap: 200,
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

function normalizeRuleSymbol(value: unknown): string | null {
  const raw = String(value ?? '').trim();
  if (!raw) return null;

  if (raw.includes(':')) {
    const [namespaceRaw, symbolRaw] = raw.split(':', 2);
    const namespace = String(namespaceRaw ?? '').trim().toLowerCase();
    const symbol = String(symbolRaw ?? '').trim().toUpperCase();
    if (!namespace || !symbol) return null;
    const normalized = `${namespace}:${symbol}`;
    return SYMBOL_RE.test(normalized) ? normalized : null;
  }

  const symbol = raw.toUpperCase();
  if (!SYMBOL_RE.test(symbol)) return null;
  return symbol;
}

function normalizeBiasMode(value: unknown, fallback: BiasMode): BiasMode {
  const raw = String(value ?? '').trim().toLowerCase();
  return raw === 'global' || raw === 'symbol' ? raw : fallback;
}

export function inferAssetClassFromSymbol(symbol: string): AssetClass {
  const normalized = normalizeRuleSymbol(symbol) ?? String(symbol ?? '').trim().toUpperCase();
  const core = normalized.includes(':') ? normalized.split(':', 2)[1] : normalized;
  const token = String(core ?? '').toUpperCase();

  if (!token) return 'other';

  if (/(?:^|[^A-Z])(XAU|XAG|GOLD|SILVER|WTI|BRENT|OIL)(?:[^A-Z]|$)/.test(token)) {
    return 'commodity';
  }

  if (token.length === 6) {
    const base = token.slice(0, 3);
    const quote = token.slice(3);
    if (FX_CODES.has(base) && FX_CODES.has(quote)) return 'forex';
  }

  if (/(SPX|SP500|NASDAQ|NQ|NDX|DJI|DOW|DAX|FTSE|HSI|NIKKEI)/.test(token)) {
    return 'index';
  }

  if (/(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|LTC|DOT|LINK|MATIC|TON|TRX|ATOM|SUI|ARB|OP)/.test(token)) {
    return 'crypto';
  }

  // Default for unknown perps remains crypto to preserve historical behavior.
  return 'crypto';
}

export function normalizeAssetClass(value: unknown, fallback: AssetClass = 'crypto'): AssetClass {
  const raw = String(value ?? '').trim().toLowerCase();
  return ASSET_CLASSES.includes(raw as AssetClass) ? (raw as AssetClass) : fallback;
}

function normalizeBiasPolicy(value: unknown, fallback: BiasPolicySettings): BiasPolicySettings {
  const base = JSON.parse(JSON.stringify(fallback)) as BiasPolicySettings;
  const raw = value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

  const symbolOverridesRaw = raw.symbolOverrides && typeof raw.symbolOverrides === 'object'
    ? (raw.symbolOverrides as Record<string, unknown>)
    : {};

  const normalizedOverrides: BiasPolicySettings['symbolOverrides'] = {};
  for (const [symbolRaw, overrideRaw] of Object.entries(symbolOverridesRaw)) {
    const symbol = normalizeRuleSymbol(symbolRaw);
    if (!symbol || !overrideRaw || typeof overrideRaw !== 'object') continue;

    const override = overrideRaw as Record<string, unknown>;
    const mode = normalizeBiasMode(override.mode, 'global');

    normalizedOverrides[symbol] = { mode };
  }

  base.symbolOverrides = normalizedOverrides;
  return base;
}

export function cloneTradingRulesDefaults(): TradingRulesSettings {
  return JSON.parse(JSON.stringify(DEFAULT_TRADING_RULES)) as TradingRulesSettings;
}

export function normalizeTradingRules(input: unknown): TradingRulesSettings {
  const base = cloneTradingRulesDefaults();
  const raw = (input && typeof input === 'object') ? (input as Record<string, unknown>) : {};

  const coinsRaw = Array.isArray(raw.coins) ? raw.coins : [];
  const normalizedCoins: TradingRulesSettings['coins'] = [];
  const seenSymbols = new Set<string>();

  for (const row of coinsRaw) {
    if (!row || typeof row !== 'object') continue;
    const item = row as Record<string, unknown>;
    const symbol = normalizeRuleSymbol(item.symbol);
    if (!symbol || seenSymbols.has(symbol)) continue;
    seenSymbols.add(symbol);

    const inferredClass = inferAssetClassFromSymbol(symbol);
    normalizedCoins.push({
      symbol,
      enabled: Boolean(item.enabled),
      pct: clampNumber(item.pct, 0, 100, 0),
      assetClass: normalizeAssetClass(item.assetClass, inferredClass),
    });
  }

  base.coins = normalizedCoins.length > 0
    ? normalizedCoins
    : DEFAULT_COINS.map((coin) => ({ ...coin }));

  base.entryTf = normalizeTimeframe(raw.entryTf, base.entryTf);
  base.exitTf = normalizeTimeframe(raw.exitTf, base.exitTf);

  // ── Multi-timeframe arrays (back-compat: migrate from scalar if arrays absent) ──
  base.entryTimeframes = normalizeTimeframeArray(raw.entryTimeframes, [base.entryTf]);
  base.emergencyExitTimeframes = normalizeTimeframeArray(raw.emergencyExitTimeframes, [base.exitTf]);
  base.engulfingLookbackCandles = Math.round(clampNumber(raw.engulfingLookbackCandles, 1, 500, base.engulfingLookbackCandles));

  // Keep scalar fields in sync with first element of array
  base.entryTf = base.entryTimeframes[0];
  base.exitTf = base.emergencyExitTimeframes[0];

  base.fvgRetrace = clampNumber(raw.fvgRetrace, 10, 90, base.fvgRetrace);
  base.fvgMinWidthPct = clampNumber(raw.fvgMinWidthPct, 0, 10, base.fvgMinWidthPct);
  base.fvgRequireSweep = Boolean(raw.fvgRequireSweep ?? raw.fvgRequireSweepDisplacement);
  base.fvgSweepLookbackCandles = Math.round(clampNumber(raw.fvgSweepLookbackCandles, 3, 100, base.fvgSweepLookbackCandles));
  base.fvgRequireFirstTouch = Boolean(raw.fvgRequireFirstTouch);
  base.maxZoneAgeCandles = Math.round(clampNumber(raw.maxZoneAgeCandles, 1, 500, base.maxZoneAgeCandles));
  base.fvgRequireConfirmation = Boolean(raw.fvgRequireConfirmation ?? raw.fvgRequireLowerTfConfirmation);
  const legacyConfirmationMap = raw.fvgLowerTfConfirmations && typeof raw.fvgLowerTfConfirmations === 'object'
    ? Object.values(raw.fvgLowerTfConfirmations as Record<string, unknown>)
    : [];
  base.fvgConfirmationTimeframes = normalizeTimeframeArray(
    raw.fvgConfirmationTimeframes,
    normalizeTimeframeArray(legacyConfirmationMap.filter((value) => value !== 'off'), base.fvgConfirmationTimeframes),
  );
  base.maxLeverage = Math.round(clampNumber(raw.maxLeverage, 1, 50, base.maxLeverage));
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
  base.biasPolicy = normalizeBiasPolicy(raw.biasPolicy, DEFAULT_BIAS_POLICY);

  // ── Stage-1 SignalQualityContext fields (issue #61) ────────────────
  base.regimeTf = raw.regimeTf === '4h' ? '4h' : raw.regimeTf === '1h' ? '1h' : (base.regimeTf ?? '1h');
  base.regimeFilterEnabled = typeof raw.regimeFilterEnabled === 'boolean' ? raw.regimeFilterEnabled : (base.regimeFilterEnabled ?? true);
  base.adxMin = clampNumber(raw.adxMin, 0, 100, base.adxMin ?? 0);
  base.adxEnabled = typeof raw.adxEnabled === 'boolean' ? raw.adxEnabled : base.adxMin > 0;
  base.minImpulseAtr = clampNumber(raw.minImpulseAtr, 0, 10, base.minImpulseAtr ?? 0);
  base.minImpulseAtrEnabled = typeof raw.minImpulseAtrEnabled === 'boolean' ? raw.minImpulseAtrEnabled : base.minImpulseAtr > 0;
  base.timeStopBars = Math.round(clampNumber(raw.timeStopBars, 0, 1000, base.timeStopBars ?? 0));
  base.timeStopEnabled = typeof raw.timeStopEnabled === 'boolean' ? raw.timeStopEnabled : base.timeStopBars > 0;
  base.riskPerTradePct = clampNumber(raw.riskPerTradePct, 0, 100, base.riskPerTradePct ?? 0);
  base.riskPerTradeEnabled = typeof raw.riskPerTradeEnabled === 'boolean' ? raw.riskPerTradeEnabled : base.riskPerTradePct > 0;
  base.eventLockoutMinutes = Math.round(clampNumber(raw.eventLockoutMinutes, 0, 1440, base.eventLockoutMinutes ?? 0));
  base.eventLockoutEnabled = typeof raw.eventLockoutEnabled === 'boolean' ? raw.eventLockoutEnabled : base.eventLockoutMinutes > 0;
  base.portfolioGrossCap = clampNumber(raw.portfolioGrossCap, 0, 10000, base.portfolioGrossCap ?? 200);
  base.portfolioGrossCapEnabled = typeof raw.portfolioGrossCapEnabled === 'boolean' ? raw.portfolioGrossCapEnabled : base.portfolioGrossCap > 0;

  return base;
}

function normalizeSymbol(symbol: string): string {
  const raw = String(symbol ?? '').trim();
  if (!raw) return '';

  if (raw.includes(':')) {
    const [namespaceRaw, symbolRaw] = raw.split(':', 2);
    const namespace = String(namespaceRaw ?? '').trim().toLowerCase();
    const symbolPart = String(symbolRaw ?? '').trim().toUpperCase();
    if (!namespace || !symbolPart) return '';
    return `${namespace}:${symbolPart}`;
  }

  return raw.toUpperCase();
}

/**
 * Returns the concrete list of symbols to monitor for entry signals (Radar, Engulfing, FVG).
 *
 * This is the single source of truth for "which assets are actively monitored."
 * Monitored symbols come exclusively from Trading Rules enabled coins list.
 *
 * Asset classes (crypto/commodity/forex/etc) are used ONLY for:
 *   - Verdict policy thresholds (different score cutoffs per asset class)
 *   - Diagnostics and display labels
 *   - Bias policy organization
 *
 * Asset classes do NOT determine which symbols are monitored.
 *
 * Note: Returns normalized symbols. Deduplicates if multiple entries resolve to same symbol.
 * Falls back to a default symbol if enabled list is empty (to maintain backwards compatibility).
 */
export function getMonitoredSymbols(rules: TradingRulesSettings, fallbackSymbol = 'BTC'): string[] {
  const enabled = (rules.coins ?? [])
    .filter((coin) => coin.enabled)
    .map((coin) => normalizeSymbol(coin.symbol))
    .filter((s) => s.length > 0);

  const base = enabled.length > 0 ? enabled : [fallbackSymbol];
  return [...new Set(base)];
}

/** Check if a symbol is in the monitored set (enabled in Trading Rules). */
export function isSymbolMonitored(rules: TradingRulesSettings, symbol: string): boolean {
  const normalized = normalizeRuleSymbol(symbol);
  if (!normalized) return false;
  return (rules.coins ?? []).some((coin) => normalizeRuleSymbol(coin.symbol) === normalized && coin.enabled);
}
