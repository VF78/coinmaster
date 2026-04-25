/**
 * backtestEngine.ts
 *
 * Isolated backtest execution engine.
 * Uses the SAME canonical signal evaluators and TP/SL logic as the live production engine.
 * Guaranteed zero side-effects: no exchange calls, no DB writes, no Telegram, no live state mutation.
 *
 * Input:  TradingRulesSettings snapshot + historical candles + time range
 * Output: BacktestRun with summary + per-symbol stats + trade list
 */

import { nanoid } from 'nanoid';
import type { Candle, CandleTimeframe } from '../exchange/types.js';
import type {
  BacktestRun,
  BacktestRunSummary,
  BacktestRunSymbolStats,
  TradeSide,
  TradingRulesSettings,
  TradingRulesTimeframe,
} from '../shared/dto.js';
import { evaluateTimeframe } from './engulfingEvaluator.js';
import { evaluateFvg, type FvgTimeframe } from './fvgEvaluator.js';
import { evaluateSignalQuality } from './signalQualityContext.js';

// ─── Internal types (not exported to DTO — backtest-only) ─────────────

interface SimPosition {
  id: string;
  symbol: string;
  side: TradeSide;
  entryPrice: number;
  size: number;
  remainingSize: number;
  stopLoss: number;
  takeProfits: number[];
  tp1Done: boolean;
  tp2Done: boolean;
  tp3Done: boolean;
  openedAt: string;
  entryTimeframe: TradingRulesTimeframe;
  closedAt?: string;
  status: 'open' | 'closed';
  realizedPnl: number;
  closeReason?: string;
}

interface BacktestTradeRecord {
  positionId: string;
  symbol: string;
  side: TradeSide;
  action: 'open' | 'partial' | 'close';
  price: number;
  size: number;
  pnl: number;
  reason: string;
  timestamp: string;
}

export interface BacktestCandleSet {
  symbol: string;
  timeframe: CandleTimeframe;
  candles: Candle[];
}

export interface BacktestEngineInput {
  run: BacktestRun;
  candleSets: BacktestCandleSet[];
  depositUsd: number;
}

export interface BacktestEngineOutput {
  summary: BacktestRunSummary;
  bySymbol: BacktestRunSymbolStats[];
  trades: BacktestTradeRecord[];
  equityCurve: number[];
}

// ─── Helpers ──────────────────────────────────────────────────────────

const TF_MS: Record<string, number> = {
  '5m': 5 * 60_000,
  '15m': 15 * 60_000,
  '1h': 60 * 60_000,
  '4h': 4 * 60 * 60_000,
};

function round(v: number, decimals = 2): number {
  const f = 10 ** decimals;
  return Math.round(v * f) / f;
}

function computeDiff(side: TradeSide, entry: number, exit: number): number {
  return side === 'long' ? exit - entry : entry - exit;
}

function resolveTpSlFromRules(
  entryPrice: number,
  side: TradeSide,
  rules: TradingRulesSettings,
): { stopLoss: number; takeProfits: number[] } {
  const isLong = side === 'long';
  const slPct = rules.slPct || 2;
  const tpLevels = rules.tpLevels?.length ? rules.tpLevels : (rules.tpPct ? [rules.tpPct] : [6]);

  const stopLoss = isLong
    ? entryPrice * (1 - slPct / 100)
    : entryPrice * (1 + slPct / 100);

  const takeProfits = tpLevels.map((pct) => {
    return isLong
      ? entryPrice * (1 + pct / 100)
      : entryPrice * (1 - pct / 100);
  });

  return { stopLoss: round(stopLoss, 8), takeProfits: takeProfits.map((tp) => round(tp, 8)) };
}

function computeSizeFromRules(
  price: number,
  depositUsd: number,
  rules: TradingRulesSettings,
  symbol: string,
): number {
  const coin = rules.coins.find((c) => c.symbol.toUpperCase() === symbol.toUpperCase());
  const allocationPct = coin?.pct ?? 100;
  const leverage = rules.maxLeverage || 1;

  const marginUsd = depositUsd * (allocationPct / 100);
  const notionalUsd = marginUsd * leverage;
  const rawSize = notionalUsd / price;

  return Math.floor(rawSize * 1e6) / 1e6;
}

// TP split sizing (same as prod: 40% / 35% / 25% for 3 TPs)
const TP_SPLIT_3 = [0.4, 0.35, 0.25];
const TP_SPLIT_2 = [0.5, 0.5];
const TP_SPLIT_1 = [1.0];

function tpSplitRatios(count: number): number[] {
  if (count >= 3) return TP_SPLIT_3;
  if (count === 2) return TP_SPLIT_2;
  return TP_SPLIT_1;
}

function computeMaxDrawdownPct(equityCurve: number[]): number {
  if (equityCurve.length === 0) return 0;
  let peak = equityCurve[0];
  let maxDd = 0;
  for (const value of equityCurve) {
    peak = Math.max(peak, value);
    if (peak > 0) {
      const dd = ((peak - value) / peak) * 100;
      maxDd = Math.max(maxDd, dd);
    }
  }
  return round(maxDd);
}

function isSideAllowed(side: TradeSide, biasMode: BacktestRun['biasMode'] | undefined): boolean {
  const effective = biasMode ?? 'both';
  if (effective === 'both') return true;
  return side === effective;
}

function closedCandlesAtTime(candles: Candle[], eventCloseMs: number, tf: string): Candle[] {
  const tfMs = TF_MS[tf] ?? 900_000;
  return candles.filter((c) => Date.parse(c.timestamp) + tfMs <= eventCloseMs);
}

// ─── Main Engine ──────────────────────────────────────────────────────

export function runBacktestEngine(input: BacktestEngineInput): BacktestEngineOutput {
  const { run, candleSets, depositUsd } = input;
  const rules = run.rulesSnapshot;
  const symbol = run.symbol;

  // Organize candles by timeframe, sorted by time
  const candlesByTf = new Map<string, Candle[]>();
  for (const cs of candleSets) {
    const sorted = [...cs.candles].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
    candlesByTf.set(cs.timeframe, sorted);
  }

  // Determine which timeframes to use for entry and exit signals
  const entryTfs: TradingRulesTimeframe[] = rules.entryTimeframes?.length
    ? rules.entryTimeframes
    : ['15m'];
  const exitTfs: TradingRulesTimeframe[] = rules.emergencyExitTimeframes?.length
    ? rules.emergencyExitTimeframes
    : ['1h'];
  const fvgTfs: FvgTimeframe[] = ['1h', '4h'];
  const lookback = rules.engulfingLookbackCandles ?? 30;
  const fvgRetracePct = rules.fvgRetrace ?? 50;
  const exitClosePct = rules.exitClosePct ?? 50;
  const fvgQualification = {
    minWidthPct: rules.fvgMinWidthPct ?? 0.3,
    requireSweep: rules.fvgRequireSweep ?? false,
    sweepLookbackCandles: rules.fvgSweepLookbackCandles ?? 20,
    requireFirstTouch: rules.fvgRequireFirstTouch ?? false,
    maxZoneAgeCandles: rules.maxZoneAgeCandles ?? 12,
    requireConfirmation: rules.fvgRequireConfirmation ?? false,
    confirmationTimeframes: rules.fvgConfirmationTimeframes ?? ['15m'],
  };

  // Issue #61 — Mirror live signal-quality thresholds.
  const regimeTf: TradingRulesTimeframe = (rules.regimeTf ?? '1h');
  const adxMin = Number(rules.adxMin ?? 0);
  const minImpulseAtr = Number(rules.minImpulseAtr ?? 0);
  const minExpectedRr = Number(rules.minExpectedRr ?? 0);
  const qualityGateEnabled = adxMin > 0 || minImpulseAtr > 0 || minExpectedRr > 0;
  const timeStopBars = Math.max(0, Math.round(Number(rules.timeStopBars ?? 0)));

  // Build a unified timeline of candle close events across all TFs
  // Each event = { timestamp, tf, candleIndex }
  interface TimelineEvent {
    timestampMs: number;
    tf: string;
    candleIndex: number;
    closePrice: number;
  }

  const timeline: TimelineEvent[] = [];
  for (const [tf, candles] of candlesByTf.entries()) {
    const tfMs = TF_MS[tf] ?? 900_000;
    for (let i = 0; i < candles.length; i++) {
      const closeMs = Date.parse(candles[i].timestamp) + tfMs;
      if (closeMs >= run.startTimeMs && closeMs <= run.endTimeMs) {
        timeline.push({
          timestampMs: closeMs,
          tf,
          candleIndex: i,
          closePrice: candles[i].close,
        });
      }
    }
  }
  timeline.sort((a, b) => a.timestampMs - b.timestampMs || a.tf.localeCompare(b.tf));

  // State
  const positions: SimPosition[] = [];
  const trades: BacktestTradeRecord[] = [];
  const equityCurve: number[] = [];
  let currentEquity = depositUsd;
  const entryDebounce = new Map<string, number>();
  const exitDebounce = new Map<string, number>();

  // Stats accumulators
  let slCount = 0;
  let tp1Count = 0;
  let tp2Count = 0;
  let tp3Count = 0;
  let emergencyExitCount = 0;
  let rejectedSignals = 0;

  function closeChunk(pos: SimPosition, price: number, qty: number): number {
    const pnl = computeDiff(pos.side, pos.entryPrice, price) * qty;
    pos.realizedPnl += pnl;
    pos.remainingSize = Math.max(0, pos.remainingSize - qty);
    return round(pnl);
  }

  function getOpenPosition(): SimPosition | undefined {
    return positions.find((p) => p.symbol === symbol && p.status === 'open');
  }

  function recordTrade(
    positionId: string,
    action: 'open' | 'partial' | 'close',
    price: number,
    size: number,
    pnl: number,
    reason: string,
    timestamp: string,
  ) {
    trades.push({ positionId, symbol, side: positions.find((p) => p.id === positionId)?.side ?? 'long', action, price, size, pnl, reason, timestamp });
  }

  // Process each timeline event
  for (const event of timeline) {
    const { timestampMs, tf, candleIndex } = event;
    const timestamp = new Date(timestampMs).toISOString();
    const candles = candlesByTf.get(tf) ?? [];

    // Get up-to-and-including current candle as "closed" candles for evaluator
    const closedCandles = candles.slice(0, candleIndex + 1);
    if (closedCandles.length < 3) continue;

    const currentPrice = closedCandles[closedCandles.length - 1].close;
    const openPos = getOpenPosition();

    // ── TICK: check TP/SL hits on open position ──────────────────────
    if (openPos) {
      const remaining = openPos.remainingSize;
      if (remaining <= 0) {
        openPos.status = 'closed';
        openPos.closedAt = timestamp;
        continue;
      }

      // SL check
      const hitSl = openPos.side === 'long'
        ? currentPrice <= openPos.stopLoss
        : currentPrice >= openPos.stopLoss;

      if (hitSl) {
        const pnl = closeChunk(openPos, currentPrice, remaining);
        openPos.status = 'closed';
        openPos.closedAt = timestamp;
        openPos.closeReason = 'sl_hit';
        slCount++;
        recordTrade(openPos.id, 'close', currentPrice, remaining, pnl, 'sl_hit', timestamp);
        currentEquity += pnl;
        equityCurve.push(currentEquity);
        continue;
      }

      // TP checks (same order as prod: TP1 → TP2 → TP3)
      const tps = openPos.takeProfits;
      const splits = tpSplitRatios(tps.length);

      if (!openPos.tp1Done && tps[0] !== undefined) {
        const hitTp1 = openPos.side === 'long'
          ? currentPrice >= tps[0]
          : currentPrice <= tps[0];
        if (hitTp1) {
          const qty = round(openPos.size * splits[0], 6);
          const pnl = closeChunk(openPos, currentPrice, qty);
          openPos.tp1Done = true;
          openPos.stopLoss = round(openPos.entryPrice, 8); // move SL to break-even
          tp1Count++;
          recordTrade(openPos.id, 'partial', currentPrice, qty, pnl, 'tp1_partial_be', timestamp);
          currentEquity += pnl;
        }
      }

      if (!openPos.tp2Done && tps[1] !== undefined) {
        const hitTp2 = openPos.side === 'long'
          ? currentPrice >= tps[1]
          : currentPrice <= tps[1];
        if (hitTp2) {
          const qty = round(openPos.size * splits[1], 6);
          const actualQty = Math.min(qty, openPos.remainingSize);
          const pnl = closeChunk(openPos, currentPrice, actualQty);
          openPos.tp2Done = true;
          tp2Count++;
          recordTrade(openPos.id, 'partial', currentPrice, actualQty, pnl, 'tp2_partial', timestamp);
          currentEquity += pnl;
        }
      }

      if (!openPos.tp3Done && tps[2] !== undefined) {
        const hitTp3 = openPos.side === 'long'
          ? currentPrice >= tps[2]
          : currentPrice <= tps[2];
        if (hitTp3) {
          const actualQty = openPos.remainingSize;
          const pnl = closeChunk(openPos, currentPrice, actualQty);
          openPos.tp3Done = true;
          openPos.status = 'closed';
          openPos.closedAt = timestamp;
          openPos.closeReason = 'tp3_full_close';
          tp3Count++;
          recordTrade(openPos.id, 'close', currentPrice, actualQty, pnl, 'tp3_full_close', timestamp);
          currentEquity += pnl;
          equityCurve.push(currentEquity);
          continue;
        }
      }

      // If only 1 or 2 TPs and all done, close remaining
      if (openPos.remainingSize <= 0 || (tps.length <= 2 && openPos.tp2Done) || (tps.length <= 1 && openPos.tp1Done)) {
        if (openPos.remainingSize > 0) {
          const pnl = closeChunk(openPos, currentPrice, openPos.remainingSize);
          recordTrade(openPos.id, 'close', currentPrice, openPos.remainingSize, pnl, 'tp_all_done', timestamp);
          currentEquity += pnl;
        }
        openPos.status = 'closed';
        openPos.closedAt = timestamp;
        openPos.closeReason = 'tp_all_done';
        equityCurve.push(currentEquity);
        continue;
      }

      // Time stop: if there is no TP1 follow-through after N entry-TF bars,
      // close the remaining position instead of waiting for a reverse signal.
      if (timeStopBars > 0 && !openPos.tp1Done) {
        const entryTfMs = TF_MS[openPos.entryTimeframe] ?? TF_MS[tf] ?? 900_000;
        const openedMs = Date.parse(openPos.openedAt);
        const barsHeld = Number.isFinite(openedMs) ? Math.floor((timestampMs - openedMs) / entryTfMs) : 0;
        if (barsHeld >= timeStopBars && openPos.remainingSize > 0) {
          const remaining = openPos.remainingSize;
          const pnl = closeChunk(openPos, currentPrice, remaining);
          openPos.status = 'closed';
          openPos.closedAt = timestamp;
          openPos.closeReason = 'time_stop';
          recordTrade(openPos.id, 'close', currentPrice, remaining, pnl, 'time_stop', timestamp);
          currentEquity += pnl;
          equityCurve.push(currentEquity);
          continue;
        }
      }

      // Emergency exit check (engulfing reverse signal)
      if (exitClosePct > 0) {
        const exitTfSet = exitTfs as string[];
        if (exitTfSet.includes(tf)) {
          const exitSignal = evaluateTimeframe(closedCandles, tf as TradingRulesTimeframe, lookback);
          if (exitSignal.detected && exitSignal.direction) {
            const isReverse =
              (openPos.side === 'long' && exitSignal.direction === 'bearish') ||
              (openPos.side === 'short' && exitSignal.direction === 'bullish');
            if (isReverse) {
              const debounceKey = `exit:${symbol}:${tf}:${exitSignal.direction}`;
              const candleOpenMs = Date.parse(closedCandles[closedCandles.length - 1].timestamp);
              const lastProcessed = exitDebounce.get(debounceKey) ?? -1;
              if (candleOpenMs > lastProcessed) {
                exitDebounce.set(debounceKey, candleOpenMs);
                const exitQty = round(openPos.remainingSize * (exitClosePct / 100), 6);
                if (exitQty > 0) {
                  const pnl = closeChunk(openPos, currentPrice, exitQty);
                  emergencyExitCount++;
                  recordTrade(openPos.id, exitQty >= openPos.remainingSize + exitQty ? 'close' : 'partial', currentPrice, exitQty, pnl, `emergency_exit_${tf}`, timestamp);
                  currentEquity += pnl;

                  // If partial emergency exit, move SL to entry
                  if (openPos.remainingSize > 0 && exitClosePct < 100) {
                    openPos.stopLoss = round(openPos.entryPrice, 8);
                  }
                  if (openPos.remainingSize <= 0) {
                    openPos.status = 'closed';
                    openPos.closedAt = timestamp;
                    openPos.closeReason = 'emergency_exit';
                  }
                }
              }
            }
          }
        }
      }

      equityCurve.push(currentEquity);
      continue;
    }

    // ── NO OPEN POSITION: check for entry signals ────────────────────
    // Engulfing entry
    const entryTfSet = entryTfs as string[];
    if (entryTfSet.includes(tf)) {
      const signal = evaluateTimeframe(closedCandles, tf as TradingRulesTimeframe, lookback);
      if (signal.detected && signal.direction) {
        const side: TradeSide = signal.direction === 'bullish' ? 'long' : 'short';
        if (!isSideAllowed(side, run.biasMode)) {
          rejectedSignals++;
          equityCurve.push(currentEquity);
          continue;
        }
        const debounceKey = `entry:${symbol}:${tf}:${signal.direction}`;
        const tfMs = TF_MS[tf] ?? 900_000;
        const lastFired = entryDebounce.get(debounceKey) ?? 0;
        if (timestampMs - lastFired >= tfMs) {
          entryDebounce.set(debounceKey, timestampMs);

          if (currentEquity <= 0) {
            rejectedSignals++;
            equityCurve.push(currentEquity);
            continue;
          }

          const size = computeSizeFromRules(currentPrice, currentEquity, rules, symbol);
          if (size <= 0) { rejectedSignals++; equityCurve.push(currentEquity); continue; }

          const { stopLoss, takeProfits } = resolveTpSlFromRules(currentPrice, side, rules);

          if (qualityGateEnabled) {
            const regimeCandles = closedCandlesAtTime(candlesByTf.get(regimeTf) ?? [], timestampMs, regimeTf);
            const verdict = evaluateSignalQuality({
              side,
              regimeCandles,
              regimeTf,
              entryCandles: closedCandles,
              entry: currentPrice,
              stopLoss,
              takeProfits,
              thresholds: { adxMin, minImpulseAtr, minExpectedRr, requireQuartile: minImpulseAtr > 0 },
            });
            if (!verdict.ok) {
              rejectedSignals++;
              equityCurve.push(currentEquity);
              continue;
            }
          }
          const pos: SimPosition = {
            id: nanoid(),
            symbol,
            side,
            entryPrice: currentPrice,
            size,
            remainingSize: size,
            stopLoss,
            takeProfits,
            tp1Done: false,
            tp2Done: false,
            tp3Done: false,
            openedAt: timestamp,
            entryTimeframe: tf as TradingRulesTimeframe,
            status: 'open',
            realizedPnl: 0,
          };
          positions.push(pos);
          recordTrade(pos.id, 'open', currentPrice, size, 0, `engulfing_entry_${tf}`, timestamp);
          equityCurve.push(currentEquity);
          continue;
        }
      }
    }

    // FVG entry
    if (!getOpenPosition()) {
      let openedFvgPosition = false;
      for (const fvgTf of fvgTfs) {
        const htfCandles = closedCandlesAtTime(candlesByTf.get(fvgTf) ?? [], timestampMs, fvgTf);
        if (htfCandles.length < 3) continue;

        const fvgSignal = evaluateFvg(htfCandles, fvgTf, {
          currentPrice,
          currentTimeMs: timestampMs,
          retracePct: fvgRetracePct,
          lookback: 10,
          qualification: fvgQualification,
          lowerTfCandles: {
            '5m': closedCandlesAtTime(candlesByTf.get('5m') ?? [], timestampMs, '5m'),
            '15m': closedCandlesAtTime(candlesByTf.get('15m') ?? [], timestampMs, '15m'),
            '1h': closedCandlesAtTime(candlesByTf.get('1h') ?? [], timestampMs, '1h'),
            '4h': closedCandlesAtTime(candlesByTf.get('4h') ?? [], timestampMs, '4h'),
          },
        });
        if (!fvgSignal.detected || !fvgSignal.direction) continue;

        const side: TradeSide = fvgSignal.direction === 'bullish' ? 'long' : 'short';
        if (!isSideAllowed(side, run.biasMode)) {
          rejectedSignals++;
          continue;
        }
        const debounceKey = `fvg:${symbol}:${fvgTf}:${fvgSignal.direction}`;
        const debounceTfMs = TF_MS[fvgTf] ?? 3_600_000;
        const lastFired = entryDebounce.get(debounceKey) ?? 0;
        if (timestampMs - lastFired < debounceTfMs) continue;
        entryDebounce.set(debounceKey, timestampMs);

        if (currentEquity <= 0) {
          rejectedSignals++;
          continue;
        }

        const size = computeSizeFromRules(currentPrice, currentEquity, rules, symbol);
        if (size <= 0) { rejectedSignals++; continue; }

        const { stopLoss, takeProfits } = resolveTpSlFromRules(currentPrice, side, rules);

        if (qualityGateEnabled) {
          const regimeCandles = closedCandlesAtTime(candlesByTf.get(regimeTf) ?? [], timestampMs, regimeTf);
          const fvgEntryCandles = closedCandlesAtTime(candlesByTf.get(fvgTf) ?? [], timestampMs, fvgTf);
          const fvgCompletionIndex = fvgSignal.zone?.completionIndex;
          const fvgImpulseTriple = typeof fvgCompletionIndex === 'number'
            ? {
                c0: fvgEntryCandles[fvgCompletionIndex - 2],
                c1: fvgEntryCandles[fvgCompletionIndex - 1],
                c2: fvgEntryCandles[fvgCompletionIndex],
              }
            : undefined;
          const verdict = evaluateSignalQuality({
            side,
            regimeCandles,
            regimeTf,
            entryCandles: fvgEntryCandles,
            impulseTriple: fvgImpulseTriple?.c0 && fvgImpulseTriple.c1 && fvgImpulseTriple.c2 ? fvgImpulseTriple : undefined,
            entry: currentPrice,
            stopLoss,
            takeProfits,
            thresholds: { adxMin, minImpulseAtr, minExpectedRr, requireQuartile: minImpulseAtr > 0 },
          });
          if (!verdict.ok) {
            rejectedSignals++;
            continue;
          }
        }

        const pos: SimPosition = {
          id: nanoid(),
          symbol,
          side,
          entryPrice: currentPrice,
          size,
          remainingSize: size,
          stopLoss,
          takeProfits,
          tp1Done: false,
          tp2Done: false,
          tp3Done: false,
          openedAt: timestamp,
          entryTimeframe: fvgTf,
          status: 'open',
          realizedPnl: 0,
        };
        positions.push(pos);
        recordTrade(pos.id, 'open', currentPrice, size, 0, `fvg_entry_${fvgTf}_${fvgSignal.reason}`, timestamp);
        equityCurve.push(currentEquity);
        openedFvgPosition = true;
        break;
      }
      if (openedFvgPosition) continue;
    }

    equityCurve.push(currentEquity);
  }

  // Force-close any still-open position at the last known price
  const openPos = getOpenPosition();
  if (openPos && openPos.remainingSize > 0) {
    const lastPrice = timeline.length > 0 ? timeline[timeline.length - 1].closePrice : openPos.entryPrice;
    const pnl = closeChunk(openPos, lastPrice, openPos.remainingSize);
    openPos.status = 'closed';
    openPos.closedAt = new Date(run.endTimeMs).toISOString();
    openPos.closeReason = 'backtest_end';
    recordTrade(openPos.id, 'close', lastPrice, openPos.remainingSize, pnl, 'backtest_end', openPos.closedAt);
    currentEquity += pnl;
    equityCurve.push(currentEquity);
  }

  // Build output
  const closedPositions = positions.filter((p) => p.status === 'closed');
  const realizedPnl = closedPositions.reduce((acc, p) => acc + p.realizedPnl, 0);
  const wins = closedPositions.filter((p) => p.realizedPnl > 0).length;
  const losses = closedPositions.filter((p) => p.realizedPnl <= 0).length;
  const winRatePct = closedPositions.length > 0 ? (wins / closedPositions.length) * 100 : 0;
  const roiPct = depositUsd > 0 ? (realizedPnl / depositUsd) * 100 : 0;

  const summary: BacktestRunSummary = {
    totalTrades: closedPositions.length,
    winRatePct: round(winRatePct),
    realizedPnlUsd: round(realizedPnl),
    openPnlUsd: 0,
    netPnlUsd: round(realizedPnl),
    roiPct: round(roiPct),
    maxDrawdownPct: computeMaxDrawdownPct(equityCurve),
  };

  const symbolStats: BacktestRunSymbolStats = {
    symbol,
    totalTrades: closedPositions.length,
    wins,
    losses,
    realizedPnlUsd: round(realizedPnl),
    netPnlUsd: round(realizedPnl),
    slCount,
    tp1Count,
    tp2Count,
    tp3Count,
    emergencyExitCount,
    rejectedSignals,
  };

  return {
    summary,
    bySymbol: [symbolStats],
    trades,
    equityCurve,
  };
}
