import { useEffect, useMemo, useState, type ReactNode } from 'react';
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
const REGIME_TIMEFRAMES: TradingRulesTimeframe[] = ['1h', '4h'];
const ASSET_CLASSES: AssetClass[] = ['crypto', 'commodity', 'forex', 'index', 'other'];
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
  const display = decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));

  function apply(nextRaw: number) {
    const clamped = clampNumber(nextRaw, min, max);
    onChange(+(clamped.toFixed(decimals + 2)));
  }

  return (
    <div className="rules-stepper" role="group" aria-label="Number stepper">
      <button
        type="button"
        className="rules-stepper__btn"
        disabled={disabled || value <= min}
        onClick={() => apply(value - step)}
      >−</button>

      <div className="rules-stepper__center">
        <input
          type="number"
          className="rules-stepper__input"
          value={display}
          min={min}
          max={max}
          step={step}
          inputMode="decimal"
          disabled={disabled}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === '') return;
            const parsed = Number(raw);
            if (!Number.isFinite(parsed)) return;
            apply(parsed);
          }}
          onBlur={(e) => {
            const parsed = Number(e.target.value);
            if (!Number.isFinite(parsed)) {
              apply(value);
              return;
            }
            apply(parsed);
          }}
        />
        {unit ? <span className="rules-stepper__unit">{unit}</span> : null}
      </div>

      <button
        type="button"
        className="rules-stepper__btn"
        disabled={disabled || value >= max}
        onClick={() => apply(value + step)}
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

interface GuardControlProps {
  label: string;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  children: ReactNode;
  note?: string;
}

function GuardControl({ label, enabled, onToggle, children, note }: GuardControlProps) {
  return (
    <div style={{ display: 'grid', gap: 6, justifyItems: 'start' }}>
      <label className="rules-toggle-row" style={{ width: '100%', gap: 8 }}>
        <span className="rules-label" style={{ margin: 0 }}>{label}</span>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          className={`rules-toggle ${enabled ? 'rules-toggle--on' : ''}`}
          onClick={() => onToggle(!enabled)}
        >
          <span className="rules-toggle__thumb" />
        </button>
      </label>
      <div style={{ opacity: enabled ? 1 : 0.45, pointerEvents: enabled ? 'auto' : 'none' }}>{children}</div>
      {note ? <p className="stat-note muted" style={{ margin: 0 }}>{note}</p> : null}
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
  const [fvgMinWidthPct, setFvgMinWidthPct] = useState(defaults.fvgMinWidthPct);
  const [fvgRequireSweep, setFvgRequireSweep] = useState(defaults.fvgRequireSweep);
  const [fvgSweepLookbackCandles, setFvgSweepLookbackCandles] = useState(defaults.fvgSweepLookbackCandles);
  const [fvgRequireFirstTouch, setFvgRequireFirstTouch] = useState(defaults.fvgRequireFirstTouch);
  const [maxZoneAgeCandles, setMaxZoneAgeCandles] = useState(defaults.maxZoneAgeCandles);
  const [fvgRequireConfirmation, setFvgRequireConfirmation] = useState(defaults.fvgRequireConfirmation);
  const [fvgConfirmationTimeframes, setFvgConfirmationTimeframes] = useState<TradingRulesTimeframe[]>(defaults.fvgConfirmationTimeframes);
  const [maxLeverage, setMaxLeverage] = useState(defaults.maxLeverage);
  const [dailyDrawdown, setDailyDrawdown] = useState(defaults.dailyDrawdown);
  const [tpLevels, setTpLevels] = useState<number[]>(defaults.tpLevels ?? [defaults.tpPct]);
  const [slPct, setSlPct] = useState(defaults.slPct);
  const [exitClosePct, setExitClosePct] = useState(defaults.exitClosePct ?? 50);
  const [regimeFilterEnabled, setRegimeFilterEnabled] = useState(defaults.regimeFilterEnabled ?? true);
  const [regimeTf, setRegimeTf] = useState<TradingRulesTimeframe>(defaults.regimeTf ?? '1h');
  const [adxEnabled, setAdxEnabled] = useState(defaults.adxEnabled ?? false);
  const [adxMin, setAdxMin] = useState(defaults.adxMin ?? 0);
  const [minImpulseAtrEnabled, setMinImpulseAtrEnabled] = useState(defaults.minImpulseAtrEnabled ?? false);
  const [minImpulseAtr, setMinImpulseAtr] = useState(defaults.minImpulseAtr ?? 0);
  const [timeStopEnabled, setTimeStopEnabled] = useState(defaults.timeStopEnabled ?? false);
  const [timeStopBars, setTimeStopBars] = useState(defaults.timeStopBars ?? 0);
  const [riskPerTradeEnabled, setRiskPerTradeEnabled] = useState(defaults.riskPerTradeEnabled ?? false);
  const [riskPerTradePct, setRiskPerTradePct] = useState(defaults.riskPerTradePct ?? 0);
  const [portfolioGrossCapEnabled, setPortfolioGrossCapEnabled] = useState(defaults.portfolioGrossCapEnabled ?? true);
  const [portfolioGrossCap, setPortfolioGrossCap] = useState(defaults.portfolioGrossCap ?? 200);
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
    fvgMinWidthPct,
    fvgRequireSweep,
    fvgSweepLookbackCandles,
    fvgRequireFirstTouch,
    maxZoneAgeCandles,
    fvgRequireConfirmation,
    fvgConfirmationTimeframes,
    maxLeverage,
    dailyDrawdown,
    tpPct: tpLevels[0] ?? 6,
    tpLevels,
    slPct,
    exitClosePct,
    autoConfirm: false,
    regimeFilterEnabled,
    regimeTf,
    adxEnabled,
    adxMin,
    minImpulseAtrEnabled,
    minImpulseAtr,
    timeStopEnabled,
    timeStopBars,
    riskPerTradeEnabled,
    riskPerTradePct,
    eventLockoutEnabled: false,
    eventLockoutMinutes: 0,
    portfolioGrossCapEnabled,
    portfolioGrossCap,
    biasPolicy: {
      symbolOverrides: cloneSymbolOverrides(symbolBiasOverrides),
    },
  }), [
    coins,
    entryTimeframes,
    emergencyExitTimeframes,
    engulfingLookbackCandles,
    fvgRetrace,
    fvgMinWidthPct,
    fvgRequireSweep,
    fvgSweepLookbackCandles,
    fvgRequireFirstTouch,
    maxZoneAgeCandles,
    fvgRequireConfirmation,
    fvgConfirmationTimeframes,
    maxLeverage,
    dailyDrawdown,
    tpLevels,
    slPct,
    exitClosePct,
    regimeFilterEnabled,
    regimeTf,
    adxEnabled,
    adxMin,
    minImpulseAtrEnabled,
    minImpulseAtr,
    timeStopEnabled,
    timeStopBars,
    riskPerTradeEnabled,
    riskPerTradePct,
    portfolioGrossCapEnabled,
    portfolioGrossCap,
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
    setFvgMinWidthPct(normalized.fvgMinWidthPct);
    setFvgRequireSweep(normalized.fvgRequireSweep);
    setFvgSweepLookbackCandles(normalized.fvgSweepLookbackCandles);
    setFvgRequireFirstTouch(normalized.fvgRequireFirstTouch);
    setMaxZoneAgeCandles(normalized.maxZoneAgeCandles);
    setFvgRequireConfirmation(normalized.fvgRequireConfirmation);
    setFvgConfirmationTimeframes(normalized.fvgConfirmationTimeframes);
    setMaxLeverage(normalized.maxLeverage);
    setDailyDrawdown(normalized.dailyDrawdown);
    setTpLevels(normalized.tpLevels ?? [normalized.tpPct]);
    setSlPct(normalized.slPct);
    setExitClosePct(normalized.exitClosePct ?? 50);
    setRegimeFilterEnabled(normalized.regimeFilterEnabled ?? true);
    setRegimeTf(normalized.regimeTf ?? '1h');
    setAdxEnabled(normalized.adxEnabled ?? false);
    setAdxMin(normalized.adxMin ?? 0);
    setMinImpulseAtrEnabled(normalized.minImpulseAtrEnabled ?? false);
    setMinImpulseAtr(normalized.minImpulseAtr ?? 0);
    setTimeStopEnabled(normalized.timeStopEnabled ?? false);
    setTimeStopBars(normalized.timeStopBars ?? 0);
    setRiskPerTradeEnabled(normalized.riskPerTradeEnabled ?? false);
    setRiskPerTradePct(normalized.riskPerTradePct ?? 0);
    setPortfolioGrossCapEnabled(normalized.portfolioGrossCapEnabled ?? true);
    setPortfolioGrossCap(normalized.portfolioGrossCap ?? 200);
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
  }, [onRegisterSaveHandler, currentRules, coins, entryTimeframes, emergencyExitTimeframes, engulfingLookbackCandles, fvgRetrace, fvgMinWidthPct, fvgRequireSweep, fvgSweepLookbackCandles, fvgRequireFirstTouch, maxZoneAgeCandles, fvgRequireConfirmation, fvgConfirmationTimeframes, maxLeverage, dailyDrawdown, tpLevels, slPct, exitClosePct, regimeFilterEnabled, regimeTf, adxEnabled, adxMin, minImpulseAtrEnabled, minImpulseAtr, timeStopEnabled, timeStopBars, riskPerTradeEnabled, riskPerTradePct, portfolioGrossCapEnabled, portfolioGrossCap, symbolBiasOverrides]);

  return (
    <main className="terminal-layout trading-rules-page">
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
          Enabled rows become the Freqtrade pair whitelist. Allocation % caps the maximum margin Freqtrade may use per asset via custom_stake_amount(). Pair whitelist changes require Freqtrade reload/restart; sizing changes are hot-reloaded by the strategy.
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span className="rules-label" style={{ margin: 0 }}>FVG Retrace Level (1H/4H)</span>
                <div className="actions-row">
                  <input
                    type="number"
                    min={10}
                    max={90}
                    step={1}
                    value={fvgRetrace}
                    className="rules-input rules-input--sm"
                    onChange={(e) => setFvgRetrace(clampNumber(Number(e.target.value), 10, 90))}
                  />
                  <strong style={{ fontSize: 14 }}>{fvgRetrace}%</strong>
                </div>
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
            <div style={{ display: 'grid', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span className="rules-label" style={{ margin: 0 }}>FVG Min Width Filter</span>
                <div className="actions-row">
                  <input
                    type="number"
                    min={0}
                    max={10}
                    step={0.1}
                    value={fvgMinWidthPct}
                    className="rules-input rules-input--sm"
                    onChange={(e) => setFvgMinWidthPct(clampNumber(Number(e.target.value), 0, 10))}
                  />
                  <strong style={{ fontSize: 14 }}>{fvgMinWidthPct}%</strong>
                </div>
              </div>
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={fvgMinWidthPct}
                onChange={(e) => setFvgMinWidthPct(clampNumber(Number(e.target.value), 0, 10))}
                className="rules-range"
                style={{ width: '100%', marginTop: 0 }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted, #666)' }}>
                <span>0%</span><span>0.3%</span><span>2%</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gap: 14, marginTop: 14 }}>
            <label className="rules-toggle-row">
              <span>Require HTF sweep</span>
              <button
                type="button"
                role="switch"
                aria-checked={fvgRequireSweep}
                className={`rules-toggle ${fvgRequireSweep ? 'rules-toggle--on' : ''}`}
                onClick={() => setFvgRequireSweep((v) => !v)}
              >
                <span className="rules-toggle__thumb" />
              </button>
            </label>
            {fvgRequireSweep ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 320px)', gap: 14 }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <span className="rules-label" style={{ margin: 0 }}>Sweep lookback candles</span>
                  <Stepper value={fvgSweepLookbackCandles} min={3} max={100} step={1} decimals={0} onChange={setFvgSweepLookbackCandles} />
                </div>
              </div>
            ) : null}

            <label className="rules-toggle-row">
              <span>Only first touch of fresh FVG</span>
              <button
                type="button"
                role="switch"
                aria-checked={fvgRequireFirstTouch}
                className={`rules-toggle ${fvgRequireFirstTouch ? 'rules-toggle--on' : ''}`}
                onClick={() => setFvgRequireFirstTouch((v) => !v)}
              >
                <span className="rules-toggle__thumb" />
              </button>
            </label>
            <p className="stat-note muted" style={{ marginTop: -8 }}>
              {fvgRequireFirstTouch ? 'Rejects already mitigated HTF gaps; only the first live touch can qualify.' : 'Already mitigated HTF gaps remain eligible.'}
            </p>
            {fvgRequireFirstTouch ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 320px)', gap: 14 }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <span className="rules-label" style={{ margin: 0 }}>Max zone age candles</span>
                  <Stepper value={maxZoneAgeCandles} min={1} max={500} step={1} decimals={0} onChange={setMaxZoneAgeCandles} />
                </div>
              </div>
            ) : null}

            <label className="rules-toggle-row">
              <span>Require engulfing-body confirmation after retrace touch</span>
              <button
                type="button"
                role="switch"
                aria-checked={fvgRequireConfirmation}
                className={`rules-toggle ${fvgRequireConfirmation ? 'rules-toggle--on' : ''}`}
                onClick={() => setFvgRequireConfirmation((v) => !v)}
              >
                <span className="rules-toggle__thumb" />
              </button>
            </label>
            {fvgRequireConfirmation ? (
              <div style={{ display: 'grid', gap: 8 }}>
                <span className="rules-label" style={{ margin: 0 }}>Allowed confirmation timeframes</span>
                <div className="rules-btn-group rules-btn-group--left">
                  {TIMEFRAMES.map((tf) => (
                    <Button
                      key={`fvg-confirm-${tf}`}
                      variant={fvgConfirmationTimeframes.includes(tf) ? 'primary' : 'secondary'}
                      onClick={() => toggleTf(tf, fvgConfirmationTimeframes, setFvgConfirmationTimeframes)}
                    >
                      {tf}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </Card>

      <Card title="Signal Quality / Portfolio Guards" actions={<Badge tone="neutral">Stage 1</Badge>}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 14,
            alignItems: 'start',
          }}
        >
          <GuardControl label="Regime timeframe" enabled={regimeFilterEnabled} onToggle={setRegimeFilterEnabled} note="When off, EMA/ADX regime direction does not block entries.">
            <Segmented options={REGIME_TIMEFRAMES} value={regimeTf} onChange={setRegimeTf} />
          </GuardControl>

          <GuardControl label="Minimum ADX" enabled={adxEnabled} onToggle={setAdxEnabled}>
            <Stepper value={adxMin} min={0} max={100} step={1} decimals={0} onChange={setAdxMin} disabled={!adxEnabled} />
          </GuardControl>

          <GuardControl label="Minimum impulse / ATR" enabled={minImpulseAtrEnabled} onToggle={setMinImpulseAtrEnabled}>
            <Stepper value={minImpulseAtr} min={0} max={10} step={0.1} decimals={1} onChange={setMinImpulseAtr} disabled={!minImpulseAtrEnabled} />
          </GuardControl>

          <GuardControl label="Exit timeframe (Opposite Engulfing)" enabled={exitClosePct > 0} onToggle={(enabled) => setExitClosePct(enabled ? 50 : 0)} note="0% disables opposite-engulfing exits.">
            <div style={{ display: 'grid', gap: 8 }}>
              <div className="rules-btn-group rules-btn-group--left">
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
              <div className="actions-row" style={{ justifyContent: 'flex-start' }}>
                <Segmented
                  options={EXIT_CLOSE_PRESETS}
                  value={EXIT_CLOSE_PRESETS.includes(exitClosePct) ? exitClosePct : 50}
                  format={(v) => `${v}%`}
                  onChange={setExitClosePct}
                />
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={exitClosePct}
                  className="rules-input rules-input--sm"
                  onChange={(e) => setExitClosePct(clampNumber(Number(e.target.value), 0, 100))}
                  aria-label="Custom close size on exit signal"
                />
              </div>
            </div>
          </GuardControl>

          <GuardControl label="Time stop" enabled={timeStopEnabled} onToggle={setTimeStopEnabled}>
            <Stepper value={timeStopBars} min={0} max={1000} step={1} unit="bars" decimals={0} onChange={setTimeStopBars} disabled={!timeStopEnabled} />
          </GuardControl>

          <GuardControl label="Risk per trade" enabled={riskPerTradeEnabled} onToggle={setRiskPerTradeEnabled} note="Caps stake by equity risk at the configured SL distance.">
            <Stepper value={riskPerTradePct} min={0} max={100} step={0.1} unit="%" decimals={1} onChange={setRiskPerTradePct} disabled={!riskPerTradeEnabled} />
          </GuardControl>

          <GuardControl label="Portfolio gross cap" enabled={portfolioGrossCapEnabled} onToggle={setPortfolioGrossCapEnabled} note="Caps maximum notional exposure as % of equity in Freqtrade stake sizing.">
            <Stepper value={portfolioGrossCap} min={0} max={10000} step={25} unit="%" decimals={0} onChange={setPortfolioGrossCap} disabled={!portfolioGrossCapEnabled} />
          </GuardControl>
        </div>
        <p className="stat-note muted">
          Disabled guards are exported as inactive and do not affect Freqtrade strategy decisions.
        </p>
      </Card>

      <Card title="Execution Settings" actions={<Badge tone="neutral">Freqtrade</Badge>}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: 14,
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'grid', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <span className="rules-label" style={{ margin: 0 }}>Max Leverage</span>
              <div className="actions-row">
                <input
                  type="number"
                  min={1}
                  max={20}
                  step={1}
                  value={maxLeverage}
                  className="rules-input rules-input--sm"
                  onChange={(e) => setMaxLeverage(clampNumber(Number(e.target.value), 1, 20))}
                />
                <strong style={{ fontSize: 14 }}>{maxLeverage}x</strong>
              </div>
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
        <p className="stat-note muted">
          Max Leverage is applied by Freqtrade leverage(). Drawdown/stop-loss streak protections are native Freqtrade config protections and are intentionally not duplicated here.
        </p>
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

              {idx === 0 ? (
                tpLevels.length < 3 ? (
                  <Button type="button" variant="secondary" className="rules-mini-btn" onClick={addTpLevel}>+ TP</Button>
                ) : (
                  <span className="rules-mini-btn rules-mini-btn--ghost" />
                )
              ) : (
                <Button
                  type="button"
                  variant="danger"
                  className="rules-mini-btn"
                  onClick={() => removeTpLevel(idx)}
                  title="Remove level"
                >
                  Remove
                </Button>
              )}

              {idx === 0 ? (
                <span className="muted rules-level-hint">Freqtrade exits at TP1 for Stage 1</span>
              ) : (
                <span className="rules-mini-btn rules-mini-btn--ghost" />
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
          SL is applied through custom_stoploss(); TP1 is applied through custom_exit(). TP2/TP3 are saved for later partial-exit parity.
          {' '}R:R → TP1: <strong>{slPct > 0 ? ((tpLevels[0] ?? 0) / slPct).toFixed(1) : '—'}:1</strong>
          {tpLevels.length > 1 ? (
            <span> · TP2: <strong>{slPct > 0 ? ((tpLevels[1] ?? 0) / slPct).toFixed(1) : '—'}:1</strong></span>
          ) : null}
          {tpLevels.length > 2 ? (
            <span> · TP3: <strong>{slPct > 0 ? ((tpLevels[2] ?? 0) / slPct).toFixed(1) : '—'}:1</strong></span>
          ) : null}
        </p>
      </Card>

      <div className="rules-apply-row rules-apply-row--sticky-mobile">
        <Button variant="primary" fullWidth onClick={() => { void handleApply(); }} disabled={saving || loading}>
          {saving ? 'Saving...' : 'Apply changes'}
        </Button>
      </div>

      {isDirty ? <p className="stat-note" style={{ color: 'var(--warning, #f59e0b)' }}>You have unsaved changes.</p> : null}
      {saveInfo ? <p className="stat-note muted">{saveInfo}</p> : null}
    </main>
  );
}
