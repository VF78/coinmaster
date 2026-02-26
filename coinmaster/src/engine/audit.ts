import logger from '../lib/logger.js';
import type { ActionOutcome } from './act.js';
import type { RuleDecision } from './decide.js';
import type { EvaluatedRule } from './evaluate.js';
import type { RuleEngineSnapshot, TriggerSource } from './types.js';

export interface SnapshotDigest {
  timestamp: number;
  source: TriggerSource;
  positionCount?: number;
  openOrderCount?: number;
  equity?: number;
  dailyPnlPct?: number;
  portfolioLeverage?: number;
}

export interface AuditEntry<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  cycleId: string;
  createdAt: string;
  source: TriggerSource;
  snapshotDigest: SnapshotDigest;
  evaluations: EvaluatedRule<S>[];
  decisions: RuleDecision<S>[];
  outcomes: ActionOutcome<S>[];
}

export type AuditSink<S extends RuleEngineSnapshot = RuleEngineSnapshot> = (entry: AuditEntry<S>) => Promise<void> | void;

export class InMemoryAuditStore<S extends RuleEngineSnapshot = RuleEngineSnapshot> {
  private readonly entries: AuditEntry<S>[] = [];

  append(entry: AuditEntry<S>): void {
    this.entries.push(entry);
  }

  list(): AuditEntry<S>[] {
    return [...this.entries];
  }
}

export function defaultAuditSink<S extends RuleEngineSnapshot>(entry: AuditEntry<S>): void {
  const fired = entry.decisions.filter((d) => d.action === 'FIRE').map((d) => d.ruleId);
  const suppressed = entry.decisions.filter((d) => d.action === 'SUPPRESSED').map((d) => d.ruleId);

  logger.info(
    {
      component: 'rule-engine',
      cycleId: entry.cycleId,
      source: entry.source,
      fired,
      suppressed,
      outcomeCount: entry.outcomes.length,
    },
    'rule engine cycle audited',
  );
}

export async function auditCycle<S extends RuleEngineSnapshot>(
  entry: AuditEntry<S>,
  sinks: ReadonlyArray<AuditSink<S>>,
): Promise<void> {
  for (const sink of sinks) {
    await sink(entry);
  }
}

export function snapshotDigestFromSnapshot<S extends RuleEngineSnapshot>(snapshot: S): SnapshotDigest {
  const digest: SnapshotDigest = {
    timestamp: snapshot.timestamp,
    source: snapshot.source,
  };

  const positions = snapshot.positions;
  if (Array.isArray(positions)) digest.positionCount = positions.length;

  const openOrders = snapshot.openOrders;
  if (Array.isArray(openOrders)) digest.openOrderCount = openOrders.length;

  if (typeof snapshot.equity === 'number') digest.equity = snapshot.equity;
  if (typeof snapshot.dailyPnlPct === 'number') digest.dailyPnlPct = snapshot.dailyPnlPct;
  if (typeof snapshot.portfolioLeverage === 'number') digest.portfolioLeverage = snapshot.portfolioLeverage;

  return digest;
}
