import crypto from 'node:crypto';
import { Hyperliquid } from 'hyperliquid';
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

  constructor(options: HyperliquidAdapterOptions = {}) {
    this.infoUrl = options.infoUrl ?? DEFAULT_INFO_URL;
    this.wsUrl = options.wsUrl ?? DEFAULT_WS_URL;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.testnet = options.testnet ?? false;

    this.accountAddress = process.env.HYPERLIQUID_ACCOUNT_ADDRESS?.trim();
    this.privateKey = process.env.HYPERLIQUID_API_PRIVATE_KEY?.trim();
    this.apiWalletAddress = process.env.HYPERLIQUID_API_WALLET_ADDRESS?.trim();

    const hasAccount = Boolean(this.accountAddress);
    const hasTrading = Boolean(this.accountAddress && this.privateKey);

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
    const user = this.requireAccountAddress();
    const state = await this.requestInfo<any>({ type: 'clearinghouseState', user });

    const accountValue = this.toNumber(state?.crossMarginSummary?.accountValue ?? state?.marginSummary?.accountValue);
    const marginUsed = this.toNumber(state?.crossMarginSummary?.totalMarginUsed ?? state?.marginSummary?.totalMarginUsed);
    const withdrawable = this.toNumber(state?.withdrawable);

    const availableToTrade =
      accountValue !== undefined
        ? Math.max(0, Number((accountValue - (marginUsed ?? 0)).toFixed(6)))
        : undefined;

    return {
      equityUsd: accountValue,
      availableUsd: availableToTrade ?? withdrawable,
      usedMarginUsd: marginUsed,
      raw: state
    };
  }

  async getOpenOrders(symbol?: string): Promise<OrderSnapshot[]> {
    const user = this.requireAccountAddress();
    const raw = await this.requestInfo<any[]>({ type: 'openOrders', user });
    const target = symbol ? this.normalizeSymbol(symbol) : null;

    return (Array.isArray(raw) ? raw : [])
      .map((item) => {
        const normalized = this.normalizeSymbol(String(item?.coin ?? ''));
        if (target && normalized !== target) return null;

        const px = this.toNumber(item?.limitPx);
        const sz = this.toNumber(item?.sz);
        if (!px || !sz) return null;

        return {
          id: String(item?.oid ?? ''),
          symbol: normalized,
          side: String(item?.side ?? '').toLowerCase().includes('buy') ? 'buy' : 'sell',
          price: px,
          size: sz,
          status: 'open',
          raw: item
        } as OrderSnapshot;
      })
      .filter((x): x is OrderSnapshot => Boolean(x));
  }

  async getOpenPositions(symbol?: string): Promise<PositionSnapshot[]> {
    const user = this.requireAccountAddress();
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
    const user = this.requireAccountAddress();
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

  async placeLimitOrder(intent: OrderIntent): Promise<OrderAck> {
    try {
      const client = await this.getTradingClient();
      const cloid = this.toCloid(intent.clientOrderId);
      const response = await client.exchange.placeOrder({
        coin: this.toSdkCoin(intent.symbol),
        is_buy: intent.side === 'buy',
        sz: intent.size,
        limit_px: intent.price,
        order_type: { limit: { tif: 'Gtc' } },
        reduce_only: Boolean(intent.reduceOnly),
        ...(cloid ? { cloid } : {})
      } as any);

      const first = response?.response?.data?.statuses?.[0];
      const oid = first?.resting?.oid ?? first?.filled?.oid;
      const ok = String(response?.status ?? '').toLowerCase() === 'ok' || Boolean(oid);

      return {
        ok,
        orderId: oid !== undefined ? String(oid) : undefined,
        clientOrderId: intent.clientOrderId,
        status: first?.resting ? 'resting' : first?.filled ? 'filled' : response?.status,
        raw: response,
        error: ok ? undefined : 'order_failed'
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
      const response = await client.exchange.placeOrder({
        coin: this.toSdkCoin(intent.symbol),
        is_buy: intent.side === 'buy',
        sz: intent.size,
        limit_px: intent.triggerPrice,
        order_type: {
          trigger: {
            triggerPx: intent.triggerPrice,
            isMarket: true,
            tpsl: intent.kind
          }
        },
        reduce_only: Boolean(intent.reduceOnly ?? true),
        ...(intent.clientOrderId ? { cloid: this.toCloid(intent.clientOrderId) } : {})
      } as any);

      const first = response?.response?.data?.statuses?.[0];
      const oid = first?.resting?.oid ?? first?.filled?.oid;
      const ok = String(response?.status ?? '').toLowerCase() === 'ok' || Boolean(oid);

      return {
        ok,
        orderId: oid !== undefined ? String(oid) : undefined,
        clientOrderId: intent.clientOrderId,
        status: first?.resting ? 'resting' : first?.filled ? 'filled' : response?.status,
        raw: response,
        error: ok ? undefined : 'trigger_order_failed'
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
      const user = this.requireAccountAddress();
      const openOrders = await this.requestInfo<any[]>({ type: 'openOrders', user });

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
      const user = this.requireAccountAddress();
      const openOrders = await this.requestInfo<any[]>({ type: 'openOrders', user });
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

  private requireAccountAddress(): string {
    if (!this.accountAddress) {
      throw new Error('HYPERLIQUID_ACCOUNT_ADDRESS is missing');
    }
    return this.accountAddress;
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
    this.requireAccountAddress();

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
          walletAddress: this.accountAddress,
          testnet: this.testnet,
          disableAssetMapRefresh: true
        });
        await client.connect();
        return client;
      })();
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
