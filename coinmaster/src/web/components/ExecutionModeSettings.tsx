import { useEffect, useState } from 'react';
import { Card } from './Card';
import { Badge } from './Badge';
import { Button } from './Button';
type ModeState = { sandbox: { state: string }; live: { state: string; run_epoch: string | null; orders_enabled?: boolean }; activate_enabled: boolean; blockers: string[]; stop_enabled: boolean; stop_reason: string };
const label = (value: string | undefined) => value === 'RUNNING' ? 'Running' : value === 'INACTIVE' ? 'Inactive' : value === 'STARTING' ? 'Starting' : value === 'UNCONFIRMED' ? 'Unconfirmed' : value === 'FAILED' ? 'Failed' : 'Unavailable';
export function ExecutionModeSettings() {
  const [state, setState] = useState<ModeState | null>(null);
  const [view, setView] = useState<'sandbox' | 'live'>('sandbox');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  async function refresh() {
    try {
      const response = await fetch('/api/v1/connections/mode', { credentials: 'same-origin', cache: 'no-store' });
      if (response.status === 401) { window.location.assign('/login'); return; }
      if (!response.ok) throw new Error();
      const next = await response.json() as ModeState;
      if (!next.sandbox || !next.live || !Array.isArray(next.blockers) || next.activate_enabled !== false) throw new Error();
      setState(next); setError(false);
    } catch { setState(null); setError(true); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 10_000); return () => window.clearInterval(timer); }, []);
  return <Card title="Execution mode" actions={<Badge tone={state?.sandbox.state === 'RUNNING' ? 'success' : 'neutral'}>{loading ? 'Loading…' : 'Dry-run ' + label(state?.sandbox.state)}</Badge>}>
    <div className="execution-mode-selectors" role="group" aria-label="Inspect execution mode">
      <button type="button" aria-pressed={view === 'sandbox'} onClick={() => setView('sandbox')}>Dry-run</button><button type="button" aria-pressed={view === 'live'} onClick={() => setView('live')}>Live</button>
      <Button variant="secondary" onClick={() => void refresh()}>Refresh</Button>
    </div>
    {error ? <p role="alert">Execution status unavailable. Refresh to retry.</p> : view === 'sandbox' ? <p className="trader-note">Dry-run: {label(state?.sandbox.state)}. Virtual Sandbox capital and orders remain independent of the connected exchange account.</p> : <div className="execution-mode-live"><p><strong>Live: {label(state?.live.state)}</strong></p><p className="trader-note">Selecting this view does not start or stop either trader.</p><Button variant="primary" disabled title={state?.blockers.join(' ')}>Activate Live</Button>{state?.blockers.map((reason) => <p className="trader-note" key={reason}>{reason}</p>)}{state?.live.state === 'RUNNING' ? <p className="trader-note">{state.stop_reason}</p> : null}</div>}
  </Card>;
}
