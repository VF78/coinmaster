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

function formatOrderSize(value: number): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 6,
  }).format(value);
}

function normalizeLevel(value: number): number {
  return Number(value.toFixed(2));
}

function sameLevels(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (normalizeLevel(a[i]) !== normalizeLevel(b[i])) return false;
  }
  return true;
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
  const panningRef = useRef<{ startY: number; top: number; bottom: number } | null>(null);
  const manualScaleRef = useRef(false);

  const initialStopLossRef = useRef(normalizeLevel(stopLoss));
  const initialTakeProfitsRef = useRef(takeProfits.map(normalizeLevel));

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

  const tpDisplaySizes = useMemo(() => {
    const count = Math.max(1, takeProfits.length);
    const factor = 1e6;
    const base = Math.floor((position.size / count) * factor) / factor;
    return Array.from({ length: count }, (_, i) =>
      i < count - 1 ? base : Math.max(0, Math.round((position.size - base * (count - 1)) * factor) / factor)
    );
  }, [position.size, takeProfits.length]);

  const isDirty = useMemo(() => {
    const currentSl = normalizeLevel(stopLoss);
    const currentTps = takeProfits.map(normalizeLevel);
    if (currentSl !== initialStopLossRef.current) return true;
    return !sameLevels(currentTps, initialTakeProfitsRef.current);
  }, [stopLoss, takeProfits]);

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
        void handleCloseAttempt();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isDirty, stopLoss, takeProfits, isApplying]);

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
        return `Stop-loss is above current market price (${formatNumber(currentPrice)}). Please set SL below current market price.`;
      }
      if (takeProfits.some((tp) => tp <= entry)) {
        return 'For LONG, all TP levels must be above entry price.';
      }
      if (stopLoss >= Math.min(...takeProfits)) {
        return 'For LONG, stop-loss must be below all TP levels.';
      }
    } else {
      if (stopLoss <= currentPrice) {
        return `Stop-loss is below current market price (${formatNumber(currentPrice)}). Please set SL above current market price.`;
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
        vertTouchDrag: true,
      },
      handleScale: {
        // We handle wheel manually (right price scale only) to mimic TradingView behavior.
        mouseWheel: false,
        pinch: true,
        axisPressedMouseMove: {
          time: true,
          price: false,
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

    const setPriceScaleAutoScale = (enabled: boolean) => {
      const ps = candleSeriesRef.current?.priceScale();
      if (!ps) return;
      if (enabled && manualScaleRef.current) return;
      ps.applyOptions({ autoScale: enabled });
    };

    const pointerDown = (event: PointerEvent) => {
      const nearest = findNearestDraggable(event.clientY);
      const ps = candleSeriesRef.current?.priceScale();

      if (nearest) {
        event.preventDefault();
        event.stopPropagation();

        draggingRef.current = nearest;
        setDragging(nearest);
        host.style.cursor = 'ns-resize';
        setPriceScaleAutoScale(false);
        host.setPointerCapture?.(event.pointerId);
        return;
      }

      // Start chart panning mode (vertical by dragging up/down; horizontal is native via chart scroll).
      const opts = ps?.options?.();
      if (!ps || !opts) return;
      const top = opts.scaleMargins?.top ?? 0.12;
      const bottom = opts.scaleMargins?.bottom ?? 0.12;
      panningRef.current = { startY: event.clientY, top, bottom };
      manualScaleRef.current = true;
      setPriceScaleAutoScale(false);
      host.style.cursor = 'grabbing';
      host.setPointerCapture?.(event.pointerId);
    };

    const pointerMove = (event: PointerEvent) => {
      const drag = draggingRef.current;
      if (drag) {
        event.preventDefault();
        event.stopPropagation();

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
        return;
      }

      const pan = panningRef.current;
      if (!pan) return;

      const ps = candleSeriesRef.current?.priceScale();
      if (!ps) return;

      const rect = host.getBoundingClientRect();
      const dy = event.clientY - pan.startY;
      const shift = dy / Math.max(120, rect.height);

      let nextTop = pan.top - shift;
      let nextBottom = pan.bottom + shift;

      nextTop = Math.max(0.001, Math.min(0.499, nextTop));
      nextBottom = Math.max(0.001, Math.min(0.499, nextBottom));

      if (nextTop + nextBottom > 0.998) {
        const overflow = nextTop + nextBottom - 0.998;
        nextTop = Math.max(0.001, nextTop - overflow / 2);
        nextBottom = Math.max(0.001, nextBottom - overflow / 2);
      }

      ps.applyOptions({
        autoScale: false,
        scaleMargins: { top: nextTop, bottom: nextBottom },
      });
    };

    const pointerUp = (event?: PointerEvent) => {
      if (event && draggingRef.current) {
        event.preventDefault();
        event.stopPropagation();
      }
      draggingRef.current = null;
      panningRef.current = null;
      setDragging(null);
      host.style.cursor = 'default';
      setPriceScaleAutoScale(true);
    };

    const wheelOnPriceScale = (event: WheelEvent) => {
      // Always stop wheel from scrolling the page behind the modal when cursor is over chart host.
      event.preventDefault();
      event.stopPropagation();

      if (draggingRef.current) return;

      const rect = host.getBoundingClientRect();
      const ps = candleSeriesRef.current?.priceScale();
      const ts = chart.timeScale();
      const scaleWidth = ps?.width?.() ?? 56;
      const inRightScale = event.clientX >= rect.right - Math.max(48, scaleWidth + 8);

      // Right scale: vertical zoom
      if (inRightScale) {
        manualScaleRef.current = true;
        const opts = ps?.options?.();
        if (!ps || !opts) return;

        const currentTop = opts.scaleMargins?.top ?? 0.12;
        const currentBottom = opts.scaleMargins?.bottom ?? 0.12;
        const currentSpan = Math.max(0.01, 1 - currentTop - currentBottom);
        const center = currentTop + currentSpan / 2;

        // Wider zoom range vs previous version (more zoom-in/out freedom)
        const factor = event.deltaY < 0 ? 0.84 : 1.16;
        const nextSpan = Math.max(0.02, Math.min(0.98, currentSpan * factor));

        let nextTop = center - nextSpan / 2;
        let nextBottom = 1 - (nextTop + nextSpan);

        nextTop = Math.max(0.001, Math.min(0.499, nextTop));
        nextBottom = Math.max(0.001, Math.min(0.499, nextBottom));

        if (nextTop + nextBottom > 0.998) {
          const overflow = nextTop + nextBottom - 0.998;
          nextTop = Math.max(0.001, nextTop - overflow / 2);
          nextBottom = Math.max(0.001, nextBottom - overflow / 2);
        }

        ps.applyOptions({
          autoScale: false,
          scaleMargins: { top: nextTop, bottom: nextBottom },
        });
        return;
      }

      // Rest of chart: horizontal zoom (time scale), TradingView-like behavior.
      const logical = ts.getVisibleLogicalRange();
      if (!logical || !Number.isFinite(logical.from) || !Number.isFinite(logical.to)) return;

      const x = event.clientX - rect.left;
      const anchor = ts.coordinateToLogical(x) ?? (logical.from + logical.to) / 2;
      if (!Number.isFinite(anchor)) return;

      const zoom = event.deltaY < 0 ? 0.9 : 1.1;
      const nextFrom = anchor + (logical.from - anchor) * zoom;
      const nextTo = anchor + (logical.to - anchor) * zoom;
      if (!Number.isFinite(nextFrom) || !Number.isFinite(nextTo)) return;
      if (Math.abs(nextTo - nextFrom) < 2) return;

      ts.setVisibleLogicalRange({ from: nextFrom, to: nextTo });
    };

    host.addEventListener('pointerdown', pointerDown, { capture: true });
    host.addEventListener('pointermove', pointerMove, { capture: true });
    host.addEventListener('pointerup', pointerUp, { capture: true });
    host.addEventListener('pointercancel', pointerUp, { capture: true });
    host.addEventListener('wheel', wheelOnPriceScale, { passive: false });

    return () => {
      resizeObserver.disconnect();
      host.removeEventListener('pointerdown', pointerDown, true);
      host.removeEventListener('pointermove', pointerMove, true);
      host.removeEventListener('pointerup', pointerUp, true);
      host.removeEventListener('pointercancel', pointerUp, true);
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
      const mapOnSeries = (
        seriesRef: ISeriesApi<'Line'> | ISeriesApi<'Candlestick'> | null,
        value: number | undefined
      ) => {
        if (!value || value <= 0 || !seriesRef) return null;
        const api = seriesRef as unknown as { priceToCoordinate?: (p: number) => number | null };
        return api.priceToCoordinate?.(value) ?? null;
      };

      const mapOnScale = (value: number | undefined) => {
        if (!value || value <= 0 || !chartRef.current) return null;
        const scale = (chartRef.current as unknown as { priceScale?: (id: string) => { priceToCoordinate?: (p: number) => number | null } }).priceScale?.('right');
        return scale?.priceToCoordinate?.(value) ?? null;
      };

      const h = chartHostRef.current?.clientHeight ?? 0;
      const clampY = (y: number | null) => {
        if (y === null || !Number.isFinite(y)) return null;
        if (h <= 0) return y;
        return Math.max(10, Math.min(h - 10, y));
      };

      setChipCoords({
        pnl: clampY(mapOnSeries(pnlSeriesRef.current, markPrice) ?? mapOnScale(markPrice) ?? mapOnSeries(candleSeriesRef.current, markPrice)),
        sl: clampY(mapOnSeries(slSeriesRef.current, stopLoss) ?? mapOnScale(stopLoss) ?? mapOnSeries(candleSeriesRef.current, stopLoss)),
        tps: takeProfits.map((tp, idx) => clampY(mapOnSeries(tpSeriesRefs.current[idx] ?? null, tp) ?? mapOnScale(tp) ?? mapOnSeries(candleSeriesRef.current, tp))),
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

  async function applyLevels(options?: { skipConfirmPrompt?: boolean }): Promise<boolean> {
    if (validation) {
      await dialog.alert({
        title: 'Validation',
        message: validation,
        confirmText: 'OK',
      });
      return false;
    }

    if (!options?.skipConfirmPrompt) {
      const confirmed = await dialog.confirm({
        title: 'Apply TP/SL',
        message: 'Apply these TP/SL levels to live position?',
        confirmText: 'Apply',
        cancelText: 'Cancel',
      });
      if (!confirmed) return false;
    }

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

      const nextSl = normalizeLevel(response.stopLoss);
      const nextTps = confirmedTps.map((v) => normalizeLevel(v)).slice(0, 3);

      setStopLoss(nextSl);
      setTakeProfits(nextTps);
      initialStopLossRef.current = nextSl;
      initialTakeProfitsRef.current = nextTps;
      setInfo('TP/SL levels applied successfully and confirmed by exchange API.');

      await onApplied();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'set_levels_failed');
      return false;
    } finally {
      setIsApplying(false);
    }
  }

  async function handleCloseAttempt() {
    if (isApplying) return;

    if (!isDirty) {
      onClose();
      return;
    }

    const applyBeforeClose = await dialog.confirm({
      title: 'Unsaved chart changes',
      message: 'Apply TP/SL changes before closing the chart?',
      confirmText: 'Apply',
      cancelText: "Don’t apply",
    });

    if (applyBeforeClose) {
      const ok = await applyLevels({ skipConfirmPrompt: true });
      if (!ok) return;
    }

    onClose();
  }

  return (
    <section className="position-panel hl-panel" aria-label="Position levels panel">
      <header className="position-panel__header" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="hl-close-btn" onClick={() => { void handleCloseAttempt(); }} aria-label="Close panel">
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
                    <strong>{formatOrderSize(tpDisplaySizes[idx] ?? position.size)}</strong>
                  </div>
                );
              })}

              {chipCoords.pnl !== null ? (
                <div className="hl-line-chip hl-line-chip--pnl" style={{ top: chipCoords.pnl }}>
                  <span>PNL {formatMoney(unrealizedPnl)}</span>
                  <strong>{formatOrderSize(position.size)}</strong>
                </div>
              ) : null}

              {chipCoords.sl !== null ? (
                <div className="hl-line-chip hl-line-chip--sl" style={{ top: chipCoords.sl }}>
                  <span>SL Price {formatNumber(stopLoss)}</span>
                  <strong>{formatOrderSize(position.size)}</strong>
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

      <div className="actions-row hl-confirm-row">
        <Button onClick={() => { void applyLevels(); }} disabled={Boolean(validation) || isApplying} fullWidth>
          {isApplying ? 'Applying…' : 'Confirm'}
        </Button>
      </div>
      {error ? <p className="down hl-confirm-msg">{error}</p> : null}
      {info ? <p className="up hl-confirm-msg">{info}</p> : null}
    </section>
  );
}
