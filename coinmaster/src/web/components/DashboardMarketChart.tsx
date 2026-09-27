import { useEffect, useMemo, useRef, useState } from 'react';
import { createChart, type IChartApi, type IPriceLine, type ISeriesApi } from 'lightweight-charts';
import { Badge } from './Badge';
import { Button } from './Button';
import { getHyperliquidCandles, type HlNativeEquityChanges, type HlPublicCandles, type HlStagegFillHistory, type HlStagegProjection } from '../lib/nautilusApi';
import { candleBars, equityWindowRows, nativeOverlays, type CandleBar, type TraderCoin, type TraderInterval } from '../lib/traderMarketData';

const INTERVALS: TraderInterval[] = ['1m', '5m', '15m', '1h', '4h', '1d'];
const REFRESH_MS: Record<TraderInterval, number> = { '1m': 60_000, '5m': 300_000, '15m': 900_000, '1h': 3_600_000, '4h': 14_400_000, '1d': 21_600_000 };

function ChartCanvas({ bars, lines, markers, hasBars, overlaysReady }: { bars: CandleBar[]; lines: Array<{ price: number; title: string; color: string }>; markers: ReturnType<typeof nativeOverlays>['markers']; hasBars: boolean; overlaysReady: boolean }) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const priceLines = useRef<IPriceLine[]>([]);
  useEffect(() => {
    const node = container.current;
    if (!node) return;
    const instance = createChart(node, {
      width: node.clientWidth || 640,
      height: node.clientWidth < 560 ? 245 : 330,
      layout: { background: { color: '#07110f' }, textColor: '#9bb0aa', attributionLogo: true },
      grid: { vertLines: { color: '#152521' }, horzLines: { color: '#152521' } },
      rightPriceScale: { borderColor: '#263a34' }, timeScale: { borderColor: '#263a34', timeVisible: true, secondsVisible: false },
      crosshair: { vertLine: { color: '#668d7f' }, horzLine: { color: '#668d7f' } },
    });
    chart.current = instance;
    series.current = instance.addCandlestickSeries({ upColor: '#39b98d', downColor: '#df7378', borderUpColor: '#39b98d', borderDownColor: '#df7378', wickUpColor: '#39b98d', wickDownColor: '#df7378' });
    const resize = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) { instance.applyOptions({ width, height: width < 560 ? 245 : 330 }); }
    });
    resize.observe(node);
    return () => { resize.disconnect(); priceLines.current = []; series.current = null; chart.current = null; instance.remove(); };
  }, []);
  useEffect(() => {
    const current = series.current;
    if (!current) return;
    current.setData(hasBars ? bars : []);
    if (hasBars) chart.current?.timeScale().fitContent();
  }, [bars, hasBars]);
  useEffect(() => {
    const current = series.current;
    if (!current) return;
    current.setMarkers(overlaysReady ? markers : []);
    priceLines.current.forEach((line) => current.removePriceLine(line));
    priceLines.current = overlaysReady ? lines.map((line) => current.createPriceLine({ price: line.price, title: line.title, color: line.color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true })) : [];
  }, [lines, markers, overlaysReady]);
  return <div className="dashboard-candles__canvas" ref={container} role="img" aria-label="Hyperliquid public candlestick chart with current native position, order and fill overlays" />;
}

export function DashboardMarketChart({ projection, history, equity }: { projection: HlStagegProjection | null; history: HlStagegFillHistory | null; equity: HlNativeEquityChanges | null }) {
  const [coin, setCoin] = useState<TraderCoin>('BTC');
  const [interval, setInterval] = useState<TraderInterval>('15m');
  const [snapshot, setSnapshot] = useState<HlPublicCandles | null>(null);
  const [lastBars, setLastBars] = useState<CandleBar[]>([]);
  const [requestKey, setRequestKey] = useState(0);
  const [error, setError] = useState(false);
  const currentSnapshot = snapshot?.coin === coin && snapshot.interval === interval ? snapshot : null;
  const bars = useMemo(() => currentSnapshot?.state === 'READY' ? candleBars(currentSnapshot.candles) : currentSnapshot?.state === 'STALE' ? (currentSnapshot.candles.length ? candleBars(currentSnapshot.candles) : lastBars) : [], [currentSnapshot, lastBars]);
  const ready = currentSnapshot?.state === 'READY' && bars.length > 0;
  const overlays = useMemo(() => nativeOverlays(projection, history, coin, ready), [projection, history, coin, ready]);
  const equityRows = useMemo(() => equityWindowRows(projection, equity, Date.now()), [projection, equity]);
  const badge = error ? 'Unavailable' : currentSnapshot?.state === 'READY' ? 'Ready' : currentSnapshot?.state === 'STALE' ? 'Stale' : currentSnapshot?.state === 'INVALID' ? 'Invalid' : currentSnapshot?.state === 'UNAVAILABLE' ? 'Unavailable' : 'Loading';
  const tone = badge === 'Ready' ? 'success' : badge === 'Loading' ? 'neutral' : 'danger';

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    setSnapshot(null); setLastBars([]); setError(false);
    const refresh = async (key: number) => {
      try {
        const next = await getHyperliquidCandles(coin, interval, 300);
        if (!active || key !== requestKey) return;
        setSnapshot(next); setError(false);
        if (next.state === 'READY') setLastBars(candleBars(next.candles));
        else if (next.state === 'STALE' && next.candles.length) setLastBars(candleBars(next.candles));
        if (next.state === 'READY' || next.state === 'STALE') timer = window.setTimeout(() => void refresh(key), REFRESH_MS[interval]);
      } catch {
        if (active && key === requestKey) { setError(true); setSnapshot(null); setLastBars([]); }
      }
    };
    void refresh(requestKey);
    return () => { active = false; if (timer !== undefined) window.clearTimeout(timer); };
  }, [coin, interval, requestKey]);

  const observed = currentSnapshot?.observed_at_ms ? new Date(currentSnapshot.observed_at_ms).toISOString() : null;
  const latest = currentSnapshot?.latest_closed_at_ms ? new Date(currentSnapshot.latest_closed_at_ms).toISOString() : null;
  return <section className="dashboard-market-section" aria-label="Market chart and equity history">
    <div className="dashboard-market-section__head"><div><h2>Market &amp; account history</h2><p className="muted">Official Hyperliquid public candles; Sandbox execution overlays are shown only for the confirmed current epoch.</p></div><div className="dashboard-equity-windows" aria-label="Native account change windows">{equityRows ? equityRows.map((row) => <div key={row.label}><span>{row.label}</span><strong>{row.value}</strong></div>) : <span className="muted">24h / 7d / 30d account history unavailable until fresh same-epoch samples exist.</span>}</div></div><p className="dashboard-equity-asof">{equityRows && equity?.as_of_ns != null ? `Native account sample ${new Date(equity.as_of_ns / 1_000_000).toISOString()} · values are not tick-current.` : 'Account-change sample time unavailable.'}</p>
    <div className="dashboard-chart-card"><div className="dashboard-chart-toolbar"><div className="dashboard-chart-selectors" role="group" aria-label="Market"><button className={coin === 'BTC' ? 'selected' : ''} onClick={() => setCoin('BTC')}>BTC</button><button className={coin === 'SOL' ? 'selected' : ''} onClick={() => setCoin('SOL')}>SOL</button></div><label>Interval <select value={interval} onChange={(event) => setInterval(event.target.value as TraderInterval)}>{INTERVALS.map((value) => <option key={value}>{value}</option>)}</select></label><Badge tone={tone}>{badge}</Badge><Button variant="secondary" onClick={() => setRequestKey((key) => key + 1)}>Refresh chart</Button></div>
      {currentSnapshot?.state === 'STALE' ? <p className="dashboard-chart-notice">Source data is stale. Last returned candles are retained without native execution overlays.</p> : null}
      {currentSnapshot?.state === 'INVALID' || currentSnapshot?.state === 'UNAVAILABLE' || error ? <p className="dashboard-chart-notice">Candles unavailable. {currentSnapshot?.reason ?? 'Refresh to retry.'}</p> : null}
      {currentSnapshot?.state === 'READY' && !bars.length ? <p className="dashboard-chart-notice">No completed candles are available for this interval.</p> : null}
      <ChartCanvas bars={bars} lines={overlays.lines} markers={overlays.markers} hasBars={bars.length > 0 && (currentSnapshot?.state === 'READY' || currentSnapshot?.state === 'STALE')} overlaysReady={ready} />
      <div className="dashboard-chart-meta"><span>{currentSnapshot?.source === 'OFFICIAL_INFO_CANDLE_SNAPSHOT' ? 'Source: Hyperliquid Info candle snapshot' : 'Source unavailable'}</span><span>{observed ? `Observed ${observed}` : 'Observation time unavailable'}</span><span>{latest ? `Latest closed ${latest}` : 'Latest close unavailable'}</span><span>Chart by TradingView · public market data, not execution evidence</span></div>
    </div>
  </section>;
}
