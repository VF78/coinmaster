/**
 * engine/snapshot.ts
 *
 * Pure builder for EngineSnapshot — no side effects, no I/O.
 */

import type { EngineSnapshot } from './types.js';

export interface SnapshotInput {
  symbol: string;
  equityUsd: number;
  availableUsd: number;
  dailyDDPct: number;
  openPositionCount: number;
  currentPrice: number;
  side?: 'long' | 'short';
  /** ISO timestamp; defaults to Date.now() if omitted. */
  timestamp?: string;
}

export function buildSnapshot(input: SnapshotInput): EngineSnapshot {
  return {
    symbol: input.symbol,
    timestamp: input.timestamp ?? new Date().toISOString(),
    equityUsd: input.equityUsd,
    availableUsd: input.availableUsd,
    dailyDDPct: input.dailyDDPct,
    openPositionCount: input.openPositionCount,
    currentPrice: input.currentPrice,
    side: input.side,
  };
}
