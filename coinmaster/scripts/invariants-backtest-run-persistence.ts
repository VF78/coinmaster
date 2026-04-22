import { mutateBacktestRun, requireBacktestRun } from '../src/core/backtestWorker.js';
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
    status: 'queued',
    symbol: 'BTC',
    biasMode: 'both',
    createdAt: '2026-04-22T00:00:00.000Z',
    startTimeMs: 1_000,
    endTimeMs: 2_000,
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
      fvgRequireConfirmation: false,
      maxZoneAgeCandles: 12,
      fvgConfirmationTimeframes: ['15m'],
      maxLeverage: 5,
      dailyDrawdown: 5,
      tpPct: 2,
      tpLevels: [3],
      slPct: 1,
      exitClosePct: 50,
      autoConfirm: false,
    },
    bySymbol: [],
    aiAnalysis: { status: 'idle' },
    ...overrides,
  };
}

console.log('\n── Backtest Run Persistence Invariant ──');
{
  const originalRun = createRun();
  const db = {
    data: {
      backtestRuns: [originalRun],
    },
  } as {
    data: {
      backtestRuns: BacktestRun[];
    };
  };

  const staleReference = requireBacktestRun('run-1', db.data.backtestRuns);
  staleReference.status = 'running';

  db.data = {
    backtestRuns: [
      createRun({
        id: 'run-1',
        status: 'running',
        startedAt: '2026-04-22T00:01:00.000Z',
      }),
    ],
  };

  staleReference.status = 'completed';
  staleReference.finishedAt = '2026-04-22T00:02:00.000Z';

  assert(db.data.backtestRuns[0]?.status === 'running', 'reloading snapshot breaks stale object references');

  mutateBacktestRun(db as never, 'run-1', (run) => {
    run.status = 'completed';
    run.finishedAt = '2026-04-22T00:02:00.000Z';
    run.summary = {
      totalTrades: 3,
      winRatePct: 66.67,
      realizedPnlUsd: 12,
      openPnlUsd: 0,
      netPnlUsd: 12,
      roiPct: 1.2,
      maxDrawdownPct: 0.8,
    };
  });

  assert(db.data.backtestRuns[0]?.status === 'completed', 'mutateBacktestRun updates the latest snapshot after reload');
  assert(Boolean(db.data.backtestRuns[0]?.summary), 'result fields land on the latest persisted run object');
}

if (failed > 0) {
  console.error(`\nBacktest run persistence invariant failed (${failed} failed, ${passed} passed)`);
  process.exit(1);
}

console.log(`\nBacktest run persistence invariant passed (${passed} checks)`);
