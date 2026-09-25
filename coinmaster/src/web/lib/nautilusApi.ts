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
export type HlStagegControls = runtimeComponents['schemas']['HlStagegControls'];
type GuiSession = { username: string; csrf_token: string };
let guiSession: GuiSession | null = null;
export async function getGuiSession(): Promise<GuiSession> {
  const response = await fetch('/api/v1/auth/session', { credentials: 'same-origin', cache: 'no-store' });
  if (response.status === 401) { window.location.assign('/login'); throw new Error('Operator session expired.'); }
  if (!response.ok) throw new Error(`Session API ${response.status}`);
  guiSession = await response.json() as GuiSession;
  return guiSession;
}
export async function logoutGuiSession(): Promise<void> {
  const session = guiSession ?? await getGuiSession();
  const response = await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': session.csrf_token } });
  guiSession = null;
  if (!response.ok) throw new Error(`Logout API ${response.status}`);
  window.location.assign('/login');
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const changing = !!init?.method && !['GET', 'HEAD'].includes(init.method.toUpperCase());
  const csrf = changing ? (guiSession ?? await getGuiSession()).csrf_token : null;
  const response = await fetch(`/api/v1${path}`, { ...init, credentials: 'same-origin', headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...(csrf ? { 'X-CSRF-Token': csrf } : {}), ...(init?.headers ?? {}) } });
  if (response.status === 401) { guiSession = null; window.location.assign('/login'); throw new Error('Operator session expired.'); }
  if (!response.ok) throw new Error((await response.text()) || `API ${response.status}`);
  return response.json() as Promise<T>;
}
export const getDefaultConfiguration = () => request<{ config: StrategyConfig }>('/configurations/default');
export const saveConfiguration = (config: StrategyConfig) => request<StrategyConfiguration>('/configurations', { method: 'POST', body: JSON.stringify({ config }) });
export const getRuns = () => request<Run[]>('/runs');
export const getResearchCatalog = () => request<ResearchCatalogEntry[]>('/research/catalog');
export const getResearchCapabilities = (configId?: string) => request<ResearchCapabilities>(`/research/capabilities${configId ? `?config_id=${encodeURIComponent(configId)}` : ''}`);
export const getResearchCatalogDetail = (id: string) => request<ResearchCatalogDetail>(`/research/catalog/${encodeURIComponent(id)}`);
export const getConfigurations = () => request<StrategyConfiguration[]>('/configurations');
export const createRun = (config_id: string, kind: 'fixture' | 'backtest' | 'paper' | 'research', research_command?: string, optimizer_search?: ResearchCapabilities['optimizer_search']) => request<Run>('/runs', { method: 'POST', body: JSON.stringify({ config_id, kind, ...(research_command ? { research_command } : {}), ...(optimizer_search ? { optimizer_search } : {}) }) });
export const cancelRun = (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
// Never substitute /runtime here: that route is intentionally the separate
// coinmaster-paper worker and has a command relay.
export const getHlStagegProjection = () => request<HlStagegProjection>('/instances/hl-stageg-testnet');
export const getHlStagegStrategy = () => request<HlStagegStrategy>('/instances/hl-stageg-testnet/strategy');
export const getHlStagegControls = () => request<HlStagegControls>('/instances/hl-stageg-testnet/controls');
export const commandHlStagegEntries = (command: 'pause-new-entries' | 'resume-new-entries', idempotencyKey: string) => request<{ instance_id: 'hl-stageg-testnet'; command: 'pause-new-entries' | 'resume-new-entries'; idempotency_key: string; status: 'ACCEPTED' | 'DUPLICATE'; entry_control: 'RUNNING' | 'PAUSED' }>(`/instances/hl-stageg-testnet/controls/${command}`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } });
