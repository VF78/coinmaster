const ALPHA_RADAR_FETCH_TIMEOUT_MS = Math.max(1_000, Number(process.env.ALPHA_RADAR_FETCH_TIMEOUT_MS || 10_000));
const ALPHA_RADAR_FETCH_MAX_ATTEMPTS = Math.max(1, Number(process.env.ALPHA_RADAR_FETCH_MAX_ATTEMPTS || 3));
const ALPHA_RADAR_FETCH_RETRY_BASE_MS = Math.max(100, Number(process.env.ALPHA_RADAR_FETCH_RETRY_BASE_MS || 300));

export type AlphaRadarFetchFailureKind = 'timeout' | 'rate_limited' | 'upstream' | 'network' | 'unknown';

export interface AlphaRadarFetchFailureSummary {
  kind: AlphaRadarFetchFailureKind;
  retryable: boolean;
  operatorMessage: string;
  code: string;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 409 || status === 425 || status === 429 || status >= 500;
}

function alphaRadarFetchCauseCode(error: unknown): string {
  return typeof error === 'object' && error !== null && 'cause' in error
    ? String((error as { cause?: { code?: unknown } }).cause?.code ?? '')
    : '';
}

export function summarizeAlphaRadarFetchFailure(error: unknown): AlphaRadarFetchFailureSummary {
  const message = error instanceof Error ? error.message : String(error ?? '');
  const causeCode = alphaRadarFetchCauseCode(error);
  const statusMatch = message.match(/^alpha_radar_http_(\d{3})$/);
  const statusCode = statusMatch ? Number(statusMatch[1]) : undefined;
  const lower = message.toLowerCase();

  if (error instanceof Error && (error.name === 'AbortError' || error.name === 'TimeoutError' || causeCode === 'ETIMEDOUT' || causeCode === 'UND_ERR_CONNECT_TIMEOUT' || causeCode === 'UND_ERR_HEADERS_TIMEOUT' || /timeout/.test(lower))) {
    return {
      kind: 'timeout',
      retryable: true,
      code: 'timeout',
      operatorMessage: `upstream timed out after ${ALPHA_RADAR_FETCH_MAX_ATTEMPTS} attempt${ALPHA_RADAR_FETCH_MAX_ATTEMPTS === 1 ? '' : 's'}`,
    };
  }

  if (statusCode === 429 || /rate limit|too many/.test(lower)) {
    return {
      kind: 'rate_limited',
      retryable: true,
      code: 'rate_limited',
      operatorMessage: 'upstream rate limited the collector',
    };
  }

  if (typeof statusCode === 'number' && isRetryableStatus(statusCode)) {
    return {
      kind: 'upstream',
      retryable: true,
      code: `http_${statusCode}`,
      operatorMessage: `upstream returned HTTP ${statusCode}`,
    };
  }

  if (message === 'fetch failed' || causeCode === 'ECONNREFUSED' || causeCode === 'ECONNRESET' || causeCode === 'EAI_AGAIN') {
    return {
      kind: 'network',
      retryable: true,
      code: causeCode ? causeCode.toLowerCase() : 'network',
      operatorMessage: 'network path to upstream failed',
    };
  }

  return {
    kind: 'unknown',
    retryable: false,
    code: 'unknown',
    operatorMessage: message || 'fetch failed',
  };
}

export function isAlphaRadarRetryableFetchError(error: unknown): boolean {
  const summary = summarizeAlphaRadarFetchFailure(error);
  return summary.retryable;
}

export async function alphaRadarFetchWithRetry(url: string, init: RequestInit = {}): Promise<Response> {
  let lastError: unknown;

  for (let attempt = 0; attempt < ALPHA_RADAR_FETCH_MAX_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(url, {
        ...init,
        signal: AbortSignal.timeout(ALPHA_RADAR_FETCH_TIMEOUT_MS),
      });
      if (!response.ok) {
        const error = new Error(`alpha_radar_http_${response.status}`);
        if (attempt >= ALPHA_RADAR_FETCH_MAX_ATTEMPTS - 1 || !isRetryableStatus(response.status)) {
          throw error;
        }
        lastError = error;
      } else {
        return response;
      }
    } catch (error) {
      lastError = error;
      if (attempt >= ALPHA_RADAR_FETCH_MAX_ATTEMPTS - 1 || !isAlphaRadarRetryableFetchError(error)) {
        throw error;
      }
    }

    await sleep(ALPHA_RADAR_FETCH_RETRY_BASE_MS * (attempt + 1));
  }

  throw lastError instanceof Error ? lastError : new Error('alpha_radar_fetch_failed');
}

export async function alphaRadarFetchText(url: string, init: RequestInit = {}): Promise<string> {
  const response = await alphaRadarFetchWithRetry(url, init);
  return response.text();
}

export async function alphaRadarFetchJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await alphaRadarFetchWithRetry(url, init);
  return response.json() as Promise<T>;
}

export async function mapWithConcurrency<T, R>(items: T[], limit: number, worker: (item: T, index: number) => Promise<R>): Promise<R[]> {
  const concurrency = Math.max(1, Math.min(limit, items.length || 1));
  const results = new Array<R>(items.length);
  let cursor = 0;

  async function run(): Promise<void> {
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= items.length) return;
      results[index] = await worker(items[index] as T, index);
    }
  }

  await Promise.all(Array.from({ length: concurrency }, () => run()));
  return results;
}
