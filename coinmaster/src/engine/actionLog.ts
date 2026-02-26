export interface ActionLogEntry {
  timestamp: number;
  status: string;
}

/**
 * In-memory deduplication store for action idempotency.
 */
export class ActionLog {
  private readonly entries = new Map<string, ActionLogEntry>();

  constructor(private readonly ttlMs: number = 60_000) {}

  has(key: string, nowMs: number = Date.now()): boolean {
    const found = this.entries.get(key);
    if (!found) return false;

    if (nowMs - found.timestamp > this.ttlMs) {
      this.entries.delete(key);
      return false;
    }

    return true;
  }

  get(key: string, nowMs: number = Date.now()): ActionLogEntry | undefined {
    if (!this.has(key, nowMs)) return undefined;
    return this.entries.get(key);
  }

  set(key: string, entry: ActionLogEntry): void {
    this.entries.set(key, entry);
  }

  gc(nowMs: number = Date.now()): void {
    for (const [key, entry] of this.entries) {
      if (nowMs - entry.timestamp > this.ttlMs) {
        this.entries.delete(key);
      }
    }
  }

  size(): number {
    return this.entries.size;
  }
}
