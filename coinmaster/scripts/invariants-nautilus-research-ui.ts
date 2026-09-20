import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../src/web/pages/NautilusControlPage.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/web/lib/nautilusApi.ts', import.meta.url), 'utf8');
const catalog = readFileSync(new URL('../../runtime/coinmaster/research/catalog.py', import.meta.url), 'utf8');

const required = [
  ['catalog is loaded from the local API', 'getResearchCatalog'],
  ['strategy distinguishes immutable versions', 'Immutable research versions'],
  ['research retains the original reporting-v2 baseline', 'Original v0'],
  ['research presents selected 7.5 evidence', 'Selected 7.5 is not the paper default'],
  ['research labels liquidated candidates as exclusions', 'liquidated candidates are retained as exclusions'],
  ['research renders every catalog evidence row', 'catalog.map((item)'],
  ['catalog includes the Hyperliquid blocked evidence', 'Hyperliquid public REST evidence — blocked'],
  ['backtest control states it is an artifact reference', 'Reference selected native research'],
  ['API exposes the immutable catalog request', "request<ResearchCatalogEntry[]>('/research/catalog')"],
] as const;

let failed = 0;
for (const [label, text] of required) {
  const source = text.startsWith('request<') ? api : text.startsWith('Original v0') || text.startsWith('Hyperliquid') ? catalog : page;
  if (source.includes(text)) console.log(`  ✓ ${label}`);
  else { failed += 1; console.error(`  ✗ ${label}`); }
}

if (failed) process.exit(1);
console.log(`Nautilus research UI invariant passed (${required.length} checks)`);
