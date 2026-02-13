import express from 'express';
import cors from 'cors';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { getDb } from '../core/db.js';
import { getStats, submitBias } from '../core/services.js';
import { runSimulationStep } from '../core/simulation.js';
import { Bias } from '../core/types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../');
const distDir = path.join(rootDir, 'dist');

const app = express();
const port = Number(process.env.PORT || 8787);
const host = process.env.HOST || '0.0.0.0';

app.use(cors());
app.use(express.json());

app.get('/api/health', (_req, res) => res.json({ ok: true }));

app.get('/api/dashboard', async (_req, res) => {
  const db = await getDb();
  const activePositions = db.data.positions.filter((p) => p.status === 'open');
  const latestBias = [...db.data.biasCommands].reverse().find((b) => b.symbol === 'BTC')?.bias ?? 'off';

  res.json({ activePositions, latestBias, stats: getStats(db.data) });
});

app.get('/api/history', async (_req, res) => {
  const db = await getDb();
  const closedPositions = db.data.positions
    .filter((p) => p.status === 'closed')
    .sort((a, b) => b.openedAt.localeCompare(a.openedAt));
  res.json({ closedPositions, logs: db.data.tradeLogs.slice(-100).reverse(), stats: getStats(db.data) });
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
  const { symbol = 'BTC', price } = req.body as { symbol?: string; price: number };
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
});
