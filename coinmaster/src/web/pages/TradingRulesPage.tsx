import { useState } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';

/* ── Coin allocation ─────────────────────────────────────────────── */

interface CoinAlloc {
  symbol: string;
  enabled: boolean;
  pct: number;
}

const DEFAULT_COINS: CoinAlloc[] = [
  { symbol: 'BTC', enabled: true, pct: 50 },
  { symbol: 'ETH', enabled: true, pct: 30 },
  { symbol: 'SOL', enabled: true, pct: 20 },
];

const TIMEFRAMES = ['5m', '15m', '1h', '4h'] as const;

/* ── Page ─────────────────────────────────────────────────────────── */

export function TradingRulesPage() {
  /* coin distribution */
  const [coins, setCoins] = useState<CoinAlloc[]>(DEFAULT_COINS);

  /* entry / exit timeframes */
  const [entryTf, setEntryTf] = useState<string>('15m');
  const [exitTf, setExitTf] = useState<string>('1h');
  const [fvgRetrace, setFvgRetrace] = useState(50);

  /* risk management */
  const [maxLeverage, setMaxLeverage] = useState(5);
  const [dailyDrawdown, setDailyDrawdown] = useState(3);

  /* default TP / SL */
  const [tpPct, setTpPct] = useState(6);
  const [slPct, setSlPct] = useState(2);

  /* confirmation mode */
  const [autoConfirm, setAutoConfirm] = useState(false);

  /* ── handlers ───────────────────────────────────────────────── */

  function toggleCoin(idx: number) {
    setCoins(prev => prev.map((c, i) => (i === idx ? { ...c, enabled: !c.enabled } : c)));
  }

  function setCoinPct(idx: number, pct: number) {
    setCoins(prev => prev.map((c, i) => (i === idx ? { ...c, pct } : c)));
  }

  function handleApply() {
    const totalPct = coins.filter(c => c.enabled).reduce((s, c) => s + c.pct, 0);

    if (totalPct !== 100) {
      alert(`Сумма allocation активных монет = ${totalPct}%. Должно быть 100%.`);
      return;
    }

    console.warn(
      '[TradingRules] Placeholder save. ' +
        'Торговля криптовалютами сопряжена с высоким риском. ' +
        'Убедитесь, что вы понимаете риски перед использованием автоматических стратегий.',
    );
    console.warn('[TradingRules] Telegram-уведомление об изменении правил — placeholder.');

    alert('Настройки сохранены (placeholder)');
  }

  /* ── render ──────────────────────────────────────────────────── */

  return (
    <main className="terminal-layout">
      {/* ── Coin Distribution ──────────────────────────────────── */}
      <Card title="Coin Distribution" actions={<Badge tone="neutral">Allocation</Badge>}>
        <div className="rules-grid">
          {coins.map((c, i) => (
            <label key={c.symbol} className="rules-coin-row">
              <input
                type="checkbox"
                checked={c.enabled}
                onChange={() => toggleCoin(i)}
                className="rules-checkbox"
              />
              <span className="rules-coin-symbol">{c.symbol}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={c.pct}
                onChange={e => setCoinPct(i, Number(e.target.value))}
                className="rules-input rules-input--sm"
                disabled={!c.enabled}
              />
              <span className="muted">%</span>
            </label>
          ))}
        </div>
        <p className="stat-note muted">
          Сумма активных: {coins.filter(c => c.enabled).reduce((s, c) => s + c.pct, 0)}%
        </p>
      </Card>

      {/* ── Timeframe Selection ────────────────────────────────── */}
      <Card title="Timeframe Selection" actions={<Badge tone="neutral">Entry / Exit</Badge>}>
        <div className="rules-section">
          <p className="rules-label">Entry timeframe</p>
          <div className="rules-btn-group">
            {TIMEFRAMES.map(tf => (
              <Button
                key={tf}
                variant={entryTf === tf ? 'primary' : 'secondary'}
                onClick={() => setEntryTf(tf)}
              >
                {tf}
              </Button>
            ))}
          </div>
        </div>

        <div className="rules-section">
          <p className="rules-label">Exit timeframe</p>
          <div className="rules-btn-group">
            {TIMEFRAMES.map(tf => (
              <Button
                key={tf}
                variant={exitTf === tf ? 'primary' : 'secondary'}
                onClick={() => setExitTf(tf)}
              >
                {tf}
              </Button>
            ))}
          </div>
        </div>

        <div className="rules-section">
          <label className="rules-label">
            FVG Retrace Level: <strong>{fvgRetrace}%</strong>
          </label>
          <input
            type="range"
            min={10}
            max={90}
            value={fvgRetrace}
            onChange={e => setFvgRetrace(Number(e.target.value))}
            className="rules-range"
          />
        </div>
      </Card>

      {/* ── Risk Management ────────────────────────────────────── */}
      <Card title="Risk Management" actions={<Badge tone="danger">Risk</Badge>}>
        <div className="rules-form-grid">
          <label className="rules-field">
            <span className="rules-label">Max Leverage</span>
            <input
              type="range"
              min={1}
              max={20}
              value={maxLeverage}
              onChange={e => setMaxLeverage(Number(e.target.value))}
              className="rules-range"
            />
            <span className="rules-range-value">{maxLeverage}x</span>
          </label>

          <label className="rules-field">
            <span className="rules-label">Daily Drawdown Limit</span>
            <div className="stack-row">
              <input
                type="number"
                min={0}
                max={100}
                value={dailyDrawdown}
                onChange={e => setDailyDrawdown(Number(e.target.value))}
                className="rules-input rules-input--sm"
              />
              <span className="muted">%</span>
            </div>
          </label>
        </div>

        <p className="stat-note muted">
          Рекомендация: leverage ≤ 5x, drawdown ≤ 3% для консервативной стратегии.
        </p>
      </Card>

      {/* ── TP / SL Defaults ───────────────────────────────────── */}
      <Card title="Default TP / SL" actions={<Badge tone="success">Targets</Badge>}>
        <div className="rules-form-grid">
          <label className="rules-field">
            <span className="rules-label">Take Profit</span>
            <div className="stack-row">
              <input
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={tpPct}
                onChange={e => setTpPct(Number(e.target.value))}
                className="rules-input rules-input--sm"
              />
              <span className="muted">%</span>
            </div>
          </label>

          <label className="rules-field">
            <span className="rules-label">Stop Loss</span>
            <div className="stack-row">
              <input
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={slPct}
                onChange={e => setSlPct(Number(e.target.value))}
                className="rules-input rules-input--sm"
              />
              <span className="muted">%</span>
            </div>
          </label>
        </div>

        <p className="stat-note muted">
          Рекомендация: TP ≥ 2× SL (risk-reward ≥ 2:1). Текущий R:R ={' '}
          <strong>{slPct > 0 ? (tpPct / slPct).toFixed(1) : '—'}:1</strong>
        </p>
      </Card>

      {/* ── Confirmation Mode ──────────────────────────────────── */}
      <Card title="Confirmation Mode">
        <label className="rules-toggle-row">
          <span>Auto-confirm orders</span>
          <button
            type="button"
            role="switch"
            aria-checked={autoConfirm}
            className={`rules-toggle ${autoConfirm ? 'rules-toggle--on' : ''}`}
            onClick={() => setAutoConfirm(v => !v)}
          >
            <span className="rules-toggle__thumb" />
          </button>
        </label>
        <p className="stat-note muted">
          {autoConfirm
            ? 'Ордера будут отправляться автоматически без подтверждения.'
            : 'Каждый ордер потребует ручного подтверждения перед отправкой.'}
        </p>
      </Card>

      {/* ── Monitoring ─────────────────────────────────────────── */}
      <Card title="Monitoring" actions={<Badge tone="neutral">Info</Badge>}>
        <p className="muted" style={{ lineHeight: 1.6 }}>
          Система отслеживает изменения структуры рынка (BOS / CHoCH), формирование FVG и
          уровни ликвидности. При срабатывании условий входа — отправляется Telegram-уведомление
          (placeholder). Мониторинг активен 24/7 в выбранных timeframe.
        </p>
        <p className="stat-note" style={{ color: 'var(--danger)' }}>
          Торговля криптовалютами сопряжена с высоким риском потери капитала.
          Прошлые результаты не гарантируют будущих.
        </p>
      </Card>

      {/* ── Apply ──────────────────────────────────────────────── */}
      <div className="rules-apply-row">
        <Button variant="primary" fullWidth onClick={handleApply}>
          Применить
        </Button>
      </div>
    </main>
  );
}
