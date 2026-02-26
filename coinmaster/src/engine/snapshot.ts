import type { AccountSnapshot, OrderSnapshot, PositionSnapshot } from '../exchange/types.js';
import type { TradingRulesSettings } from '../shared/dto.js';
import type { RuleEngineSnapshot, TriggerSource } from './types.js';

export interface SnapshotBuildDeps {
  account(): Promise<AccountSnapshot>;
  positions(): Promise<PositionSnapshot[]>;
  openOrders(): Promise<OrderSnapshot[]>;
  latestPrices(): Promise<Record<string, number>>;
  marketDataAge(): Promise<number>;
  rules(): Promise<TradingRulesSettings>;
}

export interface EngineSnapshot extends RuleEngineSnapshot {
  equity?: number;
  portfolioLeverage?: number;
  positions?: PositionSnapshot[];
  openOrders?: OrderSnapshot[];
  prices?: Record<string, number>;
  marketDataAge?: number;
  tradingRules?: TradingRulesSettings;
}

/**
 * Pure helper: total notional / equity.
 * Returns 0 for empty positions or zero/negative equity.
 */
export function computePortfolioLeverage(positions: PositionSnapshot[], equity: number): number {
  if (positions.length === 0 || equity <= 0) return 0;
  const totalNotional = positions.reduce((sum, p) => {
    const price = p.markPrice ?? p.entryPrice ?? 0;
    return sum + p.size * price;
  }, 0);
  return totalNotional / equity;
}

/**
 * Build a RuleEngineSnapshot by calling all deps in parallel (best-effort).
 * A dep failure leaves that field undefined — the snapshot is still returned.
 * No side effects beyond calling the provided dep functions.
 */
export async function buildEngineSnapshot(
  source: TriggerSource,
  deps: SnapshotBuildDeps,
  request?: RuleEngineSnapshot['request'],
): Promise<EngineSnapshot> {
  const timestamp = Date.now();

  const [accountResult, positionsResult, openOrdersResult, pricesResult, ageResult, rulesResult] =
    await Promise.allSettled([
      deps.account(),
      deps.positions(),
      deps.openOrders(),
      deps.latestPrices(),
      deps.marketDataAge(),
      deps.rules(),
    ]);

  const equity =
    accountResult.status === 'fulfilled' ? accountResult.value.equityUsd : undefined;
  const positions =
    positionsResult.status === 'fulfilled' ? positionsResult.value : undefined;
  const openOrders =
    openOrdersResult.status === 'fulfilled' ? openOrdersResult.value : undefined;
  const prices =
    pricesResult.status === 'fulfilled' ? pricesResult.value : undefined;
  const marketDataAge =
    ageResult.status === 'fulfilled' ? ageResult.value : undefined;
  const tradingRules =
    rulesResult.status === 'fulfilled' ? rulesResult.value : undefined;

  const portfolioLeverage =
    positions !== undefined && equity !== undefined
      ? computePortfolioLeverage(positions, equity)
      : undefined;

  const snapshot: EngineSnapshot = {
    timestamp,
    source,
    ...(request !== undefined && { request }),
    ...(equity !== undefined && { equity }),
    ...(portfolioLeverage !== undefined && { portfolioLeverage }),
    ...(positions !== undefined && { positions }),
    ...(openOrders !== undefined && { openOrders }),
    ...(prices !== undefined && { prices }),
    ...(marketDataAge !== undefined && { marketDataAge }),
    ...(tradingRules !== undefined && { tradingRules }),
  };

  return snapshot;
}
