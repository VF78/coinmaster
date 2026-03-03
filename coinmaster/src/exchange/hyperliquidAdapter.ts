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
}

const DEFAULT_INFO_URL = 'https://api.hyperliquid.xyz/info';
const DEFAULT_WS_URL = 'wss://api.hyperliquid.xyz/ws';

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

  constructor(options: HyperliquidAdapterOptions = {}) {
    this.infoUrl = options.infoUrl ?? DEFAULT_INFO_URL;
    this.wsUrl = options.wsUrl ?? DEFAULT_WS_URL;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.testnet = options.testnet ?? false;

    this.accountAddress = process.env.HYPERLIQUID_ACCOUNT_ADDRESS?.trim();
    this.privateKey = process.env.HYPERLIQUID_API_PRIVATE_KEY?.trim();
    this.apiWalletAddress = process.env.HYPERLIQUID_API_WALLET_ADDRESS?.trim();

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
    const raw = await this.requestInfo<Array<Record<string, string | number>>>(
      {
        type: 'candleSnapshot',
        req: {
          coin: query.symbol,
          interval: query.timeframe,
          startTime: query.startTimeMs,
          endTime: query.endTimeMs
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

    return rows;
  }

  async getInstrumentMeta(symbol: string): Promise<InstrumentMeta | null> {
    const meta = await this.requestInfo<any>({ type: 'meta' });
    const universe = Array.isArray(meta?.universe) ? meta.universe : [];
    const item = universe.find((u: any) => String(u?.name ?? '').toUpperCase() === symbol.toUpperCase());
    if (!item) return null;

    return {
      symbol: symbol.toUpperCase(),
      sizeDecimals: Number.isFinite(Number(item.szDecimals)) ? Number(item.szDecimals) : undefined,
      quoteDecimals: Number.isFinite(Number(item.pxDecimals)) ? Number(item.pxDecimals) : undefined,
      raw: item
    };
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
    // frontendOpenOrders includes trigger orders (TP/SL) + regular limits
    const raw = await this.requestInfo<any[]>({ type: 'frontendOpenOrders', user });
    const target = symbol ? this.normalizeSymbol(symbol) : null;

    return (Array.isArray(raw) ? raw : [])
      .map((item) => {
        const normalized = this.normalizeSymbol(String(item?.coin ?? ''));
        if (target && normalized !== target) return null;

        const px = this.toNumber(item?.triggerPx ?? item?.limitPx);
        const sz = this.toNumber(item?.sz);
        if (!px || !sz) return null;

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
  }

  async getOpenPositions(symbol?: string): Promise<PositionSnapshot[]> {
    const user = await this.resolveEffectiveUser();
    const state = await this.requestInfo<any>({ type: 'clearinghouseState', user });
    const target = symbol ? this.normalizeSymbol(symbol) : null;

    const rows = Array.isArray(state?.assetPositions) ? state.assetPositions : [];

    return rows
      .map((row: any): PositionSnapshot | null => {
        const p = row?.position;
        if (!p) return null;

        const normalized = this.normalizeSymbol(String(p.coin ?? ''));
        if (target && normalized !== target) return null;

        const szi = this.toNumber(p.szi) ?? 0;
        const size = Math.abs(szi);
        if (size <= 0) return null;

        return {
          symbol: normalized,
          side: szi >= 0 ? 'long' : 'short',
          size,
          entryPrice: this.toNumber(p.entryPx),
          leverage: this.toNumber(p?.leverage?.value),
          unrealizedPnl: this.toNumber(p.unrealizedPnl),
          raw: row
        } as PositionSnapshot;
      })
      .filter((x: PositionSnapshot | null): x is PositionSnapshot => Boolean(x));
  }

  async getFills(symbol?: string): Promise<FillEvent[]> {
    const user = await this.resolveEffectiveUser();
    const raw = await this.requestInfo<any[]>({ type: 'userFills', user, aggregateByTime: true });
    const target = symbol ? this.normalizeSymbol(symbol) : null;

    return (Array.isArray(raw) ? raw : [])
      .map((item) => {
        const normalized = this.normalizeSymbol(String(item?.coin ?? ''));
        if (target && normalized !== target) return null;

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
      const cloid = this.toCloid(intent.clientOrderId);

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
        ...(cloid ? { cloid } : {})
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
      const triggerPxRaw = Number(intent.triggerPrice);
      const triggerPx = await this.normalizeHlPriceForSymbol(intent.symbol, triggerPxRaw);
      const marketLimitPx = await this.normalizeHlPriceForSymbol(
        intent.symbol,
        intent.side === 'buy' ? triggerPx * 1.03 : triggerPx * 0.97,
      );

      console.log('[hl-adapter] placeTriggerOrder req', {
        symbol: intent.symbol,
        side: intent.side,
        size: intent.size,
        triggerPrice: triggerPx,
        limitPx: marketLimitPx,
        kind: intent.kind,
      });

      const response = await client.exchange.placeOrder({
        coin: this.toSdkCoin(intent.symbol),
        is_buy: intent.side === 'buy',
        sz: intent.size,
        // SDK requires limit_px for order wire formatting; for trigger-market use aggressive IOC-style bound.
        limit_px: marketLimitPx,
        order_type: {
          trigger: {
            triggerPx: triggerPx,
            isMarket: true,
            tpsl: intent.kind
          }
        },
        reduce_only: Boolean(intent.reduceOnly ?? true),
        ...(intent.clientOrderId ? { cloid: this.toCloid(intent.clientOrderId) } : {})
      } as any);

      const first = response?.response?.data?.statuses?.[0];
      // Trigger orders return waiting.oid, not resting.oid
      let oid = first?.resting?.oid ?? first?.filled?.oid ?? first?.waiting?.oid;
      const status = first?.resting ? 'resting' : first?.filled ? 'filled' : first?.waiting ? 'waiting' : response?.status;
      
      // Safely extract error message
      let exchangeError: string | undefined;
      try {
        const rawError = first?.error ?? first?.err ?? response?.response?.data?.statuses?.[0]?.status ?? response?.status ?? response?.response?.status;
        if (rawError && typeof rawError === 'string') {
          exchangeError = rawError.trim() || undefined;
        } else if (rawError && typeof rawError === 'object') {
          exchangeError = JSON.stringify(rawError);
        }
      } catch {
        // ignore error extraction errors
      }

      if (exchangeError) {
        console.log(`[hl-adapter] placeTriggerOrder ${intent.symbol} ${intent.kind}: error=${exchangeError}`);
      }

      // Fallback lookup by clientOrderId if SDK response omits oid.
      if (oid === undefined && intent.clientOrderId) {
        try {
          const clientOrderId = intent.clientOrderId!;
          const user = await this.resolveEffectiveUser();
          // Use frontendOpenOrders which includes trigger orders, not just openOrders
          const allOrders = await this.requestInfo<any[]>({ type: 'frontendOpenOrders', user });
          const cloid = this.toCloid(clientOrderId);
          if (cloid) {
            const cloidLower = cloid.toLowerCase();
            const row = (Array.isArray(allOrders) ? allOrders : []).find((o) => String(o?.cloid ?? '').toLowerCase() === cloidLower);
            if (row?.oid !== undefined) {
              oid = row.oid;
              console.log(`[hl-adapter] found oid via frontendOpenOrders: ${oid}`);
            }
          }
        } catch (e) {
          console.log(`[hl-adapter] fallback oid lookup failed:`, e instanceof Error ? e.message : String(e));
        }
      }

      // Trigger levels are considered successful when waiting on exchange with oid.
      const ok = Boolean(oid) && (String(status ?? '').toLowerCase() === 'waiting' || String(status ?? '').toLowerCase() === 'resting');

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
      const user = await this.resolveEffectiveUser();
      const openOrders = await this.requestInfo<any[]>({ type: 'frontendOpenOrders', user });

      const target = (Array.isArray(openOrders) ? openOrders : []).find((o) => String(o?.oid ?? '') === String(orderIdOrClientId));
      if (!target) {
        return { ok: false, error: 'order_not_found' };
      }

      const response = await client.exchange.cancelOrder({
        coin: this.toSdkCoin(String(target.coin ?? '')),
        o: Number(target.oid)
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
      const user = await this.resolveEffectiveUser();
      const openOrders = await this.requestInfo<any[]>({ type: 'frontendOpenOrders', user });
      const target = symbol ? this.normalizeSymbol(symbol) : null;

      const rows = (Array.isArray(openOrders) ? openOrders : []).filter((o) => {
        if (!target) return true;
        return this.normalizeSymbol(String(o?.coin ?? '')) === target;
      });

      if (rows.length === 0) {
        return { ok: true, raw: { canceled: 0 } };
      }

      const cancels = rows
        .map((o) => ({
          coin: this.toSdkCoin(String(o?.coin ?? '')),
          o: Number(o?.oid)
        }))
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
      const response = await client.exchange.updateLeverage(this.toSdkCoin(symbol), 'cross', leverage);
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
   * Resolve the effective user address for read APIs.
   * If the seed address is an API agent wallet, look up the master account via userRole.
   * Result is cached after first successful resolution.
   */
  private async resolveEffectiveUser(): Promise<string> {
    const seed = this.accountAddress || this.apiWalletAddress;
    if (!seed) {
      throw new Error('HYPERLIQUID_ACCOUNT_ADDRESS or HYPERLIQUID_API_WALLET_ADDRESS is required');
    }

    if (this.effectiveUser) return this.effectiveUser;

    if (!this.effectiveUserInit) {
      this.effectiveUserInit = (async (): Promise<string> => {
        try {
          const roleResult = await this.requestInfo<any>({ type: 'userRole', user: seed });
          if (roleResult?.role === 'agent' && typeof roleResult?.data?.user === 'string') {
            const master = roleResult.data.user.trim();
            if (master) {
              logger.info({ component: 'hyperliquid', effectiveUser: `${master.slice(0, 6)}…${master.slice(-4)}` }, 'agent wallet detected');
              this.effectiveUser = master;
              return master;
            }
          }
        } catch (error) {
          logger.warn({ component: 'hyperliquid', err: error instanceof Error ? error.message : error }, 'userRole lookup failed, falling back to seed address');
        }
        // Fallback: use seed address as-is
        this.effectiveUser = seed;
        return seed;
      })();
    }

    return this.effectiveUserInit;
  }

  private requireAccountAddress(): string {
    const seed = this.accountAddress || this.apiWalletAddress;
    if (!seed) {
      throw new Error('HYPERLIQUID_ACCOUNT_ADDRESS or HYPERLIQUID_API_WALLET_ADDRESS is required');
    }
    return seed;
  }

  private normalizeSymbol(symbol: string): string {
    return symbol.toUpperCase().replace('-PERP', '');
  }

  private toSdkCoin(symbol: string): string {
    const normalized = this.normalizeSymbol(symbol);
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
