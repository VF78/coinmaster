import crypto from 'node:crypto';
import { Hyperliquid } from 'hyperliquid';
import logger from '../lib/logger.js';
import { ExchangeAdapter } from './adapter.js';
import {
  AccountSnapshot,
  Candle,
  CandleQuery,
  CommandResult,
  ExchangeCapabilities,
  ExposureSnapshot,
  FillEvent,
  InstrumentMeta,
  MidStreamHandle,
  MidStreamOptions,
  OrderAck,
  OrderIntent,
  OrderSnapshot,
  PositionSnapshot,
  TriggerOrderIntent
} from './types.js';

interface HyperliquidAdapterOptions {
  infoUrl?: string;
  wsUrl?: string;
  fetchImpl?: typeof fetch;
  testnet?: boolean;
  accountAddress?: string;
  apiWalletAddress?: string;
  apiPrivateKey?: string;
}

const DEFAULT_INFO_URL = 'https://api.hyperliquid.xyz/info';
const DEFAULT_WS_URL = 'wss://api.hyperliquid.xyz/ws';
const UNIVERSE_CACHE_TTL_MS = Math.max(30_000, Number(process.env.HYPERLIQUID_UNIVERSE_CACHE_MS || 5 * 60_000));
const DEX_DISCOVERY_CACHE_TTL_MS = Math.max(60_000, Number(process.env.HYPERLIQUID_DEX_DISCOVERY_CACHE_MS || 10 * 60_000));
const DEFAULT_TRIGGER_MARKET_SLIPPAGE_PCT = 0.03;
const DEX_TRIGGER_MARKET_SLIPPAGE_PCT = 0.08;
const EXTRA_DEXES_ENV = String(process.env.HYPERLIQUID_EXTRA_DEXES || '')
  .split(',')
  .map((x) => x.trim().toLowerCase())
  .filter(Boolean);

export class HyperliquidAdapter implements ExchangeAdapter {
  readonly name = 'hyperliquid';
  readonly capabilities: ExchangeCapabilities;

  private readonly infoUrl: string;
  private readonly wsUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly testnet: boolean;

  private readonly accountAddress?: string;
  private readonly privateKey?: string;
  private readonly apiWalletAddress?: string;

  private tradingClient: Hyperliquid | null = null;
  private tradingClientInit: Promise<Hyperliquid> | null = null;
  private tradingClientInitFailures = 0;

  /** Cached effective user address (master account resolved from agent wallet) */
  private effectiveUser: string | null = null;
  private effectiveUserInit: Promise<string> | null = null;
  private effectiveUserInitFailures = 0;

  private universeCacheByDex = new Map<string, {
    fetchedAtMs: number;
    bySymbol: Map<string, any>;
    indexBySymbol: Map<string, number>;
    symbols: string[];
  }>();

  private knownDexesCache: {
    fetchedAtMs: number;
    dexes: string[];
  } | null = null;

  constructor(options: HyperliquidAdapterOptions = {}) {
    this.infoUrl = options.infoUrl ?? DEFAULT_INFO_URL;
    this.wsUrl = options.wsUrl ?? DEFAULT_WS_URL;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.testnet = options.testnet ?? false;

    this.accountAddress = (options.accountAddress ?? process.env.HYPERLIQUID_ACCOUNT_ADDRESS ?? '').trim() || undefined;
    this.privateKey = (options.apiPrivateKey ?? process.env.HYPERLIQUID_API_PRIVATE_KEY ?? '').trim() || undefined;
    this.apiWalletAddress = (options.apiWalletAddress ?? process.env.HYPERLIQUID_API_WALLET_ADDRESS ?? '').trim() || undefined;

    const seedAddress = this.accountAddress || this.apiWalletAddress;
    const hasAccount = Boolean(seedAddress);
    const hasTrading = Boolean(seedAddress && this.privateKey);

    this.capabilities = {
      realtimeMids: true,
      historicalCandles: true,
      privateAccount: hasAccount,
      privateTrading: hasTrading,
      reduceOnly: true,
      cancelReplace: false
    };
  }

  async getMids(): Promise<Record<string, number>> {
    const payload = await this.requestInfo<Record<string, string>>({ type: 'allMids' });
    const out: Record<string, number> = {};

    for (const [symbol, raw] of Object.entries(payload ?? {})) {
      const n = Number(raw);
      if (Number.isFinite(n)) {
        out[symbol] = n;
      }
    }

    return out;
  }

  async getCandles(query: CandleQuery): Promise<Candle[]> {
    const candidates = this.symbolCandidates(query.symbol);
    let lastError: unknown;

    for (let i = 0; i < candidates.length; i++) {
      const candidate = candidates[i];

      try {
        const raw = await this.requestInfo<Array<Record<string, string | number>>>(
          {
            type: 'candleSnapshot',
            req: {
              coin: candidate,
              interval: query.timeframe,
              startTime: query.startTimeMs,
              endTime: query.endTimeMs,
            }
          }
        );

        const rows = (raw ?? [])
          .map((x) => {
            const t = Number(x.t);
            const o = Number(x.o);
            const h = Number(x.h);
            const l = Number(x.l);
            const c = Number(x.c);
            const v = Number(x.v ?? 0);

            if (![t, o, h, l, c, v].every((n) => Number.isFinite(n))) {
              return null;
            }

            return {
              timestamp: new Date(t).toISOString(),
              open: o,
              high: h,
              low: l,
              close: c,
              volume: v
            } as Candle;
          })
          .filter((x): x is Candle => Boolean(x))
          .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));

        if (rows.length > 0 || i === candidates.length - 1) {
          return rows;
        }
      } catch (error) {
        lastError = error;
        if (i === candidates.length - 1) {
          throw error;
        }
      }
    }

    if (lastError) throw lastError;
    return [];
  }

  async getInstrumentMeta(symbol: string): Promise<InstrumentMeta | null> {
    const normalized = this.normalizeSymbol(symbol);
    const core = this.coreSymbol(normalized);
    const dex = this.getDexFromSymbol(normalized);

    const universe = await this.getUniverse(dex).catch(() => null);
    let item = universe?.bySymbol.get(normalized) ?? universe?.bySymbol.get(core);

    if (!item) {
      const fallback = await this.getUniverse(null).catch(() => null);
      item = fallback?.bySymbol.get(core);
    }

    if (!item) return null;

    return {
      symbol: normalized,
      sizeDecimals: Number.isFinite(Number(item.szDecimals)) ? Number(item.szDecimals) : undefined,
      quoteDecimals: Number.isFinite(Number(item.pxDecimals)) ? Number(item.pxDecimals) : undefined,
      raw: item
    };
  }

  async getTradableSymbols(): Promise<string[]> {
    const user = await this.resolveEffectiveUser();
    const dexes = ['', ...(await this.getKnownDexes(user))];

    const universes = await Promise.all(dexes.map((dex) => this.getUniverse(dex)));
    const merged = new Set<string>();
    for (const universe of universes) {
      for (const symbol of universe.symbols) merged.add(symbol);
    }

    return [...merged].sort((a, b) => a.localeCompare(b));
  }

  async getAccountState(): Promise<AccountSnapshot | null> {
    const user = await this.resolveEffectiveUser();

    // Fetch perps state + spot state in parallel
    const [perpState, spotState] = await Promise.all([
      this.requestInfo<any>({ type: 'clearinghouseState', user }),
      this.requestInfo<any>({ type: 'spotClearinghouseState', user }).catch(() => null),
    ]);

    // Perps margin (collateral sent to perpetuals clearing account)
    const perpAccountValue = this.toNumber(
      perpState?.marginSummary?.accountValue ?? perpState?.crossMarginSummary?.accountValue
    );
    const marginUsed = this.toNumber(
      perpState?.marginSummary?.totalMarginUsed ?? perpState?.crossMarginSummary?.totalMarginUsed
    );
    const withdrawable = this.toNumber(perpState?.withdrawable);

    // Spot USDC balance = true total equity (includes perps collateral)
    // spotClearinghouseState.balances[USDC].total is the authoritative "Total Equity"
    const usdcBalance = (spotState?.balances as any[] | undefined)
      ?.find((b) => b?.coin === 'USDC');
    const spotTotalUsdc = this.toNumber(usdcBalance?.total);

    // Available = spot available after maintenance margin
    // tokenToAvailableAfterMaintenance: [[tokenId, amount], ...]
    const availAfterMaint = (spotState?.tokenToAvailableAfterMaintenance as any[] | undefined)
      ?.find((pair) => Array.isArray(pair) && pair[0] === 0);
    const spotAvailableUsdc = this.toNumber(availAfterMaint?.[1]);

    // True equity = spot total USDC (superset of perps account value)
    const equityUsd = spotTotalUsdc ?? perpAccountValue;

    // Available = spot available after maintenance margin (if no open positions, ≈ equityUsd)
    // Fallback: perps account value minus used margin
    const perpAvailable = perpAccountValue !== undefined
      ? Math.max(0, Number(((perpAccountValue ?? 0) - (marginUsed ?? 0)).toFixed(6)))
      : undefined;
    const availableUsd = spotAvailableUsdc ?? perpAvailable ?? withdrawable;

    return {
      equityUsd,
      availableUsd,
      usedMarginUsd: marginUsed,
      raw: { perpState, spotState },
    };
  }

  async getOpenOrders(symbol?: string): Promise<OrderSnapshot[]> {
    const user = await this.resolveEffectiveUser();
    const target = symbol ? this.normalizeSymbol(symbol) : null;
    const requestedDex = target ? this.getDexFromSymbol(target) : null;
    const knownDexes = await this.getKnownDexes(user).catch(() => [] as string[]);
    const dexScopes = [...new Set([requestedDex ?? '', '', ...knownDexes].filter((dex) => dex !== null && dex !== undefined))];

    const rawGroups = await Promise.all(
      dexScopes.map((dex) => this.requestInfo<any[]>({ type: 'frontendOpenOrders', user, ...(dex ? { dex } : {}) }))
    );

    const mergedRaw = rawGroups.flatMap((rows, index) => {
      const dex = dexScopes[index] ?? '';
      return (Array.isArray(rows) ? rows : []).map((item) => ({ item, dex }));
    });

    const mapped = mergedRaw
      .map(({ item, dex }) => {
        const normalized = this.normalizeScopedSymbol(String(item?.coin ?? ''), dex);
        if (target && !this.symbolsMatch(normalized, target)) return null;

        const triggerPx = this.toNumber(item?.triggerPx);
        const limitPx = this.toNumber(item?.limitPx);
        const px = Number.isFinite(triggerPx) && Number(triggerPx) > 0 ? Number(triggerPx) : Number(limitPx);
        const sz = this.toNumber(item?.sz);
        if (!Number.isFinite(px) || Number(px) <= 0 || !Number.isFinite(sz) || Number(sz) < 0) return null;

        const sideRaw = String(item?.side ?? '').toLowerCase();
        const side = sideRaw === 'b' || sideRaw.includes('buy')
          ? 'buy'
          : sideRaw === 'a' || sideRaw.includes('sell')
            ? 'sell'
            : 'sell';

        return {
          id: String(item?.oid ?? ''),
          symbol: normalized,
          side,
          price: px,
          size: sz,
          status: 'open',
          raw: item
        } as OrderSnapshot;
      })
      .filter((x): x is OrderSnapshot => Boolean(x));

    const deduped = new Map<string, OrderSnapshot>();
    for (const row of mapped) {
      if (!deduped.has(row.id)) deduped.set(row.id, row);
    }

    return [...deduped.values()];
  }

  async getOpenExposures(symbol?: string): Promise<ExposureSnapshot[]> {
    const user = await this.resolveEffectiveUser();
    const target = symbol ? this.normalizeSymbol(symbol) : null;
    const requestedDex = target ? this.getDexFromSymbol(target) : null;
    const dexScopes = requestedDex ? [requestedDex] : ['', ...(await this.getKnownDexes(user))];

    const perpStates = await Promise.all(
      dexScopes.map((dex) => this.requestInfo<any>({ type: 'clearinghouseState', user, ...(dex ? { dex } : {}) }))
    );

    const perpRows = perpStates.flatMap((state, index) => {
      const dex = dexScopes[index];
      const rows = Array.isArray(state?.assetPositions) ? state.assetPositions : [];
      return rows.map((row: any) => ({ row, dex }));
    });

    const perpExposures = perpRows
      .map(({ row, dex }): ExposureSnapshot | null => {
        const p = row?.position;
        if (!p) return null;

        const normalized = this.normalizeScopedSymbol(String(p.coin ?? ''), dex);
        if (target && !this.symbolsMatch(normalized, target)) return null;

        const szi = this.toNumber(p.szi) ?? 0;
        const size = Math.abs(szi);
        if (size <= 0) return null;

        return {
          symbol: normalized,
          side: szi >= 0 ? 'long' : 'short',
          size,
          entryPrice: this.toNumber(p.entryPx),
          markPrice: this.toNumber(p.markPx),
          leverage: this.toNumber(p?.leverage?.value),
          unrealizedPnl: this.toNumber(p.unrealizedPnl),
          productType: 'perp',
          accountScope: 'master',
          source: dex ? `clearinghouseState:dex:${dex}` : 'clearinghouseState',
          raw: row,
        } as ExposureSnapshot;
      })
      .filter((x: ExposureSnapshot | null): x is ExposureSnapshot => Boolean(x));

    let spotExposures: ExposureSnapshot[] = [];
    if (!requestedDex) {
      try {
        const spot = await this.requestInfo<any>({ type: 'spotClearinghouseState', user });
        const stable = new Set(['USDC', 'USDE', 'USDT', 'USDT0', 'USDH']);
        const balances = Array.isArray(spot?.balances) ? spot.balances : [];
        spotExposures = balances
          .map((row: any): ExposureSnapshot | null => {
            const coin = this.normalizeSymbol(String(row?.coin ?? ''));
            const total = this.toNumber(row?.total) ?? 0;
            if (!coin || total <= 0 || stable.has(this.coreSymbol(coin))) return null;
            if (target && !this.symbolsMatch(coin, target)) return null;

            return {
              symbol: coin,
              side: 'long',
              size: total,
              productType: 'spot',
              accountScope: 'master',
              source: 'spotClearinghouseState',
              raw: row,
            };
          })
          .filter((x: ExposureSnapshot | null): x is ExposureSnapshot => Boolean(x));
      } catch (error) {
        logger.debug({ component: 'hyperliquid', err: error instanceof Error ? error.message : error }, 'spot exposure fetch skipped');
      }
    }

    const deduped = new Map<string, ExposureSnapshot>();
    for (const row of [...perpExposures, ...spotExposures]) {
      const key = `${row.productType}:${row.symbol}:${row.side}`;
      if (!deduped.has(key)) deduped.set(key, row);
    }

    return [...deduped.values()];
  }

  async getOpenPositions(symbol?: string): Promise<PositionSnapshot[]> {
    const exposures = await this.getOpenExposures(symbol);
    return exposures
      .filter((x) => x.productType === 'perp')
      .map((x) => ({
        symbol: x.symbol,
        side: x.side,
        size: x.size,
        entryPrice: x.entryPrice,
        markPrice: x.markPrice,
        leverage: x.leverage,
        unrealizedPnl: x.unrealizedPnl,
        raw: x.raw,
      } satisfies PositionSnapshot));
  }

  async getFills(symbol?: string): Promise<FillEvent[]> {
    const user = await this.resolveEffectiveUser();
    const raw = await this.requestInfo<any[]>({ type: 'userFills', user, aggregateByTime: true });
    const target = symbol ? this.normalizeSymbol(symbol) : null;

    return (Array.isArray(raw) ? raw : [])
      .map((item) => {
        const normalized = this.normalizeSymbol(String(item?.coin ?? ''));
        if (target && !this.symbolsMatch(normalized, target)) return null;

        const px = this.toNumber(item?.px);
        const sz = this.toNumber(item?.sz);
        const ts = Number(item?.time);
        if (!px || !sz || !Number.isFinite(ts)) return null;

        const sideText = String(item?.side ?? item?.dir ?? '').toLowerCase();
        const side: 'buy' | 'sell' = sideText.includes('buy') || sideText === 'b' || sideText.includes('long') ? 'buy' : 'sell';

        return {
          id: String(item?.tid ?? item?.oid ?? item?.hash ?? `${normalized}-${ts}`),
          symbol: normalized,
          side,
          price: px,
          size: sz,
          timestamp: new Date(ts).toISOString(),
          raw: item
        } as FillEvent;
      })
      .filter((x): x is FillEvent => Boolean(x));
  }

  /** Convert a clientOrderId to Hyperliquid-compatible cloid (0x + 32 hex chars) or undefined */
  private toCloid(clientOrderId?: string): string | undefined {
    if (!clientOrderId) return undefined;
    // If already valid hex cloid, pass through
    if (/^0x[0-9a-f]{32}$/i.test(clientOrderId)) return clientOrderId;
    // Generate deterministic hex from the string
    const hash = crypto.createHash('md5').update(clientOrderId).digest('hex'); // 32 hex chars
    return `0x${hash}`;
  }

  /**
   * Normalize price to Hyperliquid constraints:
   * - <= 5 significant digits
   * - <= (6 - szDecimals) decimal places
   * - additionally capped by pxDecimals when available
   */
  private async normalizeHlPriceForSymbol(symbol: string, value: number): Promise<number> {
    if (!Number.isFinite(value) || value <= 0) return value;

    const meta = await this.getInstrumentMeta(symbol).catch(() => undefined);
    const sizeDecimals = Math.max(0, Math.min(8, Number(meta?.sizeDecimals ?? 5)));
    const maxPriceDecimalsBySize = Math.max(0, 6 - sizeDecimals);
    const pxDecimalsRaw = Number(meta?.quoteDecimals);
    const pxDecimals = Number.isFinite(pxDecimalsRaw) ? Math.max(0, Math.min(8, pxDecimalsRaw)) : undefined;

    const abs = Math.abs(value);
    const digitsBefore = abs >= 1 ? Math.floor(Math.log10(abs)) + 1 : 0;
    const decimalsBySig = Math.max(0, 5 - digitsBefore);

    const decimalsByRules = Math.max(0, Math.min(maxPriceDecimalsBySize, decimalsBySig));
    const decimals = pxDecimals !== undefined ? Math.min(decimalsByRules, pxDecimals) : decimalsByRules;

    return Number(value.toFixed(decimals));
  }

  async placeLimitOrder(intent: OrderIntent): Promise<OrderAck> {
    try {
      const client = await this.getTradingClient();
      await this.ensureSdkAssetIndex(intent.symbol, client);
      const cloid = this.toCloid(intent.clientOrderId);

      const normalizedSymbol = this.normalizeSymbol(intent.symbol);
      const dex = this.getDexFromSymbol(normalizedSymbol);

      const normalizedPrice = await this.normalizeHlPriceForSymbol(intent.symbol, Number(intent.price));
      const meta = await this.getInstrumentMeta(intent.symbol).catch(() => undefined);
      const sizeDecimals = Math.max(0, Math.min(8, Number(meta?.sizeDecimals ?? 5)));
      const normalizedSize = Number.isFinite(Number(intent.size))
        ? Number(Number(intent.size).toFixed(sizeDecimals))
        : Number(intent.size);

      const response = await client.exchange.placeOrder({
        coin: this.toSdkCoin(intent.symbol),
        is_buy: intent.side === 'buy',
        sz: normalizedSize,
        limit_px: normalizedPrice,
        order_type: { limit: { tif: 'Gtc' } },
        reduce_only: Boolean(intent.reduceOnly),
        ...(cloid ? { cloid } : {}),
        ...(dex ? { dex } : {})
      } as any);

      const first = response?.response?.data?.statuses?.[0];
      let oid = first?.resting?.oid ?? first?.filled?.oid ?? first?.waiting?.oid;
      const status = first?.resting ? 'resting' : first?.filled ? 'filled' : first?.waiting ? 'waiting' : response?.status;
      const exchangeError = first?.error ?? first?.err;

      // Fallback lookup by clientOrderId if SDK response omits oid.
      if (oid === undefined && intent.clientOrderId) {
        try {
          const clientOrderId = intent.clientOrderId!;
          const user = await this.resolveEffectiveUser();
          const openOrders = await this.requestInfo<any[]>({ type: 'frontendOpenOrders', user });
          const cloid = this.toCloid(clientOrderId);
          if (cloid) {
            const cloidLower = cloid.toLowerCase();
            const row = (Array.isArray(openOrders) ? openOrders : []).find((o) => String(o?.cloid ?? '').toLowerCase() === cloidLower);
            if (row?.oid !== undefined) oid = row.oid;
          }
        } catch {
          // ignore fallback errors
        }
      }

      const ok = Boolean(oid) || (String(status ?? '').toLowerCase() === 'filled');

      return {
        ok,
        orderId: oid !== undefined ? String(oid) : undefined,
        clientOrderId: intent.clientOrderId,
        status,
        raw: response,
        error: ok ? undefined : (exchangeError ? String(exchangeError) : 'order_failed')
      };
    } catch (error) {
      return {
        ok: false,
        clientOrderId: intent.clientOrderId,
        error: error instanceof Error ? error.message : 'order_failed'
      };
    }
  }

  async placeTriggerOrder(intent: TriggerOrderIntent): Promise<OrderAck> {
    try {
      const client = await this.getTradingClient();
      await this.ensureSdkAssetIndex(intent.symbol, client);
      const triggerPxRaw = Number(intent.triggerPrice);
      const triggerPx = await this.normalizeHlPriceForSymbol(intent.symbol, triggerPxRaw);

      const isReduceOnly = Boolean(intent.reduceOnly ?? true);
      const normalizedSymbol = this.normalizeSymbol(intent.symbol);
      const dex = this.getDexFromSymbol(normalizedSymbol);
      const triggerMarketSlippagePct = dex ? DEX_TRIGGER_MARKET_SLIPPAGE_PCT : DEFAULT_TRIGGER_MARKET_SLIPPAGE_PCT;
      const marketLimitPx = await this.normalizeHlPriceForSymbol(
        intent.symbol,
        intent.side === 'buy'
          ? triggerPx * (1 + triggerMarketSlippagePct)
          : triggerPx * (1 - triggerMarketSlippagePct),
      );

      const meta = await this.getInstrumentMeta(intent.symbol).catch(() => undefined);
      const sizeDecimals = Math.max(0, Math.min(8, Number(meta?.sizeDecimals ?? 5)));
      const sizeRaw = Number(intent.size);
      const sizeRounded = Number.isFinite(sizeRaw) && sizeRaw > 0
        ? Number(sizeRaw.toFixed(sizeDecimals))
        : 0;

      const usePositionTpsl = isReduceOnly && intent.kind === 'sl';
      const triggerSize = usePositionTpsl ? 0 : sizeRounded;

      if (!usePositionTpsl && (!Number.isFinite(triggerSize) || triggerSize <= 0)) {
        return {
          ok: false,
          clientOrderId: intent.clientOrderId,
          error: 'invalid_trigger_size'
        };
      }

      const response = await client.exchange.placeOrder({
        coin: this.toSdkCoin(intent.symbol),
        is_buy: intent.side === 'buy',
        sz: triggerSize,
        // SDK requires limit_px for order wire formatting; for trigger-market use aggressive IOC-style bound.
        limit_px: marketLimitPx,
        order_type: {
          trigger: {
            triggerPx: triggerPx,
            isMarket: true,
            tpsl: intent.kind
          }
        },
        reduce_only: isReduceOnly,
        ...(usePositionTpsl ? { grouping: 'positionTpsl' } : {}),
        ...(intent.clientOrderId ? { cloid: this.toCloid(intent.clientOrderId) } : {}),
        ...(dex ? { dex } : {})
      } as any);

      const first = response?.response?.data?.statuses?.[0];
      let oid: string | number | undefined;
      let status = String(response?.status ?? '').toLowerCase();
      let exchangeError: string | undefined;

      if (typeof first === 'string') {
        const wire = first.trim().toLowerCase();
        if (wire.includes('waiting')) status = 'waiting';
        else if (wire.includes('resting')) status = 'resting';
        else if (wire.includes('filled')) status = 'filled';
        else if (wire.includes('error') || wire.includes('reject') || wire.includes('invalid')) {
          exchangeError = first;
        }
      } else if (first && typeof first === 'object') {
        // Trigger orders can return waiting.oid, not only resting.oid
        oid = (first as any)?.resting?.oid ?? (first as any)?.filled?.oid ?? (first as any)?.waiting?.oid;
        status = (first as any)?.resting ? 'resting' : (first as any)?.filled ? 'filled' : (first as any)?.waiting ? 'waiting' : status;
        const rawError = (first as any)?.error ?? (first as any)?.err;
        if (typeof rawError === 'string') {
          const trimmed = rawError.trim();
          if (trimmed && trimmed.toLowerCase() !== 'ok') exchangeError = trimmed;
        } else if (rawError && typeof rawError === 'object') {
          exchangeError = JSON.stringify(rawError);
        }
      }

      // Fallback lookup by clientOrderId if SDK response omits oid.
      if (oid === undefined && intent.clientOrderId) {
        try {
          const cloid = this.toCloid(intent.clientOrderId);
          if (cloid) {
            const cloidLower = cloid.toLowerCase();
            const allOrders = await this.getOpenOrders(normalizedSymbol);
            const row = allOrders.find((o) => String((o.raw as Record<string, unknown> | undefined)?.cloid ?? '').toLowerCase() === cloidLower);
            if ((row?.raw as Record<string, unknown> | undefined)?.oid !== undefined) {
              oid = (row?.raw as Record<string, unknown>).oid as string | number;
            }
          }
        } catch (e) {
          console.log(`[hl-adapter] fallback oid lookup failed:`, e instanceof Error ? e.message : String(e));
        }
      }

      // Hyperliquid can acknowledge trigger placements with string statuses like "waitingForTrigger" (without oid in payload).
      const waitingLike = status === 'waiting' || status === 'resting' || String(first ?? '').toLowerCase().includes('waitingfortrigger');
      const ok = Boolean(waitingLike || oid);

      return {
        ok,
        orderId: oid !== undefined ? String(oid) : undefined,
        clientOrderId: intent.clientOrderId,
        status,
        raw: response,
        error: ok ? undefined : (exchangeError ? String(exchangeError) : 'trigger_order_failed')
      };
    } catch (error) {
      return {
        ok: false,
        clientOrderId: intent.clientOrderId,
        error: error instanceof Error ? error.message : 'trigger_order_failed'
      };
    }
  }

  async cancelOrder(orderIdOrClientId: string): Promise<CommandResult> {
    try {
      const client = await this.getTradingClient();
      const openOrders = await this.getOpenOrders();

      const target = openOrders.find((o) => String(o.id) === String(orderIdOrClientId));
      if (!target) {
        return { ok: false, error: 'order_not_found' };
      }

      const coinSymbol = this.normalizeSymbol(target.symbol);
      await this.ensureSdkAssetIndex(coinSymbol, client);
      const dex = this.getDexFromSymbol(coinSymbol);

      const response = await client.exchange.cancelOrder({
        coin: this.toSdkCoin(target.symbol),
        o: Number(target.id),
        ...(dex ? { dex } : {})
      } as any);

      const ok = String(response?.status ?? '').toLowerCase() === 'ok';
      return {
        ok,
        raw: response,
        error: ok ? undefined : 'cancel_failed'
      };
    } catch (error) {
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'cancel_failed'
      };
    }
  }

  async cancelAll(symbol?: string): Promise<CommandResult> {
    try {
      const client = await this.getTradingClient();
      const target = symbol ? this.normalizeSymbol(symbol) : null;
      const rows = await this.getOpenOrders(target ?? undefined);

      if (rows.length === 0) {
        return { ok: true, raw: { canceled: 0 } };
      }

      const uniqueSymbols = [...new Set(rows.map((o) => this.normalizeSymbol(o.symbol)).filter(Boolean))];
      for (const coinSymbol of uniqueSymbols) {
        await this.ensureSdkAssetIndex(coinSymbol, client);
      }

      const cancels = rows
        .map((o) => {
          const coinSymbol = this.normalizeSymbol(o.symbol);
          const dex = this.getDexFromSymbol(coinSymbol);
          return {
            coin: this.toSdkCoin(o.symbol),
            o: Number(o.id),
            ...(dex ? { dex } : {})
          };
        })
        .filter((x) => Number.isFinite(x.o));

      if (cancels.length === 0) {
        return { ok: true, raw: { canceled: 0 } };
      }

      const response = await client.exchange.cancelOrder(cancels as any);
      const ok = String(response?.status ?? '').toLowerCase() === 'ok';

      return {
        ok,
        raw: response,
        error: ok ? undefined : 'cancel_all_failed'
      };
    } catch (error) {
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'cancel_all_failed'
      };
    }
  }

  async placeReduceOnlyExit(intent: OrderIntent): Promise<OrderAck> {
    return this.placeLimitOrder({
      ...intent,
      reduceOnly: true
    });
  }

  async setLeverage(symbol: string, leverage: number): Promise<CommandResult> {
    try {
      const client = await this.getTradingClient();
      const normalized = this.normalizeSymbol(symbol);
      await this.ensureSdkAssetIndex(normalized, client);
      const dex = this.getDexFromSymbol(normalized);
      
      // updateLeverage signature: (coin, isCross, leverage, dex?)
      const response = dex
        ? await (client.exchange.updateLeverage as any)(this.toSdkCoin(symbol), 'cross', leverage, dex)
        : await client.exchange.updateLeverage(this.toSdkCoin(symbol), 'cross', leverage);
      
      const ok = response !== null && response !== undefined;

      return {
        ok,
        raw: response,
        error: ok ? undefined : 'set_leverage_failed'
      };
    } catch (error) {
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'set_leverage_failed'
      };
    }
  }

  subscribeMids(options: MidStreamOptions): MidStreamHandle {
    let ws: WebSocket | null = null;
    let closed = false;

    const symbolsFilter = new Set((options.symbols ?? []).map((s) => s.toUpperCase()));

    try {
      ws = new WebSocket(this.wsUrl);

      ws.addEventListener('open', () => {
        options.onOpen?.();
        ws?.send(JSON.stringify({ method: 'subscribe', subscription: { type: 'allMids' } }));
      });

      ws.addEventListener('message', (event) => {
        try {
          const payload = JSON.parse(String(event.data)) as any;
          const mids = payload?.data?.mids ?? payload?.mids ?? null;
          if (!mids || typeof mids !== 'object') return;

          for (const [symbol, raw] of Object.entries(mids as Record<string, string>)) {
            const price = Number(raw);
            if (!Number.isFinite(price)) continue;
            const sym = symbol.toUpperCase();
            if (symbolsFilter.size > 0 && !symbolsFilter.has(sym)) continue;
            options.onMid(sym, price);
          }
        } catch {
          // ignore malformed frame
        }
      });

      ws.addEventListener('error', (error) => {
        options.onError?.(error);
      });

      ws.addEventListener('close', () => {
        if (!closed) {
          options.onClose?.();
        }
      });
    } catch (error) {
      options.onError?.(error);
      options.onClose?.();
    }

    return {
      close: () => {
        closed = true;
        try {
          ws?.close();
        } catch {
          // ignore close errors
        }
      }
    };
  }

  /**
   * Validate that the configured Hyperliquid wallet pair points at a real master account.
   * This fails closed: if the mapping cannot be verified, the connection is treated as invalid.
   */
  async validateConnectionIdentity(): Promise<string> {
    const accountAddress = this.accountAddress?.trim() ?? '';
    const apiWalletAddress = this.apiWalletAddress?.trim() ?? '';
    const privateKey = this.privateKey?.trim() ?? '';

    if (!accountAddress || !apiWalletAddress || !privateKey) {
      throw new Error('Hyperliquid account address, API wallet address, and private key are required');
    }

    const roleResult = await this.requestInfo<any>({ type: 'userRole', user: apiWalletAddress });
    const master = typeof roleResult?.data?.user === 'string' ? roleResult.data.user.trim() : '';

    if (!master) {
      throw new Error('Hyperliquid connection could not be verified. Please provide the correct Hyperliquid keys.');
    }

    if (roleResult?.role !== 'agent') {
      throw new Error('Hyperliquid API wallet is not an agent wallet. Please provide the correct Hyperliquid keys.');
    }

    if (master.toLowerCase() !== accountAddress.toLowerCase()) {
      throw new Error('Hyperliquid account address does not match the API wallet master account. Please provide the correct Hyperliquid keys.');
    }

    return master;
  }

  /**
   * Resolve the effective user address for read APIs.
   * If the configured pair is valid, return the master account resolved from the API wallet.
   */
  private async resolveEffectiveUser(): Promise<string> {
    const seed = this.accountAddress || this.apiWalletAddress;
    if (!seed) {
      throw new Error('HYPERLIQUID_ACCOUNT_ADDRESS or HYPERLIQUID_API_WALLET_ADDRESS is required');
    }

    if (this.effectiveUser) return this.effectiveUser;

    if (!this.effectiveUserInit) {
      this.effectiveUserInit = (async (): Promise<string> => {
        if (this.accountAddress && this.apiWalletAddress) {
          const master = await this.validateConnectionIdentity();
          logger.info({ component: 'hyperliquid', effectiveUser: `${master.slice(0, 6)}…${master.slice(-4)}` }, 'agent wallet verified');
          this.effectiveUser = master;
          return master;
        }

        this.effectiveUser = seed;
        return seed;
      })();
    }

    return this.effectiveUserInit;
  }

  private async getUniverse(dex?: string | null, force = false): Promise<{ bySymbol: Map<string, any>; indexBySymbol: Map<string, number>; symbols: string[] }> {
    const dexKey = String(dex ?? '').trim().toLowerCase();
    const now = Date.now();

    const cached = this.universeCacheByDex.get(dexKey);
    if (!force && cached && (now - cached.fetchedAtMs) < UNIVERSE_CACHE_TTL_MS) {
      return { bySymbol: cached.bySymbol, indexBySymbol: cached.indexBySymbol, symbols: cached.symbols };
    }

    const meta = await this.requestInfo<any>({ type: 'meta', ...(dexKey ? { dex: dexKey } : {}) });
    const universe = Array.isArray(meta?.universe) ? meta.universe : [];

    const bySymbol = new Map<string, any>();
    const indexBySymbol = new Map<string, number>();
    const symbols: string[] = [];

    for (let i = 0; i < universe.length; i++) {
      const row = universe[i];
      const normalized = this.normalizeScopedSymbol(String(row?.name ?? ''), dexKey);
      if (!normalized || bySymbol.has(normalized)) continue;
      bySymbol.set(normalized, row);
      indexBySymbol.set(normalized, i);
      symbols.push(normalized);
    }

    symbols.sort((a, b) => a.localeCompare(b));

    this.universeCacheByDex.set(dexKey, {
      fetchedAtMs: now,
      bySymbol,
      indexBySymbol,
      symbols,
    });

    return { bySymbol, indexBySymbol, symbols };
  }

  private getDexFromSymbol(symbol: string): string | null {
    const normalized = this.normalizeSymbol(symbol);
    if (!normalized.includes(':')) return null;
    const [dex] = normalized.split(':', 2);
    const clean = String(dex ?? '').trim().toLowerCase();
    return clean || null;
  }

  private async getKnownDexes(user: string): Promise<string[]> {
    const now = Date.now();
    if (this.knownDexesCache && (now - this.knownDexesCache.fetchedAtMs) < DEX_DISCOVERY_CACHE_TTL_MS) {
      return this.knownDexesCache.dexes;
    }

    const dexes = new Set<string>(EXTRA_DEXES_ENV);

    try {
      const fills = await this.requestInfo<any[]>({ type: 'userFills', user, aggregateByTime: true });
      for (const row of Array.isArray(fills) ? fills : []) {
        const normalized = this.normalizeSymbol(String(row?.coin ?? ''));
        const dex = this.getDexFromSymbol(normalized);
        if (dex) dexes.add(dex);
      }
    } catch (error) {
      logger.warn({ component: 'hyperliquid', err: error instanceof Error ? error.message : error }, 'dex discovery from fills failed');
    }

    const discovered = [...dexes].sort((a, b) => a.localeCompare(b));
    this.knownDexesCache = {
      fetchedAtMs: now,
      dexes: discovered,
    };

    return discovered;
  }

  private requireAccountAddress(): string {
    const seed = this.accountAddress || this.apiWalletAddress;
    if (!seed) {
      throw new Error('HYPERLIQUID_ACCOUNT_ADDRESS or HYPERLIQUID_API_WALLET_ADDRESS is required');
    }
    return seed;
  }

  private normalizeSymbol(symbol: string): string {
    const value = String(symbol ?? '').trim();
    if (!value) return '';

    if (value.includes(':')) {
      const [namespaceRaw, symbolRaw] = value.split(':', 2);
      const namespace = String(namespaceRaw ?? '').trim().toLowerCase();
      const core = String(symbolRaw ?? '').trim().toUpperCase().replace('-PERP', '');
      return namespace && core ? `${namespace}:${core}` : '';
    }

    return value.toUpperCase().replace('-PERP', '');
  }

  private normalizeScopedSymbol(symbol: string, dex?: string | null): string {
    const normalized = this.normalizeSymbol(symbol);
    if (!normalized) return '';
    if (normalized.includes(':')) return normalized;

    const cleanDex = String(dex ?? '').trim().toLowerCase();
    return cleanDex ? `${cleanDex}:${normalized}` : normalized;
  }

  private coreSymbol(symbol: string): string {
    const normalized = this.normalizeSymbol(symbol);
    if (!normalized) return '';
    if (!normalized.includes(':')) return normalized;
    const [, coreRaw] = normalized.split(':', 2);
    return String(coreRaw ?? '').trim().toUpperCase().replace('-PERP', '');
  }

  private symbolCandidates(symbol: string): string[] {
    const normalized = this.normalizeSymbol(symbol);
    const core = this.coreSymbol(symbol);
    return [...new Set([normalized, core].filter(Boolean))];
  }

  private symbolsMatch(left: string, right: string): boolean {
    const a = this.symbolCandidates(left);
    const b = this.symbolCandidates(right);
    return a.some((value) => b.includes(value));
  }

  private isUnknownAssetError(error: unknown): boolean {
    const message = String(error instanceof Error ? error.message : error ?? '').toLowerCase();
    return message.includes('unknown asset') || message.includes('asset index not found') || message.includes('asset_not_found');
  }

  private async ensureSdkAssetIndex(symbol: string, client: Hyperliquid): Promise<void> {
    const normalized = this.normalizeSymbol(symbol);
    if (!normalized.includes(':')) return;

    const dex = this.getDexFromSymbol(normalized);
    if (!dex) return;

    // Force SDK symbol conversion init once; after init we can safely patch static maps.
    await (client.info as any)?.getAllAssets?.().catch(() => undefined);

    const universe = await this.getUniverse(dex);
    const idx = universe.indexBySymbol.get(normalized);
    if (!Number.isFinite(idx)) {
      throw new Error(`asset_index_not_found_for_symbol:${normalized}`);
    }

    const symbolConversion = (client as any)?.symbolConversion;
    const assetMap = symbolConversion?.assetToIndexMap;

    if (!(assetMap instanceof Map)) {
      throw new Error('sdk_asset_map_unavailable');
    }

    // SDK expects internal PERP names; patch both raw and -PERP aliases for robustness.
    const aliases = [...new Set([normalized, `${normalized}-PERP`])];
    for (const alias of aliases) {
      assetMap.set(alias, idx);
    }
  }

  private toSdkCoin(symbol: string): string {
    const normalized = this.normalizeSymbol(symbol);
    if (!normalized) return '';
    
    // DEX symbols (xyz:GOLD) are passed as-is to SDK
    if (normalized.includes(':')) {
      return normalized;
    }
    
    // Regular symbols get -PERP suffix
    return `${normalized}-PERP`;
  }

  private toNumber(value: unknown): number | undefined {
    const n = Number(value);
    return Number.isFinite(n) ? n : undefined;
  }

  private async getTradingClient(): Promise<Hyperliquid> {
    const walletAddress = await this.resolveEffectiveUser();

    if (!this.privateKey) {
      throw new Error('HYPERLIQUID_API_PRIVATE_KEY is missing');
    }

    if (this.tradingClient) {
      return this.tradingClient;
    }

    if (!this.tradingClientInit) {
      this.tradingClientInit = (async () => {
        const client = new Hyperliquid({
          enableWs: false,
          privateKey: this.privateKey,
          walletAddress,
          testnet: this.testnet,
          disableAssetMapRefresh: true
        });
        await client.connect();
        this.tradingClientInitFailures = 0;
        return client;
      })();

      // Reset the cached promise on failure so subsequent calls can retry
      this.tradingClientInit.catch(() => {
        this.tradingClientInitFailures++;
        logger.warn(
          { component: 'hyperliquid', failures: this.tradingClientInitFailures },
          'trading client init failed, will retry on next call'
        );
        this.tradingClientInit = null;
      });
    }

    this.tradingClient = await this.tradingClientInit;
    return this.tradingClient;
  }

  private async requestInfo<T>(payload: unknown): Promise<T> {
    const response = await this.fetchImpl(this.infoUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Hyperliquid info request failed: ${response.status}`);
    }

    return response.json() as Promise<T>;
  }
}
