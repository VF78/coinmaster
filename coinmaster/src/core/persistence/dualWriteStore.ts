import type { DBShape } from '../types.js';
import type { PersistenceStore } from './types.js';

/**
 * Dual-write persistence store — Phase 2 shadow mode.
 *
 * Reads always come from the primary store (lowdb).
 * On flush(), writes go to primary first, then best-effort to the shadow
 * store (postgres). Shadow failures are logged but never break the primary
 * write path.
 *
 * Activate via:
 *   PERSISTENCE_BACKEND=lowdb PERSISTENCE_DUAL_WRITE=true
 */
export class DualWriteStore implements PersistenceStore {
  constructor(
    private readonly primary: PersistenceStore,
    private readonly shadow: PersistenceStore
  ) {}

  async init(): Promise<void> {
    await this.primary.init();
    try {
      await this.shadow.init();
      console.log('[dual-write] Shadow store initialised');
    } catch (err: any) {
      console.error('[dual-write] Shadow init failed (non-fatal):', err.message ?? err);
    }
  }

  getData(): DBShape {
    return this.primary.getData();
  }

  async flush(): Promise<void> {
    // Primary write — must succeed
    await this.primary.flush();

    // Sync snapshot into shadow before flushing
    try {
      const snapshot = this.primary.getData();
      const shadowData = this.shadow.getData();
      Object.assign(shadowData, JSON.parse(JSON.stringify(snapshot)));
      await this.shadow.flush();
    } catch (err: any) {
      console.error('[dual-write] Shadow flush failed (non-fatal):', err.message ?? err);
    }
  }

  async healthCheck(): Promise<{ ok: boolean; backend: string; error?: string }> {
    const primary = await this.primary.healthCheck();
    let shadow: { ok: boolean; backend: string; error?: string };
    try {
      shadow = await this.shadow.healthCheck();
    } catch (err: any) {
      shadow = { ok: false, backend: 'postgres', error: err.message ?? 'unknown' };
    }
    return {
      ok: primary.ok,
      backend: `dual-write(primary=${primary.backend},shadow=${shadow.backend})`,
      error: !shadow.ok ? `shadow: ${shadow.error ?? 'unhealthy'}` : undefined
    };
  }

  async close(): Promise<void> {
    await this.primary.close();
    try {
      await this.shadow.close();
    } catch {
      // best effort
    }
  }
}
