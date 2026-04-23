import logger from '../lib/logger.js';
import { HyperliquidAdapter } from '../exchange/index.js';
import { executeBacktestRun } from './backtestWorker.js';
import { claimComputeJobForProcess, markComputeJobFailed, type ComputeJobKind } from './computeJob.js';
import { getDb } from './db.js';
import { executeOptimization } from './optimizerWorker.js';

function parseComputeJobKind(value: string): ComputeJobKind {
  if (value === 'backtest' || value === 'optimization') {
    return value;
  }
  throw new Error(`invalid_compute_job_kind:${value || 'missing'}`);
}

async function main() {
  const kind = parseComputeJobKind(String(process.argv[2] ?? '').trim());
  const jobId = String(process.argv[3] ?? '').trim();
  if (!jobId) {
    throw new Error('compute_job_id_required');
  }

  const db = await getDb();
  await db.reload();
  const depositUsd = Number(db.data.settings?.depositUsd) || 1000;
  const exchange = new HyperliquidAdapter();

  if (kind === 'backtest') {
    db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
    const run = db.data.backtestRuns.find((item) => item.id === jobId);
    if (!run) {
      throw new Error(`backtest_run_not_found:${jobId}`);
    }
    if (run.status === 'queued') {
      claimComputeJobForProcess(run, { workerPid: process.pid });
      await db.write();
    }
    logger.info({ component: 'compute-job-process', kind, jobId, depositUsd }, 'compute job process started');
    await executeBacktestRun(jobId, exchange, depositUsd);
    logger.info({ component: 'compute-job-process', kind, jobId }, 'compute job process finished');
    return;
  }

  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  const opt = db.data.optimizationResults.find((item) => item.id === jobId);
  if (!opt) {
    throw new Error(`optimization_not_found:${jobId}`);
  }
  if (opt.status === 'queued') {
    claimComputeJobForProcess(opt, { workerPid: process.pid });
    await db.write();
  }
  logger.info({ component: 'compute-job-process', kind, jobId, depositUsd }, 'compute job process started');
  await executeOptimization(jobId, exchange, depositUsd);
  logger.info({ component: 'compute-job-process', kind, jobId }, 'compute job process finished');
}

main().catch((err) => {
  const kindRaw = String(process.argv[2] ?? '').trim();
  const jobId = String(process.argv[3] ?? '').trim();
  const message = err instanceof Error ? err.message : String(err);
  logger.error({ component: 'compute-job-process', kind: kindRaw, jobId, err: message }, 'compute job process failed');
  void (async () => {
    try {
      const kind = parseComputeJobKind(kindRaw);
      if (!jobId) return;
      const db = await getDb();
      await db.reload();
      if (kind === 'backtest') {
        db.data.backtestRuns = Array.isArray(db.data.backtestRuns) ? db.data.backtestRuns : [];
        const run = db.data.backtestRuns.find((item) => item.id === jobId);
        if (run && (run.status === 'queued' || run.status === 'running')) {
          markComputeJobFailed(run, message, { stage: 'failed' });
          await db.write();
        }
        return;
      }

      db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
      const opt = db.data.optimizationResults.find((item) => item.id === jobId);
      if (opt && (opt.status === 'queued' || opt.status === 'running')) {
        markComputeJobFailed(opt, message, { stage: 'failed' });
        await db.write();
      }
    } catch {
      // best effort
    } finally {
      process.exitCode = 1;
    }
  })();
});
