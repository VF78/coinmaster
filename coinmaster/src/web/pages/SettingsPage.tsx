import { useEffect, useState } from 'react';
import type { ExchangeSettingsResponse } from '../../shared/dto.js';
import { getExchangeSettings } from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { Stat } from '../components/Stat';

export function SettingsPage() {
  const [data, setData] = useState<ExchangeSettingsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function refresh() {
    setIsLoading(true);
    try {
      const next = await getExchangeSettings();
      setData(next);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  if (!data) {
    return <p className="muted">Loading exchange settings…</p>;
  }

  return (
    <main className="terminal-layout">
      <Card
        title="Exchange connection settings"
        className="terminal-card"
        actions={<Button onClick={() => refresh()} variant="secondary" disabled={isLoading}>Refresh</Button>}
      >
        <div className="stats-grid">
          <Stat label="Exchange" value={data.exchange.toUpperCase()} />
          <Stat label="Connection" value={data.connected ? 'Connected' : 'Disconnected'} tone={data.connected ? 'success' : 'danger'} />
          <Stat label="Account" value={data.accountAddress ?? '—'} />
          <Stat label="API wallet" value={data.walletAddress ?? '—'} />
          <Stat label="Manual confirmation" value={data.mode.manualConfirmation ? 'ON' : 'OFF'} />
          <Stat label="Max notional" value={`${formatNumber(data.mode.maxNotionalUsdc)} USDC`} />
          <Stat label="Max leverage" value={`${formatNumber(data.mode.maxLeverage)}x`} />
          <Stat label="Private trading" value={data.capabilities.privateTrading ? 'Enabled' : 'Disabled'} tone={data.capabilities.privateTrading ? 'success' : 'danger'} />
          <Stat label="Private account" value={data.capabilities.privateAccount ? 'Enabled' : 'Disabled'} tone={data.capabilities.privateAccount ? 'success' : 'danger'} />
          <Stat label="Realtime mids" value={data.capabilities.realtimeMids ? 'Enabled' : 'Disabled'} tone={data.capabilities.realtimeMids ? 'success' : 'danger'} />
          <Stat label="Available to trade" value={data.account?.availableUsd !== undefined ? formatMoney(data.account.availableUsd) : '—'} />
          <Stat label="Used margin" value={data.account?.usedMarginUsd !== undefined ? formatMoney(data.account.usedMarginUsd) : '—'} />
        </div>
        <p className="muted stat-note">
          {data.error ? `Connection error: ${data.error}` : 'Connection settings are read-only in this MVP build.'}
        </p>
      </Card>
    </main>
  );
}
