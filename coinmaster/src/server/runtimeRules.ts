import { getDb } from '../core/db.js';
import type { TradingRulesSettings } from '../shared/dto.js';
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
      console.error('[runtime-rules] Failed to refresh from DB, keeping previous/env fallback:', err);
      // Keep whatever was last cached (env fallback on first failure)
    } finally {
      this.refreshing = false;
    }
  }
}
