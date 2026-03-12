import { nanoid } from 'nanoid';
import type { BacktestBiasMode, BacktestCreateRunRequest, BacktestRun, TradingRulesSettings } from '../shared/dto.js';
import { inferAssetClassFromSymbol, normalizeTradingRules } from '../shared/tradingRules.js';

const BACKTEST_AI_SUMMARY_MAX_CHARS = 2_000;
const BACKTEST_AI_REPORT_MAX_CHARS = 24_000;
const BACKTEST_AI_RECOMMENDATION_MAX_CHARS = 600;
const BACKTEST_AI_RECOMMENDATION_MAX_ITEMS = 12;

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

function normalizeRecommendations(input: unknown): string[] | undefined {
  if (!Array.isArray(input)) return undefined;
  const rows = input
    .map((item) => String(item ?? '').trim())
    .filter(Boolean)
    .slice(0, BACKTEST_AI_RECOMMENDATION_MAX_ITEMS)
    .map((item) => item.slice(0, BACKTEST_AI_RECOMMENDATION_MAX_CHARS));
  return rows.length > 0 ? rows : undefined;
}

export function markBacktestAiAnalysisRequested(run: BacktestRun): BacktestRun {
  run.aiAnalysis = {
    status: 'pending',
    requestedAt: new Date().toISOString(),
    completedAt: undefined,
    error: undefined,
    summary: undefined,
    report: undefined,
    recommendations: undefined,
    model: undefined,
  };
  return run;
}

export function applyBacktestAiAnalysisResult(
  run: BacktestRun,
  input: { model?: unknown; summary?: unknown; report?: unknown; recommendations?: unknown; error?: unknown }
): BacktestRun {
  const report = String(input.report ?? '').trim();
  const summary = String(input.summary ?? '').trim();
  const error = String(input.error ?? '').trim();
  const recommendations = normalizeRecommendations(input.recommendations);

  run.aiAnalysis = {
    status: report || summary ? 'completed' : 'failed',
    model: String(input.model ?? '').trim() || undefined,
    requestedAt: run.aiAnalysis?.requestedAt,
    completedAt: new Date().toISOString(),
    error: report || summary ? undefined : (error || 'backtest_ai_analysis_failed'),
    summary: summary ? summary.slice(0, BACKTEST_AI_SUMMARY_MAX_CHARS) : undefined,
    report: report ? report.slice(0, BACKTEST_AI_REPORT_MAX_CHARS) : undefined,
    recommendations,
  };
  return run;
}

function normalizeBacktestBiasMode(value: unknown): BacktestBiasMode {
  return value === 'long' || value === 'short' || value === 'both' ? value : 'both';
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
    biasMode: normalizeBacktestBiasMode(input.request.biasMode),
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
