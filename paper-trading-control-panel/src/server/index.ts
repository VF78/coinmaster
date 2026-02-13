import express from 'express';
import cors from 'cors';
import { getDb } from '../core/db.js';
import { getStats, submitBias } from '../core/services.js';
import { runSimulationStep } from '../core/simulation.js';
import { Bias } from '../core/types.js';

const app = express();
const port = 8787;

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
  const closedPositions = db.data.positions.filter((p) => p.status === 'closed').sort((a, b) => b.openedAt.localeCompare(a.openedAt));
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
  if (!price || Number.isNaN(price)) {
    return res.status(400).json({ error: 'price_required' });
  }

  const db = await getDb();
  const signal = runSimulationStep(db.data, symbol.toUpperCase(), Number(price));
  await db.write();
  return res.json({ ok: true, signal });
});

app.listen(port, () => {
  console.log(`API listening on http://localhost:${port}`);
});
