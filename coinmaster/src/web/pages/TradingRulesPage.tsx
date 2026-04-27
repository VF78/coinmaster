import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import type {
  AssetClass,
  BiasMode,
  BiasPolicySymbolOverride,
  TradingBias,
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
const TRADING_BIAS_OPTIONS: TradingBias[] = ['long', 'short', 'both', 'off'];

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
  const result: Record<string, BiasPolicySymbolOverride> = {};
  for (const [key, value] of Object.entries(input ?? {})) {
    const symbol = normalizeAssetSymbol(key);
    if (!symbol || !value) continue;
    const mode: BiasMode = value.mode === 'global' ? 'global' : 'symbol';
    const bias: TradingBias = value.bias === 'long' || value.bias === 'short' || value.bias === 'both' || value.bias === 'off' ? value.bias : 'both';
    result[symbol] = mode === 'symbol' ? { mode, bias } : { mode };
  }
  return result;
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
    <div
      style={{
        display: 'grid',
        gap: 8,
        alignContent: 'start',
        padding: '0.75rem',
        border: '1px solid var(--border)',
        borderRadius: 8,
        background: 'var(--surface-2)',
      }}
    >
      <div className="rules-toggle-row" style={{ width: '100%', gap: 10, justifyContent: 'space-between' }}>
        <span className="rules-label" style={{ margin: 0 }}>{label}</span>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          className={`rules-toggle ${enabled ? 'rules-toggle--on' : ''}`}
          onClick={() => onToggle(!enabled)}
          aria-label={`${enabled ? 'Disable' : 'Enable'} ${label}`}
        >
          <span className="rules-toggle__thumb" />
        </button>
      </div>
      <div style={{ opacity: enabled ? 1 : 0.45, pointerEvents: enabled ? 'auto' : 'none', width: '100%' }}>{children}</div>
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
  const [defaultBias, setDefaultBias] = useState<TradingBias>(defaults.biasPolicy?.defaultBias ?? 'both');
  const [symbolBiasOverrides, setSymbolBiasOverrides] = useState<Record<string, BiasPolicySymbolOverride>>(
    cloneSymbolOverrides(defaults.biasPolicy?.symbolOverrides)
  );

  const [savedRules, setSavedRules] = useState<TradingRulesSettings>(() => normalizeTradingRules(defaults));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveInfo, setSaveInfo] = useState<string>('');
  const activeCoinRows = useMemo(
    () => coins
      .map((coin, idx) => ({ coin, idx }))
      .filter(({ coin }) => coin.enabled),
    [coins],
  );

  const otherCoinRows = useMemo(
    () => activeCoinRows.filter(({ coin }) => {
      const symbol = normalizeAssetSymbol(coin.symbol);
      const assetClass = coin.assetClass ?? inferAssetClassFromSymbol(symbol);
      return assetClass === 'other';
    }),
    [activeCoinRows],
  );

  const hasNonOtherActiveCoins = activeCoinRows.length > otherCoinRows.length;

  const totalPct = useMemo(
    () => Math.round(activeCoinRows.reduce((s, { coin }) => s + coin.pct, 0) * 100) / 100,
    [activeCoinRows],
  );

  const currentRules = useMemo<TradingRulesSettings>(() => normalizeTradingRules({
    coins,
    entryTimeframes,
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
      defaultBias,
      symbolOverrides: cloneSymbolOverrides(symbolBiasOverrides),
    },
  }), [
    coins,
    entryTimeframes,
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
    defaultBias,
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
    setCoins(normalized.coins.filter((coin) => coin.enabled));
    setEntryTimeframes(normalized.entryTimeframes);
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
    setDefaultBias(normalized.biasPolicy?.defaultBias ?? 'both');
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
    // Coin Distribution mirrors the actual Freqtrade whitelist: rows shown here
    // are active rows only. Turning a row off removes it from the active list
    // instead of keeping a hidden disabled asset that could block re-adding it.
    removeCoin(idx);
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
    const symbol = normalizeAssetSymbol(coins[idx]?.symbol ?? '');
    setCoins((prev) => prev.map((c, i) => (i === idx ? { ...c, assetClass } : c)));
    if (symbol && assetClass !== 'other') {
      setSymbolBiasOverrides((prev) => {
        if (!prev[symbol]) return prev;
        const next = { ...prev };
        delete next[symbol];
        return next;
      });
    }
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

  function biasForSymbol(symbol: string): TradingBias {
    const normalized = normalizeAssetSymbol(symbol);
    const override = normalized ? symbolBiasOverrides[normalized] : undefined;
    return override?.mode === 'symbol' && override.bias ? override.bias : defaultBias;
  }

  function updateDefaultBias(bias: TradingBias) {
    setDefaultBias(bias);
    setSymbolBiasOverrides((prev) => {
      const next = { ...prev };
      for (const [symbol, override] of Object.entries(next)) {
        if (override.mode !== 'symbol' || override.bias === bias) delete next[symbol];
      }
      return next;
    });
  }

  function setSymbolBias(symbol: string, bias: TradingBias) {
    const normalized = normalizeAssetSymbol(symbol);
    if (!normalized) return;
    setSymbolBiasOverrides((prev) => {
      const next = { ...prev };
      if (bias === defaultBias) {
        delete next[normalized];
      } else {
        next[normalized] = { mode: 'symbol', bias };
      }
      return next;
    });
  }

  function renderBiasToggle(current: TradingBias, onSelect: (bias: TradingBias) => void, compact = false) {
    return (
      <div className={`exec-bias-toggle ${compact ? 'exec-bias-toggle--compact' : ''}`}>
        {TRADING_BIAS_OPTIONS.map((option) => {
          const active = current === option;
          return (
            <Button
              key={option}
              type="button"
              variant={option === 'short' || option === 'off' ? 'danger' : option === 'long' ? 'primary' : 'secondary'}
              onClick={() => onSelect(option)}
              className={`exec-bias-btn ${active ? 'exec-bias-btn--active' : ''} ${option === 'off' ? 'exec-bias-btn--off' : ''}`}
            >
              {option.toUpperCase()}
            </Button>
          );
        })}
      </div>
    );
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
    const activeCoins = coins.filter((coin) => coin.enabled);
    const normalizedSymbols = activeCoins.map((coin) => normalizeAssetSymbol(coin.symbol));
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
      coins: activeCoins.map((coin, idx) => ({
        ...coin,
        enabled: true,
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
  }, [onRegisterSaveHandler, currentRules, coins, entryTimeframes, engulfingLookbackCandles, fvgRetrace, fvgMinWidthPct, fvgRequireSweep, fvgSweepLookbackCandles, fvgRequireFirstTouch, maxZoneAgeCandles, fvgRequireConfirmation, fvgConfirmationTimeframes, maxLeverage, dailyDrawdown, tpLevels, slPct, regimeFilterEnabled, regimeTf, adxEnabled, adxMin, minImpulseAtrEnabled, minImpulseAtr, timeStopEnabled, timeStopBars, riskPerTradeEnabled, riskPerTradePct, portfolioGrossCapEnabled, portfolioGrossCap, defaultBias, symbolBiasOverrides]);

  return (
    <main className="terminal-layout trading-rules-page">
      {loading && (
        <Card title="Trading Rules" actions={<Badge tone="neutral">Loading</Badge>}>
          <p className="muted">Loading rules from server...</p>
        </Card>
      )}

      <Card title="Coin Distribution" actions={<Badge tone="neutral">Allocation + Bias</Badge>}>
        <div className="rules-distribution-layout">
          <section className="rules-distribution-main">
            <div className="rules-grid">
              {activeCoinRows.map(({ coin, idx }) => {
                const normalizedSymbol = normalizeAssetSymbol(coin.symbol);
                const rowAssetClass = coin.assetClass ?? inferAssetClassFromSymbol(normalizedSymbol);

                return (
                  <div key={`${coin.symbol || 'asset'}-${idx}`} className="rules-coin-row rules-coin-row--compact">
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
                      style={{ width: 108, textTransform: 'uppercase' }}
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
                      style={{ width: 108 }}
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
                      disabled={activeCoinRows.length <= 1}
                      title={activeCoinRows.length <= 1 ? 'At least one active asset row is required' : 'Remove asset'}
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

            <p className="stat-note muted">Active Freqtrade whitelist total: <strong>{totalPct}%</strong></p>

            <p className="stat-note muted" style={{ marginTop: 8 }}>
              This list mirrors the real Freqtrade whitelist. Allocation % sets target margin stake per asset in custom_stake_amount(). Pair whitelist changes require Freqtrade reload/restart; sizing and bias changes are hot-reloaded by the strategy.
            </p>
          </section>

          <aside className="rules-execution-controls">
            <div>
              <p className="rules-label" style={{ marginBottom: 8 }}>Execution controls</p>
              <p className="stat-note muted" style={{ marginTop: 0 }}>Freqtrade entry side bias. BOTH allows long and short; LONG/SHORT gates the opposite side; OFF blocks new entries.</p>
            </div>
            <div className="exec-bias-row">
              <span className="exec-bias-label">{hasNonOtherActiveCoins ? 'Crypto / default' : 'Default'}</span>
              {renderBiasToggle(defaultBias, updateDefaultBias)}
            </div>
            {otherCoinRows.length > 0 ? (
              <p className="muted" style={{ margin: '0.1rem 0 0', fontSize: 12 }}>Other assets</p>
            ) : null}
            {otherCoinRows.map(({ coin }) => {
              const symbol = normalizeAssetSymbol(coin.symbol);
              if (!symbol) return null;
              const bias = biasForSymbol(symbol);
              return (
                <div key={`rules-bias-${symbol}`} className="exec-bias-row">
                  <span className="exec-bias-label">{symbol}</span>
                  {renderBiasToggle(bias, (next) => setSymbolBias(symbol, next), true)}
                </div>
              );
            })}
          </aside>
        </div>
      </Card>

      <Card title="Entry Rules" actions={<Badge tone="neutral">Freqtrade MTF</Badge>}>
        <div className="rules-section">
          <p className="rules-label" style={{ marginBottom: 8 }}>
            Entry timeframes <span className="muted" style={{ fontWeight: 400 }}>(Engulfing on selected TFs; FVG uses selected 1h/4h HTFs)</span>
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
                <span className="rules-label" style={{ margin: 0 }}>FVG Retrace Level (HTF 1h/4h)</span>
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

      <Card title="Signal Quality / Portfolio Guards" actions={<Badge tone="neutral">Live in Freqtrade</Badge>}>
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
          SL is applied through custom_stoploss(); after the first TP fill, the remaining position is protected at break-even. TP exits use native Freqtrade position adjustments: one TP closes 100%; two TPs close 50/50; three TPs close 34/33/33.
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
