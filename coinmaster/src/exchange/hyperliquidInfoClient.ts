import logger from '../lib/logger.js';

/**
 * Shared coordinator for Hyperliquid `info` POST requests.
 *
 * Purpose: collapse the uncoordinated read pressure that multiple monitor
 * loops (drawdown watchdog, engulfing, FVG, TP monitor, REST fallback,
 * live dashboard warmup) put on `https://api.hyperliquid.xyz/info` — which
 * previously surfaced as 429/500 errors at startup and during concurrent
 * monitor ticks.
 *
 * Bounded mechanisms, applied to `info` reads only:
 *   1. In-flight dedupe — simultaneous identical payloads share one fetch.
 *   2. Concurrency cap — hard ceiling on concurrent upstream calls.
 *   3. Global pacing — no bursty upstream starts even when loops wake together.
 *   4. Short response cache — near-simultaneous sequential identical reads reuse
 *      a fresh result instead of stampeding after the first request resolves.
 *   5. Retry + backoff — transient 429/5xx and network errors retry with
 *      jittered exponential backoff, honoring `Retry-After` when present.
 *
 * Keep scope narrow: idempotent info reads only. Order placement goes
 * through the SDK directly and is untouched.
 */

export interface HyperliquidInfoClientOptions {
  infoUrl: string;
  fetchImpl: typeof fetch;
  maxConcurrency?: number;
  maxRetries?: number;
  baseBackoffMs?: number;
  maxBackoffMs?: number;
  minIntervalMs?: number;
  responseCacheTtlMs?: number;
}

interface CoordinatorStats {
  totalRequests: number;
  dedupedRequests: number;
  retries: number;
  failures: number;
  cachedRequests: number;
  activeCount: number;
  queueLength: number;
  inFlightCount: number;
  responseCacheCount: number;
  minIntervalMs: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseRetryAfterMs(header: string | null): number | null {
  if (!header) return null;
  const seconds = Number(header);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.floor(seconds * 1000);
  const date = Date.parse(header);
  if (Number.isFinite(date)) return Math.max(0, date - Date.now());
  return null;
}

function stableStringify(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const entries = keys.map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`);
  return `{${entries.join(',')}}`;
}

function payloadOpTag(payload: unknown): string {
  if (payload && typeof payload === 'object') {
    const type = (payload as { type?: unknown }).type;
    if (typeof type === 'string' && type) return type;
  }
  return 'unknown';
}

export class HyperliquidInfoClient {
  private readonly infoUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly maxConcurrency: number;
  private readonly maxRetries: number;
  private readonly baseBackoffMs: number;
  private readonly maxBackoffMs: number;
  private readonly minIntervalMs: number;
  private readonly responseCacheTtlMs: number;

  private readonly inFlight = new Map<string, Promise<unknown>>();
  private readonly responseCache = new Map<string, { expiresAtMs: number; value: unknown }>();
  private readonly queue: Array<() => void> = [];
  private activeCount = 0;
  private nextRequestStartAtMs = 0;
  private paceTail: Promise<void> = Promise.resolve();
  private readonly stats = { totalRequests: 0, dedupedRequests: 0, retries: 0, failures: 0, cachedRequests: 0 };

  constructor(options: HyperliquidInfoClientOptions) {
    this.infoUrl = options.infoUrl;
    this.fetchImpl = options.fetchImpl;
    this.maxConcurrency = Math.max(1, options.maxConcurrency ?? 4);
    this.maxRetries = Math.max(0, options.maxRetries ?? 3);
    this.baseBackoffMs = Math.max(50, options.baseBackoffMs ?? 250);
    this.maxBackoffMs = Math.max(this.baseBackoffMs, options.maxBackoffMs ?? 5000);
    this.minIntervalMs = Math.max(0, options.minIntervalMs ?? 500);
    this.responseCacheTtlMs = Math.max(0, options.responseCacheTtlMs ?? 1500);
  }

  async request<T>(payload: unknown): Promise<T> {
    this.stats.totalRequests += 1;
    const dedupeKey = stableStringify(payload);

    const cached = this.responseCache.get(dedupeKey);
    if (cached) {
      if (cached.expiresAtMs > Date.now()) {
        this.stats.cachedRequests += 1;
        return cached.value as T;
      }
      this.responseCache.delete(dedupeKey);
    }

    const existing = this.inFlight.get(dedupeKey);
    if (existing) {
      this.stats.dedupedRequests += 1;
      return existing as Promise<T>;
    }

    const op = payloadOpTag(payload);
    const task = this.runWithSlot<T>(payload, op);
    this.inFlight.set(dedupeKey, task);
    task.finally(() => {
      if (this.inFlight.get(dedupeKey) === task) {
        this.inFlight.delete(dedupeKey);
      }
    }).catch(() => undefined);
    return task;
  }

  getStats(): CoordinatorStats {
    return {
      ...this.stats,
      activeCount: this.activeCount,
      queueLength: this.queue.length,
      inFlightCount: this.inFlight.size,
      responseCacheCount: this.responseCache.size,
      minIntervalMs: this.minIntervalMs,
    };
  }

  private async runWithSlot<T>(payload: unknown, op: string): Promise<T> {
    await this.acquireSlot();
    try {
      return await this.runWithRetries<T>(payload, op);
    } finally {
      this.releaseSlot();
    }
  }

  private acquireSlot(): Promise<void> {
    if (this.activeCount < this.maxConcurrency) {
      this.activeCount += 1;
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      this.queue.push(() => {
        this.activeCount += 1;
        resolve();
      });
    });
  }

  private releaseSlot(): void {
    this.activeCount = Math.max(0, this.activeCount - 1);
    const next = this.queue.shift();
    if (next) next();
  }

  private computeBackoffMs(attempt: number): number {
    const exp = Math.min(this.maxBackoffMs, this.baseBackoffMs * (1 << Math.min(attempt, 8)));
    const jitter = Math.random() * 0.5 * exp;
    return Math.floor(exp + jitter);
  }

  private reserveUpstreamTurn(): Promise<void> {
    if (this.minIntervalMs <= 0) return Promise.resolve();

    const turn = this.paceTail.then(async () => {
      const now = Date.now();
      const waitMs = Math.max(0, this.nextRequestStartAtMs - now);
      if (waitMs > 0) await sleep(waitMs);
      this.nextRequestStartAtMs = Date.now() + this.minIntervalMs;
    });

    this.paceTail = turn.catch(() => undefined);
    return turn;
  }

  private rememberResponse(dedupeKey: string, value: unknown): void {
    if (this.responseCacheTtlMs <= 0) return;
    const now = Date.now();
    this.responseCache.set(dedupeKey, { value, expiresAtMs: now + this.responseCacheTtlMs });

    // Opportunistic pruning keeps this bounded without adding a timer.
    if (this.responseCache.size > 512) {
      for (const [key, cached] of this.responseCache) {
        if (cached.expiresAtMs <= now) this.responseCache.delete(key);
      }
    }
  }

  private async runWithRetries<T>(payload: unknown, op: string): Promise<T> {
    const dedupeKey = stableStringify(payload);
    let attempt = 0;
    while (true) {
      let response: Response;
      try {
        await this.reserveUpstreamTurn();
        response = await this.fetchImpl(this.infoUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        if (attempt >= this.maxRetries) {
          this.stats.failures += 1;
          throw err;
        }
        const backoff = this.computeBackoffMs(attempt);
        this.stats.retries += 1;
        logger.warn(
          { component: 'hyperliquid-info', op, attempt, backoffMs: backoff, err: err instanceof Error ? err.message : err },
          'info request network error; retrying',
        );
        await sleep(backoff);
        attempt += 1;
        continue;
      }

      if (response.ok) {
        const value = (await response.json()) as T;
        this.rememberResponse(dedupeKey, value);
        return value;
      }

      const status = response.status;
      const retriable = status === 429 || status >= 500;
      if (!retriable || attempt >= this.maxRetries) {
        this.stats.failures += 1;
        throw new Error(`Hyperliquid info request failed: ${status}`);
      }
      const retryAfter = parseRetryAfterMs(response.headers.get('retry-after'));
      const backoff = Math.min(this.maxBackoffMs, retryAfter ?? this.computeBackoffMs(attempt));
      this.stats.retries += 1;
      logger.warn(
        { component: 'hyperliquid-info', op, attempt, status, backoffMs: backoff },
        'info request rate-limited or upstream error; retrying',
      );
      try { await response.body?.cancel(); } catch { /* ignore */ }
      await sleep(backoff);
      attempt += 1;
    }
  }
}
