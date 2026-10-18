Updated: 2026-10-18 (Europe/Moscow). Research only; no deployment.
Goal: improve BTC entry execution without changing permissions/sizing rules; test explicit SOL factor hedge against verified V3 TOTAL 5,437,208.56951095.
Authority: .ops/CoinMaster_BTC_Split_SOL_Hedge_Research_Plan.md and owner message 2026-10-18. No trader/config changes, real orders or transfers.
Canonical checkout: /root/.openclaw/workspace/coinmaster/coinmaster; branch codex/nautilus-btc-sol-mvp. Never manually edit /opt/coinmaster.
Git: economic source e4f4e675c468d799d406198e04323ba04655d913; pushed result/docs checkpoint b22506c8990db6492759988d041d867626a44974.
Project #2 is status truth: #113 parent; #77 Done; #115/#116/#117 In Progress; #101 Todo (HL data blocked). 37 unrelated cards archived, issue history retained.
Owners: split_cover_engine alone edits engine/domain/tests/runner; split_cover_stats owns disjoint analytics; split_cover_review independent narrow review. New executor work: Sol6.1/medium.
P0 accepted: 105 V3 parents; real Bybit execution+mark 1m, [2024-09-01,2026-09-01), 10,000 seed, reserve=0, DP OFF; existing fee/funding/margin model.
P0 statistics: early57 / late48 (already seen, sensitivity not honest OOS); BTC .25/.50% limit, 4h, confirmation OFF; SOL .50% adverse + later closed15m + quote .25% better, 4h.
P0 warmup: official Bybit Jun–Aug2024 hourly bars, 2208/asset; 30/90d simple-return beta available for all parents. Price proxies are not native ROI.
P1 accepted: native Nautilus1.231, existing maps/journal/NETTING, flags default OFF; 32 focused tests PASS, earlier136 combined PASS with overlap; targeted independent GO.
P1 fixes and exact source/test hashes: implementation-contract.md and native-money-order-review.md under reports/btc-split-sol-cover-20261018/.
Control verified/reused: V3 TOTAL5,437,208.56951095; marked minute DD67.2863064484%; min equity4514.69512879; fees1091093.07886765;105 parents;0liq/flat.
BTC025 complete: TOTAL4,759,384.60025755; DD77.9381541151%; min2990.60113081; fees809694.77098014;619fills/104parents. All accepted Q filled, no rejects/liquidations. Fails ROI/DD/parent goal.
BTC050 complete: TOTAL4,379,050.17052615; DD77.6497393645%; min3030.52505176; fees843273.58556398;617fills/104parents. All accepted Q filled;0liq/flat. Fails goals.
BTC cause: blended entry VWAP moves TP/TRAIL thresholds. Mar13 short return crosses original3% only in V3; retained SOL blocks Mar16 entry. No order rejection or missing accepted quantity.
Earlier BTC DD cause: Sep11 second half forced at56750.6 vs first57642.4; shifted TP3 becomes later REGIME loss. Mean price improvement does not guarantee portfolio improvement.
SOL50 complete: TOTAL21,765.86882504; DD56.4035236202%; min7556.56169203; fees18200.79784808;614fills/105parents;0liq/flat; all rows and88 frozen files verified.
SOL50 matches all105 BTC permission dates/side/q0/q1/quotes;104 quantities change via equity. Fill attribution: BTC+73301.03945 / SOL-62161.94650; helps39/48 losing BTC episodes but loses55/57 winning ones.
SOL50 actual fill+mark coverage: mean49.98754%;45–55 band99.97792%;zero=0%; above100%=0%; below45=71min. Cached quote snapshots lag fills and must not be used as proof of zero hedge.
SOL75 complete: TOTAL23,826.61849406; DD55.34519210%; min7371.60560758; fees19936.44966193;675fills/105 exact BTC permissions;0liq/flat/full rows. BTC fillnet+77189.93740877/SOL-64088.02637070; tactical allocation+2061.7590646, CORE-66149.7854353; actual mean cover50.3369%, zero/>100 both0. Analysis64-file manifest verified.
Current run: cm115-split-sol100-20261018a.service; last initial case. HEADb225 docs/analytics; all88 economic/warmup files equal SOL50/e4f.
Run guards: one full engine; shared650MiB/Swap0; prelaunch availableRAM>=700MiB and disk>=1GiB; no secrets/network, frozen readonly inputs, fresh funding journal, gzip minute trace, protected-pilot check.
Selected ONE refinement: BTC025_PLANREF; same .25%/4h split, TP/fallback/TRAIL/best_f use frozen completed first-leg actual VWAP P0. Native blended VWAP/cash/fees/PnL/H stay actual.
PLANREF implemented in dev after SOL100 snapshot independence proof:88 separate nlink1 copies, snapshot-only PYTHONPATH, dev inaccessible; all frozen hashes unchanged. Fresh headroom recovered;10 focused native cases PASS in4.02s under256MiB/Swap0 after one dummy feature z=None correction; actual frozen snapshot unchanged. Prepared patch+hashes+contract under reports; preliminary review no blockers; final independent GO for isolated computation, exact6source/test pins verified; full24m economics/permissions still pending. Guard.05/15mON unrun; do not apply.
Budget: at most8 new full24m runs:5 initial +1 BTC refinement +1 eligible nonduplicate joint +1 fresh selected result. No arithmetic addition of screening savings.
Next: sole engine owner applies PLANREF and runs10 focused cases (256MiB/Swap0/CPUWeight10, private network, availableRAM>=1GiB); reviewer GO obtained; root checkpoints exact source before ONE full run, strictly after SOL100 receipt. Stats finishes SOL75/SOL100 compact analysis.
Signed funding UNKNOWN; cash residual is not funding. Asset fill attribution is analytics, not another ledger. Prior uPnL reconstruction residual183.456 remains unreconciled; do not spend further passes or claim minute joint-PnL proof.
HL blocker #101: no verified venue execution+mark/funding archive for24m or2022..today. Recent API1m only;2022 zero-volume daily rows are not trades. Probe dates are not gapfree-history proof. No Bybit substitution.
Protected Sandbox: installed81e6318, PID2009732/NRestarts0, epoch10e39dc6efa64c8b820b174c0a5b65fe. Live inactive/disabled; Hermes/sites/VPN untouched.
Previous live82 prep retained: reports/live82-implementation-20261015 and #101; source6c208fd/GUIbe2f71d, V3+DP50 planned82USDC. Funding/auth/qualification and exact real-order approval still required.
Evidence: reports/btc-split-sol-cover-20261018/{screening-recommendation.json,v3-reuse-verification.json,*receipt.json,comparison-analysis*,btc-planref-v1-*}.
Raw immutable jobs: /var/lib/coinmaster-native-gui/data/runs/jobs/cm115-split-*-20261018a. Full rows1051200/source. Minute-close diagnostic execution is not historical BBO/L2 or intraminute path proof.
Cleanup18Oct: deleted597321440B disposable apt indexes/closed OS log rotations/old GUI staging; free3658424320B, pilot unchanged. Receipt vps-safe-cleanup-20261018.json; no further obvious large safe cache.
Historical ACTIVE_TASK narrative preserved in Git e4f4e67. Read this compact status and linked evidence before old audit queues.
