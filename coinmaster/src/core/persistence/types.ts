import type { DBShape } from '../types.js';

/**
 * Minimal persistence contract consumed by the server layer.
 *
 * Phase 0: both LowdbStore and PostgresStore implement this interface.
 * The server calls `getData()` to obtain the mutable in-memory snapshot,
 * mutates it via existing core functions, then calls `flush()` to persist.
 *
 * This keeps the migration non-invasive: core logic still operates on
 * plain DBShape objects — only the storage backend changes.
 */
export interface PersistenceStore {
  /** One-time initialisation (open file / connect pool / run migrations). */
  init(): Promise<void>;

  /** Returns the current in-memory data snapshot (mutable). */
  getData(): DBShape;

  /** Reload the in-memory snapshot from the backing store. */
  reload(): Promise<void>;

  /** Persist the current in-memory snapshot to the backing store. */
  flush(): Promise<void>;

  /** Lightweight connectivity / readiness probe. */
  healthCheck(): Promise<{ ok: boolean; backend: string; error?: string }>;

  /** Graceful shutdown (close pool / file handle). */
  close(): Promise<void>;
}
