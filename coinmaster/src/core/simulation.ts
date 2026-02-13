import { nanoid } from 'nanoid';
import { BacktestV1SignalAdapter } from './strategyAdapter.js';
import { DBShape, Position, TradeLog } from './types.js';

const adapter = new BacktestV1SignalAdapter();
const RISK_PER_TRADE = 0.0125; // 1.25%
const STOP_CAP_PCT = 0.007; // 0.70%

function round2(v: number): number {
  return Number(v.toFixed(2));
}

function computeDiff(side: Position['side'], entry: number, mark: number): number {
  return side === 'long' ? mark - entry : entry - mark;
}

function positionRemainingSize(position: Position): number {
  return position.remainingSize ?? position.size;
}

function computeUnrealized(position: Position, markPrice: number): number {
  return computeDiff(position.side, position.entryPrice, markPrice) * positionRemainingSize(position);
}

function closeChunk(position: Position, price: number, qty: number) {
  const realized = computeDiff(position.side, position.entryPrice, price) * qty;
  position.realizedPnl = (position.realizedPnl ?? 0) + realized;
  position.remainingSize = Math.max(0, positionRemainingSize(position) - qty);
  return round2(realized);
}

export function runSimulationStep(db: DBShape, symbol: string, price: number) {
  const now = new Date().toISOString();
  const lastTick = [...db.marketTicks].reverse().find((t) => t.symbol === symbol);
  const lastBias = [...db.biasCommands].reverse().find((b) => b.symbol === symbol)?.bias ?? 'off';

  db.marketTicks.push({ symbol, price, timestamp: now });

  const signal = adapter.evaluate({ symbol, price, lastPrice: lastTick?.price, bias: lastBias, ticks: db.marketTicks });
  const openPositionExists = db.positions.some((p) => p.symbol === symbol && p.status === 'open');

  if (signal.shouldOpen && signal.side && !openPositionExists) {
    const stopDistance = price * STOP_CAP_PCT;
    const size = 0.15; // user-directed paper size for first live trial

    const r = stopDistance;
    const tp1 = signal.side === 'long' ? price + 1.0 * r : price - 1.0 * r;
    const tp2 = signal.side === 'long' ? price + 2.2 * r : price - 2.2 * r;
    const tp3 = signal.side === 'long' ? price + 3.8 * r : price - 3.8 * r;

    const position: Position = {
      id: nanoid(),
      symbol,
      side: signal.side,
      entryPrice: round2(price),
      stopLoss: round2(signal.side === 'long' ? price - stopDistance : price + stopDistance),
      takeProfit: round2(tp2),
      size: Number(size.toFixed(6)),
      remainingSize: Number(size.toFixed(6)),
      realizedPnl: 0,
      tp1Price: round2(tp1),
      tp2Price: round2(tp2),
      tp3Price: round2(tp3),
      tp1Done: false,
      tp2Done: false,
      tp3Done: false,
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
      note: `${signal.reason}; risk=1.25%; sl_cap=0.70%`,
      timestamp: now
    };
    db.tradeLogs.push(log);
  }

  for (const position of db.positions.filter((p) => p.symbol === symbol && p.status === 'open')) {
    const remainingBefore = positionRemainingSize(position);
    if (remainingBefore <= 0) continue;

    const hitSl = position.side === 'long' ? price <= position.stopLoss : price >= position.stopLoss;
    if (hitSl) {
      const pnlChunk = closeChunk(position, price, remainingBefore);
      position.status = 'closed';
      position.closedAt = now;
      position.pnl = round2((position.realizedPnl ?? 0));
      db.tradeLogs.push({
        id: nanoid(),
        positionId: position.id,
        symbol,
        action: 'close',
        side: position.side,
        price,
        quantity: remainingBefore,
        pnl: pnlChunk,
        note: 'sl_hit',
        timestamp: now
      });
      continue;
    }

    const tp1Hit = position.tp1Price !== undefined && (position.side === 'long' ? price >= position.tp1Price : price <= position.tp1Price);
    const tp2Hit = position.tp2Price !== undefined && (position.side === 'long' ? price >= position.tp2Price : price <= position.tp2Price);
    const tp3Hit = position.tp3Price !== undefined && (position.side === 'long' ? price >= position.tp3Price : price <= position.tp3Price);

    if (!position.tp1Done && tp1Hit) {
      const qty = Number((position.size * 0.4).toFixed(6));
      const pnlChunk = closeChunk(position, price, qty);
      position.tp1Done = true;
      position.stopLoss = round2(position.entryPrice); // BE after TP1
      db.tradeLogs.push({
        id: nanoid(),
        positionId: position.id,
        symbol,
        action: 'partial',
        side: position.side,
        price,
        quantity: qty,
        pnl: pnlChunk,
        note: 'tp1_40pct_be',
        timestamp: now
      });
    }

    if (!position.tp2Done && tp2Hit) {
      const qty = Number((position.size * 0.35).toFixed(6));
      const pnlChunk = closeChunk(position, price, Math.min(qty, positionRemainingSize(position)));
      position.tp2Done = true;
      db.tradeLogs.push({
        id: nanoid(),
        positionId: position.id,
        symbol,
        action: 'partial',
        side: position.side,
        price,
        quantity: qty,
        pnl: pnlChunk,
        note: 'tp2_35pct',
        timestamp: now
      });
    }

    if (!position.tp3Done && tp3Hit) {
      const qty = positionRemainingSize(position);
      const pnlChunk = closeChunk(position, price, qty);
      position.tp3Done = true;
      position.status = 'closed';
      position.closedAt = now;
      position.pnl = round2(position.realizedPnl ?? 0);
      db.tradeLogs.push({
        id: nanoid(),
        positionId: position.id,
        symbol,
        action: 'close',
        side: position.side,
        price,
        quantity: qty,
        pnl: pnlChunk,
        note: 'tp3_final_exit',
        timestamp: now
      });
      continue;
    }

    const unrealized = computeUnrealized(position, price);
    position.pnl = round2((position.realizedPnl ?? 0) + unrealized);

    if (positionRemainingSize(position) <= 0 && position.status === 'open') {
      position.status = 'closed';
      position.closedAt = now;
      position.pnl = round2(position.realizedPnl ?? 0);
    }
  }

  return signal;
}
