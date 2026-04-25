import type {
  AlphaRadarConnectorAuthSession,
  AlphaRadarConnectorRuntime,
  AlphaRadarConnectorRuntimeSummary,
  AlphaRadarConnectorSettings,
  AlphaRadarConnectorState,
  AlphaRadarConnectorType,
  AlphaRadarSourceClass,
  AlphaRadarSourceLayer,
  AlphaRadarSourceHealth,
} from '../shared/dto.js';

const CONNECTOR_TYPES: AlphaRadarConnectorType[] = ['telegram', 'reddit', 'bluesky'];

function normalizeStringList(value: unknown, limit = 50): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value
    .map((item) => String(item ?? '').trim())
    .filter(Boolean)
    .map((item) => item.slice(0, 80)))].slice(0, limit);
}

function normalizeTelegramWatchlist(value: unknown): string[] {
  return [...new Set(normalizeStringList(value)
    .map((item) => item.replace(/^https?:\/\/(?:www\.)?t\.me\/(?:s\/)?/i, '').replace(/^@+/, '').replace(/\/+$/, ''))
    .filter(Boolean))];
}

function normalizeAssetAllowlist(value: unknown): string[] {
  return [...new Set(normalizeStringList(value)
    .map((item) => item.toUpperCase().replace(/[^A-Z0-9:_-]/g, '').slice(0, 24))
    .filter(Boolean))];
}

function clampWeight(value: unknown, fallback = 1): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(0, Math.min(5, Number(n.toFixed(2))));
}

function normalizeSourceLayer(value: unknown, fallback: AlphaRadarSourceLayer): AlphaRadarSourceLayer {
  return value === 'duplicate' || value === 'narrative' || value === 'primary' ? value : fallback;
}

function normalizeSourceClass(value: unknown, fallback: AlphaRadarSourceClass): AlphaRadarSourceClass {
  return value === 'market' || value === 'official' || value === 'newswire' || value === 'macro' || value === 'flow' || value === 'social'
    ? value
    : fallback;
}

function normalizeIsoTimestamp(value: unknown): string | undefined {
  const text = String(value ?? '').trim();
  if (!text) return undefined;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function normalizeConnectorAuthSession(input: unknown): AlphaRadarConnectorAuthSession | undefined {
  const raw = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  if (raw.kind !== 'telegram_qr') return undefined;
  const status = raw.status === 'pending' || raw.status === 'expired' || raw.status === 'cancelled' || raw.status === 'error'
    ? raw.status
    : 'pending';
  return {
    kind: 'telegram_qr',
    status,
    startedAt: normalizeIsoTimestamp(raw.startedAt),
    expiresAt: normalizeIsoTimestamp(raw.expiresAt),
    pollAfterMs: Number.isFinite(Number(raw.pollAfterMs)) ? Math.max(500, Math.min(60_000, Math.round(Number(raw.pollAfterMs)))) : undefined,
    qrUrl: String(raw.qrUrl ?? '').trim().slice(0, 2048) || undefined,
    qrTokenBase64Url: String(raw.qrTokenBase64Url ?? '').trim().slice(0, 2048) || undefined,
    message: String(raw.message ?? '').trim().slice(0, 240) || undefined,
    error: String(raw.error ?? '').trim().slice(0, 240) || undefined,
  };
}

function normalizeConnectorState(input: unknown): AlphaRadarConnectorState {
  const raw = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  const status = raw.status === 'connected' || raw.status === 'needs_auth' || raw.status === 'awaiting_code' || raw.status === 'awaiting_qr' || raw.status === 'error' ? raw.status : 'idle';
  return {
    status,
    configured: raw.configured === true,
    needsAuth: raw.needsAuth === true || status === 'needs_auth' || status === 'awaiting_code' || status === 'awaiting_qr',
    lastSyncAt: normalizeIsoTimestamp(raw.lastSyncAt),
    lastSyncStatus: raw.lastSyncStatus === 'success' || raw.lastSyncStatus === 'error' || raw.lastSyncStatus === 'pending' ? raw.lastSyncStatus : 'pending',
    lastSyncCursor: String(raw.lastSyncCursor ?? '').trim().slice(0, 160) || undefined,
    connectionLabel: String(raw.connectionLabel ?? '').trim().slice(0, 120) || undefined,
    message: String(raw.message ?? '').trim().slice(0, 240) || undefined,
    error: String(raw.error ?? '').trim().slice(0, 240) || undefined,
    authSession: normalizeConnectorAuthSession(raw.authSession),
  };
}

export function defaultAlphaRadarConnectorSettings(): Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings> {
  return {
    telegram: {
      enabled: false,
      sourceLabel: 'Telegram official/newswire watchlists',
      sourceLayer: 'duplicate',
      sourceClass: 'social',
      weight: 0.82,
      watchlist: ['binance_announcements'],
      allowlist: [],
      state: { status: 'idle', configured: false, needsAuth: false, lastSyncStatus: 'pending' },
    },
    reddit: {
      enabled: false,
      sourceLabel: 'Reddit watchlists',
      sourceLayer: 'narrative',
      sourceClass: 'social',
      weight: 0.72,
      watchlist: [],
      allowlist: [],
      state: { status: 'idle', configured: false, needsAuth: false, lastSyncStatus: 'pending' },
    },
    bluesky: {
      enabled: false,
      sourceLabel: 'Bluesky watchlists',
      sourceLayer: 'narrative',
      sourceClass: 'social',
      weight: 0.78,
      watchlist: [],
      allowlist: [],
      state: { status: 'idle', configured: false, needsAuth: false, lastSyncStatus: 'pending' },
    },
  };
}

export function normalizeAlphaRadarConnectors(input: unknown): Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings> {
  const raw = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  const defaults = defaultAlphaRadarConnectorSettings();
  const next = {} as Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings>;

  for (const type of CONNECTOR_TYPES) {
    const row = raw[type] && typeof raw[type] === 'object' ? raw[type] as Record<string, unknown> : {};
    const base = defaults[type];
    const hasWatchlist = Object.prototype.hasOwnProperty.call(row, 'watchlist');
    const watchlist = hasWatchlist
      ? (type === 'telegram' ? normalizeTelegramWatchlist(row.watchlist) : normalizeStringList(row.watchlist))
      : base.watchlist;
    next[type] = {
      enabled: row.enabled === true,
      sourceLabel: String(row.sourceLabel ?? base.sourceLabel).trim().slice(0, 80) || base.sourceLabel,
      sourceLayer: normalizeSourceLayer(row.sourceLayer, base.sourceLayer ?? 'narrative'),
      sourceClass: normalizeSourceClass(row.sourceClass, base.sourceClass ?? 'social'),
      weight: clampWeight(row.weight, base.weight),
      watchlist,
      allowlist: normalizeAssetAllowlist(row.allowlist),
      state: normalizeConnectorState(row.state ?? base.state),
    };
  }

  return next;
}

export function buildAlphaRadarConnectorRuntimes(connectors: Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings>): AlphaRadarConnectorRuntime[] {
  return CONNECTOR_TYPES.map((type) => ({
    type,
    source: `connector:${type}`,
    sourceType: 'social',
    settings: connectors[type],
  }));
}

export function summarizeAlphaRadarConnectorRuntimes(connectors: Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings>): AlphaRadarConnectorRuntimeSummary[] {
  return buildAlphaRadarConnectorRuntimes(connectors).map((runtime) => ({
    type: runtime.type,
    source: runtime.source,
    sourceType: runtime.sourceType,
    sourceLayer: runtime.settings.sourceLayer,
    sourceClass: runtime.settings.sourceClass,
    enabled: runtime.settings.enabled,
    watchlistCount: runtime.settings.watchlist.length,
    allowlistCount: runtime.settings.allowlist.length,
    weight: runtime.settings.weight ?? 1,
    sourceLabel: runtime.settings.sourceLabel,
    state: runtime.settings.state,
  }));
}

export function buildAlphaRadarConnectorHealth(connectors: Record<AlphaRadarConnectorType, AlphaRadarConnectorSettings>): AlphaRadarSourceHealth[] {
  return summarizeAlphaRadarConnectorRuntimes(connectors).map((runtime) => ({
    source: runtime.source,
    kind: 'external',
    sourceType: runtime.sourceType,
    sourceLayer: runtime.sourceLayer,
    sourceClass: runtime.sourceClass,
    sourceWeight: runtime.weight,
    lastObservedAt: runtime.state.lastSyncAt,
    stale: runtime.enabled ? runtime.state.lastSyncStatus !== 'success' : true,
    itemCount: 0,
    status: runtime.enabled ? (runtime.state.lastSyncStatus === 'success' ? 'fresh' : runtime.state.status === 'error' ? 'stale' : 'inactive') : 'inactive',
    details: {
      connectorType: runtime.type,
      sourceLayer: runtime.sourceLayer,
      sourceClass: runtime.sourceClass,
      watchlistCount: runtime.watchlistCount,
      allowlistCount: runtime.allowlistCount,
      weight: runtime.weight,
      sourceLabel: runtime.sourceLabel,
      configured: runtime.state.configured,
      needsAuth: runtime.state.needsAuth,
      connectionStatus: runtime.state.status,
      connectionLabel: runtime.state.connectionLabel,
      message: runtime.state.message,
      lastSyncStatus: runtime.state.lastSyncStatus,
      alertable: runtime.enabled,
      label: runtime.sourceLabel ?? runtime.type,
    },
  }));
}
