import type {
  BiasPayload,
  DashboardResponse,
  ExchangeSettingsResponse,
  LiveCandlesResponse,
  LiveHistoryResponse,
  LivePositionLevelsPayload,
  LivePositionLevelsResponse
} from '../../shared/dto.js';

async function jsonFetch<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
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
