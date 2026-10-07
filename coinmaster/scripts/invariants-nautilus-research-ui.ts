import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../src/web/pages/NautilusControlPage.tsx', import.meta.url), 'utf8');
const app = readFileSync(new URL('../src/web/App.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/web/lib/nautilusApi.ts', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/web/styles.css', import.meta.url), 'utf8');
const catalog = readFileSync(new URL('../../runtime/coinmaster/research/catalog.py', import.meta.url), 'utf8');

const required = [
  ['navigation includes Dashboard', "label: 'Dashboard'"],
  ['navigation includes Strategy', "label: 'Strategy'"],
  ['navigation includes Backtest', "label: 'Backtest'"],
  ['navigation includes Settings', "label: 'Settings'"],
  ['top bar keeps one clear Sandbox and live-order state', 'Dry-run · Sandbox'],
  ['top bar removes the public-feed badge', 'PUBLIC MARKET DATA'],
  ['top bar removes the redundant Sandbox badge', 'LOCAL SANDBOX'],
  ['top bar removes operator clutter', 'nautilus-operator'],
  ['Dashboard surfaces current margin and PnL only after account verification', 'accountIsUnknown ? null : <details'],
  ['dashboard keeps warnings visible in human-readable form', 'className="runtime-warning-list"'],
  ['Backtest presents run status in trader-facing language', 'humanizeResearchCode(run.status)'],
  ['catalog is loaded from the local API', 'getResearchCatalog'],
  ['strategy reads sealed Stage-G identity from the local API', 'getHlStagegStrategy'],
  ['strategy identifies the running sealed instance', 'Running strategy'],
  ['strategy uses a trader-readable runner match badge', 'strategyRunnerLabel(strategy?.running_state'],
  ['strategy confirms running only on the API hash-match state', "strategy?.running_state === 'RUNNING_MATCH'"],
  ['strategy labels an unconfirmed runner honestly', 'worker match is not confirmed'],
  ['strategy keeps research drafts separate from the runner', 'Research drafts'],
  ['strategy does not expose an apply path to the running worker', 'Apply strategy'],
  ['strategy read-backs a saved research draft', 'Saved draft could not be read back.'],
  ['strategy separates BTC sizing from SOL exits', 'BTC sizing and exits'],
  ['strategy shows SOL sizing and exits', 'SOL sizing and exits'],
  ['strategy does not render obsolete corrected-v0 framing', 'corrected-v0'],
  ['research retains the original reporting-v2 baseline', 'Original v0'],
  ['research keeps the catalog read only', 'Historical research archive'],
  ['research preserves diagnostic classification', 'item.classification'],
  ['research renders every catalog evidence row', 'catalog.filter((item)'],
  ['catalog includes the Hyperliquid blocked evidence', 'Hyperliquid public REST evidence — blocked'],
  ['unused legacy research component was removed', 'LegacyResearchPage'],
  ['API exposes the immutable catalog request', "request<ResearchCatalogEntry[]>('/research/catalog')"],
  ['account-specific facts use honest unavailable labels', 'Unavailable'],
  ['research exposes the historical baseline action', 'Run backtest'],
  ['research shows the verified native baseline period', 'Start date'],
  ['research launches the owned native baseline job', "createRun(saved.id, 'research', 'native_baseline', undefined, period"],
  ['research shows run progress and history', 'title="Run history"'],
  ['research describes the selected run in concise trader language', 'Showing the selected run.'],
  ['research ranks the workspace by terminal total', 'Terminal total'],
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
  ['dashboard withholds stale drawdown protection values', '{protectionFresh ? <><p className="trader-note">Maximum drawdown limit'],
  ['dashboard removes worker hashes and event-cursor evidence from the normal UI', 'Diagnostics and source identity'],
  ['strategy groups exact running settings for traders', 'Signal and safety settings'],
  ['strategy drafts use separate accessible numeric inputs', 'type="number" step="any" value={field}'],
  ['invalid strategy draft fields are announced accessibly', 'aria-invalid={invalid || undefined}'],
  ['production buttons and controls have keyboard focus styles', '.nautilus-app-shell .btn:focus-visible'],
  ['trader UI includes a narrow mobile layout', '@media (max-width: 390px)'],
  ['mobile bottom nav spans the nav grid for four readable tabs', '.sidebar-nav__list { grid-column:1 / -1; width:100%; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.15rem; }'],
  ['mobile bottom nav constrains and separates 390px labels', '.nautilus-app-shell .sidebar-nav__item > span:not(.nautilus-nav-icon)'],
  ['strategy folds technical parameters under advanced rules', 'Advanced strategy rules'],
  ['research presents readable blockers without raw technical-code panels', 'Technical blocker codes'],
  ['dashboard presents recent native executions as Recent executions', 'Recent executions'],
  ['recent trades use only the verified optional action label', 'nativeFillActionLabel(fill.action)'],
  ['recent trades keep actual fee data', "header: 'Fee'"],
  ['missing legacy count remains unavailable instead of zero', 'unavailableTradeHistoryLabel(fillHistory?.historical_id_only_count)'],
  ['legacy count does not use a fabricated zero fallback', 'historical_id_only_count ?? 0'],
  ['recent trades hide technical order and episode IDs', 'Order / episode'],
  ['recent trades hide technical liquidity codes', "header: 'Liquidity'"],
  ['recent trade history does not use ID-only technical phrasing', 'IDs only'],
  ['recent trades do not add a PnL column', "key: 'pnl'"],
  ['dashboard binds fill rows to current worker epoch', 'fillHistory?.run_epoch === state.run_epoch'],
  ['worker epoch changes discard paged rows from the old run', 'current.run_epoch !== data.run_epoch'],
  ['strategy removes source-hash and account-code clutter', 'Strategy identity and account limits'],
  ['settings leaves unproven Stage-G controls disabled', 'Flatten virtual exposure'],
] as const;

let failed = 0;
for (const [label, text] of required) {
  const source = label.startsWith('production') || label.startsWith('trader UI includes') || label.startsWith('mobile bottom nav') ? styles : label.startsWith('navigation') || label.startsWith('top bar') ? app : label.startsWith('catalog') && text.startsWith('getResearchCatalog') ? page : text.startsWith('request<') ? api : text.startsWith('Original v0') || text.startsWith('Hyperliquid') ? catalog : page;
  const absent = label.includes('does not') || label.includes('do not') || label.includes('does not invent') || label.includes('does not expose') || label.includes('removes') || label.includes('without raw') || label.includes('no raw') || label.includes('hide technical') || label.includes('was removed') || label.startsWith('top bar removes');
  if (source.includes(text) !== absent) console.log(`  ✓ ${label}`);
  else { failed += 1; console.error(`  ✗ ${label}`); }
}

if (failed) process.exit(1);
console.log(`Nautilus research UI invariant passed (${required.length} checks)`);
