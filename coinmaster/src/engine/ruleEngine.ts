import { randomUUID } from 'node:crypto';
import { ActionLog } from './actionLog.js';
import { actOnDecisions, type ActOptions, type ActionExecutionContext, type ActionExecutor, type ActionOutcome } from './act.js';
import {
  auditCycle,
  defaultAuditSink,
  snapshotDigestFromSnapshot,
  type AuditEntry,
  type AuditSink,
  type InMemoryAuditStore,
} from './audit.js';
import { decideRules, type DecideOptions, type RuleDecision } from './decide.js';
import { evaluateRules, type EvaluatedRule } from './evaluate.js';
import type { ActionType, Rule, RuleEngineSnapshot } from './types.js';

export interface RuleEngineOptions<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  actionLog?: ActionLog;
  executors?: Partial<Record<ActionType, ActionExecutor<S>>>;
  auditSinks?: AuditSink<S>[];
  auditStore?: InMemoryAuditStore<S>;
  nowMs?: () => number;
}

export interface RuleEngineRunResult<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  cycleId: string;
  evaluations: EvaluatedRule<S>[];
  decisions: RuleDecision<S>[];
  outcomes: ActionOutcome<S>[];
  audit: AuditEntry<S>;
}

export class RuleEngine<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  private readonly cooldownState = new Map<string, number>();
  private readonly actionLog: ActionLog;
  private readonly executors: Partial<Record<ActionType, ActionExecutor<S>>>;
  private readonly auditSinks: AuditSink<S>[];
  private readonly nowMs: () => number;
  private rules: Rule<S>[];

  constructor(rules: ReadonlyArray<Rule<S>>, options?: RuleEngineOptions<S>) {
    this.rules = [...rules];
    this.actionLog = options?.actionLog ?? new ActionLog();
    this.executors = options?.executors ?? {};
    this.nowMs = options?.nowMs ?? Date.now;

    const sinks = options?.auditSinks ?? [];
    this.auditSinks = sinks.length > 0 ? sinks : [defaultAuditSink];

    if (options?.auditStore) {
      this.auditSinks.push((entry) => {
        options.auditStore?.append(entry);
      });
    }
  }

  setRules(rules: ReadonlyArray<Rule<S>>): void {
    this.rules = [...rules];
  }

  registerExecutor(type: ActionType, executor: ActionExecutor<S>): void {
    this.executors[type] = executor;
  }

  async run(snapshot: S, options?: { cycleId?: string; decide?: Omit<DecideOptions, 'lastFiredAt' | 'nowMs'> }): Promise<RuleEngineRunResult<S>> {
    const cycleId = options?.cycleId ?? randomUUID();
    const nowMs = this.nowMs();

    const evaluations = evaluateRules(this.rules, snapshot);
    const decisions = decideRules(evaluations, {
      ...options?.decide,
      nowMs,
      lastFiredAt: this.cooldownState,
    });

    const outcomes = await actOnDecisions(decisions, {
      cycleId,
      snapshot,
      executors: this.executors,
      actionLog: this.actionLog,
      nowMs,
    } as ActOptions<S>);

    const audit: AuditEntry<S> = {
      cycleId,
      createdAt: new Date(nowMs).toISOString(),
      source: snapshot.source,
      snapshotDigest: snapshotDigestFromSnapshot(snapshot),
      evaluations,
      decisions,
      outcomes,
    };

    await auditCycle(audit, this.auditSinks);

    return {
      cycleId,
      evaluations,
      decisions,
      outcomes,
      audit,
    };
  }

  getCooldownState(): Map<string, number> {
    return new Map(this.cooldownState);
  }

  getActionLog(): ActionLog {
    return this.actionLog;
  }

  evaluateOnly(snapshot: S): EvaluatedRule<S>[] {
    return evaluateRules(this.rules, snapshot);
  }

  decideOnly(evaluated: ReadonlyArray<EvaluatedRule<S>>, options?: Omit<DecideOptions, 'lastFiredAt' | 'nowMs'>): RuleDecision<S>[] {
    return decideRules(evaluated, {
      ...options,
      nowMs: this.nowMs(),
      lastFiredAt: this.cooldownState,
    });
  }
}

export type { ActionExecutionContext };
