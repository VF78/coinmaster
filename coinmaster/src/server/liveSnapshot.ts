import type { ExchangeAdapter } from '../exchange/adapter.js';
import type { FillEvent, OrderSnapshot, PositionSnapshot } from '../exchange/types.js';
import type { LiveDashboardState, LiveFill, LivePnlSummary, LivePosition } from '../shared/dto.js';

export interface LiveModeConfig {
  manualConfirmation: boolean;
  maxLeverage: number;
}

function toFiniteNumber(value: unknown): number | undefined {
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function toClosedPnl(fill: FillEvent): number {
  const value = toFiniteNumber((fill.raw as { closedPnl?: unknown } | undefined)?.closedPnl);
  return value ?? 0;
}

function toFee(fill: FillEvent): number {
  const value = toFiniteNumber((fill.raw as { fee?: unknown } | undefined)?.fee);
  return value !== undefined ? Math.abs(value) : 0;
}

function emptyPnl(): LivePnlSummary {
  return {
    dailyNetUsd: 0,
    weeklyNetUsd: 0,
    monthlyNetUsd: 0,
    dailyRealizedUsd: 0,
    weeklyRealizedUsd: 0,
    monthlyRealizedUsd: 0
  };
}

function isReduceOnlyOrder(order: OrderSnapshot): boolean {
  const raw = (order.raw ?? {}) as Record<string, unknown>;
  const reduceOnly = raw.reduceOnly;
  if (reduceOnly === true || reduceOnly === 'true' || reduceOnly === 1 || reduceOnly === '1') return true;
  if (reduceOnly === false || reduceOnly === 'false' || reduceOnly === 0 || reduceOnly === '0') return false;
  return true; // fallback when adapter/raw does not expose reduceOnly flag
}

function pickStopLossAndTakeProfit(position: PositionSnapshot, openOrders: OrderSnapshot[]) {
  const entry = position.entryPrice;
  if (!entry || entry <= 0) {
    return { stopLoss: undefined as number | undefined, takeProfit: undefined as number | undefined };
  }

  const closingSide: 'buy' | 'sell' = position.side === 'long' ? 'sell' : 'buy';
  const candidates = openOrders
    .filter((o) => o.symbol === position.symbol && o.side === closingSide)
    .filter(isReduceOnlyOrder);

  if (!candidates.length) {
    return { stopLoss: undefined as number | undefined, takeProfit: undefined as number | undefined };
  }

  const aboveEntry = candidates
    .filter((o) => o.price > entry)
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  const belowEntry = candidates
    .filter((o) => o.price < entry)
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  if (position.side === 'long') {
    return {
      stopLoss: belowEntry[0]?.price,
      takeProfit: aboveEntry[0]?.price
    };
  }

  return {
    stopLoss: aboveEntry[0]?.price,
    takeProfit: belowEntry[0]?.price
  };
}

function pickOpenedAt(position: PositionSnapshot, fills: FillEvent[]): string | undefined {
  const openingSide: 'buy' | 'sell' = position.side === 'long' ? 'buy' : 'sell';
  const bySymbolAndSide = fills.filter((f) => f.symbol === position.symbol && f.side === openingSide);
  if (!bySymbolAndSide.length) return undefined;

  const entry = position.entryPrice;
  const withScore = bySymbolAndSide
    .map((f) => ({
      fill: f,
      timestampMs: Date.parse(f.timestamp),
      relDiff: entry && entry > 0 ? Math.abs(f.price - entry) / entry : 0
    }))
    .filter((x) => Number.isFinite(x.timestampMs));

  if (!withScore.length) return undefined;

  const nearEntry = entry && entry > 0 ? withScore.filter((x) => x.relDiff <= 0.03) : withScore;
  const pool = nearEntry.length ? nearEntry : withScore;

  pool.sort((a, b) => b.timestampMs - a.timestampMs);
  return pool[0]?.fill.timestamp;
}

function toLivePosition(position: PositionSnapshot, openOrders: OrderSnapshot[], fills: FillEvent[]): LivePosition {
  const { stopLoss, takeProfit } = pickStopLossAndTakeProfit(position, openOrders);
  const openedAt = pickOpenedAt(position, fills);
  const rawPositionValue = toFiniteNumber(
    (position.raw as { position?: { positionValue?: unknown } } | undefined)?.position?.positionValue
  );
  const dealValue = rawPositionValue ?? (position.entryPrice ? position.entryPrice * position.size : undefined);

  return {
    id: `${position.symbol}-${position.side}-${position.entryPrice ?? 0}-${position.size}`,
    symbol: position.symbol,
    side: position.side,
    size: position.size,
    entryPrice: position.entryPrice,
    dealValue,
    stopLoss,
    takeProfit,
    openedAt,
    leverage: position.leverage,
    unrealizedPnl: position.unrealizedPnl
  };
}

export function toLiveFill(fill: FillEvent): LiveFill {
  const direction = String((fill.raw as { dir?: unknown } | undefined)?.dir ?? '').trim();

  return {
    id: fill.id,
    symbol: fill.symbol,
    side: fill.side,
    direction: direction || undefined,
    price: fill.price,
    size: fill.size,
    feeUsd: toFee(fill),
    closedPnlUsd: toClosedPnl(fill),
    timestamp: fill.timestamp
  };
}

export function computeLivePnl(fills: FillEvent[]): LivePnlSummary {
  if (!fills.length) return emptyPnl();

  const now = Date.now();
  const dayCutoff = now - 1 * 24 * 60 * 60 * 1000;
  const weekCutoff = now - 7 * 24 * 60 * 60 * 1000;
  const monthCutoff = now - 30 * 24 * 60 * 60 * 1000;

  let dailyRealized = 0;
  let dailyFees = 0;
  let weeklyRealized = 0;
  let weeklyFees = 0;
  let monthlyRealized = 0;
  let monthlyFees = 0;

  for (const fill of fills) {
    const ts = Date.parse(fill.timestamp);
    if (!Number.isFinite(ts)) continue;

    const closedPnl = toClosedPnl(fill);
    const fee = toFee(fill);

    if (ts >= monthCutoff) {
      monthlyRealized += closedPnl;
      monthlyFees += fee;
    }

    if (ts >= weekCutoff) {
      weeklyRealized += closedPnl;
      weeklyFees += fee;
    }

    if (ts >= dayCutoff) {
      dailyRealized += closedPnl;
      dailyFees += fee;
    }
  }

  const dailyNetUsd = Number((dailyRealized - dailyFees).toFixed(2));
  const weeklyNetUsd = Number((weeklyRealized - weeklyFees).toFixed(2));
  const monthlyNetUsd = Number((monthlyRealized - monthlyFees).toFixed(2));

  return {
    dailyNetUsd,
    weeklyNetUsd,
    monthlyNetUsd,
    dailyRealizedUsd: Number(dailyRealized.toFixed(2)),
    weeklyRealizedUsd: Number(weeklyRealized.toFixed(2)),
    monthlyRealizedUsd: Number(monthlyRealized.toFixed(2))
  };
}

export async function buildLiveDashboardState(
  exchange: ExchangeAdapter,
  symbol: string,
  mode: LiveModeConfig
): Promise<LiveDashboardState> {
  const base: LiveDashboardState = {
    connected: false,
    mode,
    account: null,
    pnl: emptyPnl(),
    openOrders: 0,
    openPositions: [],
    pendingConfirmations: []
  };

  try {
    const [account, openOrders, openPositions, fills] = await Promise.all([
      exchange.getAccountState(),
      exchange.getOpenOrders(symbol),
      exchange.getOpenPositions(symbol),
      exchange.getFills(symbol)
    ]);

    return {
      ...base,
      connected: true,
      account: account
        ? {
            equityUsd: account.equityUsd,
            availableUsd: account.availableUsd,
            usedMarginUsd: account.usedMarginUsd
          }
        : null,
      pnl: computeLivePnl(fills),
      openOrders: openOrders.length,
      openPositions: openPositions.map((p) => toLivePosition(p, openOrders, fills)),
      pendingConfirmations: []
    };
  } catch (error) {
    return {
      ...base,
      connected: false,
      error: error instanceof Error ? error.message : 'live_dashboard_fetch_failed'
    };
  }
}
