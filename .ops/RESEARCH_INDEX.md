# Research memory — as of2026-10-24; read before opening archives

## Fixed controls, not approximate reimplementations
- Legacy S0 source `75ffc9c69e9d79c4da4cd0614634a3eeba48d716`; configSHA `22e1eefe8f9c71669e52a8e44b7acbdfd5f177d6ef4ae2118e9df566a05c6edc`.
- S0: TOTAL6077107.23887483; global settled DD66.25691486468686414439256686%; seed10000, original SOL-overlay. Its90% net-profit floor is5470396.514987347. Never rerun it without a necessary comparability reason and explicit budget.
- Exact E4 source `bd04c9b3858bcda40060a08eff488849c69af5d8`; config `ce7c101ace5d8c21f0a912a0cd3221659591e5d56b744d3f8dc5ecb7c01d2ef6`.
- Legacy E4: TOTAL5631617.35953723/DD57.5854104596/retention92.6573%; adds wait4h and regime reentry0.5WilderATR14.
- Original S0 parameter anchor: BTC long5.5x/short7.875x, parentcap30mUSDT, EMA34; split50/50 with25bp discount, completed first-child PLANREF, selective zeroTP lifecycle and profitable positive-TP nativeIOC fallback. TP fractions21.25/21.25/57.5%; wave quantiles.1/.3/.6; history730/min8. SOL beta270/relative65/z180days; entryz1.25/2.5/3.75, exithalf.375/all.125, maxhold14d; H multipliers1.75/2.625/3.5, persistent rights, no timeout-preempts-add. These explain the version; restore exact config/source, do not rebuild from this prose.

## Latest completed execution-contract study
`reports/system-contract-repair-20261023/` is authoritative; report commit `070f1ecda5619187656bb3390e7811c83488c4f9`, publication `c619ad1c6e438c2c221b8d466a4daea42531434c`.
Engineering source `8f2f78005325776d1f600297a0c2d39e29c48bdd`, data source `4898a273183c51e666623de13ae5476527d72c78`. All research flags default OFF; source is not deployed.

| Same explicit child execution model | TOTAL USDT | Settled DD | Matched net-profit retention |
|---|---:|---:|---:|
| S0 control |6482334.93387961|66.2569%|100%|
| E4 control |6022427.55763206|57.5854%|92.8943%|
| H_SOL ADD-only55%H/ATR14 |3964359.61000698|65.6948%|61.0963%|
| H_BTC completed-wave Q90 repeat sizing |5352125.97225949|57.5854%|82.5378%|

Matched90% floor5835101.440491649, separate from legacy5470396.514987347. All4normalexit0,60native/accountchecks each, complete1051199settled receipts, zero model liquidations/terminalflat.42independent final source tests; both new native causal datasets2407checks each.4/6physical attempts spent; remaining2 CLOSED, no new GO. COMBINED NOT_RUN: all19actual decisions through Jan13 have k1 (repeat completed count<=7), so combined retains H_SOL DD>=65.6948%; first k<1May25,2025. Repeat NOT_RUN, no passing candidate. Economic goal NOT_MET.

Durable legacy S0 native report: `reports/manager-handoff-20261024/evidence/S0-legacy-native-report.json.gz`; original payload/hash retained, no new run.

Read only required evidence:
- `REPORT.md`, `comparison.json/csv`, `selection.json`, `run-ledger.json`, `protocol-final-index.json`.
- `rule-registry.csv/json`:43rules with implementation vs benefit evidence and KEEP/FIX/TEST/DEFER. `contract-audit.md`: exact state/execution findings.
- `data-native-causal-H_SOL.csv`, `data-native-causal-H_BTC.csv`: real q0 equity/held/pending, closedATR/EMA/wave age;83parents/50waves,81complete/2censored. Labels from minuteMARK; ready_at<decision. ±1ATRfirst-touch and D1-close diagnostics never feed Q90. Full internal gate vector is explicitly not exported.
- `episode-attribution.csv`:7fixedE4windows x4recipes; `monthly-attribution.csv`:24months x4. All native artifact locations and hashes are in `data-native-acceptance-*.json`, not in chat.

## Mechanisms already established
- Historical BBO helper displays1000 units.96/98E4SOL_ADD filled1000 and canceled remainder; not a venue liquidity/size limit. Pinned L1 reuses depth independently for each IOC; two can each fill1000.
- Explicit child1000 preserves original rights and genuine D1 batch/attempt frequency, but cap-before-admission admits a formerly locally denied queued add. First money divergence23Dec2024,16:47UTC, extra1000SOL@183.81/fee101.0955. Exact old denied subcomponent/level UNKNOWN. Hence archived controls are not comparable to the new execution model. Native FILLED is not forged CANCELED.
- TP1zero83/83 and TP2zero58/83 in E4; -1bp q1 perturbation changes6parents, +1bp changes10. Zero-TP size branch is execution/strategy-sensitive; positive profitable fallback must not be deleted with instant zeroTPs.
- SOL is selective alpha, not continuous insurance:56.9167%SOL-active time BTCflat;13/25cycles start BTCflat; H references grossBTC, budgets add. Effects on later BTC capital/size/admission are essential.
- H_SOL cuts OctDD57.5854->18.7753 but JanDD42.5023->65.6948: capital210575.71->109846.69, SOL4000->3225.2; smaller absolute loss, much larger relative loss. OneATR ADD budget does not repair held risk or guarantee multi-day DD.
- H_BTC reduces19/33repeat parents, mink.66056; only fromMay25. TOTAL loses670301.59 vs explicitE4; SOLfillnet unchanged. Potential remaining-wave MAE is not proof that cutting this entry improves action PnL.

## Prior experiments — reuse; do not rerun negative families
| Evidence directory | Finding / why it matters |
|---|---|
| `reports/s0-system-audit-20261023/` | Full source/rules/BTC/SOL/portfolio audit;72pins/15comparable paths/11sources/two actual2x2 interactions. Methods and uncertainty already researched. |
| `reports/b-50-90-next-20261023/` |8native variants. B4622034.27/DD57.5854; E4 best retained-profit tradeoff, not DD solution. |
| `reports/e4-sol-residual-20261023/` | R2C2610652.32/DD61.7587. Oct/Jan improved but global risk migrated;337BTC calendars same vsXS,292qty changed. Float-flat fix did not improve economics. |
| `reports/e4-budget-tp3-20261023/` | Budget+trim1360086.37/DD66.859; earlyTP3 4120806.47/DD61.0797. Not ADD-only H_SOL.3physical attempts incl invalid export; closed. |
| `reports/residual-recovery-20261023/` | C1cut/restore4388613.38/DD51.8032/ret72.17%; recovery cost.2physical attempts incl invalid export; closed. |
| `reports/sol-conditional-hedge-btc-band-20261023/` | H4/independent SOL hedge and BTC reentry;10physical attempts, no50/90winner, many liquidated. |
| `reports/btc-split-sol-cover-20261018/` and `reports/winner-6077107-stats/` | Exact6.077m winner/freshrepeat/native BTC split and full statistics. |
| `reports/conditional-sol-2-1-50-113/`, `reports/sol-risk-first-20261018/` | Earlier reactive/split/capped hedges failed insurance/ROI objective. |
| `reports/immediate-sol-insurance-113/`, Project#119 | I25/Light/Recovery/I33: sustained hedge burned alpha/commissions;607rapid re-adds were a problem, not a useful feature. Use issue/report catalog for exact path. |
| `reports/alpha-cushion-113/`, `reports/sol-corridor-113/`, #120 | ALPHA observedDD>=93.23%, total lostOOM; rejected without repeat. Corridor excessive re-add/R2 was stopped; no invented finalTOTAL. |
| `reports/ai-cycle-20261021-01/`, `reports/btc-pattern-pilot-m2-20261021/`, #121/#122 | AI numerical/visual/context/wave/event/LLM pilots did not establish actionable TP/SL lift. Full period preserved; no automatic return to AI training. Models may have been intentionally deleted, reports remain. |

## Exact data / execution reuse
Mac inputs: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data`.
Mac latest results: `.../runtime/var/research-jobs/system-contract-repair-20261023/{E4_EXPLICIT_CONTROL,S0_EXPLICIT_CONTROL,H_SOL,H_BTC}/result`.
Legacy S0 full native folder verified present on VPS (8artifacts): `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-rnd-s0-20261020T170935Z/result`.
Datahash `7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc`; policyhash `c9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834`. Individual files/engine/source/config pins in saved preparations/protocols. Preserve all unique native streams, journals and report receipts.
Use explicit Mac runtime `.venv/bin/python` (3.12.13/nautilus1.231.0), frozen source+scrubbed environment, direct Python Popen, fresh journal/namespace. Do not use macOS `time -l` wrapper as native exit authority.
Known report-only fix `6061446164cc32c27b3ea0e13e86c9cc56d955ac`: local Decimal80/original1e-24guard. Never relax tests or manufacture missing JSON/terminal money. Actual native JSON serialization tested before engines.
Full artifact catalog: `reports/manager-handoff-20261024/research-catalog.json` (paths/hashes, not instructions). No full manifest/log dumps at startup.

## Current market redesign checkpoint — 2026-10-24

Project#131; reports/market-redesign-20261024/REPORT.md. Exact archivedE4 pins verified, four M1windows31/48/65/81 complete. Cycle81 source/lifecycle scheduling hole diagnosed: unfinishedsplit suppresses targets; dayendstop does not requeue. Cheap83row CLEAN_Q sizing and82nativeTP3proxy geometry checks are not candidate economics. Native3TP/livequeue realism remains unproven.

Owner explicitly approved implementation +<=3newfull physicalattempts R1BTCnoSOL→R2U3TP/.5%limit-only LEGACY_Q→R3CLEAN_Q, including failures/repeats. Effective protocol PROTOCOL_PROPOSED.md +approval.json; current spend/active state only run-ledger.json/ACTIVE_TASK. Closed prior budgets remain closed. One isolatedVPSwriter, frozenMacexecution, shortlifecyclechecks and independent money/orderreview before rootfullGO. No additionalBTC/SOLfull/stress/repeat/ML authorization. Economic50/90goal remainsNOT_MET. Saved E4SOLscreen:1560H4/78cycles,4h/24h,three size meanings+equalfactorBTCtrim; INCONCLUSIVE/no riskgate; not lifecycle/R3/economicDD. See sol-screen-report.md in current reportdir.
