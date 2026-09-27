import assert from 'node:assert/strict';
import test from 'node:test';
import { controlAvailabilityLabel, humanizeBlocker, isAdvancedStrategySetting, strategySettingLabel, strategySettingValue } from './traderLabels';

test('humanizes exact strategy keys and values without altering data', () => {
  assert.equal(strategySettingLabel('sol_timeout_preempts_add'), 'SOL timeout stops further additions');
  assert.equal(strategySettingLabel('episode_fixed_beta'), 'Keep beta fixed during each episode');
  assert.equal(strategySettingValue('max_parent_notional', 10000000.0), '10,000,000');
  assert.equal(strategySettingValue('sol_overlay_enabled', false), 'Disabled');
  assert.equal(isAdvancedStrategySetting('sol_overlay_enabled'), true);
});

test('humanizes blockers and separates control availability from recovery status', () => {
  assert.equal(humanizeBlocker('MISSING_1M_MANIFEST'), 'Verified 1-minute market data is not available.');
  assert.equal(humanizeBlocker('NO_IDEMPOTENT_NATIVE_FLATTEN_RECOVERY'), 'Flattening is unavailable until native crash-safe recovery is supported.');
  assert.equal(controlAvailabilityLabel(true, false), 'Pause / resume available');
  assert.equal(controlAvailabilityLabel(true, true), 'Unavailable · recovery required');
});
