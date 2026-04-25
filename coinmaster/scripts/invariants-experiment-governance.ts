import {
  buildBacktestLiveDeltaReport,
  buildDefaultReplayAssumptions,
  buildObjectiveMetrics,
  buildRollingWindowSchedule,
  createExperimentFromRun,
  createExperimentTrial,
  createOptunaRequest,
  createUnavailableQuantStatsReport,
  evaluateChampionAcceptance,
  promoteChampionTrial,
} from '../src/core/experimentGovernance.js';
import type { DBShape } from '../src/core/types.js';
import type { BacktestRun } from '../src/shared/dto.js';

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string): void {
  if (condition) {
    passed += 1;
    console.log(`  ✓ ${label}`);
  } else {
    failed += 1;
    console.error(`  ✗ FAIL: ${label}`);
  }
}

function createRun(overrides: Partial<BacktestRun> = {}): BacktestRun {
  return {
    id: 'run-1',
    status: 'completed',
    symbol: 'BTC',
    biasMode: 'both',
    createdAt: '2026-04-22T00:00:00.000Z',
    startTimeMs: Date.parse('2025-01-01T00:00:00.000Z'),
    endTimeMs: Date.parse('2025-06-01T00:00:00.000Z'),
    engineVersion: 'v1',
    engineCommit: 'abc',
    rulesSnapshot: {
      coins: [{ symbol: 'BTC', enabled: true, pct: 100 }],
      entryTf: '15m',
      exitTf: '1h',
      entryTimeframes: ['15m'],
      emergencyExitTimeframes: ['1h'],
      engulfingLookbackCandles: 5,
      fvgRetrace: 0.5,
      fvgMinWidthPct: 0.3,
      fvgRequireSweep: false,
      fvgSweepLookbackCandles: 20,
      fvgRequireFirstTouch: false,
      maxZoneAgeCandles: 12,
      fvgRequireConfirmation: false,
      fvgConfirmationTimeframes: ['15m'],
      maxLeverage: 5,
      dailyDrawdown: 5,
      tpPct: 2,
      tpLevels: [3],
      slPct: 1,
      exitClosePct: 50,
      autoConfirm: false,
    },
    coverage: {
      symbols: ['BTC'],
      timeframes: ['15m', '1h', '4h'],
      window: {
        startTimeMs: Date.parse('2025-01-01T00:00:00.000Z'),
        endTimeMs: Date.parse('2025-06-01T00:00:00.000Z'),
      },
    },
    replayAssumptions: buildDefaultReplayAssumptions(),
    summary: {
      totalTrades: 12,
      winRatePct: 58.33,
      realizedPnlUsd: 120,
      openPnlUsd: 0,
      netPnlUsd: 120,
      roiPct: 12,
      maxDrawdownPct: 8,
      expectancyUsd: 10,
    },
    bySymbol: [{
      symbol: 'BTC',
      totalTrades: 12,
      wins: 7,
      losses: 5,
      realizedPnlUsd: 120,
      netPnlUsd: 120,
      slCount: 3,
      tp1Count: 4,
      tp2Count: 3,
      tp3Count: 2,
      emergencyExitCount: 1,
      rejectedSignals: 2,
    }],
    aiAnalysis: { status: 'idle' },
    ...overrides,
  };
}

console.log('\n── Experiment Governance Invariants ──');

{
  const run = createRun();
  const schedule = buildRollingWindowSchedule({
    symbol: run.symbol,
    rules: run.rulesSnapshot,
    startTimeMs: run.startTimeMs,
    endTimeMs: run.endTimeMs,
  });
  assert(schedule.windows.length >= 1, 'rolling schedule produces at least one window');
  assert(schedule.windows[0].test.startTimeMs >= schedule.windows[0].train.endTimeMs, 'test window starts after train window');
  assert(schedule.coverage.symbols[0] === 'BTC', 'coverage carries symbol');
}

{
  const report = createUnavailableQuantStatsReport('missing_python_package');
  assert(report.status === 'unavailable', 'quantstats boundary records unavailable instead of faking report');

  const request = createOptunaRequest({ experimentId: 'exp-1' });
  assert(request.storageBackend === 'postgres_rdbstorage', 'optuna request keeps RDBStorage design boundary');
  assert(request.pruner.type === 'median', 'optuna boundary declares a deterministic pruner config');
}

{
  const run = createRun();
  const experiment = createExperimentFromRun({ sourceRun: run });
  const trial = createExperimentTrial({
    experiment,
    sourceRunId: run.id,
    trialNumber: 0,
    parameterValues: { slPct: 1.25 },
    rulesSnapshot: run.rulesSnapshot,
    engineVersion: run.engineVersion,
    engineCommit: run.engineCommit,
  });
  trial.status = 'completed';
  trial.summary = run.summary;
  trial.bySymbol = run.bySymbol;
  trial.objectiveMetrics = buildObjectiveMetrics(run.summary);
  trial.deltaReport = buildBacktestLiveDeltaReport({
    coverage: experiment.coverage,
    backtestSummary: run.summary,
    tradeBreakdown: [{ setup: 'engulfing', timeframe: '15m', source: 'backtest:engulfing', tradeCount: 12, wins: 7, losses: 5, netPnlUsd: 120 }],
    livePositions: [{
      id: 'p1',
      symbol: 'BTC',
      side: 'long',
      entryPrice: 100,
      stopLoss: 95,
      takeProfit: 110,
      size: 1,
      openedAt: '2025-04-10T00:00:00.000Z',
      closedAt: '2025-04-10T01:00:00.000Z',
      status: 'closed',
      pnl: 15,
      source: 'live',
    }],
    executionIntents: [{
      id: 'e1',
      component: 'engulfing-monitor',
      price: 100,
      reduceOnly: false,
      reason: 'engulfing_entry_15m',
      symbol: 'BTC',
      side: 'buy',
      timeframe: '15m',
      strategy: 'engulfing',
      sourceLabel: 'engulfing:auto:15m',
      status: 'auto_order_placed',
      auditedOperatorOverride: false,
      policyDecision: 'accepted',
      createdAt: '2025-04-10T00:00:00.000Z',
      updatedAt: '2025-04-10T00:00:00.000Z',
    }],
  });

  const acceptance = evaluateChampionAcceptance({ trial, experiment });
  assert(acceptance.passed, 'completed candidate trial can satisfy acceptance criteria');

  const db = {
    settings: {} as DBShape['settings'],
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
    experiments: [experiment],
    experimentTrials: [trial],
    championConfigs: [],
    radarSignals: [],
    alphaRadarObservations: [],
    evidenceBundles: [],
    signalCandidates: [],
    radarContextPolicies: [],
    executionIntents: [],
  } as DBShape;

  const champion = promoteChampionTrial({ db, experiment, trial, promotedBy: 'invariant' });
  assert(champion.status === 'active', 'promotion creates active champion only after acceptance passes');
  assert(db.championConfigs.length === 1, 'champion persists into durable collection');
}

if (failed > 0) {
  console.error(`\nExperiment governance invariants failed (${failed} failed, ${passed} passed)`);
  process.exit(1);
}

console.log(`\nExperiment governance invariants passed (${passed} checks)`);
