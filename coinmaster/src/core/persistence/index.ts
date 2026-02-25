import type { PersistenceStore } from './types.js';
import { LowdbStore } from './lowdbStore.js';

export type { PersistenceStore } from './types.js';
export { LowdbStore } from './lowdbStore.js';
export { PostgresStore } from './postgresStore.js';
export { DualWriteStore } from './dualWriteStore.js';

export type PersistenceBackend = 'lowdb' | 'postgres';

const BACKEND = (process.env.PERSISTENCE_BACKEND ?? 'lowdb') as PersistenceBackend;
const DUAL_WRITE = ['true', '1'].includes(
  (process.env.PERSISTENCE_DUAL_WRITE ?? '').toLowerCase()
);

let _store: PersistenceStore | null = null;

/**
 * Returns the singleton PersistenceStore based on PERSISTENCE_BACKEND env var.
 * First call triggers async initialisation; subsequent calls return the
 * same instance.
 *
 * When PERSISTENCE_BACKEND=lowdb and PERSISTENCE_DUAL_WRITE=true,
 * a DualWriteStore wraps lowdb (primary) + postgres (shadow).
 */
export async function getStore(): Promise<PersistenceStore> {
  if (_store) return _store;

  if (BACKEND === 'postgres') {
    // Dynamic import avoids pulling pg into lowdb-only bundles
    const { PostgresStore } = await import('./postgresStore.js');
    _store = new PostgresStore();
  } else if (DUAL_WRITE) {
    const { PostgresStore } = await import('./postgresStore.js');
    const { DualWriteStore } = await import('./dualWriteStore.js');
    _store = new DualWriteStore(new LowdbStore(), new PostgresStore());
  } else {
    _store = new LowdbStore();
  }

  await _store.init();
  return _store;
}
