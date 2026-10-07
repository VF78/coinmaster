import { useEffect, useMemo, useRef, useState } from 'react';
import { createChart, type IChartApi, type IPriceLine, type ISeriesApi } from 'lightweight-charts';
import { humanizeBlocker } from '../lib/traderLabels';
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
      height: node.clientWidth < 560 ? 235 : 300,
      layout: { background: { color: '#15191d' }, textColor: '#96a2aa', attributionLogo: true },
      grid: { vertLines: { color: '#242c32' }, horzLines: { color: '#242c32' } },
      rightPriceScale: { borderColor: '#303940' }, timeScale: { borderColor: '#303940', timeVisible: true, secondsVisible: false },
      crosshair: { vertLine: { color: '#74858f' }, horzLine: { color: '#74858f' } },
    });
    chart.current = instance;
    series.current = instance.addCandlestickSeries({ upColor: '#70e1cb', downColor: '#df7378', borderUpColor: '#70e1cb', borderDownColor: '#df7378', wickUpColor: '#70e1cb', wickDownColor: '#df7378' });
    const resize = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) { instance.applyOptions({ width, height: width < 560 ? 235 : 300 }); }
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
  const overlays = useMemo(() => nativeOverlays(projection, history, coin, ready ? currentSnapshot?.candles ?? [] : [], ready), [projection, history, coin, ready, currentSnapshot]);
  const equityRows = useMemo(() => equityWindowRows(projection, equity, Date.now()), [projection, equity]);
  const badge = error ? 'Unavailable' : currentSnapshot?.state === 'READY' ? 'Ready' : currentSnapshot?.state === 'STALE' ? 'Stale' : currentSnapshot?.state === 'INVALID' ? 'Invalid' : currentSnapshot?.state === 'UNAVAILABLE' ? 'Unavailable' : 'Loading';
  const tone = badge === 'Ready' ? 'success' : badge === 'Loading' ? 'neutral' : 'danger';
  const equityAsOf = equity?.as_of_ns != null ? new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(equity.as_of_ns / 1_000_000)) : null;

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
        timer = window.setTimeout(() => void refresh(key), next.state === 'READY' || next.state === 'STALE' ? REFRESH_MS[interval] : 15_000);
      } catch {
        if (active && key === requestKey) { setError(true); setSnapshot(null); setLastBars([]); timer = window.setTimeout(() => void refresh(key), 15_000); }
      }
    };
    void refresh(requestKey);
    return () => { active = false; if (timer !== undefined) window.clearTimeout(timer); };
  }, [coin, interval, requestKey]);

  const observed = currentSnapshot?.observed_at_ms ? new Date(currentSnapshot.observed_at_ms).toISOString() : null;
  const latest = currentSnapshot?.latest_closed_at_ms ? new Date(currentSnapshot.latest_closed_at_ms).toISOString() : null;
  return <section className="dashboard-market-section" aria-label="Market chart and equity history">
    <div className="dashboard-market-section__head"><div><h2>Market &amp; account history</h2><p className="muted">Public candles · sampled Sandbox equity.</p></div><div className="dashboard-equity-windows" aria-label="Native account change windows">{equityRows ? equityRows.map((row) => <div className={row.value.startsWith('+') ? 'dashboard-equity-window dashboard-equity-window--positive' : row.value.startsWith('-') ? 'dashboard-equity-window dashboard-equity-window--negative' : 'dashboard-equity-window'} key={row.label}><span>{row.label}</span><strong>{row.value}</strong><small>{row.percent}</small></div>) : <span className="muted">24h / 7d / 30d account history unavailable until fresh same-epoch samples exist.</span>}</div></div><p className="dashboard-equity-asof">{equityRows && equityAsOf ? `Samples through ${equityAsOf} UTC · not tick-current.` : 'Account sample time unavailable.'}</p>
    <div className="dashboard-chart-card"><div className="dashboard-chart-toolbar"><div className="dashboard-chart-selectors" role="group" aria-label="Market"><button type="button" aria-pressed={coin === 'BTC'} className={coin === 'BTC' ? 'selected' : ''} onClick={() => setCoin('BTC')}>BTC</button><button type="button" aria-pressed={coin === 'SOL'} className={coin === 'SOL' ? 'selected' : ''} onClick={() => setCoin('SOL')}>SOL</button></div><label>Interval <select value={interval} onChange={(event) => setInterval(event.target.value as TraderInterval)}>{INTERVALS.map((value) => <option key={value}>{value}</option>)}</select></label><Badge tone={tone}>{badge}</Badge><Button variant="secondary" onClick={() => setRequestKey((key) => key + 1)}>Refresh chart</Button></div>
      {currentSnapshot?.state === 'STALE' ? <p className="dashboard-chart-notice">Source data is stale. Last returned candles are retained without native execution overlays.</p> : null}
      {currentSnapshot?.state === 'INVALID' || currentSnapshot?.state === 'UNAVAILABLE' || error ? <p className="dashboard-chart-notice">Candles unavailable. {currentSnapshot?.reason ? humanizeBlocker(currentSnapshot.reason) : 'Retrying automatically. You can also refresh.'}</p> : null}
      {currentSnapshot?.state === 'READY' && !bars.length ? <p className="dashboard-chart-notice">No completed candles are available for this interval.</p> : null}
      <ChartCanvas bars={bars} lines={overlays.lines} markers={overlays.markers} hasBars={bars.length > 0 && (currentSnapshot?.state === 'READY' || currentSnapshot?.state === 'STALE')} overlaysReady={ready} />
      <div className="dashboard-chart-provenance" aria-label="Chart data and execution overlay availability"><span><i className="dashboard-chart-provenance__swatch dashboard-chart-provenance__swatch--market" />Public market candles</span><span className={ready ? 'dashboard-chart-provenance__native dashboard-chart-provenance__native--ready' : 'dashboard-chart-provenance__native'}><i className="dashboard-chart-provenance__swatch dashboard-chart-provenance__swatch--native" />{ready ? overlays.lines.length || overlays.markers.length ? 'Native Sandbox positions, orders and fills' : 'No native overlays in this interval' : 'Native overlays wait for fresh candles and confirmed account state'}</span></div>
      <details className="dashboard-chart-meta"><summary>Market data details</summary><span>{currentSnapshot?.source === 'OFFICIAL_INFO_CANDLE_SNAPSHOT' ? 'Source: Hyperliquid Info candle snapshot' : 'Source unavailable'}</span><span>{observed ? `Observed ${observed}` : 'Observation time unavailable'}</span><span>{latest ? `Latest closed ${latest}` : 'Latest close unavailable'}</span><span>Chart by TradingView · public market data, not execution evidence</span></details>
    </div>
  </section>;
}
