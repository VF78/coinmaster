import type { components } from './nautilus.generated';
export type StrategyConfig = components['schemas']['StrategyConfig'];
export type StrategyConfiguration = components['schemas']['ConfigurationRecord'];
export type Run = components['schemas']['RunRecord'];
export interface RuntimeState { status: string; active_usdt: string; reserve_usdt: string; total_usdt: string; warnings: string[] }
export interface Preflight { requested: Record<string, string>; allowed: boolean; im: string | null; mm: string | null; reasons: string[]; cap_label?: string }
// Local operator supplies this ephemeral value; no API secret is bundled into the UI.
export const setApiToken = (value: string) => window.localStorage.setItem('coinmaster-api-token', value);
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = window.localStorage.getItem('coinmaster-api-token') ?? '';
  const response = await fetch(`/api/v1${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(init?.headers ?? {}) } });
  if (!response.ok) throw new Error((await response.text()) || `API ${response.status}`);
  return response.json() as Promise<T>;
}
export const getDefaultConfiguration = () => request<{ config: StrategyConfig }>('/configurations/default');
export const saveConfiguration = (config: StrategyConfig) => request<StrategyConfiguration>('/configurations', { method: 'POST', body: JSON.stringify({ config }) });
export const getRuns = () => request<Run[]>('/runs');
export const getConfigurations = () => request<StrategyConfiguration[]>('/configurations');
export const createRun = (config_id: string, kind: 'fixture' | 'backtest' | 'paper') => request<Run>('/runs', { method: 'POST', body: JSON.stringify({ config_id, kind }) });
export const cancelRun = (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
export const getRuntime = () => request<RuntimeState>('/runtime');
export const getPreflight = (config: StrategyConfig, beta: string | null, leverage: string | null) => request<Preflight>('/preflight', { method: 'POST', body: JSON.stringify({ venue: config.venue ?? 'bybit', active_usdt: config.initial_total_usdt, btc_notional: (Number(config.initial_total_usdt) * config.btc_notional_multiplier).toFixed(2), beta, selected_leverage: leverage, sol_multipliers: config.sol_size_multipliers_H }) });
