import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import type { TradingCoinAllocation, TradingRulesSettings, TradingRulesTimeframe } from '../../shared/dto.js';
import { cloneTradingRulesDefaults, normalizeTradingRules } from '../../shared/tradingRules.js';
import { getTradingRules, saveTradingRules } from '../lib/api';

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

export function TradingRulesPage() {
  const defaults = cloneTradingRulesDefaults();

  const [coins, setCoins] = useState<TradingCoinAllocation[]>(defaults.coins);
  const [entryTimeframes, setEntryTimeframes] = useState<TradingRulesTimeframe[]>(defaults.entryTimeframes);
  const [emergencyExitTimeframes, setEmergencyExitTimeframes] = useState<TradingRulesTimeframe[]>(defaults.emergencyExitTimeframes);
  const [engulfingLookbackCandles, setEngulfingLookbackCandles] = useState(defaults.engulfingLookbackCandles);
  const [fvgRetrace, setFvgRetrace] = useState(defaults.fvgRetrace);
  const [maxLeverage, setMaxLeverage] = useState(defaults.maxLeverage);
  const [dailyDrawdown, setDailyDrawdown] = useState(defaults.dailyDrawdown);
  const [tpPct, setTpPct] = useState(defaults.tpPct);
  const [slPct, setSlPct] = useState(defaults.slPct);
  const [autoConfirm, setAutoConfirm] = useState(defaults.autoConfirm);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveInfo, setSaveInfo] = useState<string>('');

  const totalPct = useMemo(
    () => Math.round(coins.filter(c => c.enabled).reduce((s, c) => s + c.pct, 0) * 100) / 100,
    [coins],
  );

  function applyRules(rules: TradingRulesSettings) {
    const normalized = normalizeTradingRules(rules);
    setCoins(normalized.coins);
    setEntryTimeframes(normalized.entryTimeframes);
    setEmergencyExitTimeframes(normalized.emergencyExitTimeframes);
    setEngulfingLookbackCandles(normalized.engulfingLookbackCandles);
    setFvgRetrace(normalized.fvgRetrace);
    setMaxLeverage(normalized.maxLeverage);
    setDailyDrawdown(normalized.dailyDrawdown);
    setTpPct(normalized.tpPct);
    setSlPct(normalized.slPct);
    setAutoConfirm(normalized.autoConfirm);
  }

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const response = await getTradingRules();
        if (!active) return;
        applyRules(response.rules);
        setSaveInfo('Настройки загружены с сервера');
      } catch (error) {
        console.error('[TradingRules] failed to load rules:', error);
        if (!active) return;
        applyRules(defaults);
        setSaveInfo('Не удалось загрузить настройки — использованы значения по умолчанию');
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  function currentRules(): TradingRulesSettings {
    return normalizeTradingRules({
      coins,
      entryTimeframes,
      emergencyExitTimeframes,
      engulfingLookbackCandles,
      fvgRetrace,
      maxLeverage,
      dailyDrawdown,
      tpPct,
      slPct,
      autoConfirm,
    });
  }

  function toggleCoin(idx: number) {
    setCoins(prev => prev.map((c, i) => (i === idx ? { ...c, enabled: !c.enabled } : c)));
  }

  function setCoinPct(idx: number, pct: number) {
    setCoins(prev => prev.map((c, i) => (i === idx ? { ...c, pct: clampNumber(pct, 0, 100) } : c)));
  }

  async function handleApply() {
    const rules = currentRules();
    const enabled = rules.coins.filter(c => c.enabled);
    const enabledTotal = Math.round(enabled.reduce((s, c) => s + c.pct, 0) * 100) / 100;

    if (enabled.length === 0) {
      alert('Нужно включить хотя бы одну монету.');
      return;
    }

    if (Math.abs(enabledTotal - 100) > 0.01) {
      alert(`Сумма allocation активных монет = ${enabledTotal}%. Должно быть 100%.`);
      return;
    }

    setSaving(true);
    setSaveInfo('Сохраняю на сервере...');

    try {
      const response = await saveTradingRules(rules);
      applyRules(response.rules);
      setSaveInfo(`Сохранено на сервере (${new Date().toLocaleTimeString()})`);
    } catch (error) {
      console.error('[TradingRules] failed to save rules:', error);
      setSaveInfo('Ошибка сохранения. Значения не были подтверждены сервером.');
      alert('Не удалось сохранить настройки на сервере. Проверь лог сервера.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="terminal-layout">
      {loading ? (
        <Card title="Trading Rules" actions={<Badge tone="neutral">Loading</Badge>}>
          <p className="muted">Загрузка настроек с сервера...</p>
        </Card>
      ) : null}

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
        <p className="stat-note muted">Сумма активных: {totalPct}%</p>
      </Card>

      <Card title="Timeframe Selection" actions={<Badge tone="neutral">Entry / Exit</Badge>}>
        <div className="rules-section">
          <p className="rules-label">Entry timeframes (multi-select)</p>
          <div className="rules-btn-group">
            {TIMEFRAMES.map(tf => (
              <Button
                key={tf}
                variant={entryTimeframes.includes(tf) ? 'primary' : 'secondary'}
                onClick={() => setEntryTimeframes(prev => {
                  if (prev.includes(tf)) {
                    const next = prev.filter(t => t !== tf);
                    return next.length > 0 ? next : prev;
                  }
                  return [...prev, tf];
                })}
              >
                {tf}
              </Button>
            ))}
          </div>
        </div>

        <div className="rules-section">
          <p className="rules-label">Emergency-exit timeframes (multi-select)</p>
          <div className="rules-btn-group">
            {TIMEFRAMES.map(tf => (
              <Button
                key={tf}
                variant={emergencyExitTimeframes.includes(tf) ? 'primary' : 'secondary'}
                onClick={() => setEmergencyExitTimeframes(prev => {
                  if (prev.includes(tf)) {
                    const next = prev.filter(t => t !== tf);
                    return next.length > 0 ? next : prev;
                  }
                  return [...prev, tf];
                })}
              >
                {tf}
              </Button>
            ))}
          </div>
        </div>

        <div className="rules-section">
          <label className="rules-label">
            Engulfing Lookback: <strong>{engulfingLookbackCandles}</strong> candles
          </label>
          <input
            type="number"
            min={1}
            max={500}
            value={engulfingLookbackCandles}
            onChange={e => setEngulfingLookbackCandles(clampNumber(Number(e.target.value), 1, 500))}
            className="rules-input rules-input--sm"
          />
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
            onChange={e => setFvgRetrace(clampNumber(Number(e.target.value), 10, 90))}
            className="rules-range"
          />
        </div>
      </Card>

      <Card title="Risk Management" actions={<Badge tone="danger">Risk</Badge>}>
        <div className="rules-form-grid">
          <label className="rules-field">
            <span className="rules-label">Max Leverage</span>
            <input
              type="range"
              min={1}
              max={20}
              value={maxLeverage}
              onChange={e => setMaxLeverage(clampNumber(Number(e.target.value), 1, 20))}
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
                onChange={e => setDailyDrawdown(clampNumber(Number(e.target.value), 0, 100))}
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
                onChange={e => setTpPct(clampNumber(Number(e.target.value), 0, 100))}
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
                onChange={e => setSlPct(clampNumber(Number(e.target.value), 0, 100))}
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

      <div className="rules-apply-row">
        <Button variant="primary" fullWidth onClick={handleApply} disabled={saving || loading}>
          {saving ? 'Сохранение...' : 'Применить'}
        </Button>
      </div>

      {saveInfo ? <p className="stat-note muted">{saveInfo}</p> : null}
    </main>
  );
}
