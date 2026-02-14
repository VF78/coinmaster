import { useEffect, useMemo, useRef, useState } from 'react';
import { ColorType, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import type { LiveCandle, LivePosition } from '../../shared/dto.js';
import { applyLivePositionLevels, getLiveCandles } from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';
import { Button } from './Button';
import { Badge } from './Badge';

type EditableLevel = 'entry' | 'stopLoss' | 'takeProfit';

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
    close: c.close
  }));
}

export function PositionLevelsPanel({ position, onClose, onApplied }: PositionLevelsPanelProps) {
  const chartHostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const entrySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const slSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const tpSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const [candles, setCandles] = useState<LiveCandle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const [dragging, setDragging] = useState<EditableLevel | null>(null);

  const [entry, setEntry] = useState(position.entryPrice ?? 0);
  const [stopLoss, setStopLoss] = useState(position.stopLoss ?? position.entryPrice ?? 0);
  const [takeProfit, setTakeProfit] = useState(position.takeProfit ?? position.entryPrice ?? 0);

  const sideLabel = position.side.toUpperCase();

  const validation = useMemo(() => {
    if (!entry || !stopLoss || !takeProfit) {
      return 'Set entry / stop-loss / take-profit first.';
    }

    if (position.side === 'long' && !(stopLoss < entry && takeProfit > entry)) {
      return 'For LONG: stop-loss must be below entry, take-profit above entry.';
    }

    if (position.side === 'short' && !(stopLoss > entry && takeProfit < entry)) {
      return 'For SHORT: stop-loss must be above entry, take-profit below entry.';
    }

    return null;
  }, [entry, stopLoss, takeProfit, position.side]);

  useEffect(() => {
    let active = true;

    (async () => {
      setIsLoading(true);
      try {
        const response = await getLiveCandles(position.symbol, '15m', 240);
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
  }, [position.symbol]);

  useEffect(() => {
    if (!chartHostRef.current || !candles.length) return;

    const host = chartHostRef.current;
    const chart = createChart(host, {
      layout: {
        background: { type: ColorType.Solid, color: '#08131f' },
        textColor: '#c7d8f0'
      },
      grid: {
        vertLines: { color: '#12253a' },
        horzLines: { color: '#12253a' }
      },
      rightPriceScale: {
        borderColor: '#1f3a5a'
      },
      timeScale: {
        borderColor: '#1f3a5a',
        timeVisible: true
      },
      crosshair: {
        vertLine: { color: '#2bcab0' },
        horzLine: { color: '#2bcab0' }
      }
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#2bcab0',
      downColor: '#d85d7c',
      borderVisible: false,
      wickUpColor: '#2bcab0',
      wickDownColor: '#d85d7c'
    });

    const entrySeries = chart.addLineSeries({ color: '#94a9c6', lineWidth: 2, lineStyle: 2, priceLineVisible: true });
    const slSeries = chart.addLineSeries({ color: '#f36b8a', lineWidth: 2, priceLineVisible: true });
    const tpSeries = chart.addLineSeries({ color: '#29d69a', lineWidth: 2, priceLineVisible: true });

    candleSeries.setData(toCandleData(candles));

    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    entrySeriesRef.current = entrySeries;
    slSeriesRef.current = slSeries;
    tpSeriesRef.current = tpSeries;

    const onResize = () => {
      if (!chartHostRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: chartHostRef.current.clientWidth,
        height: chartHostRef.current.clientHeight
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
      tpSeriesRef.current = null;
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

    if (tpSeriesRef.current && takeProfit > 0) {
      tpSeriesRef.current.setData([{ time: first, value: takeProfit }, { time: last, value: takeProfit }]);
    }
  }, [candles, entry, stopLoss, takeProfit]);

  useEffect(() => {
    const host = chartHostRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!host || !candleSeries || !candles.length) return;

    const pickLevelByY = (y: number): EditableLevel | null => {
      const price = candleSeries.coordinateToPrice(y);
      if (price === null || price === undefined) return null;

      const points: Array<{ key: EditableLevel; value: number }> = [
        { key: 'entry', value: entry },
        { key: 'stopLoss', value: stopLoss },
        { key: 'takeProfit', value: takeProfit }
      ];

      const nearest = points
        .map((p) => ({ key: p.key, diff: Math.abs(p.value - price) }))
        .sort((a, b) => a.diff - b.diff)[0];

      const maxDiff = Math.max(entry, stopLoss, takeProfit) * 0.004;
      return nearest && nearest.diff <= maxDiff ? nearest.key : null;
    };

    const updateByY = (target: EditableLevel, y: number) => {
      const price = candleSeries.coordinateToPrice(y);
      if (price === null || price === undefined || !Number.isFinite(price)) return;
      const normalized = Number(price.toFixed(2));

      if (target === 'entry') setEntry(normalized);
      if (target === 'stopLoss') setStopLoss(normalized);
      if (target === 'takeProfit') setTakeProfit(normalized);
    };

    const onMouseDown = (event: MouseEvent) => {
      const rect = host.getBoundingClientRect();
      const y = event.clientY - rect.top;
      const level = pickLevelByY(y);
      if (!level) return;
      setDragging(level);
      event.preventDefault();
    };

    const onMouseMove = (event: MouseEvent) => {
      if (!dragging) return;
      const rect = host.getBoundingClientRect();
      const y = event.clientY - rect.top;
      updateByY(dragging, y);
    };

    const onMouseUp = () => {
      if (dragging) setDragging(null);
    };

    host.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);

    return () => {
      host.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [candles, entry, stopLoss, takeProfit, dragging]);

  async function applyLevels() {
    if (validation) return;

    const confirmed = window.confirm('Apply these SL/TP levels to live position?');
    if (!confirmed) return;

    setIsApplying(true);
    setError(null);

    try {
      const response = await applyLivePositionLevels({
        symbol: position.symbol,
        side: position.side,
        size: position.size,
        stopLoss,
        takeProfit,
        confirm: true
      });

      if (!response.ok) {
        throw new Error(response.error || 'set_levels_failed');
      }

      onApplied();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'set_levels_failed');
    } finally {
      setIsApplying(false);
    }
  }

  return (
    <section className="position-panel" aria-label="Position levels panel">
      <header className="position-panel__header">
        <div>
          <h3>{position.symbol} position</h3>
          <p className="muted">
            <Badge tone={position.side === 'long' ? 'success' : 'danger'}>{sideLabel}</Badge>
            {' • '}Size {formatNumber(position.size)}
            {' • '}Deal {position.dealValue !== undefined ? formatMoney(position.dealValue) : '—'}
          </p>
        </div>
        <Button variant="secondary" onClick={onClose}>Close</Button>
      </header>

      <div className="position-panel__chart-wrap">
        {isLoading ? <p className="muted">Loading chart…</p> : null}
        {!isLoading && !error ? <div className="position-panel__chart" ref={chartHostRef} /> : null}
        {!isLoading && error ? <p className="muted">Chart error: {error}</p> : null}
      </div>

      <p className="muted position-panel__hint">
        Drag SL/TP/Entry lines directly on chart or edit values below.
      </p>

      <div className="position-panel__form">
        <label>
          Entry
          <input type="number" value={entry || ''} onChange={(e) => setEntry(Number(e.target.value))} />
        </label>
        <label>
          Stop-loss
          <input type="number" value={stopLoss || ''} onChange={(e) => setStopLoss(Number(e.target.value))} />
        </label>
        <label>
          Take-profit
          <input type="number" value={takeProfit || ''} onChange={(e) => setTakeProfit(Number(e.target.value))} />
        </label>
      </div>

      {validation ? <p className="down">{validation}</p> : null}
      {error ? <p className="down">{error}</p> : null}

      <div className="actions-row">
        <Button onClick={applyLevels} disabled={Boolean(validation) || isApplying}>
          {isApplying ? 'Applying…' : 'Apply levels (confirm)'}
        </Button>
      </div>
    </section>
  );
}
