import type { ExchangeAdapter } from '../exchange/adapter.js';
import type { ExposureSnapshot, FillEvent, OrderSnapshot, PositionSnapshot } from '../exchange/types.js';
import type { LiveDashboardState, LiveFill, LiveOpenOrderBreakdown, LivePnlSummary, LivePosition } from '../shared/dto.js';

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

export function getOrderClientOrderId(order: OrderSnapshot): string {
  const raw = order.raw as Record<string, unknown> | undefined;
  return String(
    (raw as { cloid?: unknown } | undefined)?.cloid
    ?? (raw as { clientOrderId?: unknown } | undefined)?.clientOrderId
    ?? ''
  ).trim();
}

export function getSystemManagedProtectiveOrderMeta(order: OrderSnapshot): { kind: 'tp' | 'sl'; correlationId: string } | null {
  const clientOrderId = getOrderClientOrderId(order).toLowerCase();
  if (!clientOrderId) return null;

  const tpMatch = clientOrderId.match(/^tptr\d+-auto-(.+)$/);
  if (tpMatch?.[1]) return { kind: 'tp', correlationId: tpMatch[1] };

  const slMatch = clientOrderId.match(/^sl-auto-(.+)$/);
  if (slMatch?.[1]) return { kind: 'sl', correlationId: slMatch[1] };

  return null;
}

function buildOpenOrderBreakdown(openOrders: OrderSnapshot[]): LiveOpenOrderBreakdown {
  let systemManagedTakeProfit = 0;
  let systemManagedStopLoss = 0;

  for (const order of openOrders) {
    const meta = getSystemManagedProtectiveOrderMeta(order);
    if (!meta) continue;
    if (meta.kind === 'tp') systemManagedTakeProfit += 1;
    if (meta.kind === 'sl') systemManagedStopLoss += 1;
  }

  const systemManagedProtective = systemManagedTakeProfit + systemManagedStopLoss;
  return {
    total: openOrders.length,
    systemManagedProtective,
    systemManagedTakeProfit,
    systemManagedStopLoss,
    other: Math.max(0, openOrders.length - systemManagedProtective),
  };
}

function normalizeLiveSymbol(symbol: string): string {
  const value = String(symbol ?? '').trim();
  if (!value) return '';

  const stripCore = (coreRaw: string) => {
    const upper = String(coreRaw ?? '').trim().toUpperCase().replace('-PERP', '');
    // Hyperliquid UI can show synthetic USD suffix (e.g. GOLDUSD) while API uses GOLD.
    if (upper.endsWith('USD') && upper.length > 3) return upper.slice(0, -3);
    return upper;
  };

  if (value.includes(':')) {
    const [nsRaw, coreRaw] = value.split(':', 2);
    const ns = String(nsRaw ?? '').trim().toLowerCase();
    const core = stripCore(coreRaw);
    return ns && core ? `${ns}:${core}` : '';
  }

  return stripCore(value);
}

function coreLiveSymbol(symbol: string): string {
  const normalized = normalizeLiveSymbol(symbol);
  if (!normalized) return '';
  if (!normalized.includes(':')) return normalized;
  const [, coreRaw] = normalized.split(':', 2);
  return String(coreRaw ?? '').trim().toUpperCase();
}

function symbolsMatch(left: string, right: string): boolean {
  const a = normalizeLiveSymbol(left);
  const b = normalizeLiveSymbol(right);
  if (!a || !b) return false;
  if (a === b) return true;
  return coreLiveSymbol(a) === coreLiveSymbol(b);
}

function orderTpslKind(order: OrderSnapshot): 'tp' | 'sl' | undefined {
  const raw = (order.raw ?? {}) as Record<string, unknown>;
  const kind = String(
    (raw as { tpsl?: unknown } | undefined)?.tpsl
    ?? (raw as { trigger?: { tpsl?: unknown } } | undefined)?.trigger?.tpsl
    ?? (raw as { orderType?: { trigger?: { tpsl?: unknown } } } | undefined)?.orderType?.trigger?.tpsl
    ?? ''
  ).trim().toLowerCase();

  if (kind === 'tp') return 'tp';
  if (kind === 'sl') return 'sl';

  // Hyperliquid frontendOpenOrders often exposes plain-text orderType:
  // "Take Profit Market" | "Stop Market" without explicit tpsl field.
  const orderTypeText = String(
    (raw as { orderType?: unknown } | undefined)?.orderType
    ?? ''
  ).trim().toLowerCase();

  if (orderTypeText.includes('take profit') || orderTypeText === 'tp') return 'tp';
  if (orderTypeText.includes('stop') || orderTypeText === 'sl') return 'sl';

  // Manual partial TP/SL ladders can be reduce-only LIMIT orders with cloid prefixes.
  const cloid = String(
    (raw as { cloid?: unknown } | undefined)?.cloid
    ?? (raw as { clientOrderId?: unknown } | undefined)?.clientOrderId
    ?? ''
  ).trim().toLowerCase();

  if (cloid.startsWith('tp')) return 'tp';
  if (cloid.startsWith('sl')) return 'sl';

  return undefined;
}

function pickStopLossAndTakeProfit(position: Pick<ExposureSnapshot, 'symbol' | 'side' | 'entryPrice'>, openOrders: OrderSnapshot[]) {
  const entry = position.entryPrice;
  if (!entry || entry <= 0) {
    return {
      stopLoss: undefined as number | undefined,
      takeProfit: undefined as number | undefined,
      takeProfits: [] as number[],
    };
  }

  const closingSide: 'buy' | 'sell' = position.side === 'long' ? 'sell' : 'buy';
  const candidates = openOrders
    .filter((o) => symbolsMatch(o.symbol, position.symbol) && o.side === closingSide)
    .filter(isReduceOnlyOrder);

  if (!candidates.length) {
    return {
      stopLoss: undefined as number | undefined,
      takeProfit: undefined as number | undefined,
      takeProfits: [] as number[],
    };
  }

  const explicitTp = candidates
    .filter((o) => orderTpslKind(o) === 'tp')
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));
  const explicitSl = candidates
    .filter((o) => orderTpslKind(o) === 'sl')
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  // Mixed mode support: explicit trigger TP/SL + reduce-only LIMIT TP ladders.
  const priceSideTp = (o: OrderSnapshot) => position.side === 'long' ? o.price >= entry : o.price <= entry;
  const priceSideSl = (o: OrderSnapshot) => position.side === 'long' ? o.price <= entry : o.price >= entry;

  const fallbackTp = candidates
    .filter((o) => orderTpslKind(o) === undefined)
    .filter((o) => priceSideTp(o))
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  const fallbackSl = candidates
    .filter((o) => orderTpslKind(o) === undefined)
    .filter((o) => priceSideSl(o))
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  const mergedTp = [...explicitTp, ...fallbackTp]
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry))
    .filter((o, idx, arr) => arr.findIndex((x) => x.id === o.id) === idx)
    .slice(0, 3);

  const slCandidateResolved = (explicitSl[0] ?? fallbackSl[0]);

  if (mergedTp.length > 0 || slCandidateResolved) {
    const takeProfits = mergedTp.map((o) => o.price);
    return {
      stopLoss: slCandidateResolved?.price,
      takeProfit: takeProfits[0],
      takeProfits,
    };
  }

  // Heuristic fallback when no explicit or inferred classification exists.
  const byDistance = candidates
    .slice()
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  const aboveEntry = candidates
    .filter((o) => o.price >= entry)
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  const belowEntry = candidates
    .filter((o) => o.price <= entry)
    .sort((a, b) => Math.abs(a.price - entry) - Math.abs(b.price - entry));

  if (position.side === 'long') {
    const tpOrders = (aboveEntry.length > 0 ? aboveEntry : byDistance).slice(0, 3);
    const tpIds = new Set(tpOrders.map((o) => o.id));
    const slCandidate = belowEntry[0] ?? byDistance.find((o) => !tpIds.has(o.id));
    const takeProfits = tpOrders.map((o) => o.price);

    return {
      stopLoss: slCandidate?.price,
      takeProfit: takeProfits[0],
      takeProfits,
    };
  }

  const tpOrders = (belowEntry.length > 0 ? belowEntry : byDistance).slice(0, 3);
  const tpIds = new Set(tpOrders.map((o) => o.id));
  const slCandidate = aboveEntry[0] ?? byDistance.find((o) => !tpIds.has(o.id));
  const takeProfits = tpOrders.map((o) => o.price);

  return {
    stopLoss: slCandidate?.price,
    takeProfit: takeProfits[0],
    takeProfits,
  };
}

function pickOpenedAt(position: Pick<ExposureSnapshot, 'symbol' | 'side' | 'entryPrice'>, fills: FillEvent[]): string | undefined {
  const openingSide: 'buy' | 'sell' = position.side === 'long' ? 'buy' : 'sell';
  const bySymbolAndSide = fills.filter((f) => symbolsMatch(f.symbol, position.symbol) && f.side === openingSide);
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

function toLivePosition(position: ExposureSnapshot, openOrders: OrderSnapshot[], fills: FillEvent[]): LivePosition {
  const { stopLoss, takeProfit, takeProfits } = pickStopLossAndTakeProfit(position, openOrders);
  const openedAt = pickOpenedAt(position, fills);
  const rawPositionValue = toFiniteNumber(
    (position.raw as { position?: { positionValue?: unknown } } | undefined)?.position?.positionValue
  );
  const fallbackValue = position.entryPrice
    ? position.entryPrice * position.size
    : position.markPrice
      ? position.markPrice * position.size
      : undefined;
  const dealValue = rawPositionValue ?? fallbackValue;

  return {
    id: `${position.productType}:${position.symbol}-${position.side}-${position.entryPrice ?? 0}-${position.size}`,
    symbol: position.symbol,
    side: position.side,
    size: position.size,
    entryPrice: position.entryPrice,
    dealValue,
    stopLoss,
    takeProfit,
    takeProfits,
    openedAt,
    leverage: position.leverage,
    unrealizedPnl: position.unrealizedPnl,
    productType: position.productType,
    accountScope: position.accountScope,
    source: position.source,
  };
}

export function toLiveFill(fill: FillEvent, fallbackSource?: string): LiveFill {
  const raw = fill.raw as { dir?: unknown; sourceExchange?: unknown } | undefined;
  const direction = String(raw?.dir ?? '').trim();
  const sourceExchange = String(raw?.sourceExchange ?? fallbackSource ?? '').trim().toLowerCase();

  return {
    id: fill.id,
    symbol: fill.symbol,
    side: fill.side,
    sourceExchange: sourceExchange || undefined,
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
  mode: LiveModeConfig,
  pendingConfirmations: LivePosition[] = []
): Promise<LiveDashboardState> {
  const base: LiveDashboardState = {
    connected: false,
    mode,
    account: null,
    pnl: emptyPnl(),
    openOrders: 0,
    openOrderBreakdown: {
      total: 0,
      systemManagedProtective: 0,
      systemManagedTakeProfit: 0,
      systemManagedStopLoss: 0,
      other: 0,
    },
    openPositions: [],
    pendingConfirmations
  };

  try {
    const exposuresPromise: Promise<ExposureSnapshot[]> = typeof exchange.getOpenExposures === 'function'
      ? exchange.getOpenExposures()
      : exchange.getOpenPositions().then((rows: PositionSnapshot[]) => rows.map((row): ExposureSnapshot => ({
          symbol: row.symbol,
          side: row.side,
          size: row.size,
          entryPrice: row.entryPrice,
          markPrice: row.markPrice,
          leverage: row.leverage,
          unrealizedPnl: row.unrealizedPnl,
          productType: 'perp',
          accountScope: 'master',
          source: 'getOpenPositions',
          raw: row.raw,
        })));

    const [account, openOrders, openExposures, fills] = await Promise.all([
      exchange.getAccountState(),
      exchange.getOpenOrders(),
      exposuresPromise,
      exchange.getFills()
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
      openOrderBreakdown: buildOpenOrderBreakdown(openOrders),
      openPositions: openExposures.map((p) => toLivePosition(p, openOrders, fills)),
      pendingConfirmations
    };
  } catch (error) {
    return {
      ...base,
      connected: false,
      error: error instanceof Error ? error.message : 'live_dashboard_fetch_failed'
    };
  }
}
