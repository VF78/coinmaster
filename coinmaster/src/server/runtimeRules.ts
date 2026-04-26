import { getDb } from '../core/db.js';
import logger from '../lib/logger.js';
import type { TradingCoinAllocation, TradingRulesSettings } from '../shared/dto.js';
import { normalizeTradingRules } from '../shared/tradingRules.js';

// ─── Env-based hard defaults (fallback when DB is unavailable) ────────
const ENV_MAX_LEVERAGE = Number(process.env.LIVE_MAX_LEVERAGE || 10);
const ENV_MANUAL_CONFIRMATION = String(process.env.LIVE_MANUAL_CONFIRMATION ?? 'true').toLowerCase() !== 'false';
const ENV_DAILY_DD_LIMIT_PCT = Number(process.env.LIVE_DAILY_DD_LIMIT_PCT || 20);
const ENV_PORTFOLIO_LEVERAGE_CAP = Number(process.env.LIVE_PORTFOLIO_LEVERAGE_CAP || 10);
const EXECUTION_AVAILABLE_MARGIN_BUFFER_PCT = Math.min(100, Math.max(1, Number(process.env.EXECUTION_AVAILABLE_MARGIN_BUFFER_PCT || 90)));

export interface EffectiveRules {
  manualConfirmation: boolean;
  maxLeverage: number;
  portfolioLeverageCap: number;
  dailyDDLimitPct: number;
  source: 'runtime' | 'env_fallback';
  lastRefreshedAt: string | null;
  raw: TradingRulesSettings | null;
}

function envFallback(): EffectiveRules {
  return {
    manualConfirmation: ENV_MANUAL_CONFIRMATION,
    maxLeverage: ENV_MAX_LEVERAGE,
    portfolioLeverageCap: ENV_PORTFOLIO_LEVERAGE_CAP,
    dailyDDLimitPct: ENV_DAILY_DD_LIMIT_PCT,
    source: 'env_fallback',
    lastRefreshedAt: null,
    raw: null,
  };
}

// ─── Symbol Allowlist + Allocation Helpers ─────────────────────────────

/** Check whether a symbol is enabled in current trading rules. */
export function isSymbolEnabled(rules: EffectiveRules, symbol: string): boolean {
  if (!rules.raw) return false; // env fallback has no coin config → deny all
  const coin = rules.raw.coins.find((c) => c.symbol.toUpperCase() === symbol.toUpperCase());
  return coin?.enabled === true;
}

/** Get the coin allocation entry for a symbol (or undefined). */
export function getCoinAllocation(rules: EffectiveRules, symbol: string): TradingCoinAllocation | undefined {
  return rules.raw?.coins.find((c) => c.symbol.toUpperCase() === symbol.toUpperCase());
}

export interface SymbolNotionalCap {
  symbol: string;
  allocationPct: number;
  effectiveLeverage: number;
  allocationMarginUsd: number;
  allocationNotionalUsd: number;
  capNotionalUsd: number;
  riskPerTradePct?: number;
  riskCapNotionalUsd?: number;
}

/**
 * Maximum notional (in USD) allowed for one symbol.
 *
 * `coins[].pct` is the margin allocation. Notional cap therefore includes the
 * configured leverage, then optionally gets clipped by risk-per-trade sizing.
 * This is the canonical formula shared by auto-sizing and manual order guards.
 */
export function computeSymbolNotionalCap(equityUsd: number, rules: EffectiveRules, symbol: string): SymbolNotionalCap | null {
  const coin = getCoinAllocation(rules, symbol);
  if (!coin?.enabled || !Number.isFinite(equityUsd) || equityUsd <= 0) return null;

  const allocationPct = Number(coin.pct);
  if (!Number.isFinite(allocationPct) || allocationPct <= 0) return null;

  const effectiveLeverage = Number(rules.maxLeverage);
  if (!Number.isFinite(effectiveLeverage) || effectiveLeverage <= 0) return null;

  const allocationMarginUsd = equityUsd * (allocationPct / 100);
  const allocationNotionalUsd = allocationMarginUsd * effectiveLeverage;

  const riskPerTradePct = Number(rules.raw?.riskPerTradePct ?? 0);
  const slPct = Number(rules.raw?.slPct ?? 0);
  const riskCapNotionalUsd = riskPerTradePct > 0 && slPct > 0
    ? equityUsd * (riskPerTradePct / 100) / (slPct / 100)
    : Number.POSITIVE_INFINITY;

  return {
    symbol: coin.symbol,
    allocationPct,
    effectiveLeverage,
    allocationMarginUsd,
    allocationNotionalUsd,
    capNotionalUsd: Math.min(allocationNotionalUsd, riskCapNotionalUsd),
    riskPerTradePct: riskPerTradePct > 0 ? riskPerTradePct : undefined,
    riskCapNotionalUsd: Number.isFinite(riskCapNotionalUsd) ? riskCapNotionalUsd : undefined,
  };
}

/**
 * Maximum notional (in USD) allowed for a symbol.
 * Returns 0 if the symbol is not enabled or rules/equity are unavailable.
 */
export function maxNotionalForSymbol(equityUsd: number, rules: EffectiveRules, symbol: string): number {
  return computeSymbolNotionalCap(equityUsd, rules, symbol)?.capNotionalUsd ?? 0;
}

// ─── Allocation-Based Order Sizing ─────────────────────────────────────

export interface AllocationSizingResult {
  ok: true;
  size: number;
  marginUsd: number;
  notionalUsd: number;
  effectiveLeverage: number;
  allocationPct: number;
  allocationMarginUsd: number;
  allocationNotionalUsd: number;
  riskPerTradePct?: number;
  riskCapNotionalUsd?: number;
}

export interface AllocationSizingError {
  ok: false;
  reason: string;
}

export type AllocationSizingOutcome = AllocationSizingResult | AllocationSizingError;

/**
 * Compute position size from Coin Distribution allocation rules.
 *
 * Default path preserves the existing allocation model:
 * marginUsd   = equityUsd * allocationPct
 * notionalUsd = marginUsd * effectiveLeverage
 *
 * If riskPerTradePct > 0 and slPct > 0, cap notional so the configured SL
 * distance risks at most riskPerTradePct of equity. This keeps risk sizing a
 * thin deterministic layer instead of a second portfolio engine.
 */
export function computeAllocationSize(params: {
  symbol: string;
  price: number;
  equityUsd: number;
  availableUsd: number;
  rules: EffectiveRules;
  sizeDecimals?: number;
}): AllocationSizingOutcome {
  const { symbol, price, equityUsd, availableUsd, rules, sizeDecimals = 6 } = params;

  if (!Number.isFinite(price) || price <= 0) {
    return { ok: false, reason: 'invalid_price' };
  }
  if (!Number.isFinite(equityUsd) || equityUsd <= 0) {
    return { ok: false, reason: 'zero_equity' };
  }
  if (!Number.isFinite(availableUsd) || availableUsd <= 0) {
    return { ok: false, reason: 'zero_available' };
  }

  const coin = getCoinAllocation(rules, symbol);
  if (!coin?.enabled) {
    return { ok: false, reason: 'symbol_not_enabled' };
  }

  const allocationPct = coin.pct;
  if (!Number.isFinite(allocationPct) || allocationPct <= 0) {
    return { ok: false, reason: 'zero_allocation_pct' };
  }

  const effectiveLeverage = rules.maxLeverage;
  if (!Number.isFinite(effectiveLeverage) || effectiveLeverage <= 0) {
    return { ok: false, reason: 'zero_leverage' };
  }

  const symbolCap = computeSymbolNotionalCap(equityUsd, rules, symbol);
  if (!symbolCap || symbolCap.allocationMarginUsd <= 0) {
    return { ok: false, reason: 'zero_margin' };
  }

  const usableAvailableUsd = availableUsd * (EXECUTION_AVAILABLE_MARGIN_BUFFER_PCT / 100);
  const availableNotionalUsd = usableAvailableUsd * effectiveLeverage;
  const notionalUsd = Math.min(symbolCap.capNotionalUsd, availableNotionalUsd);
  const marginUsd = notionalUsd / effectiveLeverage;

  if (!Number.isFinite(notionalUsd) || notionalUsd <= 0 || !Number.isFinite(marginUsd) || marginUsd <= 0) {
    return { ok: false, reason: 'insufficient_available_margin' };
  }

  const rawSize = notionalUsd / price;

  // Round to sizeDecimals, guard against zero / NaN
  const factor = 10 ** sizeDecimals;
  const size = Math.floor(rawSize * factor) / factor;

  if (!Number.isFinite(size) || size <= 0) {
    return { ok: false, reason: 'computed_size_zero' };
  }

  return {
    ok: true,
    size,
    marginUsd: Math.round(marginUsd * 100) / 100,
    notionalUsd: Math.round(notionalUsd * 100) / 100,
    effectiveLeverage,
    allocationPct,
    allocationMarginUsd: Math.round(symbolCap.allocationMarginUsd * 100) / 100,
    allocationNotionalUsd: Math.round(symbolCap.allocationNotionalUsd * 100) / 100,
    riskPerTradePct: symbolCap.riskPerTradePct,
    riskCapNotionalUsd: symbolCap.riskCapNotionalUsd !== undefined ? Math.round(symbolCap.riskCapNotionalUsd * 100) / 100 : undefined,
  };
}

/** Maximum aggregate gross notional allowed by Trading Rules. */
export function maxPortfolioGrossNotional(equityUsd: number, rules: EffectiveRules): number {
  const capPct = Number(rules.raw?.portfolioGrossCap ?? 0);
  if (!Number.isFinite(equityUsd) || equityUsd <= 0 || !Number.isFinite(capPct) || capPct <= 0) {
    return Number.POSITIVE_INFINITY;
  }
  return equityUsd * (capPct / 100);
}

export function wouldExceedPortfolioGrossCap(params: {
  equityUsd: number;
  rules: EffectiveRules;
  currentGrossNotional: number;
  newOrderNotional: number;
}): boolean {
  const cap = maxPortfolioGrossNotional(params.equityUsd, params.rules);
  if (!Number.isFinite(cap)) return false;
  const current = Number.isFinite(params.currentGrossNotional) ? Math.max(0, params.currentGrossNotional) : 0;
  const next = Number.isFinite(params.newOrderNotional) ? Math.max(0, params.newOrderNotional) : 0;
  return current + next > cap;
}

/**
 * RuntimeRulesCache — reads TradingRulesSettings from the DB every `intervalMs`
 * and exposes a synchronous `getEffectiveRules()` for the hot request path.
 * Falls back to env-based defaults on any error.
 */
export class RuntimeRulesCache {
  private cached: EffectiveRules = envFallback();
  private timer: NodeJS.Timeout | null = null;
  private refreshing = false;

  constructor(private readonly intervalMs: number = 5_000) {}

  /** Start periodic refresh. Call once at server boot. */
  start(): void {
    if (this.timer) return;
    // Immediate first load
    this.refresh().catch((err) => logger.warn({ component: 'runtime-rules', err }, 'rules refresh failed'));
    this.timer = setInterval(() => {
      this.refresh().catch((err) => logger.warn({ component: 'runtime-rules', err }, 'rules refresh failed'));
    }, this.intervalMs);
    this.timer.unref();
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  /** Synchronous — safe to call in any request handler. */
  getEffectiveRules(): EffectiveRules {
    return this.cached;
  }

  /** Force immediate refresh from DB (used after settings updates). */
  async refreshNow(): Promise<void> {
    await this.refresh();
  }

  private async refresh(): Promise<void> {
    if (this.refreshing) return;
    this.refreshing = true;
    try {
      const db = await getDb();
      const rules = normalizeTradingRules(db.data.settings.tradingRules);

      this.cached = {
        // autoConfirm=true  →  manualConfirmation=false
        manualConfirmation: !rules.autoConfirm,
        maxLeverage: rules.maxLeverage,
        portfolioLeverageCap: rules.maxLeverage,
        dailyDDLimitPct: rules.dailyDrawdown,
        source: 'runtime',
        lastRefreshedAt: new Date().toISOString(),
        raw: rules,
      };
    } catch (err) {
      logger.error({ component: 'runtime-rules', err }, 'failed to refresh from DB, keeping previous/env fallback');
      // Keep whatever was last cached (env fallback on first failure)
    } finally {
      this.refreshing = false;
    }
  }
}
