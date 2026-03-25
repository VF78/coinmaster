import { useEffect, useState } from 'react';
import type { ExchangeSettingsResponse, ExchangeConnectionStatus } from '../../shared/dto.js';
import {
  getExchangeSettings,
  getReadOnlyExchangesSettings,
  getTelegramNotifyHealth,
  logoutHyperliquidSettings,
  saveBybitSettings,
  saveHyperliquidSettings,
  saveTelegramNotify,
  sendTelegramNotifyTest,
  testBybitConnection,
  friendlyCodeMessage,
  friendlyErrorMessage
} from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { Stat } from '../components/Stat';

export function SettingsPage() {
  const [data, setData] = useState<ExchangeSettingsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSavingTelegram, setIsSavingTelegram] = useState(false);
  const [telegramInfo, setTelegramInfo] = useState('');
  const [telegramHealth, setTelegramHealth] = useState<{
    queued: number;
    failed: number;
    oldestQueuedAgeSec: number;
    outboxRunning: boolean;
    updateRunning: boolean;
  } | null>(null);

  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');
  const [notifyOpen, setNotifyOpen] = useState(true);
  const [notifyTp, setNotifyTp] = useState(true);
  const [notifySl, setNotifySl] = useState(true);
  const [notifyManualConfirm, setNotifyManualConfirm] = useState(true);
  const [notifyDailyAnalytics, setNotifyDailyAnalytics] = useState(true);
  const [notifySignalRejected, setNotifySignalRejected] = useState(false);
  const [notifyOrderRejected, setNotifyOrderRejected] = useState(false);
  const [notifyPositionClosed, setNotifyPositionClosed] = useState(false);

  const [hlAccountAddress, setHlAccountAddress] = useState('');
  const [hlApiWalletAddress, setHlApiWalletAddress] = useState('');
  const [hlApiPrivateKey, setHlApiPrivateKey] = useState('');
  const [isSavingHyperliquid, setIsSavingHyperliquid] = useState(false);
  const [hyperliquidInfo, setHyperliquidInfo] = useState('');

  const [bybitMode, setBybitMode] = useState<'off' | 'read_only' | 'live'>('off');
  const [bybitApiKey, setBybitApiKey] = useState('');
  const [bybitApiSecret, setBybitApiSecret] = useState('');
  const [bybitAccountType, setBybitAccountType] = useState<'UNIFIED' | 'CONTRACT' | 'SPOT'>('UNIFIED');
  const [bybitCategories, setBybitCategories] = useState<Array<'linear' | 'inverse' | 'spot' | 'option'>>(['linear']);
  const [isSavingBybit, setIsSavingBybit] = useState(false);
  const [bybitInfo, setBybitInfo] = useState('');
  const [bybitStatus, setBybitStatus] = useState<ExchangeConnectionStatus | null>(null);

  function applyHyperliquidExchangeState(exchange: ExchangeSettingsResponse['hyperliquid'] | undefined) {
    if (!exchange) return;
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        connected: exchange.connected,
        hyperliquid: exchange,
      };
    });
  }

  function scheduleExchangeRefresh(delayMs = 1500) {
    setTimeout(() => {
      refresh().catch(() => undefined);
    }, delayMs);
  }

  async function refresh() {
    setIsLoading(true);
    try {
      const [next, health, roEx] = await Promise.all([
        getExchangeSettings(),
        getTelegramNotifyHealth().catch(() => null),
        getReadOnlyExchangesSettings().catch(() => null),
      ]);
      setData(next);
      setNotifyOpen(next.telegramNotify?.notifyOpen !== false);
      setNotifyTp(next.telegramNotify?.notifyTp !== false);
      setNotifySl(next.telegramNotify?.notifySl !== false);
      setNotifyManualConfirm(next.telegramNotify?.notifyManualConfirm !== false);
      setNotifyDailyAnalytics(next.telegramNotify?.notifyDailyAnalytics !== false);
      setNotifySignalRejected(next.telegramNotify?.notifySignalRejected === true);
      setNotifyOrderRejected(next.telegramNotify?.notifyOrderRejected === true);
      setNotifyPositionClosed(next.telegramNotify?.notifyPositionClosed === true);
      setChatId(next.telegramNotify?.chatId ?? '');
      setBotToken(''); // never prefill secrets

      setHlAccountAddress(next.hyperliquid?.accountAddress ?? '');
      setHlApiWalletAddress(next.hyperliquid?.apiWalletAddress ?? '');
      setHlApiPrivateKey(''); // never prefill private key

      if (roEx?.ok && roEx.exchanges.bybit) {
        setBybitMode(roEx.exchanges.bybit.mode);
        setBybitAccountType(roEx.exchanges.bybit.accountType);
        setBybitCategories(roEx.exchanges.bybit.categories);
        setBybitApiKey(''); // never prefill secrets
        setBybitApiSecret(''); // never prefill secrets
        const bybitStatusItem = roEx.status.find((s) => s.exchange === 'bybit');
        if (bybitStatusItem) setBybitStatus(bybitStatusItem);
      }

      if (health?.ok) {
        setTelegramHealth({
          queued: health.totals.queued,
          failed: health.totals.failed,
          oldestQueuedAgeSec: health.oldestQueuedAgeSec,
          outboxRunning: health.loop.outboxRunning,
          updateRunning: health.loop.updateRunning,
        });
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function saveTelegram() {
    setIsSavingTelegram(true);
    setTelegramInfo('Saving Telegram settings...');
    try {
      const payload: {
        botToken?: string;
        chatId?: string;
        notifyOpen: boolean;
        notifyTp: boolean;
        notifySl: boolean;
        notifyManualConfirm: boolean;
        notifyDailyAnalytics: boolean;
        notifySignalRejected: boolean;
        notifyOrderRejected: boolean;
        notifyPositionClosed: boolean;
      } = {
        notifyOpen,
        notifyTp,
        notifySl,
        notifyManualConfirm,
        notifyDailyAnalytics,
        notifySignalRejected,
        notifyOrderRejected,
        notifyPositionClosed,
      };

      if (botToken.trim().length > 0) payload.botToken = botToken.trim();
      payload.chatId = chatId.trim();

      const result = await saveTelegramNotify(payload);
      if (!result.ok) {
        throw new Error(friendlyCodeMessage('telegram_save_failed', 'Could not save Telegram settings.'));
      }
      setTelegramInfo('Telegram settings saved.');
      await refresh();
    } catch (error) {
      setTelegramInfo(`Save failed: ${friendlyErrorMessage(error, 'Could not save Telegram settings.')}`);
    } finally {
      setIsSavingTelegram(false);
    }
  }

  async function sendTest() {
    setTelegramInfo('Sending test message...');
    try {
      const result = await sendTelegramNotifyTest();
      if (!result.ok) {
        throw new Error(friendlyCodeMessage(result.error || 'test_failed', 'Could not send test message.'));
      }
      setTelegramInfo('Test message queued.');
      await refresh();
    } catch (error) {
      setTelegramInfo(`Test failed: ${friendlyErrorMessage(error, 'Could not send test message.')}`);
    }
  }

  async function saveHyperliquid() {
    setIsSavingHyperliquid(true);
    setHyperliquidInfo('Saving Hyperliquid API settings...');
    try {
      const result = await saveHyperliquidSettings({
        accountAddress: hlAccountAddress.trim(),
        apiWalletAddress: hlApiWalletAddress.trim(),
        apiPrivateKey: hlApiPrivateKey.trim() || undefined,
      });
      if (!result.ok || !result.exchange) {
        throw new Error(friendlyCodeMessage('hyperliquid_save_failed', 'Could not save Hyperliquid settings.'));
      }
      applyHyperliquidExchangeState(result.exchange);
      setHyperliquidInfo(result.exchange.enabled === false
        ? 'Hyperliquid credentials are stored but currently disconnected. Service restart scheduled.'
        : 'Saved. Service restart scheduled to apply Hyperliquid credentials.');
      scheduleExchangeRefresh();
    } catch (error) {
      setHyperliquidInfo(`Save failed: ${friendlyErrorMessage(error, 'Could not save Hyperliquid settings.')}`);
    } finally {
      setIsSavingHyperliquid(false);
    }
  }

  async function logoutHyperliquid() {
    setIsSavingHyperliquid(true);
    setHyperliquidInfo('Logging out Hyperliquid connection...');
    try {
      const result = await logoutHyperliquidSettings();
      if (!result.ok || !result.exchange) {
        throw new Error(friendlyCodeMessage('hyperliquid_save_failed', 'Could not remove Hyperliquid settings.'));
      }
      applyHyperliquidExchangeState(result.exchange);
      setHyperliquidInfo('Hyperliquid connection logged out. Credentials were kept, and Login will re-enable them after restart.');
      scheduleExchangeRefresh();
    } catch (error) {
      setHyperliquidInfo(`Logout failed: ${friendlyErrorMessage(error, 'Could not remove Hyperliquid settings.')}`);
    } finally {
      setIsSavingHyperliquid(false);
    }
  }

  async function saveBybit() {
    setIsSavingBybit(true);
    setBybitInfo('Saving Bybit read-only settings...');
    try {
      const payload: {
        mode: 'off' | 'read_only' | 'live';
        apiKey?: string;
        apiSecret?: string;
        accountType: 'UNIFIED' | 'CONTRACT' | 'SPOT';
        categories: Array<'linear' | 'inverse' | 'spot' | 'option'>;
      } = {
        mode: bybitMode,
        accountType: bybitAccountType,
        categories: bybitCategories,
      };

      if (bybitApiKey.trim().length > 0) payload.apiKey = bybitApiKey.trim();
      if (bybitApiSecret.trim().length > 0) payload.apiSecret = bybitApiSecret.trim();

      const result = await saveBybitSettings(payload);
      if (!result.ok) {
        throw new Error(friendlyCodeMessage('bybit_save_failed', 'Could not save Bybit settings.'));
      }
      setBybitInfo('Bybit settings saved.');
      await refresh();
    } catch (error) {
      setBybitInfo(`Save failed: ${friendlyErrorMessage(error, 'Could not save Bybit settings.')}`);
    } finally {
      setIsSavingBybit(false);
    }
  }

  async function testBybit() {
    setBybitInfo('Testing Bybit connection...');
    try {
      const result = await testBybitConnection();
      if (!result.ok) {
        throw new Error(friendlyCodeMessage('test_failed', result.status.message || 'Connection test failed.'));
      }
      setBybitStatus(result.status);
      setBybitInfo(`Connected: ${result.status.message || 'OK'}`);
    } catch (error) {
      setBybitInfo(`Test failed: ${friendlyErrorMessage(error, 'Could not test Bybit connection.')}`);
    }
  }

  const hasStoredHyperliquidCredentials = Boolean(
    data?.hyperliquid?.accountAddress || data?.hyperliquid?.apiWalletAddress || data?.hyperliquid?.hasPrivateKey
  );
  const isHyperliquidEnabled = Boolean(hasStoredHyperliquidCredentials && data?.hyperliquid?.enabled !== false);
  const canLoginHyperliquid = Boolean(
    (hlAccountAddress.trim() || data?.hyperliquid?.accountAddress)
    && (hlApiWalletAddress.trim() || data?.hyperliquid?.apiWalletAddress)
    && (hlApiPrivateKey.trim() || data?.hyperliquid?.hasPrivateKey)
  );
  const hyperliquidActionLabel = isHyperliquidEnabled ? 'Logout' : 'Login';
  const hyperliquidActionHandler = isHyperliquidEnabled ? logoutHyperliquid : saveHyperliquid;
  const hyperliquidActionDisabled = isSavingHyperliquid || (!isHyperliquidEnabled && !canLoginHyperliquid);

  if (!data) {
    return <p className="muted">Loading exchange settings…</p>;
  }

  return (
    <main className="terminal-layout">

      <Card title="Hyperliquid API credentials" className="terminal-card full-width">
        <div className="rules-form-grid">
          <label className="rules-field">
            <span className="rules-label">Account address</span>
            <input
              className="rules-input"
              type="text"
              placeholder="0x..."
              value={hlAccountAddress}
              onChange={(e) => setHlAccountAddress(e.target.value)}
            />
          </label>

          <label className="rules-field">
            <span className="rules-label">API wallet address</span>
            <input
              className="rules-input"
              type="text"
              placeholder="0x..."
              value={hlApiWalletAddress}
              onChange={(e) => setHlApiWalletAddress(e.target.value)}
            />
          </label>
        </div>

        <div className="rules-form-grid" style={{ marginTop: '0.75rem' }}>
          <label className="rules-field">
            <span className="rules-label">API private key</span>
            <input
              className="rules-input"
              type="password"
              placeholder={data.hyperliquid?.hasPrivateKey ? `${data.hyperliquid.privateKeyMasked} (leave empty to keep)` : '0x...'}
              value={hlApiPrivateKey}
              onChange={(e) => setHlApiPrivateKey(e.target.value)}
            />
          </label>
          <div className="rules-field">
            <span className="rules-label">Status</span>
            <p className="muted">
              {!data.hyperliquid?.hasPrivateKey
                ? 'Private key not configured'
                : data.hyperliquid?.enabled === false
                  ? 'Credentials stored, connection logged out'
                  : 'Private key configured and connection enabled'}
            </p>
          </div>
        </div>

        <div className="actions-row" style={{ marginTop: '0.9rem' }}>
          <Button type="button" variant="primary" onClick={saveHyperliquid} disabled={isSavingHyperliquid}>
            {isSavingHyperliquid ? 'Saving...' : 'Save Hyperliquid settings'}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={hyperliquidActionHandler}
            disabled={hyperliquidActionDisabled}
          >
            {hyperliquidActionLabel}
          </Button>
        </div>

        <p className="muted stat-note">
          Save/Login enables the stored Hyperliquid credentials. Logout disconnects Hyperliquid without erasing the saved credentials. Coinmaster restarts automatically after either action.
        </p>
        {hyperliquidInfo ? <p className="muted stat-note">{hyperliquidInfo}</p> : null}
      </Card>

      <Card title="Telegram notifications" className="terminal-card full-width">
        <div className="rules-form-grid">
          <label className="rules-field">
            <span className="rules-label">Bot token</span>
            <input
              className="rules-input"
              type="password"
              placeholder={data.telegramNotify?.hasToken ? `${data.telegramNotify.botTokenMasked} (leave empty to keep)` : '123456:ABC...'}
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
            />
          </label>

          <label className="rules-field">
            <span className="rules-label">Chat ID</span>
            <input
              className="rules-input"
              type="text"
              placeholder="e.g. 96211907 or -100..."
              value={chatId}
              onChange={(e) => setChatId(e.target.value)}
            />
          </label>
        </div>

        <div className="rules-form-grid" style={{ marginTop: '0.75rem' }}>
          <label className="rules-toggle-row">
            <span>Notify trade opened</span>
            <button type="button" role="switch" aria-checked={notifyOpen} className={`rules-toggle ${notifyOpen ? 'rules-toggle--on' : ''}`} onClick={() => setNotifyOpen((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>

          <label className="rules-toggle-row">
            <span>Notify TP events</span>
            <button type="button" role="switch" aria-checked={notifyTp} className={`rules-toggle ${notifyTp ? 'rules-toggle--on' : ''}`} onClick={() => setNotifyTp((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>

          <label className="rules-toggle-row">
            <span>Notify SL / emergency exits</span>
            <button type="button" role="switch" aria-checked={notifySl} className={`rules-toggle ${notifySl ? 'rules-toggle--on' : ''}`} onClick={() => setNotifySl((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>

          <label className="rules-toggle-row">
            <span>Notify manual confirmation required</span>
            <button type="button" role="switch" aria-checked={notifyManualConfirm} className={`rules-toggle ${notifyManualConfirm ? 'rules-toggle--on' : ''}`} onClick={() => setNotifyManualConfirm((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>

          <label className="rules-toggle-row">
            <span>Daily AI analytics summary</span>
            <button type="button" role="switch" aria-checked={notifyDailyAnalytics} className={`rules-toggle ${notifyDailyAnalytics ? 'rules-toggle--on' : ''}`} onClick={() => setNotifyDailyAnalytics((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>

          <label className="rules-toggle-row">
            <span>Notify signal rejected</span>
            <button type="button" role="switch" aria-checked={notifySignalRejected} className={`rules-toggle ${notifySignalRejected ? 'rules-toggle--on' : ''}`} onClick={() => setNotifySignalRejected((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>

          <label className="rules-toggle-row">
            <span>Notify order rejected</span>
            <button type="button" role="switch" aria-checked={notifyOrderRejected} className={`rules-toggle ${notifyOrderRejected ? 'rules-toggle--on' : ''}`} onClick={() => setNotifyOrderRejected((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>

          <label className="rules-toggle-row">
            <span>Notify position closed</span>
            <button type="button" role="switch" aria-checked={notifyPositionClosed} className={`rules-toggle ${notifyPositionClosed ? 'rules-toggle--on' : ''}`} onClick={() => setNotifyPositionClosed((v) => !v)}>
              <span className="rules-toggle__thumb" />
            </button>
          </label>
        </div>

        <div className="actions-row" style={{ marginTop: '0.9rem' }}>
          <Button type="button" variant="primary" onClick={saveTelegram} disabled={isSavingTelegram}>
            {isSavingTelegram ? 'Saving...' : 'Save Telegram settings'}
          </Button>
          <Button type="button" variant="secondary" onClick={sendTest} disabled={isSavingTelegram}>
            Send test notification
          </Button>
        </div>

        {telegramHealth ? (
          <p className="muted stat-note">
            Outbox: queued {telegramHealth.queued}, failed {telegramHealth.failed}, oldest queued age {telegramHealth.oldestQueuedAgeSec}s
            {' • '}workers: outbox {telegramHealth.outboxRunning ? 'ON' : 'OFF'}, updates {telegramHealth.updateRunning ? 'ON' : 'OFF'}
          </p>
        ) : null}

        {telegramInfo ? <p className="muted stat-note">{telegramInfo}</p> : null}
      </Card>

      <Card title="Bybit (Read-only telemetry)" className="terminal-card full-width">
        <div className="rules-form-grid">
          <label className="rules-field">
            <span className="rules-label">Mode</span>
            <select
              className="rules-input"
              value={bybitMode}
              onChange={(e) => setBybitMode(e.target.value as 'off' | 'read_only' | 'live')}
            >
              <option value="off">Off — disabled</option>
              <option value="read_only">Read-only — fetch trades for AI analytics, no order execution</option>
              <option value="live">Live — full trading (order execution enabled)</option>
            </select>
          </label>

          <label className="rules-field">
            <span className="rules-label">Account type</span>
            <select
              className="rules-input"
              value={bybitAccountType}
              onChange={(e) => setBybitAccountType(e.target.value as 'UNIFIED' | 'CONTRACT' | 'SPOT')}
            >
              <option value="UNIFIED">Unified</option>
              <option value="CONTRACT">Contract</option>
              <option value="SPOT">Spot</option>
            </select>
          </label>
        </div>

        <div className="rules-form-grid" style={{ marginTop: '0.75rem' }}>
          <label className="rules-field">
            <span className="rules-label">API key</span>
            <input
              className="rules-input"
              type="text"
              placeholder={data?.externalExchanges?.bybit.hasApiKey ? `${data.externalExchanges.bybit.apiKeyMasked} (leave empty to keep)` : 'API key'}
              value={bybitApiKey}
              onChange={(e) => setBybitApiKey(e.target.value)}
            />
          </label>

          <label className="rules-field">
            <span className="rules-label">API secret</span>
            <input
              className="rules-input"
              type="password"
              placeholder={data?.externalExchanges?.bybit.hasApiSecret ? `${data.externalExchanges.bybit.apiSecretMasked} (leave empty to keep)` : 'API secret'}
              value={bybitApiSecret}
              onChange={(e) => setBybitApiSecret(e.target.value)}
            />
          </label>
        </div>

        <div className="rules-form-grid" style={{ marginTop: '0.75rem' }}>
          <label className="rules-field">
            <span className="rules-label">Categories (read fills from)</span>
            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginTop: '0.4rem' }}>
              {(['linear', 'inverse', 'spot', 'option'] as const).map((cat) => (
                <label key={cat} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={bybitCategories.includes(cat)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setBybitCategories((prev) => [...prev, cat]);
                      } else {
                        setBybitCategories((prev) => prev.filter((x) => x !== cat));
                      }
                    }}
                  />
                  <span className="muted">{cat}</span>
                </label>
              ))}
            </div>
          </label>

          <div className="rules-field">
            <span className="rules-label">Status</span>
            <p className="muted">
              {bybitStatus
                ? `${bybitStatus.connected ? '✅ Connected' : '❌ Not connected'} • ${bybitStatus.message || 'No details'}`
                : 'Not tested yet'}
            </p>
          </div>
        </div>

        <div className="actions-row" style={{ marginTop: '0.9rem' }}>
          <Button type="button" variant="primary" onClick={saveBybit} disabled={isSavingBybit}>
            {isSavingBybit ? 'Saving...' : 'Save Bybit settings'}
          </Button>
          <Button type="button" variant="secondary" onClick={testBybit} disabled={isSavingBybit}>
            Test connection
          </Button>
        </div>

        <p className="muted stat-note">
          Read-only mode: Bybit trade data will be included in daily AI analytics. No order execution.
        </p>
        {bybitInfo ? <p className="muted stat-note">{bybitInfo}</p> : null}
      </Card>
    </main>
  );
}
