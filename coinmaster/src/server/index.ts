import express from 'express';
import cors from 'cors';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { nanoid } from 'nanoid';
import { getDb } from '../core/db.js';
import { runDeterministicReplay } from '../core/replay.js';
import { getStats, submitBias } from '../core/services.js';
import { runSimulationStep } from '../core/simulation.js';
import { appendTradeEvent } from '../core/tradeEvents.js';
import { Bias, StatsPeriod } from '../core/types.js';
import { HyperliquidAdapter, MidStreamHandle } from '../exchange/index.js';
import type { CandleTimeframe, OrderIntent } from '../exchange/types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../');
const distDir = path.join(rootDir, 'dist');

const app = express();
const port = Number(process.env.PORT || 8787);
const host = process.env.HOST || '0.0.0.0';

const LIVE_SYMBOL = 'BTC';
const REST_FALLBACK_MS = 60 * 1000; // at least 1m updates if WS unavailable

const LIVE_MAX_NOTIONAL_USDC = Number(process.env.LIVE_MAX_NOTIONAL_USDC || 30);
const LIVE_MAX_LEVERAGE = Number(process.env.LIVE_MAX_LEVERAGE || 10);
const LIVE_MANUAL_CONFIRMATION = String(process.env.LIVE_MANUAL_CONFIRMATION ?? 'true').toLowerCase() !== 'false';

const exchange = new HyperliquidAdapter();

let ingestBusy = false;
let wsReconnectTimer: NodeJS.Timeout | null = null;
let restFallbackTimer: NodeJS.Timeout | null = null;
let midStreamHandle: MidStreamHandle | null = null;

function parsePeriod(raw: unknown): StatsPeriod {
  return raw === 'week' ? 'week' : 'month';
}

function parseTimeframe(raw: unknown): CandleTimeframe {
  if (raw === '1m' || raw === '5m' || raw === '15m' || raw === '1h' || raw === '4h') {
    return raw;
  }
  return '5m';
}

function normalizeSymbol(raw: unknown): string {
  return String(raw ?? LIVE_SYMBOL).toUpperCase();
}

function toTradeSide(side: 'buy' | 'sell'): 'long' | 'short' {
  return side === 'buy' ? 'long' : 'short';
}

function isConfirmed(raw: unknown): boolean {
  return raw === true;
}

async function ingestPrice(symbol: string, price: number, _source: 'ws' | 'rest') {
  if (!Number.isFinite(price)) return;
  if (ingestBusy) return;
  ingestBusy = true;
  try {
    const db = await getDb();
    runSimulationStep(db.data, symbol, price);
    await db.write();
  } finally {
    ingestBusy = false;
  }
}

async function fetchLiveBtcMid(): Promise<number | null> {
  try {
    const mids = await exchange.getMids();
    const price = mids[LIVE_SYMBOL];
    return Number.isFinite(price) ? price : null;
  } catch {
    return null;
  }
}

async function ingestRestFallback() {
  const price = await fetchLiveBtcMid();
  if (!price) return;
  await ingestPrice(LIVE_SYMBOL, price, 'rest');
}

function startRestFallback() {
  if (restFallbackTimer) return;
  restFallbackTimer = setInterval(() => {
    ingestRestFallback().catch(() => undefined);
  }, REST_FALLBACK_MS);
  restFallbackTimer.unref?.();
}

function scheduleWsReconnect(delayMs = 3000) {
  if (wsReconnectTimer) return;
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    startLiveMidStream();
  }, delayMs);
  wsReconnectTimer.unref?.();
}

function startLiveMidStream() {
  if (!exchange.subscribeMids) {
    console.log('[live] Exchange adapter has no mid stream, using REST fallback each minute');
    startRestFallback();
    return;
  }

  if (midStreamHandle) return;

  try {
    midStreamHandle = exchange.subscribeMids({
      symbols: [LIVE_SYMBOL],
      onOpen: () => {
        console.log('[live] Hyperliquid WS connected');
        startRestFallback(); // keep fallback as safety net
      },
      onMid: (symbol, price) => {
        ingestPrice(symbol, price, 'ws').catch(() => undefined);
      },
      onClose: () => {
        console.log('[live] Hyperliquid WS disconnected, reconnecting...');
        midStreamHandle = null;
        scheduleWsReconnect();
      },
      onError: () => {
        // close event handles reconnect flow
      }
    });
  } catch {
    console.log('[live] Hyperliquid WS start failed, using REST fallback each minute');
    midStreamHandle = null;
    startRestFallback();
    scheduleWsReconnect(5000);
  }
}

app.use(cors());
app.use(express.json());

app.get('/api/health', (_req, res) => res.json({ ok: true }));

app.get('/api/dashboard', async (req, res) => {
  const period = parsePeriod(req.query.period);
  const db = await getDb();
  const activePositions = db.data.positions.filter((p) => p.status === 'open');
  const latestBias = [...db.data.biasCommands].reverse().find((b) => b.symbol === LIVE_SYMBOL)?.bias ?? 'off';
  const latestTick = [...db.data.marketTicks].reverse().find((t) => t.symbol === LIVE_SYMBOL) ?? null;

  let live = {
    connected: false,
    mode: {
      manualConfirmation: LIVE_MANUAL_CONFIRMATION,
      maxNotionalUsdc: LIVE_MAX_NOTIONAL_USDC,
      maxLeverage: LIVE_MAX_LEVERAGE
    },
    account: null as { equityUsd?: number; availableUsd?: number } | null,
    openOrders: 0,
    openPositions: [] as Array<{
      id: string;
      symbol: string;
      side: 'long' | 'short';
      size: number;
      entryPrice?: number;
      leverage?: number;
      unrealizedPnl?: number;
    }>,
    error: undefined as string | undefined
  };

  try {
    const [account, openOrders, openPositions] = await Promise.all([
      exchange.getAccountState(),
      exchange.getOpenOrders(LIVE_SYMBOL),
      exchange.getOpenPositions(LIVE_SYMBOL)
    ]);

    live = {
      ...live,
      connected: true,
      account: account ? { equityUsd: account.equityUsd, availableUsd: account.availableUsd } : null,
      openOrders: openOrders.length,
      openPositions: openPositions.map((p) => ({
        id: `${p.symbol}-${p.side}-${p.entryPrice ?? 0}-${p.size}`,
        symbol: p.symbol,
        side: p.side,
        size: p.size,
        entryPrice: p.entryPrice,
        leverage: p.leverage,
        unrealizedPnl: p.unrealizedPnl
      })),
      error: undefined
    };
  } catch (error) {
    live = {
      ...live,
      connected: false,
      error: error instanceof Error ? error.message : 'live_dashboard_fetch_failed'
    };
  }

  res.json({ activePositions, latestBias, stats: getStats(db.data, { period }), latestTick, live });
});

app.get('/api/history', async (req, res) => {
  const period = parsePeriod(req.query.period);
  const db = await getDb();
  const cutoffTs = Date.now() - (period === 'week' ? 7 : 30) * 24 * 60 * 60 * 1000;

  const closedPositions = db.data.positions
    .filter((p) => p.status === 'closed' && Date.parse(p.closedAt ?? p.openedAt) >= cutoffTs)
    .sort((a, b) => b.openedAt.localeCompare(a.openedAt));

  res.json({
    closedPositions,
    logs: db.data.tradeLogs.slice(-100).reverse(),
    events: db.data.tradeEvents.slice(-200).reverse(),
    stats: getStats(db.data, { period })
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

app.get('/api/live/status', async (_req, res) => {
  try {
    const [account, openOrders, openPositions] = await Promise.all([
      exchange.getAccountState(),
      exchange.getOpenOrders(LIVE_SYMBOL),
      exchange.getOpenPositions(LIVE_SYMBOL)
    ]);

    return res.json({
      ok: true,
      mode: {
        manualConfirmation: LIVE_MANUAL_CONFIRMATION,
        maxNotionalUsdc: LIVE_MAX_NOTIONAL_USDC,
        maxLeverage: LIVE_MAX_LEVERAGE
      },
      account,
      openOrders,
      openPositions
    });
  } catch (error) {
    return res.status(500).json({
      ok: false,
      error: error instanceof Error ? error.message : 'live_status_failed'
    });
  }
});

app.post('/api/live/leverage', async (req, res) => {
  const { symbol = LIVE_SYMBOL, leverage, confirm } = req.body as {
    symbol?: string;
    leverage?: number;
    confirm?: boolean;
  };

  const lev = Number(leverage);
  if (!Number.isFinite(lev) || lev <= 0 || lev > LIVE_MAX_LEVERAGE) {
    return res.status(400).json({ error: 'invalid_leverage' });
  }

  if (LIVE_MANUAL_CONFIRMATION && !isConfirmed(confirm)) {
    return res.status(409).json({
      ok: false,
      error: 'manual_confirmation_required',
      hint: 'resend with {"confirm": true}'
    });
  }

  const result = await exchange.setLeverage(normalizeSymbol(symbol), lev);
  return res.status(result.ok ? 200 : 400).json({ ok: result.ok, result });
});

app.post('/api/live/order/limit', async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    price,
    size,
    reduceOnly = false,
    clientOrderId,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'buy' | 'sell';
    price?: number;
    size?: number;
    reduceOnly?: boolean;
    clientOrderId?: string;
    confirm?: boolean;
  };

  if (side !== 'buy' && side !== 'sell') {
    return res.status(400).json({ error: 'invalid_side' });
  }

  const px = Number(price);
  const qty = Number(size);
  if (!Number.isFinite(px) || px <= 0 || !Number.isFinite(qty) || qty <= 0) {
    return res.status(400).json({ error: 'invalid_price_or_size' });
  }

  const notional = px * qty;
  if (!reduceOnly && notional > LIVE_MAX_NOTIONAL_USDC) {
    return res.status(400).json({
      ok: false,
      error: 'max_notional_exceeded',
      maxNotionalUsdc: LIVE_MAX_NOTIONAL_USDC,
      requestedNotionalUsdc: Number(notional.toFixed(4))
    });
  }

  if (LIVE_MANUAL_CONFIRMATION && !isConfirmed(confirm)) {
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
      maxNotionalUsdc: LIVE_MAX_NOTIONAL_USDC,
      manualConfirmation: LIVE_MANUAL_CONFIRMATION
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

  await db.write();

  return res.status(ack.ok ? 200 : 400).json({
    ok: ack.ok,
    notionalUsdc: Number(notional.toFixed(4)),
    ack
  });
});

app.post('/api/live/order/cancel', async (req, res) => {
  const { orderId, symbol = LIVE_SYMBOL, confirm } = req.body as {
    orderId?: string;
    symbol?: string;
    confirm?: boolean;
  };

  if (!orderId) {
    return res.status(400).json({ error: 'order_id_required' });
  }

  if (LIVE_MANUAL_CONFIRMATION && !isConfirmed(confirm)) {
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

app.post('/api/live/order/cancel-all', async (req, res) => {
  const { symbol = LIVE_SYMBOL, confirm } = req.body as {
    symbol?: string;
    confirm?: boolean;
  };

  if (LIVE_MANUAL_CONFIRMATION && !isConfirmed(confirm)) {
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

app.use(express.static(distDir));
app.get('*', (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

app.listen(port, host, () => {
  console.log(`Server listening on http://${host}:${port}`);
  ingestRestFallback().catch(() => undefined);
  startLiveMidStream();
});
