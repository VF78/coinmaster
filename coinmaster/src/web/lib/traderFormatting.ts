import type { HlStagegProjection } from './nautilusApi';
export function traderNumber(value: unknown, decimals = 2): string {
  if ((typeof value !== 'string' && typeof value !== 'number') || String(value).trim() === '') return 'Unavailable';
  const number = Number(value);
  if (!Number.isFinite(number)) return 'Unavailable';
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(number);
}
export function traderMoney(value: unknown, currency?: string | null): string {
  if (currency !== 'USDC' && currency !== 'USDT') return 'Unavailable';
  const display = traderNumber(value);
  return display === 'Unavailable' ? display : display + ' ' + currency;
}
export function traderPercent(value: unknown): string {
  const number = (typeof value === 'string' || typeof value === 'number') && String(value).trim() !== '' ? Number(value) : NaN;
  return Number.isFinite(number) ? traderNumber(number * 100) + '%' : 'Unavailable';
}
export function projectionCurrency(state: HlStagegProjection | null): 'USDC' | null {
  return state?.money_currency === 'USDC' && state.account.currency === 'USDC' && state.account.money_currency === 'USDC'
    && (state.mode !== 'live' || (state.equity_basis === 'HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1' && state.account.equity_basis === state.equity_basis)) ? 'USDC' : null;
}
export function nativeMoney(value: unknown, currency: unknown): string {
  return currency === 'USDC' ? traderMoney(value, 'USDC') : 'Unavailable';
}
// Informational gross exposure/equity ratio; no account or PnL model.
export function effectiveLeverage(state: HlStagegProjection | null): string {
  if (!state || !projectionCurrency(state) || state.projection_state !== 'READY' || state.recovery_required || state.account.mark_state !== 'CURRENT') return 'Unavailable';
  const equity = Number(state.account.equity);
  if (state.account.equity == null || !Number.isFinite(equity) || equity <= 0) return 'Unavailable';
  let gross = 0;
  for (const position of state.positions) {
    const feed = state.feeds[position.instrument_id];
    const quantity = Number(position.signed_quantity), mark = Number(feed?.mark);
    if (!feed || feed.state !== 'READY' || feed.mark == null || feed.mark_age_ns == null || feed.mark_age_ns < 0 || feed.mark_age_ns > 15_000_000_000 || !Number.isFinite(quantity) || !Number.isFinite(mark) || mark <= 0) return 'Unavailable';
    gross += Math.abs(quantity) * mark;
  }
  return traderNumber(gross / equity) + '×';
}
export function researchMetric(report: Record<string, unknown> | null | undefined, field: string): unknown {
  const summary = report?.summary;
  if (summary && typeof summary === 'object' && !Array.isArray(summary)) {
    const nested = (summary as Record<string, unknown>)[field];
    if (nested !== null && nested !== undefined) return nested;
  }
  return report?.[field];
}

export function nativeMarketLabel(instrumentId: string, currency: unknown): string {
  const asset = instrumentId === 'BTC-USD-PERP.HYPERLIQUID' ? 'BTC' : instrumentId === 'SOL-USD-PERP.HYPERLIQUID' ? 'SOL' : null;
  return asset ? currency === 'USDC' ? asset + '/USDC' : asset + ' · currency unverified' : 'Other market';
}
export function nativeExecutionSubtitle(fill: { order_side: string | null; quantity: string; price: string }, state: HlStagegProjection | null): string {
  return (fill.order_side ?? 'Side unavailable') + ' · ' + fill.quantity + ' @ ' + nativeMoney(fill.price, projectionCurrency(state));
}
