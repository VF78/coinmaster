import type {
  BiasPayload,
  DashboardResponse,
  ExchangeSettingsResponse,
  LiveCandlesResponse,
  LiveHistoryResponse,
  LivePositionLevelsPayload,
  LivePositionLevelsResponse,
  TradingRulesSettings,
  TradingRulesSettingsResponse
} from '../../shared/dto.js';

const RISK_BLOCK_MESSAGES: Record<string, string> = {
  leverage_limit_exceeded: 'leverage limit exceeded',
  daily_loss_limit_exceeded: 'daily drawdown limit reached',
  dd_lock_active: 'daily drawdown lock is active',
};

function formatFriendlyApiError(payload: Record<string, unknown>, status: number): string | null {
  const base = typeof payload.error === 'string' ? payload.error : '';
  const hint = typeof payload.hint === 'string' ? payload.hint : '';

  if (base.startsWith('risk_gate_blocked:')) {
    const rawBlocks = base.slice('risk_gate_blocked:'.length).split(',').map((x) => x.trim()).filter(Boolean);
    const blocks = rawBlocks.length > 0 ? rawBlocks : ['unknown_risk_block'];
    const readable = blocks.map((b) => RISK_BLOCK_MESSAGES[b] ?? b.replaceAll('_', ' '));
    const summary = readable.join(', ');
    return `Confirmation blocked by risk checks: ${summary}.`;
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

  return null;
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

    throw new Error(detail || `API error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getDashboard() {
  return jsonFetch<DashboardResponse>('/api/dashboard');
}

export function getLiveHistory() {
  return jsonFetch<LiveHistoryResponse>('/api/live/history');
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
