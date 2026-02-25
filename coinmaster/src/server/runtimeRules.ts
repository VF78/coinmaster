import { getDb } from '../core/db.js';
import logger from '../lib/logger.js';
import type { TradingCoinAllocation, TradingRulesSettings } from '../shared/dto.js';
import { normalizeTradingRules } from '../shared/tradingRules.js';

// ─── Env-based hard defaults (fallback when DB is unavailable) ────────
const ENV_MAX_LEVERAGE = Number(process.env.LIVE_MAX_LEVERAGE || 10);
const ENV_MANUAL_CONFIRMATION = String(process.env.LIVE_MANUAL_CONFIRMATION ?? 'true').toLowerCase() !== 'false';
const ENV_DAILY_DD_LIMIT_PCT = Number(process.env.LIVE_DAILY_DD_LIMIT_PCT || 20);
const ENV_PORTFOLIO_LEVERAGE_CAP = Number(process.env.LIVE_PORTFOLIO_LEVERAGE_CAP || 10);

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

/**
 * Maximum notional (in USD) allowed for a symbol based on equity and allocation %.
 * Returns 0 if the symbol is not enabled or rules are unavailable.
 */
export function maxNotionalForSymbol(equityUsd: number, rules: EffectiveRules, symbol: string): number {
  const coin = getCoinAllocation(rules, symbol);
  if (!coin?.enabled || !Number.isFinite(equityUsd) || equityUsd <= 0) return 0;
  return equityUsd * (coin.pct / 100);
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
    this.refresh().catch(() => undefined);
    this.timer = setInterval(() => {
      this.refresh().catch(() => undefined);
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
