import express from 'express';
import cors from 'cors';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { getDb } from '../core/db.js';
import { getStats, submitBias } from '../core/services.js';
import { runSimulationStep } from '../core/simulation.js';
import { Bias, StatsPeriod } from '../core/types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../');
const distDir = path.join(rootDir, 'dist');

const app = express();
const port = Number(process.env.PORT || 8787);
const host = process.env.HOST || '0.0.0.0';

const LIVE_SYMBOL = 'BTC';
const REST_FALLBACK_MS = 60 * 1000; // at least 1m updates if WS unavailable

let ingestBusy = false;
let ws: WebSocket | null = null;
let wsReconnectTimer: NodeJS.Timeout | null = null;
let restFallbackTimer: NodeJS.Timeout | null = null;

function parsePeriod(raw: unknown): StatsPeriod {
  return raw === 'week' ? 'week' : 'month';
}

async function ingestPrice(symbol: string, price: number, source: 'ws' | 'rest') {
  if (!Number.isFinite(price)) return;
  if (ingestBusy) return;
  ingestBusy = true;
  try {
    const db = await getDb();
    runSimulationStep(db.data, symbol, price);
    await db.write();
    if (source === 'ws') {
      // keep logs light: only websocket reconnect/status logs, no per-tick spam
    }
  } finally {
    ingestBusy = false;
  }
}

async function fetchHyperliquidBtcMid(): Promise<number | null> {
  try {
    const response = await fetch('https://api.hyperliquid.xyz/info', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ type: 'allMids' })
    });
    if (!response.ok) return null;

    const data = (await response.json()) as Record<string, string>;
    const raw = data[LIVE_SYMBOL];
    if (!raw) return null;
    const price = Number(raw);
    return Number.isFinite(price) ? price : null;
  } catch {
    return null;
  }
}

async function ingestRestFallback() {
  const price = await fetchHyperliquidBtcMid();
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
    startHyperliquidWs();
  }, delayMs);
  wsReconnectTimer.unref?.();
}

function startHyperliquidWs() {
  if (typeof WebSocket === 'undefined') {
    console.log('[live] WebSocket unavailable in runtime, using REST fallback each minute');
    startRestFallback();
    return;
  }

  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    ws = new WebSocket('wss://api.hyperliquid.xyz/ws');

    ws.addEventListener('open', () => {
      console.log('[live] Hyperliquid WS connected');
      ws?.send(JSON.stringify({ method: 'subscribe', subscription: { type: 'allMids' } }));
      // keep REST fallback enabled as safety net
      startRestFallback();
    });

    ws.addEventListener('message', (event) => {
      try {
        const payload = JSON.parse(String(event.data)) as any;
        const mids = payload?.data?.mids;
        const raw = mids?.[LIVE_SYMBOL];
        if (!raw) return;
        const price = Number(raw);
        if (!Number.isFinite(price)) return;
        ingestPrice(LIVE_SYMBOL, price, 'ws').catch(() => undefined);
      } catch {
        // ignore malformed frames
      }
    });

    ws.addEventListener('close', () => {
      console.log('[live] Hyperliquid WS disconnected, reconnecting...');
      ws = null;
      scheduleWsReconnect();
    });

    ws.addEventListener('error', () => {
      // rely on close->reconnect
    });
  } catch {
    console.log('[live] Hyperliquid WS start failed, using REST fallback each minute');
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

  res.json({ activePositions, latestBias, stats: getStats(db.data, { period }), latestTick });
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

app.use(express.static(distDir));
app.get('*', (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

app.listen(port, host, () => {
  console.log(`Server listening on http://${host}:${port}`);
  ingestRestFallback().catch(() => undefined);
  startHyperliquidWs();
});
