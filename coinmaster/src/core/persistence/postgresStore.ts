import type { DBShape } from '../types.js';
import { cloneTradingRulesDefaults, normalizeTradingRules } from '../../shared/tradingRules.js';
import type { PersistenceStore } from './types.js';

const SNAPSHOT_KEY = 'dbshape_v1';

const defaultData: DBShape = {
  settings: { depositUsd: 1000, tradingRules: cloneTradingRulesDefaults() },
  positions: [],
  tradeLogs: [],
  tradeEvents: [],
  biasCommands: [],
  marketTicks: [],
  dailyDDBaselines: [],
  riskGateAudit: []
};

function ensureDbShape(data: DBShape) {
  data.settings = data.settings ?? { depositUsd: 1000, tradingRules: cloneTradingRulesDefaults() };
  if (!Number.isFinite(data.settings.depositUsd)) {
    data.settings.depositUsd = 1000;
  }
  data.settings.tradingRules = normalizeTradingRules(data.settings.tradingRules);
  if (!Array.isArray(data.positions)) data.positions = [];
  if (!Array.isArray(data.tradeLogs)) data.tradeLogs = [];
  if (!Array.isArray(data.tradeEvents)) data.tradeEvents = [];
  if (!Array.isArray(data.biasCommands)) data.biasCommands = [];
  if (!Array.isArray(data.marketTicks)) data.marketTicks = [];
  if (!Array.isArray(data.dailyDDBaselines)) data.dailyDDBaselines = [];
  if (!Array.isArray(data.riskGateAudit)) data.riskGateAudit = [];
}

/**
 * PostgreSQL persistence backend — Phase 1 snapshot bridge.
 *
 * Stores the full DBShape as a single JSONB document in the
 * `state_snapshot` table. This lets all existing core logic
 * (which mutates `db.data` in-memory then calls `db.write()`)
 * work unchanged against Postgres.
 *
 * Phase 2+ will migrate to the normalised tables from 001_initial_schema.sql.
 *
 * Requires `DATABASE_URL` env var and `pg` package.
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
    this.data = { ...defaultData };
  }

  async init(): Promise<void> {
    // Dynamic import: pg is a runtime dependency when backend=postgres.
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

    // Ensure snapshot table exists (idempotent)
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS state_snapshot (
        key        TEXT        PRIMARY KEY,
        data       JSONB       NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `);

    // Load existing snapshot (if any)
    const res = await this.pool.query(
      'SELECT data FROM state_snapshot WHERE key = $1',
      [SNAPSHOT_KEY]
    );

    if (res.rows.length > 0 && res.rows[0].data) {
      this.data = res.rows[0].data as DBShape;
    } else {
      this.data = JSON.parse(JSON.stringify(defaultData));
    }

    ensureDbShape(this.data);
    console.log('[postgres] Snapshot loaded (%d positions, %d tradeLogs)',
      this.data.positions.length, this.data.tradeLogs.length);
  }

  getData(): DBShape {
    return this.data;
  }

  async flush(): Promise<void> {
    if (!this.pool) throw new Error('PostgresStore not initialised — call init() first');

    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO state_snapshot (key, data, updated_at)
         VALUES ($1, $2, now())
         ON CONFLICT (key)
         DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at`,
        [SNAPSHOT_KEY, JSON.stringify(this.data)]
      );
      await client.query('COMMIT');
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
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
