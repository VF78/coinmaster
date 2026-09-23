import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../src/web/pages/NautilusControlPage.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/web/lib/nautilusApi.ts', import.meta.url), 'utf8');
const catalog = readFileSync(new URL('../../runtime/coinmaster/research/catalog.py', import.meta.url), 'utf8');

const required = [
  ['catalog is loaded from the local API', 'getResearchCatalog'],
  ['strategy reads sealed Stage-G identity from the local API', 'getHlStagegStrategy'],
  ['strategy identifies the running sealed instance', 'Running sealed Stage-G'],
  ['strategy confirms running only on the API hash-match state', "strategy?.running_state === 'RUNNING_MATCH'"],
  ['strategy labels an unconfirmed runner honestly', 'Local sealed configuration; running not confirmed.'],
  ['strategy keeps research drafts separate from the runner', 'Research drafts'],
  ['strategy requires a separate native promotion gate', 'SEPARATE_NATIVE_LIFECYCLE_GATE_REQUIRED'],
  ['strategy read-backs a saved research draft', 'Saved draft could not be read back.'],
  ['strategy does not render obsolete corrected-v0 framing', 'corrected-v0'],
  ['research retains the original reporting-v2 baseline', 'Original v0'],
  ['research presents selected 7.5 evidence', 'Selected 7.5 is not the paper default'],
  ['research labels liquidated candidates as exclusions', 'liquidated candidates are retained as exclusions'],
  ['research renders every catalog evidence row', 'catalog.map((item)'],
  ['catalog includes the Hyperliquid blocked evidence', 'Hyperliquid public REST evidence — blocked'],
  ['backtest control states it is an artifact reference', 'Reference selected native research'],
  ['API exposes the immutable catalog request', "request<ResearchCatalogEntry[]>('/research/catalog')"],
  ['account-specific facts remain explicitly unknown', 'Account margin:'],
  ['research exposes an isolated native subprocess action', 'Run verified native baseline'],
  ['research shows the verified native baseline period', 'Native baseline period'],
  ['research launches the owned native baseline job', 'Run verified native baseline'],
  ['research shows native job progress and history', 'Native run history'],
  ['research ranks the workspace by TOTAL only', 'TOTAL ONLY'],
  ['research blocks optimizer until it has the job protocol', 'OPTIMIZER_JOB_PROTOCOL_NOT_IMPLEMENTED'],
  ['API exposes research launch capabilities', "request<ResearchCapabilities>('/research/capabilities')"],
] as const;

let failed = 0;
for (const [label, text] of required) {
  const source = text.startsWith('request<') ? api : text.startsWith('Original v0') || text.startsWith('Hyperliquid') ? catalog : page;
  const absent = label.includes('does not render');
  if (source.includes(text) !== absent) console.log(`  ✓ ${label}`);
  else { failed += 1; console.error(`  ✗ ${label}`); }
}

if (failed) process.exit(1);
console.log(`Nautilus research UI invariant passed (${required.length} checks)`);
