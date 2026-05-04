import { useEffect, useMemo, useRef, useState } from 'react';
import { ColorType, LineStyle, createChart, type IChartApi, type ISeriesApi, type SeriesMarker, type UTCTimestamp } from 'lightweight-charts';
import type {
  WaveEngineEntryTimeframe,
  WaveEngineProfilesResponse,
  WaveEngineReplayResponse,
  WaveEngineRulesSettings,
} from '../../shared/dto.js';
import { cloneWaveEngineRulesDefaults, normalizeWaveEngineRules } from '../../shared/tradingRulesV2.js';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { friendlyErrorMessage, getWaveEngineProfiles, getWaveEngineReplay, getWaveEngineRules, saveWaveEngineRules } from '../lib/api';

const TIMEFRAMES: WaveEngineEntryTimeframe[] = ['5m', '15m', '1h'];
type NumericFieldConfig = {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  setValue: (value: number) => void;
};

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function toTimestamp(value: string): UTCTimestamp | null {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.floor(parsed / 1000) as UTCTimestamp;
}

function isDateInputValue(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value));
}

function takeEvenlySpaced<T>(items: T[], limit: number): T[] {
  if (items.length <= limit) return items;
  if (limit <= 1) return [items[items.length - 1]];

  const lastIndex = items.length - 1;
  const step = lastIndex / (limit - 1);
  const result: T[] = [];

  for (let index = 0; index < limit; index += 1) {
    const sampleIndex = Math.min(lastIndex, Math.round(index * step));
    if (result[result.length - 1] !== items[sampleIndex]) {
      result.push(items[sampleIndex]);
    }
  }

  return result;
}

function prioritizeMarkers(markers: WaveEngineReplayResponse['markers'], limit: number) {
  const weightByKind: Record<WaveEngineReplayResponse['markers'][number]['kind'], number> = {
    entry: 6,
    exit: 5,
    tp: 5,
    sl: 5,
    time_stop: 4,
    structural_break: 3,
    regime: 2,
    pivot: 1,
    wave_segment: 1,
  };
  const decorated = markers.map((marker, index) => ({
    marker,
    index,
    weight: weightByKind[marker.kind] ?? 0,
  }));
  decorated.sort((left, right) => {
    if (right.weight !== left.weight) return right.weight - left.weight;
    return right.index - left.index;
  });
  const selected = decorated
    .slice(0, limit)
    .sort((left, right) => left.index - right.index)
    .map((item) => item.marker);
  return selected;
}

function summarizeMarkerKinds(markers: WaveEngineReplayResponse['markers']) {
  const counts = new Map<string, number>();
  for (const marker of markers) {
    counts.set(marker.kind, (counts.get(marker.kind) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 4)
    .map(([kind, count]) => `${kind}: ${count}`)
    .join(' · ');
}

function ChartPanel({ replay, loadingReplay }: { replay: WaveEngineReplayResponse | null; loadingReplay: boolean }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const chartStats = useMemo(() => {
    if (!replay) {
      return {
        candles: [],
        markers: [],
        waves: [],
        segments: [],
        markerTextVisible: true,
      };
    }

    const candles = replay.candles.flatMap((item) => {
      const time = toTimestamp(item.timestamp);
      if (time === null) return [];
      return [{
        time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
      }];
    });

    const maxMarkers = candles.length >= 30000 ? 180 : candles.length >= 15000 ? 260 : 420;
    const maxWaves = candles.length >= 30000 ? 160 : candles.length >= 15000 ? 240 : 360;
    const maxSegments = candles.length >= 30000 ? 220 : candles.length >= 15000 ? 320 : 480;
    const markerTextVisible = candles.length < 12000;

    const markers = prioritizeMarkers(replay.markers, maxMarkers).flatMap((item) => {
      const time = toTimestamp(item.time);
      if (time === null) return [];
      return [{
        time,
        position: item.kind === 'entry'
          ? (item.side === 'short' ? 'aboveBar' : 'belowBar')
          : (item.kind === 'sl' || item.kind === 'exit' ? 'aboveBar' : 'belowBar'),
        color: item.color,
        shape: item.shape ?? 'circle',
        text: markerTextVisible ? item.label : undefined,
      } satisfies SeriesMarker<UTCTimestamp>];
    }).sort((left, right) => Number(left.time) - Number(right.time));

    const waves = takeEvenlySpaced(replay.waves, maxWaves).flatMap((wave) => {
      const startTime = toTimestamp(wave.startTime);
      const endTime = toTimestamp(wave.endTime);
      if (startTime === null || endTime === null) return [];
      return [{
        startTime,
        startPrice: wave.startPrice,
        endTime,
        endPrice: wave.endPrice,
        direction: wave.direction,
      }];
    });

    const segments = takeEvenlySpaced(replay.segments, maxSegments).flatMap((segment) => {
      const startTime = toTimestamp(segment.startTime);
      const endTime = toTimestamp(segment.endTime);
      if (startTime === null || endTime === null) return [];
      return [{
        startTime,
        endTime,
        price: segment.price,
        kind: segment.kind,
        color: segment.color,
      }];
    });

    return { candles, markers, waves, segments, markerTextVisible };
  }, [replay]);

  useEffect(() => {
    if (!hostRef.current || !chartStats.candles.length) return;
    const chart = createChart(hostRef.current, {
      width: hostRef.current.clientWidth,
      height: 460,
      layout: {
        background: { type: ColorType.Solid, color: '#08131f' },
        textColor: '#bfd0ec',
      },
      grid: {
        vertLines: { color: 'rgba(95, 131, 184, 0.12)' },
        horzLines: { color: 'rgba(95, 131, 184, 0.12)' },
      },
      rightPriceScale: { borderColor: 'rgba(95, 131, 184, 0.28)' },
      timeScale: { borderColor: 'rgba(95, 131, 184, 0.28)', timeVisible: true },
      crosshair: {
        vertLine: { color: 'rgba(160, 182, 215, 0.35)' },
        horzLine: { color: 'rgba(160, 182, 215, 0.35)' },
      },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      borderVisible: false,
    });
    candleSeries.setData(chartStats.candles);
    candleSeries.setMarkers(chartStats.markers);

    const extraSeries: Array<ISeriesApi<'Line'>> = [];
    for (const wave of chartStats.waves) {
      const series = chart.addLineSeries({
        color: wave.direction === 'up' ? 'rgba(59, 130, 246, 0.9)' : 'rgba(249, 115, 22, 0.9)',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData([
        { time: wave.startTime, value: wave.startPrice },
        { time: wave.endTime, value: wave.endPrice },
      ]);
      extraSeries.push(series);
    }

    for (const segment of chartStats.segments) {
      const series = chart.addLineSeries({
        color: segment.color,
        lineWidth: segment.kind === 'sl' ? 1 : 2,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData([
        { time: segment.startTime, value: segment.price },
        { time: segment.endTime, value: segment.price },
      ]);
      extraSeries.push(series);
    }

    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
      if (!hostRef.current) return;
      chart.applyOptions({ width: hostRef.current.clientWidth });
    });
    observer.observe(hostRef.current);

    return () => {
      observer.disconnect();
      extraSeries.forEach((series) => {
        try {
          chart.removeSeries(series);
        } catch {
          // ignore teardown issues
        }
      });
      chart.remove();
      chartRef.current = null;
    };
  }, [chartStats]);

  if (loadingReplay && !replay) {
    return <p className="muted">Building replay from backend data source…</p>;
  }

  if (!replay) {
    return <p className="muted">Replay not loaded yet.</p>;
  }

  if (!chartStats.candles.length) {
    return <p className="muted">Replay loaded, but no valid chart timestamps were returned.</p>;
  }

  return (
    <div className="wave-engine-chart-shell">
      <div className="wave-engine-chart-meta">
        <span>{replay.request.pair}</span>
        <span>{replay.request.timeframe}</span>
        <span>{replay.candles.length} candles</span>
        <span>{replay.trades.length} trades</span>
        {chartStats.markers.length !== replay.markers.length ? <span>showing {chartStats.markers.length}/{replay.markers.length} markers</span> : null}
        {chartStats.waves.length !== replay.waves.length ? <span>showing {chartStats.waves.length}/{replay.waves.length} waves</span> : null}
        {chartStats.segments.length !== replay.segments.length ? <span>showing {chartStats.segments.length}/{replay.segments.length} segments</span> : null}
        {!chartStats.markerTextVisible ? <span>marker labels hidden on dense datasets</span> : null}
        {loadingReplay ? <span>refreshing…</span> : null}
      </div>
      <div className="position-panel__chart-wrap hl-chart-wrap wave-engine-chart-wrap">
        <div className="wave-engine-chart" ref={hostRef} />
      </div>
    </div>
  );
}

export function WaveEnginePage() {
  const defaults = useMemo(() => cloneWaveEngineRulesDefaults(), []);
  const [rules, setRules] = useState<WaveEngineRulesSettings>(() => normalizeWaveEngineRules(defaults));
  const [profiles, setProfiles] = useState<WaveEngineProfilesResponse | null>(null);
  const [replay, setReplay] = useState<WaveEngineReplayResponse | null>(null);
  const [pair, setPair] = useState('BTC/USDC:USDC');
  const [timeframe, setTimeframe] = useState<WaveEngineEntryTimeframe>('5m');
  const [start, setStart] = useState('2026-01-01');
  const [end, setEnd] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingReplay, setLoadingReplay] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activePairs = useMemo(
    () => (rules.symbols ?? []).filter((item) => item.enabled !== false).map((item) => item.pair || item.symbol),
    [rules.symbols],
  );
  const pairOptions = useMemo(
    () => [...new Set([pair, ...activePairs, ...(profiles?.profiles.map((item) => item.pair) ?? [])].filter(Boolean))],
    [activePairs, pair, profiles],
  );

  async function loadBase() {
    setLoading(true);
    try {
      const [rulesResult, profilesResult] = await Promise.all([getWaveEngineRules(), getWaveEngineProfiles()]);
      setRules(rulesResult.rules);
      setProfiles(profilesResult);
      const firstPair = rulesResult.rules.symbols.find((item) => item.enabled !== false)?.pair ?? profilesResult.profiles[0]?.pair ?? 'BTC/USDC:USDC';
      setPair((prev) => (prev && prev.trim().length > 0 ? prev : firstPair));
      setError(null);
      return { rules: rulesResult.rules, profiles: profilesResult, firstPair };
    } catch (err) {
      setError(friendlyErrorMessage(err, 'Could not load Wave Engine state.'));
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function loadReplay(next?: { pair?: string; timeframe?: WaveEngineEntryTimeframe; start?: string; end?: string }) {
    const pairValue = (next?.pair ?? pair).trim().toUpperCase();
    const timeframeValue = next?.timeframe ?? timeframe;
    const startValue = (next?.start ?? start).trim();
    const endValue = (next?.end ?? end).trim();

    if (!pairValue) {
      setError('Select a pair before building replay.');
      return;
    }
    if (!pairOptions.includes(pairValue)) {
      setError(`Pair ${pairValue} is not available in the current replay/profile snapshot.`);
      return;
    }
    if (!isDateInputValue(startValue)) {
      setError('Start date must be a valid YYYY-MM-DD value.');
      return;
    }
    if (endValue && !isDateInputValue(endValue)) {
      setError('End date must be a valid YYYY-MM-DD value.');
      return;
    }
    if (endValue && Date.parse(endValue) < Date.parse(startValue)) {
      setError('End date must be on or after the start date.');
      return;
    }

    setLoadingReplay(true);
    setMessage(null);
    try {
      const response = await getWaveEngineReplay({
        pair: pairValue,
        timeframe: timeframeValue,
        start: startValue,
        end: endValue || undefined,
      });
      setPair(response.request.pair);
      setTimeframe(response.request.timeframe);
      setStart(response.request.start);
      setEnd(response.request.end ?? '');
      setReplay(response);
      setError(null);
    } catch (err) {
      setReplay(null);
      setError(friendlyErrorMessage(err, 'Could not build Wave Engine replay.'));
    } finally {
      setLoadingReplay(false);
    }
  }

  useEffect(() => {
    void loadBase();
  }, []);

  useEffect(() => {
    if (!profiles && loading) return;
    const selectedPair = pair || activePairs[0] || profiles?.profiles[0]?.pair || 'BTC/USDC:USDC';
    void loadReplay({ pair: selectedPair });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profiles]);

  async function refreshPageState() {
    const base = await loadBase();
    const fallbackPair = pair || base?.firstPair || base?.profiles.profiles[0]?.pair || 'BTC/USDC:USDC';
    await loadReplay({ pair: fallbackPair });
  }

  async function saveRules() {
    setSaving(true);
    try {
      const result = await saveWaveEngineRules(rules);
      setRules(result.rules);
      setMessage('Wave Engine settings saved. Replay recomputed from backend source of truth.');
      await loadReplay();
    } catch (err) {
      setError(friendlyErrorMessage(err, 'Could not save Wave Engine settings.'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="terminal-layout wave-engine-page">
      {message ? <p className="stat-note" style={{ color: '#22c55e' }}>{message}</p> : null}
      {error ? <p className="stat-note" style={{ color: '#ef4444' }}>{error}</p> : null}
      {loading ? <p className="muted">Loading Wave Engine…</p> : null}

      <div className="wave-engine-grid">
        <Card
          title="Wave Engine / Trading Rules 2"
          className="terminal-card wave-engine-card"
          actions={(
            <div className="actions-row">
              <Badge tone={rules.enabled ? 'success' : 'neutral'}>{rules.enabled ? 'enabled' : 'disabled'}</Badge>
              <Button type="button" variant="secondary" onClick={() => { void refreshPageState(); }}>Refresh</Button>
              <Button type="button" onClick={() => { void saveRules(); }} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
            </div>
          )}
        >
          <div className="wave-engine-form">
            <label className="wave-engine-field wave-engine-field--toggle">
              <span>Engine enabled</span>
              <input
                type="checkbox"
                checked={rules.enabled}
                onChange={(event) => setRules((current) => ({ ...current, enabled: event.target.checked }))}
              />
            </label>

            <div className="wave-engine-field">
              <span>Active pairs</span>
              <div className="wave-engine-pill-row">
                {rules.symbols.map((item, index) => (
                  <button
                    key={item.pair || item.symbol}
                    type="button"
                    className={item.enabled !== false ? 'wave-engine-pill wave-engine-pill--active' : 'wave-engine-pill'}
                    onClick={() => setRules((current) => ({
                      ...current,
                      symbols: current.symbols.map((row, rowIndex) => rowIndex === index ? { ...row, enabled: row.enabled === false } : row),
                    }))}
                  >
                    {item.pair || item.symbol}
                  </button>
                ))}
              </div>
            </div>

            <div className="wave-engine-field">
              <span>Wave engine</span>
              <div className="wave-engine-pill-row">
                {(['atr_zigzag', 'pct_zigzag'] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={rules.waveEngine === value ? 'wave-engine-pill wave-engine-pill--active' : 'wave-engine-pill'}
                    onClick={() => setRules((current) => ({ ...current, waveEngine: value }))}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </div>

            <div className="wave-engine-field">
              <span>Break basis</span>
              <div className="wave-engine-pill-row">
                {(['wick', 'close'] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={rules.breakBasis === value ? 'wave-engine-pill wave-engine-pill--active' : 'wave-engine-pill'}
                    onClick={() => setRules((current) => ({ ...current, breakBasis: value }))}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </div>

            <div className="wave-engine-field">
              <span>Entry timeframes</span>
              <div className="wave-engine-pill-row">
                {TIMEFRAMES.map((value) => {
                  const active = rules.entryTimeframes.includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      className={active ? 'wave-engine-pill wave-engine-pill--active' : 'wave-engine-pill'}
                      onClick={() => setRules((current) => {
                        const currentSet = new Set(current.entryTimeframes);
                        if (active && current.entryTimeframes.length > 1) currentSet.delete(value);
                        if (!active) currentSet.add(value);
                        return { ...current, entryTimeframes: Array.from(currentSet) as WaveEngineEntryTimeframe[] };
                      })}
                    >
                      {value}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="wave-engine-number-grid">
              {([
                { label: 'ATR mult', value: rules.atrMult, min: 1.5, max: 4, step: 0.25, setValue: (value) => setRules((current) => ({ ...current, atrMult: value })) },
                { label: 'Pct move', value: rules.pctMove, min: 0.02, max: 0.05, step: 0.005, setValue: (value) => setRules((current) => ({ ...current, pctMove: value })) },
                { label: 'Flat extreme h', value: rules.flatExtremeLookbackHours, min: 60, max: 150, step: 1, setValue: (value) => setRules((current) => ({ ...current, flatExtremeLookbackHours: Math.round(value) })) },
                { label: 'Pullback ratio', value: rules.pullbackRatio, min: 0.4, max: 0.8, step: 0.05, setValue: (value) => setRules((current) => ({ ...current, pullbackRatio: value })) },
                { label: 'Max SL %', value: rules.maxSlPct, min: 0.02, max: 0.04, step: 0.005, setValue: (value) => setRules((current) => ({ ...current, maxSlPct: value })) },
                { label: 'TP2 %', value: rules.tp2Pct, min: 0.02, max: 0.04, step: 0.005, setValue: (value) => setRules((current) => ({ ...current, tp2Pct: value })) },
                { label: 'TP3 %', value: rules.tp3Pct, min: 0.04, max: 0.08, step: 0.01, setValue: (value) => setRules((current) => ({ ...current, tp3Pct: value })) },
                { label: 'Time stop h', value: rules.timeStopHours, min: 4, max: 16, step: 1, setValue: (value) => setRules((current) => ({ ...current, timeStopHours: Math.round(value) })) },
              ] as NumericFieldConfig[]).map((field) => (
                <label key={field.label} className="wave-engine-field">
                  <span>{field.label}</span>
                  <input
                    type="number"
                    value={String(field.value)}
                    min={field.min}
                    max={field.max}
                    step={field.step}
                    onChange={(event) => field.setValue(clampNumber(Number(event.target.value), field.min, field.max))}
                  />
                </label>
              ))}
            </div>
          </div>
        </Card>

        <Card
          title="Replay / Visualization"
          className="terminal-card wave-engine-card"
          actions={(
            <div className="actions-row">
              <Badge tone="neutral">{replay?.dataSource.kind ?? 'pending'}</Badge>
              <Button
                type="button"
                variant="secondary"
                onClick={() => { void loadReplay(); }}
                disabled={loadingReplay}
              >
                {loadingReplay ? 'Building…' : 'Recompute'}
              </Button>
            </div>
          )}
        >
          <div className="wave-engine-replay-controls">
            <label className="wave-engine-field">
              <span>Pair</span>
              <select value={pair} onChange={(event) => setPair(event.target.value)}>
                {pairOptions.map((value) => (
                  <option value={value} key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="wave-engine-field">
              <span>Display TF</span>
              <select value={timeframe} onChange={(event) => setTimeframe(event.target.value as WaveEngineEntryTimeframe)}>
                {TIMEFRAMES.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="wave-engine-field">
              <span>Start</span>
              <input type="date" value={start} onChange={(event) => setStart(event.target.value)} />
            </label>
            <label className="wave-engine-field">
              <span>End</span>
              <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
            </label>
            <Button type="button" onClick={() => { void loadReplay(); }} disabled={loadingReplay}>
              {loadingReplay ? 'Building…' : 'Load Replay'}
            </Button>
          </div>

          <ChartPanel replay={replay} loadingReplay={loadingReplay} />

          <div className="wave-engine-summary-grid">
            <article className="wave-engine-summary-card">
              <h3>Selected profile</h3>
              {replay?.profile ? (
                <p className="muted">
                  {replay.profile.pair} · {replay.profile.waveEngine} · {replay.profile.breakBasis} · entry {replay.profile.entryTimeframe}
                </p>
              ) : <p className="muted">No replay profile yet.</p>}
            </article>
            <article className="wave-engine-summary-card">
              <h3>Annotations</h3>
              <p className="muted">
                {replay ? `${replay.markers.length} markers · ${replay.segments.length} level segments · ${replay.waves.length} waves` : 'No annotations yet.'}
              </p>
              {replay?.markers.length ? <p className="wave-engine-card-note">{summarizeMarkerKinds(replay.markers)}</p> : null}
            </article>
            <article className="wave-engine-summary-card">
              <h3>Research snapshot</h3>
              <p className="muted">
                {profiles?.selectedFrom ? `${profiles.selectedFrom} · ${profiles.selectedAt ?? 'n/a'}` : 'No selected profile snapshot loaded.'}
              </p>
            </article>
          </div>

          {replay?.trades.length ? (
            <div className="wave-engine-trades">
              <h3>Trades</h3>
              <div className="table-wrap wave-engine-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Entry</th>
                      <th>Exit</th>
                      <th>Side</th>
                      <th>Reason</th>
                      <th>Entry px</th>
                      <th>Exit px</th>
                    </tr>
                  </thead>
                  <tbody>
                    {replay.trades.slice().reverse().slice(0, 12).map((trade) => (
                      <tr key={trade.id}>
                        <td>{trade.entryTime.replace('T', ' ').slice(0, 16)}</td>
                        <td>{trade.exitTime.replace('T', ' ').slice(0, 16)}</td>
                        <td className={trade.side === 'long' ? 'up' : 'down'}>{trade.side}</td>
                        <td>{trade.exitReason}</td>
                        <td>{trade.entryPrice}</td>
                        <td>{trade.exitPrice}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {profiles?.notes?.length ? (
            <div className="wave-engine-notes">
              {profiles.notes.slice(0, 4).map((note) => <p className="muted" key={note}>{note}</p>)}
            </div>
          ) : null}
        </Card>
      </div>
    </main>
  );
}
