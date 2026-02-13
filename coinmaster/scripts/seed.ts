import { getDb } from '../src/core/db.js';
import { submitBias } from '../src/core/services.js';
import { runSimulationStep } from '../src/core/simulation.js';

async function main() {
  const db = await getDb();
  db.data.positions = [];
  db.data.tradeLogs = [];
  db.data.biasCommands = [];
  db.data.marketTicks = [];

  submitBias(db.data, 'BTC', 'long');
  const prices = [42000, 42120, 42210, 42340, 42600, 42500, 42820, 43000, 42700, 42400, 42050];
  for (const price of prices) runSimulationStep(db.data, 'BTC', price);

  submitBias(db.data, 'BTC', 'short');
  const prices2 = [41900, 41720, 41400, 41220, 40900, 40650, 40300, 40500, 40700, 41050];
  for (const price of prices2) runSimulationStep(db.data, 'BTC', price);

  submitBias(db.data, 'BTC', 'off');

  await db.write();
  console.log('Seeded demo data in data/db.json');
}

main();
