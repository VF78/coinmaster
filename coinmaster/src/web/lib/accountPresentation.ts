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
  if (!raw) return 'Not posted; settlement is unconfirmed';
  if (raw === 'OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT') return 'Observed/modelled; next payment and settlement are unconfirmed';
  if (raw === 'OBSERVED_MODELLED_UNPOSTED') return 'Observed/modelled; not posted';
  if (raw === 'UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT') return 'Not posted; next payment and settlement are unconfirmed';
  return raw.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}

export function formatUtcTimestamp(value: string | null | undefined): string {
  if (!value) return 'Unavailable';
  const normalized = value.replace(/(\.\d{3})\d+(?=Z|[+-]\d{2}:\d{2}$)/, '$1');
  const date = new Date(normalized);
  if (!Number.isFinite(date.getTime())) return 'Unavailable';
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(date);
  const valueOf = (type: string) => parts.find((part) => part.type === type)?.value ?? '';
  return valueOf('day') + ' ' + valueOf('month') + ' ' + valueOf('year') + ' · ' + valueOf('hour') + ':' + valueOf('minute') + ' UTC';
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
  const processLabels: Record<string, string> = {
    PUBLIC_FEEDS_READY: "Public market data ready",
    READY: "Sandbox worker ready",
    "DATA_STALE/PAUSED": "Market data stale · paused",
    WORKER_DISCONNECTED: "Worker disconnected",
  };
  return { label: processLabels[state.process_state] ?? state.process_state.replaceAll("_", " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase()), tone: "success", detail: "Native Sandbox account and exposure are available.", exposure: exposure || (canAssertFlat ? "Flat" : "Exposure not reconciled"), canAssertFlat };
}

export function protectionIsVerified(state: HlStagegProjection | null): boolean {
  return Boolean(state && state.recovery_required !== true && state.projection_state === "READY" && state.deposit_protection?.state === "ARMED");
}

export function protectionIsFresh(
  state: HlStagegProjection | null,
  nowNs = Date.now() * 1_000_000,
  maxAgeNs = 15_000_000_000,
): boolean {
  if (!protectionIsVerified(state)) return false;
  const observedAtNs = state?.deposit_protection?.observed_at_ns;
  if (observedAtNs == null || !Number.isFinite(observedAtNs)) return false;
  const ageNs = nowNs - observedAtNs;
  return ageNs >= 0 && ageNs <= maxAgeNs;
}
