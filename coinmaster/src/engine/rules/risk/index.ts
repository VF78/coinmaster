/**
 * engine/rules/risk/index.ts
 *
 * RISK rule definitions + preemption logic.
 * Pure functions — no server, DB, or exchange imports.
 *
 * Preemption order:
 *   RISK (block) > EXIT (block) > ENTRY
 *
 * Any blocking RISK or EXIT decision suppresses ENTRY 'allow' decisions.
 * RISK preemption takes priority when both RISK and EXIT are blocking.
 */

import type { DecisionAction, EngineDecision, EngineSnapshot } from '../../types.js';

// ─── Risk rule result ──────────────────────────────────────────────────

export interface RiskRuleResult {
  rule: string;
  action: DecisionAction;
  reason: string;
  context?: Record<string, unknown>;
}

// ─── Individual rules ──────────────────────────────────────────────────

/** Block if daily drawdown has reached or exceeded the configured limit. */
export function evalDailyDrawdownRule(
  snapshot: EngineSnapshot,
  ddLimitPct: number,
): RiskRuleResult {
  if (snapshot.dailyDDPct >= ddLimitPct) {
    return {
      rule: 'daily_drawdown',
      action: 'block',
      reason: 'daily_dd_exceeded',
      context: { actual: snapshot.dailyDDPct, limit: ddLimitPct },
    };
  }
  return { rule: 'daily_drawdown', action: 'allow', reason: 'dd_within_limit' };
}

/** Block if equity is zero or non-finite. */
export function evalEquityRule(snapshot: EngineSnapshot): RiskRuleResult {
  if (!Number.isFinite(snapshot.equityUsd) || snapshot.equityUsd <= 0) {
    return {
      rule: 'equity_guard',
      action: 'block',
      reason: 'zero_or_invalid_equity',
    };
  }
  return { rule: 'equity_guard', action: 'allow', reason: 'equity_ok' };
}

/** Wrap a RiskRuleResult into an EngineDecision of kind='RISK'. */
export function riskResultToDecision(
  result: RiskRuleResult,
  symbol: string,
): EngineDecision {
  return {
    kind: 'RISK',
    action: result.action,
    symbol,
    reason: result.reason,
    context: result.context,
  };
}

// ─── Preemption ────────────────────────────────────────────────────────

/**
 * Apply preemption to a mixed decision set.
 *
 * Rules:
 * - If any RISK decision is 'block', all ENTRY 'allow' decisions are
 *   converted to 'block' with reason='preempted_by_risk'.
 * - If any EXIT decision is 'block' (and no RISK block), all ENTRY
 *   'allow' decisions are converted to 'block' with reason='preempted_by_exit'.
 * - Non-ENTRY decisions are always returned unchanged.
 */
export function applyPreemption(decisions: EngineDecision[]): EngineDecision[] {
  const hasBlockingRisk = decisions.some((d) => d.kind === 'RISK' && d.action === 'block');
  const hasBlockingExit = decisions.some((d) => d.kind === 'EXIT' && d.action === 'block');

  if (!hasBlockingRisk && !hasBlockingExit) return decisions;

  const suppressionReason = hasBlockingRisk ? 'preempted_by_risk' : 'preempted_by_exit';

  return decisions.map((d): EngineDecision => {
    if (d.kind === 'ENTRY' && d.action === 'allow') {
      return { ...d, action: 'block', reason: suppressionReason };
    }
    return d;
  });
}

/**
 * Count how many ENTRY decisions were suppressed (allow → block) by preemption.
 * Both arrays must be index-aligned (same length, same original order).
 */
export function countSuppressedEntries(
  original: EngineDecision[],
  afterPreemption: EngineDecision[],
): number {
  let count = 0;
  for (let i = 0; i < original.length; i++) {
    const orig = original[i];
    const after = afterPreemption[i];
    if (orig.kind === 'ENTRY' && orig.action === 'allow' && after.action === 'block') {
      count++;
    }
  }
  return count;
}
