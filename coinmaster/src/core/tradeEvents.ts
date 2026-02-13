import { createHash } from 'node:crypto';
import { nanoid } from 'nanoid';

import { DBShape, TradeEvent, TradeEventPayload, TradeEventSource, TradeEventType } from './types.js';

export interface AppendTradeEventInput {
  symbol: string;
  type: TradeEventType;
  source?: TradeEventSource;
  timestamp?: string;
  correlationId?: string;
  positionId?: string;
  side?: 'long' | 'short';
  price?: number;
  quantity?: number;
  pnl?: number;
  reason?: string;
  payload?: TradeEventPayload;
}

function normalizePayload(payload?: TradeEventPayload): TradeEventPayload | undefined {
  if (!payload) return undefined;
  const entries = Object.entries(payload).sort(([a], [b]) => a.localeCompare(b));
  return Object.fromEntries(entries) as TradeEventPayload;
}

function computeEventHash(event: Omit<TradeEvent, 'hash'>): string {
  return createHash('sha256').update(JSON.stringify(event)).digest('hex');
}

export function appendTradeEvent(db: DBShape, input: AppendTradeEventInput): TradeEvent {
  const now = input.timestamp ?? new Date().toISOString();
  const prev = db.tradeEvents.length > 0 ? db.tradeEvents[db.tradeEvents.length - 1] : null;
  const seq = (prev?.seq ?? 0) + 1;
  const payload = normalizePayload(input.payload);

  const baseEvent: Omit<TradeEvent, 'hash'> = {
    id: nanoid(),
    seq,
    symbol: input.symbol,
    type: input.type,
    source: input.source ?? 'paper',
    timestamp: now,
    correlationId: input.correlationId ?? nanoid(),
    positionId: input.positionId,
    side: input.side,
    price: input.price,
    quantity: input.quantity,
    pnl: input.pnl,
    reason: input.reason,
    prevHash: prev?.hash ?? null,
    payload
  };

  const event: TradeEvent = {
    ...baseEvent,
    hash: computeEventHash(baseEvent)
  };

  db.tradeEvents.push(event);
  return event;
}
