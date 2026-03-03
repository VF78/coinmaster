import { useEffect, useState } from 'react';
import type { ExchangeSettingsResponse } from '../../shared/dto.js';
import { getExchangeSettings, getTelegramNotifyHealth, saveHyperliquidSettings, saveTelegramNotify, sendTelegramNotifyTest } from '../lib/api';
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

  const [hlAccountAddress, setHlAccountAddress] = useState('');
  const [hlApiWalletAddress, setHlApiWalletAddress] = useState('');
  const [hlApiPrivateKey, setHlApiPrivateKey] = useState('');
  const [isSavingHyperliquid, setIsSavingHyperliquid] = useState(false);
  const [hyperliquidInfo, setHyperliquidInfo] = useState('');

  async function refresh() {
    setIsLoading(true);
    try {
      const [next, health] = await Promise.all([
        getExchangeSettings(),
        getTelegramNotifyHealth().catch(() => null),
      ]);
      setData(next);
      setNotifyOpen(next.telegramNotify?.notifyOpen !== false);
      setNotifyTp(next.telegramNotify?.notifyTp !== false);
      setNotifySl(next.telegramNotify?.notifySl !== false);
      setNotifyManualConfirm(next.telegramNotify?.notifyManualConfirm !== false);
      setChatId(next.telegramNotify?.chatId ?? '');
      setBotToken(''); // never prefill secrets

      setHlAccountAddress(next.hyperliquid?.accountAddress ?? '');
      setHlApiWalletAddress(next.hyperliquid?.apiWalletAddress ?? '');
      setHlApiPrivateKey(''); // never prefill private key
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
      } = {
        notifyOpen,
        notifyTp,
        notifySl,
        notifyManualConfirm,
      };

      if (botToken.trim().length > 0) payload.botToken = botToken.trim();
      payload.chatId = chatId.trim();

      const result = await saveTelegramNotify(payload);
      if (!result.ok) {
        throw new Error('telegram_save_failed');
      }
      setTelegramInfo('Telegram settings saved.');
      await refresh();
    } catch (error) {
      setTelegramInfo(`Save failed: ${error instanceof Error ? error.message : 'unknown_error'}`);
    } finally {
      setIsSavingTelegram(false);
    }
  }

  async function sendTest() {
    setTelegramInfo('Sending test message...');
    try {
      const result = await sendTelegramNotifyTest();
      if (!result.ok) {
        throw new Error(result.error || 'test_failed');
      }
      setTelegramInfo('Test message queued.');
      await refresh();
    } catch (error) {
      setTelegramInfo(`Test failed: ${error instanceof Error ? error.message : 'unknown_error'}`);
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
      if (!result.ok) {
        throw new Error('hyperliquid_save_failed');
      }
      setHyperliquidInfo('Saved. Service restart scheduled to apply new credentials.');
    } catch (error) {
      setHyperliquidInfo(`Save failed: ${error instanceof Error ? error.message : 'unknown_error'}`);
    } finally {
      setIsSavingHyperliquid(false);
    }
  }

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
              {data.hyperliquid?.hasPrivateKey ? 'Private key configured' : 'Private key not configured'}
            </p>
          </div>
        </div>

        <div className="actions-row" style={{ marginTop: '0.9rem' }}>
          <Button type="button" variant="primary" onClick={saveHyperliquid} disabled={isSavingHyperliquid}>
            {isSavingHyperliquid ? 'Saving...' : 'Save Hyperliquid settings'}
          </Button>
        </div>

        <p className="muted stat-note">
          After saving credentials, Coinmaster restarts automatically to apply the new Hyperliquid API settings.
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
    </main>
  );
}
