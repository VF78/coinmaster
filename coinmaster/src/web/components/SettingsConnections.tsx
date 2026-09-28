import { useEffect, useState, type FormEvent } from 'react';
import { Badge } from './Badge';
import { Button } from './Button';
import { Card } from './Card';
import { getGuiSession } from '../lib/nautilusApi';
import { connectionDisplayLabel, connectionVerificationRows } from '../lib/connectionPresentation';
import './SettingsConnections.css';

type Venue = 'hyperliquid' | 'bybit';
type Connection = {
  id: string;
  venue: Venue;
  account_label: string;
  verification_state: Record<string, unknown>;
  last_tested_at: string | null;
};
type ConnectionResponse = { connections: Connection[]; display_connection_id: string | null };
type DisplayResponse = { display_connection_id: string | null };

async function connectionRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (init.body) headers['Content-Type'] = 'application/json';
  if (!['GET', 'HEAD'].includes(method)) headers['X-CSRF-Token'] = (await getGuiSession()).csrf_token;
  const response = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: 'same-origin', cache: 'no-store' });
  if (response.status === 401) {
    window.location.assign('/login');
    throw new Error('Your session expired. Sign in again.');
  }
  if (!response.ok) {
    const message = response.status === 400 || response.status === 422
      ? 'Check the connection details and try again.'
      : response.status === 403
        ? 'This change could not be authorized. Refresh and try again.'
        : response.status === 409
          ? 'The connection changed. Refresh and try again.'
          : `Connection request failed (${response.status}).`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function isConnection(value: unknown): value is Connection {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<Connection>;
  return typeof row.id === 'string' && typeof row.account_label === 'string'
    && (row.venue === 'hyperliquid' || row.venue === 'bybit')
    && typeof row.verification_state === 'object' && row.verification_state !== null;
}

function testedAt(value: string | null) {
  if (!value) return 'Not tested';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not tested' : date.toLocaleString();
}

export function SettingsConnections() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [displayId, setDisplayId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [savingDisplay, setSavingDisplay] = useState(false);
  const [venue, setVenue] = useState<Venue>('hyperliquid');
  const [masterAddress, setMasterAddress] = useState('');
  const [agentPrivateKey, setAgentPrivateKey] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const result = await connectionRequest<ConnectionResponse>('/connections');
      if (!result || !Array.isArray(result.connections) || !result.connections.every(isConnection)) {
        throw new Error('The connection service returned an invalid response.');
      }
      setConnections(result.connections);
      setDisplayId(result.display_connection_id ?? null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load saved connections.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function addConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setError('');
    setMessage('');
    setSaving(true);
    try {
      const body = venue === 'hyperliquid'
        ? { venue, master_address: masterAddress.trim(), ...(agentPrivateKey.trim() ? { agent_private_key: agentPrivateKey.trim() } : {}) }
        : { venue, api_key: apiKey.trim(), api_secret: apiSecret.trim() };
      const created = await connectionRequest<Connection>('/connections', { method: 'POST', body: JSON.stringify(body) });
      if (!isConnection(created)) throw new Error('The new connection could not be confirmed. Refresh to check its status.');
      setConnections((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setMessage(`${venue === 'hyperliquid' ? 'Hyperliquid' : 'Bybit'} connection saved.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save the connection.');
    } finally {
      setMasterAddress('');
      setAgentPrivateKey('');
      setApiKey('');
      setApiSecret('');
      setSaving(false);
    }
  }

  async function testConnection(item: Connection) {
    if (testingId) return;
    setTestingId(item.id);
    setError('');
    setMessage('');
    try {
      const updated = await connectionRequest<Connection>(`/connections/${encodeURIComponent(item.id)}/test`, { method: 'POST' });
      if (!isConnection(updated)) throw new Error('The test result could not be confirmed. Refresh to check its status.');
      setConnections((current) => current.map((row) => row.id === updated.id ? updated : row));
      setMessage('Access status updated.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not test this connection.');
    } finally {
      setTestingId(null);
    }
  }

  async function removeConnection(item: Connection) {
    if (removingId) return;
    if (!window.confirm(`Remove the saved ${item.venue === 'hyperliquid' ? 'Hyperliquid' : 'Bybit'} credentials for “${item.account_label}”?`)) return;
    setRemovingId(item.id);
    setError('');
    setMessage('');
    try {
      await connectionRequest<void>(`/connections/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
      await refresh();
      setMessage('Credentials removed.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not remove this connection.');
    } finally {
      setRemovingId(null);
    }
  }

  async function saveDisplayConnection() {
    if (savingDisplay) return;
    setSavingDisplay(true);
    setError('');
    setMessage('');
    try {
      const result = await connectionRequest<DisplayResponse>('/connections/display', {
        method: 'PUT', body: JSON.stringify({ connection_id: displayId }),
      });
      setDisplayId(result.display_connection_id ?? null);
      setMessage('Dashboard selection saved.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save the display account.');
    } finally {
      setSavingDisplay(false);
    }
  }

  const validHyperliquid = /^0x[0-9a-fA-F]{40}$/.test(masterAddress.trim());
  const validBybit = apiKey.trim().length > 0 && apiSecret.trim().length > 0;
  const canSubmit = venue === 'hyperliquid' ? validHyperliquid : validBybit;
  const displayLabel = (item: Connection) => connectionDisplayLabel(item.venue, item.account_label, item.id, connections.filter((row) => row.venue === item.venue && row.account_label === item.account_label).length > 1);

  return <section className="settings-connections" aria-label="Exchange connections">
    <Card title="Exchange accounts" actions={<Badge tone="neutral">Display only</Badge>}>
      <p className="settings-connections__intro">Add an account. Its identity can appear on Dashboard.</p>
      <form className="settings-connections__form" onSubmit={(event) => void addConnection(event)}>
        <label className="rules-field">
          <span className="rules-label">Exchange</span>
          <select className="rules-input" value={venue} onChange={(event) => setVenue(event.target.value as Venue)} disabled={saving}>
            <option value="hyperliquid">Hyperliquid</option>
            <option value="bybit">Bybit</option>
          </select>
        </label>
        {venue === 'hyperliquid' ? <>
          <label className="rules-field">
            <span className="rules-label">Master address</span>
            <input className="rules-input" autoComplete="off" spellCheck={false} inputMode="text" placeholder="0x…" value={masterAddress} onChange={(event) => setMasterAddress(event.target.value)} aria-invalid={masterAddress.length > 0 && !validHyperliquid || undefined} />
            {masterAddress.length > 0 && !validHyperliquid ? <span className="settings-connections__field-error">Enter a valid 0x address.</span> : null}
          </label>
          <label className="rules-field settings-connections__wide">
            <span className="rules-label">Agent private key <span className="muted">· optional</span></span>
            <input className="rules-input" type="password" autoComplete="new-password" placeholder="API agent key" value={agentPrivateKey} onChange={(event) => setAgentPrivateKey(event.target.value)} />
          </label>
        </> : <>
          <label className="rules-field">
            <span className="rules-label">API key</span>
            <input className="rules-input" type="password" autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} />
          </label>
          <label className="rules-field">
            <span className="rules-label">API secret</span>
            <input className="rules-input" type="password" autoComplete="new-password" value={apiSecret} onChange={(event) => setApiSecret(event.target.value)} />
          </label>
        </>}
        <div className="settings-connections__submit"><Button type="submit" variant="primary" disabled={!canSubmit || saving}>{saving ? 'Saving…' : 'Add account'}</Button></div>
      </form>
      <details className="settings-connections__help"><summary>Permissions and safety</summary><p>Hyperliquid public reads and optional agent authorization are separate checks. Bybit access is read-only. This page does not provide order controls.</p></details>
      {message ? <p className="settings-connections__notice" role="status">{message}</p> : null}
      {error ? <p className="settings-connections__error" role="alert">{error}</p> : null}
    </Card>

    <Card title="Saved accounts" actions={<Button type="button" variant="secondary" onClick={() => void refresh()} disabled={loading}>{loading ? 'Loading…' : 'Refresh'}</Button>}>
      <div className="settings-connections__display">
        <label className="rules-field">
          <span className="rules-label">Dashboard account</span>
          <select className="rules-input" value={displayId ?? ''} onChange={(event) => setDisplayId(event.target.value || null)} disabled={loading || connections.length === 0}>
            <option value="">No account selected</option>
            {connections.map((item) => <option key={item.id} value={item.id}>{item.venue === 'hyperliquid' ? 'Hyperliquid' : 'Bybit'} · {displayLabel(item)}</option>)}
          </select>
        </label>
        <Button type="button" variant="secondary" onClick={() => void saveDisplayConnection()} disabled={savingDisplay || loading}>{savingDisplay ? 'Saving…' : 'Save selection'}</Button>
      </div>
      {loading ? <p className="settings-connections__empty">Loading saved accounts…</p> : error && connections.length === 0 ? null : connections.length === 0 ? <div className="settings-connections__empty"><strong>No accounts connected</strong><span>Add an account above to show its identity on Dashboard.</span></div> : <div className="settings-connections__table-wrap">
        <table className="settings-connections__table">
          <thead><tr><th scope="col">Account</th><th scope="col">Verification</th><th scope="col">Last tested</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>{connections.map((item) => <tr key={item.id}>
            <td data-label="Account"><div className="settings-connections__account-name"><strong>{displayLabel(item)}</strong><span>{item.venue === 'hyperliquid' ? 'Hyperliquid' : 'Bybit'}{item.id === displayId ? ' · Dashboard' : ''}</span></div></td>
            <td data-label="Verification"><div className="settings-connections__verification">{connectionVerificationRows(item.venue, item.verification_state).map((row) => <span key={row.label}><small>{row.label}</small><Badge tone={row.tone}>{row.value}</Badge></span>)}</div></td>
            <td data-label="Last tested" className="settings-connections__tested">{testedAt(item.last_tested_at)}</td>
            <td data-label="Actions"><div className="settings-connections__actions">
              <Button type="button" variant="secondary" onClick={() => void testConnection(item)} disabled={testingId !== null || removingId !== null}>{testingId === item.id ? 'Testing…' : 'Test access'}</Button>
              <Button type="button" variant="secondary" onClick={() => void removeConnection(item)} disabled={removingId !== null || testingId !== null}>{removingId === item.id ? 'Removing…' : 'Disconnect'}</Button>
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>}
    </Card>
  </section>;
}
