import type { FillEvent } from '../../exchange/types.js';
import type {
  AppSettings,
  BybitConnectionSettings,
  LiveAccountSummary,
  MaskedBybitConnectionSettings,
  ExchangeConnectionStatus,
} from '../../shared/dto.js';
import logger from '../../lib/logger.js';
import { getReadOnlyExchangeConnectorById, getReadOnlyExchangeConnectors } from './registry.js';

function defaultBybitSettings(): BybitConnectionSettings {
  return {
    mode: 'off',
    apiKey: '',
    apiSecret: '',
    accountType: 'UNIFIED',
    categories: ['linear'],
  };
}

function maskSecret(raw: string): string {
  const value = String(raw ?? '').trim();
  if (!value) return '';
  if (value.length <= 8) return '••••';
  return `${value.slice(0, 3)}••••${value.slice(-3)}`;
}

export function getBybitConnectionSettings(settings: AppSettings): BybitConnectionSettings {
  const raw: Partial<BybitConnectionSettings> | undefined =
    settings.externalExchanges?.bybit ??
    (settings as any).readOnlyExchanges?.bybit;
  const fallback = defaultBybitSettings();

  const resolveMode = (m: string | undefined): 'off' | 'read_only' | 'live' =>
    m === 'read_only' ? 'read_only' : m === 'live' ? 'live' : 'off';

  const validCategory = (c: unknown): c is 'linear' | 'inverse' | 'spot' | 'option' =>
    c === 'linear' || c === 'inverse' || c === 'spot' || c === 'option';

  return {
    mode: resolveMode(raw?.mode),
    apiKey: String(raw?.apiKey ?? fallback.apiKey).trim(),
    apiSecret: String(raw?.apiSecret ?? fallback.apiSecret).trim(),
    accountType: raw?.accountType === 'CONTRACT' || raw?.accountType === 'SPOT' ? raw.accountType : 'UNIFIED',
    categories: Array.isArray(raw?.categories) && raw.categories.length > 0
      ? [...new Set(raw.categories.filter(validCategory))]
      : ['linear'],
  };
}

export function getMaskedBybitConnectionSettings(settings: AppSettings): MaskedBybitConnectionSettings {
  const bybit = getBybitConnectionSettings(settings);
  return {
    mode: bybit.mode,
    hasApiKey: bybit.apiKey.length > 0,
    apiKeyMasked: maskSecret(bybit.apiKey),
    hasApiSecret: bybit.apiSecret.length > 0,
    apiSecretMasked: maskSecret(bybit.apiSecret),
    accountType: bybit.accountType,
    categories: bybit.categories,
  };
}

export function applyBybitConnectionPatch(settings: AppSettings, patch: {
  mode?: 'off' | 'read_only' | 'live';
  apiKey?: string;
  apiSecret?: string;
  accountType?: 'UNIFIED' | 'CONTRACT' | 'SPOT';
  categories?: Array<'linear' | 'inverse' | 'spot' | 'option'>;
}): BybitConnectionSettings {
  const current = getBybitConnectionSettings(settings);
  const resolveMode = (m: string | undefined, fallback: 'off' | 'read_only' | 'live'): 'off' | 'read_only' | 'live' =>
    m === 'read_only' ? 'read_only' : m === 'live' ? 'live' : m === 'off' ? 'off' : fallback;
  const next: BybitConnectionSettings = {
    mode: resolveMode(patch.mode, current.mode),
    apiKey: patch.apiKey !== undefined ? String(patch.apiKey).trim() : current.apiKey,
    apiSecret: patch.apiSecret !== undefined ? String(patch.apiSecret).trim() : current.apiSecret,
    accountType: patch.accountType === 'CONTRACT' || patch.accountType === 'SPOT' || patch.accountType === 'UNIFIED'
      ? patch.accountType
      : current.accountType,
    categories: Array.isArray(patch.categories) && patch.categories.length > 0
      ? [...new Set(patch.categories.filter((x): x is 'linear' | 'inverse' | 'spot' | 'option' => x === 'linear' || x === 'inverse' || x === 'spot' || x === 'option'))]
      : current.categories,
  };

  if (next.categories.length === 0) next.categories = ['linear'];

  settings.externalExchanges = settings.externalExchanges ?? { bybit: defaultBybitSettings() };
  settings.externalExchanges.bybit = next;

  return next;
}

export async function getExchangeConnectionStatuses(settings: AppSettings): Promise<ExchangeConnectionStatus[]> {
  const connectors = getReadOnlyExchangeConnectors();

  const jobs = connectors.map(async (connector) => {
    try {
      if (connector.id === 'bybit') {
        return await connector.getStatus(getBybitConnectionSettings(settings));
      }
      return {
        exchange: connector.id,
        mode: 'off' as const,
        configured: false,
        connected: false,
        readOnly: true,
        message: 'unsupported_connector_config',
      };
    } catch (error) {
      logger.warn({ component: 'read-only-exchanges', exchange: connector.id, err: error }, 'status probe failed');
      return {
        exchange: connector.id,
        mode: 'off' as const,
        configured: false,
        connected: false,
        readOnly: true,
        message: error instanceof Error ? error.message : 'status_failed',
      };
    }
  });

  return Promise.all(jobs);
}

export async function testReadOnlyExchangeConnection(settings: AppSettings, exchangeId: string): Promise<ExchangeConnectionStatus> {
  const connector = getReadOnlyExchangeConnectorById(exchangeId);
  if (!connector) {
    return {
      exchange: exchangeId,
      mode: 'off',
      configured: false,
      connected: false,
      readOnly: true,
      message: 'exchange_not_supported',
    };
  }

  if (connector.id === 'bybit') {
    return connector.getStatus(getBybitConnectionSettings(settings));
  }

  return {
    exchange: connector.id,
    mode: 'off',
    configured: false,
    connected: false,
    readOnly: true,
    message: 'exchange_not_supported',
  };
}

export async function collectExternalFills(settings: AppSettings, sinceMs: number): Promise<FillEvent[]> {
  const bybit = getBybitConnectionSettings(settings);
  const connector = getReadOnlyExchangeConnectorById('bybit');
  // Collect fills whenever connected (read_only or live)
  if (!connector || bybit.mode === 'off') return [];

  try {
    return await connector.getRecentFills(bybit, sinceMs);
  } catch (error) {
    logger.warn({ component: 'external-exchanges', exchange: 'bybit', err: error }, 'recent fills fetch failed');
    return [];
  }
}

/** @deprecated use collectExternalFills */
export const collectReadOnlyExternalFills = collectExternalFills;

export async function getExternalAccountSummaries(settings: AppSettings): Promise<Array<{ exchange: string; account: LiveAccountSummary | null }>> {
  const bybit = getBybitConnectionSettings(settings);
  const connector = getReadOnlyExchangeConnectorById('bybit');
  if (!connector || bybit.mode === 'off' || typeof connector.getAccountSnapshot !== 'function') return [];

  try {
    const account = await connector.getAccountSnapshot(bybit);
    return [{ exchange: 'bybit', account }];
  } catch (error) {
    logger.warn({ component: 'external-exchanges', exchange: 'bybit', err: error }, 'account snapshot fetch failed');
    return [];
  }
}

/** @deprecated use getExternalAccountSummaries */
export const getReadOnlyExternalAccountSummaries = getExternalAccountSummaries;
