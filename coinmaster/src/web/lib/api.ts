import type { BiasPayload, DashboardResponse, HistoryResponse, SimulateTickPayload } from '../../shared/dto.js';

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

export function getHistory() {
  return jsonFetch<HistoryResponse>('/api/history');
}

export function postBias(payload: BiasPayload) {
  return jsonFetch('/api/bias', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export function postTick(payload: SimulateTickPayload) {
  return jsonFetch('/api/simulate/tick', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  });
}
