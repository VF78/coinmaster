import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import type { TradingCoinAllocation, TradingRulesSettings, TradingRulesTimeframe } from '../../shared/dto.js';
import { cloneTradingRulesDefaults, normalizeTradingRules } from '../../shared/tradingRules.js';
import { getTradingRules, saveTradingRules } from '../lib/api';

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];
const EXIT_CLOSE_PRESETS = [25, 50, 75, 100];

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

// ─── Number Stepper ─────────────────────────────────────────────────
interface StepperProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  decimals?: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}

function Stepper({ value, min, max, step = 1, unit = '', decimals = 0, onChange, disabled = false }: StepperProps) {
  const dec = decimals;
  const display = dec > 0 ? value.toFixed(dec) : String(value);
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 0, border: '1px solid var(--border, #333)', borderRadius: 6, overflow: 'hidden', userSelect: 'none' }}>
      <button
        type="button"
        disabled={disabled || value <= min}
        onClick={() => onChange(+(Math.max(min, value - step).toFixed(dec + 2)))}
        style={{ width: 32, height: 34, border: 'none', background: 'var(--surface2, #1a1a1a)', color: 'var(--text, #ccc)', fontSize: 18, cursor: disabled || value <= min ? 'not-allowed' : 'pointer', opacity: disabled || value <= min ? 0.4 : 1, fontWeight: 400 }}
      >−</button>
      <span style={{ minWidth: 52, textAlign: 'center', padding: '0 6px', fontSize: 13, color: 'var(--text, #eee)', background: 'var(--surface, #111)', height: 34, lineHeight: '34px', display: 'inline-block' }}>
        {display}{unit}
      </span>
      <button
        type="button"
        disabled={disabled || value >= max}
        onClick={() => onChange(+(Math.min(max, value + step).toFixed(dec + 2)))}
        style={{ width: 32, height: 34, border: 'none', background: 'var(--surface2, #1a1a1a)', color: 'var(--text, #ccc)', fontSize: 18, cursor: disabled || value >= max ? 'not-allowed' : 'pointer', opacity: disabled || value >= max ? 0.4 : 1, fontWeight: 400 }}
      >+</button>
    </div>
  );
}

// ─── Segmented (pill) buttons ────────────────────────────────────────
interface SegmentedProps<T extends string | number> {
  options: T[];
  value: T;
  format?: (v: T) => string;
  onChange: (v: T) => void;
}

function Segmented<T extends string | number>({ options, value, format, onChange }: SegmentedProps<T>) {
  return (
    <div style={{ display: 'inline-flex', border: '1px solid var(--border, #333)', borderRadius: 6, overflow: 'hidden' }}>
      {options.map((opt, i) => {
        const active = opt === value;
        return (
          <button
            key={i}
            type="button"
            onClick={() => onChange(opt)}
            style={{
              padding: '6px 14px', border: 'none', borderLeft: i > 0 ? '1px solid var(--border, #333)' : 'none',
              background: active ? 'var(--accent, #4f8ef7)' : 'var(--surface2, #1a1a1a)',
              color: active ? '#fff' : 'var(--text-muted, #888)', fontSize: 13,
              cursor: 'pointer', fontWeight: active ? 600 : 400,
            }}
          >
            {format ? format(opt) : String(opt)}
          </button>
        );
      })}
    </div>
  );
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
  const [tpLevels, setTpLevels] = useState<number[]>(defaults.tpLevels ?? [defaults.tpPct]);
  const [slPct, setSlPct] = useState(defaults.slPct);
  const [exitClosePct, setExitClosePct] = useState(defaults.exitClosePct ?? 50);
  const [autoConfirm, setAutoConfirm] = useState(defaults.autoConfirm);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveInfo, setSaveInfo] = useState<string>('');

  const totalPct = useMemo(
    () => Math.round(coins.filter(c => c.enabled).reduce((s, c) => s + c.pct, 0) * 100) / 100,
    [coins],
  );

  function applyRules(rules: TradingRulesSettings) {
    const n = normalizeTradingRules(rules);
    setCoins(n.coins);
    setEntryTimeframes(n.entryTimeframes);
    setEmergencyExitTimeframes(n.emergencyExitTimeframes);
    setEngulfingLookbackCandles(n.engulfingLookbackCandles);
    setFvgRetrace(n.fvgRetrace);
    setMaxLeverage(n.maxLeverage);
    setDailyDrawdown(n.dailyDrawdown);
    setTpLevels(n.tpLevels ?? [n.tpPct]);
    setSlPct(n.slPct);
    setExitClosePct(n.exitClosePct ?? 50);
    setAutoConfirm(n.autoConfirm);
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
    return () => { active = false; };
  }, []);

  function currentRules(): TradingRulesSettings {
    return normalizeTradingRules({
      coins, entryTimeframes, emergencyExitTimeframes, engulfingLookbackCandles,
      fvgRetrace, maxLeverage, dailyDrawdown,
      tpPct: tpLevels[0] ?? 6, tpLevels, slPct, exitClosePct, autoConfirm,
    });
  }

  function toggleCoin(idx: number) {
    setCoins(prev => prev.map((c, i) => (i === idx ? { ...c, enabled: !c.enabled } : c)));
  }
  function setCoinPct(idx: number, pct: number) {
    setCoins(prev => prev.map((c, i) => (i === idx ? { ...c, pct: clampNumber(pct, 0, 100) } : c)));
  }

  // ─── TP level helpers ──────────────────────────────────────────────
  function addTpLevel() {
    if (tpLevels.length >= 3) return;
    const last = tpLevels[tpLevels.length - 1] ?? 6;
    setTpLevels(prev => [...prev, clampNumber(Math.round(last * 1.5 * 2) / 2, 0, 100)]);
  }
  function removeTpLevel(idx: number) {
    if (tpLevels.length <= 1) return;
    setTpLevels(prev => prev.filter((_, i) => i !== idx));
  }
  function updateTpLevel(idx: number, value: number) {
    setTpLevels(prev => prev.map((v, i) => (i === idx ? value : v)));
  }

  // ─── TF toggle ────────────────────────────────────────────────────
  function toggleTf(tf: TradingRulesTimeframe, current: TradingRulesTimeframe[], set: (v: TradingRulesTimeframe[]) => void) {
    if (current.includes(tf)) {
      const next = current.filter(t => t !== tf);
      if (next.length > 0) set(next);
    } else {
      set([...current, tf]);
    }
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
      setSaveInfo(`Сохранено (${new Date().toLocaleTimeString()})`);
    } catch (error) {
      console.error('[TradingRules] failed to save rules:', error);
      setSaveInfo('Ошибка сохранения. Значения не подтверждены сервером.');
      alert('Не удалось сохранить настройки. Проверь лог сервера.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="terminal-layout">
      {loading && (
        <Card title="Trading Rules" actions={<Badge tone="neutral">Loading</Badge>}>
          <p className="muted">Загрузка настроек с сервера...</p>
        </Card>
      )}

      {/* ── Coin Distribution ─────────────────────────────────────── */}
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
              <Stepper
                value={c.pct}
                min={0}
                max={100}
                step={1}
                unit="%"
                decimals={0}
                disabled={!c.enabled}
                onChange={v => setCoinPct(i, v)}
              />
            </label>
          ))}
        </div>
        <p className="stat-note muted">Сумма активных: <strong>{totalPct}%</strong></p>
      </Card>

      {/* ── Entry / Exit rules ────────────────────────────────────── */}
      <Card title="Entry / Exit rules" actions={<Badge tone="neutral">Signals</Badge>}>

        {/* Entry timeframe */}
        <div className="rules-section">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
            <p className="rules-label" style={{ margin: 0 }}>
              Entry timeframe <span className="muted" style={{ fontWeight: 400 }}>(Bullish / Bearish Engulfing)</span>
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="muted" style={{ fontSize: 12 }}>Lookback candles</span>
              <Stepper
                value={engulfingLookbackCandles}
                min={5}
                max={200}
                step={5}
                decimals={0}
                onChange={setEngulfingLookbackCandles}
              />
            </div>
          </div>
          <div className="rules-btn-group">
            {TIMEFRAMES.map(tf => (
              <Button
                key={tf}
                variant={entryTimeframes.includes(tf) ? 'primary' : 'secondary'}
                onClick={() => toggleTf(tf, entryTimeframes, setEntryTimeframes)}
              >
                {tf}
              </Button>
            ))}
          </div>
        </div>

        {/* FVG Retrace */}
        <div className="rules-section">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <label className="rules-label" style={{ margin: 0 }}>
              FVG Retrace Level <span className="muted" style={{ fontWeight: 400 }}>(1H/4H)</span>
            </label>
            <strong style={{ fontSize: 14 }}>{fvgRetrace}%</strong>
          </div>
          <input
            type="range"
            min={10}
            max={90}
            value={fvgRetrace}
            onChange={e => setFvgRetrace(clampNumber(Number(e.target.value), 10, 90))}
            className="rules-range"
            style={{ width: '100%' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted, #666)', marginTop: 2 }}>
            <span>10%</span><span>50%</span><span>90%</span>
          </div>
        </div>

        {/* Exit timeframe */}
        <div className="rules-section">
          <p className="rules-label" style={{ marginBottom: 8 }}>
            Exit timeframe <span className="muted" style={{ fontWeight: 400 }}>(Opposite Engulfing)</span>
          </p>
          <div className="rules-btn-group" style={{ marginBottom: 12 }}>
            {TIMEFRAMES.map(tf => (
              <Button
                key={tf}
                variant={emergencyExitTimeframes.includes(tf) ? 'primary' : 'secondary'}
                onClick={() => toggleTf(tf, emergencyExitTimeframes, setEmergencyExitTimeframes)}
              >
                {tf}
              </Button>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span className="muted" style={{ fontSize: 12 }}>Close on exit signal</span>
            <Segmented
              options={EXIT_CLOSE_PRESETS}
              value={EXIT_CLOSE_PRESETS.includes(exitClosePct) ? exitClosePct : 50}
              format={v => `${v}%`}
              onChange={setExitClosePct}
            />
            {!EXIT_CLOSE_PRESETS.includes(exitClosePct) && (
              <span style={{ fontSize: 12, color: 'var(--accent, #4f8ef7)' }}>{exitClosePct}%</span>
            )}
          </div>
          <p className="stat-note muted" style={{ marginTop: 6, fontSize: 11 }}>
            {exitClosePct < 100
              ? `При частичном закрытии (${exitClosePct}%) — SL переносится на цену входа (безубыток)`
              : 'Полное закрытие позиции'}
          </p>
        </div>
      </Card>

      {/* ── Risk Management ───────────────────────────────────────── */}
      <Card title="Risk Management" actions={<Badge tone="danger">Risk</Badge>}>
        <div className="rules-form-grid">
          <div className="rules-field">
            <span className="rules-label">Max Leverage</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
              <input
                type="range"
                min={1}
                max={20}
                value={maxLeverage}
                onChange={e => setMaxLeverage(clampNumber(Number(e.target.value), 1, 20))}
                className="rules-range"
                style={{ flex: 1 }}
              />
              <Stepper value={maxLeverage} min={1} max={20} step={1} unit="x" decimals={0} onChange={setMaxLeverage} />
            </div>
          </div>

          <div className="rules-field">
            <span className="rules-label">Daily Drawdown Limit</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
              <Stepper value={dailyDrawdown} min={0} max={100} step={0.5} unit="%" decimals={1} onChange={setDailyDrawdown} />
            </div>
          </div>
        </div>
        <p className="stat-note muted">
          Рекомендация: leverage ≤ 5x, drawdown ≤ 3% для консервативной стратегии.
        </p>
      </Card>

      {/* ── Default TP / SL ───────────────────────────────────────── */}
      <Card title="Default TP / SL" actions={<Badge tone="success">Targets</Badge>}>
        {/* TP levels */}
        <div className="rules-section">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <p className="rules-label" style={{ margin: 0 }}>Take Profits</p>
            {tpLevels.length < 3 && (
              <button
                type="button"
                onClick={addTpLevel}
                style={{ fontSize: 12, color: 'var(--accent, #4f8ef7)', background: 'none', border: '1px solid var(--accent, #4f8ef7)', borderRadius: 4, padding: '3px 10px', cursor: 'pointer' }}
              >
                + Add TP level
              </button>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {tpLevels.map((tp, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ minWidth: 30, fontSize: 12, color: 'var(--text-muted, #888)', fontWeight: 600 }}>
                  TP{i + 1}
                </span>
                <Stepper
                  value={tp}
                  min={0.5}
                  max={100}
                  step={0.5}
                  unit="%"
                  decimals={1}
                  onChange={v => updateTpLevel(i, v)}
                />
                {tpLevels.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeTpLevel(i)}
                    style={{ fontSize: 16, color: 'var(--danger, #e05c5c)', background: 'none', border: 'none', cursor: 'pointer', lineHeight: 1, padding: '0 4px' }}
                    title="Удалить уровень"
                  >
                    ×
                  </button>
                )}
                {i === 0 && tpLevels.length > 1 && (
                  <span className="muted" style={{ fontSize: 11 }}>→ SL на вход</span>
                )}
              </div>
            ))}
          </div>

          {tpLevels.length > 1 && (
            <p className="stat-note muted" style={{ marginTop: 8, fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ color: 'var(--accent, #4f8ef7)' }}>ℹ</span>
              После срабатывания TP1 — SL автоматически переносится на цену входа (безубыток)
            </p>
          )}
        </div>

        {/* SL */}
        <div className="rules-section">
          <p className="rules-label" style={{ marginBottom: 8 }}>Stop Loss</p>
          <Stepper value={slPct} min={0.5} max={100} step={0.5} unit="%" decimals={1} onChange={setSlPct} />
        </div>

        {/* R:R ratio */}
        <p className="stat-note muted">
          R:R (TP1 : SL) ={' '}
          <strong>
            {slPct > 0 ? ((tpLevels[0] ?? 0) / slPct).toFixed(1) : '—'}:1
          </strong>
          {tpLevels.length > 1 && (
            <span> &nbsp;·&nbsp; TP2 R:R = <strong>{slPct > 0 ? ((tpLevels[1] ?? 0) / slPct).toFixed(1) : '—'}:1</strong></span>
          )}
        </p>
      </Card>

      {/* ── Confirmation Mode ─────────────────────────────────────── */}
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

      {/* ── Apply ─────────────────────────────────────────────────── */}
      <div className="rules-apply-row">
        <Button variant="primary" fullWidth onClick={handleApply} disabled={saving || loading}>
          {saving ? 'Сохранение...' : 'Применить'}
        </Button>
      </div>

      {saveInfo ? <p className="stat-note muted">{saveInfo}</p> : null}
    </main>
  );
}
