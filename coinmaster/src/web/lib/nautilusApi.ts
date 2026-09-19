// Generated from runtime/coinmaster/api/app.py OpenAPI surface (P2 snapshot).
export interface StrategyConfiguration { id: string; config_hash: string; created_at: string; config: Record<string, unknown> }
export interface Run { id: string; config_id: string; kind: string; status: string; evidence: string[]; created_at: string; report?: Record<string, unknown> | null }
export interface RuntimeState { status: string; active_usdt: string; reserve_usdt: string; total_usdt: string; warnings: string[] }
export interface Preflight { requested: Record<string, string>; allowed: boolean; im: string | null; mm: string | null; reasons: string[]; cap_label?: string }
// Local operator supplies this ephemeral value; no API secret is bundled into the UI.
const token = window.localStorage.getItem('coinmaster-api-token') ?? '';
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(init?.headers ?? {}) } });
  if (!response.ok) throw new Error((await response.text()) || `API ${response.status}`);
  return response.json() as Promise<T>;
}
export const getDefaultConfiguration = () => request<{ config: Record<string, unknown> }>('/configurations/default');
export const saveConfiguration = (config: Record<string, unknown>) => request<StrategyConfiguration>('/configurations', { method: 'POST', body: JSON.stringify({ config }) });
export const getRuns = () => request<Run[]>('/runs');
export const createRun = (config_id: string, kind: 'fixture' | 'backtest' | 'paper') => request<Run>('/runs', { method: 'POST', body: JSON.stringify({ config_id, kind }) });
export const cancelRun = (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
export const getRuntime = () => request<RuntimeState>('/runtime');
export const getPreflight = () => request<Preflight>('/preflight', { method: 'POST', body: JSON.stringify({ venue: 'bybit', active_usdt: '10000', btc_notional: '90000', sol_notional: '0' }) });
