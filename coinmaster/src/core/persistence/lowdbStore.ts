import { JSONFilePreset } from 'lowdb/node';
import type { Low } from 'lowdb';
import type { DBShape } from '../types.js';
import { cloneTradingRulesDefaults } from '../../shared/tradingRules.js';
import type { PersistenceStore } from './types.js';

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
  backtestRuns: [],
  optimizationResults: [],
  radarSignals: []
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
  if (!Array.isArray(data.optimizationResults)) data.optimizationResults = [];
  if (!Array.isArray(data.radarSignals)) data.radarSignals = [];
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

  async reload(): Promise<void> {
    if (!this.db) throw new Error('LowdbStore not initialised — call init() first');
    this.db = await JSONFilePreset<DBShape>(this.file, defaultData);
    ensureDbShape(this.db.data);
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
