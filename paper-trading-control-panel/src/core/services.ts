import { nanoid } from 'nanoid';
import { DBShape, Bias, Stats } from './types.js';

export function submitBias(db: DBShape, symbol: string, bias: Bias) {
  const cmd = { id: nanoid(), symbol, bias, createdAt: new Date().toISOString() };
  db.biasCommands.push(cmd);
  db.tradeLogs.push({
    id: nanoid(),
    symbol,
    action: 'bias',
    note: `${symbol} ${bias}`,
    timestamp: cmd.createdAt
  });
  return cmd;
}

export function getStats(db: DBShape): Stats {
  const closed = db.positions.filter((p) => p.status === 'closed');
  const open = db.positions.filter((p) => p.status === 'open');

  const realizedPnl = closed.reduce((a, p) => a + p.pnl, 0);
  const openPnl = open.reduce((a, p) => a + p.pnl, 0);
  const wins = closed.filter((p) => p.pnl > 0).length;

  return {
    totalTrades: closed.length,
    winRate: closed.length ? Number(((wins / closed.length) * 100).toFixed(2)) : 0,
    realizedPnl: Number(realizedPnl.toFixed(2)),
    openPnl: Number(openPnl.toFixed(2)),
    avgPnl: closed.length ? Number((realizedPnl / closed.length).toFixed(2)) : 0
  };
}
