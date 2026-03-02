import { JSONFilePreset } from 'lowdb/node';
import type { Low } from 'lowdb';
import type { DBShape } from '../types.js';
import { cloneTradingRulesDefaults, normalizeTradingRules } from '../../shared/tradingRules.js';
import type { PersistenceStore } from './types.js';

const defaultData: DBShape = {
  settings: { depositUsd: 1000, tradingRules: cloneTradingRulesDefaults() },
  positions: [],
  tradeLogs: [],
  tradeEvents: [],
  biasCommands: [],
  marketTicks: [],
  dailyDDBaselines: [],
  riskGateAudit: [],
  pendingConfirmations: []
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
  if (!Array.isArray(data.pendingConfirmations)) data.pendingConfirmations = [];
}

export class LowdbStore implements PersistenceStore {
  private db: Low<DBShape> | null = null;
  private readonly file: string;

  constructor(file?: string) {
    this.file = file ?? process.env.COINMASTER_DB_FILE ?? 'data/db.json';
  }

  async init(): Promise<void> {
    this.db = await JSONFilePreset<DBShape>(this.file, defaultData);
    ensureDbShape(this.db.data);
  }

  getData(): DBShape {
    if (!this.db) throw new Error('LowdbStore not initialised — call init() first');
    return this.db.data;
  }

  async flush(): Promise<void> {
    if (!this.db) throw new Error('LowdbStore not initialised — call init() first');
    await this.db.write();
  }

  async healthCheck(): Promise<{ ok: boolean; backend: string; error?: string }> {
    return { ok: this.db !== null, backend: 'lowdb' };
  }

  async close(): Promise<void> {
    this.db = null;
  }
}
