import { getDb } from '../src/core/db.js';
import { submitBias } from '../src/core/services.js';
import { runSimulationStep } from '../src/core/simulation.js';

async function main() {
  const db = await getDb();
  db.data.settings = { depositUsd: 1000 };
  db.data.positions = [];
  db.data.tradeLogs = [];
  db.data.biasCommands = [];
  db.data.marketTicks = [];

  submitBias(db.data, 'BTC', 'long');
  const prices = [65800, 65920, 66080, 66220, 66410, 66330, 66500, 66620, 66470, 66290, 66180];
  for (const price of prices) runSimulationStep(db.data, 'BTC', price);

  submitBias(db.data, 'BTC', 'short');
  const prices2 = [66120, 65980, 65840, 65690, 65520, 65410, 65280, 65420, 65580, 65720];
  for (const price of prices2) runSimulationStep(db.data, 'BTC', price);

  submitBias(db.data, 'BTC', 'off');

  await db.write();
  console.log('Seeded demo data in data/db.json');
}

main();
