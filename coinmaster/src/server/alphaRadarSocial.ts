import type { AlphaRadarConnectorSettings, AlphaRadarConnectorState, AlphaRadarConnectorType } from '../shared/dto.js';
import { extractRssItems } from './alphaRadar.js';
import { alphaRadarFetchJson, alphaRadarFetchText } from './alphaRadarHttp.js';
import { collectTelegramConnector } from './alphaRadarTelegram.js';

export interface AlphaRadarSocialCandidate {
  connectorType: AlphaRadarConnectorType;
  source: string;
  title: string;
  excerpt: string;
  observedAt?: string;
  sentimentScore?: number;
  noveltyScore?: number;
  urgencyScore?: number;
  marketAlignmentScore?: number;
  assetTags?: string[];
  topicTags?: string[];
  provenance?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface AlphaRadarSocialCollectorResult {
  type: AlphaRadarConnectorType;
  state: AlphaRadarConnectorState;
  candidates: AlphaRadarSocialCandidate[];
  fetchedSources: string[];
}

const USER_AGENT = 'coinmaster-alpha-radar/5.5.1';
const REDDIT_POST_LIMIT = 12;

function normalizeWatchItem(value: string): string {
  return value.trim().replace(/^https?:\/\/(?:www\.)?/i, '').replace(/\/$/, '');
}

function connectorState(base: AlphaRadarConnectorSettings, patch: Partial<AlphaRadarConnectorState>): AlphaRadarConnectorState {
  return {
    ...base.state,
    configured: base.watchlist.length > 0,
    needsAuth: false,
    status: base.watchlist.length > 0 ? 'connected' : 'idle',
    lastSyncStatus: 'pending',
    ...patch,
  };
}

function clampUnit(value: number): number {
  return Number(Math.max(-1, Math.min(1, value)).toFixed(4));
}

function clamp01(value: number): number {
  return Number(Math.max(0, Math.min(1, value)).toFixed(4));
}

function applyWeight(base: number, weight: number | undefined, floor = 0): number {
  const multiplier = Math.max(0.25, Math.min(2, Number(weight) || 1));
  return clamp01(Math.max(floor, base * multiplier));
}

function sentimentFromText(text: string): number {
  if (/\b(?:approval|approved|launch|listing|listed|partnership|integration|buyback|breakout|inflow|mainnet|upgrade)\b/i.test(text)) return 0.58;
  if (/\b(?:hack|exploit|breach|lawsuit|delay|ban|drain|outflow|liquidation|rug)\b/i.test(text)) return -0.62;
  return 0;
}

function topicTagsFromText(text: string, seed: string[]): string[] {
  const next = new Set(seed);
  if (/\b(?:reddit|subreddit)\b/i.test(text)) next.add('reddit');
  if (/\b(?:bluesky|atproto|at protocol)\b/i.test(text)) next.add('bluesky');
  if (/\b(?:airdrop|token generation|tge)\b/i.test(text)) next.add('token');
  if (/\b(?:etf)\b/i.test(text)) next.add('etf');
  if (/\b(?:listing|listed|launch)\b/i.test(text)) next.add('listing');
  if (/\b(?:hack|exploit|breach|drain)\b/i.test(text)) next.add('security');
  return [...next];
}

function normalizeRedditWatchlistItem(item: string): { subreddit: string; label: string } | null {
  const normalized = normalizeWatchItem(item)
    .replace(/^reddit\.com\//i, '')
    .replace(/^r\//i, '')
    .replace(/\.json$/i, '')
    .split(/[/?#]/)[0] ?? '';
  const subreddit = normalized.replace(/[^A-Za-z0-9_]/g, '').trim();
  if (!subreddit) return null;
  return { subreddit, label: `r/${subreddit}` };
}

function normalizeBlueskyActor(item: string): { actor: string; label: string } | null {
  const normalized = normalizeWatchItem(item)
    .replace(/^bsky\.app\/profile\//i, '')
    .split(/[/?#]/)[0] ?? '';
  const actor = normalized.trim();
  if (!actor) return null;
  return { actor, label: actor };
}

function normalizeObservedAt(value: string | undefined): string | undefined {
  const normalized = String(value ?? '').trim();
  if (!normalized) return undefined;
  const parsed = Date.parse(normalized);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function buildRedditCandidate(input: {
  settings: AlphaRadarConnectorSettings;
  watchLabel: string;
  subreddit: string;
  title: string;
  excerpt: string;
  observedAt?: string;
  author?: string;
  url: string;
  score?: number;
  comments?: number;
  over18?: boolean;
  fetchMode: 'json' | 'atom';
}): AlphaRadarSocialCandidate {
  const text = `${input.title} ${input.excerpt}`;
  const observedAt = normalizeObservedAt(input.observedAt);
  const ageHours = observedAt ? Math.max(0, (Date.now() - Date.parse(observedAt)) / 36e5) : null;
  const noveltyBase = Number.isFinite(input.score)
    ? input.score! >= 50 ? 0.74 : input.score! >= 15 ? 0.66 : 0.54
    : input.excerpt.length >= 180 ? 0.7 : input.title.length >= 90 ? 0.64 : 0.56;
  const urgencyBase = Number.isFinite(input.comments)
    ? input.comments! >= 20 ? 0.78 : input.comments! >= 5 ? 0.68 : 0.52
    : ageHours === null ? 0.56 : ageHours <= 6 ? 0.76 : ageHours <= 24 ? 0.66 : 0.54;

  return {
    connectorType: 'reddit',
    source: 'social_reddit',
    title: input.title,
    excerpt: input.excerpt,
    observedAt,
    sentimentScore: clampUnit(sentimentFromText(text)),
    noveltyScore: applyWeight(noveltyBase, input.settings.weight, 0.35),
    urgencyScore: applyWeight(urgencyBase, input.settings.weight, 0.3),
    marketAlignmentScore: applyWeight(/\b(?:bitcoin|ethereum|solana|hyperliquid|etf|listing|funding|perp|sec|stablecoin)\b/i.test(text) ? 0.62 : 0.42, input.settings.weight, 0.25),
    topicTags: topicTagsFromText(text, ['reddit', input.subreddit.toLowerCase()]),
    provenance: {
      sourceLabel: input.settings.sourceLabel || 'Reddit watchlists',
      publisher: input.watchLabel,
      author: input.author,
      url: input.url,
      publishedAt: observedAt,
      ingestedAt: new Date().toISOString(),
    },
    metadata: {
      connectorType: 'reddit',
      watchlist: input.watchLabel,
      score: input.score,
      numComments: input.comments,
      over18: input.over18,
      permalink: input.url,
      fetchMode: input.fetchMode,
    },
  };
}

async function fetchRedditJsonCandidates(settings: AlphaRadarConnectorSettings, watch: { subreddit: string; label: string }): Promise<AlphaRadarSocialCandidate[]> {
  const url = `https://www.reddit.com/r/${encodeURIComponent(watch.subreddit)}/new.json?limit=${REDDIT_POST_LIMIT}&raw_json=1`;
  const payload = await alphaRadarFetchJson<{ data?: { children?: Array<{ data?: Record<string, unknown> }> } }>(url, { headers: { 'user-agent': USER_AGENT, accept: 'application/json' } });
  const rows = Array.isArray(payload?.data?.children) ? payload.data.children : [];

  return rows.map((row) => {
    const data = row?.data ?? {};
    const title = String(data.title ?? '').trim();
    const selftext = String(data.selftext ?? '').replace(/\s+/g, ' ').trim();
    if (!title) return null;
    const permalink = String(data.permalink ?? '').trim();
    const urlValue = permalink ? `https://www.reddit.com${permalink}` : `https://www.reddit.com/r/${watch.subreddit}`;
    return buildRedditCandidate({
      settings,
      watchLabel: watch.label,
      subreddit: watch.subreddit,
      title,
      excerpt: selftext || title,
      observedAt: typeof data.created_utc === 'number' ? new Date(data.created_utc * 1000).toISOString() : undefined,
      author: String(data.author ?? '').trim() || undefined,
      url: urlValue,
      score: Number(data.score ?? 0),
      comments: Number(data.num_comments ?? 0),
      over18: data.over_18 === true,
      fetchMode: 'json',
    });
  }).filter((item): item is AlphaRadarSocialCandidate => Boolean(item));
}

async function fetchRedditAtomCandidates(settings: AlphaRadarConnectorSettings, watch: { subreddit: string; label: string }): Promise<AlphaRadarSocialCandidate[]> {
  const url = `https://www.reddit.com/r/${encodeURIComponent(watch.subreddit)}/new/.rss?limit=${REDDIT_POST_LIMIT}`;
  const xml = await alphaRadarFetchText(url, { headers: { 'user-agent': USER_AGENT, accept: 'application/atom+xml, application/xml, text/xml' } });
  const items = extractRssItems(xml).slice(0, REDDIT_POST_LIMIT);

  return items.map((item) => {
    const title = String(item.title ?? '').trim();
    const excerpt = String(item.excerpt ?? '').trim() || title;
    if (!title) return null;
    return buildRedditCandidate({
      settings,
      watchLabel: watch.label,
      subreddit: watch.subreddit,
      title,
      excerpt,
      observedAt: item.observedAt,
      author: item.sourceName,
      url: item.link || `https://www.reddit.com/r/${watch.subreddit}`,
      fetchMode: 'atom',
    });
  }).filter((item): item is AlphaRadarSocialCandidate => Boolean(item));
}

export async function collectTelegramAuthReadyConnector(settings: AlphaRadarConnectorSettings): Promise<AlphaRadarSocialCollectorResult> {
  const result = await collectTelegramConnector(settings);
  return {
    type: 'telegram',
    fetchedSources: result.fetchedSources,
    candidates: result.candidates,
    state: connectorState(settings, result.state),
  };
}

export async function collectRedditConnector(settings: AlphaRadarConnectorSettings): Promise<AlphaRadarSocialCollectorResult> {
  if (!settings.enabled) {
    return { type: 'reddit', fetchedSources: [], candidates: [], state: connectorState(settings, { status: 'idle', lastSyncStatus: 'pending', message: 'Disabled', connectionLabel: 'Off' }) };
  }
  if (settings.watchlist.length === 0) {
    return { type: 'reddit', fetchedSources: [], candidates: [], state: connectorState(settings, { status: 'idle', lastSyncStatus: 'pending', message: 'Add subreddits like r/CryptoCurrency or bitcoin.', connectionLabel: 'No watchlist' }) };
  }

  const candidates: AlphaRadarSocialCandidate[] = [];
  const fetchedSources: string[] = [];
  let atomFallbackCount = 0;

  for (const rawItem of settings.watchlist) {
    const watch = normalizeRedditWatchlistItem(rawItem);
    if (!watch) continue;
    fetchedSources.push(watch.label);
    try {
      candidates.push(...await fetchRedditJsonCandidates(settings, watch));
    } catch (jsonError) {
      try {
        candidates.push(...await fetchRedditAtomCandidates(settings, watch));
        atomFallbackCount += 1;
      } catch (atomError) {
        const primary = jsonError instanceof Error ? jsonError.message : String(jsonError);
        const fallback = atomError instanceof Error ? atomError.message : String(atomError);
        throw new Error(`${primary}; reddit_atom_fallback_failed:${fallback}`);
      }
    }
  }

  return {
    type: 'reddit',
    fetchedSources,
    candidates,
    state: connectorState(settings, {
      status: 'connected',
      needsAuth: false,
      lastSyncAt: new Date().toISOString(),
      lastSyncStatus: 'success',
      connectionLabel: fetchedSources.length > 0 ? fetchedSources.slice(0, 2).join(', ') : 'Configured',
      message: fetchedSources.length > 0
        ? `Public-read active across ${fetchedSources.length} subreddit${fetchedSources.length === 1 ? '' : 's'}${atomFallbackCount > 0 ? ` (${atomFallbackCount} via Atom fallback)` : ''}.`
        : 'No valid subreddit watchlists.',
      error: undefined,
    }),
  };
}

export async function collectBlueskyConnector(settings: AlphaRadarConnectorSettings): Promise<AlphaRadarSocialCollectorResult> {
  if (!settings.enabled) {
    return { type: 'bluesky', fetchedSources: [], candidates: [], state: connectorState(settings, { status: 'idle', lastSyncStatus: 'pending', message: 'Disabled', connectionLabel: 'Off' }) };
  }
  if (settings.watchlist.length === 0) {
    return { type: 'bluesky', fetchedSources: [], candidates: [], state: connectorState(settings, { status: 'idle', lastSyncStatus: 'pending', message: 'Add Bluesky handles or DIDs.', connectionLabel: 'No watchlist' }) };
  }

  const candidates: AlphaRadarSocialCandidate[] = [];
  const fetchedSources: string[] = [];

  for (const rawItem of settings.watchlist) {
    const watch = normalizeBlueskyActor(rawItem);
    if (!watch) continue;
    const url = `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=${encodeURIComponent(watch.actor)}&limit=12`;
    const payload = await alphaRadarFetchJson<{ feed?: Array<Record<string, unknown>> }>(url, { headers: { 'user-agent': USER_AGENT, accept: 'application/json' } });
    fetchedSources.push(watch.label);
    const rows = Array.isArray(payload?.feed) ? payload.feed : [];

    for (const row of rows) {
      const post = (row.post && typeof row.post === 'object' ? row.post as Record<string, unknown> : {}) as Record<string, unknown>;
      const record = (post.record && typeof post.record === 'object' ? post.record as Record<string, unknown> : {}) as Record<string, unknown>;
      const author = (post.author && typeof post.author === 'object' ? post.author as Record<string, unknown> : {}) as Record<string, unknown>;
      const text = String(record.text ?? '').replace(/\s+/g, ' ').trim();
      if (!text) continue;
      const labels = Array.isArray(row.reason) ? row.reason : undefined;
      const uri = String(post.uri ?? '').trim();
      const did = String(author.did ?? '').trim();
      const handle = String(author.handle ?? watch.actor).trim();
      candidates.push({
        connectorType: 'bluesky',
        source: 'social_bluesky',
        title: text.slice(0, 240),
        excerpt: text,
        observedAt: String(record.createdAt ?? post.indexedAt ?? '').trim() || undefined,
        sentimentScore: clampUnit(sentimentFromText(text)),
        noveltyScore: applyWeight(text.length >= 180 ? 0.76 : 0.64, settings.weight, 0.38),
        urgencyScore: applyWeight(/\b(?:now|today|breaking|just|alert)\b/i.test(text) ? 0.78 : 0.6, settings.weight, 0.32),
        marketAlignmentScore: applyWeight(/\b(?:bitcoin|ethereum|solana|hyperliquid|btc|eth|sol|hype|perp|funding|etf|listing|stablecoin)\b/i.test(text) ? 0.68 : 0.44, settings.weight, 0.25),
        topicTags: topicTagsFromText(text, ['bluesky']),
        provenance: {
          sourceLabel: settings.sourceLabel || 'Bluesky watchlists',
          publisher: handle,
          author: handle,
          url: did && uri ? `https://bsky.app/profile/${did}/post/${uri.split('/').pop()}` : `https://bsky.app/profile/${handle}`,
          publishedAt: String(record.createdAt ?? post.indexedAt ?? '').trim() || undefined,
          ingestedAt: new Date().toISOString(),
        },
        metadata: {
          connectorType: 'bluesky',
          watchlist: watch.label,
          handle,
          did: did || undefined,
          uri: uri || undefined,
          indexedAt: String(post.indexedAt ?? '').trim() || undefined,
          labels,
        },
      });
    }
  }

  return {
    type: 'bluesky',
    fetchedSources,
    candidates,
    state: connectorState(settings, {
      status: 'connected',
      needsAuth: false,
      lastSyncAt: new Date().toISOString(),
      lastSyncStatus: 'success',
      connectionLabel: fetchedSources.length > 0 ? fetchedSources.slice(0, 2).join(', ') : 'Configured',
      message: fetchedSources.length > 0 ? `Public-read active across ${fetchedSources.length} Bluesky source${fetchedSources.length === 1 ? '' : 's'}.` : 'No valid Bluesky watchlists.',
      error: undefined,
    }),
  };
}
