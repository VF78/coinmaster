import assert from 'node:assert/strict';
import test from 'node:test';
import type { HlNativeEquityChanges, HlPublicCandle, HlStagegFillHistory, HlStagegProjection } from './nautilusApi';
import { candleBars, equityWindowRows, nativeOverlays } from './traderMarketData';

const projection = (patch: Record<string, unknown> = {}) => ({ projection_state: 'READY', recovery_required: false, run_epoch: 'epoch-a', positions: [], orders: [], ...patch }) as unknown as HlStagegProjection;
const candle = (patch: Partial<HlPublicCandle> = {}) => ({ open_time_ms: 1_700_000_000_000, close_time_ms: 1_700_000_059_999, open: '10', high: '12', low: '9', close: '11', volume: '3', trades: 2, ...patch });
const history = (patch: Record<string, unknown> = {}) => ({ run_epoch: 'epoch-a', fills: [], ...patch }) as unknown as HlStagegFillHistory;

test('maps only valid unique official candles to ordered chart bars', () => {
  const bars = candleBars([candle(), candle({ open_time_ms: 1_700_000_000_000, close: '10.5' }), candle({ open_time_ms: 1_700_000_060_000, low: '13' })]);
  assert.equal(bars.length, 1);
  assert.equal(bars[0].close, 10.5);
});

test('native overlays require ready current epoch and preserve exact partial fill actions', () => {
  const state = projection({ positions: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', signed_quantity: '0.2', average_entry_price: '101' }], orders: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', client_order_id: 'tp-1', side: 'SELL', price: '110', leaves_quantity: '0.1', quantity: '0.2', status: 'ACCEPTED', reduce_only: true }] });
  const fills = history({ fills: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', order_side: 'SELL', action: 'TP_PARTIAL', quantity: '0.1', price: '110', ts_event_ns: 1_700_000_000_000_000_000 }] });
  const overlays = nativeOverlays(state, fills, 'BTC', true);
  assert.equal(overlays.lines.length, 2);
  assert.equal(overlays.lines[0].price, 101);
  assert.match(overlays.lines[1].title, /0\.1/);
  assert.equal(overlays.markers[0].text, 'TP_PARTIAL 0.1 @ 110');
  assert.deepEqual(nativeOverlays(null, fills, 'BTC', true), { markers: [], lines: [] });
  assert.deepEqual(nativeOverlays(projection({ projection_state: 'STALE' }), fills, 'BTC', true), { markers: [], lines: [] });
  assert.deepEqual(nativeOverlays(state, history({ run_epoch: 'epoch-old' }), 'BTC', false), { markers: [], lines: [] });
  assert.deepEqual(nativeOverlays(state, history({ run_epoch: 'epoch-old' }), 'BTC', true), { markers: [], lines: [] });
  assert.deepEqual(nativeOverlays(state, null, 'BTC', true), { markers: [], lines: [] });
});

test('flat and null native prices do not create execution overlays', () => {
  const state = projection({ orders: [{ instrument_id: 'BTC-USD-PERP.HYPERLIQUID', client_order_id: 'unknown-price', price: null, leaves_quantity: null }] });
  assert.deepEqual(nativeOverlays(state, null, 'BTC', true), { markers: [], lines: [] });
  assert.deepEqual(nativeOverlays(projection(), history(), 'BTC', true), { markers: [], lines: [] });
});

test('equity changes require ready matching epoch and recent as-of', () => {
  const now = 1_700_000_000_000;
  const equity = (patch: Record<string, unknown> = {}) => ({ instance_id: 'hl-stageg-testnet', source: 'NATIVE_SANDBOX_ACCOUNT', state: 'READY', run_epoch: 'epoch-a', as_of_ns: now * 1_000_000, windows: { '24h': { state: 'AVAILABLE', change_usdc: '2' }, '7d': { state: 'AVAILABLE', change_usdc: '-1' }, '30d': { state: 'AVAILABLE', change_usdc: '0' } }, ...patch }) as unknown as HlNativeEquityChanges;
  assert.deepEqual(equityWindowRows(projection(), equity(), now), [{ label: '24h', value: '+2.00 USDC' }, { label: '7d', value: '-1.00 USDC' }, { label: '30d', value: '0.00 USDC' }]);
  assert.equal(equityWindowRows(projection(), equity({ run_epoch: 'epoch-b' }), now), null);
  assert.equal(equityWindowRows(projection(), equity({ state: 'STALE' }), now), null);
  assert.equal(equityWindowRows(projection(), equity({ windows: { '24h': { state: 'AVAILABLE', change_usdc: null }, '7d': { state: 'AVAILABLE', change_usdc: '1' }, '30d': { state: 'AVAILABLE', change_usdc: '2' } } }), now), null);
  assert.equal(equityWindowRows(projection(), equity({ as_of_ns: (now - 601_000) * 1_000_000 }), now), null);
  assert.equal(equityWindowRows(projection({ projection_state: 'UNAVAILABLE' }), equity(), now), null);
  assert.equal(equityWindowRows(projection(), equity({ windows: { '24h': { state: 'UNAVAILABLE' }, '7d': { state: 'AVAILABLE', change_usdc: '1' }, '30d': { state: 'AVAILABLE', change_usdc: '2' } } }), now), null);
});
