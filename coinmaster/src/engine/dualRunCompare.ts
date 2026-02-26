/**
 * engine/dualRunCompare.ts
 *
 * Helpers for dual-run (shadow) comparison between legacy gate results
 * and new engine decisions.
 *
 * AUDIT/LOG ONLY — no effect on live server behavior.
 * No imports from server/index.ts.
 */

import type { EngineDecision } from './types.js';
import { applyPreemption } from './rules/risk/index.js';

// ─── Types ─────────────────────────────────────────────────────────────

/** Result shape from the current live server gate (legacy path). */
export interface LegacyGateResult {
  blocked: boolean;
  reason?: string;
  context?: Record<string, unknown>;
}

/** Summarized engine output after preemption is applied. */
export interface EngineDecisionSummary {
  blocked: boolean;
  reason?: string;
  context?: Record<string, unknown>;
}

export interface DualRunMismatch {
  field: string;
  legacy: unknown;
  engine: unknown;
}

export interface DualRunCompareResult {
  matches: boolean;
  mismatches: DualRunMismatch[];
  legacyBlocked: boolean;
  engineBlocked: boolean;
  timestamp: string;
}

// ─── Summarize ─────────────────────────────────────────────────────────

/**
 * Apply preemption to a decision list, then reduce to a single summary.
 * The first blocking decision wins (RISK > EXIT > ENTRY after preemption).
 */
export function summarizeDecisions(decisions: EngineDecision[]): EngineDecisionSummary {
  const effective = applyPreemption(decisions);
  // Primary blocking reason follows preemption priority: RISK > EXIT > any other
  const blocking =
    effective.find((d) => d.kind === 'RISK' && d.action === 'block') ??
    effective.find((d) => d.kind === 'EXIT' && d.action === 'block') ??
    effective.find((d) => d.action === 'block');
  return {
    blocked: blocking !== undefined,
    reason: blocking?.reason,
    context: blocking?.context,
  };
}

// ─── Compare ───────────────────────────────────────────────────────────

/**
 * Compare legacy gate result against engine summary.
 * Returns full mismatch list for audit logging.
 * This function has no side effects and never throws.
 */
export function compareResults(
  legacy: LegacyGateResult,
  engine: EngineDecisionSummary,
): DualRunCompareResult {
  const mismatches: DualRunMismatch[] = [];

  if (legacy.blocked !== engine.blocked) {
    mismatches.push({
      field: 'blocked',
      legacy: legacy.blocked,
      engine: engine.blocked,
    });
  }

  const legacyReason = legacy.reason ?? null;
  const engineReason = engine.reason ?? null;
  if (legacyReason !== engineReason) {
    mismatches.push({
      field: 'reason',
      legacy: legacyReason,
      engine: engineReason,
    });
  }

  return {
    matches: mismatches.length === 0,
    mismatches,
    legacyBlocked: legacy.blocked,
    engineBlocked: engine.blocked,
    timestamp: new Date().toISOString(),
  };
}

// ─── Format ────────────────────────────────────────────────────────────

/** Format a compare result as a single audit log line. */
export function formatCompareResult(result: DualRunCompareResult): string {
  if (result.matches) {
    return `[dual-run] MATCH legacy=${result.legacyBlocked} engine=${result.engineBlocked}`;
  }
  const fields = result.mismatches
    .map((m) => `${m.field}:legacy=${String(m.legacy)}→engine=${String(m.engine)}`)
    .join(' ');
  return `[dual-run] MISMATCH ${fields}`;
}
