import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import type {
  AssetClass,
  BiasMode,
  BiasPolicySymbolOverride,
  TradingCoinAllocation,
  TradingRulesSettings,
  TradingRulesTimeframe
} from '../../shared/dto.js';
import { cloneTradingRulesDefaults, inferAssetClassFromSymbol, normalizeTradingRules } from '../../shared/tradingRules.js';
import { friendlyErrorMessage, getTradingRuleSymbols, getTradingRules, saveTradingRules } from '../lib/api';
import { useDialog } from '../components/DialogProvider';

const TIMEFRAMES: TradingRulesTimeframe[] = ['5m', '15m', '1h', '4h'];
const ASSET_CLASSES: AssetClass[] = ['crypto', 'commodity', 'forex', 'index', 'other'];
const BIAS_MODE_OPTIONS: Array<{ value: BiasMode; label: string }> = [
  { value: 'global', label: 'shared' },
  { value: 'symbol', label: 'custom' },
];
const EXIT_CLOSE_PRESETS = [0, 25, 50, 75, 100];

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function normalizeAssetSymbol(value: string): string {
  const raw = String(value || '').trim();
  if (!raw) return '';

  if (raw.includes(':')) {
    const [namespaceRaw, symbolRaw] = raw.split(':', 2);
    const namespace = String(namespaceRaw || '').trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
    const symbol = String(symbolRaw || '').trim().toUpperCase().replace(/[^A-Z0-9_-]/g, '');
    if (!namespace || !symbol) return '';
    return `${namespace}:${symbol}`;
  }

  return raw.toUpperCase().replace(/[^A-Z0-9_-]/g, '');
}

function cloneSymbolOverrides(input?: Record<string, BiasPolicySymbolOverride>): Record<string, BiasPolicySymbolOverride> {
  return Object.fromEntries(
    Object.entries(input ?? {})
      .map(([key, value]) => {
        const symbol = normalizeAssetSymbol(key);
        if (!symbol || !value) return null;
        const mode: BiasMode = value.mode === 'global' ? 'global' : 'symbol';
        return [symbol, { mode } satisfies BiasPolicySymbolOverride] as const;
      })
      .filter((x): x is readonly [string, BiasPolicySymbolOverride] => Boolean(x))
  );
}

interface TradingRulesPageProps {
  onDirtyChange?: (dirty: boolean) => void;
  onRegisterSaveHandler?: (handler: (() => Promise<boolean>) | null) => void;
}

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
  const display = decimals > 0 ? value.toFixed(decimals) : String(value);
  return (
    <div className="rules-stepper" role="group" aria-label="Number stepper">
      <button
        type="button"
        className="rules-stepper__btn"
        disabled={disabled || value <= min}
        onClick={() => onChange(+(Math.max(min, value - step).toFixed(decimals + 2)))}
      >−</button>
      <span className="rules-stepper__value">
        {display}{unit}
      </span>
      <button
        type="button"
        className="rules-stepper__btn"
        disabled={disabled || value >= max}
        onClick={() => onChange(+(Math.min(max, value + step).toFixed(decimals + 2)))}
      >+</button>
    </div>
  );
}

interface SegmentedProps<T extends string | number> {
  options: T[];
  value: T;
  format?: (v: T) => string;
  onChange: (v: T) => void;
}

function Segmented<T extends string | number>({ options, value, format, onChange }: SegmentedProps<T>) {
  return (
    <div className="rules-segmented" role="tablist" aria-label="Segmented control">
      {options.map((opt, i) => {
        const active = opt === value;
        return (
          <button
            key={i}
            type="button"
            className={`rules-segmented__btn ${active ? 'rules-segmented__btn--active' : ''}`}
            onClick={() => onChange(opt)}
          >
            {format ? format(opt) : String(opt)}
          </button>
        );
      })}
    </div>
  );
}

export function TradingRulesPage({ onDirtyChange, onRegisterSaveHandler }: TradingRulesPageProps) {
  const defaults = cloneTradingRulesDefaults();
  const dialog = useDialog();

  const [coins, setCoins] = useState<TradingCoinAllocation[]>(defaults.coins);
  const [availableSymbols, setAvailableSymbols] = useState<string[]>([]);
  const [newSymbol, setNewSymbol] = useState('');
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
  const [symbolBiasOverrides, setSymbolBiasOverrides] = useState<Record<string, BiasPolicySymbolOverride>>(
    cloneSymbolOverrides(defaults.biasPolicy?.symbolOverrides)
  );

  const [savedRules, setSavedRules] = useState<TradingRulesSettings>(() => normalizeTradingRules(defaults));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveInfo, setSaveInfo] = useState<string>('');

  const totalPct = useMemo(
    () => Math.round(coins.filter((c) => c.enabled).reduce((s, c) => s + c.pct, 0) * 100) / 100,
    [coins],
  );

  const currentRules = useMemo<TradingRulesSettings>(() => normalizeTradingRules({
    coins,
    entryTimeframes,
    emergencyExitTimeframes,
    engulfingLookbackCandles,
    fvgRetrace,
    maxLeverage,
    dailyDrawdown,
    tpPct: tpLevels[0] ?? 6,
    tpLevels,
    slPct,
    exitClosePct,
    autoConfirm,
    biasPolicy: {
      symbolOverrides: cloneSymbolOverrides(symbolBiasOverrides),
    },
  }), [
    coins,
    entryTimeframes,
    emergencyExitTimeframes,
    engulfingLookbackCandles,
    fvgRetrace,
    maxLeverage,
    dailyDrawdown,
    tpLevels,
    slPct,
    exitClosePct,
    autoConfirm,
    symbolBiasOverrides,
  ]);

  const isDirty = useMemo(
    () => JSON.stringify(currentRules) !== JSON.stringify(savedRules),
    [currentRules, savedRules],
  );

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);

  useEffect(() => {
    if (!isDirty) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  function applyRules(rules: TradingRulesSettings) {
    const normalized = normalizeTradingRules(rules);
    setCoins(normalized.coins);
    setEntryTimeframes(normalized.entryTimeframes);
    setEmergencyExitTimeframes(normalized.emergencyExitTimeframes);
    setEngulfingLookbackCandles(normalized.engulfingLookbackCandles);
    setFvgRetrace(normalized.fvgRetrace);
    setMaxLeverage(normalized.maxLeverage);
    setDailyDrawdown(normalized.dailyDrawdown);
    setTpLevels(normalized.tpLevels ?? [normalized.tpPct]);
    setSlPct(normalized.slPct);
    setExitClosePct(normalized.exitClosePct ?? 50);
    setAutoConfirm(normalized.autoConfirm);
    setSymbolBiasOverrides(cloneSymbolOverrides(normalized.biasPolicy?.symbolOverrides));
    setSavedRules(normalized);
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [rulesResponse, symbolsResponse] = await Promise.all([
          getTradingRules(),
          getTradingRuleSymbols().catch(() => null),
        ]);
        if (!active) return;

        const configuredSymbols = (rulesResponse.rules.coins ?? [])
          .map((coin) => normalizeAssetSymbol(coin.symbol))
          .filter(Boolean);
        const exchangeSymbols = symbolsResponse?.symbols ?? [];
        const mergedSymbols = [...new Set([...exchangeSymbols, ...configuredSymbols])].sort((a, b) => a.localeCompare(b));

        setAvailableSymbols(mergedSymbols);
        applyRules(rulesResponse.rules);
        setSaveInfo('Rules loaded from server.');
      } catch (error) {
        console.error('[TradingRules] failed to load rules:', error);
        if (!active) return;
        applyRules(defaults);
        setAvailableSymbols(defaults.coins.map((c) => normalizeAssetSymbol(c.symbol)).filter(Boolean));
        setSaveInfo('Could not load rules. Defaults were applied.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function toggleCoin(idx: number) {
    setCoins((prev) => prev.map((c, i) => (i === idx ? { ...c, enabled: !c.enabled } : c)));
  }

  function setCoinSymbol(idx: number, symbol: string) {
    const normalized = normalizeAssetSymbol(symbol);
    const previousSymbol = normalizeAssetSymbol(coins[idx]?.symbol ?? '');

    setCoins((prev) => prev.map((c, i) => {
      if (i !== idx) return c;
      const nextSymbol = normalized;
      return {
        ...c,
        symbol: nextSymbol,
        assetClass: nextSymbol ? inferAssetClassFromSymbol(nextSymbol) : c.assetClass,
      };
    }));

    if (previousSymbol !== normalized) {
      setSymbolBiasOverrides((prev) => {
        const next = { ...prev };
        const existing = previousSymbol ? next[previousSymbol] : undefined;
        if (previousSymbol) delete next[previousSymbol];
        if (normalized && existing) next[normalized] = existing;
        return next;
      });
    }
  }

  function setCoinPct(idx: number, pct: number) {
    setCoins((prev) => prev.map((c, i) => (i === idx ? { ...c, pct: clampNumber(pct, 0, 100) } : c)));
  }

  function setCoinAssetClass(idx: number, assetClass: AssetClass) {
    setCoins((prev) => prev.map((c, i) => (i === idx ? { ...c, assetClass } : c)));
  }

  function removeCoin(idx: number) {
    const symbolToRemove = normalizeAssetSymbol(coins[idx]?.symbol ?? '');
    setCoins((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((_, i) => i !== idx);
    });

    if (symbolToRemove) {
      setSymbolBiasOverrides((prev) => {
        if (!prev[symbolToRemove]) return prev;
        const next = { ...prev };
        delete next[symbolToRemove];
        return next;
      });
    }
  }

  async function addCoinFromInput(): Promise<void> {
    const symbol = normalizeAssetSymbol(newSymbol);
    if (!symbol) {
      await dialog.alert({
        title: 'Validation',
        message: 'Enter a symbol first (example: GOLDUSDC).',
        confirmText: 'OK',
      });
      return;
    }

    if (coins.some((coin) => normalizeAssetSymbol(coin.symbol) === symbol)) {
      await dialog.alert({
        title: 'Validation',
        message: `${symbol} is already in the list.`,
        confirmText: 'OK',
      });
      return;
    }

    if (availableSymbols.length > 0 && !availableSymbols.includes(symbol)) {
      await dialog.alert({
        title: 'Validation',
        message: `${symbol} is not present in the exchange symbol catalog.`,
        confirmText: 'OK',
      });
      return;
    }

    setCoins((prev) => [...prev, { symbol, enabled: true, pct: 0, assetClass: inferAssetClassFromSymbol(symbol) }]);
    setNewSymbol('');
  }

  function addTpLevel() {
    if (tpLevels.length >= 3) return;
    const last = tpLevels[tpLevels.length - 1] ?? 6;
    setTpLevels((prev) => [...prev, clampNumber(Math.round(last * 1.5 * 2) / 2, 0.5, 100)]);
  }

  function removeTpLevel(idx: number) {
    if (tpLevels.length <= 1) return;
    setTpLevels((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateTpLevel(idx: number, value: number) {
    setTpLevels((prev) => prev.map((v, i) => (i === idx ? value : v)));
  }

  function toggleTf(
    timeframe: TradingRulesTimeframe,
    current: TradingRulesTimeframe[],
    set: (v: TradingRulesTimeframe[]) => void,
  ) {
    if (current.includes(timeframe)) {
      const next = current.filter((tf) => tf !== timeframe);
      if (next.length > 0) set(next);
    } else {
      set([...current, timeframe]);
    }
  }

  function getRowBiasMode(coin: TradingCoinAllocation): BiasMode {
    const symbol = normalizeAssetSymbol(coin.symbol);
    const override = symbol ? symbolBiasOverrides[symbol] : undefined;
    return override?.mode ?? 'global';
  }

  function setRowBiasMode(coin: TradingCoinAllocation, mode: BiasMode) {
    const symbol = normalizeAssetSymbol(coin.symbol);
    if (!symbol) return;

    setSymbolBiasOverrides((prev) => {
      const next = { ...prev };
      if (mode === 'global') {
        delete next[symbol];
        return next;
      }

      next[symbol] = { mode: 'symbol' };
      return next;
    });
  }

  async function handleApply(): Promise<boolean> {
    const normalizedSymbols = coins.map((coin) => normalizeAssetSymbol(coin.symbol));
    const hasEmptySymbol = normalizedSymbols.some((symbol) => symbol.length === 0);
    if (hasEmptySymbol) {
      await dialog.alert({
        title: 'Validation',
        message: 'Each asset row must have a valid symbol.',
        confirmText: 'OK',
      });
      return false;
    }

    const duplicateSymbols = normalizedSymbols.filter((symbol, idx) => normalizedSymbols.indexOf(symbol) !== idx);
    if (duplicateSymbols.length > 0) {
      await dialog.alert({
        title: 'Validation',
        message: `Duplicate symbols are not allowed: ${[...new Set(duplicateSymbols)].join(', ')}`,
        confirmText: 'OK',
      });
      return false;
    }

    const payload = normalizeTradingRules({
      ...currentRules,
      coins: coins.map((coin, idx) => ({
        ...coin,
        symbol: normalizedSymbols[idx],
      })),
    });

    const enabled = payload.coins.filter((c) => c.enabled);
    const enabledTotal = Math.round(enabled.reduce((s, c) => s + c.pct, 0) * 100) / 100;

    if (enabled.length === 0) {
      await dialog.alert({
        title: 'Validation',
        message: 'Enable at least one coin.',
        confirmText: 'OK',
      });
      return false;
    }

    if (Math.abs(enabledTotal - 100) > 0.01) {
      await dialog.alert({
        title: 'Validation',
        message: `Active coin allocation sum is ${enabledTotal}%. It must be exactly 100%.`,
        confirmText: 'OK',
      });
      return false;
    }

    setSaving(true);
    setSaveInfo('Saving rules...');
    try {
      const response = await saveTradingRules(payload);
      applyRules(response.rules);
      setSaveInfo(`Saved at ${new Date().toLocaleTimeString()}`);
      return true;
    } catch (error) {
      console.error('[TradingRules] failed to save rules:', error);
      const msg = friendlyErrorMessage(error, 'Could not save rules. Check server logs.');
      setSaveInfo(`Save failed: ${msg}`);
      await dialog.alert({
        title: 'Save failed',
        message: msg,
        confirmText: 'OK',
      });
      return false;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    if (!onRegisterSaveHandler) return;
    onRegisterSaveHandler(() => handleApply());
    return () => onRegisterSaveHandler(null);
  }, [onRegisterSaveHandler, currentRules, coins, entryTimeframes, emergencyExitTimeframes, engulfingLookbackCandles, fvgRetrace, maxLeverage, dailyDrawdown, tpLevels, slPct, exitClosePct, autoConfirm, symbolBiasOverrides]);

  return (
    <main className="terminal-layout">
      {loading && (
        <Card title="Trading Rules" actions={<Badge tone="neutral">Loading</Badge>}>
          <p className="muted">Loading rules from server...</p>
        </Card>
      )}

      <Card title="Coin Distribution" actions={<Badge tone="neutral">Allocation</Badge>}>
        <div className="rules-grid">
          {coins.map((coin, idx) => {
            const normalizedSymbol = normalizeAssetSymbol(coin.symbol);
            const rowAssetClass = coin.assetClass ?? inferAssetClassFromSymbol(normalizedSymbol);
            const rowBiasMode = getRowBiasMode(coin);

            return (
              <div key={`${coin.symbol || 'asset'}-${idx}`} className="rules-coin-row">
                <input
                  type="checkbox"
                  checked={coin.enabled}
                  onChange={() => toggleCoin(idx)}
                  className="rules-checkbox"
                />

                <input
                  type="text"
                  value={coin.symbol}
                  onChange={(e) => setCoinSymbol(idx, e.target.value)}
                  className="rules-input"
                  style={{ width: 130, textTransform: 'uppercase' }}
                  list="coinmaster-tradable-symbols"
                  placeholder="SYMBOL"
                />

                <Stepper
                  value={coin.pct}
                  min={0}
                  max={100}
                  step={1}
                  unit="%"
                  decimals={0}
                  disabled={!coin.enabled}
                  onChange={(v) => setCoinPct(idx, v)}
                />

                <select
                  className="rules-input"
                  value={rowAssetClass}
                  onChange={(e) => setCoinAssetClass(idx, e.target.value as AssetClass)}
                  style={{ width: 120 }}
                  title="Asset class"
                >
                  {ASSET_CLASSES.map((assetClass) => (
                    <option key={assetClass} value={assetClass}>{assetClass}</option>
                  ))}
                </select>

                <select
                  className="rules-input"
                  value={rowBiasMode}
                  onChange={(e) => setRowBiasMode(coin, e.target.value as BiasMode)}
                  style={{ width: 110 }}
                  title="Bias mode"
                >
                  {BIAS_MODE_OPTIONS.map((mode) => (
                    <option key={mode.value} value={mode.value}>{mode.label}</option>
                  ))}
                </select>

                <span className="muted" style={{ minWidth: 130, textAlign: 'center', fontSize: 12 }}>
                  {rowBiasMode === 'global' ? 'uses class bias' : 'custom bias in dashboard'}
                </span>

                <Button
                  type="button"
                  variant="danger"
                  className="rules-mini-btn"
                  onClick={() => removeCoin(idx)}
                  disabled={coins.length <= 1}
                  title={coins.length <= 1 ? 'At least one asset row is required' : 'Remove asset'}
                >
                  Remove
                </Button>
              </div>
            );
          })}
        </div>

        <datalist id="coinmaster-tradable-symbols">
          {availableSymbols.map((symbol) => (
            <option key={symbol} value={symbol} />
          ))}
        </datalist>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, marginTop: 10 }}>
          <input
            type="text"
            value={newSymbol}
            onChange={(e) => setNewSymbol(normalizeAssetSymbol(e.target.value))}
            className="rules-input"
            list="coinmaster-tradable-symbols"
            placeholder="Add asset (e.g. GOLDUSDC)"
          />
          <Button type="button" variant="secondary" onClick={() => { void addCoinFromInput(); }}>+ Add asset</Button>
        </div>

        <p className="stat-note muted">Active total: <strong>{totalPct}%</strong></p>

        <p className="stat-note muted" style={{ marginTop: 8 }}>
          Bias direction controls moved to Dashboard → Execution controls. Here you only choose mode per asset: shared class bias or custom.
        </p>
      </Card>

      <Card title="Entry / Exit Rules" actions={<Badge tone="neutral">Signals</Badge>}>
        <div className="rules-section">
          <p className="rules-label" style={{ marginBottom: 8 }}>
            Entry timeframe <span className="muted" style={{ fontWeight: 400 }}>(Bullish / Bearish Engulfing)</span>
          </p>
          <div className="rules-btn-group rules-btn-group--left">
            {TIMEFRAMES.map((tf) => (
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

        <div
          className="rules-section"
          style={{
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '0.8rem',
            background: 'linear-gradient(180deg, var(--surface-2) 0%, #0f1c2e 100%)',
          }}
        >
          <p className="rules-label" style={{ marginBottom: 10 }}>
            Signal Sensitivity (Engulfing + FVG)
          </p>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 14,
              alignItems: 'center',
            }}
          >
            <div style={{ display: 'grid', gap: 6, justifyItems: 'start' }}>
              <span className="rules-label" style={{ margin: 0 }}>Lookback candles</span>
              <Stepper
                value={engulfingLookbackCandles}
                min={5}
                max={200}
                step={5}
                decimals={0}
                onChange={setEngulfingLookbackCandles}
              />
            </div>
            <div style={{ display: 'grid', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="rules-label" style={{ margin: 0 }}>FVG Retrace Level (1H/4H)</span>
                <strong style={{ fontSize: 14 }}>{fvgRetrace}%</strong>
              </div>
              <input
                type="range"
                min={10}
                max={90}
                value={fvgRetrace}
                onChange={(e) => setFvgRetrace(clampNumber(Number(e.target.value), 10, 90))}
                className="rules-range"
                style={{ width: '100%', marginTop: 0 }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted, #666)' }}>
                <span>10%</span><span>50%</span><span>90%</span>
              </div>
            </div>
          </div>
        </div>

        <div className="rules-section">
          <p className="rules-label" style={{ marginBottom: 8 }}>
            Exit timeframe <span className="muted" style={{ fontWeight: 400 }}>(Opposite Engulfing)</span>
          </p>
          <div className="rules-btn-group rules-btn-group--left rules-btn-group--mb">
            {TIMEFRAMES.map((tf) => (
              <Button
                key={tf}
                variant={emergencyExitTimeframes.includes(tf) ? 'primary' : 'secondary'}
                onClick={() => toggleTf(tf, emergencyExitTimeframes, setEmergencyExitTimeframes)}
              >
                {tf}
              </Button>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'center' }}>
            <span className="rules-label" style={{ margin: 0 }}>Close size on exit signal</span>
            <Segmented
              options={EXIT_CLOSE_PRESETS}
              value={EXIT_CLOSE_PRESETS.includes(exitClosePct) ? exitClosePct : 50}
              format={(v) => `${v}%`}
              onChange={setExitClosePct}
            />
          </div>

          <p className="stat-note muted" style={{ marginTop: 8, fontSize: 11 }}>
            {exitClosePct === 0
              ? '0% disables emergency engulfing exit actions.'
              : exitClosePct < 100
                ? `Partial close (${exitClosePct}%) moves SL to entry (break-even).`
                : '100% closes the full position.'}
          </p>
        </div>
      </Card>

      <Card title="Risk Management" actions={<Badge tone="danger">Risk</Badge>}>
        <div style={{ display: 'grid', gap: 14 }}>
          <div className="rules-field">
            <span className="rules-label">Daily Drawdown Limit</span>
            <Stepper
              value={dailyDrawdown}
              min={0}
              max={100}
              step={0.5}
              unit="%"
              decimals={1}
              onChange={setDailyDrawdown}
            />
          </div>

          <div className="rules-field">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="rules-label" style={{ margin: 0 }}>Max Leverage</span>
              <strong style={{ fontSize: 14 }}>{maxLeverage}x</strong>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              value={maxLeverage}
              onChange={(e) => setMaxLeverage(clampNumber(Number(e.target.value), 1, 20))}
              className="rules-range"
              style={{ marginTop: 0 }}
            />
          </div>
        </div>
        <p className="stat-note muted">Suggested: leverage ≤ 5x and drawdown ≤ 3% for conservative operation.</p>
      </Card>

      <Card title="Default TP / SL" actions={<Badge tone="success">Targets</Badge>}>
        <div className="rules-section rules-levels-grid">
          {tpLevels.map((tp, idx) => (
            <div key={idx} className="rules-level-row">
              <span className="rules-level-tag">TP{idx + 1}</span>
              <Stepper
                value={tp}
                min={0.5}
                max={100}
                step={0.5}
                unit="%"
                decimals={1}
                onChange={(v) => updateTpLevel(idx, v)}
              />

              {idx === 0 && tpLevels.length < 3 ? (
                <Button type="button" variant="secondary" className="rules-mini-btn" onClick={addTpLevel}>+ TP</Button>
              ) : (
                <span className="rules-mini-btn rules-mini-btn--ghost" />
              )}

              {idx > 0 ? (
                <Button
                  type="button"
                  variant="danger"
                  className="rules-mini-btn"
                  onClick={() => removeTpLevel(idx)}
                  title="Remove level"
                >
                  Remove
                </Button>
              ) : (
                <span className="muted rules-level-hint">TP1 → move SL to entry</span>
              )}
            </div>
          ))}

          <div className="rules-level-row">
            <span className="rules-level-tag">SL</span>
            <Stepper value={slPct} min={0.5} max={100} step={0.5} unit="%" decimals={1} onChange={setSlPct} />
            <span className="rules-mini-btn rules-mini-btn--ghost" />
            <span className="rules-mini-btn rules-mini-btn--ghost" />
          </div>
        </div>

        <p className="stat-note muted">
          R:R → TP1: <strong>{slPct > 0 ? ((tpLevels[0] ?? 0) / slPct).toFixed(1) : '—'}:1</strong>
          {tpLevels.length > 1 ? (
            <span> · TP2: <strong>{slPct > 0 ? ((tpLevels[1] ?? 0) / slPct).toFixed(1) : '—'}:1</strong></span>
          ) : null}
          {tpLevels.length > 2 ? (
            <span> · TP3: <strong>{slPct > 0 ? ((tpLevels[2] ?? 0) / slPct).toFixed(1) : '—'}:1</strong></span>
          ) : null}
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
            onClick={() => setAutoConfirm((v) => !v)}
          >
            <span className="rules-toggle__thumb" />
          </button>
        </label>
        <p className="stat-note muted">
          {autoConfirm
            ? 'Orders are submitted automatically without manual confirmation.'
            : 'Each order requires manual confirmation before submission.'}
        </p>
      </Card>

      <div className="rules-apply-row">
        <Button variant="primary" fullWidth onClick={() => { void handleApply(); }} disabled={saving || loading}>
          {saving ? 'Saving...' : 'Apply changes'}
        </Button>
      </div>

      {isDirty ? <p className="stat-note" style={{ color: 'var(--warning, #f59e0b)' }}>You have unsaved changes.</p> : null}
      {saveInfo ? <p className="stat-note muted">{saveInfo}</p> : null}
    </main>
  );
}
