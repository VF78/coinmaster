import type { DBShape } from '../types.js';
import { cloneTradingRulesDefaults } from '../../shared/tradingRules.js';
import logger from '../../lib/logger.js';
import type { PersistenceStore } from './types.js';

const SNAPSHOT_KEY = 'dbshape_v1';

const defaultData: DBShape = {
  settings: {
    depositUsd: 1000,
    tradingRules: cloneTradingRulesDefaults(),
    telegramNotify: {
      botToken: '',
      chatId: '',
      notifyOpen: true,
      notifyTp: true,
      notifySl: true,
      notifyManualConfirm: true,
      notifyDailyAnalytics: true,
      notifySignalRejected: false,
      notifyOrderRejected: false,
      notifyPositionClosed: false,
    },
    hyperliquid: {
      accountAddress: '',
      apiWalletAddress: '',
      apiPrivateKey: '',
    },
    externalExchanges: {
      bybit: {
        mode: 'off',
        apiKey: '',
        apiSecret: '',
        accountType: 'UNIFIED',
        categories: ['linear'],
      },
    },
  },
  positions: [],
  tradeLogs: [],
  tradeEvents: [],
  biasCommands: [],
  marketTicks: [],
  dailyDDBaselines: [],
  riskGateAudit: [],
  pendingConfirmations: [],
  telegramOutbox: [],
  aiMasterInsights: [],
  aiMasterQa: [],
  backtestRuns: []
};

function ensureDbShape(data: DBShape) {
  data.settings = data.settings ?? { depositUsd: 1000, tradingRules: cloneTradingRulesDefaults() };
  if (!Number.isFinite(data.settings.depositUsd)) {
    data.settings.depositUsd = 1000;
  }
  if (!data.settings.tradingRules || typeof data.settings.tradingRules !== 'object') {
    data.settings.tradingRules = cloneTradingRulesDefaults();
  }
  data.settings.telegramNotify = data.settings.telegramNotify ?? {
    botToken: '',
    chatId: '',
    notifyOpen: true,
    notifyTp: true,
    notifySl: true,
    notifyManualConfirm: true,
    notifyDailyAnalytics: true,
    notifySignalRejected: false,
    notifyOrderRejected: false,
    notifyPositionClosed: false,
  };
  data.settings.telegramNotify.botToken = String(data.settings.telegramNotify.botToken ?? '');
  data.settings.telegramNotify.chatId = String(data.settings.telegramNotify.chatId ?? '');
  data.settings.telegramNotify.notifyOpen = data.settings.telegramNotify.notifyOpen !== false;
  data.settings.telegramNotify.notifyTp = data.settings.telegramNotify.notifyTp !== false;
  data.settings.telegramNotify.notifySl = data.settings.telegramNotify.notifySl !== false;
  data.settings.telegramNotify.notifyManualConfirm = data.settings.telegramNotify.notifyManualConfirm !== false;
  data.settings.telegramNotify.notifyDailyAnalytics = data.settings.telegramNotify.notifyDailyAnalytics !== false;
  data.settings.telegramNotify.notifySignalRejected = data.settings.telegramNotify.notifySignalRejected === true;
  data.settings.telegramNotify.notifyOrderRejected = data.settings.telegramNotify.notifyOrderRejected === true;
  data.settings.telegramNotify.notifyPositionClosed = data.settings.telegramNotify.notifyPositionClosed === true;

  data.settings.hyperliquid = data.settings.hyperliquid ?? {
    accountAddress: '',
    apiWalletAddress: '',
    apiPrivateKey: '',
  };
  data.settings.hyperliquid.accountAddress = String(data.settings.hyperliquid.accountAddress ?? '').trim();
  data.settings.hyperliquid.apiWalletAddress = String(data.settings.hyperliquid.apiWalletAddress ?? '').trim();
  data.settings.hyperliquid.apiPrivateKey = String(data.settings.hyperliquid.apiPrivateKey ?? '').trim();

  // Migrate legacy key from earlier implementation
  if (!data.settings.externalExchanges && (data.settings as any).readOnlyExchanges) {
    data.settings.externalExchanges = (data.settings as any).readOnlyExchanges;
    delete (data.settings as any).readOnlyExchanges;
  }

  data.settings.externalExchanges = data.settings.externalExchanges ?? {
    bybit: {
      mode: 'off',
      apiKey: '',
      apiSecret: '',
      accountType: 'UNIFIED',
      categories: ['linear'],
    },
  };

  const bybit = data.settings.externalExchanges.bybit ?? {
    mode: 'off',
    apiKey: '',
    apiSecret: '',
    accountType: 'UNIFIED',
    categories: ['linear'],
  };

  bybit.mode = bybit.mode === 'read_only' ? 'read_only' : bybit.mode === 'live' ? 'live' : 'off';
  bybit.apiKey = String(bybit.apiKey ?? '').trim();
  bybit.apiSecret = String(bybit.apiSecret ?? '').trim();
  bybit.accountType = bybit.accountType === 'CONTRACT' || bybit.accountType === 'SPOT' ? bybit.accountType : 'UNIFIED';
  bybit.categories = Array.isArray(bybit.categories) && bybit.categories.length > 0
    ? [...new Set(bybit.categories.filter((c): c is 'linear' | 'inverse' | 'spot' | 'option' => c === 'linear' || c === 'inverse' || c === 'spot' || c === 'option'))]
    : ['linear'];
  if (bybit.categories.length === 0) bybit.categories = ['linear'];

  data.settings.externalExchanges.bybit = bybit;

  if (!Array.isArray(data.positions)) data.positions = [];
  if (!Array.isArray(data.tradeLogs)) data.tradeLogs = [];
  if (!Array.isArray(data.tradeEvents)) data.tradeEvents = [];
  if (!Array.isArray(data.biasCommands)) data.biasCommands = [];
  if (!Array.isArray(data.marketTicks)) data.marketTicks = [];
  if (!Array.isArray(data.dailyDDBaselines)) data.dailyDDBaselines = [];
  if (!Array.isArray(data.riskGateAudit)) data.riskGateAudit = [];
  if (!Array.isArray(data.pendingConfirmations)) data.pendingConfirmations = [];
  if (!Array.isArray(data.telegramOutbox)) data.telegramOutbox = [];
  if (!Array.isArray(data.aiMasterInsights)) data.aiMasterInsights = [];
  if (!Array.isArray(data.aiMasterQa)) data.aiMasterQa = [];
  if (!Array.isArray(data.backtestRuns)) data.backtestRuns = [];
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

    logger.info({ component: 'postgres' }, 'connected to PostgreSQL');

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
    logger.info({ component: 'postgres', positions: this.data.positions.length, tradeLogs: this.data.tradeLogs.length }, 'snapshot loaded');
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
