import type { LiveAccountSummary, ExchangeConnectionStatus, ExchangeConnectionMode } from '../../shared/dto.js';
import type { FillEvent } from '../../exchange/types.js';

export type ReadOnlyExchangeId = 'bybit' | string;

export interface ReadOnlyExchangeRuntimeConfig {
  mode: ExchangeConnectionMode;
}

export interface ReadOnlyExchangeConnector<TConfig extends ReadOnlyExchangeRuntimeConfig = ReadOnlyExchangeRuntimeConfig> {
  id: ReadOnlyExchangeId;
  validateConfig(config: TConfig): { ok: true } | { ok: false; error: string };
  getStatus(config: TConfig): Promise<ExchangeConnectionStatus>;
  getRecentFills(config: TConfig, sinceMs: number): Promise<FillEvent[]>;
  getAccountSnapshot?(config: TConfig): Promise<LiveAccountSummary | null>;
}
