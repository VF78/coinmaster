import type { HlStagegProjection } from './nautilusApi';
import { traderMoney, projectionCurrency } from './traderFormatting';

export type AccountFigure = { key: string; label: string; value: string };


export function accountFigures(state: HlStagegProjection | null): AccountFigure[] {
  const account = state?.account;
  const amount = (value: string | null | undefined) => traderMoney(value, projectionCurrency(state));
  const stale = account?.mark_state === 'STALE_OR_MISSING';
  return [
    { key: 'cash', label: state?.mode === 'live' ? 'Reported account total' : 'Cash', value: amount(account?.native_cash) },
    { key: 'available', label: 'Available cash', value: amount(account?.native_free) },
    { key: 'hold', label: state?.mode === 'live' ? 'USDC hold · proxy' : 'Reserved cash', value: amount(account?.native_locked) },
    { key: 'equity', label: state?.mode === 'live' ? 'Reported equity' : 'Marked equity', value: stale ? 'Not current' : amount(account?.equity) },
    { key: 'realized', label: 'Realized PnL after fees', value: amount(account?.realized_pnl_net_fees) },
    { key: 'unrealized', label: 'Unrealized PnL', value: stale ? 'Not current' : amount(account?.unrealized_pnl) },
    { key: 'fees', label: 'Fees paid', value: amount(account?.fees) },
  ];
}

export function fundingLabel(state: HlStagegProjection | null): string {
  const raw = state?.funding_state?.trim();
  if (!raw) return 'Not posted; settlement is unconfirmed';
  if (raw === 'OBSERVED_MODELLED_UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT') return 'Observed only; next payment and settlement are unconfirmed';
  if (raw === 'OBSERVED_MODELLED_UNPOSTED') return 'Observed only; not credited';
  if (raw === 'UNPOSTED_NEXT_PAYMENT_NOT_CONFIRMED_SETTLEMENT') return 'Not credited; next payment and settlement are unconfirmed';
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

function humanizeProjectionState(value: string): string {
  const labels: Record<string, string> = { STALE: 'Stale', UNAVAILABLE: 'Unavailable', WORKER_DISCONNECTED: 'Worker disconnected' };
  return labels[value] ?? value.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}

export function dashboardState(state: HlStagegProjection | null): DashboardState {
  if (!state) return { label: "Unavailable", tone: "danger", detail: "Stage-G status could not be read.", exposure: "Unavailable", canAssertFlat: false };
  const positions = state.positions.length;
  const orders = state.orders.length;
  const exposure = [positions ? `${positions} position${positions === 1 ? "" : "s"}` : "", orders ? `${orders} order${orders === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ");
  const canAssertFlat = state.projection_state === "READY" && state.recovery_required !== true && positions === 0 && orders === 0;
  if (state.recovery_required === true) return {
    label: "Recovery required", tone: "danger",
    detail: "Stored positions and orders are visible, but this worker has not recovered ownership. Account valuation and protection values are unverified.",
    exposure: exposure || "Exposure not reconciled", canAssertFlat: false,
  };
  if (state.projection_state !== "READY") return { label: humanizeProjectionState(state.projection_state), tone: "danger", detail: "Stage-G status is not ready; exposure cannot be confirmed.", exposure: exposure || "Unavailable", canAssertFlat: false };
  if (!projectionCurrency(state)) return { label: "Currency unverified", tone: "danger", detail: "USDC denomination is unverified; account values are withheld.", exposure: "Exposure not reconciled", canAssertFlat: false };
  if (state.account.status === "UNAVAILABLE") return { label: "Account unavailable", tone: "danger", detail: "The native account read is unavailable. No account value is inferred from the planned seed.", exposure: exposure || (canAssertFlat ? "Flat" : "Exposure not reconciled"), canAssertFlat };
  const processLabels: Record<string, string> = {
    PUBLIC_FEEDS_READY: "Public market data ready",
    READY: "Worker ready",
    "DATA_STALE/PAUSED": "Market data stale · paused",
    WORKER_DISCONNECTED: "Worker disconnected",
  };
  return { label: processLabels[state.process_state] ?? state.process_state.replaceAll("_", " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase()), tone: "success", detail: "Native account and exposure are available.", exposure: exposure || (canAssertFlat ? "Flat" : "Exposure not reconciled"), canAssertFlat };
}

export function protectionIsVerified(state: HlStagegProjection | null): boolean {
  return Boolean(state && state.recovery_required !== true && state.projection_state === "READY" && state.deposit_protection?.state === "ARMED" && state.deposit_protection.currency === "USDC" && projectionCurrency(state) === "USDC");
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
