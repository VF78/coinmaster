import type { HlStagegProjection } from './nautilusApi';

export const TRADER_MARKETS = [
  { symbol: 'BTC', instrumentId: 'BTC-USD-PERP.HYPERLIQUID' },
  { symbol: 'SOL', instrumentId: 'SOL-USD-PERP.HYPERLIQUID' },
] as const;

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
