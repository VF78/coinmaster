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

Approvedpacket candidate-native-probe-proposed.md/NATIVE_PROBE_APPROVAL_RU.md; SHA9de474042ab5c2757b043a0272f4a5869f4c4d2c968d6adb7aebbdf28efc19a1. Newhypothesis realSOL3TP harvesting+PERMANENTBTCpairedcuts/monotoneparentceiling/cancelincreases. Actualpartialentrycapacitydeficit→BTCdebt; UNKNOWNrisknotinactive; absolutecapsavoidrecursive75→56.25; threeinitialtargets/unconsumedrights; VWAPfreezeIOCterminal; stockliquidity_consumptionTrue identicalOFF/candidate. Implemented/source+nativefixtures+independentreviewPASS; actualeconomicprefixcoverage remains an outcome gate, never inferred from fixtures.

OwnerAPPROVED: «Утверждаю реализацию и до 4 prefix-прогонов»; approval.json records directhumanreply/protocolSHA. Isolatedimplementation+connectedtests/review+max4prefixphysicalattemptsSep1,2024→Jan15,2025(each4.5mo includingfailures): OFF/B2/combined/onecorrectionreserve. Currentphysicalcounts onlynative-run-ledger.json; full0, future2fullrequiresseparateapproval+strongprefixcapital2xcontrol/DD50/accounting/TPgates. Old#1313/3full8/8shortCLOSED. OneVPSsourceowner native_paired_owner, branchcodex/b2-f0-paired-prefix-20261024; Macimmutablecopies only. StockGTC-stop syntheticremainder failure preserved; verifiedIOCstop preservesactualpartialdebt. Market-only4380H4feed/815prefix. Publicsourcepublication separatelyexplicitlyownerAPPROVED; no deployment/pilot/production.

Currentimplementation source3323f08c57ede411058f93d96acee88928c93481 published/exactremoteverified.105/105PASS, twofocusedreviewsPASS/P0P1=0,184source/27dataengine/4additionalpins verified. TwoOFFattemptsFAILED/count2of4: firstreportdescriptor→APIbool beforeengine (repaired6f7/87PASS); secondactualnativecomplete butpartialJan monthcount4vs5/exportfailure and133funding-priorM1watermark gaps. Failedraw headline19544.07357286/82fills/fees1135.02982656/funding−633.29250058exactarchive, butNOTvalidfinalTOTAL/control; no artifact fabrication/reclassification. StrictorderedUTCmonthlabels/full24/tolerances preserved; immutableactualcash/Positionbytes/hash/epoch retained beforefunding; genuine2assettrueM1fixture11/11coverage+ON/OFFnativeeconomicparityPASS. No trading/formula/parameter/fundingchange. Uniqueallfailedsource/log/raw/journals/observerstream preserved. Detailedrepairreceipts/reviews in implementation-*.

Owner2026-10-25explicitAPPROVED+1(total5): implementation-owner-prefix-budget-amendment.json/4cb061410f40ef5d51977cd5d3f8f8a8d9ba9d21529b25eb278421137a71b4ae. Max5includingfailures/full0/noreserve; unchangedsource3323/shortgates/S0floors. OFFphysical3completed+rootacceptedmatchedcontrol TOTAL19544.07357286,settled/eventDD53.9699012088%,195839receipts/82fills/133funding exactarchive,observerPASS/flat/orders0. OSexitrcnotretained/UNKNOWN, nofalseexit0claim; fullnativeaccount/export/completionproofPASS. DailyES20=6.1399196456%,19parentES20=19.8861957744%,all136days+nativeendpointsproven. B2physical4/combined5 nextonlyrootGO. No automaticfull/sourcechanges; goalNOT_MET. Exactcurrentprocess/resultsONLYACTIVE/ledger.

## Prior floor/floor paired prefix outcome — 2026-10-25 (closed)

APPROVED5_RESULTS_RU.md: currentfixed3323 economicobservations OFFphysical3TOTAL19544.07357286/DD53.9699012088; B2physical4TOTAL20472.41817762/DD44.02687381755,ratio1.0475000568FAIL2x. Bothnativecash/fund/coverage/terminalPASS;B2exit0/OFFOSrcUNKNOWNbutdurablecompleteaccepted.136commondays/19nativeparentendpoints, dailyES20OFF6.1399196456%/B25.32672930035%,parent19.8861957744%/16.21698371226%. CostgatePASS(gain928.34460476>2x391.48732860) insufficient.990BTCdebt+985SOLcapfills on9activations/7TPfills prove sharedfloor/floor recursion; architectureNO_GO/combinedNOT_RUN. Currentledger4of5/2FAILED2COMPLETED0active/remaining1HOLDsame-source-ineligible. Do not reclassify money data/erasefailed histories.

Exactlot ratio1817/1037coprime forcespartialfloor/floor tozero; actualtrace136.3SOL->Bmax.777->SOLcap136.1->Bmax.776/.775. Read-only25088integerstatesPASS; no economicPnl/nativeextra. Proposal lot-safeBTCfloor/SOLceil mustusefrozenintegeru/v, actualreconciledcorridor, <1SOLlotextra/noadds/noreanchor/trueoversizedebt/clocks/ACK/dustguard. LOT_CORRIDOR_REPAIR_PROTOCOL_PROPOSED_RU.md SHA0e7bca174c0268f0dc2769a4918d7017d88e98f84115ee52ad22dd59c97ca7be andlot-corridor-protocol-review.md PASS. Owner laterAPPROVED exactlotcorridor protocol/cap7; currentclosedresultbelow. Old3323resultsremainhistorical/ineligible; noautomaticreuse.

## Current lot-safe native outcome — 2026-10-25, CLOSED_NO_GO

Ownerapproval lot-corridor-owner-approval.json/8da53003133e9d9781545975a37d929239834bbbbe141b3db84c6fd21d63ab8f/protocol0e7bca174c0268f0dc2769a4918d7017d88e98f84115ee52ad22dd59c97ca7be implementedas7d513ca1e0ec0fadd67167661a3173f105b19ba7 (branchcodex/paired-lot-corridor-20261025),clean/published/defaultOFF/nodeployment.112distinctqualifiedPASS acrossconnected105PASS7envSKIP+supplement12PASS/0unresolved;4nativecoprimeproofs;independentsource+supervisorreviewPASS. Exactintegeru/v/BTCfloor/SOLceil fixedrecursion; realmacro7/2B2and8/2combineddebt/caps,0spuriousdebt. Allinitialfailures/NOT_INSTRUMENTEDearlyfixturecounts preserved.

LOT_CORRIDOR_RESULTS_RU.md/lot-corridor-comparison.json:3newactualexit0matchedprefixes[2024-09-01,2025-01-15). OFF5TOTAL19544.07357286/DD53.9699012088; B26TOTAL19754.54867403/DD48.0795680585; primarycombined7TOTAL14318.18376985/DD52.0135683404. Nativecash/fees/funding/continuouscoherent+settled/terminalflatorders0/noLiqPASS; riskbasedonmarked/event, notcashheadlineDD. B2ratio1.01076925444/costFAIL; primaryratio.7326100015/capital+cost+DD50+improve5ppFAIL. All136commonUTCdays/19OFFB2parents20combinednativeparents; exactfractionaltailES20contractunchanged. No alternateB2winner/full/nativeextension. All7physicalslotsCLOSED:2FAILED5COMPLETED/0active0remaining/full0; no newsource/dataforrun/training/fullpermission. Targets70/50+90/50NOT_MET,prefixnotfull/notfreshOOS.

Observeddata/admissionNO_GO Sep2 04UTC F0_SHORT: ONLYSOLH4ATR14 unavailable; actualBTCshort1.096 nativeforcedclose BUY57721.3/fee34.79439964, flat9651.178546. D1andbothassetfundingknown. FrozenBTC/SOL1mfilesstartbenchmarkexactly;firstvalidATR Sep3 08UTC. TargetedrealH1/H4cache+knownrefs NOT_FOUND (notglobalnonexistence). No syntheticATR/backdatedsnapshot/excludedbadwindow. Warmupfixnotshownprofitable: bySep30combined14007.95>OFF12854.19/B213830.17,persistentgapfromOct13.

Completedreadonlyadmissionmemo lot-corridor-next-admission-memo.json/0902d3650210e1ff9aed7dd610ab7d7934ae29c6a395aa15f25c440e9ce8d7f5: Oct12F0closedafter85minwithnoTP/debtbutcancelled.440ofrequested.880BTCpermanent, whileactualOFF/B2laterfilledsecondchild.434/.438@62413.6. Oct25allSOLTPs170.09/168.16/164.31closedBTC.220/.220/.441toflat22:58; combinedownparent12772.446->12251.890, whileactualOFF/B2ownparentscontinuedtoOct29end16605.950/15995.205. Theseareobservedcontractgrowthlossmechanisms, notmatchedcounterfactual$effects/oracleliveentryrules. Cheapestnextadmission: qualifytrueprebenchmarkwarmupandthesetworiskoverridesagainstBTCentrycore beforeanynewnativeprotocol. No profitablefix/nativeadmissionestablished; no newbudgetinferred.


## Continuous hedge admission/preflight — #135, 2026-10-25, CLOSED LIMITED_PASS

Currentreport reports/continuous-hedge-plan-20261025/RESULTS_AND_NEXT_PLAN_RU.md merges owner goals/attachment hypotheses; goals originalS0net70%intermediate/90%final andsettled+coherenteventDD<=50/zeroLiq NOT_MET. No wipe/priority reversal. FullA/B/C/SOL/ETHgrid NOT_RUN.
BaselinearchivedS0gzip/payload/config hashesPASS, BTC-onlyreceipt distinct, correctedR3prefix reused/no neweconomicreplay. ExactR2/R3archivedconfigsdifferonlyqmode; real3TPR2225919.51 vsR3120718.40 motivatesinvestigatinglegacy sizing, coreUNSELECTED/R2SOLNOT_ADMITTED.
CHEAP_CHECK_CONTRACT frozen;48Fractionproofs/2920causalD1states(730xW30/90/180/270),inputs/UTC/gapsPASS, noWselection/ROI/OOS. hMV=rho*sB/sA; inversebeta=hMV/rho², same-windowvarianceaboveBTC105/53/27/0days. ETHnotfoundtargetcacheonly; earlyHLdailyproxyclassificationspreserved.
PublicBybit408H1Aug15-31->102H4+1680oldM1->7H4continuous; rawSHA2afa407a476e5b52ea6b1296f39be5f941445d07a586ad4e2f6ad190fc9204c0;2requests/1response/DNSfailpreserved. Exactbuilder47704f6.../Decimal50Wilder, strictSep2ATR3.7765887612 vsinclusive3.6889752782. Loaderavailable=t/ATRend=t/ordersnotbefore=t+60s retained; publicationlatency/revisionsUNKNOWN. Newfeed5a02a0bc2555404261780cb4979e398494c70194e99317d8db1020fb026b8698/4380rows only3ATRcolschanged; allD1/funding/BTCpatternsunchanged/7mutationrejects. Oldinputsnotmodified.
Ownerengineeringapproval protocolSHA28da74095f65c4ee4f2fca0ef9cfa26a999abcb2613881e2ffd8e44d89084c46 implementedas06f75778dbc3cdb9894ffed4f4e7621261e94d3e, branchcodex/continuous-hedge-preflight-20261025/clean/pushed/notdeployed. CanonicalVPSisolated same-name; Macjobsource-06f7577. Sharednativeconfighelper ASTequivalentfrozen7d, actualregisteredkwargs/domainrequestednotional/q0q1/nativefills/BASEfees/3TP verified; oldR3guard/R2pairedrejection retained, strategy/domainmoneyfunctions/SOLTP/BTCcuts/rearm unchanged.
32finalenginefreePASS;7freshnativePASS/process0 plus1F03independentlyauditednative04component(source596, physical4FAILED/process1 stays). Ledger858b453f502c3994ca563cec931544d0a7235e6f5c751ebfbe8c3aa9aed66b7f CLOSED_ENGINEERING_ACCEPTED_COMPONENT_LIMITS:11physical=9COMPLETED2FAILED,0active/disposed11, unused1CLOSED/remainingauthorized0, prefix/full/training/newdownloads0. Originalphysical3causeUNKNOWN/cachelost; first2COMPLETEDseedlimited excludedfinalcoverage; allfailedsources/logs/GOrevocations preserved. Rootfinalacceptance/process-exitreceipts/finalreviews pinned; no newbudgetinferred.
Syntheticquote/finiteseed/completedwavefixture context and NativeProbe dailyadvance/tieradmission overrides explicit; F07/F08genericregressions/F07intentionallyopen. No fullfinancialparity/venueadmission/allcasesflat/ROI/DD50/freshOOS proof. Publicsourcepublicationverified;pilot/productionuntouched. #135 Done/CLOSED/archived actualreadback; engineeringgaterootGO=false.
Nextonlycheapcontract/coreadmission: fixedcoverage+allSOLTP logicallyforcesBTCexhaustion. Chooseactualdeficit/stressbudget/deadline orprotectedresidual+realTPrights; rearmmarketedge/fee/hysteresis/turnover andstill-validBTCchildrights remainUNRESOLVED. Newmonetarycode/economicnative requiresconcreteprotocol+explicitownerbudget. Old#1347/7and#1313/3full8/8shortstayCLOSED.


## A0 bounded stage — #136, 2026-10-25, CLOSED / TP continuity AMEND4 APPROVED

Current FINAL_RESULTS_AND_NEXT_PLAN_RU.md in reports/hedge-risk-contract-20261025; allactualproofs/ownerapprovals/closedledgers/failures preserved. Source763d985617abd7a7afef5eec13912303983d8837 PUBLICexactremote/notdeployed; financialpackage340f unchanged, inputrootpathguard andwrapper fixes recorded.
Engineering7/7=3COMPLETED4FAILED/rem0/LIMITED_PASS. PrefixAMEND4CLOSED3/4=FAILED1wrongdata_rootpreengine+COMPLETEDOFF2/C03 OS0; unusedA0slot1CLOSED_NOT_RUN_NOT_TRANSFERABLE/remaining0/ledgerf893aafc7c5b65acbc55a2069af1c8738ed798a72e50816f6ab5ed5108b0d7f3/allattemptrows unchanged.
OFF financiallyqualified TOTAL20911.13611487/DDsettled-event50.130142814%/dailyES20all1365.8899433101%; C0 diagnosticcash16046.38189782/DD47.474401846%/dailyES4.5296871861%/other10checksPASS/native3TPFAIL. A0NOT_RUN/NOT_TESTED. NetC0retention55.41477839%ofOFFinTHISprefix, notoriginal2yprofitfloor; global70/50+90/50NOT_MET. DirectSOLnetPnL/causal$BTCeffectsUNKNOWN, no importedgridprofits.
IndependentactualTPadjudication raw57120s=540real(9x60)absence+56580falseaudit afterconsumedTP1/2. ActualTP3native269/273 coversheldduringmostJan7. SourcecancelsallBTCintentsincludingTPwhendebtarmed, MDwaitsdebt, nextBTCquote+60s; auditstaleacceptedsetsseparatebug. RootrejectC0; no rawreport/metric/PnL/receiptPASSrewrite. Nativecash/funding/flat/Liq remainverifiedcomponents, notqualifiedcandidate.
TPcontinuity CURRENT CLOSED_ENGINEERING_NO_GO: last-slot directownerreply/receipt1629dc8e/protocol54ecd880 preserved. IsolateddefaultOFFsource7f38278257624b321c9d88d9df962505b6f5bab0 reviewedP0/P1=0 c8f0f627, immutableMacenginefreePASS/296pins/rootGO0b4c86e8 beforeONEphysical4. ActualF4attemptf3962d0c-612d-43b2-9aa0-f3535dd67743/PID7164/OS1: PROTECTION_OVERDUE_NEXT_QUOTE153s; nonquote152.01SOLreplacementTPs matchedbook96/.3+.5 actualfills causingSECONDcancel2swindow beforequote153. BTC1.006/TP3leaves1.006,SOL0/pendingSTOP; notflat; actual5STOPPED→DISPOSED. CleanBTCDEBT.150/3queuedlatestACK/SOLinvalidtotalNativeReject/TP0TP1standing componentsreachedonly; DEFERbranchafterNO_GO notacceptednormalrisk; P2/A0/latefill/marginstalefresh/flatnodebtNOT_REACHED. Cause9b761ca0/independent4c278d64; old3rawrowsunchanged. Finalengineering4FAILED/max4/active0/rem0 ledgercc73a630; prefix0/3unused3CLOSEDnontransferable ledger899052b1/closurereceipt1cddb6ac. Original70/90profit+DD50NOT_MET, no neweconomicresult. Project2Done/issue136CLOSED/archived actualF4_CLOSED_PROJECT_READBACK. Source/defaultOFFnotacceptedforactivation, publicationnotdeployment. NextpossiblecontractSOLcancelreplacewithoutweakeningguard; newcode/nativeonlynewconcreteprotocol+ownerbudget. CurrentRESULTS_AND_NEXT_STEP_RU/ROOT_CURRENT_DISPOSITION/ACTIVEsolehandoff; allrawimmutablefailedsources/drafts/locks preserved; full/pilot/production0.
Realstockinputpreflight /inputs/data/9files/730SOURCErows/814fundpriorM1/195840alignedminutes and financialframework UUID+COMPLETED+reportSHA/immutableentrysnapshots/priorfinancialreceipts retained; newSource mandatory/freshOFFparity thenC0financialPASSbeforeA0. Exactcurrentauthority onlyACTIVE/actualownerreceipts, oldbudgets#135/#134/#131CLOSED. PUBLICsource+managerbranches alreadyexplicitlyapproved/no newpublicationpermission needed/no deployment.
