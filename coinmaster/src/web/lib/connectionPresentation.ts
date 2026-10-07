export type ConnectionVerification = Record<string, unknown>;
export type ConnectionVerificationRow = { label: string; value: string; tone: 'success' | 'danger' | 'neutral' };

function state(value: unknown, labels: Record<string, ConnectionVerificationRow>): ConnectionVerificationRow {
  return typeof value === 'string' && labels[value] ? labels[value] : { label: 'Status unavailable', value: 'Not confirmed', tone: 'neutral' };
}

export function connectionVerificationRows(venue: 'hyperliquid' | 'bybit', verification: ConnectionVerification): ConnectionVerificationRow[] {
  if (venue === 'hyperliquid') {
    return [
      state(verification.public_observation, {
        UNTESTED: { label: 'Public account', value: 'Not tested', tone: 'neutral' },
        REACHABLE: { label: 'Public account', value: 'Readable', tone: 'success' },
        ERROR: { label: 'Public account', value: 'Unavailable', tone: 'danger' },
      }),
      state(verification.agent_authorization, {
        NOT_PROVIDED: { label: 'Agent wallet', value: 'Not provided', tone: 'neutral' },
        UNVERIFIED: { label: 'Agent wallet', value: 'Not verified', tone: 'neutral' },
        VERIFIED: { label: 'Agent wallet', value: 'Verified', tone: 'success' },
        NOT_AUTHORIZED: { label: 'Agent wallet', value: 'Agent authorization missing', tone: 'danger' },
        MISMATCH: { label: 'Agent wallet', value: 'Wrong master account', tone: 'danger' },
        ERROR: { label: 'Agent wallet', value: 'Verification unavailable', tone: 'danger' },
      }),
    ];
  }
  return [state(verification.read_only_access, {
    UNTESTED: { label: 'Read-only access', value: 'Not tested', tone: 'neutral' },
    VERIFIED: { label: 'Read-only access', value: 'Verified', tone: 'success' },
    ERROR: { label: 'Read-only access', value: 'Unavailable', tone: 'danger' },
  })];
}

export function connectionDisplayLabel(venue: 'hyperliquid' | 'bybit', label: string, id: string, duplicateLabel: boolean): string {
  return venue === 'bybit' && duplicateLabel ? `${label} · ${id.slice(-6)}` : label;
}

export type ConnectionIdentity = { id: string; venue: 'hyperliquid' | 'bybit'; account_label: string; verification_state: ConnectionVerification };

export function selectedConnectionIdentity(connections: ConnectionIdentity[], displayId: string | null): ConnectionIdentity | null {
  return displayId ? connections.find((item) => item.id === displayId) ?? null : null;
}
