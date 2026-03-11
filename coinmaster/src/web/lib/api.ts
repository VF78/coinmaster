import type {
  AiMasterQaItem,
  AiMasterSnapshotResponse,
  AnalyticsQualityMetrics,
  AnalyticsWeeklyReportResponse,
  BiasPayload,
  DashboardResponse,
  ExchangeSettingsResponse,
  LiveCandlesResponse,
  LiveHistoryResponse,
  LivePositionLevelsPayload,
  LivePositionLevelsResponse,
  ExchangeConnectionSettingsPayload,
  ExternalExchangesSettingsResponse,
  ExchangeConnectionStatus,
  PostTradeAnalyticsResponse,
  TradingRulesSettings,
  TradingRulesSettingsResponse,
  TradingRulesSymbolsResponse
} from '../../shared/dto.js';

const RISK_BLOCK_MESSAGES: Record<string, string> = {
  leverage_limit_exceeded: 'leverage limit exceeded',
  daily_loss_limit_exceeded: 'daily drawdown limit reached',
  dd_lock_active: 'daily drawdown lock is active',
};

function formatFriendlyApiError(payload: Record<string, unknown>, _status: number): string | null {
  const base = typeof payload.error === 'string' ? payload.error : '';
  const hint = typeof payload.hint === 'string' ? payload.hint : '';

  if (base.startsWith('risk_gate_blocked:')) {
    const rawBlocks = base.slice('risk_gate_blocked:'.length).split(',').map((x) => x.trim()).filter(Boolean);
    const blocks = rawBlocks.length > 0 ? rawBlocks : ['unknown_risk_block'];
    const readable = blocks.map((b) => RISK_BLOCK_MESSAGES[b] ?? b.replaceAll('_', ' '));
    const summary = readable.join(', ');
    return `Confirmation blocked by risk checks: ${summary}. Reduce exposure or adjust Trading Rules, then retry.`;
  }

  if (base === 'pending_not_found') {
    return 'This pending signal no longer exists (already processed or expired).';
  }

  if (base === 'manual_confirmation_required') {
    return 'Manual confirmation is required for this operation.';
  }

  if (base === 'auth_required') {
    return 'Authentication required. Please sign in again.';
  }

  if (base === 'invalid_stop_loss_vs_market') {
    const marketPrice = typeof payload.marketPrice === 'number' ? payload.marketPrice : undefined;
    return `${hint || 'Stop-loss is on the wrong side of current market price.'}${marketPrice !== undefined ? ` (current market: ${marketPrice})` : ''}`;
  }

  if (base === 'invalid_take_profits_vs_entry') {
    const entryPrice = typeof payload.entryPrice === 'number' ? payload.entryPrice : undefined;
    return `${hint || 'Take-profit levels are on the wrong side of entry price.'}${entryPrice !== undefined ? ` (entry: ${entryPrice})` : ''}`;
  }

  if (base === 'symbol_catalog_unavailable') {
    return 'Exchange symbol catalog is temporarily unavailable. Try again in a minute.';
  }

  if (base === 'symbols_not_on_exchange') {
    const invalid = Array.isArray(payload.invalidSymbols)
      ? payload.invalidSymbols.map((x) => String(x).toUpperCase()).filter(Boolean)
      : [];
    if (invalid.length > 0) {
      return `These symbols are not tradable on the connected exchange: ${invalid.join(', ')}.`;
    }
    return 'One or more symbols are not tradable on the connected exchange.';
  }

  return null;
}

export function friendlyErrorMessage(error: unknown, fallback = 'Request failed. Please try again.'): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return fallback;
}

export function friendlyCodeMessage(code: string, fallback = 'Operation failed. Please try again.'): string {
  const trimmed = String(code || '').trim();
  if (!trimmed) return fallback;

  if (trimmed.startsWith('risk_gate_blocked:')) {
    const rawBlocks = trimmed.slice('risk_gate_blocked:'.length).split(',').map((x) => x.trim()).filter(Boolean);
    const blocks = rawBlocks.length > 0 ? rawBlocks : ['unknown_risk_block'];
    const readable = blocks.map((b) => RISK_BLOCK_MESSAGES[b] ?? b.replaceAll('_', ' '));
    return `Blocked by risk checks: ${readable.join(', ')}.`;
  }

  const known: Record<string, string> = {
    pending_not_found: 'This pending signal no longer exists.',
    confirm_failed: 'Could not confirm this signal.',
    reject_failed: 'Could not reject this signal.',
    set_levels_failed: 'Could not apply TP/SL levels.',
    test_failed: 'Could not send test message.',
    telegram_save_failed: 'Could not save Telegram settings.',
    hyperliquid_save_failed: 'Could not save Hyperliquid settings.',
    symbol_catalog_unavailable: 'Exchange symbol catalog is temporarily unavailable.',
    symbols_not_on_exchange: 'Some symbols are not tradable on the connected exchange.',
  };

  return known[trimmed] ?? fallback;
}

async function jsonFetch<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    let detail = '';
    try {
      const payload = await response.clone().json() as Record<string, unknown>;
      const base = typeof payload.error === 'string' ? payload.error : '';
      const hint = typeof payload.hint === 'string' ? payload.hint : '';
      const slErr = typeof (payload.stopLossOrder as { error?: unknown } | undefined)?.error === 'string'
        ? String((payload.stopLossOrder as { error?: string }).error)
        : '';
      const tpErr = typeof (payload.takeProfitOrder as { error?: unknown } | undefined)?.error === 'string'
        ? String((payload.takeProfitOrder as { error?: string }).error)
        : '';

      detail = formatFriendlyApiError(payload, response.status) ?? [base, hint, slErr, tpErr].filter(Boolean).join(' | ');
    } catch {
      // ignore body parse errors
    }

    throw new Error(detail || 'Request failed. Please try again.');
  }

  return response.json() as Promise<T>;
}

export function getDashboard() {
  return jsonFetch<DashboardResponse>('/api/dashboard');
}

export function getLiveHistory() {
  return jsonFetch<LiveHistoryResponse>('/api/live/history');
}

export function getAnalyticsQuality(hours = 24 * 7) {
  const params = new URLSearchParams({ hours: String(hours) });
  return jsonFetch<{ ok: boolean; metrics: AnalyticsQualityMetrics }>(`/api/analytics/quality?${params.toString()}`);
}

export function getPostTradeAnalytics(hours = 24 * 7) {
  const params = new URLSearchParams({ hours: String(hours) });
  return jsonFetch<PostTradeAnalyticsResponse>(`/api/analytics/trades/post-trade?${params.toString()}`);
}

export function getWeeklyAnalyticsReport() {
  return jsonFetch<AnalyticsWeeklyReportResponse>('/api/analytics/weekly/report');
}

export function getAiMasterSnapshot(limit = 50) {
  const params = new URLSearchParams({ limit: String(limit) });
  return jsonFetch<AiMasterSnapshotResponse>(`/api/ai-master/snapshot?${params.toString()}`);
}

export function submitAiMasterQuestion(question: string) {
  return jsonFetch<{ ok: boolean; item: AiMasterQaItem }>('/api/ai-master/qa', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ question })
  });
}

export function getExchangeSettings() {
  return jsonFetch<ExchangeSettingsResponse>('/api/settings/exchange');
}

export interface HyperliquidSettingsPayload {
  accountAddress?: string;
  apiWalletAddress?: string;
  apiPrivateKey?: string;
}

export function saveHyperliquidSettings(payload: HyperliquidSettingsPayload) {
  return jsonFetch<{ ok: boolean; restartScheduled?: boolean; exchange?: ExchangeSettingsResponse['hyperliquid'] }>('/api/settings/exchange/hyperliquid', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export interface TelegramNotifyPayload {
  botToken?: string;
  chatId?: string;
  notifyOpen?: boolean;
  notifyTp?: boolean;
  notifySl?: boolean;
  notifyManualConfirm?: boolean;
  notifyDailyAnalytics?: boolean;
  notifySignalRejected?: boolean;
  notifyOrderRejected?: boolean;
  notifyPositionClosed?: boolean;
}

export function saveTelegramNotify(payload: TelegramNotifyPayload) {
  return jsonFetch<{ ok: boolean; telegramNotify: ExchangeSettingsResponse['telegramNotify'] }>('/api/settings/telegram-notify', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export function sendTelegramNotifyTest() {
  return jsonFetch<{ ok: boolean; error?: string }>('/api/settings/telegram-notify/test', {
    method: 'POST'
  });
}

export function getTelegramNotifyHealth() {
  return jsonFetch<{
    ok: boolean;
    totals: { queued: number; failed: number; all: number };
    oldestQueuedAgeSec: number;
    failedSample: Array<{ id: string; attempts: number; error?: string }>;
    loop: { outboxRunning: boolean; updateRunning: boolean };
    configPresent: boolean;
  }>('/api/settings/telegram-notify/health');
}

export function getTradingRules() {
  return jsonFetch<TradingRulesSettingsResponse>('/api/settings/trading-rules');
}

export function getTradingRuleSymbols() {
  return jsonFetch<TradingRulesSymbolsResponse>('/api/settings/trading-rules/symbols');
}

export function saveTradingRules(rules: TradingRulesSettings) {
  return jsonFetch<TradingRulesSettingsResponse>('/api/settings/trading-rules', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(rules)
  });
}

export function getLiveCandles(symbol = 'BTC', timeframe: '1m' | '5m' | '15m' | '1h' | '4h' = '15m', limit = 200) {
  const params = new URLSearchParams({ symbol, timeframe, limit: String(limit) });
  return jsonFetch<LiveCandlesResponse>(`/api/live/candles?${params.toString()}`);
}

export function applyLivePositionLevels(payload: LivePositionLevelsPayload) {
  return jsonFetch<LivePositionLevelsResponse>('/api/live/position/levels', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export function postBias(payload: BiasPayload) {
  return jsonFetch('/api/bias', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export function confirmPendingConfirmation(id: string) {
  return jsonFetch<{ ok: boolean; error?: string }>(`/api/live/pending-confirmations/${encodeURIComponent(id)}/confirm`, {
    method: 'POST'
  });
}

export function rejectPendingConfirmation(id: string) {
  return jsonFetch<{ ok: boolean; error?: string }>(`/api/live/pending-confirmations/${encodeURIComponent(id)}/reject`, {
    method: 'POST'
  });
}

// ─── Order Confirmation Flow ──────────────────────────────────────────

export interface PlaceOrderPayload {
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  leverage?: number;
  reduceOnly?: boolean;
  clientOrderId?: string;
  confirm?: boolean;
}

export interface PlaceOrderResponse {
  ok: boolean;
  orderId?: string;
  clientOrderId?: string;
  status?: string;
  errorCode?: string;
  error?: string;
  idempotent?: boolean;
}

export interface RiskCheckResponse {
  canTrade: boolean;
  dailyDDPct: number;
  portfolioLeverage: number;
  blocks: string[];
  equityUsd: number;
  baselineEquityUsd: number;
}

export function getRiskCheck() {
  return jsonFetch<RiskCheckResponse>('/api/live/risk-check');
}

export async function placeOrder(payload: PlaceOrderPayload): Promise<PlaceOrderResponse> {
  const response = await fetch('/api/live/order', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await response.json() as PlaceOrderResponse;
  // Return the response even on non-2xx so caller can read errorCode
  return data;
}

// ─── Read-Only Exchanges ─────────────────────────────────────────────

export function getReadOnlyExchangesSettings() {
  return jsonFetch<ExternalExchangesSettingsResponse>('/api/settings/read-only-exchanges');
}

export function saveBybitSettings(payload: ExchangeConnectionSettingsPayload) {
  return jsonFetch<{ ok: boolean; bybit: any }>('/api/settings/read-only-exchanges/bybit', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function testBybitConnection() {
  return jsonFetch<{ ok: boolean; status: ExchangeConnectionStatus }>('/api/settings/read-only-exchanges/bybit/test', {
    method: 'POST',
  });
}
