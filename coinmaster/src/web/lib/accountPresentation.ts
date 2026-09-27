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


export type DashboardState = {
  label: string;
  tone: "success" | "danger" | "neutral";
  detail: string;
  exposure: string;
  canAssertFlat: boolean;
};

export function dashboardState(state: HlStagegProjection | null): DashboardState {
  if (!state) return { label: "UNAVAILABLE", tone: "danger", detail: "Stage-G status could not be read.", exposure: "Unavailable", canAssertFlat: false };
  const positions = state.positions.length;
  const orders = state.orders.length;
  const exposure = [positions ? `${positions} position${positions === 1 ? "" : "s"}` : "", orders ? `${orders} order${orders === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ");
  const canAssertFlat = state.projection_state === "READY" && state.recovery_required !== true && positions === 0 && orders === 0;
  if (state.recovery_required === true) return {
    label: "RECOVERY REQUIRED", tone: "danger",
    detail: "Stored positions and orders are visible, but this worker has not recovered ownership. Account valuation and protection values are unverified.",
    exposure: exposure || "Exposure not reconciled", canAssertFlat: false,
  };
  if (state.projection_state !== "READY") return { label: state.projection_state, tone: "danger", detail: "Stage-G status is not ready; exposure cannot be confirmed.", exposure: exposure || "Unavailable", canAssertFlat: false };
  if (state.account.status === "UNAVAILABLE") return { label: "ACCOUNT UNAVAILABLE", tone: "danger", detail: "The native account read is unavailable. No account value is inferred from the Sandbox seed.", exposure: exposure || (canAssertFlat ? "Flat" : "Exposure not reconciled"), canAssertFlat };
  return { label: state.process_state, tone: "success", detail: "Native Sandbox account and exposure are available.", exposure: exposure || (canAssertFlat ? "Flat" : "Exposure not reconciled"), canAssertFlat };
}

export function protectionIsVerified(state: HlStagegProjection | null): boolean {
  return Boolean(state && state.recovery_required !== true && state.projection_state === "READY" && state.deposit_protection?.state === "ARMED");
}
