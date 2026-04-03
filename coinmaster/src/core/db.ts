import { getStore } from './persistence/index.js';
import type { DBShape } from './types.js';

/**
 * Returns an object matching the legacy lowdb interface: { data, write() }.
 *
 * All existing call sites (`db.data.positions`, `await db.write()`, etc.)
 * continue to work unchanged — the backing store is selected by
 * `PERSISTENCE_BACKEND` env var (default: lowdb).
 */
export async function getDb() {
  const store = await getStore();
  return {
    get data(): DBShape {
      return store.getData();
    },
    async reload(): Promise<void> {
      await store.reload();
    },
    async write(): Promise<void> {
      await store.flush();
    }
  };
}
