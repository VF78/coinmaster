import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { connectionDisplayLabel, connectionVerificationRows, selectedConnectionIdentity } from './connectionPresentation.js';

test('Hyperliquid public readability does not imply agent authorization', () => {
  assert.deepEqual(connectionVerificationRows('hyperliquid', { public_observation: 'REACHABLE', agent_authorization: 'NOT_PROVIDED' }), [
    { label: 'Public account', value: 'Readable', tone: 'success' },
    { label: 'Agent wallet', value: 'Not provided', tone: 'neutral' },
  ]);
});

test('Hyperliquid agent authorization states remain distinct', () => {
  assert.equal(connectionVerificationRows('hyperliquid', { public_observation: 'ERROR', agent_authorization: 'UNVERIFIED' })[0].value, 'Unavailable');
  assert.equal(connectionVerificationRows('hyperliquid', { public_observation: 'ERROR', agent_authorization: 'UNVERIFIED' })[1].value, 'Not verified');
  assert.equal(connectionVerificationRows('hyperliquid', { public_observation: 'REACHABLE', agent_authorization: 'VERIFIED' })[1].value, 'Verified');
  assert.equal(connectionVerificationRows('hyperliquid', { public_observation: 'REACHABLE', agent_authorization: 'ERROR' })[1].value, 'Authorization failed');
});

test('Bybit verification only describes read-only access', () => {
  assert.deepEqual(connectionVerificationRows('bybit', { read_only_access: 'VERIFIED' }), [
    { label: 'Read-only access', value: 'Verified', tone: 'success' },
  ]);
  assert.equal(connectionVerificationRows('bybit', { read_only_access: 'ERROR' })[0].value, 'Unavailable');
});

test('unknown verification values never leak machine codes into the UI', () => {
  assert.equal(connectionVerificationRows('bybit', { read_only_access: 'SECRET_INTERNAL_CODE' })[0].value, 'Not confirmed');
  assert.equal(connectionVerificationRows('hyperliquid', {})[1].value, 'Not confirmed');
});

test('duplicate Bybit account labels get a short identity suffix without exposing full IDs', () => {
  assert.equal(connectionDisplayLabel('bybit', 'Bybit account', 'opaque-abcdef123456', true), 'Bybit account · 123456');
  assert.equal(connectionDisplayLabel('bybit', 'Bybit account', 'opaque-abcdef123456', false), 'Bybit account');
  assert.equal(connectionDisplayLabel('hyperliquid', '0x…1234', 'opaque-abcdef123456', true), '0x…1234');
});

test('dashboard identity follows only the selected opaque connection ID', () => {
  const connections = [
    { id: 'a1', venue: 'hyperliquid' as const, account_label: '0x…1111', verification_state: { public_observation: 'REACHABLE' } },
    { id: 'b2', venue: 'bybit' as const, account_label: 'Bybit account', verification_state: { read_only_access: 'VERIFIED' } },
  ];
  assert.equal(selectedConnectionIdentity(connections, null), null);
  assert.equal(selectedConnectionIdentity(connections, 'missing'), null);
  assert.equal(selectedConnectionIdentity(connections, 'b2')?.venue, 'bybit');
});

test('Settings keeps permissions guidance collapsed and the saved-account table responsive', () => {
  const component = readFileSync(new URL('../components/SettingsConnections.tsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('../components/SettingsConnections.css', import.meta.url), 'utf8');
  assert.match(component, /<details className=\"settings-connections__help\"><summary>Permissions and safety<\/summary>/);
  assert.match(component, /<table className=\"settings-connections__table\">/);
  assert.match(styles, /\.settings-connections__table \{ width:100%; border-collapse:collapse; table-layout:fixed; \}/);
  assert.match(styles, /@media \(max-width:700px\)[\s\S]*?\.settings-connections__table tr \{ display:grid;/);
});
