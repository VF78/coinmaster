import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { nanoid } from 'nanoid';
import logger from '../lib/logger.js';
import { getDb } from '../core/db.js';
import { runDeterministicReplay } from '../core/replay.js';
import { submitBias } from '../core/services.js';
import { runSimulationStep } from '../core/simulation.js';
import { appendTradeEvent } from '../core/tradeEvents.js';
import { Bias, DailyDDBaseline, RiskGateAuditEntry } from '../core/types.js';
import type { LivePosition, PendingConfirmation, TelegramOutboxItem, TradingRulesSettings, TradingRulesTimeframe } from '../shared/dto.js';
import { normalizeTradingRules } from '../shared/tradingRules.js';
import { RuntimeRulesCache, isSymbolEnabled, maxNotionalForSymbol, computeAllocationSize } from './runtimeRules.js';
import type { AllocationSizingResult } from './runtimeRules.js';
import { HyperliquidAdapter, MidStreamHandle } from '../exchange/index.js';
import type { Candle, CandleTimeframe, OrderIntent, PositionSnapshot, TradingErrorCode } from '../exchange/types.js';
import { buildLiveDashboardState, toLiveFill } from './liveSnapshot.js';
import { evaluateMultiTf, evaluateTimeframe } from '../core/engulfingEvaluator.js';
import { evaluateFvg, type FvgTimeframe } from '../core/fvgEvaluator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../');
const distDir = path.join(rootDir, 'dist');

const app = express();
const port = Number(process.env.PORT || 8787);
const host = process.env.HOST || '0.0.0.0';

const LIVE_SYMBOL = 'BTC';
const REST_FALLBACK_MS = 60 * 1000; // at least 1m updates if WS unavailable

const LIVE_TICK_STALE_MS = Math.max(5000, Number(process.env.LIVE_TICK_STALE_MS || 120000));

const ENABLE_PAPER_ENGINE = String(process.env.ENABLE_PAPER_ENGINE ?? 'false').toLowerCase() === 'true';
const ENABLE_SIMULATION_API = String(process.env.ENABLE_SIMULATION_API ?? 'false').toLowerCase() === 'true';
const ENABLE_REPLAY_API = String(process.env.ENABLE_REPLAY_API ?? 'false').toLowerCase() === 'true';

const ENABLE_MULTI_TF_ENGULFING = String(process.env.ENABLE_MULTI_TF_ENGULFING ?? 'false').toLowerCase() === 'true';
const ENABLE_FVG_MONITOR = String(process.env.ENABLE_FVG_MONITOR ?? 'false').toLowerCase() === 'true';
const FVG_MONITOR_INTERVAL_MS = Math.max(60_000, Number(process.env.FVG_MONITOR_INTERVAL_MS || 300_000)); // default 5m
const ENABLE_DRAWDOWN_WATCHDOG = String(process.env.ENABLE_DRAWDOWN_WATCHDOG ?? 'true').toLowerCase() !== 'false';
const DRAWDOWN_WATCHDOG_INTERVAL_MS = Math.max(2000, Number(process.env.DRAWDOWN_WATCHDOG_INTERVAL_MS || 5000));
const OWNER_AUTH_TOKEN = process.env.OWNER_AUTH_TOKEN || '';
const OWNER_HMAC_SECRET = process.env.OWNER_HMAC_SECRET || '';

const PENDING_CONFIRMATION_TTL_MS = Math.max(5 * 60_000, Number(process.env.PENDING_CONFIRMATION_TTL_MS || 6 * 60 * 60_000)); // default 6h
const TELEGRAM_BOT_TOKEN = (process.env.TELEGRAM_BOT_TOKEN || '').trim();
const TELEGRAM_CHAT_ID = (process.env.TELEGRAM_CHAT_ID || '').trim();
const TELEGRAM_OUTBOX_RETRY_BASE_MS = Math.max(2000, Number(process.env.TELEGRAM_OUTBOX_RETRY_BASE_MS || 10_000));
const TELEGRAM_OUTBOX_RETRY_MAX_MS = Math.max(30_000, Number(process.env.TELEGRAM_OUTBOX_RETRY_MAX_MS || 15 * 60_000));
const TELEGRAM_OUTBOX_MAX_ATTEMPTS = Math.max(3, Number(process.env.TELEGRAM_OUTBOX_MAX_ATTEMPTS || 12));
const COINMASTER_ENV_PATH = process.env.COINMASTER_ENV_PATH || '/etc/coinmaster/coinmaster.env';

// ─── Runtime Rules Cache (hot-reloads from DB every 5s) ──────────────
const rulesCache = new RuntimeRulesCache(5_000);

/** Build a fresh LIVE_MODE snapshot from current effective rules. */
function getLiveMode() {
  const r = rulesCache.getEffectiveRules();
  return { manualConfirmation: r.manualConfirmation, maxLeverage: r.maxLeverage };
}

function prunePendingConfirmations(list: PendingConfirmation[]): PendingConfirmation[] {
  const cutoff = Date.now() - PENDING_CONFIRMATION_TTL_MS;
  return list.filter((p) => Date.parse(p.createdAt) >= cutoff);
}

function pendingToLivePosition(pending: PendingConfirmation): LivePosition {
  return {
    id: pending.id,
    symbol: pending.symbol,
    side: pending.side,
    size: pending.size,
    entryPrice: pending.price,
    dealValue: Number((pending.price * pending.size).toFixed(2)),
    leverage: pending.leverage,
    openedAt: pending.createdAt,
  };
}

async function loadPendingConfirmations(): Promise<PendingConfirmation[]> {
  const db = await getDb();
  const next = prunePendingConfirmations(db.data.pendingConfirmations);
  if (next.length !== db.data.pendingConfirmations.length) {
    db.data.pendingConfirmations = next;
    await db.write();
  }
  return next;
}

async function loadPendingConfirmationRows(): Promise<LivePosition[]> {
  const pending = await loadPendingConfirmations();
  return pending
    .slice()
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .map(pendingToLivePosition);
}

async function getTelegramConfig(): Promise<{
  token: string;
  chatId: string;
  notifyOpen: boolean;
  notifyTp: boolean;
  notifySl: boolean;
  notifyManualConfirm: boolean;
} | null> {
  const db = await getDb();
  const s = db.data.settings.telegramNotify;
  const token = String(s?.botToken || TELEGRAM_BOT_TOKEN || '').trim();
  const chatId = String(s?.chatId || TELEGRAM_CHAT_ID || '').trim();
  if (!token || !chatId) return null;
  return {
    token,
    chatId,
    notifyOpen: s?.notifyOpen !== false,
    notifyTp: s?.notifyTp !== false,
    notifySl: s?.notifySl !== false,
    notifyManualConfirm: s?.notifyManualConfirm !== false,
  };
}

function maskBotToken(token: string): string {
  if (!token) return '';
  if (token.length <= 8) return '••••';
  return `${token.slice(0, 4)}••••${token.slice(-4)}`;
}

async function sendTelegramText(text: string, opts?: { replyMarkup?: unknown }): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg) return;
  const response = await fetch(`https://api.telegram.org/bot${cfg.token}/sendMessage`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      chat_id: cfg.chatId,
      text,
      ...(opts?.replyMarkup ? { reply_markup: opts.replyMarkup } : {}),
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`telegram_send_failed_${response.status}${body ? `_${body.slice(0, 80)}` : ''}`);
  }
}

async function enqueueTelegramOutbox(params: {
  category: TelegramOutboxItem['category'];
  text: string;
  replyMarkup?: unknown;
  dedupeKey?: string;
}): Promise<{ queued: boolean; id?: string }> {
  const cfg = await getTelegramConfig();
  if (!cfg) return { queued: false };

  const db = await getDb();
  db.data.telegramOutbox = Array.isArray(db.data.telegramOutbox) ? db.data.telegramOutbox : [];

  if (params.dedupeKey) {
    const exists = db.data.telegramOutbox.find((m) => m.dedupeKey === params.dedupeKey && m.status !== 'failed');
    if (exists) return { queued: false, id: exists.id };
  }

  const now = new Date().toISOString();
  const msg: TelegramOutboxItem = {
    id: `tg-${nanoid(10)}`,
    category: params.category,
    text: params.text,
    replyMarkup: params.replyMarkup,
    dedupeKey: params.dedupeKey,
    status: 'queued',
    attempts: 0,
    nextAttemptAt: now,
    createdAt: now,
  };

  db.data.telegramOutbox.push(msg);
  if (db.data.telegramOutbox.length > 5000) {
    db.data.telegramOutbox = db.data.telegramOutbox.slice(-5000);
  }
  await db.write();
  return { queued: true, id: msg.id };
}

let telegramOutboxTimer: NodeJS.Timeout | null = null;
let telegramOutboxBusy = false;

async function runTelegramOutboxTick(): Promise<void> {
  if (telegramOutboxBusy) return;
  telegramOutboxBusy = true;
  try {
    const cfg = await getTelegramConfig();
    if (!cfg) return;

    const db = await getDb();
    db.data.telegramOutbox = Array.isArray(db.data.telegramOutbox) ? db.data.telegramOutbox : [];

    const now = Date.now();
    const due = db.data.telegramOutbox
      .filter((m) => m.status === 'queued' && Date.parse(m.nextAttemptAt) <= now)
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
      .slice(0, 20);

    if (due.length === 0) return;

    let changed = false;

    for (const msg of due) {
      try {
        const response = await fetch(`https://api.telegram.org/bot${cfg.token}/sendMessage`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            chat_id: cfg.chatId,
            text: msg.text,
            ...(msg.replyMarkup ? { reply_markup: msg.replyMarkup } : {}),
          }),
        });

        if (!response.ok) {
          const body = await response.text().catch(() => '');
          throw new Error(`telegram_send_failed_${response.status}${body ? `_${body.slice(0, 120)}` : ''}`);
        }

        msg.status = 'sent';
        msg.sentAt = new Date().toISOString();
        msg.lastError = undefined;
        changed = true;
      } catch (error) {
        msg.attempts += 1;
        msg.lastError = error instanceof Error ? error.message : String(error);
        if (msg.attempts >= TELEGRAM_OUTBOX_MAX_ATTEMPTS) {
          msg.status = 'failed';
          logger.error({ component: 'telegram', outboxId: msg.id, attempts: msg.attempts, err: msg.lastError }, 'telegram outbox message permanently failed');
        } else {
          const backoff = Math.min(TELEGRAM_OUTBOX_RETRY_MAX_MS, TELEGRAM_OUTBOX_RETRY_BASE_MS * (2 ** Math.max(0, msg.attempts - 1)));
          msg.nextAttemptAt = new Date(Date.now() + backoff).toISOString();
          logger.warn({ component: 'telegram', outboxId: msg.id, attempts: msg.attempts, retryInMs: backoff, err: msg.lastError }, 'telegram outbox retry scheduled');
        }
        changed = true;
      }
    }

    if (changed) {
      db.data.telegramOutbox = db.data.telegramOutbox.filter((m) => m.status !== 'sent' || (m.sentAt && Date.now() - Date.parse(m.sentAt) < 24 * 60 * 60_000));
      await db.write();
    }
  } finally {
    telegramOutboxBusy = false;
  }
}

function startTelegramOutboxLoop(): void {
  if (telegramOutboxTimer) return;
  runTelegramOutboxTick().catch((err) => logger.warn({ component: 'telegram', err }, 'initial telegram outbox tick failed'));
  telegramOutboxTimer = setInterval(() => {
    runTelegramOutboxTick().catch((err) => logger.warn({ component: 'telegram', err }, 'telegram outbox tick failed'));
  }, 3000);
  telegramOutboxTimer.unref?.();
}

async function notifyPendingConfirmationTelegram(pending: PendingConfirmation): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyManualConfirm) return;

  const text = [
    '⚠️ Coinmaster signal requires confirmation',
    `ID: ${pending.id}`,
    `${pending.strategy.toUpperCase()} ${pending.timeframe} • ${pending.symbol} ${pending.side.toUpperCase()}`,
    `Price: ${pending.price}`,
    `Size: ${pending.size}`,
    `Leverage: ${pending.leverage}x`,
    `Reason: ${pending.reason}`,
    'Reply command: /confirm <ID> or /reject <ID>',
  ].join('\n');

  await enqueueTelegramOutbox({
    category: 'manual_confirm',
    text,
    dedupeKey: `pending:${pending.id}`,
    replyMarkup: {
      inline_keyboard: [[
        { text: '✅ Confirm', callback_data: `confirm:${pending.id}` },
        { text: '❌ Reject', callback_data: `reject:${pending.id}` },
      ]],
    },
  });
}

async function clearPendingConfirmationForSymbol(symbol: string): Promise<void> {
  const db = await getDb();
  const before = db.data.pendingConfirmations.length;
  db.data.pendingConfirmations = db.data.pendingConfirmations.filter((p) => p.symbol.toUpperCase() !== symbol.toUpperCase());
  if (db.data.pendingConfirmations.length !== before) {
    await db.write();
  }
}

async function getOperatorBias(symbol: string): Promise<Bias> {
  const db = await getDb();
  const normalized = symbol.toUpperCase();
  const latest = [...db.data.biasCommands].reverse();
  const symbolBias = latest.find((b) => b.symbol === normalized)?.bias;
  if (symbolBias) return symbolBias;
  const globalBias = latest.find((b) => b.symbol === LIVE_SYMBOL)?.bias;
  return globalBias ?? 'off';
}

function getMonitoredSymbols(raw: TradingRulesSettings): string[] {
  const enabled = (raw.coins ?? [])
    .filter((coin) => coin.enabled)
    .map((coin) => normalizeSymbol(coin.symbol))
    .filter((s) => s.length > 0);

  const base = enabled.length > 0 ? enabled : [LIVE_SYMBOL];
  return [...new Set(base)];
}

async function getFreshExitClosePct(fallback = 50): Promise<number> {
  try {
    const db = await getDb();
    const rules = normalizeTradingRules(db.data.settings.tradingRules);
    const pct = Number(rules.exitClosePct);
    if (!Number.isFinite(pct)) return fallback;
    return Math.max(0, Math.min(100, pct));
  } catch {
    return fallback;
  }
}

async function queuePendingConfirmation(params: {
  symbol: string;
  side: 'long' | 'short';
  strategy: 'engulfing' | 'fvg';
  timeframe: TradingRulesTimeframe;
  reason: string;
  price: number;
  size: number;
  leverage: number;
  correlationId: string;
}): Promise<{ queued: boolean; id: string }> {
  const db = await getDb();
  const now = new Date().toISOString();

  const operatorBias = await getOperatorBias(params.symbol);
  const directionBias: Bias = params.side === 'long' ? 'long' : 'short';
  const biasBlocked = operatorBias === 'off' || operatorBias !== directionBias;
  if (biasBlocked) {
    logRiskGateAudit({
      gate: params.strategy === 'fvg' ? 'fvg_entry_signal' : 'engulfing_entry_signal',
      passed: false,
      reason: 'operator_bias_block',
      details: { symbol: params.symbol, strategy: params.strategy, side: params.side, operatorBias },
    });
    return { queued: false, id: 'operator_bias_block' };
  }

  const cleaned = prunePendingConfirmations(db.data.pendingConfirmations);
  db.data.pendingConfirmations = cleaned;

  const next: PendingConfirmation = {
    id: `pc-${nanoid(10)}`,
    symbol: params.symbol,
    side: params.side,
    strategy: params.strategy,
    timeframe: params.timeframe,
    reason: params.reason,
    price: Number(params.price.toFixed(8)),
    size: Math.max(0, Number(params.size.toFixed(6))),
    leverage: params.leverage,
    createdAt: now,
  };

  const existingIdx = db.data.pendingConfirmations.findIndex((p) => p.symbol.toUpperCase() === params.symbol.toUpperCase());
  if (existingIdx >= 0) {
    const existing = db.data.pendingConfirmations[existingIdx];
    const duplicate =
      existing.side === next.side &&
      existing.strategy === next.strategy &&
      existing.timeframe === next.timeframe &&
      Math.abs(Date.parse(now) - Date.parse(existing.createdAt)) < 60_000;

    if (duplicate) {
      return { queued: false, id: existing.id };
    }

    db.data.pendingConfirmations.splice(existingIdx, 1, next);
  } else {
    db.data.pendingConfirmations.push(next);
  }

  appendTradeEvent(db.data, {
    symbol: params.symbol,
    source: 'live',
    type: 'signal_detected',
    timestamp: now,
    correlationId: params.correlationId,
    side: params.side,
    price: params.price,
    quantity: params.size,
    reason: `${params.strategy}_signal_pending_confirmation`,
    payload: {
      pendingConfirmationId: next.id,
      timeframe: params.timeframe,
      strategy: params.strategy,
      leverage: params.leverage,
    },
  });

  await db.write();

  try {
    await notifyPendingConfirmationTelegram(next);
  } catch (error) {
    logger.warn({ component: 'pending-confirmation', err: error instanceof Error ? error.message : error }, 'telegram notification failed');
  }

  return { queued: true, id: next.id };
}

async function notifyTradeOpen(params: {
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  source: string;
}): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyOpen) return;
  await enqueueTelegramOutbox({
    category: 'trade_open',
    dedupeKey: `open:${params.symbol}:${params.side}:${params.price}:${params.size}:${params.source}`,
    text: [
      '🟢 Trade opened',
      `${params.symbol} ${params.side.toUpperCase()}`,
      `Price: ${params.price}`,
      `Size: ${params.size}`,
      `Source: ${params.source}`,
    ].join('\n'),
  });
}

async function notifyTpHit(params: { symbol: string; entryPrice: number; remainingSize: number; tpIds: string[] }): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifyTp) return;
  await enqueueTelegramOutbox({
    category: 'tp',
    dedupeKey: `tp:${params.symbol}:${params.tpIds.join(',')}`,
    text: [
      '🎯 Take-profit filled',
      `${params.symbol}`,
      `Filled TP orders: ${params.tpIds.join(', ')}`,
      `SL moved to break-even: ${params.entryPrice}`,
      `Remaining size: ${params.remainingSize}`,
    ].join('\n'),
  });
}

async function notifySlEvent(params: { symbol: string; reason: string }): Promise<void> {
  const cfg = await getTelegramConfig();
  if (!cfg || !cfg.notifySl) return;
  await enqueueTelegramOutbox({
    category: 'sl',
    dedupeKey: `sl:${params.symbol}:${params.reason}:${Math.floor(Date.now() / 60000)}`,
    text: [
      '🛑 Stop-loss / emergency exit event',
      `${params.symbol}`,
      `Reason: ${params.reason}`,
    ].join('\n'),
  });
}

async function executePendingConfirmation(pendingId: string, actor: 'dashboard' | 'telegram'): Promise<{ ok: boolean; error?: string }> {
  const db = await getDb();
  const pending = db.data.pendingConfirmations.find((p) => p.id === pendingId);
  if (!pending) return { ok: false, error: 'pending_not_found' };

  const rules = rulesCache.getEffectiveRules();
  const normalizedSymbol = normalizeSymbol(pending.symbol);
  const side: 'buy' | 'sell' = pending.side === 'long' ? 'buy' : 'sell';
  const now = new Date().toISOString();

  // Risk check before submit
  const risk = await evaluateRiskGates({ emitAudit: false });
  if (!risk.canTrade) {
    appendTradeEvent(db.data, {
      symbol: normalizedSymbol,
      source: 'live',
      type: 'signal_rejected',
      timestamp: now,
      correlationId: `pending-${pending.id}`,
      side: pending.side,
      price: pending.price,
      quantity: pending.size,
      reason: 'pending_rejected_risk_gate',
      payload: { blocks: risk.blocks.join(','), actor },
    });
    await db.write();
    return { ok: false, error: `risk_gate_blocked:${risk.blocks.join(',')}` };
  }

  // leverage
  if (Number.isFinite(pending.leverage) && pending.leverage > 0) {
    const lev = Math.min(pending.leverage, rules.maxLeverage);
    await exchange.setLeverage(normalizedSymbol, lev);
  }

  const correlationId = `pending-confirm-${pending.id}`;
  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: now,
    correlationId,
    side: pending.side,
    price: pending.price,
    quantity: pending.size,
    reason: 'pending_confirm_submit',
    payload: { actor, strategy: pending.strategy, timeframe: pending.timeframe },
  });

  const placeWithRetry = async () => {
    const attemptPrices: number[] = [pending.price];
    let lastAck: Awaited<ReturnType<typeof exchange.placeLimitOrder>> | null = null;

    for (let attempt = 0; attempt < attemptPrices.length; attempt++) {
      const price = attemptPrices[attempt];
      const ack = await exchange.placeLimitOrder({
        symbol: normalizedSymbol,
        side,
        price,
        size: pending.size,
        reduceOnly: false,
        clientOrderId: `${correlationId}-${attempt + 1}`,
      });

      if (ack.ok) return { ack, usedPrice: price };
      lastAck = ack;

      const err = String(ack.error ?? '').toLowerCase();
      const retryablePriceError = err.includes('tick size') || err.includes('divisible') || err.includes('invalid price') || err.includes('tofixed');
      if (attempt === 0 && retryablePriceError) {
        const mid = await fetchLiveMid(normalizedSymbol);
        if (mid && Number.isFinite(mid) && mid > 0) {
          attemptPrices.push(mid);
          logger.warn({ component: 'pending-confirmation', pendingId, attempt: attempt + 1, originalPrice: price, fallbackMid: mid, err: ack.error }, 'retrying pending confirmation with fresh mid price');
          continue;
        }
      }
    }

    return { ack: lastAck ?? { ok: false, error: 'exchange_rejected' }, usedPrice: pending.price };
  };

  const { ack, usedPrice } = await placeWithRetry();

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: pending.side,
    price: usedPrice,
    quantity: pending.size,
    reason: ack.ok ? 'pending_confirm_ack' : 'pending_confirm_rejected',
    payload: { orderId: ack.orderId ?? null, status: ack.status ?? null, error: ack.error ?? null, actor, usedPrice },
  });

  if (!ack.ok) {
    await db.write();
    return { ok: false, error: ack.error ?? 'exchange_rejected' };
  }

  db.data.pendingConfirmations = db.data.pendingConfirmations.filter((p) => p.id !== pendingId);

  const tpSl = resolveTpSlDefaults(usedPrice, side, undefined, undefined);
  if (tpSl) {
    try {
      await placeTpSlTriggerOrders(normalizedSymbol, side, pending.size, tpSl, correlationId, usedPrice);
    } catch {
      // best effort
    }
  }

  await db.write();

  try {
    await notifyTradeOpen({ symbol: normalizedSymbol, side, price: usedPrice, size: pending.size, source: `pending:${actor}` });
  } catch (error) {
    logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
  }

  return { ok: true };
}

async function rejectPendingConfirmation(pendingId: string, actor: 'dashboard' | 'telegram'): Promise<{ ok: boolean; error?: string }> {
  const db = await getDb();
  const before = db.data.pendingConfirmations.length;
  db.data.pendingConfirmations = db.data.pendingConfirmations.filter((p) => p.id !== pendingId);
  if (db.data.pendingConfirmations.length === before) {
    return { ok: false, error: 'pending_not_found' };
  }
  appendTradeEvent(db.data, {
    symbol: LIVE_SYMBOL,
    source: 'live',
    type: 'signal_rejected',
    timestamp: new Date().toISOString(),
    correlationId: `pending-reject-${pendingId}`,
    reason: 'pending_confirmation_rejected',
    payload: { pendingId, actor },
  });
  await db.write();
  return { ok: true };
}

let telegramUpdateTimer: NodeJS.Timeout | null = null;
let telegramUpdateBusy = false;

async function answerTelegramCallback(token: string, callbackQueryId: string, text?: string): Promise<void> {
  await fetch(`https://api.telegram.org/bot${token}/answerCallbackQuery`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ callback_query_id: callbackQueryId, ...(text ? { text } : {}) }),
  }).catch(() => undefined);
}

async function runTelegramUpdateTick(): Promise<void> {
  if (telegramUpdateBusy) return;
  telegramUpdateBusy = true;
  try {
    const cfg = await getTelegramConfig();
    if (!cfg) return;

    const db = await getDb();
    const updateOffset = Math.max(0, Number(db.data.settings.telegramNotify?.updateOffset ?? 0));

    const response = await fetch(`https://api.telegram.org/bot${cfg.token}/getUpdates`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ timeout: 20, offset: updateOffset, allowed_updates: ['message', 'callback_query'] }),
    });
    if (!response.ok) return;

    const payload = await response.json() as { ok?: boolean; result?: any[] };
    if (!payload.ok || !Array.isArray(payload.result) || payload.result.length === 0) return;

    let nextOffset = updateOffset;

    for (const update of payload.result) {
      nextOffset = Math.max(nextOffset, Number(update.update_id || 0) + 1);

      const msg = update.message;
      const cb = update.callback_query;
      const chatIdRaw = cb?.message?.chat?.id ?? msg?.chat?.id;
      if (String(chatIdRaw ?? '') !== String(cfg.chatId)) continue;

      if (msg?.text) {
        const text = String(msg.text).trim();
        if (text.startsWith('/confirm')) {
          const id = text.split(/\s+/)[1];
          if (!id) {
            await sendTelegramText('Usage: /confirm <pending-id>');
            continue;
          }
          const result = await executePendingConfirmation(id, 'telegram');
          await sendTelegramText(result.ok ? `✅ Confirmed: ${id}` : `❌ Confirm failed: ${id} (${result.error})`);
        } else if (text.startsWith('/reject')) {
          const id = text.split(/\s+/)[1];
          if (!id) {
            await sendTelegramText('Usage: /reject <pending-id>');
            continue;
          }
          const result = await rejectPendingConfirmation(id, 'telegram');
          await sendTelegramText(result.ok ? `🗑 Rejected: ${id}` : `❌ Reject failed: ${id} (${result.error})`);
        } else if (text === '/pending') {
          const pending = await loadPendingConfirmations();
          if (!pending.length) {
            await sendTelegramText('No pending confirmations.');
          } else {
            const lines = pending.slice(0, 10).map((p) => `${p.id} • ${p.symbol} ${p.side.toUpperCase()} • ${p.strategy}/${p.timeframe} • px ${p.price}`);
            await sendTelegramText(`Pending confirmations:\n${lines.join('\n')}`);
          }
        }
      }

      if (cb?.id && cb?.data) {
        const data = String(cb.data);
        if (data.startsWith('confirm:')) {
          const id = data.slice('confirm:'.length);
          const result = await executePendingConfirmation(id, 'telegram');
          await answerTelegramCallback(cfg.token, cb.id, result.ok ? 'Confirmed' : `Failed: ${result.error ?? 'error'}`);
          await sendTelegramText(result.ok ? `✅ Confirmed: ${id}` : `❌ Confirm failed: ${id} (${result.error})`);
        } else if (data.startsWith('reject:')) {
          const id = data.slice('reject:'.length);
          const result = await rejectPendingConfirmation(id, 'telegram');
          await answerTelegramCallback(cfg.token, cb.id, result.ok ? 'Rejected' : `Failed: ${result.error ?? 'error'}`);
          await sendTelegramText(result.ok ? `🗑 Rejected: ${id}` : `❌ Reject failed: ${id} (${result.error})`);
        }
      }
    }

    if (nextOffset !== updateOffset) {
      db.data.settings.telegramNotify = db.data.settings.telegramNotify ?? {
        botToken: '',
        chatId: '',
        notifyOpen: true,
        notifyTp: true,
        notifySl: true,
        notifyManualConfirm: true,
      };
      db.data.settings.telegramNotify.updateOffset = nextOffset;
      await db.write();
    }
  } catch (err) {
    logger.warn({ component: 'telegram', err }, 'telegram update tick failed');
  } finally {
    telegramUpdateBusy = false;
  }
}

function startTelegramUpdateLoop(): void {
  if (telegramUpdateTimer) return;
  runTelegramUpdateTick().catch((err) => logger.warn({ component: 'telegram', err }, 'initial telegram tick failed'));
  telegramUpdateTimer = setInterval(() => {
    runTelegramUpdateTick().catch((err) => logger.warn({ component: 'telegram', err }, 'telegram tick failed'));
  }, 5000);
  telegramUpdateTimer.unref?.();
}

// ─── Owner Auth Middleware ────────────────────────────────────────────

function ownerAuth(req: Request, res: Response, next: NextFunction) {
  // If no auth token configured, skip auth (dev mode)
  if (!OWNER_AUTH_TOKEN && !OWNER_HMAC_SECRET) {
    return next();
  }

  // Bearer token check
  const authHeader = req.headers.authorization;
  if (authHeader) {
    const token = authHeader.replace(/^Bearer\s+/i, '');
    if (OWNER_AUTH_TOKEN && token === OWNER_AUTH_TOKEN) {
      return next();
    }
  }

  // Query param token check
  const queryToken = req.query.token as string | undefined;
  if (OWNER_AUTH_TOKEN && queryToken === OWNER_AUTH_TOKEN) {
    return next();
  }

  // HMAC verification: ?ts=<unix_s>&sig=<hex>
  if (OWNER_HMAC_SECRET) {
    const ts = req.query.ts as string | undefined;
    const sig = req.query.sig as string | undefined;
    if (ts && sig) {
      const age = Math.abs(Date.now() / 1000 - Number(ts));
      if (age < 300) { // 5 min window
        const expected = crypto.createHmac('sha256', OWNER_HMAC_SECRET).update(ts).digest('hex');
        if (crypto.timingSafeEqual(Buffer.from(sig, 'hex'), Buffer.from(expected, 'hex'))) {
          return next();
        }
      }
    }
  }

  logRiskGateAudit({ gate: 'auth', passed: false, reason: 'auth_required' });
  return res.status(401).json({ ok: false, errorCode: 'auth_required' as TradingErrorCode, error: 'Authentication required for live trading endpoints' });
}

// ─── Risk Gate Helpers ────────────────────────────────────────────────

/** In-memory risk gate audit buffer, flushed to DB periodically */
const riskAuditBuffer: RiskGateAuditEntry[] = [];

function logRiskGateAudit(entry: Omit<RiskGateAuditEntry, 'timestamp'>) {
  const full: RiskGateAuditEntry = { ...entry, timestamp: new Date().toISOString() };
  riskAuditBuffer.push(full);

  // Keep persistent DB audit for all checks, but avoid noisy success logs by default.
  if (!full.passed) {
    logger.warn({ component: 'risk-gate', gate: full.gate, passed: full.passed, reason: full.reason ?? undefined }, 'risk gate check failed');
  } else if (process.env.RISK_GATE_VERBOSE === '1') {
    logger.info({ component: 'risk-gate', gate: full.gate, passed: full.passed, reason: full.reason ?? undefined }, 'risk gate check');
  }
}

async function flushRiskAudit() {
  if (!riskAuditBuffer.length) return;
  const db = await getDb();
  const batch = riskAuditBuffer.splice(0, riskAuditBuffer.length);
  db.data.riskGateAudit.push(...batch);
  // Keep last 10000 entries
  if (db.data.riskGateAudit.length > 10000) {
    db.data.riskGateAudit = db.data.riskGateAudit.slice(-10000);
  }
  await db.write();
}

// Flush audit every 30s
const auditFlushTimer = setInterval(() => { flushRiskAudit().catch((err) => logger.warn({ component: 'audit', err }, 'audit flush failed')); }, 30_000);
auditFlushTimer.unref();

function todayDateStr(): string {
  return new Date().toISOString().slice(0, 10);
}

async function getOrCreateDDBaseline(equityUsd: number): Promise<DailyDDBaseline> {
  const today = todayDateStr();
  const db = await getDb();
  let baseline = db.data.dailyDDBaselines.find(b => b.date === today);
  if (!baseline) {
    baseline = { date: today, startEquityUsd: equityUsd, updatedAt: new Date().toISOString() };
    db.data.dailyDDBaselines.push(baseline);
    // Prune old baselines (keep 90 days)
    if (db.data.dailyDDBaselines.length > 90) {
      db.data.dailyDDBaselines = db.data.dailyDDBaselines.slice(-90);
    }
    await db.write();
  }
  return baseline;
}

interface RiskCheckResult {
  canTrade: boolean;
  dailyDDPct: number;
  portfolioLeverage: number;
  blocks: string[];
  equityUsd: number;
  baselineEquityUsd: number;
}

async function evaluateRiskGates(options?: { emitAudit?: boolean }): Promise<RiskCheckResult> {
  const emitAudit = options?.emitAudit ?? true;
  const blocks: string[] = [];

  // Fetch account state
  const [account, positions] = await Promise.all([
    exchange.getAccountState(),
    exchange.getOpenPositions()
  ]);

  const equityUsd = account?.equityUsd ?? 0;

  const effectiveRules = rulesCache.getEffectiveRules();

  // Daily DD check
  const baseline = await getOrCreateDDBaseline(equityUsd);
  const ddPct = baseline.startEquityUsd > 0
    ? ((baseline.startEquityUsd - equityUsd) / baseline.startEquityUsd) * 100
    : 0;

  if (ddPct >= effectiveRules.dailyDDLimitPct) {
    blocks.push('daily_loss_limit_exceeded');
    if (emitAudit) {
      logRiskGateAudit({ gate: 'daily_dd', passed: false, reason: 'daily_loss_limit_exceeded', details: { ddPct: Number(ddPct.toFixed(2)), limit: effectiveRules.dailyDDLimitPct, equityUsd, baselineEquityUsd: baseline.startEquityUsd } });
    }
  } else if (emitAudit) {
    logRiskGateAudit({ gate: 'daily_dd', passed: true, details: { ddPct: Number(ddPct.toFixed(2)) } });
  }

  // Portfolio leverage check
  let totalNotional = 0;
  for (const pos of positions) {
    const notional = (pos.entryPrice ?? pos.markPrice ?? 0) * pos.size;
    totalNotional += notional;
  }
  const portfolioLeverage = equityUsd > 0 ? totalNotional / equityUsd : 0;

  if (portfolioLeverage > effectiveRules.portfolioLeverageCap) {
    blocks.push('leverage_limit_exceeded');
    if (emitAudit) {
      logRiskGateAudit({ gate: 'leverage_cap', passed: false, reason: 'leverage_limit_exceeded', details: { portfolioLeverage: Number(portfolioLeverage.toFixed(2)), cap: effectiveRules.portfolioLeverageCap } });
    }
  } else if (emitAudit) {
    logRiskGateAudit({ gate: 'leverage_cap', passed: true, details: { portfolioLeverage: Number(portfolioLeverage.toFixed(2)) } });
  }

  return {
    canTrade: blocks.length === 0,
    dailyDDPct: Number(ddPct.toFixed(2)),
    portfolioLeverage: Number(portfolioLeverage.toFixed(2)),
    blocks,
    equityUsd,
    baselineEquityUsd: baseline.startEquityUsd
  };
}

const emergencyCloseLock = {
  running: false,
  hardStopActive: false
};

const ddLock = {
  active: false,
  activatedAt: '',
};

const WATCHDOG_IDLE_LOG_INTERVAL_MS = 5 * 60 * 1000;
const watchdogLogState: Record<string, number> = {};

function shouldLogWatchdog(key: string, intervalMs = WATCHDOG_IDLE_LOG_INTERVAL_MS): boolean {
  const now = Date.now();
  const last = watchdogLogState[key] ?? 0;
  if (now - last < intervalMs) return false;
  watchdogLogState[key] = now;
  return true;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function emergencyClosePrice(pos: { side: 'long' | 'short'; markPrice?: number; entryPrice?: number }, closeSide: 'buy' | 'sell'): number {
  const mark = pos.markPrice ?? pos.entryPrice ?? 0;
  if (!Number.isFinite(mark) || mark <= 0) {
    return closeSide === 'sell' ? 1 : 999_999;
  }
  const price = closeSide === 'sell' ? mark * 0.985 : mark * 1.015;
  return Math.max(0.00000001, Number(price.toFixed(8)));
}

/** Close all positions emergency (daily DD hard stop). Best effort but retried by watchdog every few seconds until flat. */
async function emergencyCloseAll(reason = 'daily_loss_limit_exceeded') {
  if (emergencyCloseLock.running) return;
  emergencyCloseLock.running = true;
  try {
    const [positions, openOrders] = await Promise.all([
      exchange.getOpenPositions(),
      exchange.getOpenOrders()
    ]);

    if (positions.length === 0 && openOrders.length === 0) {
      if (shouldLogWatchdog('already-flat')) {
        logger.warn({ component: 'risk-gate' }, 'emergency close skipped: account already flat (no positions/orders)');
      }
      return;
    }

    logger.error({ component: 'risk-gate', reason, positions: positions.length, openOrders: openOrders.length }, 'EMERGENCY: closing positions and cancelling orders');

    // Cancel resting orders first to reduce conflicts with reduce-only exits.
    if (openOrders.length > 0) {
      try {
        await exchange.cancelAll();
      } catch (error) {
        logger.error({ component: 'risk-gate', err: error }, 'cancelAll during emergency failed');
      }
    }

    if (positions.length === 0) {
      return;
    }

    for (const pos of positions) {
      const closeSide: 'buy' | 'sell' = pos.side === 'long' ? 'sell' : 'buy';
      const price = emergencyClosePrice(pos, closeSide);
      try {
        const ack = await exchange.placeLimitOrder({
          symbol: pos.symbol,
          side: closeSide,
          price,
          size: pos.size,
          reduceOnly: true,
          clientOrderId: `emergency-${Date.now()}-${nanoid(6)}`
        });

        if (!ack.ok) {
          // Retry once with more aggressive price.
          const retryPrice = closeSide === 'sell' ? Math.max(0.00000001, price * 0.95) : price * 1.05;
          await exchange.placeLimitOrder({
            symbol: pos.symbol,
            side: closeSide,
            price: Number(retryPrice.toFixed(8)),
            size: pos.size,
            reduceOnly: true,
            clientOrderId: `emergency-retry-${Date.now()}-${nanoid(6)}`
          });
        }

        try {
          await notifySlEvent({ symbol: pos.symbol, reason });
        } catch (notifyErr) {
          logger.warn({ component: 'telegram', err: notifyErr instanceof Error ? notifyErr.message : notifyErr }, 'SL telegram notify failed');
        }
      } catch (error) {
        logger.error({ component: 'risk-gate', symbol: pos.symbol, err: error }, 'failed to emergency-close position');
      }
    }

    // Brief settle and re-check position count.
    await sleep(400);

    const remaining = await exchange.getOpenPositions();
    if (remaining.length > 0) {
      logger.error({ component: 'risk-gate', remaining: remaining.length }, 'emergency close incomplete, watchdog will retry');
    }
  } finally {
    emergencyCloseLock.running = false;
  }
}

/** Close emergency only for one symbol (used by per-symbol strategy exits). */
async function emergencyCloseSymbol(symbol: string, reason = 'strategy_emergency_exit') {
  const normalized = normalizeSymbol(symbol);
  try {
    const [positions, openOrders] = await Promise.all([
      exchange.getOpenPositions(normalized),
      exchange.getOpenOrders(normalized),
    ]);

    if (positions.length === 0 && openOrders.length === 0) return;

    if (openOrders.length > 0) {
      await exchange.cancelAll(normalized).catch(() => undefined);
    }

    for (const pos of positions) {
      const closeSide: 'buy' | 'sell' = pos.side === 'long' ? 'sell' : 'buy';
      const price = emergencyClosePrice(pos, closeSide);
      const ack = await exchange.placeLimitOrder({
        symbol: normalized,
        side: closeSide,
        price,
        size: pos.size,
        reduceOnly: true,
        clientOrderId: `emergency-${normalized}-${Date.now()}-${nanoid(6)}`,
      });

      if (!ack.ok) {
        const retryPrice = closeSide === 'sell' ? Math.max(0.00000001, price * 0.95) : price * 1.05;
        await exchange.placeLimitOrder({
          symbol: normalized,
          side: closeSide,
          price: Number(retryPrice.toFixed(8)),
          size: pos.size,
          reduceOnly: true,
          clientOrderId: `emergency-retry-${normalized}-${Date.now()}-${nanoid(6)}`,
        }).catch(() => undefined);
      }

      await notifySlEvent({ symbol: normalized, reason }).catch(() => undefined);
    }
  } catch (error) {
    logger.error({ component: 'risk-gate', symbol: normalized, err: error }, 'failed to emergency-close symbol');
  }
}

let drawdownWatchdogTimer: NodeJS.Timeout | null = null;
let drawdownWatchdogBusy = false;

async function runDrawdownWatchdogTick() {
  if (drawdownWatchdogBusy) return;
  drawdownWatchdogBusy = true;
  try {
    const risk = await evaluateRiskGates({ emitAudit: false });

    if (risk.blocks.includes('daily_loss_limit_exceeded')) {
      if (!emergencyCloseLock.hardStopActive) {
        emergencyCloseLock.hardStopActive = true;
        logRiskGateAudit({
          gate: 'daily_dd',
          passed: false,
          reason: 'daily_loss_limit_exceeded_watchdog',
          details: {
            ddPct: risk.dailyDDPct,
            limit: rulesCache.getEffectiveRules().dailyDDLimitPct,
            equityUsd: risk.equityUsd,
            baselineEquityUsd: risk.baselineEquityUsd
          }
        });
      }

      if (!ddLock.active) {
        ddLock.active = true;
        ddLock.activatedAt = new Date().toISOString();
        logRiskGateAudit({
          gate: 'daily_dd',
          passed: false,
          reason: 'dd_lock_activated_watchdog',
          details: {
            activatedAt: ddLock.activatedAt,
            ddPct: risk.dailyDDPct,
            limit: rulesCache.getEffectiveRules().dailyDDLimitPct,
          },
        });
      }

      const [positions, openOrders] = await Promise.all([
        exchange.getOpenPositions(),
        exchange.getOpenOrders()
      ]);

      if (positions.length === 0 && openOrders.length === 0) {
        if (shouldLogWatchdog('dd-hardstop-flat')) {
          logger.warn({ component: 'risk-gate' }, 'hard-stop active but account already flat; skipping emergency close tick');
        }
        return;
      }

      await emergencyCloseAll('daily_loss_limit_exceeded_watchdog');
      return;
    }

    if (emergencyCloseLock.hardStopActive) {
      emergencyCloseLock.hardStopActive = false;
      logRiskGateAudit({
        gate: 'daily_dd',
        passed: true,
        reason: 'daily_loss_recovered_watchdog',
        details: {
          ddPct: risk.dailyDDPct,
          limit: rulesCache.getEffectiveRules().dailyDDLimitPct,
          equityUsd: risk.equityUsd,
          baselineEquityUsd: risk.baselineEquityUsd,
          ddLockActive: ddLock.active,
          ddLockActivatedAt: ddLock.activatedAt || undefined,
        }
      });
    }
  } catch (error) {
    logger.error({ component: 'risk-gate', err: error }, 'drawdown watchdog tick failed');
  } finally {
    drawdownWatchdogBusy = false;
  }
}

function startDrawdownWatchdog() {
  if (!ENABLE_DRAWDOWN_WATCHDOG) {
    logger.info({ component: 'risk-gate' }, 'drawdown watchdog disabled via ENABLE_DRAWDOWN_WATCHDOG=false');
    return;
  }
  if (!exchange.capabilities.privateAccount || !exchange.capabilities.privateTrading) {
    logger.info({ component: 'risk-gate' }, 'drawdown watchdog not started (private account/trading unavailable)');
    return;
  }
  if (drawdownWatchdogTimer) return;

  // Warm-up tick immediately so baseline is created early in the day.
  runDrawdownWatchdogTick().catch((err) => logger.warn({ component: 'risk-gate', err }, 'drawdown watchdog tick failed'));

  drawdownWatchdogTimer = setInterval(() => {
    runDrawdownWatchdogTick().catch((err) => logger.warn({ component: 'risk-gate', err }, 'drawdown watchdog tick failed'));
  }, DRAWDOWN_WATCHDOG_INTERVAL_MS);
  drawdownWatchdogTimer.unref?.();

  logger.info({ component: 'risk-gate', intervalMs: DRAWDOWN_WATCHDOG_INTERVAL_MS }, 'drawdown watchdog started');
}

// ─── Engulfing Monitor Loop ───────────────────────────────────────────
let engulfingMonitorTimer: NodeJS.Timeout | null = null;
let engulfingMonitorBusy = false;
let engulfingMonitorIntervalAppliedMs = 0;

/** Per-signal debounce: key = `${symbol}:${tf}:${direction}`, value = last fired ms */
const lastEntrySignalAt = new Map<string, number>();
/** Per-candle emergency-exit debounce: key = `${symbol}:${tf}:${direction}`, value = engulfing candle open timestamp ms. */
const lastEmergencyExitSignalAt = new Map<string, number>();

async function estimateSignalSize(params: {
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  effectiveRules: ReturnType<typeof rulesCache.getEffectiveRules>;
}): Promise<{ size: number; leverage: number }> {
  const { symbol, price, effectiveRules } = params;
  const leverage = effectiveRules.maxLeverage;

  const account = await exchange.getAccountState();
  const equityUsd = account?.equityUsd ?? 0;
  const availableUsd = account?.availableUsd ?? 0;

  let sizeDecimals = 6;
  try {
    const meta = await exchange.getInstrumentMeta(symbol);
    if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
  } catch {
    // best effort
  }

  const sizing = computeAllocationSize({ symbol, price, equityUsd, availableUsd, rules: effectiveRules, sizeDecimals });
  if (!sizing.ok) {
    return { size: 0, leverage };
  }
  return { size: sizing.size, leverage };
}

/**
 * One tick of the engulfing background monitor.
 * - Entry signals: detected on entryTimeframes[] when no open position → log + auto-order if autoConfirm
 * - Emergency exit signals: reverse engulfing on emergencyExitTimeframes[] when position is open → emergencyCloseAll
 */
async function runEngulfingMonitorTick(): Promise<void> {
  if (engulfingMonitorBusy) return;
  engulfingMonitorBusy = true;
  try {
    const effectiveRules = rulesCache.getEffectiveRules();
    const raw = effectiveRules.raw;
    if (!raw) return; // env fallback, no rules configured

    const symbols = getMonitoredSymbols(raw);
    const lookback = raw.engulfingLookbackCandles ?? 30;
    const entryTfs = raw.entryTimeframes?.length ? raw.entryTimeframes : ['15m' as const];
    const exitTfs = raw.emergencyExitTimeframes?.length ? raw.emergencyExitTimeframes : ['1h' as const];
    const minCandles = lookback + 5;
    const now = Date.now();

    // Fetch open positions once
    let positions: PositionSnapshot[] = [];
    try {
      positions = await exchange.getOpenPositions();
    } catch (err) {
      logger.warn({ component: 'engulfing-monitor', err }, 'failed to get open positions');
      return;
    }

    for (const symbol of symbols) {
      const operatorBias = await getOperatorBias(symbol);
      const symbolPosition = positions.find((p) => p.symbol.toUpperCase() === symbol.toUpperCase());
      if (symbolPosition) {
        await clearPendingConfirmationForSymbol(symbol);
      }

      // ── ENTRY signals (only when no open position for symbol) ────────
      if (!symbolPosition) {
      for (const tf of entryTfs) {
        try {
          const tfMs = TF_MS[tf] ?? 900_000;
          const candles = await exchange.getCandles({
            symbol,
            timeframe: TF_LABEL_TO_CANDLE_TF[tf],
            startTimeMs: now - tfMs * (minCandles + 2),
            endTimeMs: now,
          });

          const closedCandles = candles.filter((c) => Date.parse(c.timestamp) <= now - tfMs);
          const signal = evaluateTimeframe(closedCandles, tf, lookback);
          if (!signal.detected || !signal.direction) continue;

          const side: 'buy' | 'sell' = signal.direction === 'bullish' ? 'buy' : 'sell';
          const blockedByBias = operatorBias === 'off'
            || (operatorBias === 'short' && side !== 'sell')
            || (operatorBias === 'long' && side !== 'buy');
          if (blockedByBias) {
            logRiskGateAudit({
              gate: 'engulfing_entry_signal',
              passed: false,
              reason: 'operator_bias_block',
              details: { symbol, tf, direction: signal.direction, operatorBias, side },
            });
            continue;
          }

          // Debounce: skip if same signal fired within this candle period
          const debounceKey = `${symbol}:${tf}:${signal.direction}`;
          const lastFired = lastEntrySignalAt.get(debounceKey) ?? 0;
          if (now - lastFired < tfMs) continue;
          lastEntrySignalAt.set(debounceKey, now);

          logRiskGateAudit({
            gate: 'engulfing_entry_signal',
            passed: true,
            details: { symbol, tf, direction: signal.direction, confidence: signal.confidence, reason: signal.reason, operatorBias },
          });
          logger.info(
            { component: 'engulfing-monitor', symbol, tf, direction: signal.direction, confidence: signal.confidence, operatorBias },
            'engulfing entry signal detected',
          );

          const mid = await fetchLiveMid(symbol);
          if (!mid) { logger.warn({ component: 'engulfing-monitor' }, 'entry signal: no mid price'); continue; }

          // Manual mode: queue confirmation + notify, do not place order directly
          if (!raw.autoConfirm) {
            const estimate = await estimateSignalSize({ symbol, side, price: mid, effectiveRules });
            const correlationId = `engulf-pending-${nanoid(8)}`;
            const queued = await queuePendingConfirmation({
              symbol,
              side: side === 'buy' ? 'long' : 'short',
              strategy: 'engulfing',
              timeframe: tf,
              reason: signal.reason,
              price: mid,
              size: estimate.size,
              leverage: estimate.leverage,
              correlationId,
            });

            logger.info({ component: 'engulfing-monitor', symbol, tf, side, pendingId: queued.id, queued: queued.queued }, 'entry signal queued for manual confirmation');
            break;
          }

          // Auto-confirm mode: place order immediately
          try {
            const account = await exchange.getAccountState();
            const equityUsd = account?.equityUsd ?? 0;
            const availableUsd = account?.availableUsd ?? 0;
            if (equityUsd <= 0) { logger.warn({ component: 'engulfing-monitor' }, 'auto-entry: zero equity'); continue; }

            let sizeDecimals = 6;
            try { const meta = await exchange.getInstrumentMeta(symbol); if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals; } catch { /* best-effort */ }

            const sizing = computeAllocationSize({ symbol, price: mid, equityUsd, availableUsd, rules: effectiveRules, sizeDecimals });

            if (!sizing.ok) {
              logRiskGateAudit({ gate: 'engulfing_entry_signal', passed: false, reason: sizing.reason, details: { symbol, tf } });
              logger.warn({ component: 'engulfing-monitor', reason: sizing.reason }, 'auto-entry sizing failed');
              continue;
            }

            // Run risk gates before placing
            const risk = await evaluateRiskGates({ emitAudit: false });
            if (!risk.canTrade) {
              logger.warn({ component: 'engulfing-monitor', blocks: risk.blocks }, 'auto-entry blocked by risk gates');
              continue;
            }

            const correlationId = `engulf-auto-${nanoid(8)}`;
            const ack = await exchange.placeLimitOrder({ symbol, side, price: mid, size: sizing.size, reduceOnly: false, clientOrderId: correlationId });

            logRiskGateAudit({
              gate: 'engulfing_entry_signal',
              passed: ack.ok,
              reason: ack.ok ? 'auto_order_placed' : 'auto_order_failed',
              details: { symbol, tf, direction: signal.direction, side, size: sizing.size, price: mid, orderId: ack.orderId, error: ack.error },
            });
            logger.info({ component: 'engulfing-monitor', symbol, side, size: sizing.size, orderId: ack.orderId, ok: ack.ok }, 'auto-entry order result');

            // Auto-apply TP/SL if available
            if (ack.ok) {
              try {
                await notifyTradeOpen({ symbol, side, price: mid, size: sizing.size, source: 'engulfing:auto' });
              } catch (error) {
                logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
              }
              const tpSl = resolveTpSlDefaults(mid, side, undefined, undefined);
              if (tpSl) {
                try { await placeTpSlTriggerOrders(symbol, side, sizing.size, tpSl, correlationId, mid); } catch { /* best-effort */ }
              }
            }
          } catch (err) {
            logger.error({ component: 'engulfing-monitor', err }, 'auto-entry order failed');
          }
        } catch (err) {
          logger.warn({ component: 'engulfing-monitor', tf, err }, 'entry signal evaluation failed for tf');
        }
      }
    }

    // ── EMERGENCY EXIT signals (only when position is open) ──────────
    if (symbolPosition) {
      for (const tf of exitTfs) {
        try {
          const tfMs = TF_MS[tf] ?? 3_600_000;
          const candles = await exchange.getCandles({
            symbol,
            timeframe: TF_LABEL_TO_CANDLE_TF[tf],
            startTimeMs: now - tfMs * (minCandles + 2),
            endTimeMs: now,
          });

          const closedCandles = candles.filter((c) => Date.parse(c.timestamp) <= now - tfMs);
          const signal = evaluateTimeframe(closedCandles, tf, lookback);
          if (!signal.detected || !signal.direction) continue;

          // Reverse signal check: bullish position + bearish signal → exit
          const isLong = symbolPosition.side === 'long';
          const isReverseSignal = (isLong && signal.direction === 'bearish') || (!isLong && signal.direction === 'bullish');
          if (!isReverseSignal) continue;

          // One-shot per closed engulfing candle: prevent repeated emergency exits
          // on every monitor tick for the same TF signal.
          const signalCandleOpenMs = Date.parse(closedCandles[closedCandles.length - 1]?.timestamp ?? '');
          if (!Number.isFinite(signalCandleOpenMs)) continue;
          const exitDebounceKey = `${symbol}:${tf}:${signal.direction}`;
          const lastProcessedCandleMs = lastEmergencyExitSignalAt.get(exitDebounceKey) ?? -1;
          if (signalCandleOpenMs <= lastProcessedCandleMs) continue;
          lastEmergencyExitSignalAt.set(exitDebounceKey, signalCandleOpenMs);

          const reason = `engulfing_exit_signal_${signal.direction}`;
          const cachedExitClosePct = Number(raw.exitClosePct ?? 50);
          const exitClosePct = await getFreshExitClosePct(cachedExitClosePct);
          const closeFraction = exitClosePct / 100;

          if (exitClosePct <= 0) {
            logRiskGateAudit({
              gate: 'engulfing_emergency_exit',
              passed: true,
              reason: 'exit_close_pct_zero_skip',
              details: {
                symbol,
                tf,
                direction: signal.direction,
                positionSide: symbolPosition.side,
                exitClosePct,
                cachedExitClosePct,
                reason: signal.reason,
              },
            });
            logger.info(
              {
                component: 'engulfing-monitor',
                symbol,
                tf,
                direction: signal.direction,
                position: symbolPosition.side,
                exitClosePct,
                cachedExitClosePct,
              },
              'reverse engulfing detected — emergency exit disabled (0%)',
            );
            break;
          }

          logRiskGateAudit({
            gate: 'engulfing_emergency_exit',
            passed: true,
            details: {
              symbol,
              tf,
              direction: signal.direction,
              positionSide: symbolPosition.side,
              exitClosePct,
              cachedExitClosePct,
              reason: signal.reason,
            },
          });
          logger.warn(
            {
              component: 'engulfing-monitor',
              symbol,
              tf,
              direction: signal.direction,
              position: symbolPosition.side,
              exitClosePct,
              cachedExitClosePct,
            },
            'reverse engulfing detected — exit triggered',
          );

          if (closeFraction >= 0.9999) {
            // Full close for this symbol only.
            await emergencyCloseSymbol(symbol, reason);
          } else {
            // Partial close → then set SL at entry price (break-even)
            const posSize = symbolPosition.size;
            const closeSize = Math.max(0, Math.floor(posSize * closeFraction * 1e6) / 1e6);
            const closingSide: 'buy' | 'sell' = symbolPosition.side === 'long' ? 'sell' : 'buy';
            const markPrice = symbolPosition.markPrice ?? symbolPosition.entryPrice ?? 0;
            const exitPrice = markPrice > 0
              ? (closingSide === 'sell' ? markPrice * 0.985 : markPrice * 1.015)
              : (closingSide === 'sell' ? 1 : 999_999);

            try {
              const closeAck = await exchange.placeLimitOrder({
                symbol, side: closingSide, price: Number(exitPrice.toFixed(8)),
                size: closeSize, reduceOnly: true,
                clientOrderId: `partial-exit-${nanoid(8)}`,
              });
              logRiskGateAudit({
                gate: 'partial_close', passed: closeAck.ok,
                details: { symbol, closeSize, exitPrice, posSize, exitClosePct, orderId: closeAck.orderId, error: closeAck.error ?? null },
              });

              try {
                const db = await getDb();
                appendTradeEvent(db.data, {
                  symbol,
                  source: 'live',
                  type: closeAck.ok ? 'order_submitted' : 'order_rejected',
                  timestamp: new Date().toISOString(),
                  correlationId: closeAck.orderId ? `partial-close-${closeAck.orderId}` : `partial-close-${nanoid(8)}`,
                  side: symbolPosition.side,
                  price: Number(exitPrice.toFixed(8)),
                  quantity: closeSize,
                  reason: closeAck.ok ? 'engulfing_partial_close' : 'engulfing_partial_close_failed',
                  payload: {
                    exitClosePct,
                    posSize,
                    closeFraction,
                    orderId: closeAck.orderId ?? null,
                    error: closeAck.error ?? null,
                  },
                });
                await db.write();
              } catch {
                // best effort forensic log
              }

              if (!closeAck.ok) {
                throw new Error(closeAck.error || 'partial_close_order_rejected');
              }

              // Move SL to entry price (break-even) for remaining position.
              // Guarantee exactly one SL after partial close: cancel old SL(s), then place BE SL.
              const entryPrice = symbolPosition.entryPrice ?? markPrice;
              if (entryPrice > 0) {
                const remainingSize = Math.max(0, Math.round((posSize - closeSize) * 1e6) / 1e6);
                if (remainingSize > 0) {
                  const openOrders = await exchange.getOpenOrders(symbol).catch(() => []);
                  const isLikelyStopLoss = (order: Awaited<ReturnType<typeof exchange.getOpenOrders>>[number]) => {
                    const raw = order.raw as Record<string, unknown> | undefined;
                    const tpsl = String(
                      (raw as { tpsl?: unknown } | undefined)?.tpsl
                      ?? (raw as { trigger?: { tpsl?: unknown } } | undefined)?.trigger?.tpsl
                      ?? (raw as { orderType?: { trigger?: { tpsl?: unknown } } } | undefined)?.orderType?.trigger?.tpsl
                      ?? ''
                    ).toLowerCase();
                    if (tpsl === 'sl') return true;
                    if (tpsl === 'tp') return false;

                    const orderTypeText = JSON.stringify((raw as { orderType?: unknown } | undefined)?.orderType ?? '').toLowerCase();
                    const looksTp = orderTypeText.includes('take') || orderTypeText.includes('tp');
                    const looksSl = orderTypeText.includes('stop') || orderTypeText.includes('sl');
                    return looksSl && !looksTp;
                  };

                  const oldStops = openOrders.filter((o) => o.side === closingSide && isLikelyStopLoss(o));
                  for (const old of oldStops) {
                    await exchange.cancelOrder(old.id).catch(() => undefined);
                  }

                  const beAck = await exchange.placeTriggerOrder({
                    symbol, side: closingSide, size: remainingSize,
                    triggerPrice: entryPrice, kind: 'sl', reduceOnly: true,
                    clientOrderId: `be-sl-partial-${nanoid(8)}`,
                  });

                  logRiskGateAudit({
                    gate: 'break_even_sl_after_partial',
                    passed: beAck.ok,
                    details: {
                      symbol,
                      entryPrice,
                      remainingSize,
                      cancelledStops: oldStops.length,
                      orderId: beAck.orderId ?? null,
                      error: beAck.error ?? null,
                    },
                  });

                  if (!beAck.ok) {
                    throw new Error(beAck.error || 'break_even_sl_failed');
                  }

                  logger.info({ component: 'engulfing-monitor', symbol, entryPrice, remainingSize, cancelledStops: oldStops.length }, 'break-even SL placed after partial close');
                }
              }
            } catch (err) {
              logger.error({ component: 'engulfing-monitor', symbol, err }, 'partial close failed, falling back to symbol emergency close');
              await emergencyCloseSymbol(symbol, reason);
            }
          }
          break; // one exit action per tick is enough
        } catch (err) {
          logger.warn({ component: 'engulfing-monitor', tf, err }, 'exit signal evaluation failed for tf');
        }
      }
    }
  }
  } catch (err) {
    logger.error({ component: 'engulfing-monitor', err }, 'engulfing monitor tick failed');
  } finally {
    engulfingMonitorBusy = false;
  }
}

/** Compute poll interval from current rules: min entry TF / 10, clamped to [30s, 2m]. */
function engulfingMonitorIntervalMs(): number {
  const effective = rulesCache.getEffectiveRules();
  if (effective.source !== 'runtime' || !effective.raw) {
    // On startup before DB rules hydrate, poll fast to avoid a blind window.
    return 30_000;
  }
  const entryTfs = effective.raw.entryTimeframes?.length ? effective.raw.entryTimeframes : ['15m' as const];
  const minTfMs = Math.min(...entryTfs.map(tf => TF_MS[tf] ?? 900_000));
  return Math.max(30_000, Math.min(120_000, Math.floor(minTfMs / 10)));
}

function scheduleNextEngulfingTick(delayMs: number): void {
  if (engulfingMonitorTimer) clearTimeout(engulfingMonitorTimer);
  engulfingMonitorTimer = setTimeout(async () => {
    try {
      await runEngulfingMonitorTick();
    } catch (err) {
      logger.warn({ component: 'engulfing-monitor', err }, 'tick failed');
    } finally {
      const nextInterval = engulfingMonitorIntervalMs();
      if (nextInterval !== engulfingMonitorIntervalAppliedMs) {
        engulfingMonitorIntervalAppliedMs = nextInterval;
        logger.info({ component: 'engulfing-monitor', intervalMs: nextInterval }, 'engulfing monitor interval updated');
      }
      scheduleNextEngulfingTick(nextInterval);
    }
  }, delayMs);
  engulfingMonitorTimer.unref?.();
}

// ─── FVG Monitor Loop ─────────────────────────────────────────────────
/** Timeframes for FVG scanning (spec: 1H/4H only) */
const FVG_TIMEFRAMES: FvgTimeframe[] = ['1h', '4h'];
const FVG_TF_TO_CANDLE_TF: Record<FvgTimeframe, CandleTimeframe> = { '1h': '1h', '4h': '4h' };

let fvgMonitorTimer: NodeJS.Timeout | null = null;
let fvgMonitorBusy = false;

/** Debounce: key = `${symbol}:${tf}:${direction}`, value = last fired ms */
const lastFvgSignalAt = new Map<string, number>();

async function runFvgMonitorTick(): Promise<void> {
  if (fvgMonitorBusy) return;
  fvgMonitorBusy = true;
  try {
    const effectiveRules = rulesCache.getEffectiveRules();
    const raw = effectiveRules.raw;
    if (!raw) return; // env fallback

    const fvgRetracePct = raw.fvgRetrace ?? 50;
    if (!Number.isFinite(fvgRetracePct) || fvgRetracePct <= 0) return;

    const symbols = getMonitoredSymbols(raw);
    const now = Date.now();

    // Open positions (entry only when flat for each monitored symbol)
    let positions: PositionSnapshot[] = [];
    try { positions = await exchange.getOpenPositions(); } catch (err) {
      logger.warn({ component: 'fvg-monitor', err }, 'failed to get positions');
      return;
    }

    for (const symbol of symbols) {
      const operatorBias = await getOperatorBias(symbol);

      // Current mid price (required for retrace check)
      const mid = await fetchLiveMid(symbol);
      if (!mid) {
        logger.warn({ component: 'fvg-monitor', symbol }, 'no mid price, skipping symbol this tick');
        continue;
      }

      const symbolPosition = positions.find((p) => p.symbol.toUpperCase() === symbol.toUpperCase());

      // Only check entry signals when no open position for this symbol
      if (symbolPosition) {
        await clearPendingConfirmationForSymbol(symbol);
        continue;
      }

      for (const tf of FVG_TIMEFRAMES) {
        try {
          const tfMs = TF_MS[tf];
          const lookback = 10; // fixed lookback for FVG zone detection
          const candles = await exchange.getCandles({
            symbol,
            timeframe: FVG_TF_TO_CANDLE_TF[tf],
            startTimeMs: now - tfMs * (lookback + 25), // extra room for structure break (20 candles)
            endTimeMs: now,
          });

          const closedCandles = candles.filter((c) => Date.parse(c.timestamp) <= now - tfMs);
          const signal = evaluateFvg(closedCandles, tf, mid, fvgRetracePct, lookback);
          if (!signal.detected || !signal.direction) continue;

          const side: 'buy' | 'sell' = signal.direction === 'bullish' ? 'buy' : 'sell';
          const blockedByBias = operatorBias === 'off'
            || (operatorBias === 'short' && side !== 'sell')
            || (operatorBias === 'long' && side !== 'buy');
          if (blockedByBias) {
            logRiskGateAudit({
              gate: 'fvg_entry_signal',
              passed: false,
              reason: 'operator_bias_block',
              details: { symbol, tf, direction: signal.direction, operatorBias, side, currentPrice: mid, triggerPrice: signal.triggerPrice },
            });
            continue;
          }

        // Debounce: once per TF interval
        const debounceKey = `${symbol}:${tf}:${signal.direction}`;
        const lastFired = lastFvgSignalAt.get(debounceKey) ?? 0;
        if (now - lastFired < tfMs) continue;
        lastFvgSignalAt.set(debounceKey, now);

        logRiskGateAudit({
          gate: 'fvg_entry_signal',
          passed: true,
          details: {
            symbol, tf, direction: signal.direction,
            currentPrice: mid,
            triggerPrice: signal.triggerPrice,
            zoneTop: signal.zone?.top,
            zoneBottom: signal.zone?.bottom,
            fvgRetracePct,
            operatorBias,
            reason: signal.reason,
          },
        });
        logger.info(
          { component: 'fvg-monitor', symbol, tf, direction: signal.direction, mid, triggerPrice: signal.triggerPrice, operatorBias },
          'FVG retrace entry signal detected',
        );

        // Manual mode: queue signal for explicit confirmation
        if (!raw.autoConfirm) {
          const estimate = await estimateSignalSize({ symbol, side, price: mid, effectiveRules });
          const correlationId = `fvg-pending-${nanoid(8)}`;
          const queued = await queuePendingConfirmation({
            symbol,
            side: side === 'buy' ? 'long' : 'short',
            strategy: 'fvg',
            timeframe: tf,
            reason: signal.reason,
            price: mid,
            size: estimate.size,
            leverage: estimate.leverage,
            correlationId,
          });
          logger.info({ component: 'fvg-monitor', symbol, tf, side, pendingId: queued.id, queued: queued.queued }, 'FVG signal queued for manual confirmation');
          break;
        }

        // Auto-confirm mode: place order immediately
        try {
          const account = await exchange.getAccountState();
          const equityUsd = account?.equityUsd ?? 0;
          const availableUsd = account?.availableUsd ?? 0;
          if (equityUsd <= 0) { logger.warn({ component: 'fvg-monitor' }, 'auto-entry: zero equity'); continue; }

          let sizeDecimals = 6;
          try { const meta = await exchange.getInstrumentMeta(symbol); if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals; } catch { /* best-effort */ }

          const sizing = computeAllocationSize({ symbol, price: mid, equityUsd, availableUsd, rules: effectiveRules, sizeDecimals });

          if (!sizing.ok) {
            logRiskGateAudit({ gate: 'fvg_entry_signal', passed: false, reason: sizing.reason, details: { symbol, tf } });
            continue;
          }

          const risk = await evaluateRiskGates({ emitAudit: false });
          if (!risk.canTrade) { logger.warn({ component: 'fvg-monitor', blocks: risk.blocks }, 'auto-entry blocked by risk gates'); continue; }

          const correlationId = `fvg-auto-${nanoid(8)}`;
          const ack = await exchange.placeLimitOrder({ symbol, side, price: mid, size: sizing.size, reduceOnly: false, clientOrderId: correlationId });

          logRiskGateAudit({
            gate: 'fvg_entry_signal',
            passed: ack.ok,
            reason: ack.ok ? 'auto_order_placed' : 'auto_order_failed',
            details: { symbol, tf, direction: signal.direction, side, size: sizing.size, price: mid, orderId: ack.orderId, error: ack.error },
          });
          logger.info({ component: 'fvg-monitor', symbol, side, size: sizing.size, ok: ack.ok, orderId: ack.orderId }, 'FVG auto-entry result');

          if (ack.ok) {
            try {
              await notifyTradeOpen({ symbol, side, price: mid, size: sizing.size, source: 'fvg:auto' });
            } catch (error) {
              logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
            }
            const tpSl = resolveTpSlDefaults(mid, side, undefined, undefined);
            if (tpSl) { try { await placeTpSlTriggerOrders(symbol, side, sizing.size, tpSl, correlationId, mid); } catch { /* best-effort */ } }
          }
        } catch (err) {
          logger.error({ component: 'fvg-monitor', err }, 'FVG auto-entry order failed');
        }
      } catch (err) {
        logger.warn({ component: 'fvg-monitor', tf, err }, 'FVG signal evaluation failed for tf');
      }
    }
  }
  } catch (err) {
    logger.error({ component: 'fvg-monitor', err }, 'FVG monitor tick failed');
  } finally {
    fvgMonitorBusy = false;
  }
}

function startFvgMonitor(): void {
  if (!ENABLE_FVG_MONITOR) {
    logger.info({ component: 'fvg-monitor' }, 'FVG monitor disabled via ENABLE_FVG_MONITOR=false');
    return;
  }
  if (!exchange.capabilities.privateAccount || !exchange.capabilities.privateTrading) {
    logger.info({ component: 'fvg-monitor' }, 'FVG monitor not started (private account/trading unavailable)');
    return;
  }
  if (fvgMonitorTimer) return;

  runFvgMonitorTick().catch(err => logger.warn({ component: 'fvg-monitor', err }, 'initial tick failed'));
  fvgMonitorTimer = setInterval(() => {
    runFvgMonitorTick().catch(err => logger.warn({ component: 'fvg-monitor', err }, 'tick failed'));
  }, FVG_MONITOR_INTERVAL_MS);
  fvgMonitorTimer.unref?.();
  logger.info({ component: 'fvg-monitor', intervalMs: FVG_MONITOR_INTERVAL_MS }, 'FVG monitor started');
}

function startEngulfingMonitor(): void {
  if (!ENABLE_MULTI_TF_ENGULFING) {
    logger.info({ component: 'engulfing-monitor' }, 'engulfing monitor disabled via ENABLE_MULTI_TF_ENGULFING=false');
    return;
  }
  if (!exchange.capabilities.privateAccount || !exchange.capabilities.privateTrading) {
    logger.info({ component: 'engulfing-monitor' }, 'engulfing monitor not started (private account/trading unavailable)');
    return;
  }
  if (engulfingMonitorTimer) return;

  const intervalMs = engulfingMonitorIntervalMs();
  engulfingMonitorIntervalAppliedMs = intervalMs;
  logger.info({ component: 'engulfing-monitor', intervalMs }, 'engulfing monitor started');

  // First tick immediately, then self-schedule with dynamic interval from latest rules.
  scheduleNextEngulfingTick(0);
}

/** Risk gate middleware for trading endpoints — checks DD + leverage before allowing order */
function isProtectionOnlyRequest(req: Request): boolean {
  const p = (req.path || req.originalUrl || '').toLowerCase();
  return p.startsWith('/api/live/position/levels');
}

async function riskGateMiddleware(req: Request, res: Response, next: NextFunction) {
  try {
    const protectionOnly = isProtectionOnlyRequest(req);
    const reduceOnly = req.body?.reduceOnly === true || protectionOnly;

    // If DD lock is active, block new entry orders but always allow reduce-only exits.
    if (ddLock.active && !reduceOnly) {
      return res.status(403).json({
        ok: false,
        errorCode: 'dd_lock_active' as TradingErrorCode,
        error: 'DD lock is active. New entry orders are blocked until owner resets the lock.',
        ddLock: {
          active: true,
          activatedAt: ddLock.activatedAt,
        },
      });
    }

    const risk = await evaluateRiskGates();
    const effectiveRules = rulesCache.getEffectiveRules();

    if (risk.blocks.includes('daily_loss_limit_exceeded')) {
      if (!ddLock.active) {
        ddLock.active = true;
        ddLock.activatedAt = new Date().toISOString();
      }

      // Keep exits possible even while DD lock is active.
      if (reduceOnly) {
        (req as any)._riskCheck = risk;
        return next();
      }

      // Hard stop for new entries: close everything and block.
      await emergencyCloseAll();
      return res.status(403).json({
        ok: false,
        errorCode: 'dd_lock_active' as TradingErrorCode,
        error: `Daily drawdown ${risk.dailyDDPct}% exceeds ${effectiveRules.dailyDDLimitPct}% limit. DD lock activated; new entries blocked until reset.`,
        riskCheck: risk,
        ddLock: {
          active: true,
          activatedAt: ddLock.activatedAt,
        },
      });
    }

    if (risk.blocks.includes('leverage_limit_exceeded')) {
      // Only block new non-reduceOnly orders
      if (!reduceOnly) {
        return res.status(403).json({
          ok: false,
          errorCode: 'leverage_limit_exceeded' as TradingErrorCode,
          error: `Portfolio leverage ${risk.portfolioLeverage}x exceeds ${effectiveRules.portfolioLeverageCap}x cap. Reduce positions first.`,
          riskCheck: risk
        });
      }
    }

    // Attach risk check to request for downstream use
    (req as any)._riskCheck = risk;
    next();
  } catch (error) {
    logger.error({ component: 'risk-gate', err: error }, 'risk evaluation failed, blocking trade (fail-closed)');
    logRiskGateAudit({ gate: 'daily_dd', passed: false, reason: 'risk_check_unavailable' });
    return res.status(503).json({
      ok: false,
      errorCode: 'risk_check_unavailable' as TradingErrorCode,
      error: 'Risk engine unavailable. Trading is temporarily blocked.'
    });
  }
}

/** Symbol allowlist + allocation cap middleware — runs after riskGateMiddleware */
async function symbolAllocationGate(req: Request, res: Response, next: NextFunction) {
  try {
    // Skip for reduce-only orders and protection-only management endpoints.
    if (req.body?.reduceOnly === true || isProtectionOnlyRequest(req)) return next();

    const symbol = normalizeSymbol(req.body?.symbol);
    const effectiveRules = rulesCache.getEffectiveRules();

    // 1. Symbol allowlist check
    if (!isSymbolEnabled(effectiveRules, symbol)) {
      logRiskGateAudit({
        gate: 'symbol_allowlist',
        passed: false,
        reason: 'symbol_not_enabled',
        details: { symbol }
      });
      return res.status(403).json({
        ok: false,
        errorCode: 'symbol_not_enabled' as TradingErrorCode,
        error: `Symbol ${symbol} is not enabled in trading rules.`,
        symbol
      });
    }

    // 2. Allocation cap check (best-effort: uses mark/entry price from open positions)
    const price = Number(req.body?.price);
    const size = Number(req.body?.size);
    if (Number.isFinite(price) && price > 0 && Number.isFinite(size) && size > 0) {
      const riskCheck: RiskCheckResult | undefined = (req as any)._riskCheck;
      const equityUsd = riskCheck?.equityUsd ?? 0;
      const cap = maxNotionalForSymbol(equityUsd, effectiveRules, symbol);

      if (cap > 0 && equityUsd > 0) {
        // Current exposure for this symbol from open positions
        let currentExposure = 0;
        try {
          const positions = await exchange.getOpenPositions();
          for (const pos of positions) {
            if (pos.symbol.toUpperCase() === symbol) {
              currentExposure += (pos.entryPrice ?? pos.markPrice ?? 0) * pos.size;
            }
          }
        } catch {
          // best-effort: if we can't fetch positions, skip exposure calc
        }

        const newNotional = price * size;
        const totalExposure = currentExposure + newNotional;

        if (totalExposure > cap) {
          logRiskGateAudit({
            gate: 'allocation_cap',
            passed: false,
            reason: 'allocation_limit_exceeded',
            details: {
              symbol,
              newNotional: Number(newNotional.toFixed(2)),
              currentExposure: Number(currentExposure.toFixed(2)),
              totalExposure: Number(totalExposure.toFixed(2)),
              cap: Number(cap.toFixed(2)),
              equityUsd: Number(equityUsd.toFixed(2))
            }
          });
          return res.status(403).json({
            ok: false,
            errorCode: 'allocation_limit_exceeded' as TradingErrorCode,
            error: `Order would bring ${symbol} exposure to $${totalExposure.toFixed(2)}, exceeding allocation cap of $${cap.toFixed(2)}.`,
            symbol,
            currentExposure: Number(currentExposure.toFixed(2)),
            newNotional: Number(newNotional.toFixed(2)),
            totalExposure: Number(totalExposure.toFixed(2)),
            cap: Number(cap.toFixed(2))
          });
        }
      }

      logRiskGateAudit({
        gate: 'allocation_cap',
        passed: true,
        details: { symbol }
      });
    }

    // Symbol is enabled and within cap
    logRiskGateAudit({
      gate: 'symbol_allowlist',
      passed: true,
      details: { symbol }
    });

    next();
  } catch (error) {
    logger.error({ component: 'risk-gate', err: error }, 'symbol/allocation check failed, blocking trade (fail-closed)');
    logRiskGateAudit({ gate: 'allocation_cap', passed: false, reason: 'allocation_check_unavailable' });
    return res.status(503).json({
      ok: false,
      errorCode: 'allocation_check_unavailable' as TradingErrorCode,
      error: 'Allocation guard unavailable. Trading is temporarily blocked.'
    });
  }
}

async function staleMarketDataGate(req: Request, res: Response, next: NextFunction) {
  try {
    const body = (req.body ?? {}) as { symbol?: string; reduceOnly?: boolean };
    const symbol = normalizeSymbol(body.symbol ?? LIVE_SYMBOL);

    // Reduce-only operations lower risk; allow them even when feed is stale.
    if (body.reduceOnly) {
      return next();
    }

    const fresh = await ensureFreshTick(symbol);
    if (fresh.ok) {
      return next();
    }

    logRiskGateAudit({
      gate: 'market_data',
      passed: false,
      reason: 'stale_market_data',
      details: {
        symbol,
        staleMs: fresh.staleMs,
        staleThresholdMs: LIVE_TICK_STALE_MS,
        source: fresh.source
      }
    });

    return res.status(503).json({
      ok: false,
      errorCode: 'stale_market_data' as TradingErrorCode,
      error: 'Market data is stale. New entry orders are temporarily blocked.',
      details: {
        symbol,
        staleMs: fresh.staleMs,
        staleThresholdMs: LIVE_TICK_STALE_MS
      }
    });
  } catch (error) {
    logger.error({ component: 'market-data', err: error }, 'stale market data gate failed, blocking trade');
    return res.status(503).json({
      ok: false,
      errorCode: 'stale_market_data' as TradingErrorCode,
      error: 'Market data validation unavailable. Trading is temporarily blocked.'
    });
  }
}

const exchange = new HyperliquidAdapter();

// ─── Multi-TF Engulfing Gate (feature-flagged) ─────────────────────────
const TF_LABEL_TO_CANDLE_TF: Record<TradingRulesTimeframe, CandleTimeframe> = {
  '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h',
};

const TF_MS: Record<TradingRulesTimeframe, number> = {
  '5m': 5 * 60_000,
  '15m': 15 * 60_000,
  '1h': 60 * 60_000,
  '4h': 4 * 60 * 60_000,
};

async function engulfingGate(req: Request, res: Response, next: NextFunction) {

  const body = (req.body ?? {}) as { symbol?: string; reduceOnly?: boolean };
  if (body.reduceOnly) return next();

  try {
    const effectiveRules = rulesCache.getEffectiveRules();
    const raw = effectiveRules.raw;

    // Fail-safe: rules unavailable => allow through, but audit explicit reason.
    if (!raw) {
      logRiskGateAudit({
        gate: 'multi_tf_engulfing',
        passed: true,
        reason: 'rules_unavailable_failsafe',
      });
      return next();
    }

    const symbol = normalizeSymbol(body.symbol ?? LIVE_SYMBOL);
    const lookback = raw.engulfingLookbackCandles ?? 30;
    const entryTfs = raw.entryTimeframes;
    const exitTfs = raw.emergencyExitTimeframes;

    const allTfs = new Set([...entryTfs, ...exitTfs]);
    const candlesByTf = new Map<TradingRulesTimeframe, Candle[]>();
    const fetchFailedTfs: TradingRulesTimeframe[] = [];

    const now = Date.now();
    const minCandles = lookback + 5;

    await Promise.all([...allTfs].map(async (tf) => {
      try {
        const tfMs = ({ '5m': 300_000, '15m': 900_000, '1h': 3_600_000, '4h': 14_400_000 })[tf] ?? 900_000;
        const startTimeMs = now - tfMs * (minCandles + 2);
        const candles = await exchange.getCandles({
          symbol,
          timeframe: TF_LABEL_TO_CANDLE_TF[tf],
          startTimeMs,
          endTimeMs: now,
        });
        candlesByTf.set(tf, candles);
      } catch (err) {
        fetchFailedTfs.push(tf);
        logger.warn({ component: 'engulfing-gate', tf, err }, 'candle fetch failed for tf');
      }
    }));

    // Fail-safe: data fetch failed => allow through, but audit explicit reason.
    if (fetchFailedTfs.length > 0) {
      logRiskGateAudit({
        gate: 'multi_tf_engulfing',
        passed: true,
        reason: 'candle_fetch_error_failsafe',
        details: { symbol, failedTimeframes: fetchFailedTfs },
      });
      return next();
    }

    const result = evaluateMultiTf(candlesByTf, {
      lookbackCandles: lookback,
      entryTimeframes: entryTfs,
      emergencyExitTimeframes: exitTfs,
    });

    // Attach result for downstream handlers to inspect
    (req as any)._engulfingResult = result;

    // Hard gate under feature-flag: no entry signal => block order.
    if (!result.anyEntry) {
      logRiskGateAudit({
        gate: 'multi_tf_engulfing',
        passed: false,
        reason: 'no_engulfing_entry_signal',
        details: {
          symbol,
          signals: result.entry.map((s) => ({ tf: s.timeframe, detected: s.detected, reason: s.reason })),
        },
      });

      return res.status(403).json({
        ok: false,
        errorCode: 'no_engulfing_entry_signal' as TradingErrorCode,
        error: 'No engulfing entry signal detected for configured Trading Rules timeframes.',
      });
    }

    logRiskGateAudit({
      gate: 'multi_tf_engulfing',
      passed: true,
      details: {
        symbol,
        anyEntry: result.anyEntry,
        signals: result.entry.map((s) => ({ tf: s.timeframe, detected: s.detected })),
      },
    });

    return next();
  } catch (error) {
    logRiskGateAudit({
      gate: 'multi_tf_engulfing',
      passed: true,
      reason: 'gate_exception_failsafe',
      details: { error: error instanceof Error ? error.message : String(error) },
    });
    logger.error({ component: 'engulfing-gate', err: error }, 'engulfing gate error, allowing trade through');
    return next();
  }
}

let ingestBusy = false;
let wsReconnectTimer: NodeJS.Timeout | null = null;
let restFallbackTimer: NodeJS.Timeout | null = null;
let midStreamHandle: MidStreamHandle | null = null;
let latestLiveTick: { symbol: string; price: number; timestamp: string } | null = null;
const latestTickBySymbol = new Map<string, { price: number; timestamp: string; source: 'ws' | 'rest' }>();

// ─── WS reconnect backoff state ──────────────────────────────────────
const WS_BACKOFF_INITIAL_MS = 1000;
const WS_BACKOFF_MAX_MS = 60_000;
let wsBackoffMs = WS_BACKOFF_INITIAL_MS;
const wsDiag = { reconnectAttempts: 0, disconnectCount: 0, lastReconnectDelayMs: 0 };

function parseTimeframe(raw: unknown): CandleTimeframe {
  if (raw === '1m' || raw === '5m' || raw === '15m' || raw === '1h' || raw === '4h') {
    return raw;
  }
  return '5m';
}

function timeframeToMs(timeframe: CandleTimeframe): number {
  if (timeframe === '1m') return 60_000;
  if (timeframe === '5m') return 5 * 60_000;
  if (timeframe === '15m') return 15 * 60_000;
  if (timeframe === '1h') return 60 * 60_000;
  return 4 * 60 * 60_000;
}

function normalizeSymbol(raw: unknown): string {
  return String(raw ?? LIVE_SYMBOL).toUpperCase();
}

function enabledAllocationTotalPct(rules: TradingRulesSettings): number {
  const total = rules.coins
    .filter((coin) => coin.enabled)
    .reduce((sum, coin) => sum + Number(coin.pct || 0), 0);
  return Math.round(total * 100) / 100;
}

function toTradeSide(side: 'buy' | 'sell'): 'long' | 'short' {
  return side === 'buy' ? 'long' : 'short';
}

function isConfirmed(raw: unknown): boolean {
  return raw === true;
}

function maskAddress(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const v = value.trim();
  if (v.length <= 10) return v;
  return `${v.slice(0, 6)}…${v.slice(-4)}`;
}

function maskPrivateKey(value: string | undefined): string {
  if (!value) return '';
  const v = value.trim();
  if (v.length <= 12) return '••••••';
  return `${v.slice(0, 6)}••••${v.slice(-4)}`;
}

async function patchEnvFile(patch: Record<string, string>): Promise<void> {
  let raw = '';
  try {
    raw = await fs.readFile(COINMASTER_ENV_PATH, 'utf-8');
  } catch {
    raw = '';
  }

  const lines = raw.split(/\r?\n/);
  const nextLines = [...lines];

  for (const [key, value] of Object.entries(patch)) {
    const prefix = `${key}=`;
    const idx = nextLines.findIndex((line) => line.startsWith(prefix));
    const serialized = `${key}=${value}`;
    if (idx >= 0) {
      nextLines[idx] = serialized;
    } else {
      nextLines.push(serialized);
    }
    process.env[key] = value;
  }

  const output = `${nextLines.filter((line, i, arr) => !(i === arr.length - 1 && line === '')).join('\n')}\n`;
  await fs.writeFile(COINMASTER_ENV_PATH, output, 'utf-8');
}

async function ingestPrice(symbol: string, price: number, source: 'ws' | 'rest') {
  if (!Number.isFinite(price)) return;

  const normalizedSymbol = normalizeSymbol(symbol);
  const timestamp = new Date().toISOString();

  latestTickBySymbol.set(normalizedSymbol, {
    price,
    timestamp,
    source
  });

  // Keep dashboard latest tick anchored to LIVE_SYMBOL.
  if (normalizedSymbol === LIVE_SYMBOL) {
    latestLiveTick = {
      symbol: normalizedSymbol,
      price,
      timestamp
    };
  }

  if (!ENABLE_PAPER_ENGINE) return;
  if (ingestBusy) return;

  ingestBusy = true;
  try {
    const db = await getDb();
    runSimulationStep(db.data, normalizedSymbol, price);
    await db.write();
  } finally {
    ingestBusy = false;
  }
}

function tickAgeMs(symbol: string): number | null {
  const tick = latestTickBySymbol.get(normalizeSymbol(symbol));
  if (!tick) return null;
  const age = Date.now() - new Date(tick.timestamp).getTime();
  return Number.isFinite(age) ? Math.max(0, age) : null;
}

async function fetchLiveMid(symbol = LIVE_SYMBOL): Promise<number | null> {
  try {
    const normalizedSymbol = normalizeSymbol(symbol);
    const mids = await exchange.getMids();
    const price = mids[normalizedSymbol];
    return Number.isFinite(price) ? price : null;
  } catch {
    return null;
  }
}

async function ensureFreshTick(symbol: string): Promise<{ ok: boolean; staleMs: number | null; source: 'cache' | 'rest' | 'none' }> {
  const normalizedSymbol = normalizeSymbol(symbol);
  const age = tickAgeMs(normalizedSymbol);
  if (age !== null && age <= LIVE_TICK_STALE_MS) {
    return { ok: true, staleMs: age, source: 'cache' };
  }

  const price = await fetchLiveMid(normalizedSymbol);
  if (price) {
    await ingestPrice(normalizedSymbol, price, 'rest');
    return { ok: true, staleMs: 0, source: 'rest' };
  }

  return { ok: false, staleMs: age, source: 'none' };
}

async function ingestRestFallback() {
  const price = await fetchLiveMid(LIVE_SYMBOL);
  if (!price) return;
  await ingestPrice(LIVE_SYMBOL, price, 'rest');
}

function startRestFallback() {
  if (restFallbackTimer) return;
  restFallbackTimer = setInterval(() => {
    ingestRestFallback().catch((err) => logger.warn({ component: 'live', err }, 'REST fallback ingest failed'));
  }, REST_FALLBACK_MS);
  restFallbackTimer.unref?.();
}

function scheduleWsReconnect() {
  if (wsReconnectTimer) return;
  const delay = wsBackoffMs;
  wsDiag.reconnectAttempts++;
  wsDiag.lastReconnectDelayMs = delay;
  logger.info({ component: 'live', delayMs: delay, attempt: wsDiag.reconnectAttempts }, 'scheduling WS reconnect');
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    startLiveMidStream();
  }, delay);
  wsReconnectTimer.unref?.();
  // Exponential backoff: double up to cap
  wsBackoffMs = Math.min(wsBackoffMs * 2, WS_BACKOFF_MAX_MS);
}

function resetWsBackoff() {
  wsBackoffMs = WS_BACKOFF_INITIAL_MS;
}

function startLiveMidStream() {
  if (!exchange.subscribeMids) {
    logger.info({ component: 'live' }, 'exchange adapter has no mid stream, using REST fallback each minute');
    startRestFallback();
    return;
  }

  if (midStreamHandle) return;

  try {
    midStreamHandle = exchange.subscribeMids({
      symbols: [LIVE_SYMBOL],
      onOpen: () => {
        logger.info({ component: 'live' }, 'Hyperliquid WS connected');
        resetWsBackoff();
        startRestFallback(); // keep fallback as safety net
      },
      onMid: (symbol, price) => {
        ingestPrice(symbol, price, 'ws').catch((err) => logger.warn({ component: 'live', symbol, err }, 'WS price ingest failed'));
      },
      onClose: () => {
        wsDiag.disconnectCount++;
        logger.info({ component: 'live', disconnects: wsDiag.disconnectCount }, 'Hyperliquid WS disconnected, reconnecting...');
        midStreamHandle = null;
        scheduleWsReconnect();
      },
      onError: () => {
        // close event handles reconnect flow
      }
    });
  } catch {
    logger.warn({ component: 'live' }, 'Hyperliquid WS start failed, using REST fallback each minute');
    midStreamHandle = null;
    startRestFallback();
    scheduleWsReconnect();
  }
}

app.use(cors());
app.use(express.json({ limit: process.env.API_JSON_LIMIT || '256kb' }));

// ─── In-memory rate limiter (/api/* except health) ────────────────────
const RATE_LIMIT_RPM = Math.max(1, Number(process.env.API_RATE_LIMIT_RPM || 120));
const RATE_LIMIT_WINDOW_MS = 60_000;
const rateLimitMap = new Map<string, number[]>();

// Prune stale entries every 2 minutes to prevent unbounded growth
const rateLimitPruneTimer = setInterval(() => {
  const cutoff = Date.now() - RATE_LIMIT_WINDOW_MS;
  for (const [ip, timestamps] of rateLimitMap) {
    const fresh = timestamps.filter(t => t > cutoff);
    if (fresh.length === 0) rateLimitMap.delete(ip);
    else rateLimitMap.set(ip, fresh);
  }
}, 2 * 60_000);
rateLimitPruneTimer.unref();

app.use('/api', (req: Request, res: Response, next: NextFunction) => {
  // Exclude health endpoints from rate limiting
  if (req.path === '/health' || req.path === '/health/perf') return next();

  const ip = req.ip || req.socket.remoteAddress || 'unknown';
  const now = Date.now();
  const cutoff = now - RATE_LIMIT_WINDOW_MS;

  let timestamps = rateLimitMap.get(ip);
  if (!timestamps) {
    timestamps = [];
    rateLimitMap.set(ip, timestamps);
  }

  // Remove expired entries for this IP
  while (timestamps.length > 0 && timestamps[0] <= cutoff) {
    timestamps.shift();
  }

  if (timestamps.length >= RATE_LIMIT_RPM) {
    logger.warn({ component: 'rate-limit', ip, count: timestamps.length, limit: RATE_LIMIT_RPM }, 'rate limit exceeded');
    return res.status(429).json({ ok: false, error: 'rate_limited' });
  }

  timestamps.push(now);
  next();
});

app.get('/api/health', (_req, res) => res.json({ ok: true }));

// ─── Performance / observability (non-invasive) ──────────────────────
app.get('/api/health/perf', (_req, res) => {
  const mem = process.memoryUsage();
  const start = performance.now();
  setImmediate(() => {
    const lagMs = Math.round((performance.now() - start) * 100) / 100;
    res.json({
      ok: true,
      uptimeSeconds: Math.round(process.uptime()),
      memory: {
        rss: Math.round(mem.rss / 1024 / 1024 * 100) / 100,
        heapTotal: Math.round(mem.heapTotal / 1024 / 1024 * 100) / 100,
        heapUsed: Math.round(mem.heapUsed / 1024 / 1024 * 100) / 100,
        external: Math.round(mem.external / 1024 / 1024 * 100) / 100,
      },
      eventLoopLagMs: lagMs,
      ws: {
        reconnectAttempts: wsDiag.reconnectAttempts,
        lastReconnectDelayMs: wsDiag.lastReconnectDelayMs,
        disconnectCount: wsDiag.disconnectCount,
        connected: midStreamHandle !== null,
      },
      marketData: {
        liveSymbol: LIVE_SYMBOL,
        staleThresholdMs: LIVE_TICK_STALE_MS,
        lastTickAgeMs: tickAgeMs(LIVE_SYMBOL),
        stale: (() => {
          const age = tickAgeMs(LIVE_SYMBOL);
          return age === null ? true : age > LIVE_TICK_STALE_MS;
        })()
      },
      timestamp: new Date().toISOString(),
    });
  });
});

app.get('/api/dashboard', async (_req, res) => {
  const db = await getDb();
  const latestBias = [...db.data.biasCommands].reverse().find((b) => b.symbol === LIVE_SYMBOL)?.bias ?? 'off';

  let latestTick = latestLiveTick;
  if (!latestTick) {
    const freshMid = await fetchLiveMid(LIVE_SYMBOL);
    if (freshMid) {
      latestTick = {
        symbol: LIVE_SYMBOL,
        price: freshMid,
        timestamp: new Date().toISOString()
      };
    }
  }

  const pendingRows = await loadPendingConfirmationRows();
  const live = await buildLiveDashboardState(exchange, LIVE_SYMBOL, getLiveMode(), pendingRows);

  res.json({ latestBias, latestTick: latestTick ?? null, live });
});

app.get('/api/live/history', async (_req, res) => {
  try {
    const fills = await exchange.getFills();
    const rows = fills
      .map(toLiveFill)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp));

    return res.json({ fills: rows });
  } catch (error) {
    return res.status(500).json({
      fills: [],
      error: error instanceof Error ? error.message : 'live_history_failed'
    });
  }
});

app.get('/api/live/candles', async (req, res) => {
  const symbol = normalizeSymbol(req.query.symbol);
  const timeframe = parseTimeframe(req.query.timeframe);
  const limit = Math.max(50, Math.min(500, Number(req.query.limit) || 200));
  const endTimeMs = Date.now();
  const startTimeMs = endTimeMs - timeframeToMs(timeframe) * (limit + 5);

  try {
    const candles = await exchange.getCandles({ symbol, timeframe, startTimeMs, endTimeMs });
    const rows = candles.slice(-limit);
    return res.json({ symbol, timeframe, candles: rows });
  } catch (error) {
    return res.status(500).json({
      symbol,
      timeframe,
      candles: [],
      error: error instanceof Error ? error.message : 'live_candles_failed'
    });
  }
});

app.get('/api/settings/trading-rules', async (_req, res) => {
  const db = await getDb();
  const rules = normalizeTradingRules(db.data.settings.tradingRules);

  if (JSON.stringify(rules) !== JSON.stringify(db.data.settings.tradingRules)) {
    db.data.settings.tradingRules = rules;
    await db.write();
  }

  return res.json({ ok: true, rules });
});

app.put('/api/settings/trading-rules', async (req, res) => {
  const rules = normalizeTradingRules(req.body);
  const enabled = rules.coins.filter((coin) => coin.enabled);
  const totalPct = enabledAllocationTotalPct(rules);

  if (enabled.length === 0) {
    return res.status(400).json({ ok: false, error: 'at_least_one_coin_required' });
  }

  if (Math.abs(totalPct - 100) > 0.01) {
    return res.status(400).json({
      ok: false,
      error: 'allocation_total_must_be_100',
      totalPct
    });
  }

  const db = await getDb();
  db.data.settings.tradingRules = rules;
  await db.write();

  // Ensure monitors pick up new rules immediately (no cache-delay window).
  await rulesCache.refreshNow().catch((err) => logger.warn({ component: 'runtime-rules', err }, 'forced rules refresh failed'));

  return res.json({ ok: true, rules });
});

// ─── Effective Trading Rules (diagnostic) ─────────────────────────────
app.get('/api/settings/trading-rules/effective', ownerAuth, (_req, res) => {
  return res.json({ ok: true, ...rulesCache.getEffectiveRules() });
});

app.get('/api/settings/exchange', async (_req, res) => {
  const liveMode = getLiveMode();
  const live = await buildLiveDashboardState(exchange, LIVE_SYMBOL, liveMode);

  const db = await getDb();
  const tg = db.data.settings.telegramNotify;

  return res.json({
    exchange: exchange.name,
    connected: live.connected,
    accountAddress: maskAddress(process.env.HYPERLIQUID_ACCOUNT_ADDRESS),
    walletAddress: maskAddress(process.env.HYPERLIQUID_API_WALLET_ADDRESS),
    mode: liveMode,
    account: live.account,
    capabilities: {
      privateAccount: exchange.capabilities.privateAccount,
      privateTrading: exchange.capabilities.privateTrading,
      realtimeMids: exchange.capabilities.realtimeMids
    },
    hyperliquid: {
      accountAddress: process.env.HYPERLIQUID_ACCOUNT_ADDRESS || '',
      apiWalletAddress: process.env.HYPERLIQUID_API_WALLET_ADDRESS || '',
      hasPrivateKey: Boolean(process.env.HYPERLIQUID_API_PRIVATE_KEY),
      privateKeyMasked: maskPrivateKey(process.env.HYPERLIQUID_API_PRIVATE_KEY),
    },
    telegramNotify: {
      hasToken: Boolean(tg?.botToken?.trim() || TELEGRAM_BOT_TOKEN),
      chatId: tg?.chatId || TELEGRAM_CHAT_ID,
      botTokenMasked: maskBotToken(String(tg?.botToken || TELEGRAM_BOT_TOKEN || '')),
      notifyOpen: tg?.notifyOpen !== false,
      notifyTp: tg?.notifyTp !== false,
      notifySl: tg?.notifySl !== false,
      notifyManualConfirm: tg?.notifyManualConfirm !== false,
    },
    error: live.error
  });
});

app.put('/api/settings/exchange/hyperliquid', ownerAuth, async (req, res) => {
  const {
    accountAddress,
    apiWalletAddress,
    apiPrivateKey,
  } = req.body as {
    accountAddress?: string;
    apiWalletAddress?: string;
    apiPrivateKey?: string;
  };

  const patch: Record<string, string> = {};

  if (accountAddress !== undefined) {
    const value = String(accountAddress).trim();
    if (value && !/^0x[a-fA-F0-9]{40}$/.test(value)) {
      return res.status(400).json({ ok: false, error: 'invalid_account_address' });
    }
    patch.HYPERLIQUID_ACCOUNT_ADDRESS = value;
  }

  if (apiWalletAddress !== undefined) {
    const value = String(apiWalletAddress).trim();
    if (value && !/^0x[a-fA-F0-9]{40}$/.test(value)) {
      return res.status(400).json({ ok: false, error: 'invalid_api_wallet_address' });
    }
    patch.HYPERLIQUID_API_WALLET_ADDRESS = value;
  }

  if (apiPrivateKey !== undefined) {
    const value = String(apiPrivateKey).trim();
    if (value && !/^0x[a-fA-F0-9]{64}$/.test(value)) {
      return res.status(400).json({ ok: false, error: 'invalid_api_private_key_format' });
    }
    patch.HYPERLIQUID_API_PRIVATE_KEY = value;
  }

  if (Object.keys(patch).length === 0) {
    return res.status(400).json({ ok: false, error: 'no_fields_provided' });
  }

  await patchEnvFile(patch);

  const responsePayload = {
    ok: true,
    restartScheduled: true,
    exchange: {
      accountAddress: process.env.HYPERLIQUID_ACCOUNT_ADDRESS || '',
      apiWalletAddress: process.env.HYPERLIQUID_API_WALLET_ADDRESS || '',
      hasPrivateKey: Boolean(process.env.HYPERLIQUID_API_PRIVATE_KEY),
      privateKeyMasked: maskPrivateKey(process.env.HYPERLIQUID_API_PRIVATE_KEY),
    },
  };

  res.json(responsePayload);

  setTimeout(() => {
    logger.warn({ component: 'server' }, 'restarting process to apply Hyperliquid credential changes');
    process.exit(0);
  }, 350);
});

app.put('/api/settings/telegram-notify', ownerAuth, async (req, res) => {
  const {
    botToken,
    chatId,
    notifyOpen,
    notifyTp,
    notifySl,
    notifyManualConfirm,
  } = req.body as {
    botToken?: string;
    chatId?: string;
    notifyOpen?: boolean;
    notifyTp?: boolean;
    notifySl?: boolean;
    notifyManualConfirm?: boolean;
  };

  const db = await getDb();
  const current = db.data.settings.telegramNotify ?? {
    botToken: '',
    chatId: '',
    notifyOpen: true,
    notifyTp: true,
    notifySl: true,
    notifyManualConfirm: true,
  };

  db.data.settings.telegramNotify = {
    botToken: botToken !== undefined ? String(botToken).trim() : current.botToken,
    chatId: chatId !== undefined ? String(chatId).trim() : current.chatId,
    notifyOpen: notifyOpen !== undefined ? Boolean(notifyOpen) : current.notifyOpen,
    notifyTp: notifyTp !== undefined ? Boolean(notifyTp) : current.notifyTp,
    notifySl: notifySl !== undefined ? Boolean(notifySl) : current.notifySl,
    notifyManualConfirm: notifyManualConfirm !== undefined ? Boolean(notifyManualConfirm) : current.notifyManualConfirm,
  };

  await db.write();

  if (!telegramUpdateTimer) startTelegramUpdateLoop();
  if (!telegramOutboxTimer) startTelegramOutboxLoop();

  return res.json({
    ok: true,
    telegramNotify: {
      hasToken: Boolean(db.data.settings.telegramNotify.botToken),
      chatId: db.data.settings.telegramNotify.chatId,
      botTokenMasked: maskBotToken(db.data.settings.telegramNotify.botToken),
      notifyOpen: db.data.settings.telegramNotify.notifyOpen,
      notifyTp: db.data.settings.telegramNotify.notifyTp,
      notifySl: db.data.settings.telegramNotify.notifySl,
      notifyManualConfirm: db.data.settings.telegramNotify.notifyManualConfirm,
    },
  });
});

app.post('/api/settings/telegram-notify/test', ownerAuth, async (_req, res) => {
  const cfg = await getTelegramConfig();
  if (!cfg) {
    return res.status(400).json({ ok: false, error: 'telegram_not_configured' });
  }
  await enqueueTelegramOutbox({
    category: 'system',
    dedupeKey: `test:${Math.floor(Date.now() / 10000)}`,
    text: `✅ Coinmaster Telegram test ping\nTime: ${new Date().toISOString()}`,
  });
  return res.json({ ok: true });
});

app.get('/api/settings/telegram-notify/health', ownerAuth, async (_req, res) => {
  const db = await getDb();
  const outbox = Array.isArray(db.data.telegramOutbox) ? db.data.telegramOutbox : [];
  const queued = outbox.filter((m) => m.status === 'queued');
  const failed = outbox.filter((m) => m.status === 'failed');
  const oldestQueued = queued
    .map((m) => Date.parse(m.createdAt))
    .filter((ts) => Number.isFinite(ts))
    .sort((a, b) => a - b)[0];

  return res.json({
    ok: true,
    totals: {
      queued: queued.length,
      failed: failed.length,
      all: outbox.length,
    },
    oldestQueuedAgeSec: oldestQueued ? Math.max(0, Math.floor((Date.now() - oldestQueued) / 1000)) : 0,
    failedSample: failed.slice(-5).map((m) => ({ id: m.id, attempts: m.attempts, error: m.lastError })),
    loop: {
      outboxRunning: Boolean(telegramOutboxTimer),
      updateRunning: Boolean(telegramUpdateTimer),
    },
    configPresent: Boolean((db.data.settings.telegramNotify?.botToken || TELEGRAM_BOT_TOKEN) && (db.data.settings.telegramNotify?.chatId || TELEGRAM_CHAT_ID)),
  });
});

app.post('/api/bias', async (req, res) => {
  const { symbol, bias } = req.body as { symbol: string; bias: Bias };
  if (!symbol || !['long', 'short', 'off'].includes(bias)) {
    return res.status(400).json({ error: 'invalid_payload' });
  }

  const db = await getDb();
  const cmd = submitBias(db.data, symbol.toUpperCase(), bias);
  await db.write();
  return res.json({ ok: true, command: cmd });
});

if (ENABLE_SIMULATION_API) {
  app.post('/api/simulate/tick', async (req, res) => {
    const { symbol = LIVE_SYMBOL, price } = req.body as { symbol?: string; price: number };
    if (price === undefined || Number.isNaN(price)) {
      return res.status(400).json({ error: 'price_required' });
    }

    const db = await getDb();
    const signal = runSimulationStep(db.data, symbol.toUpperCase(), Number(price));
    await db.write();
    return res.json({ ok: true, signal });
  });
}

if (ENABLE_REPLAY_API) {
  app.post('/api/replay/run', async (req, res) => {
    const {
      symbol = LIVE_SYMBOL,
      bias,
      timeframe,
      startTimeMs,
      endTimeMs,
      depositUsd
    } = req.body as {
      symbol?: string;
      bias?: Bias;
      timeframe?: CandleTimeframe;
      startTimeMs?: number;
      endTimeMs?: number;
      depositUsd?: number;
    };

    if (bias !== 'long' && bias !== 'short') {
      return res.status(400).json({ error: 'bias_required_long_or_short' });
    }

    const fromMs = Number(startTimeMs);
    const toMs = Number(endTimeMs);
    if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || toMs <= fromMs) {
      return res.status(400).json({ error: 'invalid_time_range' });
    }

    const tf = parseTimeframe(timeframe);

    try {
      const candles = await exchange.getCandles({
        symbol: symbol.toUpperCase(),
        timeframe: tf,
        startTimeMs: fromMs,
        endTimeMs: toMs
      });

      const summary = runDeterministicReplay({
        symbol: symbol.toUpperCase(),
        bias,
        timeframe: tf,
        candles,
        depositUsd
      });

      return res.json({ ok: true, summary });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'replay_failed';
      const status = message === 'not_enough_candles_for_replay' ? 400 : 500;
      return res.status(status).json({ error: message });
    }
  });
}

// ─── Risk Check Endpoint ──────────────────────────────────────────────
app.get('/api/live/risk-check', ownerAuth, async (_req, res) => {
  try {
    const risk = await evaluateRiskGates();
    return res.json({
      ...risk,
      ddLock: {
        active: ddLock.active,
        activatedAt: ddLock.activatedAt || undefined,
      },
    });
  } catch (error) {
    return res.status(500).json({
      canTrade: false,
      dailyDDPct: 0,
      portfolioLeverage: 0,
      blocks: ['risk_check_failed'],
      ddLock: {
        active: ddLock.active,
        activatedAt: ddLock.activatedAt || undefined,
      },
      error: error instanceof Error ? error.message : 'risk_check_failed'
    });
  }
});

app.post('/api/live/dd-lock/reset', ownerAuth, async (_req, res) => {
  ddLock.active = false;
  ddLock.activatedAt = '';
  logger.info({ component: 'risk-gate' }, 'DD lock manually reset by owner');
  return res.json({ ok: true, ddLockActive: false });
});

app.get('/api/live/status', async (_req, res) => {
  const pendingRows = await loadPendingConfirmationRows();
  const live = await buildLiveDashboardState(exchange, LIVE_SYMBOL, getLiveMode(), pendingRows);
  return res.json({
    ok: live.connected,
    ...live
  });
});

app.get('/api/live/pending-confirmations', ownerAuth, async (_req, res) => {
  const pending = await loadPendingConfirmations();
  return res.json({ ok: true, pending });
});

app.post('/api/live/pending-confirmations/:id/confirm', ownerAuth, async (req, res) => {
  const result = await executePendingConfirmation(req.params.id, 'dashboard');
  return res.status(result.ok ? 200 : 400).json(result);
});

app.post('/api/live/pending-confirmations/:id/reject', ownerAuth, async (req, res) => {
  const result = await rejectPendingConfirmation(req.params.id, 'dashboard');
  return res.status(result.ok ? 200 : 400).json(result);
});

app.post('/api/live/leverage', ownerAuth, async (req, res) => {
  const { symbol = LIVE_SYMBOL, leverage, confirm } = req.body as {
    symbol?: string;
    leverage?: number;
    confirm?: boolean;
  };

  const lev = Number(leverage);
  if (!Number.isFinite(lev) || lev <= 0 || lev > rulesCache.getEffectiveRules().maxLeverage) {
    return res.status(400).json({ error: 'invalid_leverage' });
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const result = await exchange.setLeverage(normalizeSymbol(symbol), lev);
  return res.status(result.ok ? 200 : 400).json({ ok: result.ok, result });
});

app.post('/api/live/position/levels', ownerAuth, riskGateMiddleware, symbolAllocationGate, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    size,
    stopLoss,
    takeProfit,
    takeProfits,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'long' | 'short';
    size?: number;
    stopLoss?: number;
    takeProfit?: number;
    takeProfits?: number[];
    confirm?: boolean;
  };

  if (side !== 'long' && side !== 'short') {
    return res.status(400).json({ ok: false, error: 'invalid_side' });
  }

  const normalizedSymbol = normalizeSymbol(symbol);
  const qtyRaw = Number(size);
  const slRaw = Number(stopLoss);

  const meta = await exchange.getInstrumentMeta(normalizedSymbol).catch(() => null);
  const sizeDecimals = Math.max(0, Math.min(8, Number(meta?.sizeDecimals ?? 5)));
  const qty = Number.isFinite(qtyRaw) ? Number(qtyRaw.toFixed(sizeDecimals)) : qtyRaw;

  // Hyperliquid price normalization:
  // - max 5 significant digits
  // - max (6 - szDecimals) decimal places
  const maxPriceDecimals = Math.max(0, 6 - sizeDecimals);
  const normalizeHlPrice = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) return value;
    const abs = Math.abs(value);
    const digitsBefore = abs >= 1 ? Math.floor(Math.log10(abs)) + 1 : 0;
    const decimalsBySig = Math.max(0, 5 - digitsBefore);
    const decimals = Math.max(0, Math.min(maxPriceDecimals, decimalsBySig));
    return Number(value.toFixed(decimals));
  };

  const sl = normalizeHlPrice(slRaw);

  const rawTps = Array.isArray(takeProfits) && takeProfits.length > 0
    ? takeProfits
    : (takeProfit !== undefined ? [takeProfit] : []);

  const normalizedTps = rawTps
    .map((x) => Number(x))
    .filter((x) => Number.isFinite(x) && x > 0)
    .slice(0, 3)
    .map((x) => normalizeHlPrice(x));

  if (!Number.isFinite(qty) || qty <= 0 || !Number.isFinite(sl) || sl <= 0 || normalizedTps.length === 0) {
    return res.status(400).json({ ok: false, error: 'invalid_size_or_levels' });
  }

  const sortedTps = side === 'long'
    ? [...normalizedTps].sort((a, b) => a - b)
    : [...normalizedTps].sort((a, b) => b - a);

  const levelOrderValid = side === 'long'
    ? sortedTps.every((tp) => tp > sl)
    : sortedTps.every((tp) => tp < sl);

  if (!levelOrderValid) {
    return res.status(400).json({ ok: false, error: 'invalid_level_order' });
  }

  // Validate levels against actual entry price to prevent dangerous SL/TP placement.
  let entryPrice: number | undefined;
  try {
    const expectedSide = side === 'long' ? 'long' : 'short';
    const openPositions = await exchange.getOpenPositions(normalizedSymbol);
    const pos = openPositions.find((p) => p.symbol === normalizedSymbol && p.side === expectedSide);
    if (pos?.entryPrice && Number.isFinite(pos.entryPrice) && pos.entryPrice > 0) {
      entryPrice = pos.entryPrice;
    }
  } catch {
    // best-effort validation
  }

  if (entryPrice) {
    const tpsValidVsEntry = side === 'long'
      ? sortedTps.every((tp) => tp > entryPrice)
      : sortedTps.every((tp) => tp < entryPrice);

    if (!tpsValidVsEntry) {
      return res.status(400).json({
        ok: false,
        error: 'invalid_take_profits_vs_entry',
        entryPrice,
        hint: side === 'long'
          ? 'LONG requires all TP levels above entry price'
          : 'SHORT requires all TP levels below entry price',
      });
    }
  }

  // Validate SL vs current market to prevent instant/invalid trigger side.
  const liveMid = await fetchLiveMid(normalizedSymbol);
  if (liveMid && Number.isFinite(liveMid) && liveMid > 0) {
    const validVsMarket = side === 'long' ? sl < liveMid : sl > liveMid;
    if (!validVsMarket) {
      return res.status(400).json({
        ok: false,
        error: 'invalid_stop_loss_vs_market',
        marketPrice: liveMid,
        hint: side === 'long'
          ? 'LONG requires SL below current market price'
          : 'SHORT requires SL above current market price',
      });
    }
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const closingSide: 'buy' | 'sell' = side === 'long' ? 'sell' : 'buy';
  const cancelAllResult = await exchange.cancelAll(normalizedSymbol);

  if (!cancelAllResult.ok) {
    return res.status(400).json({
      ok: false,
      symbol: normalizedSymbol,
      side,
      size: qty,
      stopLoss: sl,
      takeProfit: sortedTps[0],
      takeProfits: sortedTps,
      cancelAllResult: {
        ok: false,
        error: cancelAllResult.error
      },
      error: 'cancel_existing_orders_failed'
    });
  }

  const factor = 10 ** sizeDecimals;
  const tpCount = sortedTps.length;
  const baseSize = Math.floor((qty / tpCount) * factor) / factor;
  const tpSizes: number[] = Array.from({ length: tpCount }, (_, i) =>
    i < tpCount - 1 ? baseSize : Math.max(0, Math.round((qty - baseSize * (tpCount - 1)) * factor) / factor)
  );

  async function placeTriggerWithRetry(args: Parameters<typeof exchange.placeTriggerOrder>[0], retries = 2) {
    let last: Awaited<ReturnType<typeof exchange.placeTriggerOrder>> | null = null;
    let lastErr = '';
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const ack = await exchange.placeTriggerOrder(args);
        last = ack;
        if (ack.ok) return ack;
        lastErr = ack.error || 'trigger_order_failed';
      } catch (error) {
        lastErr = error instanceof Error ? error.message : 'trigger_order_exception';
      }
      if (attempt < retries) {
        await sleep(300 * (attempt + 1));
      }
    }
    return { ok: false, error: last?.error || lastErr } as Awaited<ReturnType<typeof exchange.placeTriggerOrder>>;
  }

  const slOrder = await placeTriggerWithRetry({
    symbol: normalizedSymbol,
    side: closingSide,
    size: qty,
    triggerPrice: sl,
    kind: 'sl',
    reduceOnly: true,
    clientOrderId: `sl-${nanoid()}`
  });

  const tpOrders: Array<{ ok: boolean; orderId?: string; error?: string }> = [];
  for (let i = 0; i < sortedTps.length; i++) {
    const ack = await placeTriggerWithRetry({
      symbol: normalizedSymbol,
      side: closingSide,
      size: tpSizes[i],
      triggerPrice: sortedTps[i],
      kind: 'tp',
      reduceOnly: true,
      clientOrderId: `tp${i + 1}-${nanoid(8)}`
    });
    tpOrders.push({ ok: ack.ok, orderId: ack.orderId, error: ack.error });
  }

  let ok = slOrder.ok && tpOrders.every((o) => o.ok);

  // Extra confirmation: verify SL+TP trigger orders are actually present on exchange.
  let verificationError: string | undefined;
  if (ok && (slOrder.orderId || tpOrders.some((o) => o.orderId))) {
    const expectedIds = [slOrder.orderId, ...tpOrders.map((o) => o.orderId)].filter((x): x is string => Boolean(x));
    let verified = false;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        // Query open orders to verify placement
        const allOrders = await exchange.getOpenOrders().catch(() => []);
        const openIds = new Set((allOrders || []).map((o) => String(o?.id ?? '')));
        verified = expectedIds.every((id) => openIds.has(String(id)));
        if (verified) {
          console.log(`[levels] trigger orders verified: ${expectedIds.join(',')}`);
          break;
        }
        if (attempt === 0) {
          console.log(`[levels] verification attempt ${attempt + 1}/5: expected ${expectedIds.length} orders, found ${openIds.size} total orders`);
        }
      } catch (e) {
        console.log(`[levels] verification query failed:`, e instanceof Error ? e.message : String(e));
      }
      await sleep(250 + attempt * 250);
    }
    if (!verified) {
      ok = false;
      verificationError = 'orders_not_visible_after_ack';
      console.log(`[levels] verification failed after 5 attempts, cancelling all orders`);
    }
  }

  // Prevent inconsistent partial state if one of levels failed.
  if (!ok) {
    console.warn('[levels] set failed', {
      symbol: normalizedSymbol,
      side,
      size: qty,
      sl,
      tps: sortedTps,
      slOrder,
      tpOrders,
      verificationError,
    });
    await exchange.cancelAll(normalizedSymbol).catch(() => undefined);
  }

  return res.status(ok ? 200 : 400).json({
    ok,
    symbol: normalizedSymbol,
    side,
    size: qty,
    stopLoss: sl,
    takeProfit: sortedTps[0],
    takeProfits: sortedTps,
    cancelAllResult: {
      ok: cancelAllResult.ok,
      error: String(cancelAllResult.error ?? '').trim() || undefined
    },
    stopLossOrder: {
      ok: slOrder.ok,
      orderId: slOrder.orderId,
      error: String(slOrder.error ?? '').trim() || undefined
    },
    takeProfitOrder: {
      ok: tpOrders[0]?.ok,
      orderId: tpOrders[0]?.orderId,
      error: String(tpOrders[0]?.error ?? '').trim() || undefined
    },
    takeProfitOrders: tpOrders.map((o) => ({
      ok: o.ok,
      orderId: o.orderId,
      error: String(o.error ?? '').trim() || undefined
    })),
    error: ok ? undefined : (verificationError ?? 'set_levels_failed')
  });
});

app.post('/api/live/order/limit', ownerAuth, staleMarketDataGate, riskGateMiddleware, symbolAllocationGate, engulfingGate, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    price,
    size,
    reduceOnly = false,
    clientOrderId,
    stopLoss: requestStopLoss,
    takeProfit: requestTakeProfit,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'buy' | 'sell';
    price?: number;
    size?: number;
    reduceOnly?: boolean;
    clientOrderId?: string;
    stopLoss?: number;
    takeProfit?: number;
    confirm?: boolean;
  };

  if (side !== 'buy' && side !== 'sell') {
    return res.status(400).json({ error: 'invalid_side' });
  }

  const px = Number(price);
  if (!Number.isFinite(px) || px <= 0) {
    return res.status(400).json({ error: 'invalid_price' });
  }

  // ── Allocation sizing: compute size when not provided ──────────────
  let qty = Number(size);
  let sizingSource: 'explicit' | 'runtime_allocation' = 'explicit';
  let sizingMeta: { marginUsd: number; notionalUsd: number; effectiveLeverage: number } | undefined;

  if (!Number.isFinite(qty) || qty <= 0) {
    const normalizedSym = normalizeSymbol(symbol);
    const effectiveRules = rulesCache.getEffectiveRules();
    const riskCheck: RiskCheckResult | undefined = (req as any)._riskCheck;

    let equityUsd = riskCheck?.equityUsd ?? 0;
    let availableUsd = 0;
    try {
      const account = await exchange.getAccountState();
      if (account) {
        if (!equityUsd) equityUsd = account.equityUsd ?? 0;
        availableUsd = account.availableUsd ?? 0;
      }
    } catch {
      // best-effort
    }

    let sizeDecimals = 6;
    try {
      const meta = await exchange.getInstrumentMeta(normalizedSym);
      if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
    } catch {
      // best-effort: use default
    }

    const sizing = computeAllocationSize({
      symbol: normalizedSym,
      price: px,
      equityUsd,
      availableUsd,
      rules: effectiveRules,
      sizeDecimals,
    });

    if (!sizing.ok) {
      logRiskGateAudit({ gate: 'allocation_sizing', passed: false, reason: sizing.reason, details: { symbol: normalizedSym, price: px, equityUsd, availableUsd } });
      return res.status(400).json({
        ok: false,
        errorCode: 'allocation_sizing_failed' as TradingErrorCode,
        error: `Allocation sizing failed: ${sizing.reason}`,
      });
    }

    qty = sizing.size;
    sizingSource = 'runtime_allocation';
    sizingMeta = { marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage };

    logRiskGateAudit({
      gate: 'allocation_sizing',
      passed: true,
      details: { symbol: normalizedSym, size: qty, marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage, allocationPct: sizing.allocationPct },
    });
  }

  const notional = px * qty;

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const normalizedSymbol = normalizeSymbol(symbol);
  const correlationId = clientOrderId || nanoid();
  const now = new Date().toISOString();

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: now,
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: 'manual_live_order',
    payload: {
      reduceOnly: Boolean(reduceOnly),
      notionalUsdc: Number(notional.toFixed(4)),
      manualConfirmation: rulesCache.getEffectiveRules().manualConfirmation
    }
  });

  const intent: OrderIntent = {
    symbol: normalizedSymbol,
    side,
    price: px,
    size: qty,
    reduceOnly: Boolean(reduceOnly),
    clientOrderId: correlationId
  };

  const ack = await exchange.placeLimitOrder(intent);

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: ack.ok ? 'manual_live_order_ack' : 'manual_live_order_rejected',
    payload: {
      orderId: ack.orderId ?? null,
      status: ack.status ?? null,
      error: ack.error ?? null
    }
  });

  // TP/SL defaults: auto-apply after successful non-reduceOnly order
  let tpSlResult: Awaited<ReturnType<typeof placeTpSlTriggerOrders>> | undefined;
  let tpSlApplied: TpSlDefaults | null = null;

  if (ack.ok && !reduceOnly) {
    await clearPendingConfirmationForSymbol(normalizedSymbol);
    try {
      await notifyTradeOpen({ symbol: normalizedSymbol, side, price: px, size: qty, source: 'api:order_limit' });
    } catch (error) {
      logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
    }
    tpSlApplied = resolveTpSlDefaults(px, side, requestStopLoss, requestTakeProfit);
    if (tpSlApplied) {
      try {
        tpSlResult = await placeTpSlTriggerOrders(normalizedSymbol, side, qty, tpSlApplied, correlationId, px);
      } catch {
        tpSlResult = {
          stopLossOrder: { ok: false, error: 'tp_sl_placement_failed' },
          takeProfitOrder: { ok: false, error: 'tp_sl_placement_failed' }, takeProfitOrders: [{ ok: false, error: 'tp_sl_placement_failed' }]
        };
      }

      logRiskGateAudit({
        gate: 'tp_sl_defaults',
        passed: true,
        reason: tpSlApplied.applied ? 'runtime_defaults_applied' : 'explicit_values_used',
        details: {
          source: tpSlApplied.source,
          stopLoss: tpSlApplied.stopLoss,
          takeProfit: tpSlApplied.takeProfit,
          entryPrice: px,
          side,
          slOrderOk: tpSlResult?.stopLossOrder.ok ?? false,
          tpOrderOk: tpSlResult?.takeProfitOrder.ok ?? false
        }
      });
    }
  }

  await db.write();

  const responseBody: Record<string, unknown> = {
    ok: ack.ok,
    notionalUsdc: Number(notional.toFixed(4)),
    sizingSource,
    ack
  };

  if (sizingMeta) {
    responseBody.marginUsd = sizingMeta.marginUsd;
    responseBody.notionalUsd = sizingMeta.notionalUsd;
    responseBody.effectiveLeverage = sizingMeta.effectiveLeverage;
  }

  if (tpSlApplied && tpSlResult) {
    responseBody.stopLoss = tpSlApplied.stopLoss;
    responseBody.takeProfit = tpSlApplied.takeProfit;
    responseBody.tpSlSource = tpSlApplied.source;
    responseBody.stopLossOrder = tpSlResult.stopLossOrder;
    responseBody.takeProfitOrder = tpSlResult.takeProfitOrder;
  }

  return res.status(ack.ok ? 200 : 400).json(responseBody);
});

app.post('/api/live/order/cancel', ownerAuth, async (req, res) => {
  const { orderId, symbol = LIVE_SYMBOL, confirm } = req.body as {
    orderId?: string;
    symbol?: string;
    confirm?: boolean;
  };

  if (!orderId) {
    return res.status(400).json({ error: 'order_id_required' });
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const result = await exchange.cancelOrder(orderId);

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: normalizeSymbol(symbol),
    source: 'live',
    type: result.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId: nanoid(),
    reason: result.ok ? 'manual_cancel_order' : 'manual_cancel_order_failed',
    payload: {
      orderId,
      error: result.error ?? null
    }
  });
  await db.write();

  return res.status(result.ok ? 200 : 400).json({ ok: result.ok, result });
});

app.post('/api/live/order/cancel-all', ownerAuth, async (req, res) => {
  const { symbol = LIVE_SYMBOL, confirm } = req.body as {
    symbol?: string;
    confirm?: boolean;
  };

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const result = await exchange.cancelAll(normalizeSymbol(symbol));

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: normalizeSymbol(symbol),
    source: 'live',
    type: result.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId: nanoid(),
    reason: result.ok ? 'manual_cancel_all' : 'manual_cancel_all_failed',
    payload: {
      error: result.error ?? null
    }
  });
  await db.write();

  return res.status(result.ok ? 200 : 400).json({ ok: result.ok, result });
});

// ─── TP/SL Defaults Helper ────────────────────────────────────────────

interface TpSlDefaults {
  stopLoss: number;
  /** All computed TP trigger prices (1–3), sorted ascending for longs / descending for shorts */
  takeProfits: number[];
  /** First TP price (back-compat) */
  takeProfit: number;
  applied: boolean;
  source: 'explicit' | 'runtime_defaults';
}

// ─── Active Trade TP Tracking ─────────────────────────────────────────
interface ActiveTradeState {
  symbol: string;
  side: 'buy' | 'sell';
  entryPrice: number;
  slOrderId: string | null;
  tpOrderIds: string[];        // pending TP order IDs (removed as they fill)
  firstTpFired: boolean;
  positionSize: number;
}
/** correlationId → ActiveTradeState */
const activeTrades = new Map<string, ActiveTradeState>();

/**
 * Compute TP/SL levels from runtime rules when the client omits them.
 * Priority: explicit request > runtime defaults.
 * Returns up to 3 TP prices and a SL price.
 */
function resolveTpSlDefaults(
  entryPrice: number,
  side: 'buy' | 'sell',
  requestSl: number | undefined,
  requestTp: number | undefined
): TpSlDefaults | null {
  const hasSl = requestSl !== undefined && Number.isFinite(Number(requestSl)) && Number(requestSl) > 0;
  const hasTp = requestTp !== undefined && Number.isFinite(Number(requestTp)) && Number(requestTp) > 0;

  if (hasSl && hasTp) {
    const tp = Number(requestTp);
    return { stopLoss: Number(requestSl), takeProfits: [tp], takeProfit: tp, applied: false, source: 'explicit' };
  }

  const rules = rulesCache.getEffectiveRules();
  if (!rules.raw) return null;

  const tpLevels = rules.raw.tpLevels?.length ? rules.raw.tpLevels : (rules.raw.tpPct ? [rules.raw.tpPct] : null);
  const slPct = rules.raw.slPct;
  if (!tpLevels || !slPct) return null;

  const isLong = side === 'buy';
  const takeProfits = tpLevels.map(pct => {
    const price = isLong ? entryPrice * (1 + pct / 100) : entryPrice * (1 - pct / 100);
    return Number(price.toFixed(8));
  });
  const defaultSl = isLong ? entryPrice * (1 - slPct / 100) : entryPrice * (1 + slPct / 100);

  return {
    stopLoss: hasSl ? Number(requestSl) : Number(defaultSl.toFixed(8)),
    takeProfits,
    takeProfit: takeProfits[0],
    applied: true,
    source: 'runtime_defaults',
  };
}

/**
 * Place SL + up to 3 TP trigger orders after a successful entry.
 * Registers trade state for the TP fill monitor (SL→entry on first TP hit).
 */
async function placeTpSlTriggerOrders(
  symbol: string,
  side: 'buy' | 'sell',
  size: number,
  tpSl: TpSlDefaults,
  correlationId: string,
  entryPrice?: number,
): Promise<{
  stopLossOrder: { ok: boolean; orderId?: string; error?: string };
  takeProfitOrder: { ok: boolean; orderId?: string; error?: string };
  takeProfitOrders: { ok: boolean; orderId?: string; error?: string }[];
}> {
  const closingSide: 'buy' | 'sell' = side === 'buy' ? 'sell' : 'buy';
  const tpCount = tpSl.takeProfits.length;

  // Split position equally across TP levels (floor to avoid over-sizing)
  const factor = 1e6;
  const baseSize = Math.floor((size / tpCount) * factor) / factor;
  const tpSizes: number[] = Array.from({ length: tpCount }, (_, i) =>
    i < tpCount - 1 ? baseSize : Math.max(0, Math.round((size - baseSize * (tpCount - 1)) * factor) / factor)
  );

  // Place SL (full position)
  const slOrder = await exchange.placeTriggerOrder({
    symbol, side: closingSide, size, triggerPrice: tpSl.stopLoss,
    kind: 'sl', reduceOnly: true, clientOrderId: `sl-auto-${correlationId}`,
  });

  // Place TP orders sequentially (avoid parallel trigger order conflicts)
  const tpOrders: { ok: boolean; orderId?: string; error?: string }[] = [];
  for (let i = 0; i < tpSl.takeProfits.length; i++) {
    try {
      const ack = await exchange.placeTriggerOrder({
        symbol, side: closingSide, size: tpSizes[i], triggerPrice: tpSl.takeProfits[i],
        kind: 'tp', reduceOnly: true, clientOrderId: `tp${i + 1}-auto-${correlationId}`,
      });
      tpOrders.push({ ok: ack.ok, orderId: ack.orderId, error: ack.error });
    } catch (err) {
      tpOrders.push({ ok: false, error: err instanceof Error ? err.message : 'tp_placement_failed' });
    }
  }

  // Register in active trade tracking (for TP fill monitor)
  const tpOrderIds = tpOrders.map(o => o.orderId).filter((id): id is string => Boolean(id));
  if (tpOrderIds.length > 0 && tpCount > 1) {
    activeTrades.set(correlationId, {
      symbol, side, entryPrice: entryPrice ?? tpSl.stopLoss,
      slOrderId: slOrder.orderId ?? null,
      tpOrderIds, firstTpFired: false, positionSize: size,
    });
  }

  return {
    stopLossOrder: { ok: slOrder.ok, orderId: slOrder.orderId, error: slOrder.error },
    takeProfitOrder: tpOrders[0] ?? { ok: false, error: 'no_tp' },
    takeProfitOrders: tpOrders,
  };
}

// ─── TP Fill Monitor (SL → entry price after first TP) ────────────────
let tpFillMonitorTimer: NodeJS.Timeout | null = null;
let tpFillMonitorBusy = false;

async function runTpFillMonitorTick(): Promise<void> {
  if (tpFillMonitorBusy || activeTrades.size === 0) return;
  tpFillMonitorBusy = true;
  try {
    const openOrders = await exchange.getOpenOrders();
    const openOrderIds = new Set(openOrders.map(o => o.id));

    for (const [correlationId, trade] of activeTrades) {
      const stillPending = trade.tpOrderIds.filter(id => openOrderIds.has(id));
      const justFilled = trade.tpOrderIds.filter(id => !openOrderIds.has(id));

      // If SL order disappeared before any TP fill, DO NOT assume immediate SL fill.
      // Confirm with live position state first to avoid false alerts from order id churn.
      if (!trade.firstTpFired && trade.slOrderId && !openOrderIds.has(trade.slOrderId)) {
        let remainingSize = 0;
        try {
          const positions = await exchange.getOpenPositions(trade.symbol);
          const pos = positions.find((p) => p.symbol.toUpperCase() === trade.symbol.toUpperCase());
          remainingSize = pos?.size ?? 0;
        } catch {
          remainingSize = 0;
        }

        if (remainingSize <= 0) {
          try {
            await notifySlEvent({ symbol: trade.symbol, reason: 'stop_loss_trigger_filled' });
          } catch (error) {
            logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'SL telegram notify failed');
          }
          activeTrades.delete(correlationId);
          continue;
        }

        const closingSide: 'buy' | 'sell' = trade.side === 'buy' ? 'sell' : 'buy';
        const slCandidate = openOrders.find((o) => {
          if (o.symbol.toUpperCase() !== trade.symbol.toUpperCase()) return false;
          if (o.side !== closingSide) return false;
          const raw = o.raw as Record<string, unknown> | undefined;
          const tpsl = String(
            (raw as { tpsl?: unknown } | undefined)?.tpsl
            ?? (raw as { trigger?: { tpsl?: unknown } } | undefined)?.trigger?.tpsl
            ?? (raw as { orderType?: { trigger?: { tpsl?: unknown } } } | undefined)?.orderType?.trigger?.tpsl
            ?? ''
          ).toLowerCase();
          return tpsl === 'sl';
        });

        const oldSlOrderId = trade.slOrderId;
        trade.slOrderId = slCandidate?.id ?? null;
        logger.warn(
          { component: 'tp-monitor', symbol: trade.symbol, correlationId, oldSlOrderId, reboundSlOrderId: slCandidate?.id ?? null, remainingSize },
          'SL order disappeared but position remains open; skip SL alert and continue tracking',
        );
      }

      if (justFilled.length === 0) continue;

      trade.tpOrderIds = stillPending;

      if (!trade.firstTpFired && justFilled.length > 0) {
        trade.firstTpFired = true;
        logger.info({ component: 'tp-monitor', symbol: trade.symbol, correlationId, filledTp: justFilled }, 'first TP filled → moving SL to entry (break-even)');

        // Cancel current SL
        if (trade.slOrderId) {
          try { await exchange.cancelOrder(trade.slOrderId); } catch { /* best-effort */ }
        }

        // Determine remaining position size
        let remainingSize = 0;
        try {
          const positions = await exchange.getOpenPositions();
          const pos = positions.find(p => p.symbol.toUpperCase() === trade.symbol.toUpperCase());
          remainingSize = pos?.size ?? 0;
        } catch { remainingSize = 0; }

        if (remainingSize > 0 && trade.entryPrice > 0) {
          const closingSide: 'buy' | 'sell' = trade.side === 'buy' ? 'sell' : 'buy';
          try {
            const beSlAck = await exchange.placeTriggerOrder({
              symbol: trade.symbol, side: closingSide, size: remainingSize,
              triggerPrice: trade.entryPrice, kind: 'sl', reduceOnly: true,
              clientOrderId: `be-sl-${correlationId}`,
            });
            trade.slOrderId = beSlAck.orderId ?? null;
            logRiskGateAudit({
              gate: 'tp_fill_monitor', passed: beSlAck.ok,
              reason: beSlAck.ok ? 'break_even_sl_placed' : 'break_even_sl_failed',
              details: { symbol: trade.symbol, entryPrice: trade.entryPrice, remainingSize, orderId: beSlAck.orderId },
            });
            if (beSlAck.ok) {
              try {
                await notifyTpHit({ symbol: trade.symbol, entryPrice: trade.entryPrice, remainingSize, tpIds: justFilled });
              } catch (error) {
                logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'TP telegram notify failed');
              }
            }
          } catch (err) {
            logger.error({ component: 'tp-monitor', err }, 'failed to place break-even SL');
          }
        }
      }

      if (stillPending.length === 0) {
        activeTrades.delete(correlationId);
      }
    }
  } catch (err) {
    logger.warn({ component: 'tp-monitor', err }, 'TP fill monitor tick failed');
  } finally {
    tpFillMonitorBusy = false;
  }
}

function startTpFillMonitor(): void {
  if (tpFillMonitorTimer) return;
  tpFillMonitorTimer = setInterval(() => {
    runTpFillMonitorTick().catch(err => logger.warn({ component: 'tp-monitor', err }, 'tick error'));
  }, 30_000);
  tpFillMonitorTimer.unref?.();
  logger.info({ component: 'tp-monitor' }, 'TP fill monitor started');
}

// ─── RESTful Trading Command Layer (ISSUE #12) ───────────────────────

/** Classify exchange errors into standard codes */
function classifyError(error: string | undefined): TradingErrorCode {
  if (!error) return 'exchange_error';
  const lower = error.toLowerCase();
  if (lower.includes('rate limit') || lower.includes('429') || lower.includes('too many')) return 'rate_limited';
  if (lower.includes('insufficient') || lower.includes('not enough') || lower.includes('balance')) return 'insufficient_balance';
  if (lower.includes('invalid') || lower.includes('bad') || lower.includes('param')) return 'invalid_params';
  if (lower.includes('not found') || lower.includes('not_found') || lower.includes('no order')) return 'order_not_found';
  if (lower.includes('already') && (lower.includes('cancel') || lower.includes('filled'))) return 'already_canceled';
  return 'exchange_error';
}

/** Idempotency store: clientOrderId → response (in-memory, survives within process) */
const idempotencyCache = new Map<string, { timestamp: number; response: any }>();
const IDEMPOTENCY_TTL_MS = 30 * 60 * 1000; // 30 minutes
const IDEMPOTENCY_MAX_SIZE = 1000;

function pruneIdempotencyCache() {
  const cutoff = Date.now() - IDEMPOTENCY_TTL_MS;
  for (const [key, entry] of idempotencyCache) {
    if (entry.timestamp < cutoff) idempotencyCache.delete(key);
  }
  // FIFO eviction if still over max size
  while (idempotencyCache.size > IDEMPOTENCY_MAX_SIZE) {
    const oldest = idempotencyCache.keys().next().value;
    if (oldest !== undefined) idempotencyCache.delete(oldest);
    else break;
  }
}

// POST /api/live/order — idempotent place order
app.post('/api/live/order', ownerAuth, staleMarketDataGate, riskGateMiddleware, symbolAllocationGate, engulfingGate, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    price,
    size,
    leverage,
    clientOrderId,
    reduceOnly = false,
    stopLoss: requestStopLoss,
    takeProfit: requestTakeProfit,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'buy' | 'sell';
    price?: number;
    size?: number;
    leverage?: number;
    clientOrderId?: string;
    reduceOnly?: boolean;
    stopLoss?: number;
    takeProfit?: number;
    confirm?: boolean;
  };

  // Validation
  if (side !== 'buy' && side !== 'sell') {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'side must be buy or sell' });
  }
  const px = Number(price);
  if (!Number.isFinite(px) || px <= 0) {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'invalid price' });
  }

  // ── Allocation sizing: compute size when not provided ──────────────
  let qty = Number(size);
  let sizingSource: 'explicit' | 'runtime_allocation' = 'explicit';
  let sizingMeta: { marginUsd: number; notionalUsd: number; effectiveLeverage: number } | undefined;

  if (!Number.isFinite(qty) || qty <= 0) {
    // Auto-size from runtime allocation rules
    const normalizedSym = normalizeSymbol(symbol);
    const effectiveRules = rulesCache.getEffectiveRules();
    const riskCheck: RiskCheckResult | undefined = (req as any)._riskCheck;

    let equityUsd = riskCheck?.equityUsd ?? 0;
    let availableUsd = 0;
    try {
      const account = await exchange.getAccountState();
      if (account) {
        if (!equityUsd) equityUsd = account.equityUsd ?? 0;
        availableUsd = account.availableUsd ?? 0;
      }
    } catch {
      // best-effort
    }

    let sizeDecimals = 6;
    try {
      const meta = await exchange.getInstrumentMeta(normalizedSym);
      if (meta?.sizeDecimals !== undefined) sizeDecimals = meta.sizeDecimals;
    } catch {
      // best-effort: use default
    }

    const sizing = computeAllocationSize({
      symbol: normalizedSym,
      price: px,
      equityUsd,
      availableUsd,
      rules: effectiveRules,
      sizeDecimals,
    });

    if (!sizing.ok) {
      logRiskGateAudit({ gate: 'allocation_sizing', passed: false, reason: sizing.reason, details: { symbol: normalizedSym, price: px, equityUsd, availableUsd } });
      return res.status(400).json({
        ok: false,
        errorCode: 'allocation_sizing_failed' as TradingErrorCode,
        error: `Allocation sizing failed: ${sizing.reason}`,
      });
    }

    qty = sizing.size;
    sizingSource = 'runtime_allocation';
    sizingMeta = { marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage };

    logRiskGateAudit({
      gate: 'allocation_sizing',
      passed: true,
      details: { symbol: normalizedSym, size: qty, marginUsd: sizing.marginUsd, notionalUsd: sizing.notionalUsd, effectiveLeverage: sizing.effectiveLeverage, allocationPct: sizing.allocationPct },
    });
  }

  const notional = px * qty;

  // Manual confirmation gate
  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({ ok: false, errorCode: 'manual_confirmation_required' as TradingErrorCode, hint: 'resend with {"confirm": true}' });
  }

  const correlationId = clientOrderId || nanoid();

  // Idempotency check
  pruneIdempotencyCache();
  if (clientOrderId && idempotencyCache.has(clientOrderId)) {
    const cached = idempotencyCache.get(clientOrderId)!;
    return res.status(200).json({ ...cached.response, idempotent: true });
  }

  const normalizedSymbol = normalizeSymbol(symbol);

  // Set leverage if provided — enforce runtime maxLeverage cap
  if (leverage !== undefined) {
    const lev = Number(leverage);
    if (!Number.isFinite(lev) || lev <= 0 || lev > rulesCache.getEffectiveRules().maxLeverage) {
      logRiskGateAudit({ gate: 'leverage_cap', passed: false, reason: 'leverage_limit_exceeded', details: { requested: lev, max: rulesCache.getEffectiveRules().maxLeverage } });
      return res.status(400).json({ ok: false, errorCode: 'leverage_limit_exceeded' as TradingErrorCode, error: `Leverage ${lev}x exceeds max ${rulesCache.getEffectiveRules().maxLeverage}x` });
    }
    await exchange.setLeverage(normalizedSymbol, lev);
  }

  const db = await getDb();
  const now = new Date().toISOString();

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: now,
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: 'live_place_order',
    payload: { reduceOnly: Boolean(reduceOnly), notionalUsdc: Number(notional.toFixed(4)), clientOrderId: correlationId }
  });

  const intent: OrderIntent = { symbol: normalizedSymbol, side, price: px, size: qty, reduceOnly: Boolean(reduceOnly), clientOrderId: correlationId };
  const ack = await exchange.placeLimitOrder(intent);

  const errorCode = ack.ok ? undefined : classifyError(ack.error);

  appendTradeEvent(db.data, {
    symbol: normalizedSymbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(side),
    price: px,
    quantity: qty,
    reason: ack.ok ? 'live_order_ack' : 'live_order_rejected',
    payload: { orderId: ack.orderId ?? null, status: ack.status ?? null, error: ack.error ?? null, errorCode: errorCode ?? null }
  });

  // TP/SL defaults: auto-apply after successful non-reduceOnly order
  let tpSlResult: Awaited<ReturnType<typeof placeTpSlTriggerOrders>> | undefined;
  let tpSlApplied: TpSlDefaults | null = null;

  if (ack.ok && !reduceOnly) {
    await clearPendingConfirmationForSymbol(normalizedSymbol);
    try {
      await notifyTradeOpen({ symbol: normalizedSymbol, side, price: px, size: qty, source: 'api:order' });
    } catch (error) {
      logger.warn({ component: 'telegram', err: error instanceof Error ? error.message : error }, 'trade-open telegram notify failed');
    }
    tpSlApplied = resolveTpSlDefaults(px, side, requestStopLoss, requestTakeProfit);
    if (tpSlApplied) {
      try {
        tpSlResult = await placeTpSlTriggerOrders(normalizedSymbol, side, qty, tpSlApplied, correlationId, px);
      } catch (err) {
        tpSlResult = {
          stopLossOrder: { ok: false, error: 'tp_sl_placement_failed' },
          takeProfitOrder: { ok: false, error: 'tp_sl_placement_failed' }, takeProfitOrders: [{ ok: false, error: 'tp_sl_placement_failed' }]
        };
      }

      logRiskGateAudit({
        gate: 'tp_sl_defaults',
        passed: true,
        reason: tpSlApplied.applied ? 'runtime_defaults_applied' : 'explicit_values_used',
        details: {
          source: tpSlApplied.source,
          stopLoss: tpSlApplied.stopLoss,
          takeProfit: tpSlApplied.takeProfit,
          entryPrice: px,
          side,
          slOrderOk: tpSlResult?.stopLossOrder.ok ?? false,
          tpOrderOk: tpSlResult?.takeProfitOrder.ok ?? false
        }
      });
    }
  }

  await db.write();

  const response: Record<string, unknown> = { ok: ack.ok, orderId: ack.orderId, clientOrderId: correlationId, status: ack.status, errorCode, error: ack.error, sizingSource };

  if (sizingMeta) {
    response.marginUsd = sizingMeta.marginUsd;
    response.notionalUsd = sizingMeta.notionalUsd;
    response.effectiveLeverage = sizingMeta.effectiveLeverage;
  }

  if (tpSlApplied && tpSlResult) {
    response.stopLoss = tpSlApplied.stopLoss;
    response.takeProfit = tpSlApplied.takeProfit;
    response.tpSlSource = tpSlApplied.source;
    response.stopLossOrder = tpSlResult.stopLossOrder;
    response.takeProfitOrder = tpSlResult.takeProfitOrder;
  }

  // Cache for idempotency
  if (clientOrderId) {
    idempotencyCache.set(clientOrderId, { timestamp: Date.now(), response });
  }

  return res.status(ack.ok ? 200 : 400).json(response);
});

// DELETE /api/live/order/:id — safe re-cancel
app.delete('/api/live/order/:id', ownerAuth, async (req, res) => {
  const orderId = req.params.id;
  const { confirm } = req.query as { confirm?: string };
  const confirmed = confirm === 'true' || confirm === '1';

  if (rulesCache.getEffectiveRules().manualConfirmation && !confirmed) {
    return res.status(409).json({ ok: false, errorCode: 'manual_confirmation_required' as TradingErrorCode, hint: 'add ?confirm=true' });
  }

  const result = await exchange.cancelOrder(orderId);

  // Safe re-cancel: if order not found, treat as success (already canceled/filled)
  const safeOk = result.ok || classifyError(result.error) === 'order_not_found' || classifyError(result.error) === 'already_canceled';

  const db = await getDb();
  appendTradeEvent(db.data, {
    symbol: LIVE_SYMBOL,
    source: 'live',
    type: safeOk ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId: nanoid(),
    reason: safeOk ? 'live_cancel_order' : 'live_cancel_failed',
    payload: { orderId, originalOk: result.ok, safeOk, error: result.error ?? null, errorCode: safeOk ? null : classifyError(result.error) }
  });
  await db.write();

  return res.status(safeOk ? 200 : 400).json({
    ok: safeOk,
    orderId,
    alreadyCanceled: !result.ok && safeOk,
    errorCode: safeOk ? undefined : classifyError(result.error),
    error: safeOk ? undefined : result.error
  });
});

// PUT /api/live/order/:id/reduce — reduce-only modify with audit
app.put('/api/live/order/:id/reduce', ownerAuth, async (req, res) => {
  const orderId = req.params.id;
  const { newSize, confirm } = req.body as { newSize?: number; confirm?: boolean };

  const qty = Number(newSize);
  if (!Number.isFinite(qty) || qty <= 0) {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'newSize must be a positive number' });
  }

  if (rulesCache.getEffectiveRules().manualConfirmation && !isConfirmed(confirm)) {
    return res.status(409).json({ ok: false, errorCode: 'manual_confirmation_required' as TradingErrorCode, hint: 'resend with {"confirm": true}' });
  }

  const db = await getDb();
  const correlationId = nanoid();
  const user = process.env.HYPERLIQUID_ACCOUNT_ADDRESS?.trim();

  // Find the existing order
  let existingOrder: any = null;
  try {
    const openOrders = await exchange.getOpenOrders();
    existingOrder = openOrders.find((o) => o.id === orderId);
  } catch {
    // continue
  }

  if (!existingOrder) {
    appendTradeEvent(db.data, {
      symbol: LIVE_SYMBOL,
      source: 'live',
      type: 'order_rejected',
      timestamp: new Date().toISOString(),
      correlationId,
      reason: 'live_reduce_order_not_found',
      payload: { orderId, newSize: qty }
    });
    await db.write();
    return res.status(404).json({ ok: false, errorCode: 'order_not_found' as TradingErrorCode, error: 'order not found in open orders' });
  }

  if (qty >= existingOrder.size) {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: `newSize (${qty}) must be less than current size (${existingOrder.size})` });
  }

  // Log the reduce intent
  appendTradeEvent(db.data, {
    symbol: existingOrder.symbol,
    source: 'live',
    type: 'order_submitted',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(existingOrder.side),
    price: existingOrder.price,
    quantity: qty,
    reason: 'live_reduce_order',
    payload: { orderId, originalSize: existingOrder.size, newSize: qty, action: 'reduce' }
  });

  // Cancel existing order
  const cancelResult = await exchange.cancelOrder(orderId);
  if (!cancelResult.ok) {
    const errorCode = classifyError(cancelResult.error);
    appendTradeEvent(db.data, {
      symbol: existingOrder.symbol,
      source: 'live',
      type: 'order_rejected',
      timestamp: new Date().toISOString(),
      correlationId,
      reason: 'live_reduce_cancel_failed',
      payload: { orderId, error: cancelResult.error ?? null, errorCode }
    });
    await db.write();
    return res.status(400).json({ ok: false, errorCode, error: cancelResult.error });
  }

  // Place new order with reduced size (reduce-only)
  const newClientOrderId = `reduce-${correlationId}`;
  const intent: OrderIntent = {
    symbol: existingOrder.symbol,
    side: existingOrder.side,
    price: existingOrder.price,
    size: qty,
    reduceOnly: true,
    clientOrderId: newClientOrderId
  };

  const ack = await exchange.placeLimitOrder(intent);
  const errorCode = ack.ok ? undefined : classifyError(ack.error);

  appendTradeEvent(db.data, {
    symbol: existingOrder.symbol,
    source: 'live',
    type: ack.ok ? 'order_acknowledged' : 'order_rejected',
    timestamp: new Date().toISOString(),
    correlationId,
    side: toTradeSide(existingOrder.side),
    price: existingOrder.price,
    quantity: qty,
    reason: ack.ok ? 'live_reduce_order_ack' : 'live_reduce_order_failed',
    payload: {
      originalOrderId: orderId,
      newOrderId: ack.orderId ?? null,
      originalSize: existingOrder.size,
      newSize: qty,
      error: ack.error ?? null,
      errorCode: errorCode ?? null
    }
  });
  await db.write();

  return res.status(ack.ok ? 200 : 400).json({
    ok: ack.ok,
    originalOrderId: orderId,
    newOrderId: ack.orderId,
    originalSize: existingOrder.size,
    newSize: qty,
    errorCode,
    error: ack.error
  });
});

app.use(express.static(distDir));
app.get('*', (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

// ─── Process-level error handlers ─────────────────────────────────────
process.on('unhandledRejection', (reason) => {
  logger.error({ component: 'process', err: reason }, 'unhandled rejection');
});

process.on('uncaughtException', (error) => {
  logger.fatal({ component: 'process', err: error }, 'uncaught exception');
  // Let the process crash after logging — do not swallow fatal errors
  process.exit(1);
});

// ─── Graceful shutdown ────────────────────────────────────────────────
let shuttingDown = false;

const server = app.listen(port, host, () => {
  logger.info({ component: 'server', host, port }, `server listening on http://${host}:${port}`);
  rulesCache.start();
  ingestRestFallback().catch((err) => logger.warn({ component: 'live', err }, 'initial REST fallback ingest failed'));
  startLiveMidStream();
  startDrawdownWatchdog();
  startEngulfingMonitor();
  startFvgMonitor();
  startTpFillMonitor();
  startTelegramOutboxLoop();
  startTelegramUpdateLoop();
  getTelegramConfig()
    .then((cfg) => {
      if (!cfg) {
        logger.warn({ component: 'pending-confirmation' }, 'Telegram alerts disabled (configure bot token + chat id in Settings)');
      } else {
        logger.info({ component: 'telegram', chatId: cfg.chatId }, 'Telegram notifications enabled');
      }
    })
    .catch(() => undefined);
});

async function gracefulShutdown(signal: string) {
  if (shuttingDown) return;
  shuttingDown = true;
  logger.info({ component: 'shutdown', signal }, 'received signal, shutting down gracefully');

  // 1. Stop accepting new connections
  server.close(() => {
    logger.info({ component: 'shutdown' }, 'HTTP server closed');
  });

  // 2. Clear timers
  rulesCache.stop();
  clearInterval(auditFlushTimer);
  clearInterval(rateLimitPruneTimer);
  if (drawdownWatchdogTimer) { clearInterval(drawdownWatchdogTimer); drawdownWatchdogTimer = null; }
  if (engulfingMonitorTimer) { clearInterval(engulfingMonitorTimer); engulfingMonitorTimer = null; }
  if (fvgMonitorTimer) { clearInterval(fvgMonitorTimer); fvgMonitorTimer = null; }
  if (tpFillMonitorTimer) { clearInterval(tpFillMonitorTimer); tpFillMonitorTimer = null; }
  if (telegramOutboxTimer) { clearInterval(telegramOutboxTimer); telegramOutboxTimer = null; }
  if (telegramUpdateTimer) { clearInterval(telegramUpdateTimer); telegramUpdateTimer = null; }
  if (restFallbackTimer) { clearInterval(restFallbackTimer); restFallbackTimer = null; }
  if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }

  // 3. Close WS stream
  if (midStreamHandle) { midStreamHandle.close(); midStreamHandle = null; }

  // 4. Best-effort: flush risk audit + close persistence
  try { await flushRiskAudit(); } catch { /* best effort */ }
  try {
    const { getStore } = await import('../core/persistence/index.js');
    const store = await getStore();
    await store.close();
    logger.info({ component: 'shutdown' }, 'persistence store closed');
  } catch { /* store may not have been initialised */ }

  logger.info({ component: 'shutdown' }, 'cleanup complete, exiting');
  process.exit(0);
}

process.on('SIGTERM', () => { gracefulShutdown('SIGTERM'); });
process.on('SIGINT', () => { gracefulShutdown('SIGINT'); });
