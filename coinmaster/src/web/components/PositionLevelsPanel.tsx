import { useEffect, useMemo, useRef, useState } from 'react';
import { ColorType, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import type { LiveCandle, LivePosition } from '../../shared/dto.js';
import { applyLivePositionLevels, getLiveCandles } from '../lib/api';
import { formatMoney, formatNumber } from '../lib/format';
import { Button } from './Button';
import { useDialog } from './DialogProvider';

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
  const dialog = useDialog();
  const chartHostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const entrySeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const pnlSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const slSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const tpSeriesRefs = useRef<Array<ISeriesApi<'Line'>>>([]);

  const [timeframe, setTimeframe] = useState<CandleTf>('15m');
  const [candles, setCandles] = useState<LiveCandle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ kind: 'sl' | 'tp'; index: number } | null>(null);
  const [chipCoords, setChipCoords] = useState<{ pnl: number | null; sl: number | null; tps: Array<number | null> }>({ pnl: null, sl: null, tps: [] });

  const entry = position.entryPrice ?? 0;
  const side = position.side;

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

  const stopLossRef = useRef(stopLoss);
  const takeProfitsRef = useRef(takeProfits);
  const draggingRef = useRef<typeof dragging>(dragging);

  const markPrice = useMemo(() => {
    const last = candles[candles.length - 1];
    return last?.close ?? position.entryPrice ?? 0;
  }, [candles, position.entryPrice]);

  const unrealizedPnl = useMemo(() => {
    if (typeof position.unrealizedPnl === 'number' && Number.isFinite(position.unrealizedPnl)) {
      return position.unrealizedPnl;
    }
    if (!entry || !markPrice) return 0;
    const delta = side === 'long' ? (markPrice - entry) : (entry - markPrice);
    return Number((delta * position.size).toFixed(6));
  }, [entry, markPrice, position.size, position.unrealizedPnl, side]);

  useEffect(() => {
    stopLossRef.current = stopLoss;
  }, [stopLoss]);

  useEffect(() => {
    takeProfitsRef.current = takeProfits;
  }, [takeProfits]);

  useEffect(() => {
    draggingRef.current = dragging;
  }, [dragging]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const validation = useMemo(() => {
    if (!entry || !stopLoss || takeProfits.length === 0) {
      return 'Set stop-loss and at least one TP level.';
    }

    if (takeProfits.length > 3) {
      return 'Maximum 3 TP levels.';
    }

    const currentPrice = markPrice > 0 ? markPrice : entry;

    if (side === 'long') {
      if (stopLoss >= currentPrice) {
        return 'For LONG, stop-loss must be below current market price.';
      }
      if (takeProfits.some((tp) => tp <= entry)) {
        return 'For LONG, all TP levels must be above entry price.';
      }
      if (stopLoss >= Math.min(...takeProfits)) {
        return 'For LONG, stop-loss must be below all TP levels.';
      }
    } else {
      if (stopLoss <= currentPrice) {
        return 'For SHORT, stop-loss must be above current market price.';
      }
      if (takeProfits.some((tp) => tp >= entry)) {
        return 'For SHORT, all TP levels must be below entry price.';
      }
      if (stopLoss <= Math.max(...takeProfits)) {
        return 'For SHORT, stop-loss must be above all TP levels.';
      }
    }

    return null;
  }, [entry, markPrice, stopLoss, takeProfits, side]);

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
      rightPriceScale: {
        borderColor: '#243a5a',
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      leftPriceScale: { visible: false },
      timeScale: {
        borderColor: '#243a5a',
        timeVisible: true,
      },
      crosshair: {
        vertLine: { color: '#2f4d7a' },
        horzLine: { color: '#2f4d7a' },
      },
      handleScroll: {
        mouseWheel: false,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: {
          time: true,
          price: true,
        },
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#16c784',
      downColor: '#ea5b72',
      borderVisible: false,
      wickUpColor: '#16c784',
      wickDownColor: '#ea5b72',
    });

    const entrySeries = chart.addLineSeries({ color: '#bccbe6', lineWidth: 1, lineStyle: 2, priceLineVisible: true, lastValueVisible: false });
    const pnlSeries = chart.addLineSeries({ color: '#9fb0cf', lineWidth: 1, lineStyle: 2, priceLineVisible: true, lastValueVisible: false });
    const slSeries = chart.addLineSeries({ color: '#ea5b72', lineWidth: 1, lineStyle: 2, priceLineVisible: true, lastValueVisible: false });
    const tpSeries1 = chart.addLineSeries({ color: '#16c784', lineWidth: 1, lineStyle: 2, priceLineVisible: true, lastValueVisible: false });
    const tpSeries2 = chart.addLineSeries({ color: '#32d39a', lineWidth: 1, lineStyle: 2, priceLineVisible: true, lastValueVisible: false });
    const tpSeries3 = chart.addLineSeries({ color: '#58e0b0', lineWidth: 1, lineStyle: 2, priceLineVisible: true, lastValueVisible: false });

    candleSeries.setData(toCandleData(candles));
    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    entrySeriesRef.current = entrySeries;
    pnlSeriesRef.current = pnlSeries;
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

    const findNearestDraggable = (clientY: number): { kind: 'sl' | 'tp'; index: number } | null => {
      const rect = host.getBoundingClientRect();
      const y = clientY - rect.top;
      const priceToY = (price: number) => {
        const series = candleSeriesRef.current as unknown as { priceToCoordinate?: (p: number) => number | null } | null;
        return series?.priceToCoordinate?.(price) ?? null;
      };

      const candidates: Array<{ kind: 'sl' | 'tp'; index: number; dist: number }> = [];
      const slY = priceToY(stopLossRef.current);
      if (slY !== null) {
        candidates.push({ kind: 'sl', index: 0, dist: Math.abs(slY - y) });
      }
      takeProfitsRef.current.forEach((tp, idx) => {
        const tpY = priceToY(tp);
        if (tpY !== null) {
          candidates.push({ kind: 'tp', index: idx, dist: Math.abs(tpY - y) });
        }
      });

      candidates.sort((a, b) => a.dist - b.dist);
      if (!candidates.length || candidates[0].dist > 12) return null;
      return { kind: candidates[0].kind, index: candidates[0].index };
    };

    const pointerDown = (event: PointerEvent) => {
      const nearest = findNearestDraggable(event.clientY);
      if (!nearest) return;
      draggingRef.current = nearest;
      setDragging(nearest);
      host.style.cursor = 'ns-resize';
      host.setPointerCapture?.(event.pointerId);
    };

    const pointerMove = (event: PointerEvent) => {
      const drag = draggingRef.current;
      if (!drag) return;
      const rect = host.getBoundingClientRect();
      const y = event.clientY - rect.top;
      const series = candleSeriesRef.current as unknown as { coordinateToPrice?: (y: number) => number | null } | null;
      const price = series?.coordinateToPrice?.(y);
      if (!price || !Number.isFinite(price)) return;
      const normalized = Number(price.toFixed(2));
      if (drag.kind === 'sl') {
        setStopLoss(normalized);
      } else {
        setTakeProfits((prev) => prev.map((tp, idx) => (idx === drag.index ? normalized : tp)));
      }
    };

    const pointerUp = () => {
      draggingRef.current = null;
      setDragging(null);
      host.style.cursor = 'default';
    };

    const wheelOnPriceScale = (event: WheelEvent) => {
      const rect = host.getBoundingClientRect();
      const inRightScale = event.clientX >= rect.right - 92;
      if (!inRightScale) return;

      event.preventDefault();
      event.stopPropagation();

      const chartAny = chart as unknown as { priceScale?: (id: string) => unknown };
      const ps = chartAny.priceScale?.('right') as { getVisibleRange?: () => { from: number; to: number }; setVisibleRange?: (r: { from: number; to: number }) => void } | undefined;
      const range = ps?.getVisibleRange?.();
      if (!range || !Number.isFinite(range.from) || !Number.isFinite(range.to)) return;

      const series = candleSeriesRef.current as unknown as { coordinateToPrice?: (y: number) => number | null } | null;
      const y = event.clientY - rect.top;
      const center = series?.coordinateToPrice?.(y) ?? (range.from + range.to) / 2;
      if (!Number.isFinite(center)) return;

      const zoom = event.deltaY < 0 ? 0.92 : 1.08;
      const nextFrom = center + (range.from - center) * zoom;
      const nextTo = center + (range.to - center) * zoom;
      if (!Number.isFinite(nextFrom) || !Number.isFinite(nextTo) || Math.abs(nextTo - nextFrom) < 1e-7) return;

      ps?.setVisibleRange?.({ from: nextFrom, to: nextTo });
    };

    host.addEventListener('pointerdown', pointerDown);
    host.addEventListener('pointermove', pointerMove);
    host.addEventListener('pointerup', pointerUp);
    host.addEventListener('pointercancel', pointerUp);
    host.addEventListener('wheel', wheelOnPriceScale, { passive: false });

    return () => {
      resizeObserver.disconnect();
      host.removeEventListener('pointerdown', pointerDown);
      host.removeEventListener('pointermove', pointerMove);
      host.removeEventListener('pointerup', pointerUp);
      host.removeEventListener('pointercancel', pointerUp);
      host.removeEventListener('wheel', wheelOnPriceScale);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      entrySeriesRef.current = null;
      pnlSeriesRef.current = null;
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

    if (pnlSeriesRef.current && markPrice > 0) {
      pnlSeriesRef.current.setData([{ time: first, value: markPrice }, { time: last, value: markPrice }]);
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

    const updateChipCoords = () => {
      const mapPrice = (value: number | undefined) => {
        if (!value || value <= 0) return null;
        const series = candleSeriesRef.current as unknown as { priceToCoordinate?: (p: number) => number | null } | null;
        return series?.priceToCoordinate?.(value) ?? null;
      };
      setChipCoords({
        pnl: mapPrice(markPrice),
        sl: mapPrice(stopLoss),
        tps: takeProfits.map((tp) => mapPrice(tp)),
      });
    };

    updateChipCoords();
    const id = setInterval(updateChipCoords, 240);
    return () => clearInterval(id);
  }, [candles, entry, markPrice, stopLoss, takeProfits]);

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

    const confirmed = await dialog.confirm({
      title: 'Apply TP/SL',
      message: 'Apply these TP/SL levels to live position?',
      confirmText: 'Apply',
      cancelText: 'Cancel',
    });
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
      <header className="position-panel__header" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="hl-close-btn" onClick={onClose} aria-label="Close panel">
          ×
        </button>
      </header>

      <div className="hl-summary-grid">
        <span className="muted">Coin</span><strong>{position.symbol}</strong>
        <span className="muted">Position</span><strong>{formatNumber(position.size)} {position.symbol} (Value {position.dealValue !== undefined ? formatMoney(position.dealValue) : '—'})</strong>
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
        {!isLoading && !error ? (
          <div className="hl-chart-stage">
            <div className="position-panel__chart" ref={chartHostRef} />
            <div className="hl-line-overlay" aria-hidden>
              {takeProfits.map((tp, idx) => {
                const y = chipCoords.tps[idx];
                if (y === null || y === undefined) return null;
                return (
                  <div key={`tp-chip-${idx}`} className="hl-line-chip hl-line-chip--tp" style={{ top: y }}>
                    <span>TP Price {formatNumber(tp)}</span>
                    <strong>{formatNumber(position.size)}</strong>
                  </div>
                );
              })}

              {chipCoords.pnl !== null ? (
                <div className="hl-line-chip hl-line-chip--pnl" style={{ top: chipCoords.pnl }}>
                  <span>PNL {formatMoney(unrealizedPnl)}</span>
                  <strong>{formatNumber(position.size)}</strong>
                </div>
              ) : null}

              {chipCoords.sl !== null ? (
                <div className="hl-line-chip hl-line-chip--sl" style={{ top: chipCoords.sl }}>
                  <span>SL Price {formatNumber(stopLoss)}</span>
                  <strong>{formatNumber(position.size)}</strong>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
        {!isLoading && error ? <p className="muted">Chart error: {error}</p> : null}
      </div>

      <div className="hl-levels-layout">
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

        <aside className="muted position-panel__hint hl-side-hint">
          TP amount is split equally across active TP levels. After TP1 fill, SL moves to break-even.
        </aside>
      </div>

      {validation ? <p className="down">{validation}</p> : null}
      {error ? <p className="down">{error}</p> : null}

      <div className="actions-row hl-confirm-row">
        <Button onClick={applyLevels} disabled={Boolean(validation) || isApplying} fullWidth>
          {isApplying ? 'Applying…' : 'Confirm'}
        </Button>
      </div>
      {info ? <p className="up hl-confirm-msg">{info}</p> : null}
    </section>
  );
}
