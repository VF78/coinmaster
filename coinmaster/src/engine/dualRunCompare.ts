import type { RuleDecision } from './decide.js';
import { RuleTier, type RuleEngineSnapshot } from './types.js';

// ── Types ──────────────────────────────────────────────────────────────────

/** Normalized result from the legacy gate system (pre-engine path). */
export interface LegacyGateResult {
  /** Whether the legacy gate allowed the action. */
  allowed: boolean;
  /** Optional reason string from the legacy gate (e.g. rule id or label). */
  reason?: string;
}

/** Compact summary of engine risk decisions, used for cross-path comparison. */
export interface EngineRiskDecisionSummary {
  /** True if any RISK-tier rule fired (i.e. engine would block). */
  blocked: boolean;
  /** Rule ids that fired at RISK tier or above. */
  firedRiskRuleIds: string[];
  /** Rule ids that were suppressed (any tier). */
  suppressedRuleIds: string[];
}

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Reduce a list of engine RuleDecisions into a normalized risk summary.
 * Only RISK-tier (>= 300) FIRE decisions count as "blocked".
 */
export function summarizeEngineRiskDecisions(
  decisions: ReadonlyArray<RuleDecision<RuleEngineSnapshot>>,
): EngineRiskDecisionSummary {
  const firedRiskRuleIds: string[] = [];
  const suppressedRuleIds: string[] = [];

  for (const d of decisions) {
    if (d.action === 'FIRE' && d.tier >= RuleTier.RISK) {
      firedRiskRuleIds.push(d.ruleId);
    } else if (d.action === 'SUPPRESSED') {
      suppressedRuleIds.push(d.ruleId);
    }
  }

  return {
    blocked: firedRiskRuleIds.length > 0,
    firedRiskRuleIds,
    suppressedRuleIds,
  };
}

export interface DualRunMismatch {
  field: string;
  legacy: unknown;
  engine: unknown;
  note: string;
}

/**
 * Compare legacy gate result vs engine risk summary.
 * Returns an array of mismatches; empty array means full agreement.
 *
 * Agreement rules:
 *   legacy.allowed === false  ↔  engine.blocked === true   → agree
 *   legacy.allowed === true   ↔  engine.blocked === false  → agree
 *   any other combination                                   → mismatch
 */
export function compareLegacyVsEngine(
  legacy: LegacyGateResult,
  engine: EngineRiskDecisionSummary,
): DualRunMismatch[] {
  const mismatches: DualRunMismatch[] = [];

  const legacyBlocked = !legacy.allowed;
  if (legacyBlocked !== engine.blocked) {
    mismatches.push({
      field: 'blocked',
      legacy: legacyBlocked,
      engine: engine.blocked,
      note: legacyBlocked
        ? `Legacy blocked (reason: ${legacy.reason ?? 'none'}) but engine fired no risk rules`
        : `Legacy allowed but engine fired risk rules: [${engine.firedRiskRuleIds.join(', ')}]`,
    });
  }

  return mismatches;
}

export interface DualRunMismatchLogPayload {
  hasMismatch: boolean;
  mismatchCount: number;
  mismatches: DualRunMismatch[];
  legacyAllowed: boolean;
  engineBlocked: boolean;
  engineFiredRiskRuleIds: string[];
}

/**
 * Format a compare result into a compact log payload suitable for audit/log sinks.
 */
export function formatDualRunMismatchLog(
  legacy: LegacyGateResult,
  engine: EngineRiskDecisionSummary,
  mismatches: DualRunMismatch[],
): DualRunMismatchLogPayload {
  return {
    hasMismatch: mismatches.length > 0,
    mismatchCount: mismatches.length,
    mismatches,
    legacyAllowed: legacy.allowed,
    engineBlocked: engine.blocked,
    engineFiredRiskRuleIds: engine.firedRiskRuleIds,
  };
}
