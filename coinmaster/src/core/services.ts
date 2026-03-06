import { nanoid } from 'nanoid';
import { appendTradeEvent } from './tradeEvents.js';
import { DBShape, Bias, Stats, StatsPeriod } from './types.js';

interface StatsOptions {
  period: StatsPeriod;
}

function periodDays(period: StatsPeriod): number {
  return period === 'week' ? 7 : 30;
}

function normalizeBiasSymbol(symbol: string): string {
  const raw = String(symbol ?? '').trim();
  if (!raw) return '';

  if (raw.includes(':')) {
    const [namespaceRaw, symbolRaw] = raw.split(':', 2);
    const namespace = String(namespaceRaw ?? '').trim().toLowerCase();
    const baseSymbol = String(symbolRaw ?? '').trim().toUpperCase();
    if (namespace && baseSymbol) return `${namespace}:${baseSymbol}`;
  }

  return raw.toUpperCase();
}

export function submitBias(db: DBShape, symbol: string, bias: Bias) {
  const normalizedSymbol = normalizeBiasSymbol(symbol);
  const cmd = { id: nanoid(), symbol: normalizedSymbol, bias, createdAt: new Date().toISOString() };
  db.biasCommands.push(cmd);
  db.tradeLogs.push({
    id: nanoid(),
    symbol: normalizedSymbol,
    action: 'bias',
    note: `${normalizedSymbol} ${bias}`,
    timestamp: cmd.createdAt
  });

  appendTradeEvent(db, {
    symbol: normalizedSymbol,
    type: 'bias_changed',
    timestamp: cmd.createdAt,
    correlationId: cmd.id,
    reason: 'operator_bias_command',
    payload: {
      bias
    }
  });

  return cmd;
}

export function getStats(db: DBShape, options: StatsOptions): Stats {
  const days = periodDays(options.period);
  const cutoffTs = Date.now() - days * 24 * 60 * 60 * 1000;
  const deposit = db.settings?.depositUsd ?? 1000;

  const closed = db.positions.filter(
    (p) => p.status === 'closed' && Date.parse(p.closedAt ?? p.openedAt) >= cutoffTs
  );
  const open = db.positions.filter(
    (p) => p.status === 'open' && Date.parse(p.openedAt) >= cutoffTs
  );

  const realizedPnl = closed.reduce((a, p) => a + p.pnl, 0);
  const openPnl = open.reduce((a, p) => a + p.pnl, 0);
  const wins = closed.filter((p) => p.pnl > 0).length;

  const realizedPnlPct = deposit > 0 ? (realizedPnl / deposit) * 100 : 0;
  const openPnlPct = deposit > 0 ? (openPnl / deposit) * 100 : 0;
  const equityUsd = deposit + realizedPnl + openPnl;
  const equityPct = deposit > 0 ? ((equityUsd - deposit) / deposit) * 100 : 0;

  return {
    period: options.period,
    periodDays: days,
    depositUsd: Number(deposit.toFixed(2)),
    totalTrades: closed.length,
    winRate: closed.length ? Number(((wins / closed.length) * 100).toFixed(2)) : 0,
    realizedPnl: Number(realizedPnl.toFixed(2)),
    realizedPnlPct: Number(realizedPnlPct.toFixed(2)),
    openPnl: Number(openPnl.toFixed(2)),
    openPnlPct: Number(openPnlPct.toFixed(2)),
    avgPnl: closed.length ? Number((realizedPnl / closed.length).toFixed(2)) : 0,
    equityUsd: Number(equityUsd.toFixed(2)),
    equityPct: Number(equityPct.toFixed(2))
  };
}
