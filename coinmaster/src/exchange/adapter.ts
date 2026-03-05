import {
  AccountSnapshot,
  Candle,
  CandleQuery,
  CommandResult,
  ExchangeCapabilities,
  ExchangeName,
  FillEvent,
  InstrumentMeta,
  MidStreamHandle,
  MidStreamOptions,
  OrderAck,
  OrderIntent,
  OrderSnapshot,
  PositionSnapshot,
  TriggerOrderIntent
} from './types.js';

export interface ExchangeAdapter {
  readonly name: ExchangeName;
  readonly capabilities: ExchangeCapabilities;

  // Market
  getMids(): Promise<Record<string, number>>;
  getCandles(query: CandleQuery): Promise<Candle[]>;
  getInstrumentMeta(symbol: string): Promise<InstrumentMeta | null>;
  getTradableSymbols?(): Promise<string[]>;

  // Account
  getAccountState(): Promise<AccountSnapshot | null>;
  getOpenOrders(symbol?: string): Promise<OrderSnapshot[]>;
  getOpenPositions(symbol?: string): Promise<PositionSnapshot[]>;
  getFills(symbol?: string): Promise<FillEvent[]>;

  // Trading
  placeLimitOrder(intent: OrderIntent): Promise<OrderAck>;
  placeTriggerOrder(intent: TriggerOrderIntent): Promise<OrderAck>;
  cancelOrder(orderIdOrClientId: string): Promise<CommandResult>;
  cancelAll(symbol?: string): Promise<CommandResult>;
  placeReduceOnlyExit(intent: OrderIntent): Promise<OrderAck>;
  setLeverage(symbol: string, leverage: number): Promise<CommandResult>;

  // Realtime
  subscribeMids?(options: MidStreamOptions): MidStreamHandle;
}

export class ExchangeAdapterNotImplementedError extends Error {
  constructor(method: string, exchange: string) {
    super(`${exchange}: method ${method} is not implemented yet`);
  }
}
