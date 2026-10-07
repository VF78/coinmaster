import test from 'node:test';
import assert from 'node:assert/strict';
import { verifiedControlReadback } from './controlReadback';
import type { HlStagegProjection } from './nautilusApi';
const current = { run_epoch: 'current', projection_state: 'READY', recovery_required: false, entry_control: { state: 'RUNNING' } } as unknown as HlStagegProjection;
test('only fresh same-run native control state confirms success', () => {
  assert.equal(verifiedControlReadback(current, { ...current, entry_control: { state: 'PAUSED', capability: 'READY' } }, 'PAUSED'), true);
  assert.equal(verifiedControlReadback(current, null, 'PAUSED'), false);
  assert.equal(verifiedControlReadback(current, { ...current, run_epoch: 'replacement' }, 'RUNNING'), false);
  assert.equal(verifiedControlReadback(current, current, 'PAUSED'), false);
  assert.equal(verifiedControlReadback(current, { ...current, projection_state: 'STALE' }, 'RUNNING'), false);
  assert.equal(verifiedControlReadback(current, { ...current, recovery_required: true }, 'RUNNING'), false);
});
