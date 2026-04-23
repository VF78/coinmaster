import type { ComputeJobProgress, TradingRulesSettings, TradingRulesTimeframe } from '../shared/dto.js';

export type ComputeJobStatus = 'queued' | 'running' | 'completed' | 'failed';
export type ComputeJobKind = 'backtest' | 'optimization';

export interface ComputeJobRecord {
  status: ComputeJobStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  error?: string;
  workerPid?: number;
  workerHeartbeatAt?: string;
  progress?: ComputeJobProgress;
}

type MutableRecord = Record<string, unknown>;

function shouldTrackHeartbeat(job: ComputeJobRecord): boolean {
  const mutable = job as unknown as MutableRecord;
  return typeof job.workerPid === 'number'
    || typeof job.workerHeartbeatAt === 'string'
    || 'workerPid' in mutable
    || 'workerHeartbeatAt' in mutable;
}

export const CANDLE_TIMEFRAME_MS: Record<TradingRulesTimeframe, number> = {
  '5m': 5 * 60_000,
  '15m': 15 * 60_000,
  '1h': 60 * 60_000,
  '4h': 4 * 60 * 60_000,
};

export function createComputeJobProgress(
  completed: number,
  total: number,
  stage: string,
  updatedAt = new Date().toISOString(),
): ComputeJobProgress {
  const safeTotal = Math.max(0, Number.isFinite(total) ? total : 0);
  const safeCompleted = Math.min(safeTotal, Math.max(0, Number.isFinite(completed) ? completed : 0));
  const percent = safeTotal <= 0 ? 0 : Math.round((safeCompleted / safeTotal) * 10_000) / 100;
  return {
    completed: safeCompleted,
    total: safeTotal,
    percent,
    stage,
    updatedAt,
  };
}

export function markComputeJobStarted<T extends ComputeJobRecord>(
  job: T,
  options: {
    now?: string;
    workerPid?: number;
    stage?: string;
    total?: number;
    completed?: number;
  } = {},
): T {
  const now = options.now ?? new Date().toISOString();
  job.status = 'running';
  job.startedAt = job.startedAt ?? now;
  job.finishedAt = undefined;
  job.error = undefined;
  if (options.workerPid !== undefined) {
    job.workerPid = options.workerPid;
  }
  if (shouldTrackHeartbeat(job)) {
    job.workerHeartbeatAt = now;
  }
  if (options.stage) {
    job.progress = createComputeJobProgress(options.completed ?? 0, options.total ?? 0, options.stage, now);
  }
  return job;
}

export function updateComputeJobProgress<T extends ComputeJobRecord>(
  job: T,
  options: {
    completed: number;
    total: number;
    stage: string;
    now?: string;
    heartbeat?: boolean;
  },
): T {
  const now = options.now ?? new Date().toISOString();
  job.progress = createComputeJobProgress(options.completed, options.total, options.stage, now);
  if (options.heartbeat !== false && shouldTrackHeartbeat(job)) {
    job.workerHeartbeatAt = now;
  }
  return job;
}

export function claimComputeJobForProcess<T extends ComputeJobRecord>(
  job: T,
  options: {
    now?: string;
    workerPid?: number;
  } = {},
): T {
  const now = options.now ?? new Date().toISOString();
  job.workerPid = options.workerPid ?? process.pid;
  return updateComputeJobProgress(job, {
    completed: job.progress?.completed ?? 0,
    total: job.progress?.total ?? 0,
    stage: job.progress?.stage ?? 'queued',
    now,
  });
}

export function markComputeJobCompleted<T extends ComputeJobRecord>(
  job: T,
  options: {
    now?: string;
    stage?: string;
    total?: number;
  } = {},
): T {
  const now = options.now ?? new Date().toISOString();
  job.status = 'completed';
  job.finishedAt = now;
  job.error = undefined;
  if (options.stage) {
    const total = Math.max(0, options.total ?? job.progress?.total ?? 0);
    job.progress = createComputeJobProgress(total, total, options.stage, now);
  }
  if (shouldTrackHeartbeat(job)) {
    job.workerHeartbeatAt = now;
  }
  return job;
}

export function markComputeJobFailed<T extends ComputeJobRecord>(
  job: T,
  error: string,
  options: {
    now?: string;
    stage?: string;
  } = {},
): T {
  const now = options.now ?? new Date().toISOString();
  job.status = 'failed';
  job.finishedAt = now;
  job.error = error;
  if (options.stage) {
    const completed = job.progress?.completed ?? 0;
    const total = job.progress?.total ?? 0;
    job.progress = createComputeJobProgress(completed, total, options.stage, now);
  }
  if (shouldTrackHeartbeat(job)) {
    job.workerHeartbeatAt = now;
  }
  return job;
}

export function getRequiredComputeTimeframes(rules: TradingRulesSettings): TradingRulesTimeframe[] {
  const required = new Set<TradingRulesTimeframe>();
  for (const tf of rules.entryTimeframes ?? ['15m']) {
    required.add(tf);
  }
  for (const tf of rules.emergencyExitTimeframes ?? ['1h']) {
    required.add(tf);
  }
  required.add('1h');
  required.add('4h');
  if (rules.fvgRequireConfirmation) {
    for (const tf of rules.fvgConfirmationTimeframes ?? []) {
      required.add(tf);
    }
  }
  return [...required];
}

export function computeCandleLoadWindow(params: {
  timeframe: TradingRulesTimeframe;
  startTimeMs: number;
  endTimeMs: number;
  extraPaddingCandles?: number;
}): { startTimeMs: number; endTimeMs: number } {
  const paddingCandles = Math.max(0, params.extraPaddingCandles ?? 50);
  const tfMs = CANDLE_TIMEFRAME_MS[params.timeframe] ?? CANDLE_TIMEFRAME_MS['15m'];
  return {
    startTimeMs: params.startTimeMs - (tfMs * paddingCandles),
    endTimeMs: params.endTimeMs,
  };
}

export function shouldPersistProgress(params: {
  completed: number;
  total: number;
  forceEvery?: number;
}): boolean {
  const completed = Math.max(0, params.completed);
  const total = Math.max(0, params.total);
  if (completed <= 0 || total <= 0) return false;
  if (completed >= total) return true;
  if (total <= 25) return true;
  if (total <= 100) return completed % 5 === 0;
  return completed % Math.max(10, params.forceEvery ?? 25) === 0;
}

export function reconcileComputeJob(params: {
  job: ComputeJobRecord;
  nowMs?: number;
  queuedTimeoutMs?: number;
  heartbeatTimeoutMs?: number;
  isLocallyActive?: boolean;
  isWorkerAlive?: boolean;
  queuedFailureReason?: string;
  runningFailureReason?: string;
  missingWorkerReason?: string;
}): string | null {
  const nowMs = params.nowMs ?? Date.now();
  const queuedTimeoutMs = params.queuedTimeoutMs ?? 30_000;
  const heartbeatTimeoutMs = params.heartbeatTimeoutMs ?? 30_000;
  const createdMs = Date.parse(params.job.createdAt);
  const startedMs = params.job.startedAt ? Date.parse(params.job.startedAt) : 0;
  const heartbeatMs = params.job.workerHeartbeatAt ? Date.parse(params.job.workerHeartbeatAt) : 0;

  if (params.job.status === 'queued') {
    const queuedSinceMs = startedMs > 0 ? startedMs : createdMs;
    if (!Number.isFinite(queuedSinceMs) || queuedSinceMs <= 0) return null;
    if (params.isLocallyActive === true || params.isWorkerAlive === true) return null;
    if (nowMs - queuedSinceMs > queuedTimeoutMs) {
      return params.queuedFailureReason ?? 'compute job did not start';
    }
    return null;
  }

  if (params.job.status !== 'running') {
    return null;
  }

  if (params.isLocallyActive === false) {
    return params.runningFailureReason ?? 'compute job is not active';
  }
  if (params.isWorkerAlive === false) {
    return params.missingWorkerReason ?? 'compute job worker exited unexpectedly';
  }
  if (heartbeatMs > 0 && nowMs - heartbeatMs > heartbeatTimeoutMs) {
    return params.runningFailureReason ?? 'compute job heartbeat timed out';
  }
  return null;
}
