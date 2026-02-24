import type { DBShape } from '../types.js';
import type { PersistenceStore } from './types.js';

/**
 * PostgreSQL persistence backend — Phase 0 skeleton.
 *
 * Provides `init()` (with pool creation + connectivity check) and
 * `healthCheck()`. Full CRUD will be implemented in Phase 1.
 *
 * Requires `DATABASE_URL` env var.
 * The `pg` package is dynamically imported so the dependency is
 * optional — lowdb-only deployments don't need it installed.
 */
export class PostgresStore implements PersistenceStore {
  private pool: any = null; // pg.Pool — dynamically imported
  private data: DBShape;
  private readonly connectionString: string;

  constructor(connectionString?: string) {
    this.connectionString = connectionString ?? process.env.DATABASE_URL ?? '';
    if (!this.connectionString) {
      throw new Error('PostgresStore requires DATABASE_URL or a connection string');
    }
    // In-memory snapshot — same shape as lowdb so core logic works unchanged.
    this.data = {
      settings: { depositUsd: 1000 },
      positions: [],
      tradeLogs: [],
      tradeEvents: [],
      biasCommands: [],
      marketTicks: [],
      dailyDDBaselines: [],
      riskGateAudit: []
    };
  }

  async init(): Promise<void> {
    // Dynamic import: pg is an optional peer dependency for Phase 0.
    let pg: any;
    try {
      const mod = 'pg';
      pg = await import(/* webpackIgnore: true */ mod);
    } catch {
      throw new Error(
        'PostgresStore requires the "pg" package. Install it with: npm install pg'
      );
    }

    const Pool = pg.default?.Pool ?? pg.Pool;
    this.pool = new Pool({ connectionString: this.connectionString });

    // Verify connectivity
    const client = await this.pool.connect();
    try {
      await client.query('SELECT 1');
    } finally {
      client.release();
    }

    console.log('[postgres] Connected to PostgreSQL');

    // TODO Phase 1: load current state into this.data from PG tables
  }

  getData(): DBShape {
    return this.data;
  }

  async flush(): Promise<void> {
    if (!this.pool) throw new Error('PostgresStore not initialised — call init() first');
    // TODO Phase 1: persist this.data snapshot to PG tables
    console.log('[postgres] flush() called — not yet implemented (Phase 1)');
  }

  async healthCheck(): Promise<{ ok: boolean; backend: string; error?: string }> {
    if (!this.pool) {
      return { ok: false, backend: 'postgres', error: 'pool not initialised' };
    }
    try {
      const client = await this.pool.connect();
      try {
        await client.query('SELECT 1');
      } finally {
        client.release();
      }
      return { ok: true, backend: 'postgres' };
    } catch (err: any) {
      return { ok: false, backend: 'postgres', error: err.message ?? 'unknown' };
    }
  }

  async close(): Promise<void> {
    if (this.pool) {
      await this.pool.end();
      this.pool = null;
    }
  }
}
