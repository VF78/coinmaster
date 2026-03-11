import { nanoid } from 'nanoid';
import type { BacktestCreateRunRequest, BacktestRun, TradingRulesSettings } from '../shared/dto.js';
import { inferAssetClassFromSymbol, normalizeTradingRules } from '../shared/tradingRules.js';

export interface BacktestEngineVersion {
  version: string;
  commit: string;
}

function normalizeBacktestRules(rawRules: TradingRulesSettings, symbol: string): TradingRulesSettings {
  const normalized = normalizeTradingRules(rawRules);
  const selectedKey = String(symbol).trim().toLowerCase();
  const selected = normalized.coins.find((coin) => String(coin.symbol).trim().toLowerCase() === selectedKey);

  return {
    ...normalized,
    coins: [
      {
        symbol,
        enabled: true,
        pct: 100,
        assetClass: selected?.assetClass ?? inferAssetClassFromSymbol(symbol),
      },
    ],
    autoConfirm: false,
  };
}

export function getBacktestEngineVersion(): BacktestEngineVersion {
  return {
    version: process.env.npm_package_version || '0.1.0',
    commit: process.env.COINMASTER_BUILD_COMMIT || process.env.GIT_COMMIT || process.env.COMMIT_SHA || 'unknown',
  };
}

export function createQueuedBacktestRun(input: {
  request: BacktestCreateRunRequest;
  rules: TradingRulesSettings;
  symbol: string;
  requestedBy?: string;
}): BacktestRun {
  const now = new Date().toISOString();
  const engine = getBacktestEngineVersion();

  return {
    id: nanoid(),
    status: 'queued',
    symbol: input.symbol,
    createdAt: now,
    requestedBy: input.requestedBy,
    startTimeMs: input.request.startTimeMs,
    endTimeMs: input.request.endTimeMs,
    engineVersion: engine.version,
    engineCommit: engine.commit,
    marketDataCoverage: {
      requestedFromMs: input.request.startTimeMs,
      requestedToMs: input.request.endTimeMs,
    },
    rulesSnapshot: normalizeBacktestRules(input.rules, input.symbol),
    bySymbol: [],
    aiAnalysis: {
      status: 'idle',
    },
  };
}
