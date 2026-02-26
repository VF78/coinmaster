import { ActionLog } from './actionLog.js';
import type { ActionOutcomeStatus, ActionType, RuleEngineSnapshot } from './types.js';
import type { RuleDecision } from './decide.js';

export interface ActionExecutionContext<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  cycleId: string;
  snapshot: S;
  decision: RuleDecision<S>;
  actionKey: string;
}

export type ActionExecutor<S extends RuleEngineSnapshot = RuleEngineSnapshot> = (
  context: ActionExecutionContext<S>,
) => Promise<unknown>;

export interface ActionOutcome<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  ruleId: string;
  actionType: ActionType;
  actionKey: string;
  status: ActionOutcomeStatus;
  attempts: number;
  result?: unknown;
  error?: string;
  decision: RuleDecision<S>;
}

export interface ActOptions<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  cycleId: string;
  snapshot: S;
  executors: Partial<Record<ActionType, ActionExecutor<S>>>;
  actionLog?: ActionLog;
  nowMs?: number;
  sleep?: (ms: number) => Promise<void>;
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function stringifyError(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

function renderTemplate(template: string, variables: Record<string, string>): string {
  return template.replace(/\$\{([a-zA-Z0-9_]+)\}/g, (_full, key: string) => variables[key] ?? '');
}

function actionKeyForDecision<S extends RuleEngineSnapshot>(decision: RuleDecision<S>, snapshot: S): string {
  const params = decision.evaluated.rule.action.params;
  const request = snapshot.request;

  const vars: Record<string, string> = {
    ruleId: decision.ruleId,
    source: decision.source,
    timestamp: String(snapshot.timestamp),
    actionType: decision.evaluated.rule.action.type,
    symbol: request?.symbol ? String(request.symbol) : '',
    side: request?.side ? String(request.side) : '',
  };

  for (const [key, value] of Object.entries(params)) {
    vars[key] = String(value);
  }

  const template = decision.evaluated.rule.action.idempotencyKeyTemplate.trim();
  if (template.length === 0) {
    return `${decision.ruleId}:${decision.evaluated.rule.action.type}:${snapshot.timestamp}`;
  }

  return renderTemplate(template, vars);
}

/**
 * Execute decided actions with retry + idempotency.
 */
export async function actOnDecisions<S extends RuleEngineSnapshot>(
  decisions: ReadonlyArray<RuleDecision<S>>,
  options: ActOptions<S>,
): Promise<ActionOutcome<S>[]> {
  const actionLog = options.actionLog ?? new ActionLog();
  const sleep = options.sleep ?? defaultSleep;
  const nowMs = options.nowMs ?? Date.now();
  actionLog.gc(nowMs);

  const outcomes: ActionOutcome<S>[] = [];

  for (const decision of decisions) {
    if (decision.action !== 'FIRE') continue;

    const action = decision.evaluated.rule.action;
    const actionKey = actionKeyForDecision(decision, options.snapshot);

    if (actionLog.has(actionKey, nowMs)) {
      outcomes.push({
        ruleId: decision.ruleId,
        actionType: action.type,
        actionKey,
        status: 'DEDUPED',
        attempts: 0,
        decision,
      });
      continue;
    }

    const executor = options.executors[action.type];
    if (!executor) {
      outcomes.push({
        ruleId: decision.ruleId,
        actionType: action.type,
        actionKey,
        status: 'SKIPPED',
        attempts: 0,
        error: `no executor registered for ${action.type}`,
        decision,
      });
      continue;
    }

    const maxAttempts = Math.max(1, action.retryPolicy?.maxAttempts ?? 1);
    const backoffMs = Math.max(0, action.retryPolicy?.backoffMs ?? 0);

    let attempts = 0;
    let lastError: string | undefined;

    while (attempts < maxAttempts) {
      attempts += 1;
      try {
        const result = await executor({
          cycleId: options.cycleId,
          snapshot: options.snapshot,
          decision,
          actionKey,
        });

        actionLog.set(actionKey, { timestamp: Date.now(), status: attempts > 1 ? 'RETRIED_OK' : 'OK' });

        outcomes.push({
          ruleId: decision.ruleId,
          actionType: action.type,
          actionKey,
          status: attempts > 1 ? 'RETRIED_OK' : 'OK',
          attempts,
          result,
          decision,
        });

        lastError = undefined;
        break;
      } catch (error) {
        lastError = stringifyError(error);
        if (attempts < maxAttempts && backoffMs > 0) {
          await sleep(backoffMs);
        }
      }
    }

    if (lastError) {
      actionLog.set(actionKey, { timestamp: Date.now(), status: 'FAILED' });
      outcomes.push({
        ruleId: decision.ruleId,
        actionType: action.type,
        actionKey,
        status: 'FAILED',
        attempts,
        error: lastError,
        decision,
      });
    }
  }

  return outcomes;
}
