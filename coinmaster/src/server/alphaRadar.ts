import type {
  AlphaRadarConnectorType,
  EvidenceBundle,
  AlphaRadarMarketSnapshotSettings,
  AlphaRadarMonitoringWatchAsset,
  AlphaRadarPerpContext,
  AlphaRadarFeedConfig,
  AlphaRadarIdea,
  AlphaRadarMonitoringGroup,
  AlphaRadarObservation,
  AlphaRadarObservationKind,
  AlphaRadarSourceClass,
  AlphaRadarSourceLayer,
  AlphaRadarSourceHealth,
  AlphaRadarSettings,
  AlphaRadarSourceType,
  MarketTick,
  Position,
  SignalCandidate,
} from '../shared/dto.js';
import { defaultAlphaRadarConnectorSettings, normalizeAlphaRadarConnectors } from './alphaRadarConnectors.js';
import { extractRssItems as extractRssItemsFallback, extractRssItemsWithFeedparser } from './alphaRadarFeedParser.js';

const DEFAULT_ALPHA_RADAR_MACRO_WATCHLIST: AlphaRadarMonitoringWatchAsset[] = [
  {
    id: 'wti',
    label: 'WTI crude oil',
    symbol: 'WTI',
    provider: 'stooq',
    providerSymbol: 'cl.f',
    realtimeSymbol: 'CL=F',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'macro',
    sourceClass: 'macro',
    weight: 1.04,
    topicTags: ['macro', 'oil', 'monitoring-only'],
  },
  {
    id: 'eurusd',
    label: 'EUR/USD',
    symbol: 'EURUSD',
    provider: 'stooq',
    providerSymbol: 'eurusd',
    realtimeSymbol: 'EURUSD=X',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'macro',
    sourceClass: 'macro',
    weight: 1.04,
    topicTags: ['macro', 'fx', 'monitoring-only'],
  },
  {
    id: 'gold',
    label: 'Gold spot',
    symbol: 'XAUUSD',
    provider: 'stooq',
    providerSymbol: 'xauusd',
    realtimeSymbol: 'GC=F',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'macro',
    sourceClass: 'macro',
    weight: 1.04,
    topicTags: ['macro', 'gold', 'monitoring-only'],
  },
  {
    id: 'dxy',
    label: 'US dollar index proxy',
    symbol: 'DXY',
    provider: 'stooq',
    providerSymbol: 'uup.us',
    realtimeSymbol: 'UUP',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'proxy',
    sourceClass: 'macro',
    weight: 1.03,
    topicTags: ['macro', 'usd', 'proxy', 'monitoring-only'],
  },
  {
    id: 'us10y',
    label: 'US 10Y Treasury proxy',
    symbol: 'US10Y',
    provider: 'stooq',
    providerSymbol: 'ief.us',
    realtimeSymbol: 'IEF',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'proxy',
    sourceClass: 'macro',
    weight: 1.03,
    topicTags: ['macro', 'rates', 'proxy', 'monitoring-only'],
  },
];

const DEFAULT_ALPHA_RADAR_EQUITY_WATCHLIST: AlphaRadarMonitoringWatchAsset[] = [
  {
    id: 'nvda',
    label: 'NVIDIA',
    symbol: 'NVDA',
    provider: 'stooq',
    providerSymbol: 'nvda.us',
    realtimeSymbol: 'NVDA',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.02,
    topicTags: ['equity', 'us-equity', 'semis', 'monitoring-only'],
  },
  {
    id: 'tsla',
    label: 'Tesla',
    symbol: 'TSLA',
    provider: 'stooq',
    providerSymbol: 'tsla.us',
    realtimeSymbol: 'TSLA',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.02,
    topicTags: ['equity', 'us-equity', 'auto', 'monitoring-only'],
  },
  {
    id: 'aapl',
    label: 'Apple',
    symbol: 'AAPL',
    provider: 'stooq',
    providerSymbol: 'aapl.us',
    realtimeSymbol: 'AAPL',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.02,
    topicTags: ['equity', 'us-equity', 'megacap', 'monitoring-only'],
  },
  {
    id: 'msft',
    label: 'Microsoft',
    symbol: 'MSFT',
    provider: 'stooq',
    providerSymbol: 'msft.us',
    realtimeSymbol: 'MSFT',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.02,
    topicTags: ['equity', 'us-equity', 'megacap', 'monitoring-only'],
  },
  {
    id: 'amzn',
    label: 'Amazon',
    symbol: 'AMZN',
    provider: 'stooq',
    providerSymbol: 'amzn.us',
    realtimeSymbol: 'AMZN',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.02,
    topicTags: ['equity', 'us-equity', 'megacap', 'monitoring-only'],
  },
  {
    id: 'meta',
    label: 'Meta',
    symbol: 'META',
    provider: 'stooq',
    providerSymbol: 'meta.us',
    realtimeSymbol: 'META',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.02,
    topicTags: ['equity', 'us-equity', 'megacap', 'monitoring-only'],
  },
  {
    id: 'qqq',
    label: 'Nasdaq 100 ETF',
    symbol: 'QQQ',
    provider: 'stooq',
    providerSymbol: 'qqq.us',
    realtimeSymbol: 'QQQ',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.03,
    topicTags: ['equity', 'us-equity', 'broad-risk', 'monitoring-only'],
  },
  {
    id: 'spy',
    label: 'S&P 500 ETF',
    symbol: 'SPY',
    provider: 'stooq',
    providerSymbol: 'spy.us',
    realtimeSymbol: 'SPY',
    enabled: true,
    monitoringOnly: true,
    monitoringGroup: 'equity',
    sourceClass: 'market',
    weight: 1.03,
    topicTags: ['equity', 'us-equity', 'broad-risk', 'monitoring-only'],
  },
];

export const ALPHA_RADAR_LIMITS = {
  maxObservations: 2000,
  maxSourceChars: 64,
  maxTitleChars: 240,
  maxExcerptChars: 4000,
  maxAssetTags: 12,
  maxAssetTagChars: 24,
  maxTopicTags: 12,
  maxTopicTagChars: 24,
  maxCycleIdChars: 128,
  maxRunIdChars: 128,
  maxTimeframeChars: 12,
} as const;

type AlphaRadarCollectedItem = {
  title: string;
  excerpt: string;
  link?: string;
  observedAt?: string;
  sourceName?: string;
  author?: string;
  externalId?: string;
  canonicalUrl?: string;
  rawPayloadRef?: string;
  assetTags?: string[];
  topicTags?: string[];
  metadata?: Record<string, unknown>;
};

export function normalizeFeedCollectorType(value: unknown): NonNullable<AlphaRadarFeedConfig['collectorType']> {
  if (value === 'rsshub' || value === 'gdelt' || value === 'json') return value;
  return 'rss';
}

function normalizeFeedParser(value: unknown): AlphaRadarFeedConfig['parser'] | undefined {
  return value === 'statuspage_incidents'
    || value === 'statuspage_maintenances'
    || value === 'binance_cms_articles'
    || value === 'tree_news'
    ? value
    : undefined;
}

export function alphaRadarFeedSourceType(collectorType: AlphaRadarFeedConfig['collectorType']): AlphaRadarSourceType {
  if (collectorType === 'gdelt') return 'news';
  if (collectorType === 'rsshub' || collectorType === 'json') return 'direct';
  return 'rss';
}

export const DEFAULT_ALPHA_RADAR_SETTINGS: AlphaRadarSettings = {
  enabled: true,
  manualQueueOnly: true,
  autoConfirmOrders: false,
  allowHypothesisEntries: true,
  maxIdeasPerCycle: 2,
  minIdeaScore: 0.58,
  collectorLookbackHours: 24,
  refreshIntervalMinutes: 30,
  marketSnapshot: {
    macroWatchlist: DEFAULT_ALPHA_RADAR_MACRO_WATCHLIST.map((item) => ({
      ...item,
      topicTags: [...(item.topicTags ?? [])],
    })),
    equityWatchlist: DEFAULT_ALPHA_RADAR_EQUITY_WATCHLIST.map((item) => ({
      ...item,
      topicTags: [...(item.topicTags ?? [])],
    })),
  },
  connectors: defaultAlphaRadarConnectorSettings(),
  feeds: [
    {
      id: 'coindesk',
      label: 'CoinDesk Headlines',
      url: 'https://www.coindesk.com/arc/outboundfeeds/rss/',
      enabled: true,
      source: 'coindesk_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 0.96,
    },
    {
      id: 'cointelegraph',
      label: 'Cointelegraph Headlines',
      url: 'https://cointelegraph.com/rss',
      enabled: true,
      source: 'cointelegraph_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 0.88,
    },
    {
      id: 'theblock',
      label: 'The Block Headlines',
      url: 'https://www.theblock.co/rss.xml',
      enabled: true,
      source: 'theblock_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 0.97,
    },
    {
      id: 'decrypt',
      label: 'Decrypt Headlines',
      url: 'https://decrypt.co/feed',
      enabled: true,
      source: 'decrypt_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 0.9,
    },
    {
      id: 'thedefiant',
      label: 'The Defiant Headlines',
      url: 'https://thedefiant.io/feed',
      enabled: true,
      source: 'thedefiant_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 0.92,
      topicTags: ['defi'],
    },
    {
      id: 'coinbase-exchange-status',
      label: 'Coinbase Exchange Status',
      url: 'https://status.exchange.coinbase.com/history.rss',
      enabled: true,
      source: 'coinbase_exchange_status_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 1.24,
      topicTags: ['exchange', 'status', 'operations'],
    },
    {
      id: 'kraken-status',
      label: 'Kraken Status',
      url: 'https://status.kraken.com/history.rss',
      enabled: true,
      source: 'kraken_status_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 1.18,
      topicTags: ['exchange', 'status', 'operations'],
    },
    {
      id: 'binance-announcements',
      label: 'Binance Announcements API',
      url: 'https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?catalogId=48&type=1&pageNo=1&pageSize=20',
      enabled: true,
      source: 'binance_announcements_api',
      collectorType: 'json',
      parser: 'binance_cms_articles',
      sourceLayer: 'primary',
      weight: 1.22,
      topicTags: ['listing', 'exchange'],
    },
    {
      id: 'coinbase-blog',
      label: 'Coinbase Blog via RSSHub',
      url: 'https://rsshub.app/coinbase/blog',
      enabled: true,
      source: 'coinbase_blog_rsshub',
      collectorType: 'rsshub',
      sourceLayer: 'primary',
      weight: 0.98,
      topicTags: ['exchange'],
    },
    {
      id: 'kraken-blog',
      label: 'Kraken Blog',
      url: 'https://blog.kraken.com/feed',
      enabled: true,
      source: 'kraken_blog_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 0.9,
      topicTags: ['exchange'],
    },
    {
      id: 'coinbase-exchange-incidents',
      label: 'Coinbase Exchange Unresolved Incidents',
      url: 'https://status.exchange.coinbase.com/api/v2/incidents/unresolved.json',
      enabled: true,
      source: 'coinbase_exchange_incidents_api',
      collectorType: 'json',
      parser: 'statuspage_incidents',
      sourceLayer: 'primary',
      weight: 1.28,
      topicTags: ['exchange', 'status', 'operations'],
    },
    {
      id: 'coinbase-exchange-maintenances',
      label: 'Coinbase Exchange Active Maintenances',
      url: 'https://status.exchange.coinbase.com/api/v2/scheduled-maintenances/active.json',
      enabled: true,
      source: 'coinbase_exchange_maintenances_api',
      collectorType: 'json',
      parser: 'statuspage_maintenances',
      sourceLayer: 'primary',
      weight: 1.2,
      topicTags: ['exchange', 'status', 'maintenance'],
    },
    {
      id: 'sec-press',
      label: 'SEC Press Releases',
      url: 'https://www.sec.gov/news/pressreleases.rss',
      enabled: true,
      source: 'sec_press_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 1.16,
      topicTags: ['regulation'],
    },
    {
      id: 'cftc-press',
      label: 'CFTC Press Releases',
      url: 'https://www.cftc.gov/RSS/RSSGP/rssgp.xml',
      enabled: true,
      source: 'cftc_press_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      weight: 1.12,
      topicTags: ['regulation'],
    },
    {
      id: 'fed-press',
      label: 'Fed Press Releases',
      url: 'https://www.federalreserve.gov/feeds/press_all.xml',
      enabled: true,
      source: 'fed_press_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      sourceClass: 'official',
      weight: 1.2,
      assetTags: ['DXY', 'US10Y', 'XAUUSD', 'EURUSD'],
      topicTags: ['macro', 'fed', 'rates', 'usd'],
    },
    {
      id: 'ecb-press',
      label: 'ECB Press Releases',
      url: 'https://www.ecb.europa.eu/rss/press.html',
      enabled: true,
      source: 'ecb_press_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      sourceClass: 'official',
      weight: 1.16,
      assetTags: ['EURUSD', 'DXY', 'XAUUSD'],
      topicTags: ['macro', 'ecb', 'rates', 'euro'],
    },
    {
      id: 'eia-today-in-energy',
      label: 'EIA Today in Energy',
      url: 'https://www.eia.gov/rss/todayinenergy.xml',
      enabled: true,
      source: 'eia_today_in_energy_rss',
      collectorType: 'rss',
      sourceLayer: 'primary',
      sourceClass: 'official',
      weight: 1.08,
      assetTags: ['WTI'],
      topicTags: ['macro', 'eia', 'energy', 'oil'],
    },
    {
      id: 'opec-oil-wire',
      label: 'OPEC / OPEC+ oil wire',
      url: 'https://api.gdeltproject.org/api/v2/doc/doc?query=(opec%20OR%20%22opec%2B%22)%20(oil%20OR%20crude%20OR%20production%20OR%20output)%20-sourcelang:Russian&mode=artlist&maxrecords=10&format=json&sort=datedesc',
      enabled: false,
      source: 'opec_oil_wire_gdelt',
      collectorType: 'gdelt',
      sourceLayer: 'duplicate',
      sourceClass: 'macro',
      weight: 0.78,
      assetTags: ['WTI'],
      topicTags: ['macro', 'opec', 'oil'],
    },
    {
      id: 'tree-news',
      label: 'Tree News Live Feed',
      url: 'https://news.treeofalpha.com/api/news',
      enabled: true,
      source: 'tree_news_api',
      collectorType: 'json',
      parser: 'tree_news',
      sourceLayer: 'duplicate',
      weight: 0.9,
      topicTags: ['realtime', 'catalyst'],
    },
    {
      id: 'gdelt-crypto',
      label: 'GDELT Crypto Pilot',
      url: 'https://api.gdeltproject.org/api/v2/doc/doc?query=(bitcoin%20OR%20btc%20OR%20ethereum%20OR%20eth%20OR%20solana%20OR%20sol%20OR%20hyperliquid%20OR%20hype%20OR%20crypto%20OR%20cryptocurrency)%20(theme:CRISISLEX_T11_UPGRADE%20OR%20theme:WB_696_PUBLIC_SECTOR_MANAGEMENT_REGULATION%20OR%20theme:TAX_FNCACT_EXCHANGE%20OR%20theme:ECON_STOCKMARKET%20OR%20theme:ECON_BANKRUPTCY)%20-sourcelang:Russian&mode=artlist&maxrecords=25&format=json&sort=datedesc',
      enabled: true,
      source: 'gdelt_crypto_pilot',
      collectorType: 'gdelt',
      sourceLayer: 'duplicate',
      weight: 0.72,
      topicTags: ['macro', 'confirmation'],
    },
  ],
};

function trimString(value: unknown, max: number): string | undefined {
  const text = String(value ?? '').trim();
  if (!text) return undefined;
  return text.slice(0, max);
}

function clamp01(value: unknown): number | undefined {
  const n = Number(value);
  if (!Number.isFinite(n)) return undefined;
  return Math.max(0, Math.min(1, Number(n.toFixed(4))));
}

function clampSourceWeight(value: unknown, fallback = 1): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(0.1, Math.min(5, Number(n.toFixed(2))));
}

function normalizeSourceClass(value: unknown, fallback: AlphaRadarSourceClass): AlphaRadarSourceClass {
  return value === 'market' || value === 'official' || value === 'newswire' || value === 'macro' || value === 'flow' || value === 'social'
    ? value
    : fallback;
}

function clampSignedUnit(value: unknown): number | undefined {
  const n = Number(value);
  if (!Number.isFinite(n)) return undefined;
  return Math.max(-1, Math.min(1, Number(n.toFixed(4))));
}

function normalizeTimestamp(value: unknown, fallback: string): string {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : fallback;
}

function normalizeTimestampOrUndefined(value: unknown): string | undefined {
  const text = String(value ?? '').trim();
  if (!text) return undefined;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function normalizeEpochMs(value: unknown): string | undefined {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return undefined;
  return new Date(n).toISOString();
}

export function normalizeAssetTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const next = value
    .map((item) => String(item ?? '').trim().toUpperCase())
    .filter(Boolean)
    .map((item) => item.replace(/[^A-Z0-9:_-]/g, '').slice(0, ALPHA_RADAR_LIMITS.maxAssetTagChars));
  return [...new Set(next)].slice(0, ALPHA_RADAR_LIMITS.maxAssetTags);
}

export function normalizeTopicTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const next = value
    .map((item) => String(item ?? '').trim().toLowerCase())
    .filter(Boolean)
    .map((item) => item.replace(/[^a-z0-9:_-]/g, '').slice(0, ALPHA_RADAR_LIMITS.maxTopicTagChars));
  return [...new Set(next)].slice(0, ALPHA_RADAR_LIMITS.maxTopicTags);
}

function normalizeFeedConfig(input: unknown, index: number, fallback?: AlphaRadarFeedConfig): AlphaRadarFeedConfig | null {
  const row = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  const url = String(row.url ?? fallback?.url ?? '').trim();
  const source = String(row.source ?? fallback?.source ?? '').trim().slice(0, ALPHA_RADAR_LIMITS.maxSourceChars);
  if (!url || !source) return null;
  const collectorType = normalizeFeedCollectorType(row.collectorType ?? fallback?.collectorType);
  const sourceType = alphaRadarFeedSourceType(collectorType);
  const topicTags = normalizeTopicTags(row.topicTags ?? fallback?.topicTags);
  const sourceLayer = normalizeSourceLayer(row.sourceLayer ?? fallback?.sourceLayer, sourceType);
  const sourceClass = normalizeSourceClass(
    row.sourceClass ?? fallback?.sourceClass,
    deriveAlphaRadarSourceClass({ source, sourceType, sourceLayer, title: String(row.label ?? fallback?.label ?? ''), topicTags })
  );

  return {
    id: trimString(row.id, 48) ?? fallback?.id ?? `feed-${index + 1}`,
    label: trimString(row.label, 64) ?? fallback?.label ?? `Feed ${index + 1}`,
    url,
    enabled: row.enabled !== false,
    source,
    collectorType,
    parser: normalizeFeedParser(row.parser ?? fallback?.parser),
    sourceLayer,
    sourceClass,
    weight: clampSourceWeight(row.weight ?? fallback?.weight, fallback?.weight ?? 1),
    assetTags: normalizeAssetTags(row.assetTags ?? fallback?.assetTags),
    topicTags,
  };
}

function normalizeMonitoringGroup(value: unknown, fallback: AlphaRadarMonitoringGroup): AlphaRadarMonitoringGroup {
  return value === 'macro' || value === 'proxy' || value === 'equity'
    ? value
    : fallback;
}

function normalizeMonitoringWatchAsset(
  input: unknown,
  index: number,
  fallback?: AlphaRadarMonitoringWatchAsset,
  idPrefix = 'monitor',
): AlphaRadarMonitoringWatchAsset | null {
  const row = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  const symbol = trimString(row.symbol, 24)?.toUpperCase()
    ?? trimString(fallback?.symbol, 24)?.toUpperCase();
  const providerSymbol = trimString(row.providerSymbol, 32)?.toLowerCase()
    ?? trimString(fallback?.providerSymbol, 32)?.toLowerCase();
  const realtimeSymbol = trimString(row.realtimeSymbol, 32)?.toUpperCase()
    ?? trimString(fallback?.realtimeSymbol, 32)?.toUpperCase();
  if (!symbol || !providerSymbol) return null;
  const monitoringGroup = normalizeMonitoringGroup(row.monitoringGroup ?? fallback?.monitoringGroup, fallback?.monitoringGroup ?? 'macro');
  const defaultSourceClass = monitoringGroup === 'equity' ? 'market' : 'macro';

  return {
    id: trimString(row.id, 48) ?? fallback?.id ?? `${idPrefix}-${index + 1}`,
    label: trimString(row.label, 64) ?? fallback?.label ?? symbol,
    symbol,
    provider: 'stooq',
    providerSymbol,
    realtimeSymbol,
    enabled: row.enabled !== false,
    monitoringOnly: row.monitoringOnly !== false,
    monitoringGroup,
    sourceClass: normalizeSourceClass(row.sourceClass ?? fallback?.sourceClass, fallback?.sourceClass ?? defaultSourceClass),
    weight: clampSourceWeight(row.weight ?? fallback?.weight, fallback?.weight ?? 1.04),
    topicTags: normalizeTopicTags(row.topicTags ?? fallback?.topicTags),
  };
}

function normalizeMonitoringWatchlist(
  rows: unknown[],
  defaults: AlphaRadarMonitoringWatchAsset[],
  idPrefix: string,
): AlphaRadarMonitoringWatchAsset[] {
  const watchlist = rows
    .map((row, index) => normalizeMonitoringWatchAsset(row, index, defaults[index], idPrefix))
    .filter((item): item is AlphaRadarMonitoringWatchAsset => Boolean(item));

  if (watchlist.length === 0) {
    return defaults.map((item) => ({ ...item, topicTags: [...(item.topicTags ?? [])] }));
  }

  const byId = new Map(watchlist.map((item) => [item.id, item] as const));
  const mergedDefaults = defaults.map((item, index) => {
    const merged = { ...item, ...(byId.get(item.id) ?? {}) };
    return normalizeMonitoringWatchAsset(merged, index, item, idPrefix) ?? item;
  });
  const extras = watchlist.filter((item) => !defaults.some((base) => base.id === item.id));

  return [...mergedDefaults, ...extras].map((item) => ({
    ...item,
    topicTags: [...(item.topicTags ?? [])],
  }));
}

function normalizeAlphaRadarMarketSnapshotSettings(input: unknown): AlphaRadarMarketSnapshotSettings {
  const raw = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  return {
    macroWatchlist: normalizeMonitoringWatchlist(
      Array.isArray(raw.macroWatchlist) ? raw.macroWatchlist : [],
      DEFAULT_ALPHA_RADAR_MACRO_WATCHLIST,
      'macro',
    ),
    equityWatchlist: normalizeMonitoringWatchlist(
      Array.isArray(raw.equityWatchlist) ? raw.equityWatchlist : [],
      DEFAULT_ALPHA_RADAR_EQUITY_WATCHLIST,
      'equity',
    ),
  };
}

function normalizeEnabledMonitoringWatchlist(items: AlphaRadarMonitoringWatchAsset[]): AlphaRadarMonitoringWatchAsset[] {
  const seen = new Set<string>();
  return items
    .filter((item) => item.enabled !== false)
    .map((item) => ({
      ...item,
      symbol: String(item.symbol ?? '').trim().toUpperCase(),
      providerSymbol: String(item.providerSymbol ?? '').trim().toLowerCase(),
      realtimeSymbol: String(item.realtimeSymbol ?? '').trim().toUpperCase() || undefined,
      monitoringGroup: normalizeMonitoringGroup(item.monitoringGroup, 'macro'),
      topicTags: [...(item.topicTags ?? [])],
    }))
    .filter((item) => item.symbol && item.providerSymbol)
    .filter((item) => {
      const key = `${item.symbol}|${item.providerSymbol}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

export function enabledAlphaRadarMacroWatchlist(settings: AlphaRadarSettings): AlphaRadarMonitoringWatchAsset[] {
  return normalizeEnabledMonitoringWatchlist(settings.marketSnapshot?.macroWatchlist ?? []);
}

export function enabledAlphaRadarEquityWatchlist(settings: AlphaRadarSettings): AlphaRadarMonitoringWatchAsset[] {
  return normalizeEnabledMonitoringWatchlist(settings.marketSnapshot?.equityWatchlist ?? []);
}

export function enabledAlphaRadarMonitoringWatchlist(settings: AlphaRadarSettings): AlphaRadarMonitoringWatchAsset[] {
  return [
    ...enabledAlphaRadarMacroWatchlist(settings),
    ...enabledAlphaRadarEquityWatchlist(settings),
  ];
}

function migrateLegacyDefaultFeed(defaultFeed: AlphaRadarFeedConfig, raw: Record<string, unknown>): Record<string, unknown> {
  const legacyUrl = String(raw.url ?? '').trim().toLowerCase();
  const legacySource = String(raw.source ?? '').trim().toLowerCase();
  const legacyCollectorType = normalizeFeedCollectorType(raw.collectorType);
  const shouldUpgradeBinance = defaultFeed.id === 'binance-announcements'
    && (legacyCollectorType === 'rsshub' || legacyUrl.includes('rsshub.app/binance') || legacySource === 'binance_announcements_rsshub');
  const shouldUpgradeSec = defaultFeed.id === 'sec-press'
    && (legacyCollectorType === 'rsshub' || legacyUrl.includes('rsshub.app/sec/press') || legacySource === 'sec_press_rsshub');
  const shouldDisableOpecByDefault = defaultFeed.id === 'opec-oil-wire' && typeof raw.enabled !== 'boolean';
  const looksLikeLegacyOpecDefault = defaultFeed.id === 'opec-oil-wire'
    && raw.enabled === true
    && String(raw.source ?? '') === 'opec_oil_wire_gdelt'
    && normalizeFeedCollectorType(raw.collectorType) === 'gdelt'
    && String(raw.sourceLayer ?? '') === 'duplicate'
    && String(raw.sourceClass ?? '') === 'macro'
    && Number(raw.weight) === 0.78
    && JSON.stringify(normalizeAssetTags(raw.assetTags)) === JSON.stringify(defaultFeed.assetTags)
    && JSON.stringify(normalizeTopicTags(raw.topicTags)) === JSON.stringify(defaultFeed.topicTags);

  const migrated: Record<string, unknown> = shouldUpgradeBinance || shouldUpgradeSec
    ? {
      ...raw,
      label: defaultFeed.label,
      url: defaultFeed.url,
      source: defaultFeed.source,
      collectorType: defaultFeed.collectorType,
      parser: defaultFeed.parser,
      sourceLayer: raw.sourceLayer ?? defaultFeed.sourceLayer,
    }
    : { ...raw };

  if (shouldDisableOpecByDefault || looksLikeLegacyOpecDefault) {
    migrated.enabled = false;
  }

  return migrated;
}

function normalizeKind(value: unknown): AlphaRadarObservationKind {
  return value === 'market' ? 'market' : 'external';
}

function normalizeSourceType(value: unknown, kind: AlphaRadarObservationKind): AlphaRadarSourceType {
  if (value === 'rss' || value === 'news' || value === 'market' || value === 'manual' || value === 'direct' || value === 'social') return value;
  return kind === 'market' ? 'market' : 'news';
}

function normalizeSourceLayer(value: unknown, sourceType: AlphaRadarSourceType): AlphaRadarSourceLayer {
  if (value === 'primary' || value === 'duplicate' || value === 'narrative') return value;
  if (sourceType === 'social') return 'narrative';
  return 'primary';
}

export function deriveAlphaRadarSourceClass(input: {
  source?: string;
  sourceType: AlphaRadarSourceType;
  sourceLayer?: AlphaRadarSourceLayer;
  title?: string;
  excerpt?: string;
  topicTags?: string[];
}): AlphaRadarSourceClass {
  if (input.sourceType === 'market') return 'market';
  if (input.sourceType === 'social') return 'social';

  const text = [input.source, input.title, input.excerpt, ...(input.topicTags ?? [])]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  if (/(status|incident|maintenance|announcements?|listing|sec|cftc|coinbase|kraken|binance|official|blog)/.test(text)) {
    return 'official';
  }
  if (/(gdelt|macro|regulation|etf|fed|fomc|ecb|eia|opec|cpi|pce|treasury|rates|oil|gold)/.test(text)) {
    return 'macro';
  }
  if (input.sourceType === 'direct' || /(tree[_ -]?news|realtime|flow|positioning|funding|open interest|volume)/.test(text)) {
    return 'flow';
  }
  return 'newswire';
}

const ASSET_PATTERNS: Array<{ tag: string; pattern: RegExp }> = [
  { tag: 'BTC', pattern: /\b(?:btc|bitcoin)\b/i },
  { tag: 'ETH', pattern: /\b(?:eth|ether|ethereum)\b/i },
  { tag: 'WTI', pattern: /\b(?:wti|crude oil|brent|oil prices?|crude prices?|nymex crude|west texas intermediate)\b/i },
  { tag: 'XAUUSD', pattern: /\b(?:xauusd|gold|bullion|spot gold|comex gold)\b/i },
  { tag: 'EURUSD', pattern: /\b(?:eurusd|eur\/usd|euro-dollar|euro\s+vs\s+dollar|euro(?:\s+zone)?(?:\s+vs\s+|\s+against\s+)?(?:u\.s\.\s+)?dollar)\b/i },
  { tag: 'HYPE', pattern: /\b(?:hype|hyperliquid)\b/i },
  { tag: 'SOL', pattern: /\b(?:sol|solana)\b/i },
  { tag: 'ZEC', pattern: /\b(?:zec|zcash)\b/i },
  { tag: 'XRP', pattern: /\b(?:xrp|ripple)\b/i },
  { tag: 'BNB', pattern: /\b(?:bnb|binance coin)\b/i },
  { tag: 'AVAX', pattern: /\b(?:avax|avalanche)\b/i },
  { tag: 'LINK', pattern: /\b(?:link|chainlink)\b/i },
  { tag: 'AAVE', pattern: /\b(?:aave)\b/i },
  { tag: 'DOGE', pattern: /\b(?:doge|dogecoin)\b/i },
];

const TOPIC_PATTERNS: Array<{ tag: string; pattern: RegExp }> = [
  { tag: 'etf', pattern: /\betf\b|exchange traded fund/i },
  { tag: 'listing', pattern: /\blist(?:ing|ed)?\b|launchpool|perp listing/i },
  { tag: 'regulation', pattern: /\bsec\b|cftc|regulat|lawsuit|court|compliance/i },
  { tag: 'security', pattern: /hack|exploit|breach|drain|attack/i },
  { tag: 'fund-flows', pattern: /inflow|outflow|netflow|treasury|buyback/i },
  { tag: 'derivatives', pattern: /futures|perp|perpetual|options|funding/i },
  { tag: 'upgrade', pattern: /upgrade|fork|mainnet|roadmap|validator|governance/i },
  { tag: 'partnership', pattern: /partner|integrat|collaboration/i },
  { tag: 'stablecoin', pattern: /stablecoin|usdt|usdc/i },
  { tag: 'status', pattern: /status page|status update|operational issue|service degradation/i },
  { tag: 'incident', pattern: /incident|outage|degraded|investigating/i },
  { tag: 'maintenance', pattern: /maintenance|scheduled upgrade|maintenance window/i },
  { tag: 'price-action', pattern: /surge|dump|breakout|sell-off|rally|volatility/i },
  { tag: 'macro-shock', pattern: /safe haven|flight to safety|oil shock|supply shock|production cut|output cut|pipeline|strait of hormuz|fed|ecb|cpi|pce|nfp|nonfarm payrolls|rate cut|rate hike|tariff/i },
 ];

type MacroShockMatch = {
  symbol: 'WTI' | 'XAUUSD' | 'EURUSD';
  catalyst: 'oil_supply_shock' | 'safe_haven' | 'usd_eur_macro_shock';
  direction: 'long' | 'short';
  minSources: 2 | 3;
};

const MACRO_SHOCK_RULES: Array<{ match: RegExp; result: MacroShockMatch }> = [
  {
    match: /\b(?:opec|opec\+|oil|crude|brent|wti|output|production|supply|pipeline|refinery|strait of hormuz|sanction|disruption)\b/i,
    result: { symbol: 'WTI', catalyst: 'oil_supply_shock', direction: 'long', minSources: 2 },
  },
  {
    match: /\b(?:gold|bullion|safe haven|flight to safety|geopolitical|middle east|war risk|treasury yields? fall|risk aversion)\b/i,
    result: { symbol: 'XAUUSD', catalyst: 'safe_haven', direction: 'long', minSources: 2 },
  },
  {
    match: /\b(?:fed|ecb|euro|eurusd|eur\/usd|u\.s\. dollar|usd|cpi|pce|nfp|nonfarm payrolls|payrolls|rate cut|rate hike|tariff|inflation|jobs report)\b/i,
    result: { symbol: 'EURUSD', catalyst: 'usd_eur_macro_shock', direction: 'long', minSources: 3 },
  },
];

function detectMacroShock(input: { title?: string; excerpt?: string; assetTags?: string[]; topicTags?: string[]; sourceClass?: AlphaRadarSourceClass }): MacroShockMatch | null {
  const text = [input.title, input.excerpt, ...(input.assetTags ?? []), ...(input.topicTags ?? [])].filter(Boolean).join(' ').toLowerCase();
  const sourceClass = input.sourceClass ?? 'newswire';
  for (const rule of MACRO_SHOCK_RULES) {
    if (!rule.match.test(text)) continue;
    if (rule.result.symbol === 'WTI' && !/\b(?:opec|opec\+|oil|crude|supply|production|output|pipeline|strait of hormuz|refinery|sanction|disruption)\b/i.test(text)) continue;
    if (rule.result.symbol === 'XAUUSD' && !/\b(?:gold|bullion|safe haven|flight to safety|geopolitical|risk aversion|war risk)\b/i.test(text)) continue;
    if (rule.result.symbol === 'EURUSD' && !/\b(?:fed|ecb|eurusd|eur\/usd|euro|usd|cpi|pce|nfp|payrolls|rate cut|rate hike|tariff|inflation|jobs report)\b/i.test(text)) continue;
    return {
      ...rule.result,
      minSources: sourceClass === 'official' ? 2 : rule.result.minSources,
    };
  }
  return null;
}

const HIGH_SIGNAL_TOPIC_TAGS = new Set([
  'listing',
  'regulation',
  'security',
  'etf',
  'fund-flows',
  'derivatives',
  'upgrade',
  'stablecoin',
  'status',
  'incident',
  'maintenance',
  'operations',
]);

const LOW_SIGNAL_PROMO_PATTERN = /\b(?:learn(?:\s+and|\s*&)?\s+earn|giveaway|treasure hunt|register now|sign up|bonus|reward(?:s)?|quest|campaign|join us|watch now|tune in|ama|ask me anything|livestream|webinar|newsletter|daily recap|weekly recap|market wrap|market watch)\b/i;
const LOW_SIGNAL_SOCIAL_PATTERN = /\b(?:gm|good morning|community update|thread\b|podcast\b|episode\b)\b/i;

export function extractRadarTags(input: { title?: unknown; excerpt?: unknown; source?: unknown; seedAssetTags?: unknown; seedTopicTags?: unknown }): { assetTags: string[]; topicTags: string[] } {
  const haystack = [input.title, input.excerpt, input.source].map((item) => String(item ?? '')).join(' ');
  const assetTags = new Set(normalizeAssetTags(input.seedAssetTags));
  const topicTags = new Set(normalizeTopicTags(input.seedTopicTags));

  for (const entry of ASSET_PATTERNS) {
    if (entry.pattern.test(haystack)) assetTags.add(entry.tag);
  }
  for (const entry of TOPIC_PATTERNS) {
    if (entry.pattern.test(haystack)) topicTags.add(entry.tag);
  }

  if (assetTags.size === 0 && /\bcrypto|bitcoin|ethereum|token|exchange\b/i.test(haystack)) {
    topicTags.add('crypto-market');
  }

  return {
    assetTags: [...assetTags].slice(0, ALPHA_RADAR_LIMITS.maxAssetTags),
    topicTags: [...topicTags].slice(0, ALPHA_RADAR_LIMITS.maxTopicTags),
  };
}

export function shouldFilterAlphaRadarObservation(observation: Pick<AlphaRadarObservation, 'title' | 'excerpt' | 'assetTags' | 'topicTags' | 'sourceType' | 'sourceLayer'>): boolean {
  const text = `${observation.title} ${observation.excerpt}`.replace(/\s+/g, ' ').trim();
  if (!text) return true;

  const assetTags = normalizeAssetTags(observation.assetTags);
  const topicTags = normalizeTopicTags(observation.topicTags);
  const hasHighSignalTopic = topicTags.some((tag) => HIGH_SIGNAL_TOPIC_TAGS.has(tag));
  const isSocialish = observation.sourceType === 'social' || observation.sourceLayer === 'narrative';

  if (LOW_SIGNAL_PROMO_PATTERN.test(text) && !hasHighSignalTopic) return true;
  if (LOW_SIGNAL_SOCIAL_PATTERN.test(text) && !assetTags.length && !hasHighSignalTopic) return true;
  if (isSocialish && !assetTags.length && !hasHighSignalTopic) return true;
  return false;
}

function computeRank(input: {
  kind: AlphaRadarObservationKind;
  sentimentScore?: number;
  noveltyScore?: number;
  urgencyScore?: number;
  marketAlignmentScore?: number;
  baseRank?: number;
}): number {
  const sentimentComponent = Math.abs(input.sentimentScore ?? 0) * 0.2;
  const noveltyComponent = (input.noveltyScore ?? 0.5) * 0.35;
  const urgencyComponent = (input.urgencyScore ?? 0.5) * 0.3;
  const marketComponent = (input.marketAlignmentScore ?? (input.kind === 'market' ? 0.7 : 0.4)) * 0.15;
  const rank = input.baseRank ?? sentimentComponent + noveltyComponent + urgencyComponent + marketComponent;
  return Number(Math.max(0, Math.min(1, rank)).toFixed(4));
}

export function normalizeAlphaRadarSettings(input: unknown): AlphaRadarSettings {
  const raw = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  const autoConfirmOrders = typeof raw.autoConfirmOrders === 'boolean'
    ? raw.autoConfirmOrders
    : raw.manualQueueOnly === false
      ? true
      : DEFAULT_ALPHA_RADAR_SETTINGS.autoConfirmOrders;
  const feedsRaw = Array.isArray(raw.feeds) ? raw.feeds : [];
  const rawFeedRows = feedsRaw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object');
  const rawById = new Map<string, Record<string, unknown>>();
  const rawCustom: Record<string, unknown>[] = [];

  for (const row of rawFeedRows) {
    const id = trimString(row.id, 48);
    if (id) rawById.set(id, row);
    else rawCustom.push(row);
  }

  const feeds: AlphaRadarFeedConfig[] = [];
  for (const [index, defaultFeed] of DEFAULT_ALPHA_RADAR_SETTINGS.feeds.entries()) {
    const rawFeed = rawById.get(defaultFeed.id);
    rawById.delete(defaultFeed.id);
    const merged = rawFeed ? { ...defaultFeed, ...migrateLegacyDefaultFeed(defaultFeed, rawFeed) } : defaultFeed;
    const normalized = normalizeFeedConfig(merged, index, defaultFeed);
    if (normalized) feeds.push(normalized);
  }

  for (const row of [...rawById.values(), ...rawCustom]) {
    const normalized = normalizeFeedConfig(row, feeds.length);
    if (normalized) feeds.push(normalized);
  }

  return {
    enabled: raw.enabled !== false,
    manualQueueOnly: !autoConfirmOrders,
    autoConfirmOrders,
    allowHypothesisEntries: raw.allowHypothesisEntries !== false,
    maxIdeasPerCycle: Math.max(1, Math.min(2, Math.round(Number(raw.maxIdeasPerCycle) || DEFAULT_ALPHA_RADAR_SETTINGS.maxIdeasPerCycle))),
    minIdeaScore: Math.max(0.3, Math.min(0.95, Number(raw.minIdeaScore) || DEFAULT_ALPHA_RADAR_SETTINGS.minIdeaScore)),
    collectorLookbackHours: Math.max(1, Math.min(168, Math.round(Number(raw.collectorLookbackHours) || DEFAULT_ALPHA_RADAR_SETTINGS.collectorLookbackHours))),
    refreshIntervalMinutes: Math.max(5, Math.min(240, Math.round(Number(raw.refreshIntervalMinutes) || DEFAULT_ALPHA_RADAR_SETTINGS.refreshIntervalMinutes))),
    marketSnapshot: normalizeAlphaRadarMarketSnapshotSettings(raw.marketSnapshot ?? DEFAULT_ALPHA_RADAR_SETTINGS.marketSnapshot),
    connectors: normalizeAlphaRadarConnectors(raw.connectors),
    feeds: feeds.length > 0 ? feeds : DEFAULT_ALPHA_RADAR_SETTINGS.feeds.map((feed) => ({ ...feed })),
  };
}

export function pruneAlphaRadarObservations(observations: AlphaRadarObservation[]): void {
  if (observations.length > ALPHA_RADAR_LIMITS.maxObservations) {
    observations.splice(0, observations.length - ALPHA_RADAR_LIMITS.maxObservations);
  }
}

export function buildAlphaRadarObservation(input: {
  id: string;
  kind?: unknown;
  source?: unknown;
  sourceType?: unknown;
  sourceLayer?: unknown;
  sourceClass?: unknown;
  sourceWeight?: unknown;
  title?: unknown;
  excerpt?: unknown;
  assetTags?: unknown;
  topicTags?: unknown;
  sentimentScore?: unknown;
  noveltyScore?: unknown;
  urgencyScore?: unknown;
  marketAlignmentScore?: unknown;
  rank?: unknown;
  observedAt?: unknown;
  cycleId?: unknown;
  runId?: unknown;
  timeframe?: unknown;
  provenance?: unknown;
  metadata?: unknown;
  createdAt: string;
}): { ok: true; observation: AlphaRadarObservation } | { ok: false; error: string } {
  const title = trimString(input.title, ALPHA_RADAR_LIMITS.maxTitleChars);
  if (!title) return { ok: false, error: 'title_required' };

  const excerpt = trimString(input.excerpt, ALPHA_RADAR_LIMITS.maxExcerptChars);
  if (!excerpt) return { ok: false, error: 'excerpt_required' };

  const source = trimString(input.source, ALPHA_RADAR_LIMITS.maxSourceChars) ?? 'manual';
  const kind = normalizeKind(input.kind);
  const sourceType = normalizeSourceType(input.sourceType, kind);
  const sourceLayer = normalizeSourceLayer(input.sourceLayer, sourceType);
  const tags = extractRadarTags({ title, excerpt, source, seedAssetTags: input.assetTags, seedTopicTags: input.topicTags });
  const sourceClass = normalizeSourceClass(
    input.sourceClass,
    deriveAlphaRadarSourceClass({ source, sourceType, sourceLayer, title, excerpt, topicTags: tags.topicTags })
  );
  const sourceWeight = clampSourceWeight(input.sourceWeight, kind === 'market' ? 1.2 : 1);
  const macroShock = detectMacroShock({ title, excerpt, assetTags: tags.assetTags, topicTags: tags.topicTags, sourceClass });
  const assetTags = normalizeAssetTags(macroShock ? [...tags.assetTags, macroShock.symbol] : tags.assetTags);
  const topicTags = normalizeTopicTags(macroShock ? [...tags.topicTags, 'macro-shock', macroShock.catalyst] : tags.topicTags);
  const sentimentScore = clampSignedUnit(input.sentimentScore);
  const noveltyScore = clamp01(input.noveltyScore);
  const urgencyScore = clamp01(input.urgencyScore);
  const marketAlignmentScore = clamp01(input.marketAlignmentScore);
  const baseRank = clamp01(input.rank);

  return {
    ok: true,
    observation: {
      id: input.id,
      kind,
      source,
      sourceType,
      sourceLayer,
      sourceClass,
      sourceWeight,
      title,
      excerpt,
      assetTags,
      topicTags,
      sentimentScore,
      noveltyScore,
      urgencyScore,
      marketAlignmentScore,
      rank: computeRank({ kind, sentimentScore, noveltyScore, urgencyScore, marketAlignmentScore, baseRank }),
      observedAt: normalizeTimestamp(input.observedAt, input.createdAt),
      cycleId: trimString(input.cycleId, ALPHA_RADAR_LIMITS.maxCycleIdChars),
      runId: trimString(input.runId, ALPHA_RADAR_LIMITS.maxRunIdChars),
      timeframe: trimString(input.timeframe, ALPHA_RADAR_LIMITS.maxTimeframeChars),
      provenance: input.provenance && typeof input.provenance === 'object' ? input.provenance as Record<string, unknown> : undefined,
      metadata: {
        ...(input.metadata && typeof input.metadata === 'object' ? input.metadata as Record<string, unknown> : {}),
        ...(macroShock ? {
          macroShock: {
            symbol: macroShock.symbol,
            catalyst: macroShock.catalyst,
            direction: macroShock.direction,
            minSources: macroShock.minSources,
            fastTrack: true,
          },
        } : {}),
      },
      createdAt: input.createdAt,
    },
  };
}

function observationMacroShock(observation: AlphaRadarObservation): { symbol: string; catalyst: string; direction: 'long' | 'short'; minSources: number; fastTrack: boolean } | null {
  const macroShock = (observation.metadata as { macroShock?: Record<string, unknown> } | undefined)?.macroShock;
  if (!macroShock) return null;
  const symbol = String(macroShock.symbol ?? '').trim().toUpperCase();
  const catalyst = String(macroShock.catalyst ?? '').trim();
  const direction = macroShock.direction === 'short' ? 'short' : 'long';
  const minSources = Math.max(2, Math.min(3, Number(macroShock.minSources) || 2));
  return symbol && catalyst ? { symbol, catalyst, direction, minSources, fastTrack: macroShock.fastTrack === true } : null;
}

function normalizeAlphaRadarSymbol(value: unknown): string {
  const raw = String(value ?? '').trim();
  if (!raw) return '';

  if (raw.includes(':')) {
    const [namespaceRaw, symbolRaw] = raw.split(':', 2);
    const namespace = String(namespaceRaw ?? '').trim().toLowerCase();
    const symbol = String(symbolRaw ?? '').trim().toUpperCase();
    return namespace && symbol ? `${namespace}:${symbol}` : '';
  }

  return raw.toUpperCase();
}

function alphaRadarSymbolAliases(symbol: string): string[] {
  const normalized = normalizeAlphaRadarSymbol(symbol);
  if (!normalized) return [];

  const core = normalized.includes(':') ? normalizeAlphaRadarSymbol(normalized.split(':', 2)[1]) : normalized;
  const aliases = new Set<string>([normalized, core]);

  if (core === 'GOLD' || core === 'XAUUSD' || core === 'XAU') {
    aliases.add('XAUUSD');
    aliases.add('GOLD');
    aliases.add('XAU');
  }

  if (core === 'BRENTOIL' || core === 'BRENT' || core === 'WTI' || core === 'CL' || core === 'OIL') {
    aliases.add('WTI');
    aliases.add('BRENTOIL');
    aliases.add('BRENT');
    aliases.add('OIL');
    aliases.add('CL');
  }

  if (core === 'EUR' || core === 'EURUSD') {
    aliases.add('EUR');
    aliases.add('EURUSD');
  }

  return [...aliases].map((item) => normalizeAlphaRadarSymbol(item)).filter(Boolean);
}

const MACRO_SHOCK_CANDIDATE_SYMBOLS = new Set(['WTI', 'XAUUSD', 'XAU', 'GOLD', 'EURUSD', 'EUR']);

function isMacroShockCandidateSymbol(symbol: string): boolean {
  const normalized = normalizeAlphaRadarSymbol(symbol);
  if (!normalized) return false;
  const core = normalized.includes(':') ? normalizeAlphaRadarSymbol(normalized.split(':', 2)[1]) : normalized;
  return MACRO_SHOCK_CANDIDATE_SYMBOLS.has(core);
}

function observationSupportsSymbolConfirmation(observation: AlphaRadarObservation, symbol: string): boolean {
  const aliases = new Set(alphaRadarSymbolAliases(symbol));
  if (!observation.assetTags.some((tag) => aliases.has(normalizeAlphaRadarSymbol(tag)))) return false;
  if (!isMacroShockCandidateSymbol(symbol)) return true;
  if (observation.sourceClass === 'market') return true;
  const macroShock = observationMacroShock(observation);
  return Boolean(macroShock && aliases.has(normalizeAlphaRadarSymbol(macroShock.symbol)));
}

function pctChange(current: number, previous: number): number | undefined {
  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous === 0) return undefined;
  return Number((((current - previous) / previous) * 100).toFixed(4));
}

export function buildAlphaRadarMarketObservationDedupeKey(observation: Pick<AlphaRadarObservation, 'source' | 'observedAt' | 'timeframe' | 'metadata'>): string {
  const metadata = observation.metadata as { providerBarKey?: unknown } | undefined;
  const providerBarKey = String(metadata?.providerBarKey ?? '').trim();
  const timeframe = trimString(observation.timeframe, ALPHA_RADAR_LIMITS.maxTimeframeChars) ?? 'tick';
  return providerBarKey
    ? `market|${observation.source}|${timeframe}|${providerBarKey}`
    : `market|${observation.source}|${timeframe}|${observation.observedAt}`;
}

export function buildMarketObservationCandidates(input: {
  nowIso: string;
  cycleId?: string;
  runId?: string;
  ticks: MarketTick[];
  positions: Position[];
  tradableSymbols: string[];
  profilesBySymbol?: Record<string, {
    label?: string;
    source?: string;
    sourceClass?: AlphaRadarSourceClass;
    sourceWeight?: number;
    topicTags?: string[];
    assetTags?: string[];
    timeframe?: string;
    monitoringOnly?: boolean;
    sourceLabel?: string;
    publisher?: string;
    metadata?: Record<string, unknown>;
  }>;
}): Array<Omit<AlphaRadarObservation, 'id' | 'createdAt'>> {
  const bySymbol = new Map<string, MarketTick[]>();
  for (const tick of input.ticks) {
    const symbol = String(tick.symbol ?? '').trim().toUpperCase();
    if (!symbol) continue;
    const list = bySymbol.get(symbol) ?? [];
    list.push(tick);
    bySymbol.set(symbol, list);
  }

  const openSymbols = new Set(
    input.positions.filter((position) => position.status === 'open').map((position) => String(position.symbol ?? '').trim().toUpperCase())
  );

  const items: Array<Omit<AlphaRadarObservation, 'id' | 'createdAt'>> = [];

  for (const symbol of [...new Set(input.tradableSymbols.map((item) => String(item ?? '').trim().toUpperCase()).filter(Boolean))]) {
    const ticks = (bySymbol.get(symbol) ?? []).slice().sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    const latest = ticks.at(-1);
    const previous = ticks.length > 1 ? ticks.at(-2) : undefined;
    if (!latest) continue;
    const profile = input.profilesBySymbol?.[symbol];
    const changePct = previous ? pctChange(latest.price, previous.price) : undefined;
    const absChangePct = Math.abs(changePct ?? 0);
    const sentimentScore = changePct === undefined ? 0 : Math.max(-1, Math.min(1, changePct / 5));
    const noveltyScore = previous ? Math.max(0.05, Math.min(1, absChangePct / 3)) : 0.1;
    const urgencyScore = previous ? Math.max(0.05, Math.min(1, absChangePct / 2)) : 0.1;
    const monitoringOnly = profile?.monitoringOnly === true;
    const marketAlignmentScore = monitoringOnly ? 0.45 : openSymbols.has(symbol) ? 0.9 : 0.6;
    const direction = changePct === undefined ? 'flat' : changePct > 0 ? 'up' : changePct < 0 ? 'down' : 'flat';
    const label = trimString(profile?.label, 64) ?? symbol;
    const source = trimString(profile?.source, ALPHA_RADAR_LIMITS.maxSourceChars) ?? 'coinmaster_market_ticks';
    const topicTags = normalizeTopicTags([
      'price-action',
      ...(profile?.topicTags ?? []),
      ...(openSymbols.has(symbol) && !monitoringOnly ? ['portfolio'] : []),
    ]);
    const assetTags = normalizeAssetTags(profile?.assetTags ?? [symbol]);
    const sourceClass = normalizeSourceClass(profile?.sourceClass, monitoringOnly ? 'macro' : 'market');
    const sourceWeight = clampSourceWeight(profile?.sourceWeight, monitoringOnly ? 1.04 : 1.2);
    const timeframe = trimString(profile?.timeframe, ALPHA_RADAR_LIMITS.maxTimeframeChars) ?? 'tick';
    const publisher = trimString(profile?.publisher, 80) ?? (monitoringOnly ? 'stooq' : 'coinmaster');
    const sourceLabel = trimString(profile?.sourceLabel, 80) ?? (monitoringOnly ? `${label} monitor-only snapshot` : 'Live market snapshot');

    items.push({
      kind: 'market',
      source,
      title: `${label} ${direction} on latest ${monitoringOnly ? 'monitoring snapshot' : 'market snapshot'}`,
      excerpt: [
        `Last price ${latest.price}`,
        changePct === undefined ? 'change unavailable' : `vs previous tick ${changePct}%`,
        monitoringOnly
          ? 'monitoring only, excluded from live tradable universe'
          : openSymbols.has(symbol)
            ? 'symbol already in current book'
            : 'symbol not currently open',
      ].join(', '),
      sourceType: 'market',
      sourceLayer: 'primary',
      sourceClass,
      sourceWeight,
      assetTags,
      topicTags,
      sentimentScore: Number(sentimentScore.toFixed(4)),
      noveltyScore: Number(noveltyScore.toFixed(4)),
      urgencyScore: Number(urgencyScore.toFixed(4)),
      marketAlignmentScore: Number(marketAlignmentScore.toFixed(4)),
      rank: computeRank({ kind: 'market', sentimentScore, noveltyScore, urgencyScore, marketAlignmentScore }),
      observedAt: latest.timestamp,
      cycleId: input.cycleId,
      runId: input.runId,
      timeframe,
      provenance: {
        publisher,
        sourceLabel,
        publishedAt: latest.timestamp,
        ingestedAt: input.nowIso,
      },
      metadata: {
        sourceLayer: 'primary',
        sourceWeight,
        confirmedBySources: [source],
        confirmedBySourceTypes: ['market'],
        confirmedByLayers: ['primary'],
        confirmedBySourceClasses: [sourceClass],
        confirmationCount: 1,
        crossTypeConfirmationCount: 1,
        crossLayerConfirmationCount: 1,
        providerBarKey: String((profile?.metadata as { providerBarKey?: unknown } | undefined)?.providerBarKey ?? latest.timestamp),
        price: latest.price,
        previousPrice: previous?.price,
        changePct,
        inOpenPositions: openSymbols.has(symbol),
        monitoringOnly,
        ...(profile?.metadata ?? {}),
      },
    });
  }

  return items;
}

export function extractRssItems(xml: string): AlphaRadarCollectedItem[] {
  return extractRssItemsFallback(xml);
}

export async function extractRssItemsWithProvenance(xml: string): Promise<AlphaRadarCollectedItem[]> {
  return extractRssItemsWithFeedparser(xml);
}

export function buildAlphaRadarClusterKey(title: string, url?: string): string {
  const cleanedTitle = String(title ?? '')
    .toLowerCase()
    .replace(/&amp;/g, 'and')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\b(breaking|exclusive|live|update|watch)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const normalizedUrl = String(url ?? '')
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .replace(/[?#].*$/, '')
    .trim();
  return (cleanedTitle || normalizedUrl || 'untitled').slice(0, 180);
}

export function extractGdeltItems(payload: unknown): AlphaRadarCollectedItem[] {
  const root = payload && typeof payload === 'object' ? payload as {
    articles?: unknown[];
    results?: unknown[];
    features?: Array<{ properties?: Record<string, unknown> }>;
  } : {};
  const rows = Array.isArray(root.articles)
    ? root.articles
    : Array.isArray(root.results)
      ? root.results
      : Array.isArray(root.features)
        ? root.features.map((item) => item?.properties ?? {})
        : [];

  return rows.slice(0, 30)
    .map((entry) => {
      const row = entry && typeof entry === 'object' ? entry as Record<string, unknown> : {};
      const title = trimString(row.title ?? row.name, ALPHA_RADAR_LIMITS.maxTitleChars) ?? '';
      const excerpt = trimString(row.excerpt ?? row.snippet ?? row.description ?? row.seendate ?? row.socialimage ?? row.domain ?? row.sourceCountry, 240)
        ?? trimString(row.title ?? row.name, 240)
        ?? '';
      return {
        title,
        excerpt,
        link: trimString(row.url ?? row.sourceurl ?? row.shareurl, 500),
        observedAt: normalizeTimestampOrUndefined(row.seendate ?? row.date ?? row.datetime ?? row.publishedAt),
        sourceName: trimString(row.domain ?? row.sourcecountry ?? row.sourceCountry ?? row.source, 80),
      } satisfies AlphaRadarCollectedItem;
    })
    .filter((row) => row.title && row.excerpt);
}

function extractUppercaseAssetCandidates(text: string): string[] {
  const directMatches = [...text.matchAll(/\b([A-Z0-9]{2,12})(?:USDT|USDC|FDUSD|BTC|ETH)\b/g)].map((match) => match[1]);
  const standaloneMatches = [...text.matchAll(/\b(?:BTC|ETH|SOL|XRP|DOGE|BNB|ADA|AVAX|LINK|MATIC|ARB|OP|SUI|WLD|HYPE)\b/g)].map((match) => match[0]);
  return normalizeAssetTags([...directMatches, ...standaloneMatches]);
}

function parseStatuspageItems(payload: unknown, kind: 'incident' | 'maintenance'): AlphaRadarCollectedItem[] {
  const raw = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {};
  const page = raw.page && typeof raw.page === 'object' ? raw.page as Record<string, unknown> : {};
  const rows = Array.isArray(kind === 'incident' ? raw.incidents : raw.scheduled_maintenances)
    ? (kind === 'incident' ? raw.incidents : raw.scheduled_maintenances) as Array<Record<string, unknown>>
    : [];

  return rows.slice(0, 20).map((row) => {
    const updates = Array.isArray(row.incident_updates) ? row.incident_updates as Array<Record<string, unknown>> : [];
    const latestUpdate = updates
      .slice()
      .sort((a, b) => String(b.updated_at ?? '').localeCompare(String(a.updated_at ?? '')))[0];
    const title = trimString(row.name, ALPHA_RADAR_LIMITS.maxTitleChars) ?? '';
    const status = trimString(row.status, 40);
    const impact = trimString(row.impact, 40);
    const excerpt = trimString([
      kind === 'maintenance' ? 'Scheduled maintenance' : 'Exchange incident',
      status ? `status ${status}` : undefined,
      impact ? `impact ${impact}` : undefined,
      trimString(latestUpdate?.body ?? row.shortlink, 600),
    ].filter(Boolean).join(', '), ALPHA_RADAR_LIMITS.maxExcerptChars) ?? title;
    return {
      title,
      excerpt,
      link: trimString(row.shortlink, 500)
        ?? (trimString(row.id, 120) ? `https://status.exchange.coinbase.com/incidents/${trimString(row.id, 120)}` : trimString(page.url, 500)),
      observedAt: normalizeTimestampOrUndefined(latestUpdate?.updated_at ?? row.updated_at ?? row.created_at),
      sourceName: trimString(page.name ?? 'Coinbase Exchange Status', 80),
      topicTags: kind === 'maintenance' ? ['maintenance', 'operations'] : ['incident', 'operations'],
      metadata: {
        status,
        impact,
        updateCount: updates.length,
        statuspageKind: kind,
      },
    } satisfies AlphaRadarCollectedItem;
  }).filter((row) => row.title && row.excerpt);
}

function extractBinanceCmsItems(payload: unknown): AlphaRadarCollectedItem[] {
  const raw = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {};
  const data = raw.data && typeof raw.data === 'object' ? raw.data as Record<string, unknown> : {};
  const catalogs = Array.isArray(data.catalogs) ? data.catalogs as Array<Record<string, unknown>> : [];
  const rows = catalogs.length > 0
    ? catalogs.flatMap((catalog) => Array.isArray(catalog.articles) ? catalog.articles as Array<Record<string, unknown>> : [])
    : Array.isArray(data.articles) ? data.articles as Array<Record<string, unknown>> : [];

  return rows.slice(0, 30).map((row) => {
    const title = trimString(row.title, ALPHA_RADAR_LIMITS.maxTitleChars) ?? '';
    const articleCode = trimString(row.code, 120);
    return {
      title,
      excerpt: trimString(title, ALPHA_RADAR_LIMITS.maxExcerptChars) ?? title,
      link: articleCode ? `https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode=${encodeURIComponent(articleCode)}` : undefined,
      observedAt: normalizeEpochMs(row.releaseDate),
      sourceName: 'Binance Announcements',
      assetTags: extractUppercaseAssetCandidates(title),
      metadata: {
        articleId: row.id,
        articleCode,
        releaseDate: row.releaseDate,
      },
    } satisfies AlphaRadarCollectedItem;
  }).filter((row) => row.title && row.excerpt);
}

function isLikelyCryptoRelevant(text: string): boolean {
  return /\b(?:bitcoin|btc|ethereum|eth|solana|sol|hyperliquid|hype|xrp|doge|bnb|coinbase|binance|crypto|token|stablecoin|sec|cftc|etf|listing|launchpool|perp|futures|funding|wallet|exchange|defi)\b/i.test(text);
}

function extractTreeNewsItems(payload: unknown): AlphaRadarCollectedItem[] {
  const rows = Array.isArray(payload) ? payload as Array<Record<string, unknown>> : [];
  return rows.slice(0, 50).map((row) => {
    const title = trimString(row.title ?? row.en, ALPHA_RADAR_LIMITS.maxTitleChars) ?? '';
    const excerpt = trimString(row.en ?? row.title, ALPHA_RADAR_LIMITS.maxExcerptChars) ?? title;
    const suggestions = Array.isArray(row.suggestions) ? row.suggestions as Array<Record<string, unknown>> : [];
    const suggestionCoins = suggestions.map((item) => item.coin).filter(Boolean);
    const symbols = Array.isArray(row.symbols) ? row.symbols : [];
    const assetTags = normalizeAssetTags([
      ...suggestionCoins,
      ...symbols.map((item) => String(item).split(/[_/-]/)[0]),
      ...extractUppercaseAssetCandidates(title),
    ]);
    const sourceToken = String(row.source ?? '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return {
      title,
      excerpt,
      link: trimString(row.url, 500),
      observedAt: normalizeEpochMs(row.time) ?? normalizeTimestampOrUndefined(row.time),
      sourceName: trimString(row.sourceName ?? row.source, 80),
      assetTags,
      topicTags: normalizeTopicTags(['tree-news', sourceToken || undefined].filter(Boolean)),
      metadata: {
        source: trimString(row.source, 80),
        sourceName: trimString(row.sourceName, 80),
        itemId: trimString(row._id, 120),
        suggestions: suggestions.length,
        likes: Number(row.likes ?? 0),
        dislikes: Number(row.dislikes ?? 0),
      },
    } satisfies AlphaRadarCollectedItem;
  }).filter((row) => row.title && row.excerpt && ((row.assetTags?.length ?? 0) > 0 || isLikelyCryptoRelevant(`${row.title} ${row.excerpt}`)));
}

export function extractJsonFeedItems(payload: unknown, parser: AlphaRadarFeedConfig['parser']): AlphaRadarCollectedItem[] {
  switch (parser) {
    case 'statuspage_incidents':
      return parseStatuspageItems(payload, 'incident');
    case 'statuspage_maintenances':
      return parseStatuspageItems(payload, 'maintenance');
    case 'binance_cms_articles':
      return extractBinanceCmsItems(payload);
    case 'tree_news':
      return extractTreeNewsItems(payload);
    default:
      return [];
  }
}

function uniqueStringArray(value: unknown, fallback: string[] = []): string[] {
  const base = Array.isArray(value) ? value : fallback;
  return [...new Set(base.map((item) => String(item ?? '').trim()).filter(Boolean))];
}

function observationConfirmedSources(observation: AlphaRadarObservation): string[] {
  return uniqueStringArray((observation.metadata as { confirmedBySources?: unknown } | undefined)?.confirmedBySources, [observation.source]);
}

function observationConfirmedSourceTypes(observation: AlphaRadarObservation): AlphaRadarSourceType[] {
  const raw = uniqueStringArray((observation.metadata as { confirmedBySourceTypes?: unknown } | undefined)?.confirmedBySourceTypes, [observation.sourceType]);
  return raw.filter((item): item is AlphaRadarSourceType => ['rss', 'news', 'market', 'manual', 'direct', 'social'].includes(item));
}

function observationConfirmedLayers(observation: AlphaRadarObservation): AlphaRadarSourceLayer[] {
  const raw = uniqueStringArray((observation.metadata as { confirmedByLayers?: unknown } | undefined)?.confirmedByLayers, [observation.sourceLayer ?? 'primary']);
  return raw.filter((item): item is AlphaRadarSourceLayer => item === 'primary' || item === 'duplicate' || item === 'narrative');
}

function observationConfirmedSourceClasses(observation: AlphaRadarObservation): AlphaRadarSourceClass[] {
  const fallback = [observation.sourceClass ?? deriveAlphaRadarSourceClass({
    source: observation.source,
    sourceType: observation.sourceType,
    sourceLayer: observation.sourceLayer,
    title: observation.title,
    excerpt: observation.excerpt,
    topicTags: observation.topicTags,
  })];
  const raw = uniqueStringArray((observation.metadata as { confirmedBySourceClasses?: unknown } | undefined)?.confirmedBySourceClasses, fallback);
  return raw.filter((item): item is AlphaRadarSourceClass => item === 'market' || item === 'official' || item === 'newswire' || item === 'macro' || item === 'flow' || item === 'social');
}

function observationEffectiveWeight(observation: AlphaRadarObservation): number {
  const sourceTypes = observationConfirmedSourceTypes(observation);
  const layers = observationConfirmedLayers(observation);
  const sourceClasses = observationConfirmedSourceClasses(observation);
  const sourceWeight = clampSourceWeight(observation.sourceWeight, 1);
  const confirmationBoost = Math.min(0.45, Math.max(0, sourceTypes.length - 1) * 0.12 + Math.max(0, layers.length - 1) * 0.08 + Math.max(0, sourceClasses.length - 1) * 0.1);
  const layerFactor = layers.includes('primary') ? 1 : layers.includes('duplicate') ? 0.92 : 0.8;
  const sourceTypeFactor = sourceTypes.includes('market')
    ? 1.08
    : sourceTypes.includes('direct')
      ? 1.06
      : sourceTypes.includes('social')
        ? 0.86
        : sourceTypes.includes('news')
          ? 0.96
          : 0.98;
  const sourceClassFactor = sourceClasses.includes('official')
    ? 1.08
    : sourceClasses.includes('market')
      ? 1.06
      : sourceClasses.includes('flow')
        ? 1.03
        : sourceClasses.includes('social')
          ? 0.86
          : sourceClasses.includes('macro')
            ? 0.98
            : 1;
  return Number((observation.rank * sourceWeight * layerFactor * sourceTypeFactor * sourceClassFactor * (1 + confirmationBoost)).toFixed(4));
}

type MarketStructureSnapshot = {
  regime: 'trend' | 'range' | 'chop' | 'thin';
  windowChangePct?: number;
  latestMovePct?: number;
  rangePosition?: number;
  trendEfficiency?: number;
  structureAlignmentScore: number;
  structureMetrics?: {
    compression: {
      rangeWidthPct?: number;
      score: number;
      active: boolean;
    };
    breakout: {
      breakoutDistancePct?: number;
      displacementPct?: number;
      score: number;
      active: boolean;
    };
    followThrough: {
      continuationPct?: number;
      score: number;
      active: boolean;
    };
    relativeStrength: {
      vsBtc: {
        benchmark: 'BTC';
        spreadPct?: number;
        ratioChangePct?: number;
        score: number;
        leadership: 'outperform' | 'underperform' | 'flat' | 'unavailable';
      };
      vsEth: {
        benchmark: 'ETH';
        spreadPct?: number;
        ratioChangePct?: number;
        score: number;
        leadership: 'outperform' | 'underperform' | 'flat' | 'unavailable';
      };
    };
  };
};

type IdeaExecutionLevels = {
  trigger?: number;
  invalidation?: number;
  targets: number[];
  expectedRr?: number;
};

type IdeaActionabilityInputs = NonNullable<AlphaRadarIdea['actionabilityInputs']>;
type IdeaRotationContext = NonNullable<AlphaRadarIdea['rotationContext']>;

function clampIdeaScore(value: number): number {
  return Number(Math.max(0, Math.min(0.99, value)).toFixed(4));
}

function roundIdeaPrice(value: number): number {
  return Number(value.toFixed(2));
}

function clampUnit(value: number): number {
  return Number(Math.max(0, Math.min(1, value)).toFixed(4));
}

function shortIdeaLine(...parts: Array<string | number | undefined | false>): string {
  return parts.filter((part) => part !== undefined && part !== false && String(part).trim()).join(', ');
}

function classifyIdeaSignalFamily(input: {
  topicTags: string[];
  relativeStrengthScore: number;
  watchBreakoutScore: number;
  observationQualityScore: number;
  rotationAction: AlphaRadarIdea['rotationAction'];
}): Exclude<AlphaRadarIdea['signalFamily'], 'cash'> {
  const topicTags = input.topicTags.map((item) => String(item ?? '').trim().toLowerCase());
  if (topicTags.includes('catalyst') && input.observationQualityScore >= Math.max(input.watchBreakoutScore, 0.52)) {
    return 'catalyst';
  }
  if (input.rotationAction === 'rotate' && input.relativeStrengthScore >= 0.58) {
    return 'rotation';
  }
  return 'expansion';
}

const MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES = 4;

function normalizeValidMarketSeriesTicks(ticks: MarketTick[]): MarketTick[] {
  const byTimestamp = new Map<string, MarketTick>();
  for (const tick of ticks) {
    const symbol = String(tick.symbol ?? '').trim().toUpperCase();
    const price = Number(tick.price);
    const timestampMs = Date.parse(String(tick.timestamp ?? ''));
    if (!symbol || !Number.isFinite(price) || price <= 0 || !Number.isFinite(timestampMs)) continue;
    const timestamp = new Date(timestampMs).toISOString();
    byTimestamp.set(timestamp, { symbol, price, timestamp });
  }
  return [...byTimestamp.values()].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

function buildIdeaExecutionLevels(input: {
  price: number;
  direction: 'long' | 'short';
  ticks: MarketTick[];
  marketStructure: MarketStructureSnapshot;
}): IdeaExecutionLevels {
  const validTicks = normalizeValidMarketSeriesTicks(input.ticks);
  if (validTicks.length < MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES) {
    return { targets: [] };
  }
  const prices = validTicks.map((tick) => tick.price);
  const high = prices.length > 0 ? Math.max(...prices) : input.price;
  const low = prices.length > 0 ? Math.min(...prices) : input.price;
  const rangeWidthPct = input.price > 0 ? Math.max(0.0025, Math.min(0.035, (high - low) / input.price)) : 0.01;
  const rangePosition = input.marketStructure.rangePosition ?? 0.5;
  const directionLocation = input.direction === 'long' ? rangePosition : 1 - rangePosition;
  const extensionPressure = Math.max(0, directionLocation - 0.72);
  const favorableLocation = Math.max(0, 0.28 - directionLocation);

  const entryBufferPctBase = input.marketStructure.regime === 'trend'
    ? rangeWidthPct * 0.16
    : input.marketStructure.regime === 'range'
      ? rangeWidthPct * 0.08
      : rangeWidthPct * 0.12;
  const entryBufferPct = Math.max(
    0.0008,
    Math.min(0.0065, entryBufferPctBase + extensionPressure * 0.004 - favorableLocation * 0.0015),
  );

  const stopBufferPctBase = input.marketStructure.regime === 'trend'
    ? rangeWidthPct * 0.42
    : input.marketStructure.regime === 'range'
      ? rangeWidthPct * 0.34
      : rangeWidthPct * 0.3;
  const stopBufferPct = Math.max(0.0045, Math.min(0.022, stopBufferPctBase + extensionPressure * 0.0025));

  const triggerAnchor = input.direction === 'long'
    ? (input.marketStructure.regime === 'trend' ? Math.max(input.price, high) : input.price)
    : (input.marketStructure.regime === 'trend' ? Math.min(input.price, low) : input.price);
  const trigger = input.direction === 'long'
    ? roundIdeaPrice(triggerAnchor * (1 + entryBufferPct))
    : roundIdeaPrice(triggerAnchor * (1 - entryBufferPct));
  const invalidation = input.direction === 'long'
    ? roundIdeaPrice(trigger * (1 - stopBufferPct))
    : roundIdeaPrice(trigger * (1 + stopBufferPct));

  const risk = Math.abs(trigger - invalidation);
  const rewardMultipliers = input.marketStructure.regime === 'trend'
    ? [1.85, 3.15]
    : input.marketStructure.regime === 'range'
      ? [1.35, 2.2]
      : [1.15, 1.85];
  const targets = rewardMultipliers.map((multiple) => roundIdeaPrice(
    input.direction === 'long'
      ? trigger + risk * multiple
      : trigger - risk * multiple,
  ));
  const reward = Math.abs((targets[0] ?? trigger) - trigger);

  return {
    trigger,
    invalidation,
    targets,
    expectedRr: risk > 0 ? Number((reward / risk).toFixed(2)) : undefined,
  };
}

function percentileScore(values: number[], value?: number): number | undefined {
  if (!Number.isFinite(value)) return undefined;
  const ranked = values.filter((item) => Number.isFinite(item)).slice().sort((a, b) => a - b);
  if (ranked.length === 0) return undefined;
  const below = ranked.filter((item) => item <= Number(value)).length;
  return Number((Math.max(0, Math.min(1, below / ranked.length))).toFixed(4));
}

function buildIdeaActionabilityInputs(input: {
  direction: 'long' | 'short';
  perpContext?: AlphaRadarPerpContext;
  openInterestUniverse: number[];
  volumeUniverse: number[];
}): IdeaActionabilityInputs {
  const fundingRate = Number(input.perpContext?.fundingRate8h);
  const openInterestUsd = Number(input.perpContext?.openInterestUsd);
  const volume24hUsd = Number(input.perpContext?.volume24hUsd);
  const liquidityScore = [
    percentileScore(input.openInterestUniverse, openInterestUsd),
    percentileScore(input.volumeUniverse, volume24hUsd),
  ].filter((item): item is number => typeof item === 'number');
  const liquidity = liquidityScore.length > 0
    ? Number((liquidityScore.reduce((acc, item) => acc + item, 0) / liquidityScore.length).toFixed(4))
    : undefined;

  const crowdedLong = Number.isFinite(fundingRate) && fundingRate > 0 ? Math.min(1, Math.abs(fundingRate) / 0.0008) : 0;
  const crowdedShort = Number.isFinite(fundingRate) && fundingRate < 0 ? Math.min(1, Math.abs(fundingRate) / 0.0008) : 0;
  const crowdingScore = Number((input.direction === 'long' ? crowdedLong : crowdedShort).toFixed(4));
  const notes: string[] = [];

  if (Number.isFinite(fundingRate)) {
    const bp = Number((fundingRate * 10_000).toFixed(2));
    if (input.direction === 'long' && fundingRate > 0.0004) notes.push(`Funding is crowded for longs (${bp} bps), fade urgency until price confirms.`);
    else if (input.direction === 'short' && fundingRate < -0.0004) notes.push(`Funding is crowded for shorts (${bp} bps), avoid chasing late downside.`);
    else notes.push(`Funding is supportive to neutral (${bp} bps).`);
  } else {
    notes.push('Funding unavailable, keep actionability conservative.');
  }

  if (Number.isFinite(openInterestUsd)) notes.push(`Open interest ${Math.round(openInterestUsd / 1_000_000)}M USD.`);
  if (Number.isFinite(volume24hUsd)) notes.push(`24h volume ${Math.round(volume24hUsd / 1_000_000)}M USD.`);

  const actionabilityBias = Number((
    ((liquidity ?? 0.5) - 0.5) * 0.12
    + (0.42 - crowdingScore) * 0.09
  ).toFixed(4));

  return {
    fundingRate8h: Number.isFinite(fundingRate) ? fundingRate : undefined,
    openInterestUsd: Number.isFinite(openInterestUsd) ? openInterestUsd : undefined,
    volume24hUsd: Number.isFinite(volume24hUsd) ? volume24hUsd : undefined,
    liquidityScore: liquidity,
    crowdingScore,
    actionabilityBias,
    notes: notes.slice(0, 3),
  };
}

function estimateOpenPositionUnrealizedPct(position: Position, latestPrice?: number): number | undefined {
  const current = Number(latestPrice);
  const entry = Number(position.entryPrice);
  if (!Number.isFinite(entry) || entry <= 0 || !Number.isFinite(current) || current <= 0) return undefined;
  const raw = position.side === 'long'
    ? ((current - entry) / entry) * 100
    : ((entry - current) / entry) * 100;
  return Number(raw.toFixed(3));
}

function buildIdeaRotationContext(input: {
  symbol: string;
  candidateScore: number;
  positions: Position[];
  latestTickBySymbol: Map<string, MarketTick>;
}): { action: AlphaRadarIdea['rotationAction']; summary: string; context: IdeaRotationContext; scoreBias: number } {
  const openPositions = input.positions.filter((position) => position.status === 'open');
  const sameSymbol = openPositions.find((position) => String(position.symbol ?? '').trim().toUpperCase() === input.symbol);
  if (sameSymbol) {
    const samePnl = estimateOpenPositionUnrealizedPct(sameSymbol, Number(input.latestTickBySymbol.get(input.symbol)?.price));
    return {
      action: 'keep',
      summary: `${input.symbol} is already in the book. Only add or rotate if this setup materially improves the current entry quality.`,
      context: {
        openRiskCount: openPositions.length,
        weakestOpenSymbol: input.symbol,
        weakestOpenUnrealizedPnlPct: samePnl,
        rotationEdgeScore: Number((input.candidateScore - 0.62).toFixed(4)),
      },
      scoreBias: input.candidateScore >= 0.75 ? 0.01 : -0.02,
    };
  }

  if (openPositions.length === 0) {
    return {
      action: 'rotate',
      summary: `No open crypto risk is blocking ${input.symbol}. If the trigger confirms, this can become the next best slot in the book.`,
      context: { openRiskCount: 0, rotationEdgeScore: Number((input.candidateScore - 0.5).toFixed(4)) },
      scoreBias: 0.035,
    };
  }

  const weakest = openPositions
    .map((position) => {
      const symbol = String(position.symbol ?? '').trim().toUpperCase();
      const latest = Number(input.latestTickBySymbol.get(symbol)?.price);
      const unrealizedPct = estimateOpenPositionUnrealizedPct(position, latest);
      const weakness = Number((
        0.35
        + (typeof unrealizedPct === 'number' && unrealizedPct < 0 ? Math.min(0.45, Math.abs(unrealizedPct) / 8) : -0.05)
      ).toFixed(4));
      return { symbol, unrealizedPct, weakness };
    })
    .sort((a, b) => b.weakness - a.weakness)[0];

  const rotate = Boolean(weakest) && input.candidateScore >= 0.63 && (weakest.weakness >= 0.42 || (weakest.unrealizedPct ?? 0) < -0.4);
  return {
    action: rotate ? 'rotate' : 'keep',
    summary: weakest
      ? rotate
        ? `${input.symbol} outranks current open risk. First replacement candidate is ${weakest.symbol}${typeof weakest.unrealizedPct === 'number' ? ` (${weakest.unrealizedPct}% unrealized)` : ''}.`
        : `Current open risk is still competitive. Weakest slot is ${weakest.symbol}${typeof weakest.unrealizedPct === 'number' ? ` (${weakest.unrealizedPct}% unrealized)` : ''}, so wait for a clearer edge before rotating.`
      : `Existing book should stay unchanged until a stronger edge appears.`,
    context: {
      openRiskCount: openPositions.length,
      weakestOpenSymbol: weakest?.symbol,
      weakestOpenUnrealizedPnlPct: weakest?.unrealizedPct,
      rotationEdgeScore: Number((input.candidateScore - ((weakest?.weakness ?? 0.35) + 0.2)).toFixed(4)),
    },
    scoreBias: rotate ? 0.03 : -0.025,
  };
}

function buildRelativeStrengthSnapshot<TBenchmark extends 'BTC' | 'ETH'>(input: {
  symbol: string;
  direction: 'long' | 'short';
  symbolTicks: MarketTick[];
  benchmark: TBenchmark;
  benchmarkTicks: MarketTick[];
}): { benchmark: TBenchmark; spreadPct?: number; ratioChangePct?: number; score: number; leadership: 'outperform' | 'underperform' | 'flat' | 'unavailable' } {
  if (input.symbol === input.benchmark) {
    return { benchmark: input.benchmark, spreadPct: 0, ratioChangePct: 0, score: 0.5, leadership: 'flat' };
  }
  const symbolSeries = normalizeValidMarketSeriesTicks(input.symbolTicks);
  const benchmarkSeries = normalizeValidMarketSeriesTicks(input.benchmarkTicks);
  if (symbolSeries.length < MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES || benchmarkSeries.length < MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES) {
    return { benchmark: input.benchmark, score: 0.5, leadership: 'unavailable' };
  }
  const symbolFirst = symbolSeries[0]?.price ?? 0;
  const symbolLast = symbolSeries[symbolSeries.length - 1]?.price ?? 0;
  const benchmarkFirst = benchmarkSeries[0]?.price ?? 0;
  const benchmarkLast = benchmarkSeries[benchmarkSeries.length - 1]?.price ?? 0;
  if (symbolFirst <= 0 || benchmarkFirst <= 0 || symbolLast <= 0 || benchmarkLast <= 0) {
    return { benchmark: input.benchmark, score: 0.5, leadership: 'unavailable' };
  }

  const symbolReturn = pctChange(symbolLast, symbolFirst) ?? 0;
  const benchmarkReturn = pctChange(benchmarkLast, benchmarkFirst) ?? 0;
  const spreadPct = Number((symbolReturn - benchmarkReturn).toFixed(4));
  const ratioFirst = symbolFirst / benchmarkFirst;
  const ratioLast = symbolLast / benchmarkLast;
  const ratioChangePct = pctChange(ratioLast, ratioFirst) ?? 0;
  const directionalEdge = (input.direction === 'long' ? spreadPct : -spreadPct) / 4;
  const score = clampUnit(0.5 + directionalEdge * 0.5);
  const leadership = spreadPct > 0.15 ? 'outperform' : spreadPct < -0.15 ? 'underperform' : 'flat';
  return {
    benchmark: input.benchmark,
    spreadPct,
    ratioChangePct: Number(ratioChangePct.toFixed(4)),
    score,
    leadership,
  };
}

function buildMarketStructureSnapshot(input: {
  symbol: string;
  ticks: MarketTick[];
  direction: 'long' | 'short';
  benchmarkTicksBySymbol?: Map<string, MarketTick[]>;
}): MarketStructureSnapshot {
  const sorted = normalizeValidMarketSeriesTicks(input.ticks);
  if (sorted.length < MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES) {
    return {
      regime: 'thin',
      structureAlignmentScore: 0.35,
      structureMetrics: {
        compression: { score: 0.35, active: false },
        breakout: { score: 0.35, active: false },
        followThrough: { score: 0.35, active: false },
        relativeStrength: {
          vsBtc: { benchmark: 'BTC', score: 0.5, leadership: 'unavailable' },
          vsEth: { benchmark: 'ETH', score: 0.5, leadership: 'unavailable' },
        },
      },
    };
  }

  const prices = sorted.map((item) => item.price);

  const first = prices[0] ?? 0;
  const last = prices[prices.length - 1] ?? 0;
  const prev = prices[prices.length - 2] ?? first;
  const high = Math.max(...prices);
  const low = Math.min(...prices);
  const windowChangePct = pctChange(last, first) ?? 0;
  const latestMovePct = pctChange(last, prev) ?? 0;
  const preBreakoutHigh = Math.max(...prices.slice(0, -1));
  const preBreakoutLow = Math.min(...prices.slice(0, -1));
  const path = prices.slice(1).reduce((acc, price, index) => acc + Math.abs(pctChange(price, prices[index] ?? price) ?? 0), 0);
  const efficiency = path > 0 ? Math.min(1, Math.abs(windowChangePct) / path) : 0;
  const rangeWidth = high - low;
  const rangeWidthPct = last > 0 ? (rangeWidth / last) * 100 : 0;
  const rawRangePosition = rangeWidth > 0 ? (last - low) / rangeWidth : 0.5;
  const rangePosition = Number(Math.max(0, Math.min(1, rawRangePosition)).toFixed(4));
  const directionSign = input.direction === 'long' ? 1 : -1;
  const signedWindowMove = (windowChangePct / 3) * directionSign;
  const signedLatestMove = (latestMovePct / 1.5) * directionSign;
  const trendAlignment = Math.max(0, Math.min(1, 0.5 + signedWindowMove * 0.5));
  const latestAlignment = Math.max(0, Math.min(1, 0.5 + signedLatestMove * 0.5));
  const locationSupport = input.direction === 'long' ? rangePosition : 1 - rangePosition;
  const extensionPenalty = efficiency < 0.55 && locationSupport > 0.88 ? 0.18 : efficiency < 0.4 && locationSupport > 0.8 ? 0.1 : 0;
  const compressionScore = clampUnit((1 - Math.min(1, rangeWidthPct / 4.5)) * 0.7 + (1 - efficiency) * 0.3);
  const breakoutDistancePct = input.direction === 'long'
    ? Math.max(0, pctChange(last, preBreakoutHigh) ?? 0)
    : Math.max(0, pctChange(preBreakoutLow, last) ?? 0);
  const displacementPct = Math.max(0, (latestMovePct ?? 0) * directionSign);
  const breakoutScore = clampUnit(Math.min(1, breakoutDistancePct / 1.2) * 0.45 + Math.min(1, displacementPct / 1.5) * 0.55);
  const priorMovePct = pctChange(prev, prices[prices.length - 3] ?? prev) ?? 0;
  const continuationPct = Math.max(0, ((latestMovePct ?? 0) + priorMovePct) * directionSign);
  const followThroughScore = clampUnit(Math.min(1, continuationPct / 2));
  const relativeStrength = {
    vsBtc: buildRelativeStrengthSnapshot({
      symbol: input.symbol,
      direction: input.direction,
      symbolTicks: input.ticks,
      benchmark: 'BTC',
      benchmarkTicks: input.benchmarkTicksBySymbol?.get('BTC') ?? [],
    }),
    vsEth: buildRelativeStrengthSnapshot({
      symbol: input.symbol,
      direction: input.direction,
      symbolTicks: input.ticks,
      benchmark: 'ETH',
      benchmarkTicks: input.benchmarkTicksBySymbol?.get('ETH') ?? [],
    }),
  };
  const structureAlignmentScore = clampIdeaScore(
    0.2 + trendAlignment * 0.35 + latestAlignment * 0.2 + efficiency * 0.15 + locationSupport * 0.1 - extensionPenalty
  );

  const regime = efficiency >= 0.62
    ? 'trend'
    : efficiency <= 0.24
      ? 'chop'
      : rangePosition >= 0.35 && rangePosition <= 0.65
        ? 'range'
        : 'range';

  return {
    regime,
    windowChangePct: Number(windowChangePct.toFixed(4)),
    latestMovePct: Number(latestMovePct.toFixed(4)),
    rangePosition,
    trendEfficiency: Number(efficiency.toFixed(4)),
    structureAlignmentScore,
    structureMetrics: {
      compression: {
        rangeWidthPct: Number(rangeWidthPct.toFixed(4)),
        score: compressionScore,
        active: compressionScore >= 0.6,
      },
      breakout: {
        breakoutDistancePct: Number(breakoutDistancePct.toFixed(4)),
        displacementPct: Number(displacementPct.toFixed(4)),
        score: breakoutScore,
        active: breakoutDistancePct > 0 || displacementPct >= 0.45,
      },
      followThrough: {
        continuationPct: Number(continuationPct.toFixed(4)),
        score: followThroughScore,
        active: followThroughScore >= 0.55,
      },
      relativeStrength,
    },
  };
}

export function buildIdeaCandidates(input: {
  observations: AlphaRadarObservation[];
  ticks: MarketTick[];
  positions: Position[];
  perpContexts?: AlphaRadarPerpContext[];
  settings: AlphaRadarSettings;
  tradableSymbols: string[];
  evidenceBundles?: EvidenceBundle[];
  signalCandidates?: SignalCandidate[];
  nowIso: string;
}): AlphaRadarIdea[] {
  const tradable = [...new Set(input.tradableSymbols.map((item) => normalizeAlphaRadarSymbol(item)).filter(Boolean))];
  const tradableByAssetTag = new Map<string, string[]>();
  for (const symbol of tradable) {
    for (const alias of alphaRadarSymbolAliases(symbol)) {
      const list = tradableByAssetTag.get(alias) ?? [];
      if (!list.includes(symbol)) list.push(symbol);
      tradableByAssetTag.set(alias, list);
    }
  }

  const latestTickBySymbol = new Map<string, MarketTick>();
  const ticksBySymbol = new Map<string, MarketTick[]>();
  for (const tick of input.ticks.slice().sort((a, b) => a.timestamp.localeCompare(b.timestamp))) {
    const symbol = normalizeAlphaRadarSymbol(tick.symbol);
    if (!symbol) continue;
    latestTickBySymbol.set(symbol, { ...tick, symbol });
    const series = ticksBySymbol.get(symbol) ?? [];
    series.push({ ...tick, symbol });
    ticksBySymbol.set(symbol, series);
  }

  const observationsBySymbol = new Map<string, AlphaRadarObservation[]>();
  for (const observation of input.observations) {
    for (const tag of observation.assetTags) {
      const normalized = normalizeAlphaRadarSymbol(tag);
      if (!normalized) continue;
      const matchedSymbols = tradableByAssetTag.get(normalized) ?? [];
      for (const symbol of matchedSymbols) {
        const list = observationsBySymbol.get(symbol) ?? [];
        list.push(observation);
        observationsBySymbol.set(symbol, list);
      }
    }
  }

  const openBySymbol = new Map(
    input.positions
      .filter((position) => position.status === 'open')
      .map((position) => [normalizeAlphaRadarSymbol(position.symbol), position] as const)
      .filter((entry): entry is readonly [string, Position] => Boolean(entry[0]))
  );

  const perpBySymbol = new Map(
    (input.perpContexts ?? [])
      .map((item) => [normalizeAlphaRadarSymbol(item.symbol), item] as const)
      .filter((entry): entry is readonly [string, AlphaRadarPerpContext] => Boolean(entry[0]))
  );
  const openInterestUniverse = (input.perpContexts ?? []).map((item) => Number(item.openInterestUsd)).filter((item) => Number.isFinite(item) && item > 0);
  const volumeUniverse = (input.perpContexts ?? []).map((item) => Number(item.volume24hUsd)).filter((item) => Number.isFinite(item) && item > 0);

  const ideas: AlphaRadarIdea[] = [];
  const bundleByObservationId = new Map<string, EvidenceBundle>();
  for (const bundle of input.evidenceBundles ?? []) {
    for (const observationId of bundle.observationIds) {
      bundleByObservationId.set(observationId, bundle);
    }
  }
  const candidateByBundleAndSymbol = new Map<string, SignalCandidate>();
  for (const candidate of input.signalCandidates ?? []) {
    candidateByBundleAndSymbol.set(`${candidate.evidenceBundleId}|${candidate.symbol.toUpperCase()}`, candidate);
  }
  for (const symbol of tradable) {
    const allSymbolObservations = (observationsBySymbol.get(symbol) ?? [])
      .slice()
      .sort((a, b) => observationEffectiveWeight(b) - observationEffectiveWeight(a) || b.observedAt.localeCompare(a.observedAt))
      .slice(0, 4);
    if (allSymbolObservations.length === 0) continue;

    const candidateIsMacro = isMacroShockCandidateSymbol(symbol);
    const symbolObservations = candidateIsMacro
      ? allSymbolObservations.filter((item) => observationSupportsSymbolConfirmation(item, symbol))
      : allSymbolObservations;
    if (candidateIsMacro && symbolObservations.length === 0) continue;

    const latestTick = latestTickBySymbol.get(symbol);
    const price = Number(latestTick?.price);
    if (!Number.isFinite(price) || price <= 0) continue;

    const weightedSentiment = symbolObservations.reduce((acc, item) => acc + (item.sentimentScore ?? 0) * observationEffectiveWeight(item), 0);
    const totalWeight = symbolObservations.reduce((acc, item) => acc + observationEffectiveWeight(item), 0) || 1;
    const sentiment = weightedSentiment / totalWeight;
    const freshness = symbolObservations.reduce((acc, item) => acc + (item.urgencyScore ?? 0.5) * observationEffectiveWeight(item), 0) / totalWeight;
    const novelty = symbolObservations.reduce((acc, item) => acc + (item.noveltyScore ?? 0.5) * observationEffectiveWeight(item), 0) / totalWeight;
    const confirmedSources = [...new Set(symbolObservations.flatMap((item) => observationConfirmedSources(item)))];
    const confirmedSourceTypes = [...new Set(symbolObservations.flatMap((item) => observationConfirmedSourceTypes(item)))];
    const confirmedLayers = [...new Set(symbolObservations.flatMap((item) => observationConfirmedLayers(item)))];
    const confirmedSourceClasses = [...new Set(symbolObservations.flatMap((item) => observationConfirmedSourceClasses(item)))];
    const primaryCount = symbolObservations.filter((item) => observationConfirmedLayers(item).includes('primary')).length;
    const symbolAliasSet = new Set(alphaRadarSymbolAliases(symbol));
    const macroShockSignals = symbolObservations
      .map((item) => observationMacroShock(item))
      .filter((item): item is NonNullable<ReturnType<typeof observationMacroShock>> => item !== null)
      .filter((item) => symbolAliasSet.has(normalizeAlphaRadarSymbol(item.symbol)) && item.fastTrack);
    const macroShockFastTrack = macroShockSignals.length > 0;
    const macroShockMinSources = macroShockSignals.length > 0 ? Math.min(...macroShockSignals.map((item) => item.minSources)) : 99;
    const crossTypeConfirmed = confirmedSourceTypes.length >= 2;
    const crossLayerConfirmed = confirmedLayers.length >= 2;
    const crossClassConfirmed = confirmedSourceClasses.length >= 2;
    const fastMacroConfirmed = macroShockFastTrack && confirmedSources.length >= macroShockMinSources && primaryCount > 0;
    const effectiveCrossTypeConfirmed = crossTypeConfirmed || fastMacroConfirmed;
    const effectiveCrossClassConfirmed = crossClassConfirmed || fastMacroConfirmed;
    const confirmationScore = Math.min(
      1,
      0.16
      + Math.max(0, confirmedSources.length - 1) * 0.08
      + Math.max(0, confirmedSourceTypes.length - 1) * 0.22
      + Math.max(0, confirmedLayers.length - 1) * 0.12
      + Math.max(0, confirmedSourceClasses.length - 1) * 0.14
      + (primaryCount > 0 ? 0.16 : 0)
    );
    const boostedConfirmationScore = fastMacroConfirmed ? Math.max(confirmationScore, 0.72) : confirmationScore;
    const conviction = Math.min(
      1,
      Math.abs(sentiment) * 0.5
      + freshness * 0.22
      + novelty * 0.18
      + boostedConfirmationScore * 0.1
    );
    const direction = sentiment >= 0 ? 'long' : 'short';
    const symbolTicks = ticksBySymbol.get(symbol) ?? [];
    const validSeriesPoints = normalizeValidMarketSeriesTicks(symbolTicks).length;
    const marketStructure = buildMarketStructureSnapshot({
      symbol,
      ticks: symbolTicks,
      direction,
      benchmarkTicksBySymbol: ticksBySymbol,
    });
    const executionLevels = buildIdeaExecutionLevels({
      price,
      direction,
      ticks: symbolTicks,
      marketStructure,
    });
    const { trigger, invalidation, targets, expectedRr } = executionLevels;
    const actionabilityInputs = buildIdeaActionabilityInputs({
      direction,
      perpContext: perpBySymbol.get(symbol),
      openInterestUniverse,
      volumeUniverse,
    });
    const openPosition = openBySymbol.get(symbol);
    const executionReady = Number.isFinite(trigger) && Number.isFinite(invalidation) && targets.length > 0;
    const rrComponent = typeof expectedRr === 'number' ? Math.min(1, expectedRr / 3) : 0;
    const actionabilityBias = (effectiveCrossTypeConfirmed ? 0.05 : -0.04) + (effectiveCrossClassConfirmed ? 0.04 : -0.03) + (primaryCount > 0 ? 0.03 : -0.05) + (actionabilityInputs.actionabilityBias ?? 0) + (fastMacroConfirmed ? 0.06 : 0);
    const observationQualityScore = clampIdeaScore(conviction * 0.62 + boostedConfirmationScore * 0.23 + novelty * 0.15 + (fastMacroConfirmed ? 0.04 : 0));
    const structureMetrics = marketStructure.structureMetrics;
    const relativeStrengthScore = structureMetrics
      ? Number((((structureMetrics.relativeStrength.vsBtc.score ?? 0.5) + (structureMetrics.relativeStrength.vsEth.score ?? 0.5)) / 2).toFixed(4))
      : 0.5;
    const watchBreakoutScore = clampIdeaScore(
      (structureMetrics?.compression.score ?? 0.35) * 0.34
      + (structureMetrics?.breakout.score ?? 0.35) * 0.28
      + (structureMetrics?.followThrough.score ?? 0.35) * 0.18
      + relativeStrengthScore * 0.12
      + boostedConfirmationScore * 0.08
    );
    const tradeActionabilityScore = clampIdeaScore(
      marketStructure.structureAlignmentScore * 0.34 + rrComponent * 0.2 + boostedConfirmationScore * 0.2 + freshness * 0.12 + (actionabilityInputs.liquidityScore ?? 0.5) * 0.08 + (1 - (actionabilityInputs.crowdingScore ?? 0.5)) * 0.06 + actionabilityBias + (executionReady ? 0.03 : -0.12)
    );
    const compressionScore = structureMetrics?.compression.score ?? 0.35;
    const breakoutScore = structureMetrics?.breakout.score ?? 0.35;
    const followThroughScore = structureMetrics?.followThrough.score ?? 0.35;
    const compressionPromising = (structureMetrics?.compression.active ?? false) && compressionScore >= 0.62;
    const breakoutPromising = (structureMetrics?.breakout.active ?? false) && breakoutScore >= 0.5;
    const followThroughPromising = (structureMetrics?.followThrough.active ?? false) && followThroughScore >= 0.58;
    const earlyStructureReady = compressionPromising
      && marketStructure.structureAlignmentScore >= 0.46
      && (relativeStrengthScore >= 0.53 || breakoutScore >= 0.42);
    const actionableBreakoutReady = marketStructure.structureAlignmentScore >= 0.55
      && executionReady
      && (breakoutPromising || followThroughPromising)
      && watchBreakoutScore >= 0.52;
    const macroFastTrackOnly = candidateIsMacro && !fastMacroConfirmed;
    const preRotationScore = clampIdeaScore(observationQualityScore * 0.46 + tradeActionabilityScore * 0.54);
    const rotationAssessment = buildIdeaRotationContext({
      symbol,
      candidateScore: preRotationScore,
      positions: input.positions,
      latestTickBySymbol,
    });
    const rotationAction = openPosition ? 'keep' : rotationAssessment.action;
    const score = clampIdeaScore(preRotationScore + (openPosition ? -0.01 : rotationAssessment.scoreBias));
    const structureLedWatch = observationQualityScore >= 0.55
      && watchBreakoutScore >= 0.5
      && earlyStructureReady
      && !actionableBreakoutReady
      && tradeActionabilityScore < Math.max(input.settings.minIdeaScore + 0.03, observationQualityScore);
    const verdict: AlphaRadarIdea['verdict'] = structureLedWatch || macroFastTrackOnly ? 'watch_breakout' : 'idea';
    const signalFamily: AlphaRadarIdea['signalFamily'] = classifyIdeaSignalFamily({
      topicTags: symbolObservations.flatMap((item) => item.topicTags ?? []),
      relativeStrengthScore,
      watchBreakoutScore,
      observationQualityScore,
      rotationAction,
    });
    const actionabilityBlockers = [
      structureLedWatch ? 'Structure is early, wait for a cleaner breakout trigger or follow-through.' : null,
      macroFastTrackOnly ? 'Macro symbols stay watch-only until a real multi-source fast-track shock is confirmed.' : null,
      !effectiveCrossTypeConfirmed ? 'Needs broader confirmation across source types.' : null,
      !effectiveCrossClassConfirmed ? 'Needs more independent cross-class confirmation.' : null,
      !executionReady ? `Execution map is still warming up (${validSeriesPoints}/${MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES} valid points).` : null,
    ].filter((item): item is string => Boolean(item));
    const actionabilitySummary = structureLedWatch
      ? 'Watch only, early structure is promising but the breakout is not clean enough to trade yet.'
      : fastMacroConfirmed
        ? 'Actionable macro shock, verified by 2-3 fast sources and ready for the standard trigger flow.'
        : macroFastTrackOnly
          ? 'Watch only, macro catalysts need a true fast-track shock before they can become actionable.'
        : 'Actionable idea, confirmation and breakout structure are strong enough to queue.';

    const ideaAssetTags = [...new Set(symbolObservations.flatMap((item) => item.assetTags))].slice(0, 6);
    const ideaTopicTags = [...new Set(symbolObservations.flatMap((item) => item.topicTags ?? []))].slice(0, 6);
    const confirmationSummary = shortIdeaLine(
      `${confirmedSources.length} sources`,
      `${confirmedSourceTypes.length} types`,
      `${confirmedSourceClasses.length} classes`,
      `${confirmedLayers.join(' + ') || 'primary'} layers`,
    );
    const primaryObservation = symbolObservations.find((item) => observationConfirmedLayers(item).includes('primary'));
    const primaryBundle = symbolObservations
      .map((item) => bundleByObservationId.get(item.id))
      .find((bundle): bundle is EvidenceBundle => Boolean(bundle));
    const signalCandidate = primaryBundle
      ? candidateByBundleAndSymbol.get(`${primaryBundle.id}|${symbol.toUpperCase()}`)
      : undefined;
    const warnings = ['Manual confirmation required.', 'Wait for the trigger.', 'No headline-only entries.'];
    if (!effectiveCrossTypeConfirmed) warnings.push('Prefer 2+ independent source types before treating this as actionable.');
    if (!effectiveCrossClassConfirmed) warnings.push('Still thin on cross-class confirmation, avoid treating repeated headlines as independent proof.');
    if (primaryCount === 0) warnings.push('Current support is duplicate or narrative heavy, wait for a primary-source confirm.');
    if (!executionReady) warnings.push(`Execution map withheld until at least ${MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES} valid recent market points are available for this symbol (currently ${validSeriesPoints}).`);
    if (fastMacroConfirmed) warnings.push(`Fast-track macro catalyst is active for ${symbol}, keep the idea honest if the symbol is monitor-only elsewhere.`);
    if (macroFastTrackOnly) warnings.push('Macro symbols stay watch-only until a real multi-source fast-track shock is confirmed.');

    ideas.push({
      id: `idea-${symbol}-${direction}-${input.nowIso.slice(0, 16)}`,
      evidenceBundleId: primaryBundle?.id,
      signalCandidateId: signalCandidate?.id,
      signalCandidateState: signalCandidate?.state,
      durableScore: signalCandidate?.score,
      symbol,
      direction,
      score,
      observationQualityScore,
      tradeActionabilityScore,
      verdict,
      signalFamily,
      actionability: {
        actionable: verdict === 'idea',
        summary: actionabilitySummary,
        blockers: actionabilityBlockers,
      },
      title: verdict === 'watch_breakout'
        ? `${symbol} breakout watch`
        : `${symbol} ${direction === 'long' ? 'trend continuation' : 'mean-reversion short'} hypothesis`,
      whyNow: [
        shortIdeaLine('Confirmation', confirmationSummary, fastMacroConfirmed ? 'macro fast-track' : undefined),
        shortIdeaLine(
          `${marketStructure.regime} regime`,
          `structure ${Math.round(marketStructure.structureAlignmentScore * 100)}/100`,
          `watch ${Math.round(watchBreakoutScore * 100)}/100`,
        ),
        executionReady
          ? shortIdeaLine('Execution map:', `trigger ${trigger}`, `invalidation ${invalidation}`, `TP1 ${targets[0] ?? 'n/a'}`)
          : `Execution map pending, ${validSeriesPoints} valid points, need at least ${MIN_ALPHA_RADAR_MARKET_SERIES_SAMPLES}.`,
        ...actionabilityInputs.notes.map((note) => note.replace(/\.$/, '')).slice(0, 2),
        ...symbolObservations.slice(0, 2).map((item) => item.title),
      ].slice(0, 5),
      trigger,
      invalidation,
      targets,
      expectedRr,
      rotationAction,
      rotationSummary: openPosition
        ? `${symbol} is already in the book. Only rotate if this setup is clearly better.`
        : rotationAssessment.summary,
      thesis: verdict === 'watch_breakout'
        ? `${symbol} is showing early structure. Watch for a cleaner breakout and follow-through before treating it as actionable.`
        : `${symbol} has enough confirmation plus breakout follow-through to justify a trigger-based idea.`,
      assetTags: ideaAssetTags,
      topicTags: ideaTopicTags,
      supportingObservationIds: symbolObservations.map((item) => item.id),
      supportingObservationTitles: symbolObservations.map((item) => item.title),
      primarySource: primaryObservation?.source ?? symbolObservations[0]?.source,
      marketStructure,
      confirmation: {
        sourceCount: confirmedSources.length,
        sourceTypeCount: confirmedSourceTypes.length,
        layerCount: confirmedLayers.length,
        sourceClassCount: confirmedSourceClasses.length,
        primaryCount,
        crossTypeConfirmed: effectiveCrossTypeConfirmed,
        crossLayerConfirmed,
        crossClassConfirmed: effectiveCrossClassConfirmed,
        sourceTypes: confirmedSourceTypes,
        sourceLayers: confirmedLayers,
        sourceClasses: confirmedSourceClasses,
      },
      actionabilityInputs,
      rotationContext: rotationAssessment.context,
      hypothesisVersion: 'ar-6.0',
      warnings,
      asOf: input.nowIso,
    });
  }

  const ranked = ideas
    .filter((item) => item.score >= input.settings.minIdeaScore || item.verdict === 'watch_breakout')
    .sort((a, b) => b.score - a.score || String(a.symbol).localeCompare(String(b.symbol)))
    .slice(0, input.settings.maxIdeasPerCycle);

  if (ranked.length > 0) return ranked;

  return [{
    id: `idea-cash-${input.nowIso}`,
    score: 0.4,
    observationQualityScore: 0.4,
    tradeActionabilityScore: 0.3,
    verdict: 'cash',
    signalFamily: 'cash',
    actionability: {
      actionable: false,
      summary: 'No actionable setup, stay in cash.',
      blockers: ['Observation quality and trade actionability did not align strongly enough.'],
    },
    title: 'Cash is best',
    whyNow: ['No symbol cleared the Alpha Radar confidence threshold.', 'Observation quality and short-term market actionability did not align strongly enough to justify a fresh hypothesis entry.'],
    targets: [],
    rotationAction: 'cash',
    rotationSummary: 'Keep current book unchanged or stay flat until a stronger dislocation appears.',
    thesis: 'No ranked opportunity beats the current uncertainty-adjusted threshold.',
    assetTags: [],
    topicTags: [],
    supportingObservationIds: [],
    supportingObservationTitles: [],
    primarySource: undefined,
    confirmation: {
      sourceCount: 0,
      sourceTypeCount: 0,
      layerCount: 0,
      sourceClassCount: 0,
      primaryCount: 0,
      crossTypeConfirmed: false,
      crossLayerConfirmed: false,
      crossClassConfirmed: false,
      sourceTypes: [],
      sourceLayers: [],
      sourceClasses: [],
    },
    actionabilityInputs: { notes: [] },
    rotationContext: { openRiskCount: input.positions.filter((position) => position.status === 'open').length },
    hypothesisVersion: 'ar-6.0',
    warnings: ['Wait for better quality or fresher catalysts.'],
    asOf: input.nowIso,
  }];
}

const US_CASH_SESSION_TIMEZONE = 'America/New_York';
const US_CASH_SESSION_OPEN_MINUTES = 9 * 60 + 30;
const US_CASH_SESSION_CLOSE_MINUTES = 16 * 60;
const ALPHA_RADAR_MONITORING_REALTIME_STALE_MS = 45 * 60_000;
const ALPHA_RADAR_MONITORING_HOURLY_STALE_MS = 135 * 60_000;
const ALPHA_RADAR_MONITORING_REALTIME_CARRY_MS = 2 * 60 * 60_000;
const ALPHA_RADAR_MONITORING_HOURLY_CARRY_MS = 3 * 60 * 60_000;

function zonedDateParts(date: Date, timeZone: string): { year: number; month: number; day: number; hour: number; minute: number; second: number; weekday: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    weekday: 'short',
    hour12: false,
  }).formatToParts(date);
  const pick = (type: string) => Number(parts.find((item) => item.type === type)?.value ?? 0);
  const weekdayToken = parts.find((item) => item.type === 'weekday')?.value ?? 'Sun';
  const weekdayMap: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  return {
    year: pick('year'),
    month: pick('month'),
    day: pick('day'),
    hour: pick('hour'),
    minute: pick('minute'),
    second: pick('second'),
    weekday: weekdayMap[weekdayToken] ?? 0,
  };
}

function zonedLocalToUtcIso(input: { year: number; month: number; day: number; hour: number; minute: number; second?: number }, timeZone: string): string {
  let guess = Date.UTC(input.year, input.month - 1, input.day, input.hour, input.minute, input.second ?? 0);
  const target = Date.UTC(input.year, input.month - 1, input.day, input.hour, input.minute, input.second ?? 0);
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const parts = zonedDateParts(new Date(guess), timeZone);
    const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
    const diff = asUtc - target;
    if (diff === 0) break;
    guess -= diff;
  }
  return new Date(guess).toISOString();
}

function shiftZonedDate(input: { year: number; month: number; day: number }, deltaDays: number, timeZone: string): { year: number; month: number; day: number; weekday: number } {
  const noonIso = zonedLocalToUtcIso({ ...input, hour: 12, minute: 0, second: 0 }, timeZone);
  const shifted = zonedDateParts(new Date(Date.parse(noonIso) + deltaDays * 24 * 60 * 60_000), timeZone);
  return { year: shifted.year, month: shifted.month, day: shifted.day, weekday: shifted.weekday };
}

function nearestUsCashBusinessDate(input: { year: number; month: number; day: number; weekday: number }, direction: -1 | 1): { year: number; month: number; day: number; weekday: number } {
  let cursor = shiftZonedDate(input, direction, US_CASH_SESSION_TIMEZONE);
  while (cursor.weekday === 0 || cursor.weekday === 6) {
    cursor = shiftZonedDate(cursor, direction, US_CASH_SESSION_TIMEZONE);
  }
  return cursor;
}

function buildUsCashSessionWindow(nowIso: string): {
  state: 'open' | 'closed';
  sessionOpenAt: string;
  sessionCloseAt: string;
  previousSessionCloseAt: string;
  nextSessionOpenAt: string;
} {
  const nowDate = new Date(nowIso);
  const local = zonedDateParts(nowDate, US_CASH_SESSION_TIMEZONE);
  const today = { year: local.year, month: local.month, day: local.day, weekday: local.weekday };
  const currentMinutes = local.hour * 60 + local.minute;
  const isBusinessDay = local.weekday >= 1 && local.weekday <= 5;
  const todayOpenAt = zonedLocalToUtcIso({ ...today, hour: 9, minute: 30, second: 0 }, US_CASH_SESSION_TIMEZONE);
  const todayCloseAt = zonedLocalToUtcIso({ ...today, hour: 16, minute: 0, second: 0 }, US_CASH_SESSION_TIMEZONE);

  if (isBusinessDay && currentMinutes >= US_CASH_SESSION_OPEN_MINUTES && currentMinutes < US_CASH_SESSION_CLOSE_MINUTES) {
    const previousBusiness = nearestUsCashBusinessDate(today, -1);
    return {
      state: 'open',
      sessionOpenAt: todayOpenAt,
      sessionCloseAt: todayCloseAt,
      previousSessionCloseAt: zonedLocalToUtcIso({ ...previousBusiness, hour: 16, minute: 0, second: 0 }, US_CASH_SESSION_TIMEZONE),
      nextSessionOpenAt: todayOpenAt,
    };
  }

  const lastBusiness = isBusinessDay && currentMinutes >= US_CASH_SESSION_CLOSE_MINUTES
    ? today
    : nearestUsCashBusinessDate(today, -1);
  const nextBusiness = isBusinessDay && currentMinutes < US_CASH_SESSION_OPEN_MINUTES
    ? today
    : nearestUsCashBusinessDate(today, 1);

  return {
    state: 'closed',
    sessionOpenAt: zonedLocalToUtcIso({ ...lastBusiness, hour: 9, minute: 30, second: 0 }, US_CASH_SESSION_TIMEZONE),
    sessionCloseAt: zonedLocalToUtcIso({ ...lastBusiness, hour: 16, minute: 0, second: 0 }, US_CASH_SESSION_TIMEZONE),
    previousSessionCloseAt: zonedLocalToUtcIso({ ...lastBusiness, hour: 16, minute: 0, second: 0 }, US_CASH_SESSION_TIMEZONE),
    nextSessionOpenAt: zonedLocalToUtcIso({ ...nextBusiness, hour: 9, minute: 30, second: 0 }, US_CASH_SESSION_TIMEZONE),
  };
}

function monitoringFreshnessPolicyMs(details?: Record<string, unknown>): { liveMs: number; carryMs: number; mode: 'near_realtime' | 'hourly_fallback' } {
  const monitoringMode = String(details?.monitoringMode ?? '').trim().toLowerCase();
  if (monitoringMode === 'near_realtime') {
    return {
      liveMs: ALPHA_RADAR_MONITORING_REALTIME_STALE_MS,
      carryMs: ALPHA_RADAR_MONITORING_REALTIME_CARRY_MS,
      mode: 'near_realtime',
    };
  }
  return {
    liveMs: ALPHA_RADAR_MONITORING_HOURLY_STALE_MS,
    carryMs: ALPHA_RADAR_MONITORING_HOURLY_CARRY_MS,
    mode: 'hourly_fallback',
  };
}

export function applyAlphaRadarMonitoringFreshnessPolicy(input: { nowIso: string; health: AlphaRadarSourceHealth }): AlphaRadarSourceHealth {
  const details = input.health.details && typeof input.health.details === 'object'
    ? { ...input.health.details }
    : {};
  const monitoringOnly = details.monitoringOnly === true;
  const monitoringGroup = String(details.monitoringGroup ?? '').trim();
  if (!monitoringOnly) {
    return input.health;
  }

  const monitoringMode = String(details.monitoringMode ?? '').trim().toLowerCase();
  const nowDate = new Date(input.nowIso);
  const isWeekendCarryWindow = monitoringGroup === 'macro'
    && (monitoringMode === 'hourly_fallback' || monitoringMode === 'near_realtime')
    && (nowDate.getUTCDay() === 6 || nowDate.getUTCDay() === 0);
  const lastObservedAt = input.health.lastObservedAt;
  const lastObservedMs = lastObservedAt ? Date.parse(lastObservedAt) : NaN;
  const nowMs = Date.parse(input.nowIso);
  const weekendCarryMs = 72 * 60 * 60_000;

  if (isWeekendCarryWindow) {
    const ageMs = Number.isFinite(lastObservedMs) ? Math.max(0, nowMs - lastObservedMs) : undefined;
    const stale = !Number.isFinite(lastObservedMs) || (ageMs ?? weekendCarryMs + 1) > weekendCarryMs;
    return {
      ...input.health,
      ageMs,
      stale,
      status: stale ? (input.health.itemCount === 0 ? 'inactive' : 'stale') : 'fresh',
      details: {
        ...details,
        freshnessMinutes: ageMs === undefined ? undefined : Number((ageMs / 60_000).toFixed(2)),
        sessionState: 'weekend_carry',
        freshnessMode: monitoringMode || 'hourly_fallback',
        freshnessNote: stale
          ? 'Weekend carry expired before the next macro session reopen.'
          : `Macro monitor is carrying the latest ${monitoringMode === 'near_realtime' ? 'near-real-time' : 'hourly'} print through the weekend closure.`,
      },
    };
  }

  if (monitoringGroup !== 'equity' && monitoringGroup !== 'proxy') {
    return {
      ...input.health,
      details: {
        ...details,
        sessionState: 'continuous',
        freshnessNote: input.health.status === 'fresh'
          ? 'Continuous monitor, freshness follows rolling quote age.'
          : input.health.status === 'inactive'
            ? 'Continuous monitor has not produced a quote yet.'
            : 'Continuous monitor exceeded its rolling freshness budget.',
      },
    };
  }

  const session = buildUsCashSessionWindow(input.nowIso);
  const policy = monitoringFreshnessPolicyMs(details);
  const ageMs = Number.isFinite(lastObservedMs) ? Math.max(0, nowMs - lastObservedMs) : undefined;

  if (!Number.isFinite(lastObservedMs)) {
    return {
      ...input.health,
      stale: true,
      status: 'inactive',
      details: {
        ...details,
        sessionState: session.state === 'open' ? 'us_cash_open' : 'us_cash_closed',
        sessionLabel: 'US cash session',
        nextExpectedAt: session.state === 'open' ? input.nowIso : session.nextSessionOpenAt,
        freshnessMode: policy.mode,
        freshnessNote: session.state === 'open'
          ? 'US cash session is open and this monitor has no quote yet.'
          : `US cash session is closed, carrying no quote into the next open at ${session.nextSessionOpenAt}.`,
      },
    };
  }

  if (session.state === 'open') {
    const stale = (ageMs ?? policy.liveMs + 1) > policy.liveMs;
    return {
      ...input.health,
      ageMs,
      stale,
      status: stale ? 'stale' : 'fresh',
      details: {
        ...details,
        freshnessMinutes: ageMs === undefined ? undefined : Number((ageMs / 60_000).toFixed(2)),
        sessionState: 'us_cash_open',
        sessionLabel: 'US cash session',
        nextExpectedAt: new Date(lastObservedMs + policy.liveMs).toISOString(),
        freshnessMode: policy.mode,
        freshnessNote: stale
          ? `US cash session is open and the monitor has not refreshed inside its ${Math.round(policy.liveMs / 60_000)} minute budget.`
          : 'US cash session is open and the monitor is updating inside its freshness budget.',
      },
    };
  }

  const carryStartMs = Date.parse(session.previousSessionCloseAt) - policy.carryMs;
  const stale = lastObservedMs < carryStartMs;
  return {
    ...input.health,
    ageMs,
    stale,
    status: stale ? (input.health.itemCount === 0 ? 'inactive' : 'stale') : 'fresh',
    details: {
      ...details,
      freshnessMinutes: ageMs === undefined ? undefined : Number((ageMs / 60_000).toFixed(2)),
      sessionState: 'us_cash_closed',
      sessionLabel: 'US cash session',
      nextExpectedAt: session.nextSessionOpenAt,
      freshnessMode: policy.mode,
      freshnessNote: stale
        ? 'US cash session is closed, but the last monitor print predates the prior close window.'
        : `US cash session is closed, carrying the latest monitor print until the next open at ${session.nextSessionOpenAt}.`,
    },
  };
}

export function buildAlphaRadarSourceHealth(input: {
  observations: AlphaRadarObservation[];
  nowIso: string;
  expectedSources?: Array<{ source: string; kind: AlphaRadarObservationKind; sourceType?: AlphaRadarSourceType; sourceLayer?: AlphaRadarSourceLayer; sourceClass?: AlphaRadarSourceClass; sourceWeight?: number; details?: Record<string, unknown> }>;
  staleAfterMsByKind?: Partial<Record<AlphaRadarObservationKind, number>>;
}): AlphaRadarSourceHealth[] {
  type ExpectedSource = { source: string; kind: AlphaRadarObservationKind; sourceType?: AlphaRadarSourceType; sourceLayer?: AlphaRadarSourceLayer; sourceClass?: AlphaRadarSourceClass; sourceWeight?: number; details?: Record<string, unknown> };
  const nowMs = Date.parse(input.nowIso);
  const staleAfterMsByKind: Record<AlphaRadarObservationKind, number> = {
    market: input.staleAfterMsByKind?.market ?? 5 * 60_000,
    external: input.staleAfterMsByKind?.external ?? 6 * 60 * 60_000,
  };
  const bySource = new Map<string, AlphaRadarObservation[]>();
  for (const observation of input.observations) {
    const key = `${observation.kind}:${observation.source}`;
    const list = bySource.get(key) ?? [];
    list.push(observation);
    bySource.set(key, list);
  }

  const keys = new Set<string>([
    ...bySource.keys(),
    ...(input.expectedSources ?? []).map((item) => `${item.kind}:${item.source}`),
  ]);
  const expectedSourceByKey = new Map<string, ExpectedSource>((input.expectedSources ?? []).map((item) => [`${item.kind}:${item.source}`, item]));

  return [...keys].map((key) => {
    const [kind, ...sourceParts] = key.split(':');
    const source = sourceParts.join(':');
    const rows = (bySource.get(key) ?? []).slice().sort((a, b) => b.observedAt.localeCompare(a.observedAt));
    const expected = expectedSourceByKey.get(key);
    const latestRow = rows[0];
    const lastObservedAt = latestRow?.observedAt;
    const ageMs = lastObservedAt ? Math.max(0, nowMs - Date.parse(lastObservedAt)) : undefined;
    const stale = ageMs === undefined ? true : ageMs > staleAfterMsByKind[kind as AlphaRadarObservationKind];
    const rowMetadata = latestRow?.metadata as { monitoringOnly?: unknown; monitoringGroup?: unknown } | undefined;
    const expectedDetails = expected?.details as { monitoringOnly?: unknown; monitoringGroup?: unknown; enabled?: unknown } | undefined;
    const monitoringOnly = rowMetadata?.monitoringOnly === true || expectedDetails?.monitoringOnly === true;
    const monitoringGroup = String(rowMetadata?.monitoringGroup ?? expectedDetails?.monitoringGroup ?? '');
    const sourceType = latestRow?.sourceType ?? expected?.sourceType;
    const explicitlyDisabled = expectedDetails?.enabled === false;
    const connectorBackedSocialObservation = sourceType === 'social' && !source.startsWith('connector:');
    const alertable = !explicitlyDisabled && !connectorBackedSocialObservation;
    const hasExpectedDetails = Object.keys(expected?.details ?? {}).length > 0;
    const details = rows.length === 0 && !monitoringOnly && !monitoringGroup && alertable && !hasExpectedDetails
      ? undefined
      : {
        ...(expected?.details ?? {}),
        ...((latestRow?.metadata ?? {}) as Record<string, unknown>),
        duplicateRate: rows.length === 0
          ? 0
          : Number((rows.filter((row) => Number((row.metadata as { dedupeMergedCount?: unknown } | undefined)?.dedupeMergedCount) > 0).length / rows.length).toFixed(4)),
        latestClusterId: String((latestRow?.metadata as { clusterId?: unknown } | undefined)?.clusterId ?? ''),
        freshnessMinutes: ageMs === undefined ? undefined : Number((ageMs / 60_000).toFixed(2)),
        confirmationSourceTypes: uniqueStringArray((latestRow?.metadata as { confirmedBySourceTypes?: unknown } | undefined)?.confirmedBySourceTypes).length,
        confirmationLayers: uniqueStringArray((latestRow?.metadata as { confirmedByLayers?: unknown } | undefined)?.confirmedByLayers).length,
        confirmationSourceClasses: uniqueStringArray((latestRow?.metadata as { confirmedBySourceClasses?: unknown } | undefined)?.confirmedBySourceClasses).length,
        monitoringOnly,
        monitoringGroup,
        alertable,
        enabled: expectedDetails?.enabled !== false,
      } satisfies Record<string, unknown>;
    return {
      source,
      kind: kind as AlphaRadarObservationKind,
      lastObservedAt,
      ageMs,
      stale,
      itemCount: rows.length,
      status: rows.length === 0 ? 'inactive' : stale ? 'stale' : 'fresh',
      sourceType: latestRow?.sourceType ?? expected?.sourceType,
      sourceLayer: latestRow?.sourceLayer ?? expected?.sourceLayer,
      sourceClass: latestRow?.sourceClass ?? expected?.sourceClass,
      sourceWeight: latestRow?.sourceWeight ?? expected?.sourceWeight,
      details,
    } satisfies AlphaRadarSourceHealth;
  }).sort((a, b) => a.kind.localeCompare(b.kind) || a.source.localeCompare(b.source));
}

export function applyConnectedIdleSourceHealthPolicy(input: { nowIso: string; health: AlphaRadarSourceHealth }): AlphaRadarSourceHealth {
  if (input.health.status !== 'inactive' || input.health.itemCount !== 0) return input.health;
  const details = input.health.details && typeof input.health.details === 'object'
    ? { ...input.health.details }
    : {};
  if (details.connected !== true) return input.health;
  const lastConnectedAt = typeof details.lastConnectedAt === 'string' ? details.lastConnectedAt : undefined;
  const runtimeAgeMs = lastConnectedAt ? Math.max(0, Date.parse(input.nowIso) - Date.parse(lastConnectedAt)) : undefined;
  return {
    ...input.health,
    ageMs: runtimeAgeMs,
    stale: false,
    status: 'fresh',
    details: {
      ...details,
      runtimeState: 'connected_idle',
      freshnessMinutes: runtimeAgeMs === undefined ? undefined : Number((runtimeAgeMs / 60_000).toFixed(2)),
      freshnessNote: 'Source runtime is connected and idle, waiting for the first payload.',
    },
  };
}
