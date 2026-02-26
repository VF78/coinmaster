/**
 * engine/types.ts
 *
 * Core types for the Phase-1 rule engine.
 * Pure — no server, DB, or exchange imports.
 */

export type DecisionKind = 'ENTRY' | 'EXIT' | 'RISK';
export type DecisionAction = 'allow' | 'block';

export interface EngineDecision {
  kind: DecisionKind;
  action: DecisionAction;
  symbol: string;
  reason: string;
  context?: Record<string, unknown>;
}

/** Point-in-time snapshot of system state passed to rule evaluation. */
export interface EngineSnapshot {
  symbol: string;
  timestamp: string;
  equityUsd: number;
  availableUsd: number;
  /** Current daily drawdown as a percentage (0–100). */
  dailyDDPct: number;
  openPositionCount: number;
  currentPrice: number;
  side?: 'long' | 'short';
}
