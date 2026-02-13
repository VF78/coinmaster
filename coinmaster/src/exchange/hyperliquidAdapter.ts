import { ExchangeAdapter, ExchangeAdapterNotImplementedError } from './adapter.js';
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
  PositionSnapshot
} from './types.js';

interface HyperliquidAdapterOptions {
  infoUrl?: string;
  wsUrl?: string;
  fetchImpl?: typeof fetch;
}

const DEFAULT_INFO_URL = 'https://api.hyperliquid.xyz/info';
const DEFAULT_WS_URL = 'wss://api.hyperliquid.xyz/ws';

export class HyperliquidAdapter implements ExchangeAdapter {
  readonly name = 'hyperliquid';

  readonly capabilities: ExchangeCapabilities = {
    realtimeMids: true,
    historicalCandles: true,
    privateAccount: false,
    privateTrading: false,
    reduceOnly: true,
    cancelReplace: false
  };

  private readonly infoUrl: string;
  private readonly wsUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: HyperliquidAdapterOptions = {}) {
    this.infoUrl = options.infoUrl ?? DEFAULT_INFO_URL;
    this.wsUrl = options.wsUrl ?? DEFAULT_WS_URL;
    this.fetchImpl = options.fetchImpl ?? fetch;
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
    throw new ExchangeAdapterNotImplementedError('getAccountState', this.name);
  }

  async getOpenOrders(_symbol?: string): Promise<OrderSnapshot[]> {
    throw new ExchangeAdapterNotImplementedError('getOpenOrders', this.name);
  }

  async getOpenPositions(_symbol?: string): Promise<PositionSnapshot[]> {
    throw new ExchangeAdapterNotImplementedError('getOpenPositions', this.name);
  }

  async getFills(_symbol?: string): Promise<FillEvent[]> {
    throw new ExchangeAdapterNotImplementedError('getFills', this.name);
  }

  async placeLimitOrder(_intent: OrderIntent): Promise<OrderAck> {
    throw new ExchangeAdapterNotImplementedError('placeLimitOrder', this.name);
  }

  async cancelOrder(_orderIdOrClientId: string): Promise<CommandResult> {
    throw new ExchangeAdapterNotImplementedError('cancelOrder', this.name);
  }

  async cancelAll(_symbol?: string): Promise<CommandResult> {
    throw new ExchangeAdapterNotImplementedError('cancelAll', this.name);
  }

  async placeReduceOnlyExit(_intent: OrderIntent): Promise<OrderAck> {
    throw new ExchangeAdapterNotImplementedError('placeReduceOnlyExit', this.name);
  }

  async setLeverage(_symbol: string, _leverage: number): Promise<CommandResult> {
    throw new ExchangeAdapterNotImplementedError('setLeverage', this.name);
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
