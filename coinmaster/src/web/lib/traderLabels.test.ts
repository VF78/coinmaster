import assert from 'node:assert/strict';
import test from 'node:test';
import { controlAvailabilityLabel, humanizeBlocker, humanizeResearchCode, isAdvancedStrategySetting, nativeFillActionLabel, unavailableTradeHistoryLabel, researchResultContext, strategyRunnerLabel, strategySettingLabel, strategySettingValue } from './traderLabels';

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


test('humanizes research evidence codes while retaining precise diagnostic labels', () => {
  assert.equal(humanizeResearchCode('NOT_FAITHFUL_DIAGNOSTIC'), 'Diagnostic evidence · not suitable for live ranking');
  assert.equal(humanizeResearchCode('VALIDATION_SEEN_NOT_OOS + NOT_FAITHFUL_DIAGNOSTIC'), 'Seen-data validation · not out-of-sample');
  assert.equal(humanizeResearchCode('ARTIFACT_NOT_LOCAL'), 'Artifact unavailable on this host');
  assert.equal(humanizeResearchCode('PUBLIC_FEEDS_READY'), 'Public market data ready');
});


test("presents the exact strategy match plainly and keeps run-selection copy consistent", () => {
  assert.equal(strategyRunnerLabel("RUNNING_MATCH"), "Match confirmed");
  assert.equal(strategyRunnerLabel("SEALED_SOURCE_CHECKED"), "Source checked · worker match unconfirmed");
  assert.equal(researchResultContext(null, "5226e711-abc"), "Selected run results are shown below.");
  assert.equal(researchResultContext("12345678-current", "5226e711-abc"), "Research is in progress; status refreshes automatically.");
  assert.equal(researchResultContext(null, null), "Choose a run from history to inspect its results.");
});


test('labels only exact native fill actions and leaves unknown classifications explicit', () => {
  assert.equal(nativeFillActionLabel('BTC_ENTRY'), 'Entry');
  assert.equal(nativeFillActionLabel('BTC_REDUCE'), 'TP');
  assert.equal(nativeFillActionLabel('SOL_HALF_EXIT'), 'Partial exit');
  assert.equal(nativeFillActionLabel('SOL_EXIT'), 'Exit');
  assert.equal(nativeFillActionLabel('TERMINAL_CLOSE'), 'Exit');
  assert.equal(nativeFillActionLabel('LIQUIDATION_CLOSE'), 'Liquidation');
  assert.equal(nativeFillActionLabel(null), 'Fill type unavailable');
  assert.equal(nativeFillActionLabel(undefined), 'Fill type unavailable');
  assert.equal(nativeFillActionLabel('FUTURE_ACTION'), 'Fill type unavailable');
});


test('does not turn a missing historical-fill count into zero', () => {
  assert.equal(unavailableTradeHistoryLabel(null), 'Detailed trade history is unavailable.');
  assert.equal(unavailableTradeHistoryLabel(undefined), 'Detailed trade history is unavailable.');
  assert.equal(unavailableTradeHistoryLabel(Number.NaN), 'Detailed trade history is unavailable.');
  assert.equal(unavailableTradeHistoryLabel(-1), 'Detailed trade history is unavailable.');
  assert.equal(unavailableTradeHistoryLabel(0), 'Detailed trade history is unavailable. 0 older executions have no saved details.');
  assert.equal(unavailableTradeHistoryLabel(2), 'Detailed trade history is unavailable. 2 older executions have no saved details.');
});
