import { nanoid } from 'nanoid';
import { BacktestV1SignalAdapter } from './strategyAdapter.js';
import { DBShape, Position, TradeLog } from './types.js';

const adapter = new BacktestV1SignalAdapter();

export function computePositionPnl(position: Position, markPrice: number): number {
  const diff = position.side === 'long' ? markPrice - position.entryPrice : position.entryPrice - markPrice;
  return Number((diff * position.size).toFixed(2));
}

export function runSimulationStep(db: DBShape, symbol: string, price: number) {
  const now = new Date().toISOString();
  const lastTick = [...db.marketTicks].reverse().find((t) => t.symbol === symbol);
  const lastBias = [...db.biasCommands].reverse().find((b) => b.symbol === symbol)?.bias ?? 'off';

  db.marketTicks.push({ symbol, price, timestamp: now });

  const signal = adapter.evaluate({ symbol, price, lastPrice: lastTick?.price, bias: lastBias });
  const openPositionExists = db.positions.some((p) => p.symbol === symbol && p.status === 'open');

  if (signal.shouldOpen && signal.side && !openPositionExists) {
    const stopOffset = price * 0.007;
    const tpOffset = stopOffset * 2.2;
    const position: Position = {
      id: nanoid(),
      symbol,
      side: signal.side,
      entryPrice: price,
      stopLoss: Number((signal.side === 'long' ? price - stopOffset : price + stopOffset).toFixed(2)),
      takeProfit: Number((signal.side === 'long' ? price + tpOffset : price - tpOffset).toFixed(2)),
      size: 0.01,
      openedAt: now,
      status: 'open',
      pnl: 0,
      source: 'sim'
    };
    db.positions.push(position);
    const log: TradeLog = {
      id: nanoid(),
      positionId: position.id,
      symbol,
      action: 'open',
      side: position.side,
      price,
      quantity: position.size,
      note: signal.reason,
      timestamp: now
    };
    db.tradeLogs.push(log);
  }

  for (const position of db.positions.filter((p) => p.symbol === symbol && p.status === 'open')) {
    position.pnl = computePositionPnl(position, price);
    const hitTp = position.side === 'long' ? price >= position.takeProfit : price <= position.takeProfit;
    const hitSl = position.side === 'long' ? price <= position.stopLoss : price >= position.stopLoss;

    if (hitTp || hitSl) {
      position.status = 'closed';
      position.closedAt = now;
      const realizedPnl = computePositionPnl(position, price);
      position.pnl = realizedPnl;
      db.tradeLogs.push({
        id: nanoid(),
        positionId: position.id,
        symbol,
        action: 'close',
        side: position.side,
        price,
        quantity: position.size,
        pnl: realizedPnl,
        note: hitTp ? 'tp_hit' : 'sl_hit',
        timestamp: now
      });
    }
  }

  return signal;
}
