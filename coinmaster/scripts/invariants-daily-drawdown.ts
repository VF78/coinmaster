/**
 * Deterministic invariants for daily drawdown equity semantics.
 *
 * Covers:
 * 1. Risk path rejects partial/perp-only equity snapshots.
 * 2. Watchdog-style DD math triggers only on risk-valid equity.
 * 3. Partial account snapshots can still be used for display sizing inputs,
 *    but not for risk-critical equity.
 */

type AccountEquityQuality = 'full' | 'partial' | 'unavailable';

type AccountSnapshot = {
  equityUsd?: number;
  availableUsd?: number;
  equityQuality?: AccountEquityQuality;
  equitySource?: string;
  equityValidForRisk?: boolean;
};

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string): void {
  if (condition) {
    passed++;
    console.log(`  ✓ ${label}`);
  } else {
    failed++;
    console.error(`  ✗ FAIL: ${label}`);
  }
}

function isRiskUsableAccountSnapshot(account: AccountSnapshot | null | undefined): boolean {
  return Boolean(account && account.equityValidForRisk && Number.isFinite(account.equityUsd ?? NaN) && (account.equityUsd ?? 0) > 0);
}

function computeDdPct(baselineEquityUsd: number, account: AccountSnapshot | null | undefined): { ok: true; ddPct: number } | { ok: false; reason: string } {
  if (!isRiskUsableAccountSnapshot(account)) {
    return { ok: false, reason: 'risk_check_unavailable' };
  }
  const equityUsd = account?.equityUsd ?? 0;
  const ddPct = baselineEquityUsd > 0 ? ((baselineEquityUsd - equityUsd) / baselineEquityUsd) * 100 : 0;
  return { ok: true, ddPct: Number(ddPct.toFixed(2)) };
}

console.log('\n── Case 1: authoritative spot equity is risk-valid ──');
{
  const account: AccountSnapshot = {
    equityUsd: 303.455834,
    availableUsd: 303.455834,
    equityQuality: 'full',
    equitySource: 'spotClearinghouseState.balances[USDC].total',
    equityValidForRisk: true,
  };
  assert(isRiskUsableAccountSnapshot(account), 'full equity snapshot is accepted for risk');
  const result = computeDdPct(320, account);
  assert(result.ok, 'dd calculation succeeds with full equity');
  if (result.ok) {
    assert(result.ddPct < 15, 'dd remains below emergency threshold');
  }
}

console.log('\n── Case 2: partial perp-only equity is rejected for risk ──');
{
  const account: AccountSnapshot = {
    equityUsd: 143.655834,
    availableUsd: 143.655834,
    equityQuality: 'partial',
    equitySource: 'clearinghouseState.marginSummary.accountValue',
    equityValidForRisk: false,
  };
  assert(!isRiskUsableAccountSnapshot(account), 'partial equity snapshot is rejected for risk');
  const result = computeDdPct(143.655834, account);
  assert(!result.ok, 'dd calculation is blocked for partial equity');
  if (!result.ok) {
    assert(result.reason === 'risk_check_unavailable', 'partial equity reports risk_check_unavailable');
  }
}

console.log('\n── Case 3: unavailable equity is rejected for risk ──');
{
  const account: AccountSnapshot = {
    availableUsd: 50,
    equityQuality: 'unavailable',
    equityValidForRisk: false,
  };
  assert(!isRiskUsableAccountSnapshot(account), 'missing equity snapshot is rejected for risk');
}

console.log(`\nPassed: ${passed}, Failed: ${failed}`);
if (failed > 0) process.exit(1);
