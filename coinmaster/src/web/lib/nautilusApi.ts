import type { components as runtimeComponents } from './runtime.generated';
// The loopback runtime sidecar serves this whole surface; one generated
// contract prevents the SPA from drifting from its deployed API.
export type StrategyConfig = runtimeComponents['schemas']['StrategyConfig'];
export type StrategyConfiguration = runtimeComponents['schemas']['ConfigurationRecord'];
export type Run = runtimeComponents['schemas']['RunRecord'];
export type ResearchCatalogEntry = runtimeComponents['schemas']['ResearchCatalogEntry'];
export type ResearchCatalogDetail = runtimeComponents['schemas']['ResearchCatalogDetail'];
export type ResearchCapabilities = runtimeComponents['schemas']['ResearchCapabilities'];
export type HlStagegProjection = runtimeComponents['schemas']['HlStagegProjection'];
export type HlStagegStrategy = runtimeComponents['schemas']['HlStagegStrategy'];
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
export const getResearchCapabilities = () => request<ResearchCapabilities>('/research/capabilities');
export const getResearchCatalogDetail = (id: string) => request<ResearchCatalogDetail>(`/research/catalog/${encodeURIComponent(id)}`);
export const getConfigurations = () => request<StrategyConfiguration[]>('/configurations');
export const createRun = (config_id: string, kind: 'fixture' | 'backtest' | 'paper' | 'research', research_command?: string) => request<Run>('/runs', { method: 'POST', body: JSON.stringify({ config_id, kind, ...(research_command ? { research_command } : {}) }) });
export const cancelRun = (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
// Never substitute /runtime here: that route is intentionally the separate
// coinmaster-paper worker and has a command relay.
export const getHlStagegProjection = () => request<HlStagegProjection>('/instances/hl-stageg-testnet');
export const getHlStagegStrategy = () => request<HlStagegStrategy>('/instances/hl-stageg-testnet/strategy');
