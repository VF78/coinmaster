import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../src/web/pages/NautilusControlPage.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/web/lib/nautilusApi.ts', import.meta.url), 'utf8');
const catalog = readFileSync(new URL('../../runtime/coinmaster/research/catalog.py', import.meta.url), 'utf8');

const required = [
  ['catalog is loaded from the local API', 'getResearchCatalog'],
  ['strategy reads sealed Stage-G identity from the local API', 'getHlStagegStrategy'],
  ['strategy identifies the running sealed instance', 'Running strategy'],
  ['strategy confirms running only on the API hash-match state', "strategy?.running_state === 'RUNNING_MATCH'"],
  ['strategy labels an unconfirmed runner honestly', 'worker match is not confirmed'],
  ['strategy keeps research drafts separate from the runner', 'Research drafts'],
  ['strategy leaves promotion disabled without a native gate', '<Button variant="primary" disabled>Apply strategy</Button>'],
  ['strategy read-backs a saved research draft', 'Saved draft could not be read back.'],
  ['strategy separates BTC sizing from SOL exits', 'BTC sizing and exits'],
  ['strategy shows SOL sizing and exits', 'SOL sizing and exits'],
  ['strategy does not render obsolete corrected-v0 framing', 'corrected-v0'],
  ['research retains the original reporting-v2 baseline', 'Original v0'],
  ['research keeps the catalog read only', 'Verified historical evidence'],
  ['research preserves diagnostic classification', 'item.classification'],
  ['research renders every catalog evidence row', 'catalog.map((item)'],
  ['catalog includes the Hyperliquid blocked evidence', 'Hyperliquid public REST evidence — blocked'],
  ['unused legacy research component was removed', 'LegacyResearchPage'],
  ['API exposes the immutable catalog request', "request<ResearchCatalogEntry[]>('/research/catalog')"],
  ['account-specific facts remain explicitly unknown', 'Account margin:'],
  ['research exposes an isolated native subprocess action', 'Run verified native baseline'],
  ['research shows the verified native baseline period', 'Start date'],
  ['research launches the owned native baseline job', 'Run verified native baseline'],
  ['research shows native job progress and history', 'Run history · select to compare'],
  ['research ranks the workspace by TOTAL only', 'TOTAL ONLY'],
  ['research compares native TOP-20 totals and capital split', 'terminal TOTAL comparison'],
  ['research reads back started jobs', 'Native job was accepted but could not be read back.'],
  ['research reads back canceled jobs', 'Cancellation was not confirmed by read-back.'],
  ['research enables optimizer only when capability is READY', "capabilities?.optimizer_state === 'READY'"],
  ['research displays the bounded optimizer budget', 'optimizerSearch?.max_variants'],
  ['research launches the owned native optimizer job', "'native_optimizer', capabilities.optimizer_search"],
  ['API exposes selected-config research capabilities', "request<ResearchCapabilities>(`/research/capabilities"],
  ['entry controls describe availability separately from eligibility', 'New-entry eligibility:'],
  ['HL controls use only instance-bound read API', "request<HlStagegControls>('/instances/hl-stageg-testnet/controls')"],
  ['dashboard presents the verified virtual account before diagnostics', 'Account overview'],
  ['dashboard withholds account figures when unverified or recovering', 'const figures = accountIsUnknown ? [] : accountFigures(state)'],
  ['dashboard presents public BTC/SOL market context', 'Markets'],
  ['dashboard does not invent a zero trade-history claim', 'No virtual trades yet'],
  ['dashboard explains ID-only history remains unavailable', 'Older ID-only events stay unavailable.'],
  ['dashboard withholds stale drawdown protection values', '{protectionFresh ? <div className="runtime-account-grid">'],
  ['dashboard keeps raw identity in collapsed diagnostics', 'Diagnostics and source identity'],
  ['strategy groups exact running settings for traders', 'Signal and safety settings'],
  ['strategy folds technical parameters under advanced rules', 'Advanced strategy rules'],
  ['research maps blockers to human text and preserves codes', 'Technical blocker codes'],
  ['dashboard shows native fill history without pnl reconstruction', 'Native fill history'],
  ['dashboard never computes completed-round-trip PnL', 'no trade PnL or reconstructed round trips are inferred'],
  ['strategy moves source hashes into diagnostics', 'Strategy identity and account limits'],
  ['settings leaves unproven Stage-G controls disabled', 'Flatten virtual exposure'],
] as const;

let failed = 0;
for (const [label, text] of required) {
  const source = text.startsWith('request<') ? api : text.startsWith('Original v0') || text.startsWith('Hyperliquid') ? catalog : page;
  const absent = label.includes('does not render') || label.includes('does not invent') || label.includes('was removed');
  if (source.includes(text) !== absent) console.log(`  ✓ ${label}`);
  else { failed += 1; console.error(`  ✗ ${label}`); }
}

if (failed) process.exit(1);
console.log(`Nautilus research UI invariant passed (${required.length} checks)`);
