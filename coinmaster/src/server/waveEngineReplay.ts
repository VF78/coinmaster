import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import type {
  WaveEngineProfilesResponse,
  WaveEngineReplayResponse,
  WaveEngineRulesSettings,
  WaveEngineSelectedProfileSummary,
} from '../shared/dto.js';

type ReplayQuery = {
  pair: string;
  timeframe: '5m' | '15m' | '1h';
  start: string;
  end?: string;
};

type RawSelectedProfile = {
  symbol?: string;
  wave_engine?: 'atr_zigzag' | 'pct_zigzag';
  break_basis?: 'wick' | 'close';
  entry_timeframe?: '5m' | '15m' | '1h';
  pct_move?: number;
  atr_mult?: number;
  flat_extreme_lookback_hours?: number;
  pullback_ratio?: number;
  impulse_sl_buffer?: number;
  max_sl_pct?: number;
  tp1_max_pct?: number;
  tp2_pct?: number;
  tp3_pct?: number;
  time_stop_hours?: number;
  research_metrics?: {
    roi_pct?: number;
    profit_abs?: number;
    profit_factor?: number | null;
    max_drawdown_pct?: number;
    winrate_pct?: number;
    trades?: number;
  };
  source_run?: string;
  source_candidate?: string;
};

type RawProfileSnapshot = {
  selected_at?: string;
  selected_from?: string;
  research_only?: boolean;
  notes?: string[];
  pairs?: Record<string, RawSelectedProfile>;
};

function toSelectedProfile(pair: string, raw: RawSelectedProfile): WaveEngineSelectedProfileSummary {
  return {
    symbol: raw.symbol ?? pair.split('/', 1)[0],
    pair,
    waveEngine: raw.wave_engine === 'pct_zigzag' ? 'pct_zigzag' : 'atr_zigzag',
    breakBasis: raw.break_basis === 'close' ? 'close' : 'wick',
    entryTimeframe: raw.entry_timeframe === '15m' || raw.entry_timeframe === '1h' ? raw.entry_timeframe : '5m',
    pctMove: raw.pct_move,
    atrMult: raw.atr_mult,
    flatExtremeLookbackHours: Number(raw.flat_extreme_lookback_hours ?? 100),
    pullbackRatio: Number(raw.pullback_ratio ?? 0.5),
    impulseSlBuffer: Number(raw.impulse_sl_buffer ?? 0.0033),
    maxSlPct: Number(raw.max_sl_pct ?? 0.03),
    tp1MaxPct: Number(raw.tp1_max_pct ?? 0.015),
    tp2Pct: Number(raw.tp2_pct ?? 0.03),
    tp3Pct: Number(raw.tp3_pct ?? 0.06),
    timeStopHours: Number(raw.time_stop_hours ?? 8),
    researchMetrics: raw.research_metrics ? {
      roiPct: raw.research_metrics.roi_pct,
      profitAbs: raw.research_metrics.profit_abs,
      profitFactor: raw.research_metrics.profit_factor,
      maxDrawdownPct: raw.research_metrics.max_drawdown_pct,
      winratePct: raw.research_metrics.winrate_pct,
      trades: raw.research_metrics.trades,
    } : undefined,
    sourceRun: raw.source_run,
    sourceCandidate: raw.source_candidate,
  };
}

export function readWaveEngineProfiles(rootDir: string): WaveEngineProfilesResponse {
  const snapshotPath = path.join(rootDir, 'freqtrade', 'wave_engine', 'wave_engine_profiles.selected.json');
  const payload = JSON.parse(readFileSync(snapshotPath, 'utf8')) as RawProfileSnapshot;
  const profiles = Object.entries(payload.pairs ?? {})
    .map(([pair, raw]) => toSelectedProfile(pair, raw))
    .sort((a, b) => a.pair.localeCompare(b.pair));

  return {
    ok: true,
    selectedAt: payload.selected_at,
    selectedFrom: payload.selected_from,
    researchOnly: payload.research_only !== false,
    notes: Array.isArray(payload.notes) ? payload.notes.map((item) => String(item)) : [],
    profiles,
  };
}

export async function buildWaveEngineReplay(rootDir: string, rules: WaveEngineRulesSettings, query: ReplayQuery): Promise<WaveEngineReplayResponse> {
  const composeFiles = [
    path.join(rootDir, 'freqtrade', 'docker-compose.yml'),
    path.join(rootDir, 'freqtrade', 'docker-compose.research.yml'),
  ];
  const sourceDir = path.join(rootDir, 'freqtrade', 'wave_engine');
  const scriptPath = '/wave-engine-src/export_replay.py';
  const args = [
    'compose',
    '-f',
    composeFiles[0],
    '-f',
    composeFiles[1],
    'run',
    '--rm',
    '--no-deps',
    '--entrypoint',
    'python',
    '-v',
    `${sourceDir}:/wave-engine-src`,
    'freqtrade',
    scriptPath,
    '--pair',
    query.pair,
    '--timeframe',
    query.timeframe,
    '--start',
    query.start,
  ];
  if (query.end) {
    args.push('--end', query.end);
  }

  const stdout = await new Promise<string>((resolve, reject) => {
    const child = spawn('docker', args, {
      cwd: rootDir,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let out = '';
    let err = '';
    child.stdout.on('data', (chunk) => {
      out += String(chunk);
    });
    child.stderr.on('data', (chunk) => {
      err += String(chunk);
    });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolve(out.trim());
        return;
      }
      reject(new Error(err.trim() || `wave engine replay command failed with code ${code}`));
    });
  });

  const replay = JSON.parse(stdout) as WaveEngineReplayResponse;
  replay.rules = rules;
  return replay;
}
