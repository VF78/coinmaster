import { JSONFilePreset } from 'lowdb/node';
import { DBShape } from './types.js';

const defaultData: DBShape = {
  settings: {
    depositUsd: 1000
  },
  positions: [],
  tradeLogs: [],
  tradeEvents: [],
  biasCommands: [],
  marketTicks: [],
  dailyDDBaselines: [],
  riskGateAudit: []
};

function ensureDbShape(data: DBShape) {
  data.settings = data.settings ?? { depositUsd: 1000 };
  if (!Number.isFinite(data.settings.depositUsd)) {
    data.settings.depositUsd = 1000;
  }

  if (!Array.isArray(data.positions)) data.positions = [];
  if (!Array.isArray(data.tradeLogs)) data.tradeLogs = [];
  if (!Array.isArray(data.tradeEvents)) data.tradeEvents = [];
  if (!Array.isArray(data.biasCommands)) data.biasCommands = [];
  if (!Array.isArray(data.marketTicks)) data.marketTicks = [];
  if (!Array.isArray(data.dailyDDBaselines)) data.dailyDDBaselines = [];
  if (!Array.isArray(data.riskGateAudit)) data.riskGateAudit = [];
}

const DEFAULT_DB_FILE = process.env.COINMASTER_DB_FILE ?? 'data/db.json';

export async function getDb(file = DEFAULT_DB_FILE) {
  const db = await JSONFilePreset<DBShape>(file, defaultData);
  ensureDbShape(db.data);
  return db;
}
