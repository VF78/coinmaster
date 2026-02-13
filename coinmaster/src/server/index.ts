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
const LIVE_POLL_MS = 5 * 60 * 1000;
let liveBusy = false;

function parsePeriod(raw: unknown): StatsPeriod {
  return raw === 'week' ? 'week' : 'month';
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

async function ingestLiveTick() {
  if (liveBusy) return;
  liveBusy = true;
  try {
    const price = await fetchHyperliquidBtcMid();
    if (!price) return;

    const db = await getDb();
    runSimulationStep(db.data, LIVE_SYMBOL, price);
    await db.write();
  } finally {
    liveBusy = false;
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

// Keep endpoint for debugging/manual override, but UI no longer depends on it.
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

// Serve web app build from same origin (single-link deployment)
app.use(express.static(distDir));
app.get('*', (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

app.listen(port, host, () => {
  console.log(`Server listening on http://${host}:${port}`);
  ingestLiveTick();
  const timer = setInterval(ingestLiveTick, LIVE_POLL_MS);
  timer.unref?.();
});
