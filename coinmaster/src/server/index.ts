import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { nanoid } from 'nanoid';
import { getDb } from '../core/db.js';
import { runDeterministicReplay } from '../core/replay.js';
import { submitBias } from '../core/services.js';
import { runSimulationStep } from '../core/simulation.js';
import { appendTradeEvent } from '../core/tradeEvents.js';
import { Bias, DailyDDBaseline, RiskGateAuditEntry } from '../core/types.js';
import { HyperliquidAdapter, MidStreamHandle } from '../exchange/index.js';
import type { CandleTimeframe, OrderIntent, TradingErrorCode } from '../exchange/types.js';
import { buildLiveDashboardState, toLiveFill } from './liveSnapshot.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../');
const distDir = path.join(rootDir, 'dist');

const app = express();
const port = Number(process.env.PORT || 8787);
const host = process.env.HOST || '0.0.0.0';

const LIVE_SYMBOL = 'BTC';
const REST_FALLBACK_MS = 60 * 1000; // at least 1m updates if WS unavailable

const LIVE_MAX_LEVERAGE = Number(process.env.LIVE_MAX_LEVERAGE || 10);
const LIVE_MANUAL_CONFIRMATION = String(process.env.LIVE_MANUAL_CONFIRMATION ?? 'true').toLowerCase() !== 'false';
const ENABLE_PAPER_ENGINE = String(process.env.ENABLE_PAPER_ENGINE ?? 'false').toLowerCase() === 'true';
const ENABLE_SIMULATION_API = String(process.env.ENABLE_SIMULATION_API ?? 'false').toLowerCase() === 'true';
const ENABLE_REPLAY_API = String(process.env.ENABLE_REPLAY_API ?? 'false').toLowerCase() === 'true';

const LIVE_DAILY_DD_LIMIT_PCT = Number(process.env.LIVE_DAILY_DD_LIMIT_PCT || 20);
const LIVE_PORTFOLIO_LEVERAGE_CAP = Number(process.env.LIVE_PORTFOLIO_LEVERAGE_CAP || 10);
const OWNER_AUTH_TOKEN = process.env.OWNER_AUTH_TOKEN || '';
const OWNER_HMAC_SECRET = process.env.OWNER_HMAC_SECRET || '';

const LIVE_MODE = {
  manualConfirmation: LIVE_MANUAL_CONFIRMATION,
  maxLeverage: LIVE_MAX_LEVERAGE
};

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
  console.log(`[risk-gate] ${full.gate} passed=${full.passed} ${full.reason ?? ''}`);
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
setInterval(() => { flushRiskAudit().catch(() => undefined); }, 30_000);

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

async function evaluateRiskGates(): Promise<RiskCheckResult> {
  const blocks: string[] = [];

  // Fetch account state
  const [account, positions] = await Promise.all([
    exchange.getAccountState(),
    exchange.getOpenPositions()
  ]);

  const equityUsd = account?.equityUsd ?? 0;

  // Daily DD check
  const baseline = await getOrCreateDDBaseline(equityUsd);
  const ddPct = baseline.startEquityUsd > 0
    ? ((baseline.startEquityUsd - equityUsd) / baseline.startEquityUsd) * 100
    : 0;

  if (ddPct >= LIVE_DAILY_DD_LIMIT_PCT) {
    blocks.push('daily_loss_limit_exceeded');
    logRiskGateAudit({ gate: 'daily_dd', passed: false, reason: 'daily_loss_limit_exceeded', details: { ddPct: Number(ddPct.toFixed(2)), limit: LIVE_DAILY_DD_LIMIT_PCT, equityUsd, baselineEquityUsd: baseline.startEquityUsd } });
  } else {
    logRiskGateAudit({ gate: 'daily_dd', passed: true, details: { ddPct: Number(ddPct.toFixed(2)) } });
  }

  // Portfolio leverage check
  let totalNotional = 0;
  for (const pos of positions) {
    const notional = (pos.entryPrice ?? pos.markPrice ?? 0) * pos.size;
    totalNotional += notional;
  }
  const portfolioLeverage = equityUsd > 0 ? totalNotional / equityUsd : 0;

  if (portfolioLeverage > LIVE_PORTFOLIO_LEVERAGE_CAP) {
    blocks.push('leverage_limit_exceeded');
    logRiskGateAudit({ gate: 'leverage_cap', passed: false, reason: 'leverage_limit_exceeded', details: { portfolioLeverage: Number(portfolioLeverage.toFixed(2)), cap: LIVE_PORTFOLIO_LEVERAGE_CAP } });
  } else {
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

/** Close all positions emergency (daily DD hard stop) */
async function emergencyCloseAll() {
  console.log('[risk-gate] EMERGENCY: Daily DD limit hit — closing ALL positions');
  const positions = await exchange.getOpenPositions();
  for (const pos of positions) {
    const closeSide: 'buy' | 'sell' = pos.side === 'long' ? 'sell' : 'buy';
    // Market-close via limit at extreme price
    const extremePrice = closeSide === 'sell' ? 1 : 999_999;
    try {
      await exchange.placeLimitOrder({
        symbol: pos.symbol,
        side: closeSide,
        price: extremePrice,
        size: pos.size,
        reduceOnly: true,
        clientOrderId: `emergency-${nanoid()}`
      });
    } catch (e) {
      console.error(`[risk-gate] Failed to close ${pos.symbol}:`, e);
    }
  }
  // Also cancel all open orders
  try { await exchange.cancelAll(); } catch {}
}

/** Risk gate middleware for trading endpoints — checks DD + leverage before allowing order */
async function riskGateMiddleware(req: Request, res: Response, next: NextFunction) {
  try {
    const risk = await evaluateRiskGates();

    if (risk.blocks.includes('daily_loss_limit_exceeded')) {
      // Hard stop: close everything
      await emergencyCloseAll();
      return res.status(403).json({
        ok: false,
        errorCode: 'daily_loss_limit_exceeded' as TradingErrorCode,
        error: `Daily drawdown ${risk.dailyDDPct}% exceeds ${LIVE_DAILY_DD_LIMIT_PCT}% limit. All positions closed. Trading blocked.`,
        riskCheck: risk
      });
    }

    if (risk.blocks.includes('leverage_limit_exceeded')) {
      // Only block new non-reduceOnly orders
      const reduceOnly = req.body?.reduceOnly === true;
      if (!reduceOnly) {
        return res.status(403).json({
          ok: false,
          errorCode: 'leverage_limit_exceeded' as TradingErrorCode,
          error: `Portfolio leverage ${risk.portfolioLeverage}x exceeds ${LIVE_PORTFOLIO_LEVERAGE_CAP}x cap. Reduce positions first.`,
          riskCheck: risk
        });
      }
    }

    // Attach risk check to request for downstream use
    (req as any)._riskCheck = risk;
    next();
  } catch (error) {
    console.error('[risk-gate] Risk evaluation failed, allowing trade (fail-open):', error);
    next();
  }
}

const exchange = new HyperliquidAdapter();

let ingestBusy = false;
let wsReconnectTimer: NodeJS.Timeout | null = null;
let restFallbackTimer: NodeJS.Timeout | null = null;
let midStreamHandle: MidStreamHandle | null = null;
let latestLiveTick: { symbol: string; price: number; timestamp: string } | null = null;

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

async function ingestPrice(symbol: string, price: number, _source: 'ws' | 'rest') {
  if (!Number.isFinite(price)) return;

  latestLiveTick = {
    symbol,
    price,
    timestamp: new Date().toISOString()
  };

  if (!ENABLE_PAPER_ENGINE) return;
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

app.get('/api/dashboard', async (_req, res) => {
  const db = await getDb();
  const latestBias = [...db.data.biasCommands].reverse().find((b) => b.symbol === LIVE_SYMBOL)?.bias ?? 'off';

  let latestTick = latestLiveTick;
  if (!latestTick) {
    const freshMid = await fetchLiveBtcMid();
    if (freshMid) {
      latestTick = {
        symbol: LIVE_SYMBOL,
        price: freshMid,
        timestamp: new Date().toISOString()
      };
    }
  }

  const live = await buildLiveDashboardState(exchange, LIVE_SYMBOL, LIVE_MODE);

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

app.get('/api/settings/exchange', async (_req, res) => {
  const live = await buildLiveDashboardState(exchange, LIVE_SYMBOL, LIVE_MODE);

  return res.json({
    exchange: exchange.name,
    connected: live.connected,
    accountAddress: maskAddress(process.env.HYPERLIQUID_ACCOUNT_ADDRESS),
    walletAddress: maskAddress(process.env.HYPERLIQUID_API_WALLET_ADDRESS),
    mode: LIVE_MODE,
    account: live.account,
    capabilities: {
      privateAccount: exchange.capabilities.privateAccount,
      privateTrading: exchange.capabilities.privateTrading,
      realtimeMids: exchange.capabilities.realtimeMids
    },
    error: live.error
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
    return res.json(risk);
  } catch (error) {
    return res.status(500).json({
      canTrade: false,
      dailyDDPct: 0,
      portfolioLeverage: 0,
      blocks: ['risk_check_failed'],
      error: error instanceof Error ? error.message : 'risk_check_failed'
    });
  }
});

app.get('/api/live/status', async (_req, res) => {
  const live = await buildLiveDashboardState(exchange, LIVE_SYMBOL, LIVE_MODE);
  return res.json({
    ok: live.connected,
    ...live
  });
});

app.post('/api/live/leverage', ownerAuth, async (req, res) => {
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

app.post('/api/live/position/levels', ownerAuth, riskGateMiddleware, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    size,
    stopLoss,
    takeProfit,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'long' | 'short';
    size?: number;
    stopLoss?: number;
    takeProfit?: number;
    confirm?: boolean;
  };

  if (side !== 'long' && side !== 'short') {
    return res.status(400).json({ ok: false, error: 'invalid_side' });
  }

  const normalizedSymbol = normalizeSymbol(symbol);
  const qty = Number(size);
  const sl = Number(stopLoss);
  const tp = Number(takeProfit);

  if (!Number.isFinite(qty) || qty <= 0 || !Number.isFinite(sl) || sl <= 0 || !Number.isFinite(tp) || tp <= 0) {
    return res.status(400).json({ ok: false, error: 'invalid_size_or_levels' });
  }

  const sideMismatch = side === 'long' ? !(sl < tp) : !(sl > tp);
  if (sideMismatch) {
    return res.status(400).json({ ok: false, error: 'invalid_level_order' });
  }

  if (LIVE_MANUAL_CONFIRMATION && !isConfirmed(confirm)) {
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
      takeProfit: tp,
      cancelAllResult: {
        ok: false,
        error: cancelAllResult.error
      },
      error: 'cancel_existing_orders_failed'
    });
  }

  const slOrder = await exchange.placeTriggerOrder({
    symbol: normalizedSymbol,
    side: closingSide,
    size: qty,
    triggerPrice: sl,
    kind: 'sl',
    reduceOnly: true,
    clientOrderId: `sl-${nanoid()}`
  });

  const tpOrder = await exchange.placeTriggerOrder({
    symbol: normalizedSymbol,
    side: closingSide,
    size: qty,
    triggerPrice: tp,
    kind: 'tp',
    reduceOnly: true,
    clientOrderId: `tp-${nanoid()}`
  });

  const ok = slOrder.ok && tpOrder.ok;
  return res.status(ok ? 200 : 400).json({
    ok,
    symbol: normalizedSymbol,
    side,
    size: qty,
    stopLoss: sl,
    takeProfit: tp,
    cancelAllResult: {
      ok: cancelAllResult.ok,
      error: cancelAllResult.error
    },
    stopLossOrder: {
      ok: slOrder.ok,
      orderId: slOrder.orderId,
      error: slOrder.error
    },
    takeProfitOrder: {
      ok: tpOrder.ok,
      orderId: tpOrder.orderId,
      error: tpOrder.error
    },
    error: ok ? undefined : 'set_levels_failed'
  });
});

app.post('/api/live/order/limit', ownerAuth, riskGateMiddleware, async (req, res) => {
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

app.post('/api/live/order/cancel', ownerAuth, async (req, res) => {
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

app.post('/api/live/order/cancel-all', ownerAuth, async (req, res) => {
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

function pruneIdempotencyCache() {
  const cutoff = Date.now() - IDEMPOTENCY_TTL_MS;
  for (const [key, entry] of idempotencyCache) {
    if (entry.timestamp < cutoff) idempotencyCache.delete(key);
  }
}

// POST /api/live/order — idempotent place order
app.post('/api/live/order', ownerAuth, riskGateMiddleware, async (req, res) => {
  const {
    symbol = LIVE_SYMBOL,
    side,
    price,
    size,
    leverage,
    clientOrderId,
    reduceOnly = false,
    confirm
  } = req.body as {
    symbol?: string;
    side?: 'buy' | 'sell';
    price?: number;
    size?: number;
    leverage?: number;
    clientOrderId?: string;
    reduceOnly?: boolean;
    confirm?: boolean;
  };

  // Validation
  if (side !== 'buy' && side !== 'sell') {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'side must be buy or sell' });
  }
  const px = Number(price);
  const qty = Number(size);
  if (!Number.isFinite(px) || px <= 0 || !Number.isFinite(qty) || qty <= 0) {
    return res.status(400).json({ ok: false, errorCode: 'invalid_params' as TradingErrorCode, error: 'invalid price or size' });
  }

  const notional = px * qty;

  // Manual confirmation gate
  if (LIVE_MANUAL_CONFIRMATION && !isConfirmed(confirm)) {
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

  // Set leverage if provided — enforce LIVE_MAX_LEVERAGE cap
  if (leverage !== undefined) {
    const lev = Number(leverage);
    if (!Number.isFinite(lev) || lev <= 0 || lev > LIVE_MAX_LEVERAGE) {
      logRiskGateAudit({ gate: 'leverage_cap', passed: false, reason: 'leverage_limit_exceeded', details: { requested: lev, max: LIVE_MAX_LEVERAGE } });
      return res.status(400).json({ ok: false, errorCode: 'leverage_limit_exceeded' as TradingErrorCode, error: `Leverage ${lev}x exceeds max ${LIVE_MAX_LEVERAGE}x` });
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
  await db.write();

  const response = { ok: ack.ok, orderId: ack.orderId, clientOrderId: correlationId, status: ack.status, errorCode, error: ack.error };

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

  if (LIVE_MANUAL_CONFIRMATION && !confirmed) {
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

  if (LIVE_MANUAL_CONFIRMATION && !isConfirmed(confirm)) {
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

app.listen(port, host, () => {
  console.log(`Server listening on http://${host}:${port}`);
  ingestRestFallback().catch(() => undefined);
  startLiveMidStream();
});
