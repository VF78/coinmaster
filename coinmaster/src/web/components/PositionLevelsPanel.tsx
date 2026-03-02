import { useEffect, useMemo, useRef, useState } from 'react';
import { ColorType, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import type { LiveCandle, LivePosition } from '../../shared/dto.js';
import { applyLivePositionLevels, getLiveCandles } from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';
import { Button } from './Button';
import { Badge } from './Badge';

type CandleTf = '5m' | '15m' | '1h' | '4h';

interface PositionLevelsPanelProps {
  position: LivePosition;
  onClose: () => void;
  onApplied: () => void;
}

function toCandleData(candles: LiveCandle[]) {
  return candles.map((c) => ({
    time: Math.floor(Date.parse(c.timestamp) / 1000) as UTCTimestamp,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

function pctFromPrice(side: 'long' | 'short', entry: number, price: number): number {
  if (!entry || entry <= 0 || !price || price <= 0) return 0;
  if (side === 'long') return ((price - entry) / entry) * 100;
  return ((entry - price) / entry) * 100;
}

function priceFromPct(side: 'long' | 'short', entry: number, pct: number): number {
  if (!entry || entry <= 0) return entry;
  if (side === 'long') return entry * (1 + pct / 100);
  return entry * (1 - pct / 100);
}

function parseDecimalInput(raw: string): number {
  const normalized = raw.replace(',', '.').trim();
  const n = Number(normalized);
  return Number.isFinite(n) ? n : 0;
}

export function PositionLevelsPanel({ position, onClose, onApplied }: PositionLevelsPanelProps) {
  const chartHostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const entrySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const slSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const tpSeriesRefs = useRef<Array<ISeriesApi<'Line'>>>([]);

  const [timeframe, setTimeframe] = useState<CandleTf>('15m');
  const [candles, setCandles] = useState<LiveCandle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  const entry = position.entryPrice ?? 0;
  const side = position.side;
  const sideLabel = side.toUpperCase();

  const [stopLoss, setStopLoss] = useState(position.stopLoss ?? entry);
  const [takeProfits, setTakeProfits] = useState<number[]>(() => {
    const fromPosition = Array.isArray(position.takeProfits)
      ? position.takeProfits.filter((v) => Number.isFinite(v) && v > 0).slice(0, 3)
      : [];
    if (fromPosition.length > 0) {
      return fromPosition.map((v) => Number(v.toFixed(2)));
    }
    const base = position.takeProfit ?? (entry > 0 ? priceFromPct(side, entry, 2) : 0);
    return base > 0 ? [Number(base.toFixed(2))] : [];
  });

  const markPrice = useMemo(() => {
    const last = candles[candles.length - 1];
    return last?.close ?? position.entryPrice ?? 0;
  }, [candles, position.entryPrice]);

  const validation = useMemo(() => {
    if (!entry || !stopLoss || takeProfits.length === 0) {
      return 'Set stop-loss and at least one TP level.';
    }

    const levelsValid = side === 'long'
      ? stopLoss < Math.min(...takeProfits)
      : stopLoss > Math.max(...takeProfits);

    if (!levelsValid) {
      return side === 'long'
        ? 'For LONG, stop-loss must be below all TP levels.'
        : 'For SHORT, stop-loss must be above all TP levels.';
    }

    if (takeProfits.length > 3) {
      return 'Maximum 3 TP levels.';
    }

    return null;
  }, [entry, stopLoss, takeProfits, side]);

  useEffect(() => {
    let active = true;
    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await getLiveCandles(position.symbol, timeframe, 240);
        if (!active) return;
        setCandles(response.candles);
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : 'failed_to_load_candles');
      } finally {
        if (active) setIsLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [position.symbol, timeframe]);

  useEffect(() => {
    if (!chartHostRef.current || !candles.length) return;

    const host = chartHostRef.current;
    const chart = createChart(host, {
      layout: {
        background: { type: ColorType.Solid, color: '#0a1220' },
        textColor: '#a8b9d8',
      },
      grid: {
        vertLines: { color: '#16243b' },
        horzLines: { color: '#16243b' },
      },
      rightPriceScale: { borderColor: '#243a5a' },
      leftPriceScale: { visible: false },
      timeScale: {
        borderColor: '#243a5a',
        timeVisible: true,
      },
      crosshair: {
        vertLine: { color: '#2f4d7a' },
        horzLine: { color: '#2f4d7a' },
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#16c784',
      downColor: '#ea5b72',
      borderVisible: false,
      wickUpColor: '#16c784',
      wickDownColor: '#ea5b72',
    });

    const entrySeries = chart.addLineSeries({ color: '#9fb0cf', lineWidth: 2, lineStyle: 2, priceLineVisible: true });
    const slSeries = chart.addLineSeries({ color: '#ea5b72', lineWidth: 2, priceLineVisible: true });
    const tpSeries1 = chart.addLineSeries({ color: '#16c784', lineWidth: 2, priceLineVisible: true });
    const tpSeries2 = chart.addLineSeries({ color: '#32d39a', lineWidth: 2, priceLineVisible: true });
    const tpSeries3 = chart.addLineSeries({ color: '#58e0b0', lineWidth: 2, priceLineVisible: true });

    candleSeries.setData(toCandleData(candles));
    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    entrySeriesRef.current = entrySeries;
    slSeriesRef.current = slSeries;
    tpSeriesRefs.current = [tpSeries1, tpSeries2, tpSeries3];

    const onResize = () => {
      if (!chartHostRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: chartHostRef.current.clientWidth,
        height: chartHostRef.current.clientHeight,
      });
    };

    const resizeObserver = new ResizeObserver(onResize);
    resizeObserver.observe(host);
    onResize();

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      entrySeriesRef.current = null;
      slSeriesRef.current = null;
      tpSeriesRefs.current = [];
    };
  }, [candles]);

  useEffect(() => {
    if (!candles.length) return;
    const first = Math.floor(Date.parse(candles[0].timestamp) / 1000) as UTCTimestamp;
    const last = Math.floor(Date.parse(candles[candles.length - 1].timestamp) / 1000) as UTCTimestamp;

    if (entrySeriesRef.current && entry > 0) {
      entrySeriesRef.current.setData([{ time: first, value: entry }, { time: last, value: entry }]);
    }

    if (slSeriesRef.current && stopLoss > 0) {
      slSeriesRef.current.setData([{ time: first, value: stopLoss }, { time: last, value: stopLoss }]);
    }

    tpSeriesRefs.current.forEach((series, idx) => {
      const tp = takeProfits[idx];
      if (tp && tp > 0) {
        series.setData([{ time: first, value: tp }, { time: last, value: tp }]);
      } else {
        series.setData([]);
      }
    });
  }, [candles, entry, stopLoss, takeProfits]);

  function addTp() {
    if (takeProfits.length >= 3) return;
    const fallback = entry > 0 ? priceFromPct(side, entry, 2 + takeProfits.length * 1.5) : 0;
    setTakeProfits((prev) => [...prev, Number((prev[prev.length - 1] ?? fallback).toFixed(2))]);
  }

  function removeTp(index: number) {
    if (takeProfits.length <= 1) return;
    setTakeProfits((prev) => prev.filter((_, i) => i !== index));
  }

  function updateTp(index: number, price: number) {
    setTakeProfits((prev) => prev.map((tp, i) => (i === index ? Number(price.toFixed(2)) : tp)));
  }

  function updateTpPct(index: number, pct: number) {
    const price = priceFromPct(side, entry, pct);
    updateTp(index, price);
  }

  function updateSlPct(pct: number) {
    const target = side === 'long'
      ? entry * (1 - pct / 100)
      : entry * (1 + pct / 100);
    setStopLoss(Number(target.toFixed(2)));
  }

  async function applyLevels() {
    if (validation) return;

    const confirmed = window.confirm('Apply these TP/SL levels to live position?');
    if (!confirmed) return;

    setIsApplying(true);
    setError(null);
    setInfo(null);

    try {
      const sorted = side === 'long'
        ? [...takeProfits].sort((a, b) => a - b)
        : [...takeProfits].sort((a, b) => b - a);

      const response = await applyLivePositionLevels({
        symbol: position.symbol,
        side: position.side,
        size: position.size,
        stopLoss,
        takeProfit: sorted[0],
        takeProfits: sorted,
        confirm: true,
      });

      if (!response.ok) {
        throw new Error(response.error || 'set_levels_failed');
      }

      const confirmedTps = (response.takeProfits && response.takeProfits.length > 0)
        ? response.takeProfits
        : [response.takeProfit].filter((v) => Number.isFinite(v) && v > 0);

      setStopLoss(Number(response.stopLoss.toFixed(2)));
      setTakeProfits(confirmedTps.map((v) => Number(v.toFixed(2))).slice(0, 3));
      setInfo('TP/SL levels applied successfully and confirmed by exchange API.');

      await onApplied();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'set_levels_failed');
    } finally {
      setIsApplying(false);
    }
  }

  return (
    <section className="position-panel hl-panel" aria-label="Position levels panel">
      <header className="position-panel__header">
        <div>
          <h3>TP/SL for Position</h3>
          <p className="muted">
            <Badge tone={position.side === 'long' ? 'success' : 'danger'}>{sideLabel}</Badge>
            {' • '}Size {formatNumber(position.size)}
            {' • '}Value {position.dealValue !== undefined ? formatMoney(position.dealValue) : '—'}
          </p>
        </div>
        <Button variant="secondary" onClick={onClose}>Close</Button>
      </header>

      <div className="hl-summary-grid">
        <span className="muted">Coin</span><strong>{position.symbol}</strong>
        <span className="muted">Position</span><strong>{formatNumber(position.size)} {position.symbol}</strong>
        <span className="muted">Entry Price</span><strong>{entry ? formatNumber(entry) : '—'}</strong>
        <span className="muted">Mark Price</span><strong>{markPrice ? formatNumber(markPrice) : '—'}</strong>
      </div>

      <div className="position-panel__chart-wrap hl-chart-wrap">
        <div className="hl-timeframes">
          {(['5m', '15m', '1h', '4h'] as CandleTf[]).map((tf) => (
            <button
              key={tf}
              type="button"
              className={`hl-timeframe-btn ${timeframe === tf ? 'hl-timeframe-btn--active' : ''}`}
              onClick={() => setTimeframe(tf)}
            >
              {tf}
            </button>
          ))}
        </div>
        {isLoading ? <p className="muted">Loading chart…</p> : null}
        {!isLoading && !error ? <div className="position-panel__chart" ref={chartHostRef} /> : null}
        {!isLoading && error ? <p className="muted">Chart error: {error}</p> : null}
      </div>

      <div className="hl-levels-form">
        {takeProfits.map((tp, idx) => {
          const gainPct = pctFromPrice(side, entry, tp);
          return (
            <div key={idx} className="hl-level-row">
              <label>
                <span>TP{idx + 1} Price</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={tp || ''}
                  onChange={(e) => updateTp(idx, parseDecimalInput(e.target.value))}
                />
              </label>
              <label>
                <span>Gain %</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={Number.isFinite(gainPct) ? gainPct.toFixed(2) : ''}
                  onChange={(e) => updateTpPct(idx, parseDecimalInput(e.target.value))}
                />
              </label>
              <div className="hl-level-row__actions">
                {idx === 0 && takeProfits.length < 3 ? (
                  <Button className="hl-action-btn" variant="secondary" onClick={addTp}>+ TP</Button>
                ) : <span className="hl-action-spacer" />}
                {takeProfits.length > 1 ? (
                  <Button className="hl-action-btn" variant="danger" onClick={() => removeTp(idx)}>Remove</Button>
                ) : <span className="hl-action-spacer" />}
              </div>
            </div>
          );
        })}

        <div className="hl-level-row">
          <label>
            <span>SL Price</span>
            <input
              type="text"
              inputMode="decimal"
              value={stopLoss || ''}
              onChange={(e) => setStopLoss(parseDecimalInput(e.target.value))}
            />
          </label>
          <label>
            <span>Loss %</span>
            <input
              type="text"
              inputMode="decimal"
              value={Math.abs(pctFromPrice(side, entry, stopLoss)).toFixed(2)}
              onChange={(e) => updateSlPct(parseDecimalInput(e.target.value))}
            />
          </label>
          <div className="hl-level-row__actions">
            <span className="hl-action-spacer" />
            <span className="hl-action-spacer" />
          </div>
        </div>
      </div>

      <p className="muted position-panel__hint">TP amount is split equally across active TP levels. After TP1 fill, SL moves to break-even.</p>

      {validation ? <p className="down">{validation}</p> : null}
      {error ? <p className="down">{error}</p> : null}
      {info ? <p className="up">{info}</p> : null}

      <div className="actions-row">
        <Button onClick={applyLevels} disabled={Boolean(validation) || isApplying} fullWidth>
          {isApplying ? 'Applying…' : 'Confirm'}
        </Button>
      </div>
    </section>
  );
}
