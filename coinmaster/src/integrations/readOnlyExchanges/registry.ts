import { BybitReadOnlyConnector } from './bybitReadOnlyConnector.js';
import type { ReadOnlyExchangeConnector } from './types.js';

const CONNECTORS: ReadonlyArray<ReadOnlyExchangeConnector<any>> = [
  new BybitReadOnlyConnector(),
];

export function getReadOnlyExchangeConnectors(): ReadonlyArray<ReadOnlyExchangeConnector<any>> {
  return CONNECTORS;
}

export function getReadOnlyExchangeConnectorById(id: string): ReadOnlyExchangeConnector<any> | null {
  const normalized = String(id ?? '').trim().toLowerCase();
  return CONNECTORS.find((x) => x.id === normalized) ?? null;
}
