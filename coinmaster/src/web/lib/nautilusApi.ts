import type { components as runtimeComponents } from './runtime.generated';
// The loopback runtime sidecar serves this whole surface; one generated
// contract prevents the SPA from drifting from its deployed API.
export type StrategyConfig = runtimeComponents['schemas']['StrategyConfig'];
export type StrategyConfiguration = runtimeComponents['schemas']['ConfigurationRecord'];
export type Run = runtimeComponents['schemas']['RunRecord'];
export type ResearchCatalogEntry = runtimeComponents['schemas']['ResearchCatalogEntry'];
export type ResearchCatalogDetail = runtimeComponents['schemas']['ResearchCatalogDetail'];
export type RuntimeState = runtimeComponents['schemas']['RuntimeState'];
export type RuntimeEventsResponse = runtimeComponents['schemas']['RuntimeEventsResponse'];
export type RuntimeCommandResponse = runtimeComponents['schemas']['RuntimeCommandResponse'];
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
export const getResearchCatalog = () => request<ResearchCatalogEntry[]>('/research/catalog');
export const getResearchCatalogDetail = (id: string) => request<ResearchCatalogDetail>(`/research/catalog/${encodeURIComponent(id)}`);
export const getConfigurations = () => request<StrategyConfiguration[]>('/configurations');
export const createRun = (config_id: string, kind: 'fixture' | 'backtest' | 'paper' | 'research') => request<Run>('/runs', { method: 'POST', body: JSON.stringify({ config_id, kind }) });
export const cancelRun = (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
export const getRuntime = () => request<RuntimeState>('/runtime');
export const runtimeCommand = (command: 'pause-new-entries' | 'resume-new-entries' | 'flatten-paper') => request<RuntimeCommandResponse>(`/runtime/commands/${command}`, { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() } });
export const getPreflight = (config: StrategyConfig, beta: string | null, leverage: string | null) => request<Preflight>('/preflight', { method: 'POST', body: JSON.stringify({ venue: config.venue ?? 'bybit', active_usdt: config.initial_total_usdt, btc_notional: (Number(config.initial_total_usdt) * config.btc_notional_multiplier).toFixed(2), beta, selected_leverage: leverage, sol_multipliers: config.sol_size_multipliers_H }) });
