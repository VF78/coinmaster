import type { HlStagegProjection } from './nautilusApi';

export type AccountFigure = { label: string; value: string };

function amount(value: string | null | undefined): string {
  return value === null || value === undefined ? 'UNKNOWN' : `${value} USDC`;
}

export function accountFigures(state: HlStagegProjection | null): AccountFigure[] {
  const account = state?.account;
  const stale = account?.mark_state === 'STALE_OR_MISSING';
  return [
    { label: 'Native cash', value: amount(account?.native_cash) },
    { label: 'Native free', value: amount(account?.native_free) },
    { label: 'Native locked', value: amount(account?.native_locked) },
    { label: 'Marked equity', value: stale ? 'STALE' : amount(account?.equity) },
    { label: 'Realized PnL net fees', value: amount(account?.realized_pnl_net_fees) },
    { label: 'Unrealized PnL', value: stale ? 'STALE' : amount(account?.unrealized_pnl) },
    { label: 'Native fees', value: amount(account?.fees) },
  ];
}

export function fundingLabel(state: HlStagegProjection | null): string {
  const raw = state?.funding_state?.trim();
  return raw ? raw.replaceAll('_', ' ') : 'UNPOSTED';
}
