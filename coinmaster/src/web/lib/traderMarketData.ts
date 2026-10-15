import type { CandlestickData, UTCTimestamp } from 'lightweight-charts';
import type { HlNativeEquityChanges, HlPublicCandle, HlStagegFillHistory, HlStagegProjection } from './nautilusApi';
import { nativeFillActionLabel } from './traderLabels';
import { TRADER_MARKETS } from './traderPresentation';

export type TraderCoin = 'BTC' | 'SOL';
export type TraderInterval = '1m' | '5m' | '15m' | '1h' | '4h' | '1d';
export type NativeOverlay = { price: number; title: string; color: string };
export type CandleBar = CandlestickData<UTCTimestamp>;
const finitePositive = (value: unknown): number | null => {
  const number = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
};

export function candleBars(rows: HlPublicCandle[]): CandleBar[] {
  const bars = rows.flatMap((row) => {
    const time = Math.floor(row.open_time_ms / 1000);
    const open = finitePositive(row.open), high = finitePositive(row.high);
    const low = finitePositive(row.low), close = finitePositive(row.close);
    if (!Number.isSafeInteger(time) || time <= 0 || open === null || high === null || low === null || close === null) return [];
    if (high < Math.max(open, close, low) || low > Math.min(open, close, high)) return [];
    return [{ time: time as UTCTimestamp, open, high, low, close }];
  });
  return [...new Map(bars.map((bar) => [bar.time, bar])).values()].sort((a, b) => Number(a.time) - Number(b.time));
}

export function nativeOverlays(
  projection: HlStagegProjection | null,
  history: HlStagegFillHistory | null,
  coin: TraderCoin,
  candleRows: HlPublicCandle[],
  candlesReady: boolean,
): { markers: Array<{ time: UTCTimestamp; position: 'aboveBar' | 'belowBar'; color: string; shape: 'arrowUp' | 'arrowDown'; text: string }>; lines: NativeOverlay[] } {
  const markers: Array<{ time: UTCTimestamp; position: 'aboveBar' | 'belowBar'; color: string; shape: 'arrowUp' | 'arrowDown'; text: string }> = [];
  const lines: NativeOverlay[] = [];
  if (!candlesReady || !projection || projection.projection_state !== 'READY' || projection.recovery_required || !projection.run_epoch) return { markers, lines };
  const market = TRADER_MARKETS.find((item) => item.symbol === coin)!;
  const position = projection.positions.find((item) => item.instrument_id === market.instrumentId);
  if (position && Number.isFinite(Number(position.signed_quantity)) && Number(position.signed_quantity) !== 0) {
    const price = finitePositive(position.average_entry_price);
    if (price !== null) lines.push({ price, title: `Native ${Number(position.signed_quantity) > 0 ? 'long' : 'short'} average entry`, color: '#5dd6b2' });
  }
  for (const order of projection.orders) {
    if (order.instrument_id !== market.instrumentId) continue;
    const price = finitePositive(order.price);
    const leaves = finitePositive(order.leaves_quantity ?? order.quantity);
    if (price === null) continue;
    const side = order.side ? ` ${order.side}` : '';
    const status = order.status ? ` · ${order.status}` : '';
    lines.push({ price, title: `Native order${side} · ${leaves ?? 'size unavailable'}${status}`, color: order.reduce_only ? '#e8aa65' : '#85a7ff' });
  }
  if (history?.run_epoch === projection.run_epoch) {
    const validBarTimes = new Set(candleBars(candleRows).map((bar) => Number(bar.time)));
    const ranges = candleRows.flatMap((row) => {
      const open = Math.floor(row.open_time_ms / 1000);
      const close = Math.floor(row.close_time_ms / 1000);
      return validBarTimes.has(open) && Number.isSafeInteger(close) && close >= open ? [{ open, close }] : [];
    });
    for (const fill of history.fills) {
      if (fill.instrument_id !== market.instrumentId || fill.ts_event_ns === null) continue;
      const price = finitePositive(fill.price);
      if (price === null || !Number.isFinite(fill.ts_event_ns) || fill.ts_event_ns <= 0) continue;
      const fillTime = Math.floor(fill.ts_event_ns / 1_000_000_000);
      const candle = ranges.find((range) => fillTime >= range.open && fillTime <= range.close);
      if (!candle) continue;
      const isBuy = fill.order_side?.toUpperCase() === 'BUY';
      const isSell = fill.order_side?.toUpperCase() === 'SELL';
      if (!isBuy && !isSell) continue;
      const action = fill.action ? nativeFillActionLabel(fill.action) : isBuy ? 'Buy' : 'Sell';
      markers.push({ time: candle.open as UTCTimestamp, position: isBuy ? 'belowBar' : 'aboveBar', color: isBuy ? '#50c99e' : '#ef7d80', shape: isBuy ? 'arrowUp' : 'arrowDown', text: `${action} ${fill.quantity} @ ${fill.price}` });
    }
  }
  markers.sort((a, b) => Number(a.time) - Number(b.time));
  return { markers, lines };
}

export function equityWindowRows(
  projection: HlStagegProjection | null,
  data: HlNativeEquityChanges | null,
  nowMs: number,
): Array<{ label: string; value: string; percent: string }> | null {
  if (!projection || projection.projection_state !== 'READY' || projection.recovery_required || !projection.run_epoch) return null;
  if (!data || data.instance_id !== projection.instance_id || data.source !== (projection.mode === 'live' ? 'NATIVE_LIVE_ACCOUNT' : 'NATIVE_SANDBOX_ACCOUNT') || data.state !== 'READY' || data.run_epoch !== projection.run_epoch) return null;
  if (data.as_of_ns === null || !Number.isFinite(data.as_of_ns)) return null;
  const asOfMs = data.as_of_ns / 1_000_000;
  if (asOfMs > nowMs + 5_000 || nowMs - asOfMs > 600_000) return null;
  const labels = [['24h', '24h'], ['7d', '7d'], ['30d', '30d']] as const;
  const rows: Array<{ label: string; value: string; percent: string }> = [];
  for (const [key, label] of labels) {
    const window = data.windows[key];
    const available = window?.state === 'AVAILABLE';
    const change = available && typeof window.change_usdc === 'string' && window.change_usdc.trim() !== '' ? Number(window.change_usdc) : Number.NaN;
    const percent = available && typeof window.change_percent === 'string' && window.change_percent.trim() !== '' ? Number(window.change_percent) : Number.NaN;
    rows.push({ label, value: Number.isFinite(change) ? `${change > 0 ? '+' : ''}${change.toFixed(2)} USDC` : '—', percent: Number.isFinite(percent) ? `${percent > 0 ? '+' : ''}${percent.toFixed(2)}%` : '—' });
  }
  return rows;
}
