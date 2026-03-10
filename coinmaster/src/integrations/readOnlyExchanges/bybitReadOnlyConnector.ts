import crypto from 'node:crypto';
import type { FillEvent } from '../../exchange/types.js';
import type { BybitConnectionSettings, LiveAccountSummary, ExchangeConnectionStatus } from '../../shared/dto.js';
import type { ReadOnlyExchangeConnector } from './types.js';

const BYBIT_BASE_URL = process.env.BYBIT_API_BASE_URL || 'https://api.bybit.com';
const BYBIT_RECV_WINDOW = '10000';
const BYBIT_TIMEOUT_MS = Math.max(4000, Number(process.env.BYBIT_TIMEOUT_MS || 12000));
const BYBIT_MAX_PAGES = Math.max(1, Number(process.env.BYBIT_MAX_PAGES || 5));

type BybitCategory = 'linear' | 'inverse' | 'spot' | 'option';

interface BybitEnvelope<T> {
  retCode: number;
  retMsg: string;
  result?: T;
  time?: number;
}

export interface BybitExecutionRow {
  symbol?: string;
  side?: string;
  execPrice?: string;
  execQty?: string;
  execTime?: string;
  execFee?: string;
  execPnl?: string;
  closedSize?: string;
  execId?: string;
  orderId?: string;
}

interface BybitExecutionResult {
  list?: BybitExecutionRow[];
  nextPageCursor?: string;
}

interface BybitWalletRow {
  totalEquity?: string;
  totalAvailableBalance?: string;
  totalInitialMargin?: string;
  totalMarginBalance?: string;
}

interface BybitWalletResult {
  list?: BybitWalletRow[];
}

function toFinite(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeCategories(input: BybitConnectionSettings['categories']): BybitCategory[] {
  const normalized = Array.isArray(input)
    ? [...new Set(input.filter((x): x is BybitCategory => x === 'linear' || x === 'inverse' || x === 'spot' || x === 'option'))]
    : [];
  return normalized.length > 0 ? normalized : ['linear'];
}

function safeMask(value: string): string {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  if (raw.length < 8) return '••••';
  return `${raw.slice(0, 3)}••••${raw.slice(-3)}`;
}

async function signedGet<T>(config: BybitConnectionSettings, path: string, query: Record<string, string>): Promise<T> {
  const timestamp = Date.now().toString();
  const qs = new URLSearchParams(query).toString();
  const payload = `${timestamp}${config.apiKey}${BYBIT_RECV_WINDOW}${qs}`;
  const signature = crypto
    .createHmac('sha256', config.apiSecret)
    .update(payload)
    .digest('hex');

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), BYBIT_TIMEOUT_MS);

  try {
    const response = await fetch(`${BYBIT_BASE_URL}${path}?${qs}`, {
      method: 'GET',
      headers: {
        'X-BAPI-API-KEY': config.apiKey,
        'X-BAPI-SIGN': signature,
        'X-BAPI-SIGN-TYPE': '2',
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': BYBIT_RECV_WINDOW,
      },
      signal: controller.signal,
    });

    const body = await response.json() as BybitEnvelope<T>;
    if (!response.ok) {
      throw new Error(`http_${response.status}`);
    }

    if (body.retCode !== 0) {
      throw new Error(`bybit_${body.retCode}:${body.retMsg || 'request_failed'}`);
    }

    if (!body.result) {
      throw new Error('bybit_empty_result');
    }

    return body.result;
  } finally {
    clearTimeout(timer);
  }
}

function getDirection(row: BybitExecutionRow): string {
  const closedSize = toFinite(row.closedSize, 0);
  if (closedSize > 0) return 'close trade';
  return 'open trade';
}

export function normalizeBybitExecutionToFill(category: BybitCategory, row: BybitExecutionRow): FillEvent | null {
  const symbol = String(row.symbol ?? '').trim().toUpperCase();
  const sideRaw = String(row.side ?? '').trim().toLowerCase();
  const side = sideRaw === 'buy' ? 'buy' : sideRaw === 'sell' ? 'sell' : null;
  const price = toFinite(row.execPrice, NaN);
  const size = toFinite(row.execQty, NaN);
  const tsMs = toFinite(row.execTime, NaN);

  if (!symbol || !side || !Number.isFinite(price) || price <= 0 || !Number.isFinite(size) || size <= 0 || !Number.isFinite(tsMs) || tsMs <= 0) {
    return null;
  }

  const execId = String(row.execId ?? '').trim();
  const orderId = String(row.orderId ?? '').trim();
  const id = execId || orderId || `${symbol}:${tsMs}:${size}:${price}`;

  const fee = Math.abs(toFinite(row.execFee, 0));
  const closedPnl = toFinite(row.execPnl, 0);
  const dir = getDirection(row);

  return {
    id: `bybit:${category}:${id}`,
    symbol,
    side,
    price,
    size,
    timestamp: new Date(tsMs).toISOString(),
    raw: {
      sourceExchange: 'bybit',
      category,
      fee,
      closedPnl,
      dir,
      bybit: row,
    },
  } satisfies FillEvent;
}

async function fetchWallet(config: BybitConnectionSettings): Promise<LiveAccountSummary | null> {
  const result = await signedGet<BybitWalletResult>(config, '/v5/account/wallet-balance', {
    accountType: config.accountType,
  });

  const row = (result.list ?? [])[0];
  if (!row) return null;

  return {
    equityUsd: toFinite(row.totalEquity, undefined as unknown as number),
    availableUsd: toFinite(row.totalAvailableBalance, undefined as unknown as number),
    usedMarginUsd: toFinite(row.totalInitialMargin, undefined as unknown as number),
  };
}

export class BybitReadOnlyConnector implements ReadOnlyExchangeConnector<BybitConnectionSettings> {
  readonly id = 'bybit' as const;

  validateConfig(config: BybitConnectionSettings): { ok: true } | { ok: false; error: string } {
    if (config.mode === 'off') return { ok: true };
    if (!String(config.apiKey ?? '').trim()) return { ok: false, error: 'missing_api_key' };
    if (!String(config.apiSecret ?? '').trim()) return { ok: false, error: 'missing_api_secret' };
    return { ok: true };
  }

  async getStatus(config: BybitConnectionSettings): Promise<ExchangeConnectionStatus> {
    const valid = this.validateConfig(config);
    if (!valid.ok) {
      return {
        exchange: this.id,
        mode: config.mode,
        configured: false,
        connected: false,
        readOnly: true,
        message: config.mode === 'off' ? 'disabled' : valid.error,
      };
    }

    if (config.mode === 'off') {
      return {
        exchange: this.id,
        mode: config.mode,
        configured: Boolean(config.apiKey && config.apiSecret),
        connected: false,
        readOnly: true,
        message: 'disabled',
      };
    }

    try {
      const account = await this.getAccountSnapshot(config);
      return {
        exchange: this.id,
        mode: config.mode,
        configured: true,
        connected: true,
        readOnly: true,
        account,
        message: `key:${safeMask(config.apiKey)}`,
      };
    } catch (error) {
      return {
        exchange: this.id,
        mode: config.mode,
        configured: true,
        connected: false,
        readOnly: true,
        message: error instanceof Error ? error.message : 'connection_failed',
      };
    }
  }

  async getRecentFills(config: BybitConnectionSettings, sinceMs: number): Promise<FillEvent[]> {
    if (config.mode === 'off') return [];

    const valid = this.validateConfig(config);
    if (!valid.ok) return [];

    const categories = normalizeCategories(config.categories);
    const allRows: FillEvent[] = [];

    for (const category of categories) {
      let cursor = '';
      for (let page = 0; page < BYBIT_MAX_PAGES; page += 1) {
        const result = await signedGet<BybitExecutionResult>(config, '/v5/execution/list', {
          category,
          startTime: String(Math.max(0, Math.floor(sinceMs))),
          limit: '100',
          ...(cursor ? { cursor } : {}),
        });

        const rows = (result.list ?? [])
          .map((row) => normalizeBybitExecutionToFill(category, row))
          .filter((x): x is FillEvent => Boolean(x));

        allRows.push(...rows);

        const next = String(result.nextPageCursor ?? '').trim();
        if (!next) break;
        cursor = next;
      }
    }

    const deduped = new Map<string, FillEvent>();
    for (const row of allRows) {
      if (!deduped.has(row.id)) deduped.set(row.id, row);
    }

    return [...deduped.values()].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  }

  async getAccountSnapshot(config: BybitConnectionSettings): Promise<LiveAccountSummary | null> {
    if (config.mode === 'off') return null;
    return fetchWallet(config);
  }
}
