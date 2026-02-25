/**
 * persistence-seed-postgres.ts
 *
 * Copies the current lowdb snapshot into the PostgreSQL state_snapshot table.
 * Use this before enabling dual-write or when seeding a fresh PG instance.
 *
 * Requires: DATABASE_URL env var, pg package.
 *
 * Usage:
 *   npx tsx scripts/persistence-seed-postgres.ts
 *   # or
 *   npm run persistence:seed-pg
 */

import { LowdbStore } from '../src/core/persistence/lowdbStore.js';
import { PostgresStore } from '../src/core/persistence/postgresStore.js';

async function main() {
  // 1. Load lowdb snapshot
  const lowdb = new LowdbStore();
  await lowdb.init();
  const snapshot = lowdb.getData();

  console.log('[seed-pg] Loaded lowdb snapshot:');
  console.log('  positions:        %d', snapshot.positions.length);
  console.log('  tradeLogs:        %d', snapshot.tradeLogs.length);
  console.log('  tradeEvents:      %d', snapshot.tradeEvents.length);
  console.log('  biasCommands:     %d', snapshot.biasCommands.length);
  console.log('  marketTicks:      %d', snapshot.marketTicks.length);
  console.log('  dailyDDBaselines: %d', snapshot.dailyDDBaselines.length);
  console.log('  riskGateAudit:    %d', snapshot.riskGateAudit.length);
  console.log('  depositUsd:       %d', snapshot.settings.depositUsd);

  // 2. Init postgres store (creates table if needed, loads existing data)
  const pg = new PostgresStore();
  await pg.init();

  // 3. Copy snapshot into postgres store's in-memory data, then flush
  const pgData = pg.getData();
  Object.assign(pgData, JSON.parse(JSON.stringify(snapshot)));
  await pg.flush();

  console.log('[seed-pg] Snapshot written to PostgreSQL.');

  await lowdb.close();
  await pg.close();
  console.log('[seed-pg] Done.');
}

main().catch((err) => {
  console.error('[seed-pg] Fatal:', err);
  process.exit(1);
});
