import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import type { AlphaRadarConnectorAuthSession, AlphaRadarConnectorSettings, AlphaRadarConnectorState } from '../shared/dto.js';
import type { AlphaRadarSocialCandidate } from './alphaRadarSocial.js';

const TELEGRAM_SECRET_ENV_PATH = '/root/.secrets/coinmaster_telegram_alpha_radar.env';
const TELEGRAM_RUNTIME_DIR = path.resolve(process.cwd(), 'exports/alpha-radar/telegram-auth');
const TELEGRAM_SESSION_PATH = path.join(TELEGRAM_RUNTIME_DIR, 'alpha-radar');
const TELEGRAM_STATE_PATH = path.join(TELEGRAM_RUNTIME_DIR, 'auth-state.json');
const TELEGRAM_WORKER_PATH = path.resolve(process.cwd(), 'scripts/alpha_radar_telegram_worker.py');
const TELEGRAM_VENV_PYTHON = path.join(TELEGRAM_RUNTIME_DIR, 'venv/bin/python');

type TelegramWorkerAction = 'status' | 'request_code' | 'submit_code' | 'start_qr' | 'cancel_qr' | 'collect';

interface TelegramWorkerAuthSession {
  kind?: string;
  status?: string;
  startedAt?: string;
  expiresAt?: string;
  pollAfterMs?: number;
  qrUrl?: string;
  qrTokenBase64Url?: string;
  message?: string;
  error?: string;
}

interface TelegramWorkerMessage {
  status?: string;
  connectionLabel?: string;
  message?: string;
  error?: string;
  lastSyncAt?: string;
  lastSyncCursor?: string;
  authSession?: TelegramWorkerAuthSession;
}

interface TelegramWorkerObservation {
  source: string;
  title: string;
  excerpt: string;
  observedAt?: string;
  assetTags?: string[];
  topicTags?: string[];
  provenance?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

interface TelegramWorkerResponse extends TelegramWorkerMessage {
  ok: boolean;
  observations?: TelegramWorkerObservation[];
  fetchedSources?: string[];
}

function ensureRuntimeDir(): void {
  mkdirSync(TELEGRAM_RUNTIME_DIR, { recursive: true });
}

function parseSecretEnv(): Record<string, string> {
  if (!existsSync(TELEGRAM_SECRET_ENV_PATH)) return {};
  const content = readFileSync(TELEGRAM_SECRET_ENV_PATH, 'utf8');
  const out: Record<string, string> = {};
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const idx = line.indexOf('=');
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

function normalizeStatus(status: unknown): AlphaRadarConnectorState['status'] {
  return status === 'connected' || status === 'needs_auth' || status === 'awaiting_code' || status === 'awaiting_qr' || status === 'error' ? status : 'idle';
}

function normalizeAuthSession(session: TelegramWorkerAuthSession | undefined): AlphaRadarConnectorAuthSession | undefined {
  if (!session || session.kind !== 'telegram_qr') return undefined;
  return {
    kind: 'telegram_qr',
    status: session.status === 'expired' || session.status === 'cancelled' || session.status === 'error' ? session.status : 'pending',
    startedAt: session.startedAt,
    expiresAt: session.expiresAt,
    pollAfterMs: Number.isFinite(Number(session.pollAfterMs)) ? Math.max(500, Math.min(60_000, Math.round(Number(session.pollAfterMs)))) : undefined,
    qrUrl: typeof session.qrUrl === 'string' && session.qrUrl.trim() ? session.qrUrl.trim() : undefined,
    qrTokenBase64Url: typeof session.qrTokenBase64Url === 'string' && session.qrTokenBase64Url.trim() ? session.qrTokenBase64Url.trim() : undefined,
    message: typeof session.message === 'string' && session.message.trim() ? session.message.trim() : undefined,
    error: typeof session.error === 'string' && session.error.trim() ? session.error.trim() : undefined,
  };
}

function buildState(base: AlphaRadarConnectorSettings, patch: TelegramWorkerMessage): AlphaRadarConnectorState {
  const status = normalizeStatus(patch.status);
  return {
    ...base.state,
    configured: base.watchlist.length > 0,
    needsAuth: status === 'needs_auth' || status === 'awaiting_code' || status === 'awaiting_qr',
    status,
    lastSyncAt: patch.lastSyncAt ?? base.state.lastSyncAt,
    lastSyncCursor: patch.lastSyncCursor ?? base.state.lastSyncCursor,
    lastSyncStatus: status === 'connected' ? 'success' : status === 'error' ? 'error' : 'pending',
    connectionLabel: patch.connectionLabel ?? base.state.connectionLabel,
    message: patch.message ?? base.state.message,
    error: patch.error,
    authSession: status === 'awaiting_qr' ? normalizeAuthSession(patch.authSession) : undefined,
  };
}

async function runTelegramWorker(action: TelegramWorkerAction, payload: Record<string, unknown>): Promise<TelegramWorkerResponse> {
  ensureRuntimeDir();
  const secrets = parseSecretEnv();
  const env = {
    ...process.env,
    ...secrets,
    TELEGRAM_ALPHA_RADAR_ENV_PATH: TELEGRAM_SECRET_ENV_PATH,
  };
  const input = JSON.stringify({
    action,
    sessionPath: TELEGRAM_SESSION_PATH,
    statePath: TELEGRAM_STATE_PATH,
    ...payload,
  });

  return new Promise((resolve, reject) => {
    const pythonBin = existsSync(TELEGRAM_VENV_PYTHON) ? TELEGRAM_VENV_PYTHON : 'python3';
    const child = spawn(pythonBin, [TELEGRAM_WORKER_PATH], {
      cwd: process.cwd(),
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += String(chunk); });
    child.stderr.on('data', (chunk) => { stderr += String(chunk); });
    child.once('error', reject);
    child.once('close', (code) => {
      if (!stdout.trim()) {
        reject(new Error(stderr.trim() || `telegram_worker_exit_${code ?? 'unknown'}`));
        return;
      }
      try {
        const parsed = JSON.parse(stdout) as TelegramWorkerResponse;
        if (!parsed.ok && parsed.error) {
          resolve(parsed);
          return;
        }
        resolve(parsed);
      } catch {
        reject(new Error(stderr.trim() || stdout.trim() || `telegram_worker_parse_failed_${code ?? 'unknown'}`));
      }
    });

    child.stdin.end(input);
  });
}

export async function collectTelegramConnector(settings: AlphaRadarConnectorSettings): Promise<{ state: AlphaRadarConnectorState; candidates: AlphaRadarSocialCandidate[]; fetchedSources: string[] }> {
  if (!settings.enabled) {
    return {
      state: buildState(settings, { status: 'idle', connectionLabel: 'Off', message: 'Disabled' }),
      candidates: [],
      fetchedSources: [],
    };
  }
  if (settings.watchlist.length === 0) {
    return {
      state: buildState(settings, { status: 'idle', connectionLabel: 'No watchlist', message: 'Add Telegram channels or groups to watch.' }),
      candidates: [],
      fetchedSources: [],
    };
  }

  const result = await runTelegramWorker('collect', { watchlist: settings.watchlist, allowlist: settings.allowlist });
  return {
    state: buildState(settings, result),
    candidates: Array.isArray(result.observations)
      ? result.observations.map((item) => ({
        connectorType: 'telegram',
        source: item.source,
        title: item.title,
        excerpt: item.excerpt,
        observedAt: item.observedAt,
        assetTags: item.assetTags,
        topicTags: item.topicTags,
        provenance: item.provenance,
        metadata: item.metadata,
      }))
      : [],
    fetchedSources: Array.isArray(result.fetchedSources) ? result.fetchedSources : [],
  };
}

export async function requestTelegramConnectorCode(settings: AlphaRadarConnectorSettings): Promise<AlphaRadarConnectorState> {
  const result = await runTelegramWorker('request_code', { watchlist: settings.watchlist, allowlist: settings.allowlist });
  return buildState(settings, result);
}

export async function submitTelegramConnectorCode(settings: AlphaRadarConnectorSettings, code: string): Promise<AlphaRadarConnectorState> {
  const result = await runTelegramWorker('submit_code', { code, watchlist: settings.watchlist, allowlist: settings.allowlist });
  return buildState(settings, result);
}

export async function startTelegramConnectorQr(settings: AlphaRadarConnectorSettings): Promise<AlphaRadarConnectorState> {
  const result = await runTelegramWorker('start_qr', { watchlist: settings.watchlist, allowlist: settings.allowlist });
  return buildState(settings, result);
}

export async function cancelTelegramConnectorQr(settings: AlphaRadarConnectorSettings): Promise<AlphaRadarConnectorState> {
  const result = await runTelegramWorker('cancel_qr', { watchlist: settings.watchlist, allowlist: settings.allowlist });
  return buildState(settings, result);
}

export async function getTelegramConnectorStatus(settings: AlphaRadarConnectorSettings): Promise<AlphaRadarConnectorState> {
  const result = await runTelegramWorker('status', { watchlist: settings.watchlist, allowlist: settings.allowlist });
  return buildState(settings, result);
}
