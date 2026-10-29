import test from 'node:test';
import assert from 'node:assert/strict';
import { effectiveLeverage, researchMetric, traderMoney, traderPercent, nativeMarketLabel, nativeExecutionSubtitle } from './traderFormatting';
import type { HlStagegProjection } from './nautilusApi';
test('currency formatting preserves unavailable and correctly rounds exact native inputs', () => {
  assert.equal(traderMoney('11319.40534863', 'USDC'), '11,319.41 USDC');
  assert.equal(traderMoney('0', 'USDC'), '0.00 USDC');
  for (const value of [null, undefined, '', 'UNKNOWN', 'NaN', Infinity]) assert.equal(traderMoney(value), 'Unavailable');
  assert.equal(traderPercent('0E-8'), '0.00%');
  assert.equal(traderPercent('0.785710665'), '78.57%');
});
test('effective leverage requires a fresh native mark for every held market', () => {
  const flat = { projection_state: 'READY', recovery_required: false, money_currency: 'USDC', account: { currency: 'USDC', money_currency: 'USDC', equity: '10000', mark_state: 'CURRENT' }, positions: [], feeds: {} } as unknown as HlStagegProjection;
  assert.equal(effectiveLeverage(flat), '0.00×');
  const open = { ...flat, positions: [{ instrument_id: 'BTC', signed_quantity: '-0.25' }], feeds: { BTC: { mark: '80000', state: 'READY', mark_age_ns: 0 } } } as unknown as HlStagegProjection;
  assert.equal(effectiveLeverage(open), '2.00×');
  assert.equal(effectiveLeverage({ ...open, recovery_required: true }), 'Unavailable');
  assert.equal(effectiveLeverage({ ...open, feeds: {} }), 'Unavailable');
  assert.equal(effectiveLeverage({ ...flat, account: { ...flat.account, equity: null } }), 'Unavailable');
});
test('research metric accepts native nested and flat reports without zero fallback', () => {
  assert.equal(researchMetric({ summary: { roi: '0E-8' }, roi: '10' }, 'roi'), '0E-8');
  assert.equal(researchMetric({ native_fees: '2.34' }, 'native_fees'), '2.34');
  assert.equal(researchMetric({}, 'funding'), undefined);
});

test('requires explicit units and never relabels foreign native money', () => {
  assert.equal(traderMoney('10'), 'Unavailable');
  assert.equal(traderMoney('10', 'USD'), 'Unavailable');
  assert.equal(traderMoney('10', 'USDT'), '10.00 USDT');
});

test('mobile execution text and market units fail closed on unverified currency', () => {
  const fill = { order_side: 'BUY', quantity: '0.1', price: '123456' };
  assert.equal(nativeExecutionSubtitle(fill, null), 'BUY · 0.1 @ Unavailable');
  assert.equal(nativeMarketLabel('BTC-USD-PERP.HYPERLIQUID', null), 'BTC · currency unverified');
  assert.equal(nativeMarketLabel('BTC-USD-PERP.HYPERLIQUID', 'USDC'), 'BTC/USDC');
  assert.equal(nativeMarketLabel('BTC-USD-PERP.BYBIT', 'USDC'), 'Other market');
});
