import type { HlStagegProjection } from './nautilusApi';
export function verifiedControlReadback(before: HlStagegProjection | null, fresh: HlStagegProjection | null, expectedEntry?: 'RUNNING' | 'PAUSED'): boolean {
  if (!before?.run_epoch || !fresh || fresh.run_epoch !== before.run_epoch || fresh.projection_state !== 'READY' || fresh.recovery_required === true) return false;
  return expectedEntry === undefined || fresh.entry_control.state === expectedEntry;
}
