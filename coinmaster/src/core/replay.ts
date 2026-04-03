import { Candle, CandleTimeframe } from '../exchange/types.js';
import { runSimulationStep } from './simulation.js';
import { submitBias } from './services.js';
import { Bias, DBShape } from './types.js';
import { cloneTradingRulesDefaults } from '../shared/tradingRules.js';

export interface ReplayRequest {
  symbol: string;
  bias: Exclude<Bias, 'off'>;
  timeframe: CandleTimeframe;
  candles: Candle[];
  depositUsd?: number;
}

export interface ReplaySummary {
  symbol: string;
  bias: Exclude<Bias, 'off'>;
  timeframe: CandleTimeframe;
  candlesProcessed: number;
  from: string;
  to: string;
  startPrice: number;
  endPrice: number;
  marketMovePct: number;
  totalTrades: number;
  winRatePct: number;
  realizedPnlUsd: number;
  openPnlUsd: number;
  netPnlUsd: number;
  roiPct: number;
  maxDrawdownPct: number;
  openPositions: number;
  closedPositions: number;
  generatedAt: string;
}

function round2(v: number): number {
  return Number(v.toFixed(2));
}

function buildReplayDb(depositUsd: number): DBShape {
  return {
    settings: {
      depositUsd,
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
  };
}

function computeMaxDrawdownPct(equityCurve: number[]): number {
  if (equityCurve.length === 0) return 0;
  let peak = equityCurve[0];
  let maxDd = 0;
  for (const value of equityCurve) {
    peak = Math.max(peak, value);
    const dd = peak > 0 ? ((peak - value) / peak) * 100 : 0;
    maxDd = Math.max(maxDd, dd);
  }
  return round2(maxDd);
}

export function runDeterministicReplay(input: ReplayRequest): ReplaySummary {
  const symbol = input.symbol.toUpperCase();
  const depositUsd = Number.isFinite(input.depositUsd) ? Number(input.depositUsd) : 1000;

  const candles = [...input.candles]
    .filter((c) => Number.isFinite(c.close) && Number.isFinite(Date.parse(c.timestamp)))
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));

  if (candles.length < 40) {
    throw new Error('not_enough_candles_for_replay');
  }

  const db = buildReplayDb(depositUsd);
  submitBias(db, symbol, input.bias);

  const equityCurve: number[] = [];

  for (const candle of candles) {
    runSimulationStep(db, symbol, candle.close, {
      timestamp: candle.timestamp,
      mode: 'replay'
    });

    const closedPnl = db.positions
      .filter((p) => p.status === 'closed')
      .reduce((acc, p) => acc + p.pnl, 0);

    const openPnl = db.positions
      .filter((p) => p.status === 'open')
      .reduce((acc, p) => acc + p.pnl, 0);

    equityCurve.push(depositUsd + closedPnl + openPnl);
  }

  const closed = db.positions.filter((p) => p.status === 'closed');
  const open = db.positions.filter((p) => p.status === 'open');
  const realizedPnl = closed.reduce((acc, p) => acc + p.pnl, 0);
  const openPnl = open.reduce((acc, p) => acc + p.pnl, 0);
  const netPnl = realizedPnl + openPnl;

  const wins = closed.filter((p) => p.pnl > 0).length;
  const winRatePct = closed.length > 0 ? (wins / closed.length) * 100 : 0;
  const roiPct = depositUsd > 0 ? (netPnl / depositUsd) * 100 : 0;

  const first = candles[0];
  const last = candles[candles.length - 1];
  const marketMovePct = first.close > 0 ? ((last.close - first.close) / first.close) * 100 : 0;

  return {
    symbol,
    bias: input.bias,
    timeframe: input.timeframe,
    candlesProcessed: candles.length,
    from: first.timestamp,
    to: last.timestamp,
    startPrice: round2(first.close),
    endPrice: round2(last.close),
    marketMovePct: round2(marketMovePct),
    totalTrades: closed.length,
    winRatePct: round2(winRatePct),
    realizedPnlUsd: round2(realizedPnl),
    openPnlUsd: round2(openPnl),
    netPnlUsd: round2(netPnl),
    roiPct: round2(roiPct),
    maxDrawdownPct: computeMaxDrawdownPct(equityCurve),
    openPositions: open.length,
    closedPositions: closed.length,
    generatedAt: new Date().toISOString()
  };
}
