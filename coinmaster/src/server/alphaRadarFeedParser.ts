import { Readable } from 'node:stream';

import FeedParser from 'feedparser';

export interface AlphaRadarFeedParsedItem {
  title: string;
  excerpt: string;
  link?: string;
  observedAt?: string;
  sourceName?: string;
  author?: string;
  externalId?: string;
  canonicalUrl?: string;
  rawPayloadRef?: string;
  metadata?: Record<string, unknown>;
}

const FEEDPARSER_TIMEOUT_MS = 1_500;
const MAX_ITEMS = 30;
const MAX_RAW_PAYLOAD_REF_CHARS = 1_200;

function decodeHtml(text: string): string {
  return text
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

function compactRawPayloadRef(xml: string): string {
  const compact = xml.replace(/\s+/g, ' ').trim();
  return compact.slice(0, MAX_RAW_PAYLOAD_REF_CHARS);
}

function normalizeTimestamp(value: unknown): string | undefined {
  const raw = String(value ?? '').trim();
  if (!raw) return undefined;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined;
}

function canonicalizeUrl(url: unknown): string | undefined {
  const raw = String(url ?? '').trim();
  if (!raw) return undefined;
  try {
    const parsed = new URL(raw);
    parsed.hash = '';
    for (const key of [...parsed.searchParams.keys()]) {
      if (/^(utm_|fbclid$|gclid$|mc_cid$|mc_eid$|ref$|ref_src$)/i.test(key)) {
        parsed.searchParams.delete(key);
      }
    }
    parsed.hostname = parsed.hostname.toLowerCase();
    if ((parsed.protocol === 'https:' && parsed.port === '443') || (parsed.protocol === 'http:' && parsed.port === '80')) {
      parsed.port = '';
    }
    return parsed.toString();
  } catch {
    return raw;
  }
}

function itemToParsedItem(item: FeedParser.Item, rawPayloadRef: string): AlphaRadarFeedParsedItem | null {
  const title = decodeHtml(String(item.title ?? ''));
  const excerpt = decodeHtml(String(item.summary || item.description || item.title || ''));
  if (!title || !excerpt) return null;
  const link = String(item.origlink || item.link || '').trim() || undefined;
  const sourceName = decodeHtml(String(item.source?.title || item.meta?.title || item.author || '')).trim() || undefined;
  const author = decodeHtml(String(item.author || '')).trim() || undefined;
  const externalId = String(item.guid || item.link || '').trim() || undefined;
  return {
    title,
    excerpt,
    link,
    observedAt: normalizeTimestamp(item.pubdate ?? item.date),
    sourceName,
    author,
    externalId,
    canonicalUrl: canonicalizeUrl(link),
    rawPayloadRef,
    metadata: {
      parser: 'feedparser',
      categories: Array.isArray(item.categories) ? item.categories.slice(0, 12) : [],
    },
  };
}

async function parseWithFeedparser(xml: string): Promise<AlphaRadarFeedParsedItem[]> {
  if (!xml.trim()) return [];
  const rawPayloadRef = compactRawPayloadRef(xml);
  return new Promise((resolve) => {
    const parser = new FeedParser({ normalize: true, addmeta: true, resume_saxerror: true });
    const items: AlphaRadarFeedParsedItem[] = [];
    let settled = false;

    const finish = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(items.slice(0, MAX_ITEMS));
    };

    const timer = setTimeout(finish, FEEDPARSER_TIMEOUT_MS);

    parser.on('readable', function onReadable(this: FeedParser) {
      let item: FeedParser.Item | null;
      while ((item = this.read()) && items.length < MAX_ITEMS) {
        const parsed = itemToParsedItem(item, rawPayloadRef);
        if (parsed) items.push(parsed);
      }
      if (items.length >= MAX_ITEMS) finish();
    });
    parser.on('error', finish);
    parser.on('end', finish);
    parser.on('finish', finish);

    Readable.from([xml]).on('error', finish).pipe(parser);
  });
}

function pickTag(chunk: string, tag: string): string {
  const match = chunk.match(new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tag}>`, 'i'));
  return match?.[1] ? decodeHtml(match[1]) : '';
}

function pickTagAttr(chunk: string, tag: string, attr: string): string {
  const match = chunk.match(new RegExp(`<${tag}[^>]*${attr}=["']([^"']+)["'][^>]*\\/?>`, 'i'));
  return match?.[1] ? decodeHtml(match[1]) : '';
}

function parseWithFallback(xml: string): AlphaRadarFeedParsedItem[] {
  const items = [...xml.matchAll(/<(?:item|entry)(?:\s[^>]*)?>([\s\S]*?)<\/(?:item|entry)>/gi)];
  return items.slice(0, MAX_ITEMS).map((match) => {
    const chunk = match[1] ?? '';
    const link = pickTag(chunk, 'link') || pickTagAttr(chunk, 'link', 'href') || undefined;
    return {
      title: pickTag(chunk, 'title'),
      excerpt: pickTag(chunk, 'description') || pickTag(chunk, 'content:encoded') || pickTag(chunk, 'content') || pickTag(chunk, 'summary') || pickTag(chunk, 'title'),
      link,
      observedAt: normalizeTimestamp(pickTag(chunk, 'pubDate') || pickTag(chunk, 'published') || pickTag(chunk, 'updated') || undefined),
      sourceName: pickTag(chunk, 'author') || pickTag(chunk, 'dc:creator') || undefined,
      author: pickTag(chunk, 'author') || pickTag(chunk, 'dc:creator') || undefined,
      externalId: pickTag(chunk, 'guid') || pickTag(chunk, 'id') || undefined,
      canonicalUrl: canonicalizeUrl(link),
      rawPayloadRef: compactRawPayloadRef(chunk || xml),
      metadata: { parser: 'regex-fallback' },
    };
  }).filter((item) => item.title && item.excerpt);
}

/**
 * Primary RSS/Atom parser for external feed collectors.
 * Uses the `feedparser` package and falls back to the old bounded parser only on parser failure.
 */
export async function extractRssItemsWithFeedparser(xml: string): Promise<AlphaRadarFeedParsedItem[]> {
  const parsed = await parseWithFeedparser(xml);
  return parsed.length > 0 ? parsed : parseWithFallback(xml);
}

/** Synchronous compatibility parser for call sites that cannot await (for example connector helpers). */
export function extractRssItems(xml: string): AlphaRadarFeedParsedItem[] {
  return parseWithFallback(xml);
}
