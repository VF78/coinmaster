export type ExchangeName = 'hyperliquid' | 'bybit' | 'binance' | string;

export type CandleTimeframe = '1m' | '5m' | '15m' | '1h' | '4h';

export interface Candle {
  timestamp: string; // ISO UTC
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface InstrumentMeta {
  symbol: string;
  tickSize?: number;
  minSize?: number;
  sizeDecimals?: number;
  quoteDecimals?: number;
  raw?: unknown;
}

export interface AccountSnapshot {
  equityUsd?: number;
  availableUsd?: number;
  usedMarginUsd?: number;
  raw?: unknown;
}

export interface OrderSnapshot {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  status?: string;
  raw?: unknown;
}

export interface PositionSnapshot {
  symbol: string;
  side: 'long' | 'short';
  size: number;
  entryPrice?: number;
  markPrice?: number;
  leverage?: number;
  unrealizedPnl?: number;
  raw?: unknown;
}

export interface FillEvent {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  timestamp: string;
  raw?: unknown;
}

export interface OrderIntent {
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  reduceOnly?: boolean;
  clientOrderId?: string;
}

export interface TriggerOrderIntent {
  symbol: string;
  side: 'buy' | 'sell';
  size: number;
  triggerPrice: number;
  kind: 'tp' | 'sl';
  reduceOnly?: boolean;
  clientOrderId?: string;
}

export interface OrderAck {
  ok: boolean;
  orderId?: string;
  clientOrderId?: string;
  status?: string;
  raw?: unknown;
  error?: string;
}

export interface CommandResult {
  ok: boolean;
  raw?: unknown;
  error?: string;
}

/** Standardized error codes for trading operations */
export type TradingErrorCode =
  | 'rate_limited'
  | 'insufficient_balance'
  | 'invalid_params'
  | 'order_not_found'
  | 'already_canceled'
  | 'max_notional_exceeded'
  | 'manual_confirmation_required'
  | 'exchange_error'
  | 'idempotent_duplicate'
  | 'order_failed'
  | 'cancel_failed'
  | 'modify_failed'
  | 'daily_loss_limit_exceeded'
  | 'leverage_limit_exceeded'
  | 'auth_required';

export interface ExchangeCapabilities {
  realtimeMids: boolean;
  historicalCandles: boolean;
  privateAccount: boolean;
  privateTrading: boolean;
  reduceOnly: boolean;
  cancelReplace: boolean;
}

export interface MidStreamHandle {
  close: () => void;
}

export interface MidStreamOptions {
  symbols?: string[];
  onMid: (symbol: string, price: number) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: unknown) => void;
}

export interface CandleQuery {
  symbol: string;
  timeframe: CandleTimeframe;
  startTimeMs: number;
  endTimeMs: number;
}
