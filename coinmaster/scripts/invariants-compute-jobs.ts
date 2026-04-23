import {
  computeCandleLoadWindow,
  createComputeJobProgress,
  getRequiredComputeTimeframes,
  reconcileComputeJob,
  shouldPersistProgress,
} from '../src/core/computeJob.js';
import type { TradingRulesSettings } from '../src/shared/dto.js';

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

function createRules(overrides: Partial<TradingRulesSettings> = {}): TradingRulesSettings {
  return {
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
    ...overrides,
  };
}

console.log('\n── Compute Job Invariants ──');

{
  const rules = createRules({
    entryTimeframes: ['5m', '15m'],
    emergencyExitTimeframes: ['1h'],
    fvgRequireConfirmation: true,
    fvgConfirmationTimeframes: ['5m', '4h'],
  });
  const required = getRequiredComputeTimeframes(rules);

  assert(required.includes('5m'), 'required timeframes include entry timeframe');
  assert(required.includes('1h') && required.includes('4h'), 'required timeframes keep canonical higher timeframes');
  assert(required.filter((value) => value === '5m').length === 1, 'required timeframes stay deduplicated');

  const window = computeCandleLoadWindow({
    timeframe: '1h',
    startTimeMs: 1_000_000,
    endTimeMs: 2_000_000,
  });
  assert(window.startTimeMs === 1_000_000 - (50 * 60 * 60_000), 'candle load window applies shared padding by timeframe');
}

{
  const progress = createComputeJobProgress(3, 7, 'evaluating_candidates', '2026-04-23T10:00:00.000Z');
  assert(progress.percent === 42.86, 'progress percent is rounded consistently');
  assert(shouldPersistProgress({ completed: 3, total: 7 }), 'small optimization batches persist progress every candidate');
  assert(!shouldPersistProgress({ completed: 4, total: 120 }), 'large batches do not flush every candidate');
}

{
  const queuedFailure = reconcileComputeJob({
    job: {
      status: 'queued',
      createdAt: '2026-04-23T09:59:00.000Z',
    },
    nowMs: Date.parse('2026-04-23T10:00:00.000Z'),
    queuedFailureReason: 'worker did not start',
  });
  assert(queuedFailure === 'worker did not start', 'queued jobs fail deterministically after timeout');

  const stalledBacktest = reconcileComputeJob({
    job: {
      status: 'running',
      createdAt: '2026-04-23T09:58:00.000Z',
      startedAt: '2026-04-23T09:58:10.000Z',
    },
    isLocallyActive: false,
    runningFailureReason: 'backtest worker is not active',
  });
  assert(stalledBacktest === 'backtest worker is not active', 'running in-process jobs fail when no worker owns them');

  const staleOptimizer = reconcileComputeJob({
    job: {
      status: 'running',
      createdAt: '2026-04-23T09:58:00.000Z',
      startedAt: '2026-04-23T09:58:10.000Z',
      workerHeartbeatAt: '2026-04-23T09:59:00.000Z',
    },
    nowMs: Date.parse('2026-04-23T10:00:00.000Z'),
    isWorkerAlive: true,
    runningFailureReason: 'optimizer heartbeat timed out',
  });
  assert(staleOptimizer === 'optimizer heartbeat timed out', 'detached jobs fail when heartbeat expires');
}

if (failed > 0) {
  console.error(`\nCompute job invariants failed (${failed} failed, ${passed} passed)`);
  process.exit(1);
}

console.log(`\nCompute job invariants passed (${passed} checks)`);
