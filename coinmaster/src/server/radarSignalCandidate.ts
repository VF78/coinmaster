/**
 * SignalCandidate state machine — pure deterministic transitions.
 *
 *   new → validated → actionable → routed → executed
 *           │             │
 *           ↓             ↓
 *       expired        rejected
 *           │             │
 *           └────► postmortem_ready
 *
 * State transitions are append-only on `transitions[]`. Every transition records:
 *   { from, to, reason, at, [radarSignalId, pendingId, orderId] }
 *
 * This module is pure and side-effect-free; persistence is the caller's responsibility.
 * The companion invariants script (`scripts/invariants-radar-evidence.ts`) verifies
 * every reachable transition against this table.
 */

import type {
  EvidenceBundle,
  SignalCandidate,
  SignalCandidateScore,
  SignalCandidateState,
  SignalCandidateStateTransition,
} from '../shared/dto.js';

const ALLOWED_TRANSITIONS: Record<SignalCandidateState, SignalCandidateState[]> = {
  new: ['validated', 'rejected', 'expired'],
  validated: ['actionable', 'rejected', 'expired'],
  actionable: ['routed', 'rejected', 'expired'],
  routed: ['executed', 'rejected', 'expired'],
  executed: ['postmortem_ready'],
  expired: ['postmortem_ready'],
  rejected: ['postmortem_ready'],
  postmortem_ready: [],
};

export function isAllowedSignalCandidateTransition(from: SignalCandidateState, to: SignalCandidateState): boolean {
  return (ALLOWED_TRANSITIONS[from] ?? []).includes(to);
}

export function listAllowedSignalCandidateTransitions(from: SignalCandidateState): SignalCandidateState[] {
  return [...(ALLOWED_TRANSITIONS[from] ?? [])];
}

export function isTerminalSignalCandidateState(state: SignalCandidateState): boolean {
  return ALLOWED_TRANSITIONS[state]?.length === 0;
}

export interface CreateSignalCandidateInput {
  id: string;
  evidenceBundleId: string;
  symbol: string;
  side: 'buy' | 'sell';
  expiresAt?: string;
  score?: SignalCandidateScore;
  nowIso: string;
}

export function createSignalCandidate(input: CreateSignalCandidateInput): SignalCandidate {
  return {
    id: input.id,
    evidenceBundleId: input.evidenceBundleId,
    symbol: input.symbol,
    side: input.side,
    state: 'new',
    expiresAt: input.expiresAt,
    stateReason: 'created',
    transitions: [{ from: 'new', to: 'new', reason: 'created', at: input.nowIso }],
    score: input.score,
    createdAt: input.nowIso,
    updatedAt: input.nowIso,
  };
}

export interface SignalCandidateTransitionInput {
  to: SignalCandidateState;
  reason: string;
  at: string;
  score?: SignalCandidateScore;
  radarSignalId?: string;
  pendingId?: string;
  orderId?: string;
  outcome?: string;
  postmortemNotes?: string;
}

export interface SignalCandidateTransitionResult {
  ok: boolean;
  candidate: SignalCandidate;
  error?: 'illegal_transition' | 'terminal_state';
}

export function transitionSignalCandidate(
  candidate: SignalCandidate,
  input: SignalCandidateTransitionInput,
): SignalCandidateTransitionResult {
  if (isTerminalSignalCandidateState(candidate.state)) {
    return { ok: false, candidate, error: 'terminal_state' };
  }
  if (!isAllowedSignalCandidateTransition(candidate.state, input.to)) {
    return { ok: false, candidate, error: 'illegal_transition' };
  }
  const transition: SignalCandidateStateTransition = {
    from: candidate.state,
    to: input.to,
    reason: input.reason,
    at: input.at,
    radarSignalId: input.radarSignalId,
    pendingId: input.pendingId,
    orderId: input.orderId,
  };
  const next: SignalCandidate = {
    ...candidate,
    state: input.to,
    stateReason: input.reason,
    transitions: [...candidate.transitions, transition],
    score: input.score ?? candidate.score,
    radarSignalId: input.radarSignalId ?? candidate.radarSignalId,
    pendingId: input.pendingId ?? candidate.pendingId,
    orderId: input.orderId ?? candidate.orderId,
    outcome: input.outcome ?? candidate.outcome,
    postmortemNotes: input.postmortemNotes ?? candidate.postmortemNotes,
    updatedAt: input.at,
  };
  return { ok: true, candidate: next };
}

export function isSignalCandidateExpired(candidate: SignalCandidate, nowMs: number = Date.now()): boolean {
  if (isTerminalSignalCandidateState(candidate.state)) return false;
  if (!candidate.expiresAt) return false;
  const expiresMs = Date.parse(candidate.expiresAt);
  if (!Number.isFinite(expiresMs)) return false;
  return nowMs >= expiresMs;
}

/**
 * Convenience — derive the next state suggestion from an EvidenceBundle/Candidate combo.
 * Used by callers that want a default policy without writing a custom state machine.
 */
export function suggestNextSignalCandidateState(input: {
  candidate: Pick<SignalCandidate, 'state' | 'expiresAt'>;
  bundle: Pick<EvidenceBundle, 'status'>;
  scoreComposite?: number;
  thresholds: { validate: number; actionable: number };
  symbolMonitored: boolean;
  riskBlocked?: boolean;
  nowMs?: number;
}): SignalCandidateState | null {
  const { candidate, bundle } = input;
  if (isTerminalSignalCandidateState(candidate.state)) return null;
  if (bundle.status === 'expired') return 'expired';
  if (input.candidate.expiresAt) {
    const nowMs = input.nowMs ?? Date.now();
    const expiresMs = Date.parse(input.candidate.expiresAt);
    if (Number.isFinite(expiresMs) && nowMs >= expiresMs) return 'expired';
  }
  if (input.riskBlocked) return 'rejected';
  if (!input.symbolMonitored) return 'rejected';
  const score = input.scoreComposite ?? 0;
  if (candidate.state === 'new' && score >= input.thresholds.validate) return 'validated';
  if (candidate.state === 'validated' && score >= input.thresholds.actionable) return 'actionable';
  return null;
}
