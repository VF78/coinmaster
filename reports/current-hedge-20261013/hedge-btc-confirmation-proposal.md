# SOL protective hedge H1 and BTC admission B1 — owner agreement draft

2026-10-13. OWNER_APPROVAL_REQUIRED. Read-only targeted audit and concrete algorithms only: no runtime/source/config tests, economic engines, deployment, restart, orders, secrets or implementation. Canonicalhead8a488b4, installed81e6318, sourceauditedseparately. Sol6.1/medium twofocusedreadonlyreviewers; no newtotal/history audit. Reuses factualreceipt/primarysources in README.md. Proposed exact defaults are hypotheses, not optimalROI/DD proof.

## Audited installed contracts

BTCdirection comesfromcompleted1DclosevsEMA34; whenepisodeabsent, freshcrossovernotrequired. Validbeta/waves/account/admission required, marketIOC entry. NativefillinitializesmakerTPs. NativeactualTP reductions grantproportionalSOLrights (notACK). SOLoppositeBTC, signedz thresholds1.25/2.5/3.75, validbeta0.2<beta<4. H=initialconfirmedBTCgrossnotional/beta_entry staysfixedafterTP. Rollingbetamean/currentrelative, sigmafreezesfirstSOLfill. Paireddailyfeatures plus terminalnonentryfillcallback decide. SOLhalfthreshold.375/full.125afterhalfcompletionandlaterdailyindex; dailytimeout14daysfromfirstSOLfillpreemptsadds. ImmediateREGIME andDAILYprofitTRAIL groupclose ownsrestingcancel/nativeleaves. OrdinaryBTCflat retains episode/rights andcanadmitlateSOL. TheseintendedrulesdoNOTequalprotectivehedging; no newprovenbug claimed. ACK/partial/callbackedgecasesnotretestedbyreadonlyaudit.

## One shared confirmation definition

For a completed, fully warmed and received bar t at selected timeframe:

LONG(tf): Close[t] > EMA20[t] AND Close[t] > High[t-1].
SHORT(tf): Close[t] < EMA20[t] AND Close[t] < Low[t-1].

Previousbaralsofullyclosed. A freshEMA20crossoverisNOTrequired: currentdirectionandfreshcompletedbreakout suffice. Decisivebarclose strictlyafter correspondingarming, decisionuponreceiptimmediately; missed/stalebreakoutnotlatched. Same-nsdaily/hourlyboundarycannotusehourbarendingatarmtime. EMA20slopealoneisredundantwithclosevsEMAcondition understandardEMArecursion; previoushigh/lowbreakaddsdistinctpriceconfirmation. No4h requirement. Pattern/period20 areproposed, not empiricallyvalidatededge.

## H1 — replace SOL admission/lifecycle in an isolated protective candidate

ControlretainsoldSOLlogic. H1 usesONEprotectiveSOLcycle instead ofparallelalpha+hedgeowners. ExistingTPrights/z/H-multiplierentryrules remainincontrol, NOTadditionalH1prerequisites; otherwiseearlyhedge remainsblocked. TP/zvaluescanbereportdiagnostics. DoNOTpromoteH1orremoveproductionoverlaybeforeapprovednativeeconomics.

Adversitya=-sBTC*(freshBTCmark/actualBTCentryVWAP-1), sBTC=+1long/-1short. Armwhen a>0.02, actualnativeBTCheld, no mandatoryclose/pause-for-increase/reportuncertainty. ShortarmsSOLlong; longarmsSOLshortsymmetrically. Exampleshortentry81877 -> threshold83514.54; strictgreaterthan perowner. ThresholdfromENTRY notprofitablepeak.

Entryrequires a>2% stilltrueimmediatelybeforesubmit AND [CONFIRM_SOL(15m) OR CONFIRM_SOL(1h)] inoppositeBTCdirection. Qualifyingtfbarclosesafterarming, arrivesfresh;1hconfirmationnotsecondgateafter15m. A sameboundaryduplicatecannotcreate2orders. Ifpricefallsbackto<=2 beforeconfirmation, noentry; renewedcrosscanrearmbeforeanyactualhedgefill. ExistingBTCdailyregime/groupowner/control/normalquoteslotminmarginaccountbeta checksretainpriority; confirmedREGIMEclose cancelshedgeeligibility. No substitutionofunclosedbars/invaliddata.

Initialpartialfactorcoverageh=.5 (proposal). TargetSOLnotional = .5*actualremainingBTCmarkednotional/validSOL-on-BTCbeta. Reuseexistingbetawindowforfirstcandidate; no newbetaoptimization. Betaestimatevalid/fresh/positiveandexisting0.2<beta<4bounds; no nearzerodivision. Freeze beta andactualBTCquantity anchorwhenfirstprotectiveSOLfillconfirmed; qSOLnativeactual authoritative. Notional/quantityroundeddown/executableSOLquote, targetlimitedbycurrentnativeadmission/margin; notraisedbyfallingequity/growingloss. No syntheticTPrights. No separateNETTINGposition forlegacySOL+hedge: H1assumesisolatedcleanstart; cannotretrofitownershipofexistingproductionSOL.

Oneparentopening perBTCepisode; actualpartialfillsconsumehedgecycle; originalparent cancellation/ACK/leaveshandlednatively. UnknownACKdoesNOTpermitretry. Confirmedzero-fillrejectioncanretryonnew qualifyingclosedbaronlyafterterminalnativeproof; no duplicatedparent/noaveraging/no loss-inducedextraadds. Onefilledprotectivecycle/episode; no reentryafterunwind in sameepisode. Original pendingopens andactualSOL countonce inaggregatebudget, no concurrentalphaadds.

AfteractualBTCquantityreduction, protectiveSOLremainder target=qSOL_anchor*(remainingBTCqty/qBTC_anchor), nativefloor/clamp andownedreduceOnlyorder; neverincreaseSOLfromretarget. Currentprices/betadrift doNOT causecontinuousrebalancing. BTCflat targetSOLzero; settle/cancelallownedopening/TPleavesbeforenextBTCepisode, includinglateack/fillownership. No proofclaims before futuretargetednativepartial/cancel/denied/unknownACKacceptance.

H1 exitproposals: immediateexistingmandatoryREGIME/TRAIL/portfolio/liquidation/terminalclosepriority; BTCflat closesprotectiveSOL. Normalrecoveryexitwhen [a<=1% AND oppositeSOLCONFIRM(1h) onfreshcompletedbar]. 2%arm/1%releasehysteresis proposal. KeepcurrentSOLmaxholding14daysfromfirstactualfill ratherthan adduntested24h; attimeoutcloseSOLthroughnativeownedexit, no automaticsameepisodehedgereentry. TimeoutcanleaveheldBTCunprotected; thislimitedhedgeisnotguaranteedcapitalinsurance. No arbitrarynewfixedSL/noearlyprofitclosebecausehedgeisinprofit. PnLfunding/fees native, no assumedSOLeventualprofit.

## B1 — daily BTC direction, 1h actual entry confirmation

Keepcompleted1DEMA34direction. Itcreatesarmedcandidate, no immediateorder. Whenexistingnativeepisodefullyflat/ownedordersintentsresolved, waitforfreshBTC1hconfirmationinthecandidate direction. Additionalsame-sidecheckonTHESAMEcompleted1hclosevsLASTcompleteddayEMA34: shortClose1h<EMA34_daily/longClose1h>EMA34_daily. EMA34valuefrozenuntilnextdailyupdate; doNOTmixlaterlivepriceintothisclosefilter. Qualifying1hbarendsstrictlyafterarming. Actualentrynativeexecutablequote/mark/accountfilters andcurrentsizing/TPformulas/constraints unchanged, TPanchoredactualfilledVWAP.

Onnextcompletedday, expirependingcandidateandrearmlatestdailyregime evenifunchanged; nofreshdailycrossrequired/noforcedentry. InflightnativeACKownedbeforenewcandidate, unknownnotflat. AfterTRAIL/TP/genuinegroupflat, freshcandidateandfresh1hconfirmationrequiredforreentry; nooldsignalreuse. ExistingREGIMEandmandatoryexitsimmediate; WAIT appliesonlytoopening/reopening, not closinglosingpositions. No15mBTCbranchinthefirstB1proposal; speedvariant15mOR1h isseparateoptionaltestafteragreement. ThisdiffersfromR2twoconsecutiveDAILYcloses, whichmeasuredpoorDD92.13%.

## Agreement / subsequent validation

ApproveH1andB1separately: sharedEMA20+closedprevious-extremumbreak, strictentryadverse>2, SOL15mOR1h/BTC1h, h=.5, recovery<=1%+oppositeSOL1h, existing14daytimeout, onefilledhedgecycle, standaloneprotectiveSOLinsteadoldzoverlay. Values/ownership/exit changesmustbeexplicitownerchoices. Alternativepreserveoldoverlaywouldrequireanotherbudget/exitcontract, notrecommendedtoquietlycombine.

Afterfutureapproval: nativeaddressedlifecycletests/independentmoneyorderreview, thenisolatedH1onlyandB1only againstreusableV3TOTAL5437208.569511/nativeDD67.2863; jointcandidateonlyafterseeingindividualeffects/separatebounds. Full24mdata/expenses/margin/execution consistent; globalnativeDDneverreset/OHLCconditionalboundsseparate. NoROI/DDpromised. No engine or codechangeauthorizedbythisdraft. PrimarypinnedNautilus supportsnativeBarType/subscribe_bars/Cache/Portfolio/OrderFilled/oneStrategy; no executor/service/fork/versionmigrationneeded. Source/sourcehashreceiptandbacktestfaithfulnesslimitationspreserved.
