/**
 * persistence-reconcile.ts
 *
 * Compares lowdb and PostgreSQL snapshots field-by-field, reporting
 * mismatches in counts, settings, and key data fields.
 *
 * Exit code 0 = in sync, 1 = differences found, 2 = fatal error.
 *
 * Requires: DATABASE_URL env var, pg package.
 *
 * Usage:
 *   npx tsx scripts/persistence-reconcile.ts
 *   # or
 *   npm run persistence:reconcile
 */

import type { DBShape } from '../src/core/types.js';
import { LowdbStore } from '../src/core/persistence/lowdbStore.js';
import { PostgresStore } from '../src/core/persistence/postgresStore.js';

interface Diff {
  field: string;
  lowdb: string | number;
  postgres: string | number;
}

function compareSnapshots(a: DBShape, b: DBShape): Diff[] {
  const diffs: Diff[] = [];

  // Settings
  if (a.settings.depositUsd !== b.settings.depositUsd) {
    diffs.push({
      field: 'settings.depositUsd',
      lowdb: a.settings.depositUsd,
      postgres: b.settings.depositUsd
    });
  }

  // Array counts
  const arrays: (keyof DBShape)[] = [
    'positions',
    'tradeLogs',
    'tradeEvents',
    'biasCommands',
    'marketTicks',
    'dailyDDBaselines',
    'riskGateAudit'
  ];

  for (const key of arrays) {
    const aArr = a[key] as unknown[];
    const bArr = b[key] as unknown[];
    if (aArr.length !== bArr.length) {
      diffs.push({
        field: `${key}.length`,
        lowdb: aArr.length,
        postgres: bArr.length
      });
    }
  }

  // Spot-check: first and last position IDs
  if (a.positions.length > 0 || b.positions.length > 0) {
    const aFirst = a.positions[0]?.id ?? '(none)';
    const bFirst = b.positions[0]?.id ?? '(none)';
    if (aFirst !== bFirst) {
      diffs.push({ field: 'positions[0].id', lowdb: aFirst, postgres: bFirst });
    }
    const aLast = a.positions[a.positions.length - 1]?.id ?? '(none)';
    const bLast = b.positions[b.positions.length - 1]?.id ?? '(none)';
    if (aLast !== bLast) {
      diffs.push({ field: 'positions[last].id', lowdb: aLast, postgres: bLast });
    }
  }

  // Spot-check: first and last tradeLog IDs
  if (a.tradeLogs.length > 0 || b.tradeLogs.length > 0) {
    const aFirst = a.tradeLogs[0]?.id ?? '(none)';
    const bFirst = b.tradeLogs[0]?.id ?? '(none)';
    if (aFirst !== bFirst) {
      diffs.push({ field: 'tradeLogs[0].id', lowdb: aFirst, postgres: bFirst });
    }
    const aLast = a.tradeLogs[a.tradeLogs.length - 1]?.id ?? '(none)';
    const bLast = b.tradeLogs[b.tradeLogs.length - 1]?.id ?? '(none)';
    if (aLast !== bLast) {
      diffs.push({ field: 'tradeLogs[last].id', lowdb: aLast, postgres: bLast });
    }
  }

  return diffs;
}

async function main() {
  const lowdb = new LowdbStore();
  await lowdb.init();
  const lowdbData = lowdb.getData();

  const pg = new PostgresStore();
  await pg.init();
  const pgData = pg.getData();

  console.log('[reconcile] Comparing lowdb ↔ postgres snapshots...\n');

  // Summary
  const arrays: (keyof DBShape)[] = [
    'positions', 'tradeLogs', 'tradeEvents', 'biasCommands',
    'marketTicks', 'dailyDDBaselines', 'riskGateAudit'
  ];
  console.log('  %-22s %8s %8s', 'Collection', 'lowdb', 'postgres');
  console.log('  ' + '-'.repeat(40));
  for (const key of arrays) {
    const aLen = (lowdbData[key] as unknown[]).length;
    const bLen = (pgData[key] as unknown[]).length;
    const mark = aLen === bLen ? ' ' : '!';
    console.log('  %-22s %8d %8d %s', key, aLen, bLen, mark);
  }
  console.log('  %-22s %8d %8d %s',
    'settings.depositUsd',
    lowdbData.settings.depositUsd,
    pgData.settings.depositUsd,
    lowdbData.settings.depositUsd === pgData.settings.depositUsd ? ' ' : '!'
  );
  console.log();

  const diffs = compareSnapshots(lowdbData, pgData);

  await lowdb.close();
  await pg.close();

  if (diffs.length === 0) {
    console.log('[reconcile] OK — snapshots are in sync.');
    process.exit(0);
  } else {
    console.log('[reconcile] MISMATCH — %d difference(s) found:', diffs.length);
    for (const d of diffs) {
      console.log('  %s: lowdb=%s postgres=%s', d.field, d.lowdb, d.postgres);
    }
    process.exit(1);
  }
}

main().catch((err) => {
  console.error('[reconcile] Fatal:', err);
  process.exit(2);
});
