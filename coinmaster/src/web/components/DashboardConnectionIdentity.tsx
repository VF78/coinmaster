import { useEffect, useState } from 'react';
import { Badge } from './Badge';
import { connectionDisplayLabel, connectionVerificationRows, selectedConnectionIdentity, type ConnectionIdentity } from '../lib/connectionPresentation';
import './DashboardConnectionIdentity.css';

type ConnectionSnapshot = { connections: ConnectionIdentity[]; display_connection_id: string | null };
type ViewState = { kind: 'loading' } | { kind: 'none' } | { kind: 'selected'; item: ConnectionIdentity; duplicateLabel: boolean } | { kind: 'unavailable' };

function isConnectionIdentity(value: unknown): value is ConnectionIdentity {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<ConnectionIdentity>;
  return typeof row.id === 'string' && typeof row.account_label === 'string'
    && (row.venue === 'hyperliquid' || row.venue === 'bybit')
    && typeof row.verification_state === 'object' && row.verification_state !== null;
}

export function DashboardConnectionIdentity() {
  const [view, setView] = useState<ViewState>({ kind: 'loading' });
  useEffect(() => {
    let active = true;
    void fetch('/api/v1/connections', { credentials: 'same-origin', cache: 'no-store' })
      .then(async (response) => {
        if (response.status === 401) {
          window.location.assign('/login');
          throw new Error('session expired');
        }
        if (!response.ok) throw new Error(`connection status ${response.status}`);
        const snapshot = await response.json() as ConnectionSnapshot;
        if (!snapshot || !Array.isArray(snapshot.connections) || !snapshot.connections.every(isConnectionIdentity) || !(snapshot.display_connection_id === null || typeof snapshot.display_connection_id === 'string')) {
          throw new Error('invalid connection response');
        }
        const item = selectedConnectionIdentity(snapshot.connections, snapshot.display_connection_id);
        if (!active) return;
        if (!snapshot.display_connection_id) {
          setView({ kind: 'none' });
          return;
        }
        if (!item) {
          setView({ kind: 'unavailable' });
          return;
        }
        const duplicateLabel = snapshot.connections.filter((row) => row.venue === item.venue && row.account_label === item.account_label).length > 1;
        setView({ kind: 'selected', item, duplicateLabel });
      })
      .catch(() => { if (active) setView({ kind: 'unavailable' }); });
    return () => { active = false; };
  }, []);

  if (view.kind === 'loading' || view.kind === 'none') return null;
  if (view.kind === 'unavailable') return <aside className="dashboard-connection-identity dashboard-connection-identity--unavailable" aria-label="External account selection status">
    <strong>Selected exchange account unavailable</strong>
    <span>Sandbox account figures remain separate and unchanged.</span>
  </aside>;

  const label = connectionDisplayLabel(view.item.venue, view.item.account_label, view.item.id, view.duplicateLabel);
  const venue = view.item.venue === 'hyperliquid' ? 'Hyperliquid' : 'Bybit';
  const statuses = connectionVerificationRows(view.item.venue, view.item.verification_state);
  return <aside className="dashboard-connection-identity" aria-label="Selected read-only exchange account">
    <div className="dashboard-connection-identity__name"><span>Selected read-only account</span><strong>{venue} · {label}</strong></div>
    <div className="dashboard-connection-identity__checks">{statuses.map((status) => <span key={status.label}><small>{status.label}</small><Badge tone={status.tone}>{status.value}</Badge></span>)}</div>
    <p>Separate from native Sandbox equity, cash, and P&amp;L below.</p>
  </aside>;
}
