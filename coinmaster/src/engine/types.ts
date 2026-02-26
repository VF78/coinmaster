export enum RuleTier {
  EMERGENCY = 400,
  RISK = 300,
  EXIT = 200,
  ENTRY = 100,
  INFO = 0,
}

export type TriggerSource = 'TICK' | 'REQUEST' | 'MANUAL';

export enum ActionType {
  PLACE_ORDER = 'PLACE_ORDER',
  CANCEL_ORDER = 'CANCEL_ORDER',
  EMERGENCY_CLOSE = 'EMERGENCY_CLOSE',
  SET_TRIGGER_ORDER = 'SET_TRIGGER_ORDER',
  BLOCK_REQUEST = 'BLOCK_REQUEST',
  LOG_ONLY = 'LOG_ONLY',
}

export interface RuleEngineSnapshot {
  timestamp: number;
  source: TriggerSource;
  request?: {
    symbol?: string;
    side?: string;
    size?: number;
    reduceOnly?: boolean;
    confirm?: boolean;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ConditionResult {
  met: boolean;
  detail: Record<string, unknown>;
}

export interface Condition<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  id: string;
  evaluate(snapshot: S): ConditionResult;
}

export interface RetryPolicy {
  maxAttempts: number;
  backoffMs: number;
}

export interface ActionSpec {
  type: ActionType;
  idempotencyKeyTemplate: string;
  params: Record<string, unknown>;
  retryPolicy?: Partial<RetryPolicy>;
}

export interface Rule<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  id: string;
  tier: RuleTier;
  conditions: Array<Condition<S>>;
  action: ActionSpec;
  cooldownMs?: number;
  allowedSources: TriggerSource[];
  enabled: boolean;
}

export type DecisionAction = 'FIRE' | 'SUPPRESSED';

export type SuppressionReason =
  | 'conditions_not_met'
  | 'source_not_allowed'
  | 'preempted_by_higher_tier'
  | 'cooldown';

export type ActionOutcomeStatus = 'OK' | 'FAILED' | 'DEDUPED' | 'RETRIED_OK' | 'SKIPPED';
