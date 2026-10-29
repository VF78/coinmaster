import assert from 'node:assert/strict';
import test from 'node:test';
import type { HlNativeEquityChanges, HlPublicCandle, HlStagegFillHistory, HlStagegProjection } from './nautilusApi';
import { candleBars, equityWindowRows, nativeOverlays } from './traderMarketData';

const projection = (patch: Record<string, unknown> = {}) => ({ instance_id: 'hl-stageg-testnet', mode: 'sandbox', money_currency: 'USDC', account: { currency: 'USDC', money_currency: 'USDC' }, projection_state: 'READY', recovery_required: false, run_epoch: 'epoch-a', positions: [], orders: [], ...patch }) as unknown as HlStagegProjection;
const candle = (patch: Partial<HlPublicCandle> = {}) => ({ open_time_ms: 1_700_000_000_000, close_time_ms: 1_700_000_059_999, open: '10', high: '12', low: '9', close: '11', volume: '3', trades: 2, ...patch });
const history = (patch: Record<string, unknown> = {}) => ({ run_epoch: 'epoch-a', fills: [], ...patch }) as unknown as HlStagegFillHistory;

test('maps only valid unique official candles to ordered chart bars', () => {
  const bars = candleBars([candle(), candle({ open_time_ms: 1_700_000_000_000, close: '10.5' }), candle({ open_time_ms: 1_700_000_060_000, low: '13' })]);
  assert.equal(bars.length, 1);
  assert.equal(bars[0].close, 10.5);
});

test('native overlays require ready current epoch and preserve exact partial fill actions', () => {
  const state = projection({ positions: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', signed_quantity: '0.2', average_entry_price: '101' }], orders: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', client_order_id: 'tp-1', side: 'SELL', price: '110', leaves_quantity: '0.1', quantity: '0.2', status: 'ACCEPTED', reduce_only: true }] });
  const fills = history({ fills: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', order_side: 'SELL', action: 'TP_PARTIAL', quantity: '0.1', price: '110', ts_event_ns: 1_700_000_000_500_000_000 }] });
  const bar = candle({ open_time_ms: 1_700_000_000_000, close_time_ms: 1_700_000_899_999 });
  const overlays = nativeOverlays(state, fills, 'BTC', [bar], true);
  assert.equal(overlays.lines.length, 2);
  assert.equal(overlays.lines[0].price, 101);
  assert.match(overlays.lines[1].title, /0\.1/);
  assert.equal(overlays.markers[0].text, 'Partial TP 0.1 BTC @ 110 USDC');
  assert.equal(overlays.markers[0].time, 1_700_000_000);
  assert.deepEqual(nativeOverlays(state, null, 'BTC', [bar], true).lines, overlays.lines, 'position and order levels do not depend on fill history');
  assert.equal(nativeOverlays(state, fills, 'BTC', [candle({ open_time_ms: 1_700_000_900_000, close_time_ms: 1_700_004_499_999 })], true).markers.length, 0, 'fills outside loaded candles are discarded');
  assert.deepEqual(nativeOverlays(null, fills, 'BTC', [bar], true), { markers: [], lines: [] });
  assert.deepEqual(nativeOverlays(projection({ projection_state: 'STALE' }), fills, 'BTC', [bar], true), { markers: [], lines: [] });
  assert.deepEqual(nativeOverlays(state, history({ run_epoch: 'epoch-old' }), 'BTC', [], false), { markers: [], lines: [] });
  const mismatched = nativeOverlays(state, history({ run_epoch: 'epoch-old' }), 'BTC', [bar], true);
  assert.equal(mismatched.markers.length, 0);
  assert.equal(mismatched.lines.length, 2, 'ready position and order levels survive fill-history epoch mismatch');
  assert.equal(nativeOverlays(state, null, 'BTC', [bar], true).lines.length, 2, 'ready position and order levels remain visible without fills');
});


test('partial TP fill markers attach to returned 15m and 1h candle opens', () => {
  const state = projection();
  for (const durationSec of [900, 3600]) {
    const openSec = 1_700_000_000;
    const row = candle({ open_time_ms: openSec * 1000, close_time_ms: (openSec + durationSec) * 1000 - 1 });
    const fills = history({ fills: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', order_side: 'SELL', action: 'TP_PARTIAL', quantity: '0.05', price: '110', ts_event_ns: (openSec + 420) * 1_000_000_000 }] });
    const marker = nativeOverlays(state, fills, 'BTC', [row], true).markers[0];
    assert.equal(marker?.time, openSec);
    assert.equal(marker?.text, 'Partial TP 0.05 BTC @ 110 USDC');
  }
});

test('flat and null native prices do not create execution overlays', () => {
  const state = projection({ orders: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', client_order_id: 'unknown-price', price: null, leaves_quantity: null }] });
  assert.equal(nativeOverlays(state, null, 'BTC', [], true).lines.length, 0);
  assert.deepEqual(nativeOverlays(projection(), history(), 'BTC', [], true), { markers: [], lines: [] });
});

test('equity changes require ready matching epoch and recent as-of', () => {
  const now = 1_700_000_000_000;
  const equity = (patch: Record<string, unknown> = {}) => ({ instance_id: 'hl-stageg-testnet', source: 'NATIVE_SANDBOX_ACCOUNT', state: 'READY', run_epoch: 'epoch-a', as_of_ns: now * 1_000_000, windows: { '24h': { state: 'AVAILABLE', change_usdc: '2', change_percent: '1.25' }, '7d': { state: 'AVAILABLE', change_usdc: '-1', change_percent: '-0.5' }, '30d': { state: 'AVAILABLE', change_usdc: '0', change_percent: '0' } }, ...patch }) as unknown as HlNativeEquityChanges;
  assert.deepEqual(equityWindowRows(projection(), equity(), now), [{ label: '24h', value: '+2.00 USDC', percent: '+1.25%' }, { label: '7d', value: '-1.00 USDC', percent: '-0.50%' }, { label: '30d', value: '0.00 USDC', percent: '0.00%' }]);
  assert.equal(equityWindowRows(projection(), equity({ run_epoch: 'epoch-b' }), now), null);
  assert.equal(equityWindowRows(projection(), equity({ state: 'STALE' }), now), null);
  assert.deepEqual(equityWindowRows(projection(), equity({ windows: { '24h': { state: 'AVAILABLE', change_usdc: null }, '7d': { state: 'AVAILABLE', change_usdc: '1' }, '30d': { state: 'AVAILABLE', change_usdc: '2' } } }), now), [{ label: '24h', value: '—', percent: '—' }, { label: '7d', value: '+1.00 USDC', percent: '—' }, { label: '30d', value: '+2.00 USDC', percent: '—' }]);
  assert.equal(equityWindowRows(projection(), equity({ as_of_ns: (now - 601_000) * 1_000_000 }), now), null);
  assert.equal(equityWindowRows(projection({ projection_state: 'UNAVAILABLE' }), equity(), now), null);
  assert.deepEqual(equityWindowRows(projection(), equity({ windows: { '24h': { state: 'AVAILABLE', change_usdc: '2' }, '7d': { state: 'UNAVAILABLE' }, '30d': { state: 'UNAVAILABLE' } } }), now), [{ label: '24h', value: '+2.00 USDC', percent: '—' }, { label: '7d', value: '—', percent: '—' }, { label: '30d', value: '—', percent: '—' }]);
});

test('chart marker labels never infer TP from a generic native reduction', () => {
  for (const [action, label] of [['BTC_ENTRY', 'Entry'], ['BTC_REDUCE', 'Exit'], ['TP_PARTIAL', 'Partial TP']]) {
    const fills = history({ fills: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', order_side: 'SELL', action, quantity: '0.1', price: '110', ts_event_ns: 1_700_000_000_500_000_000 }] });
    assert.equal(nativeOverlays(projection(), fills, 'BTC', [candle()], true).markers[0].text, label + ' 0.1 BTC @ 110 USDC');
  }
});

test('currency-unverified projection cannot produce USDC overlays or equity windows', () => {
  const state = projection({ money_currency: 'USD' });
  assert.deepEqual(nativeOverlays(state, history(), 'BTC', [candle()], true), { markers: [], lines: [] });
  assert.equal(equityWindowRows(state, null, Date.now()), null);
});
