import { nanoid } from 'nanoid';
import { BacktestV1SignalAdapter } from './strategyAdapter.js';
import { appendTradeEvent } from './tradeEvents.js';
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

interface SimulationStepOptions {
  timestamp?: string;
  mode?: 'paper' | 'replay';
}

export function runSimulationStep(db: DBShape, rawSymbol: string, price: number, options: SimulationStepOptions = {}) {
  const symbol = rawSymbol.toUpperCase();
  const now = options.timestamp ?? new Date().toISOString();
  const mode = options.mode ?? 'paper';
  const stepCorrelationId = nanoid();
  const riskPct = Number((RISK_PER_TRADE * 100).toFixed(2));
  const stopCapPct = Number((STOP_CAP_PCT * 100).toFixed(2));

  const lastTick = [...db.marketTicks].reverse().find((t) => t.symbol === symbol);
  const lastBias = [...db.biasCommands].reverse().find((b) => b.symbol === symbol)?.bias ?? 'off';

  db.marketTicks.push({ symbol, price, timestamp: now });

  const signal = adapter.evaluate({ symbol, price, lastPrice: lastTick?.price, bias: lastBias, ticks: db.marketTicks });
  const openPositionExists = db.positions.some((p) => p.symbol === symbol && p.status === 'open');

  if (signal.shouldOpen && signal.side) {
    appendTradeEvent(db, {
      symbol,
      type: 'signal_detected',
      timestamp: now,
      correlationId: stepCorrelationId,
      side: signal.side,
      price,
      reason: signal.reason,
      payload: {
        confidence: Number(signal.confidence.toFixed(3)),
        bias: lastBias
      }
    });
  }

  if (signal.shouldOpen && signal.side && openPositionExists) {
    appendTradeEvent(db, {
      symbol,
      type: 'order_rejected',
      timestamp: now,
      correlationId: stepCorrelationId,
      side: signal.side,
      price,
      reason: 'open_position_exists',
      payload: {
        triggerReason: signal.reason
      }
    });
  }

  if (signal.shouldOpen && signal.side && !openPositionExists) {
    const stopDistance = price * STOP_CAP_PCT;
    const size = 0.15; // user-directed paper size for first live trial

    const r = stopDistance;
    const tp1 = signal.side === 'long' ? price + 1.0 * r : price - 1.0 * r;
    const tp2 = signal.side === 'long' ? price + 2.2 * r : price - 2.2 * r;
    const tp3 = signal.side === 'long' ? price + 3.8 * r : price - 3.8 * r;

    const correlationId = nanoid();
    appendTradeEvent(db, {
      symbol,
      type: 'order_submitted',
      timestamp: now,
      correlationId,
      side: signal.side,
      price,
      quantity: size,
      reason: signal.reason,
      payload: {
        riskPct,
        stopCapPct,
        mode
      }
    });

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
      source: 'sim',
      correlationId
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
      note: `${signal.reason}; risk=${riskPct}%; sl_cap=${stopCapPct}%`,
      timestamp: now
    };
    db.tradeLogs.push(log);

    appendTradeEvent(db, {
      symbol,
      type: 'order_acknowledged',
      timestamp: now,
      correlationId,
      positionId: position.id,
      side: position.side,
      price,
      quantity: position.size,
      reason: 'paper_position_opened',
      payload: {
        entryPrice: position.entryPrice,
        stopLoss: position.stopLoss,
        tp1: position.tp1Price ?? null,
        tp2: position.tp2Price ?? null,
        tp3: position.tp3Price ?? null
      }
    });
  }

  for (const position of db.positions.filter((p) => p.symbol === symbol && p.status === 'open')) {
    const remainingBefore = positionRemainingSize(position);
    if (remainingBefore <= 0) continue;

    const correlationId = position.correlationId ?? stepCorrelationId;

    const hitSl = position.side === 'long' ? price <= position.stopLoss : price >= position.stopLoss;
    if (hitSl) {
      const pnlChunk = closeChunk(position, price, remainingBefore);
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
        quantity: remainingBefore,
        pnl: pnlChunk,
        note: 'sl_hit',
        timestamp: now
      });

      appendTradeEvent(db, {
        symbol,
        type: 'position_closed',
        timestamp: now,
        correlationId,
        positionId: position.id,
        side: position.side,
        price,
        quantity: remainingBefore,
        pnl: pnlChunk,
        reason: 'sl_hit',
        payload: {
          exitType: 'sl'
        }
      });
      continue;
    }

    const tp1Hit = position.tp1Price !== undefined && (position.side === 'long' ? price >= position.tp1Price : price <= position.tp1Price);
    const tp2Hit = position.tp2Price !== undefined && (position.side === 'long' ? price >= position.tp2Price : price <= position.tp2Price);
    const tp3Hit = position.tp3Price !== undefined && (position.side === 'long' ? price >= position.tp3Price : price <= position.tp3Price);

    if (!position.tp1Done && tp1Hit) {
      const qty = Number((position.size * 0.34).toFixed(6));
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
        note: 'tp1_34pct_be',
        timestamp: now
      });

      appendTradeEvent(db, {
        symbol,
        type: 'partial_fill',
        timestamp: now,
        correlationId,
        positionId: position.id,
        side: position.side,
        price,
        quantity: qty,
        pnl: pnlChunk,
        reason: 'tp1_34pct_be',
        payload: {
          level: 'tp1',
          stopMovedToBe: true
        }
      });
    }

    if (!position.tp2Done && tp2Hit) {
      const qty = Number((position.size * 0.33).toFixed(6));
      const closeQty = Math.min(qty, positionRemainingSize(position));
      const pnlChunk = closeChunk(position, price, closeQty);
      position.tp2Done = true;
      db.tradeLogs.push({
        id: nanoid(),
        positionId: position.id,
        symbol,
        action: 'partial',
        side: position.side,
        price,
        quantity: closeQty,
        pnl: pnlChunk,
        note: 'tp2_33pct',
        timestamp: now
      });

      appendTradeEvent(db, {
        symbol,
        type: 'partial_fill',
        timestamp: now,
        correlationId,
        positionId: position.id,
        side: position.side,
        price,
        quantity: closeQty,
        pnl: pnlChunk,
        reason: 'tp2_33pct',
        payload: {
          level: 'tp2',
          stopMovedToBe: false
        }
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

      appendTradeEvent(db, {
        symbol,
        type: 'position_closed',
        timestamp: now,
        correlationId,
        positionId: position.id,
        side: position.side,
        price,
        quantity: qty,
        pnl: pnlChunk,
        reason: 'tp3_final_exit',
        payload: {
          exitType: 'tp3'
        }
      });
      continue;
    }

    const unrealized = computeUnrealized(position, price);
    position.pnl = round2((position.realizedPnl ?? 0) + unrealized);

    if (positionRemainingSize(position) <= 0 && position.status === 'open') {
      position.status = 'closed';
      position.closedAt = now;
      position.pnl = round2(position.realizedPnl ?? 0);

      appendTradeEvent(db, {
        symbol,
        type: 'position_closed',
        timestamp: now,
        correlationId,
        positionId: position.id,
        side: position.side,
        price,
        quantity: 0,
        pnl: position.pnl,
        reason: 'remaining_size_zero',
        payload: {
          exitType: 'size_zero'
        }
      });
    }
  }

  return signal;
}
