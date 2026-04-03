import logger from '../lib/logger.js';
import { HyperliquidAdapter } from '../exchange/index.js';
import { executeOptimization } from './optimizerWorker.js';
import { getDb } from './db.js';

async function main() {
  const optimizationId = String(process.argv[2] ?? '').trim();
  if (!optimizationId) {
    throw new Error('optimization_id_required');
  }

  const db = await getDb();
  await db.reload();
  db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
  const opt = db.data.optimizationResults.find((item) => item.id === optimizationId);
  if (opt) {
    opt.status = opt.status === 'completed' ? opt.status : 'running';
    opt.startedAt = opt.startedAt || new Date().toISOString();
    opt.workerPid = process.pid;
    opt.workerHeartbeatAt = new Date().toISOString();
    await db.write();
  }
  const depositUsd = Number(db.data.settings?.depositUsd) || 1000;
  const exchange = new HyperliquidAdapter();

  logger.info({ component: 'optimizer-process', optimizationId, depositUsd }, 'optimization process started');
  await executeOptimization(optimizationId, exchange, depositUsd);
  logger.info({ component: 'optimizer-process', optimizationId }, 'optimization process finished');
}

main().catch((err) => {
  const message = err instanceof Error ? err.message : String(err);
  logger.error({ component: 'optimizer-process', err: message }, 'optimizer process failed');
  void (async () => {
    try {
      const optimizationId = String(process.argv[2] ?? '').trim();
      if (!optimizationId) return;
      const db = await getDb();
      db.data.optimizationResults = Array.isArray(db.data.optimizationResults) ? db.data.optimizationResults : [];
      const opt = db.data.optimizationResults.find((item) => item.id === optimizationId);
      if (opt && (opt.status === 'queued' || opt.status === 'running')) {
        opt.status = 'failed';
        opt.finishedAt = new Date().toISOString();
        opt.error = message;
        await db.write();
      }
    } catch {
      // best effort
    } finally {
      process.exitCode = 1;
    }
  })();
});
