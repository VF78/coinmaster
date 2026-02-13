import { Bias } from './types.js';

export interface StrategyContext {
  symbol: string;
  price: number;
  lastPrice?: number;
  bias: Bias;
}

export interface StrategySignal {
  shouldOpen: boolean;
  side?: 'long' | 'short';
  confidence: number;
  reason: string;
}

/**
 * backtest_v1 adapter seam:
 * - Current MVP emulates a simplified hook for momentum + active bias.
 * - Future step: call backtest_v1/signals.py via py bridge and map outputs.
 */
export class BacktestV1SignalAdapter {
  evaluate(ctx: StrategyContext): StrategySignal {
    if (ctx.bias === 'off') {
      return { shouldOpen: false, confidence: 0, reason: 'bias_off' };
    }

    if (!ctx.lastPrice) {
      return { shouldOpen: false, confidence: 0.2, reason: 'insufficient_history' };
    }

    const move = (ctx.price - ctx.lastPrice) / ctx.lastPrice;
    if (ctx.bias === 'long' && move > 0.0015) {
      return { shouldOpen: true, side: 'long', confidence: Math.min(1, move * 1000), reason: 'momentum_up_hook' };
    }
    if (ctx.bias === 'short' && move < -0.0015) {
      return { shouldOpen: true, side: 'short', confidence: Math.min(1, Math.abs(move) * 1000), reason: 'momentum_down_hook' };
    }

    return { shouldOpen: false, confidence: 0.35, reason: 'no_trigger' };
  }
}
