# Research memory — as of2026-10-24; read before opening archives

## Fixed controls, not approximate reimplementations
- Legacy S0 source `75ffc9c69e9d79c4da4cd0614634a3eeba48d716`; configSHA `22e1eefe8f9c71669e52a8e44b7acbdfd5f177d6ef4ae2118e9df566a05c6edc`.
- S0: TOTAL6077107.23887483; global settled DD66.25691486468686414439256686%; seed10000, original SOL-overlay. Its90% net-profit floor is5470396.514987347. Never rerun it without a necessary comparability reason and explicit budget.
- Owner24Oct new plan allows experimental70% net-profit floor TOTAL4256975.067212381; final90% remains5470396.514987347. DD<=50% primary;30–50% preferred, below30 allowed. Neither floor is rebased to BTC-only/B5.
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
- SOL is selective alpha, not continuous insurance:56.9167%SOL-active time BTCflat. New actual-fill timestamp audit qualifies cycle starts as9provenBTCflat/3held/13UNKNOWNties; old brief13/25flat-start claim is not a verified ordering result. H references grossBTC, budgets add. Later BTCcapital/size/admission effects are essential; see new-system-plan attribution.
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

## Latest market redesign — 2026-10-24: NO_GO

Project#131; reports/market-redesign-20261024/REPORT.md, comparison.json/csv and artifact-index.json. Source ec2a958e383a53133f8a8d03ef0e312810881265 (branch codex/market-redesign-btc-20261024) from exactE4bd04c9b. DefaultOFF, remote ref verified, no deployment. Real U3TP actualinventory, .5%limit-only/no chase, LEGACY_Qpurecontrol and fixedphiCLEAN_Q. All83firstentrytimes/sides match archivedE4.

| New native variant, original archive policy except declared BTC/SOL changes | TOTAL | Global settled DD | Legacy S0 netprofit retention |
|---|---:|---:|---:|
| R1 E4 BTC, SOLoff |304372.03028516|66.9203964274%|4.8519338574%|
| R2 U3TP/.5%limit-only, LEGACY_Q |225919.51131228|66.8014965826%|3.5588543734%|
| R3 U3TP/.5%limit-only, CLEAN_Q |120718.40416503|68.6033754263%|1.8248961129%|

Legacyfloor5470396.514987347 unchanged; explicitchildS0floor5835101.440491649 not used. GoalNOT_MET; R3cleanNONPASSING, no winner. Removing originalSOL changes BTCcapital/compounding; do not equate archivedBTCfillnet to BTC-aloneROI. Equal-notionalnetbp R1/R2/R3 79.570/93.837/93.822, butterminalTOTALdeclines. GlobalmaxDDnewall Jul6,2026 13:40UTC→Aug19 06:14UTC; oneApril31geometryfix is not demonstratedglobalDDsolution.

Budget CLOSED3/3full,8/8short,0active/reserved/remaining; no nextautomaticGO. All3exit0;39/41/41nativeaccountchecks,1051199continuous settledreceipts each,0modelLiq/terminalflat/orders0. R2/R3TPmissingns0/openNone/noTPIOC. Freshsigned perassetfundingcash audited againstSQLite; residual native-minusderived −2e−8/−4e−8/0 retained asrounding, notfunding. Tests135relevantqualified/18native+oneobserverPASS;2independentP1closed inonefinancialcorrection, +3observer-onlyterminalFLATlines. CIactual0jobs/no greenclaim.

Native cycles/year/worst9 and all7DD>=30/22fixedwindows pervariant saved in native-analysis-attribution-*; nativecash/UPNL/eventcounts in native-analysis-window-nativepnl-*. Endpointfundingordering and rawmark/nativeprice-rounding residuals explicitUNKNOWN/notexact; noinventedcounterfactual$decomposition. Full source/config/13inputprovenance/242sourcefilepins frozenbeforeoutcomes in full-freeze.json. Preserveoriginalshort1failure andalluniquejournals/traces.

ActualR3SOLsamefixedactionscreen:1529H4/77cycles, actualQtracechecked;24new/55old-onlyvsE4calendar. Three50%meanings distinct; bothyearsnetSOLactionsnegative/tailprotectionpositive butweakerthan equalfactorBTCtrim andcostadvantageunstable. STOP_SOL/INCONCLUSIVE; no newgate/fullSOL. NextH4counter-swing pendingsecondcancel cheapgate5/83,4filledlegs aggregatefrozenfillnet+1160.23; only1of11globalDDparentsdirectlyaffected. NOT_ELIGIBLEfornewfull, P+floor notadmitted; no extraexperiment/grid/repeat.

Source rawlegacyIOCflag overriddenOFFforeffectiveRealU andmetadataqualified. Synthetic minutecloseL1/depth1000 notvenueL2/capacity; intraminuteDD/crashopeninventoryresumeUNPROVEN. Stablemanualreconciliationboundary preserved; no pilot/production/services/credentials/orders/transfer work. Anynextfull requires new supportedhypothesis/protocol/budget, not priorapprovalreuse.


## Unified plan / causal feasibility — 2026-10-24

Project#132 Done/CLOSED/archived; reports/new-system-plan-20261024/{PLAN.md,DECISION.md}; narrowindependentreviewPASS. Owner70%experimental/90%final and DD50% anchored to originalS0 above. No product/runtime/engine changes/newbudget. Five looseDownloadsattachments copied/pinned; noZIPexists. H1B5/H5≈40k/DD45 onlyexternalunreproducedsummary,≈0.5%S0netprofit; NO_NATIVE_ADMISSION, corewithoutTPconflictsall3TP.

ArchivedS0BTC-only SOURCE759759823d69a74e72b123add5ae775dd8c3aed4ac5:TOTAL280748.52263020/DD64.0739498631/105parents/416fills; receipt/preparation/calendar/wrapper4hashesverifiedgitf7587cd8, nofreshVPSrun/rawcheck. Different sourceidentity from75ffcanchor and E4R1; no unnecessaryrepeat.

SOLattribution25actualE4cycles/198fills/1051200pairedmarks:factor270376562.111754+residual356176.035746−basis1616.8925−fees17418.931709=713702.32329125fillnetexfunding,exactcash0residual. Secondary720H1beta changesparts notmoney. BTCflat110777/194630SOLheldminutes56.9167%,heldPNL426629.8025; first5SOLcycles+105055.25329125exfunding. Cycle-startqualification9flat/3held/13timestampUNKNOWN replaces unqualifiedold13/25. Residual/excesscapsdescriptive, notcausalalpha/counterfactualTOTAL. OldsignedassetfundingUNKNOWN.

Fundingaddition toexistingR3fixedstates:1529H4/77cycles/21371outcomes,3sizes/4h24h/2predeclaredlagbins/4settlementscenarios; fullmarketcalendar/prior1m marks0missing;276directchecksPASS. HALF_MVrecipient24hnet−7.7866/−12.7651bpNBfirst/secondyear,fundingcovers13.8%/7.2%fees; no stablecycle-weightededgevsBTCtrim. STOP_CARRY, notfundingDD/newlifecycle/nativeequity.

BTCparticipationA332parents,83matchedcalendar/sides each; ownquantities/equity. Meanentered/requestedgross54known E4/R1/R2/R3=83.869/83.867/76.738/75.313%;29H4requestsUNKNOWN. Equalparentexfundnetbp80.673/80.680/94.833/94.818 (differentfromolderfundinginclusivebp). Owncapitalgap mainreason, notQdivisor:parent20equityE4160437.86/R125578.64. Full730daynativewarmup and83R2/R3firstP0audited,83d3equal; no native shortwarmup/dynamicVWAPbug. A_NO_GO; no supportedearlycapitalrestoration, H_PAIR_EXIT NOT_ADMITTED. No automaticnewgate/full or negativefamilyreopening. Exactsource/inputhashes and limitations in respectiveverificationJSON.

Nextrequiresnewcausallysupported heldBTCmarket-risk/earlycapitaladmissionmemo, actual3TP/hedgedeficitcontract and predeclaredcostgatevsBTCtrim. H_PAIR_EXIT jointreductions/no readd is architecturalproposal only; no nativebudgetopen, proposed4short/2fullNOTAUTHORIZED. Productec2a958defaultOFF unchanged, prior3/3full8/8shortCLOSED. True coherenteventDD and comparable settledDD both<=50 required forfinalPASS, missingeventdataUNKNOWN; noinventedintraminute/venuecapacityguarantee.


## Early capital true-hedge continuation — #133, 2026-10-24

reports/early-capital-hedge-20261024/DECISION.md; Project133Done/CLOSED/archived, economic70/50+90/50NOT_MET. OnefrozenH_RESIDUAL_CONTINUATIONscreen, independentpre-outcomereviewPASS. AdverseH4+SIMPLE24hbetaresidualsigned<0,720H1ends t−1h, onefirstvalidoppty/episode,24h,t+60s.391featuretriggers/62actualR3episodes29/33years13early. SOLnet≈−31/−41bpNB,early−29; SOL−equalfactortrim≈−14/−16bp,early−32. All12cohort/slip/fundingboundarycellsSTOP_CAPITAL/TRIM. Actual354fills, proportionallyreduceonBTCexits/noadds/readd, strictBTCflat; comparatoravoidsnativeexitcash/fees, restoreonlystillheld24h.248endpoints/196actualexit/1344fundingchecksPASS. Do not flip/window/grid/repeat.

ProtectionUNKNOWN_DATA_CLOCK_TERMINAL_ENDPOINT: acceptednativeobserver delayedreceipt/retainedsourcemarks, terminalsame-windowcoverageunproven. Initialassertfailedbeforemoney, oneclockcorrectionpreserved; no lossmetricinvented/clockgateweakened. Nonfinancialtiescount60→5repair moneyunchanged. Screen1/1+verify1/1; physical0.

Growth-envelope83R3inclusivecycles: exactseed+sum=120718.40416503, funding4063.32156049, ownq0maxresidual1e−8. Observed/uniformhalf/oraclelosshalving scalarTOTALequiv120718.40/44053.08/1037982.53 (1.8249/.5613/16.9435%S0net). Oracle requires4.1012xstillto70. Separatepost-resultzero-loserbookend7027879.02; retainingallwinners requires86.3883%/93.1526%negative-returnremovalfor70/90. These future-knowing conditionalalgebrascenarios/inverse requirements are NOT nativeROI/globalDD/liveparameters/generalSOLupperbounds. ExactFractionindependentPASS;7decisiontimestamp tiesUNKNOWNorder, allpreviousflat<nextactualfirstfill, initialchronologyassertpreserved.

Next onlyjointstresscontract per growth-budget-admission.md: C1alreadyusedE/H/floor.5H/C; oldbudgettrim already noautorestore. RebrandingCPPIisnotnew. PotentialdifferenceonlyjointheldBTC/SOLbasisstress/executedhedgecredit/pairedreductions. ARCHITECTURE_ONLY/no newscreen/nativeadmission: missingcausalΩ/TF/lookback/horizon/Kcost/Rpending/coherentcheckpoint/actual3TP/partial/latefill/infeasible/ordinaryincreases. No dangerousBTCwaitingforunfilledSOL, noBTCtrimleavingexcessSOL. Ifsameoldhalfcut/ADDcap STOPREUSE. No newproductorfull/short/trainingbudget; allpriorclosed, sourceec2a958defaultOFFunchanged.


## Broad discovery / positive refinement — #134, 2026-10-24

reports/broad-hedge-discovery-20261024/DECISION.md; user explicitly broadened cheap research beyondpriorone-signal gate, notoldphysicalbudgets.32fixeddiscoveryconfigs+4conditionalrefinements=36/7352scenarioepisodes.83R3cycles/354fills,81withH4opportunities,1618states/1584valid. D1cov30lag1D ownerHALFVOL includesSep, notH1fallback. Factualpricecash/rawmarkC*/Wrawterminal120718.40416503/funding4063.32156049exact; notnativewalletheld/newcandidatecapital. IdealSYNCpairedattribution only, oldnativeprotectionUNKNOWNnotfixed.

Rawcapital B2failedfavorablebreak4/12h; protection B2/4,8,12/P1underwater4/F0carrycontrol4,8. OnlyB2/F0refinedat8/12perpreregisteredranking; allHolm128adjustedp1/unconfirmed, repeatedhistorynotOOS. C2/L1empty,M1sparse,A0controlnotproduct. Independent6528+824cashendpoints/19584+2472lossmetrics/funding/cost/cohort/CBbootstrap verificationPASS; financialcorrections0. Don'trerunall36toclaimconfirmation.

Post-resultscale/all36capitalalignment usescachedlabels+83scalarreturns, notnewstrategyoutcomes/nativeROI. BestworstB2/12scalar140994.14=2.1591%S0net; all144HcasescycleboundaryDD>=55.8835%. B2/4contribution+18472, F0/8−28094..−28100fixedR3qty; earlycohortendpointsnotJan15capital. NativegoalNOT_MET, smallsidecarfullnotjustified. Oraclecoveredloserszero B2only15.43%/F0only58.79%; union71cycles/28of29losers/97.14%logburden→102.97%ONLYfutureknowingzero-loss/winnerskept, notcombinedstrategy/counterfactualnativewealth.

ReviewableNEXTpacket candidate-native-probe-proposed.md/NATIVE_PROBE_APPROVAL_RU.md; SHA9de474042ab5c2757b043a0272f4a5869f4c4d2c968d6adb7aebbdf28efc19a1. Newhypothesis realSOL3TP harvesting+PERMANENTBTCpairedcuts/monotoneparentceiling/cancelincreases. Actualpartialentrycapacitydeficit→BTCdebt; UNKNOWNrisknotinactive; absolutecapsavoidrecursive75→56.25; threeinitialtargets/unconsumedrights; VWAPfreezeIOCterminal; stockliquidity_consumptionTrue identicalOFF/candidate. IndependenttargetedreviewPASS, API/SL/funding/ACK/partial/coherentobserver stilllaunchproofs.

OwnerAPPROVED: «Утверждаю реализацию и до 4 prefix-прогонов»; approval.json records directhumanreply/protocolSHA. Isolatedimplementation+connectedtests/review+max4prefixphysicalattemptsSep1,2024→Jan15,2025(each4.5mo includingfailures): OFF/B2/combined/onecorrectionreserve. Currentphysicalcounts onlynative-run-ledger.json; full0, future2fullrequiresseparateapproval+strongprefixcapital2xcontrol/DD50/accounting/TPgates. Old#1313/3full8/8shortCLOSED. OneVPSsourceowner native_paired_owner, branchcodex/b2-f0-paired-prefix-20261024; Macimmutablecopies only. NativeAPI/partial/ACK/funding/observer/source-review/freeze gatesbeforeprefix. StockGTC-stop syntheticremainder failure preserved; verifiedIOCstop preservesactualpartialdebt. Market-only4380H4feed/observerproof ready; implementationongoing, no economicGO/pilot/production.
