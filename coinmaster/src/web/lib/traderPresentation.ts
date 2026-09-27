import type { HlStagegProjection } from './nautilusApi';

export const TRADER_MARKETS = [
  { symbol: 'BTC', instrumentId: 'BTC-USD-PERP.HYPERLIQUID' },
  { symbol: 'SOL', instrumentId: 'SOL-USD-PERP.HYPERLIQUID' },
] as const;

export type MarkSample = { observedAtNs: number; mark: number };
export type PositionPresentation =
  | { state: 'OPEN'; side: 'LONG' | 'SHORT'; quantity: string }
  | { state: 'FLAT'; side: null; quantity: '0' }
  | { state: 'UNKNOWN'; side: null; quantity: null };

export function positionPresentation(
  projection: HlStagegProjection | null,
  instrumentId: string,
): PositionPresentation {
  const position = projection?.positions.find((item) => item.instrument_id === instrumentId);
  if (position) {
    const quantity = Number(position.signed_quantity);
    if (!Number.isFinite(quantity) || quantity === 0) return { state: 'UNKNOWN', side: null, quantity: null };
    return {
      state: 'OPEN',
      side: quantity > 0 ? 'LONG' : 'SHORT',
      quantity: position.signed_quantity,
    };
  }
  if (
    projection?.projection_state === 'READY'
    && projection.recovery_required !== true
    && projection.positions.length === 0
    && projection.orders.length === 0
  ) return { state: 'FLAT', side: null, quantity: '0' };
  return { state: 'UNKNOWN', side: null, quantity: null };
}

export function appendSessionMarkSample(
  samples: MarkSample[],
  projection: HlStagegProjection | null,
  instrumentId: string,
  capacity = 72,
): MarkSample[] {
  const feed = projection?.feeds[instrumentId];
  const mark = Number(feed?.mark);
  const observedAtNs = projection?.observed_at_ns;
  if (
    !projection
    || projection.projection_state !== 'READY'
    || feed?.state !== 'READY'
    || !Number.isFinite(mark)
    || mark <= 0
    || feed.mark_age_ns == null
    || feed.mark_age_ns < 0
    || feed.mark_age_ns > 15_000_000_000
  ) return [];
  if (observedAtNs == null || !Number.isFinite(observedAtNs) || observedAtNs <= 0) return samples;
  if (samples.at(-1)?.observedAtNs === observedAtNs) return samples;
  return [...samples, { observedAtNs, mark }].slice(-Math.max(2, capacity));
}

export function markSparklinePath(samples: MarkSample[], width = 240, height = 52): string {
  if (samples.length < 2) return '';
  const values = samples.map((sample) => sample.mark);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const spread = high - low || Math.max(high * 0.001, Number.EPSILON);
  const inset = 2;
  return samples.map((sample, index) => {
    const x = (index / (samples.length - 1)) * width;
    const y = height - inset - ((sample.mark - low) / spread) * (height - inset * 2);
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}
