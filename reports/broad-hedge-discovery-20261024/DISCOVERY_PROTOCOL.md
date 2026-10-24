# Broad discovery: общий протокол до новых outcomes

24.10.2026, CM-BROAD-HEDGE-20261024. Владелец прямо попросил максимально широкую начальную проверку гипотез, затем оптимизацию положительных направлений. Новый запрос разрешает ограниченный широкий **saved-data** отбор, включая честно зарегистрированные варианты старых семейств; он не меняет результаты#131–133 и не открывает старые full/short budgets. Product/native/full/short/trainingbudget0. Пилот/production исключены.

## Что проверяется и что не обещается

16 фиксированных signal/action specifications ×2 природных горизонта4h/24h =32discovery configurations. Это разные рыночные механизмы и контроли, не плотная сетка оптимизатора. Все пороги фиксируются здесь до outcomes. При положительных gates разрешена одна условная refinement-stage: максимум2разных семейств, ещё8h/12h укаждого (до4дополнительных configurations). Не менять знаки/окна/пороги по неудачным результатам. Фактически максимум36configurationsevaluations; полный potentialuniverse16rules×4горизонта×2lanes=128tests учитывается в multiplicity, включаянетестированныеварианты(p=1); это не128nativeпрогонов.

Исходный экономический benchmark/floors неизменен: S0TOTAL6077107.23887483/seed10000; research70%TOTAL4256975.067212381, final90%5470396.514987347; globalsettled/coherenteventDD<=50%, liquidations0, real3TP обеихног. Эта библиотека не выдаёт candidateTOTAL/DD/retention и не доказывает nativeexec/TP/margin/capacity.

## Общий universe и clocks

Пересобрать все H4completed-close decisions в83actualR3BTCepisodes из354nativefills, включая раннийсентябрь. OnlyheldBTC, nofills exactly t/e (UNKNOWNordering→noaction). Signalfeatures известны кt; entryreference e=t+60s. ActualBTCquantity наe проверяется изactualfills, а неpending/Qmax. Первый validqualifying opportunity каждого rule/episode; нетfuturebestentry, no re-add. БудущийBTCflat не фильтр входа.

Единый primaryriskestimate **D1cov30_lag1D**: последние30pairedSIMPLEdailyreturns, ending at latest dailyclose c<=t−24h. Covariances ddof1, beta=Cov(S,B)/Var(B), a=.5sigmaB/sigmaS; require finitepositive variances/beta/rho (rho<=1 numericaltolerance1e−12, preserve measuredresidual). Это отдельная заранее выбранная оценка для всего benchmark, не H1fallback. Daily730warmup доступен,730overlapdays OHLC exactsameasminuteaggregation. Все определения ниже используют этот beta/rho/a; H1shortcorr используется только как отдельный feature. H1lag720 выводить как provenance/control, не выбирать лучшуюsizeконвенцию. Insufficientfeaturehistory=NA, не0.

Вычислять causal H4/H1OHLCV/turnover изcompletedexecutionminutes; currentmark/executionbasis изrawcompletedminuteclose. При dailydecision/interval ties доступнытолькоcompleted fields; beta/stressdailywindowконсервативноотстаёт24h.

## Rule registry (root supersedes альтернативы design-families.md)

Notation: s=actualBTCside, rB4=CB(t)/CB(t−4h)−1, A=(s*rB4<0). Previouswindow excludes currentbar unless stated. Всеrules требуютcommonvalidity.

| ID | Fixedsignal | Identity/action |
|---|---|---|
| A0 | allheldvalidstates | Unfilteredcontrol, не самостоятельное разрешениеSOLбезриска; standardSOLaction |
| A1 | A | KnownadverseH4control; standardSOL |
| B1 | longCB<min(previous6H4lows), shortCB>max(previous6H4highs) | adverse24hrangebreak; standardSOL |
| B2 | previousH4close broke favorable preceding6H4extreme; currentclose back inside that sameextreme AND A | failedfavorablebreak; standardSOL |
| V1 | A AND abs(rB4)>2*sqrt(mean(previous6H4rB4²)) | volshock; standardSOL |
| C1 | A AND s*rS4<0 AND rhoD1>=.5 | commonmovecorroboration; standardSOL |
| C2 | A AND pairedcorr(last24completedH1returns endingt)<=0 | breakdowncontrol, notproducthedgeadmission evenifcashpositive; standardSOL |
| M1 | A AND s*(b_now−mean(b_previous30D1))>2*sd(b_previous30D1), b=markS/executionS−1−beta*(markB/executionB−1) | mark/executiondislocation, notspot/perpbasis; currentminutevsseparate30D1lag1Ddistribution; standardSOL |
| L1 | A AND BTCcurrentH4turnover<.5*median(previous42H4turnover) AND currentH4range/close>median(previous42range/close) | thin-turnovermove, noliquidityguarantee; standardSOL |
| P1 | A AND s*(CB(t)/firstactualBTCfillprice_currentepisode−1)<0 | initialfillreference underwater, NOTnativeaveragecost; standardSOL |
| P2 | A AND adversegivebackfromrunningfavorableexecutionminuteclose_sincefirstfill >=1*completedH4WilderATR14 | causalprofitgiveback, notfutureMFE; initializeATR first14TR, thenWilder, nofakewarmup; standardSOL |
| R1 | A AND s*(RS24−beta*RB24)<0 | knownresidualcontinuation, registeredcontrol; standardSOL |
| R2 | A AND s*(RS24−beta*RB24)>0 | reversalbranchofSAMEresidualfamily, explicitlypermittednewbroadcomparison; standardSOL |
| F0 | A AND s*(gS−beta*gB)>0, g=laststrictlypriorfundingrate / hoursbetweenlasttwopublications | oldcarrydifferentialcontrol, notfuturefundingprediction; standardSOL |
| J1 | held-onlyL0 >.5*max(C,0), C=observedWraw(t)−.5*historicalHraw, and ellH<bmax | cushionwarning, flooritselfold; standardSOL |
| J2 | held-onlyL0 >max(C,0) | highstress failclosedBTCtrim + optionalSOL, formula below |

P2 distance: long peakExecutionClose−CB(t); short CB(t)−troughExecutionClose. Include onlyrawclosesavailable sincefirstnativefill. P1 avoids reconstructingaveragecost/matching; no futurefillsused. B1/B2 and C1/C2 correlatedgroups; R1/R2 samefamily. A0/A1/R1/R2/F0 containknownnegative/reusedelements; positivecontextnotnewOOS/newpermission. No retrospective relabeling#133.

## Actions and held-only J2 budget

**SizingclockforALLactions:** signal/size/budget вычисляются наt, никогда наfutureexecutionclosee. qref=abs(QB_pre_t) наt; наe требуетсятажеBTCсторонаиТОЧНОтакоежеactualquantity (иначеUNKNOWN_CHANGED_POSITION/noaction, не пересчётразмера). Никакогоfuturequantitymin; eпроверяетсятолькокакусловиеисполненияужеизвестногоколичества. x=qref*PBexecution(t), y=a*x, qSOL=y/PSexecution(t), side−s. Entrycash/fees/actualreferencenotionalиспользуютценыeкакoutcome. Equal-factorBTCtrimнаentryудаляет beta*qSOL*PSexecution(e)/PBexecution(e); сигнал/количествоSOLнеизменяетсяпоценамe. Еслиэтотtrim>actualheldBTC, UNKNOWN_COMPARATOR_CAP, неclipифальшиваяfactorравность. Сizingfactorcoverageнаt=.5rho, не50%DD; fill-pricevariationсохраняется. ВсеmetricsнормируютсянафиксированныйNB=xнаt. CompareNOACTION. Continuousquantities/quote-referenceprices are diagnostic, not actualfills/lotadmission.

Jstressfeaturesuse SAME lagged30D1window: bmax=max(abs(rBday)); epsmax=max(abs(rSday−beta*rBday)); includeallfour independentcorner shocks (±bmax,±epsmax) in factor/basiscoordinates. ellH=(1−beta*a)*bmax+a*epsmax; bmax/epsmax not hardbounds. L0=x*bmax+κ*x+3*x*fB, κ=.00075 (taker.00055+reserve2bp); fB/fS=maxabspublishedfundingrate over30days strictlybeforet. Fundingreserve3BTC/12SOLsettlements perday is fixedconservative scenario assumption, nothistoricalscheduleclaim. C наt uses onlynativefills/funding withtimestamp<t плюсrawcompletedmarkatt; currenttimestampfundingнеfeature. Hraw=max(knownobservedgroup-boundarywealth at earlieru<t,currentpre-eventWraw_signal(t)). Всеx,C,H,u,vнаt; eценыисключительнодляcashflow/фактическогоfactorcomparator. Этоobservedreference, not delayednativeequity/hardfloor.

ForJ2 first reduce unsafeBTC **withoutcreditforunfilledSOL**:

`u=clip((C−κ*x)/(x*(bmax+3*fB)),0,1)`.

IfellH<bmax, optionaloppositeSOLafterBTCreduction is onlya*v*x with

`v=min(u,clip((C−κ*x)/(x*(ellH+2*κ*a+3*fB+12*a*fS)),0,1))`.

Jointaction removesBTCquantity(1−v)*qref, addsSOLquantitya*v*x/PSexecution(t). NoBTCrestorationfromhedgecredit. IfellH>=bmax, noSOL: pureBTCtrimu; tagTRIM_ONLY_FALLBACK, notSOLsuccess. IfC<=κ*x, v/u0; tagINFEASIBLE_FLOOR (emergencyfulltrimdiagnostic, noclaimfloorprotected). Zero-denominator/unknowninputs=NA. Equal-factorcomparator наe removesactualjointBTCtrimqty +beta*qSOL*PSexecution(e)/PBexecution(e); capvalidityкаквыше, безскрытогоBTCshort. Puretrimfallbacksameasreference. Jointcashflows=sumBTCtrimcomponent+SOLcomponent.

K includesfuturecosts, notpastfeesalreadyinWraw; held-onlyRpendingis **UNMODELED/UNKNOWN**, not0fullportfolioproof. No new whole-controller admission, pending/execution/3TP/increases stillrequirelaternativecontract. ActualfuturebaselineBTCadds remainobserved but do notincreaseoverlayquantities; this is one cappedaction, notpersistentbudgetguarantee.

## Descriptive loss attribution and costs

Freeze **IDEAL_SYNCHRONOUS_PAIRED_ATTRIBUTION** forcheaptriage. AtobservedBTCnativefillr, proportionalSOL/trimreductionusescompletedrawexecutioncloser; forcedflatclosesremainingSOLatthatrawclose. This is an optimistic same-timestamp pairing assumption, NOTreactiveexecutablefill/atomic3TP. Terminalrawcloseexists. Old#133nativeequityprotectionUNKNOWN remainsunchanged. StageII is stillanalytic; no nativecausalityclaim.

Useactualnativefilltimestamps, prices, qty andcommissions, plusactualpersistedsignedBTCfunding. `C*=seed+sum(−dq*fillpx−fee)+sum(actualfunding)` is settlement-equivalent **pricecash**, NOTnativefutureswalletcash whileheld. `Wraw=C*+qBTC*rawcompletedmark` is observedfillattribution. Reconcileflatendpoint andcyclecash toacceptedR3TOTAL120718.40416503 beforelabels. No averagecost/OMS/matching/newcandidatecapital. Sourcebasis/nativeprice-roundingdifferencespreserved.

Baseline localpath usesobservedWraw frome beforehypoaction throughend=min(e+horizon,firstactualBTCflat). Include completedminutes andknownpre/posttimestamp-groupfills/cash/funding, include terminalflatgroup; nofuturefullhorizonfilter. Openoverlay value fromtradecashflows plus signedcurrentqty*rawmark. Recordlocalworstchange fromstart andsampledpeak-to-trough; these are **localdescriptivemetrics, NOTglobalnative/eventDD orintraminutebound**. Same-timeactualeventorderingUNKNOWN grouped/bracketed, notfabricatedticks.

All actualBTCreductions shrinkeverydiagnosticremoved/hedgeqty pro-rata QBafter/QBbefore; noenlargingonBTCadds/no-readd. SOLclosespaytaker. BTCtrimcreditsavoidednativeexitcash+proportionalrealcommission; onlyscheduledstillheldremainderrestoreswithtaker. AtflatBTCnotreopened. FundingincrementSOL/avoidedBTCusesfullmarketcalendar andpriorcompletedmark, continuousheldqty. Two fixedbefore/afteractionfundingboundaryalternatives retained; baselinefundingactual, notestimatedratecashbridge.

Costcases0and2bpadverseperhypotheticaltakerleg, BASE.055%taker; avoidednativeexitsdon'tpayfictionalslip. Four **coherentscenario tables**: 0bp/BEFORE_ALL,0bp/AFTER_ALL,2bp/BEFORE_ALL,2bp/AFTER_ALL. ВнутрикаждойтаблицыобщийfundingorderиспользуетсянакаждомepisodeдляSOL/TRIM/NOACTION; невыбиратьразнуюветвьдляmean/tail/каждогоaction. GatesдолжныпройтиВСЕчетыретаблицы; 2bpнеавтоматическиworstдляpairedadvantage. Всеbefore/afterточкинеисчерпываютпроизвольныеmixedcallbackorders: executionambiguityневыдаётсязадоказаннуюграницу. Features neverusefuturefunding. Unknownfundcalendar/mark/ownership→NA, not0.

## Selection, statistics and refinement

All32stageIconfigurationsreported includingempty/failed/controls. Maincohorts entryyear1/year2 andearly[2024-09-01,2025-01-15). Minimum10distinctepisodes/year and3early forqualification; fewerpositivecasesonlySPARSE_DESCRIPTIVE. Counts bylong/short; don'tfitonlyonefutureprofitabledirection. ReportsallR3episodeswithnoactioncoverage, notjustgoodhorizons.

**Exactlossestimand:** L_A=max(0,Wraw_start−min_[e..end](Wraw_baseline(u)+V_A(u)))/NB_t, whereWraw_startisbaselinepreactionwealthattheentryeandV_Aincludesentryfee/markbasis. L_N usesV=0. CVaR20(L)=meanlargestceil(.2*n)L, recomputedontheSAMEpairedopportunities. Sampledpeak-to-troughisadditionaldescriptivefield, NEVERsubstitutedforL/CVaRselection.

Capital-lanepositive: meanoverlaynet>0 AND meanequal-factorpairedadvantage>0 inEVERYmaincohort andEVERYfourcoherentscenario. Protection-lanepositive requires CVaR_N−CVaR_H>0 everywhere AND **oneconsistentroute** everywhere: routeRETURN meansmean_H−mean_T>0, routeRISK meansCVaR_T−CVaR_H>0. Thisisexplicitstrictnondominance: strictreturnadvantage ORstricttailadvantage; equalityalonecannotadvance. Ifreturnrouteworksoneyearandriskrouteonlyanother, labelMIXED_FRONTIER_DESCRIPTIVE, notqualification. CostlyhedgesmayadvanceviaRISK; positiveSOLmeanineveryyear isnotnecessaryforwholeoptimization. TRIM_ONLY/C2/A0cannotbeclaimedtrueSOLcandidate, evenifdiagnosticpositive.

Monthlyclusterbootstrap B=8192 seed20261024, nominalalpha=.05, withinEACHpredeclaredcohortsamplingitscalendarmonthswithreplacement, samecalendarblockcount (12/12/5includingpartJan), allselectedepisodeswithinthemonthstaytogether. RecomputemeanandCVaR20INSIDEeachresample; sampletailnotfixedtotheoriginalextremes. Pairedsameblocksforactions. ReportCIsandcenteredone-sidedp=(1+count(Tstar−Tobs>=Tobs))/(B+1), forpositivecontrastT, as **approximate selection diagnostic** understationary-monthassumptions, notcausalevidence/OOS. Primarycapitalcomponentcontrastsmean_H andmean_H−mean_T; lane p=max(allcomponentp over3cohorts×4scenarios×2contrasts), intersection-unionrule. ProtectionrouteRETURNp=max(p(CVaR_N−CVaR_H),p(mean_H−mean_T)) overallcohorts/scenarios; routeRISKanalogouswithCVaR_T−CVaR_H. Protectionlane p=min(1,2*min(pRETURN,pRISK)), conservative2routeBonferroni. Onecombinedp/lane/config, noselectingfavorablecohort/mean/tail. Countall128potentialconfiguration/lane tests inHolm, evenunused/emptytests(p=1). Sparse/invalidp=1. Reportadjustedp alongside rawdiscoverygates, notclaimconfirmationfromuncertainp. Monthdrawwithnoepisodes→retrywithinfixedmax65536draws, otherwiseUNKNOWN. ДляrawgateFAIL/sparse/invalid можноневычислятьbootstrap: присвоитьconservativep=1/NOT_TESTED_FAIL, неутверждатьCI. Толькоrawgatepositiveconfigurationполучает8192draws; этоэкономияinference, неновыйпорогилиисключениеизHolm128.

Ranking capital: maximize minimumprimarycohortpairedmean, thencoverage. Rankingprotection: maximize minimumcohortCVaRgainvsbaseline timesepisodecoverage, thenmeannet. Atmost2distinctpositivefamiliesadvance (prefer1perlane; ifonlyonelane,2differentmechanisms). R1/R2samefamily, B1/B2samegroup,C1/C2samegroup. Nativeadmissionnotautomatic, pnonpassing=NOT_CONFIRMED. Sparseonlycasesdonottriggerparamtuning.

StageII only8h/12h forselectedrules, allsignals/size/costsunchanged; thisinternalrefinementreuseshistory, notvalidation. CombinedHolm128potentialtests andrecordallattempts. Ifnoqualifiedpositive, noStageII. No additionalcellsafterfailure, noML/Optuna/tickfillreplay. Reportpromisingdirectionsseparatelyfromconfirmed/qualified.

## Budget

Onecommonfeature/librarybuild+oneconnectedverification; oneStageIdiscoverypass+verification. Maxoneconcrete substantialcorrection perimplementationpass, initialfailurespreserved. ConditionalStageII onepass+verification max4extra configurations. Allphysicalnative/full/short/training/simulator0. Freezeprotocol/registry/source/datahashesandUTCledger BEFOREnewoutcomes. Oneanalysiswriter; independentspecificcontractreviewbeforeoutcomes. RootownsProject/ACTIVETASK/publication. Anyfutureproduct/fullrequiresconcretecandidate/nativeprotocol/explicitnewbudgetafterreview.
