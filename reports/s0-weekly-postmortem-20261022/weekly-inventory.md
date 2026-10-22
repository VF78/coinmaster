# Аудит исследований CoinMaster за 15–22 октября 2026

**Ни одна фактически проверенная адаптация точного S0 не сохранила 90% его чистой прибыли при agreed DD≤50%.** Положительный измеренный переход недели — сохранение BTC-плана через PLANREF и nativeTP-IOC catchup; новые хеджи/страховки/срезания риска в основном лишали SOL-alpha и последующего compounding. Прогнозные отрицательные результаты не являются низким измеренным ROI: у них экономики не было.

Объект контроля: S0 TOTAL 6,077,107.23887483 USDT; seed 10,000; порог TOTAL≥5,470,396.514987347; settled DD 66.256914864686864%. Все суммы ниже USDT. `UNKNOWN` означает неизвестно/не оценивалось, а не 0. Native callback DD 66.31878025 и settled DD 66.25691486 — разные наблюдатели одной экономики. CashDD/OHLC/prefixlowerbounds не объединяются с ними.

Инвентарь основан только на локальных README/summary/CSV/receipt и git history. Коммиты reports найдены 18–22 октября; отсутствие 15–17 октября не доказывает отсутствие внешней работы. Дата запуска имеет приоритет над датой повторной публикации. Source берётся из receipt; если известен только publicationcommit, executedsource остаётсяUNKNOWN. Каждый источник и его SHA указаны в JSON/CSV. Полные логи/ценовые ряды не читались; новых расчётов стратегии, прогнозов, fit или native не было.

Реестр: 68 строк недели; 21 завершённый full native с приемлемой экономической фиксацией (включая repeat/reproduction), 2 дополнительных fullfeed с исключённой ошибочной реализацией. Это не число уникальных стратегий; pipeline/ресурсные/аналитические строки не суммируются как независимые экономические опыты.

## Фактические native-опыты недели

|Дата|Опыт|Тип / контроль|Source или publication*|TOTAL|DD % / метод|Fees|Статус|
|---|---|---|---|---:|---|---:|---|
|2026-10-18|SPLIT_btc025|FULL_NATIVE_24M / V3 5437208.56951095|e4f4e675c468d799d406198e04323ba0|4,759,384.60|77.94 / NATIVE_CALLBACK_MARKED|809,694.77|COMPLETED_NOT_SELECTED|
|2026-10-18|SPLIT_btc050|FULL_NATIVE_24M / V3 5437208.56951095|e4f4e675c468d799d406198e04323ba0|4,379,050.17|77.65 / NATIVE_CALLBACK_MARKED|843,273.59|COMPLETED_NOT_SELECTED|
|2026-10-18|SPLIT_sol50|FULL_NATIVE_24M / V3 5437208.56951095|e4f4e675c468d799d406198e04323ba0|21,765.87|56.40 / NATIVE_CALLBACK_MARKED|18,200.80|COMPLETED_NOT_SELECTED|
|2026-10-18|SPLIT_sol75|FULL_NATIVE_24M / V3 5437208.56951095|1539d287f14f8e75a3c29f9025d745f7|23,826.62|55.35 / NATIVE_CALLBACK_MARKED|19,936.45|COMPLETED_NOT_SELECTED|
|2026-10-18|SPLIT_sol100|FULL_NATIVE_24M / V3 5437208.56951095|b22506c8990db6492759988d041d8676|26,111.23|54.34 / NATIVE_CALLBACK_MARKED|21,822.89|COMPLETED_NOT_SELECTED|
|2026-10-18|SPLIT_btc025-planref|FULL_NATIVE_24M / V3 5437208.56951095|0280fd67c30b29b94406ffb6b78cd07d|6,005,487.81|70.47 / NATIVE_CALLBACK_MARKED|960,263.21|COMPLETED_NOT_SELECTED|
|2026-10-18|SPLIT_btc025-planref-tp-ioc|FULL_NATIVE_24M / V3 5437208.56951095|759823d69a74e72b123add5ae775dd8c|6,077,107.24|66.32 / NATIVE_CALLBACK_MARKED|945,927.74|ACCEPTED_HISTORICAL_WINNER|
|2026-10-18|SPLIT_S0_FRESH_REPEAT|FULL_NATIVE_24M_REPEAT / S0 selected Oct18|759823d69a74e72b123add5ae775dd8c|6,077,107.24|66.32 / NATIVE_CALLBACK_MARKED|945,927.74|REPEAT_PASS_26_OF_26|
|2026-10-18|COND_INVALID_TP3|FULL_NATIVE_24M_INVALID_IMPLEMENTATION / S0|2a3f830c18c7ac5d2b5add3dc9778b84|880.08|94.52 / NATIVE_CALLBACK_MARKED|1,940.85|EXCLUDED_IMPLEMENTATION_ARTIFACT|
|2026-10-18|COND_INVALID_IOC|FULL_NATIVE_24M_INVALID_IMPLEMENTATION / S0|07339b7f8f9360ec4ddce8ac2b46da75|19,158.85|98.02 / NATIVE_CALLBACK_MARKED|51,303.93|EXCLUDED_IMPLEMENTATION_ARTIFACT|
|2026-10-18|COND_ABORT_BTCFLAT|NATIVE_PARTIAL_OR_ABORTED / S0|862fec1|UNKNOWN|UNKNOWN / NOT_EVALUATED|UNKNOWN|NO_VALID_FULL_ECONOMICS|
|2026-10-18|COND_CALLBACK_FAIL|NATIVE_PARTIAL_OR_ABORTED / S0|44f2e00|UNKNOWN|UNKNOWN / NOT_EVALUATED|UNKNOWN|NO_VALID_FULL_ECONOMICS|
|2026-10-18|COND_2_1_50_FINAL|FULL_NATIVE_24M / S0|d83e8faccdeeba26f1f4b454fdc07074|3,007,648.74|67.69 / NATIVE_CALLBACK_MARKED|844,851.65|ECONOMIC_FAIL|
|2026-10-18|SOL_RISK_cap50|FULL_NATIVE_24M / S0|6902929|3,314,315.93|58.02 / NATIVE_CALLBACK_MARKED|740,549.26|ECONOMIC_FAIL|
|2026-10-18|SOL_RISK_dd-cov|FULL_NATIVE_24M / S0|6902929|4,046.59|70.54 / NATIVE_CALLBACK_MARKED|6,933.97|ECONOMIC_FAIL|
|2026-10-18|SOL_RISK_split-atr|FULL_NATIVE_24M / S0|ddfc84c|113,562.55|93.92 / NATIVE_CALLBACK_MARKED|76,251.13|ECONOMIC_FAIL|
|2026-10-18|SOL_CAP_STARTUP|STARTUP_NO_MARKET_ROWS / S0|157258f→6902929|UNKNOWN|UNKNOWN / NOT_EVALUATED|UNKNOWN|STARTUP_FAILURE_NOT_ECONOMIC_RUN|
|2026-10-19|INSURANCE_i25|FULL_NATIVE_24M / S0|f878cd401e3ac7482e3919324c11ddaa|8,000.31|67.60 / NATIVE_CALLBACK_MARKED|19,420.70|ECONOMIC_FAIL|
|2026-10-19|INSURANCE_i25-light|FULL_NATIVE_24M / S0|f878cd401e3ac7482e3919324c11ddaa|7,864.88|68.30 / NATIVE_CALLBACK_MARKED|19,540.68|ECONOMIC_FAIL|
|2026-10-19|INSURANCE_i25-recovery|FULL_NATIVE_24M / S0|f878cd401e3ac7482e3919324c11ddaa|7,720.28|67.62 / NATIVE_CALLBACK_MARKED|20,756.64|ECONOMIC_FAIL|
|2026-10-19|INSURANCE_i33|FULL_NATIVE_24M / S0|f878cd401e3ac7482e3919324c11ddaa|2,026.97|84.64 / NATIVE_CALLBACK_MARKED|12,172.81|ECONOMIC_FAIL|
|2026-10-19|BTC_ONLY_REFERENCE|FULL_NATIVE_24M / S0|759823d69a74e72b123add5ae775dd8c|280,748.52|64.07 / NATIVE_CALLBACK_MARKED|76,260.55|STANDALONE_REFERENCE_NOT_ATTRIBUTION|
|2026-10-19|ALPHA_A|NATIVE_PARTIAL_OOM / S0|2b3cd5f|UNKNOWN|UNKNOWN / UNKNOWN|UNKNOWN|INCOMPLETE_NO_TERMINAL_TOTAL|
|2026-10-19|ALPHA_B|NATIVE_PARTIAL_OOM / S0|d1d9435|UNKNOWN|UNKNOWN / UNKNOWN|UNKNOWN|INCOMPLETE_NO_TERMINAL_TOTAL|
|2026-10-19|ALPHA_C|NATIVE_FULL_FEED_INCOMPLETE_EXPORT / S0|bd1aa69|UNKNOWN|93.23 / OBSERVED_NATIVE_CALLBACK_LOWER_BOUND|UNKNOWN|INCOMPLETE_NO_TERMINAL_TOTAL|
|2026-10-20|CHOP_CARRY_NATIVE|FULL_NATIVE_DURABLE_PARTIAL_AUDIT / S0|fdcefd633b1e611135d2a2573dbc6ad8|205.42|99.85 / NATIVE_CALLBACK_MARKED|11,256.90|ECONOMIC_FAIL_AUDIT_LIMITED|
|2026-10-20|CORRIDOR_R2_OOM|NATIVE_PARTIAL_OOM / S0|f2ebdce|UNKNOWN|77.92 / PROVISIONAL_PREFIX_CALLBACK_LOWER_BOUND|UNKNOWN|FULL_TOTAL_DD_FEES_UNKNOWN|
|2026-10-20|CORRIDOR_R2_REPEAT|NATIVE_PARTIAL_OWNER_STOP / S0|e3eaf77|UNKNOWN|UNKNOWN / UNKNOWN|UNKNOWN|FULL_TOTAL_DD_FEES_UNKNOWN|
|2026-10-20|CORRIDOR_R2_CORRECTED|NATIVE_PARTIAL_OWNER_STOP / S0|dbd18fa|UNKNOWN|77.47 / PROVISIONAL_PREFIX_CALLBACK_LOWER_BOUND|UNKNOWN|FULL_TOTAL_DD_FEES_UNKNOWN|
|2026-10-20|S0_EXACT_REPRODUCTION|FULL_NATIVE_24M_REPRODUCTION / selectedS0 Oct18|75ffc9c69e9d79c4da4cd0614634a3ee|6,077,107.24|66.26 / SETTLED_NATIVE_RECEIPT|945,927.74|EXACT_REPRODUCTION_PASS|
|2026-10-22|S0_MANAGE_M1|FULL_NATIVE_24M / exactS0 settled6077107.23887483|efa7c723d9f0c5c1bdc8f491abf12921|2,615,745.21|58.77 / SETTLED_NATIVE_RECEIPT|710,655.27|FAIL_BOTH_THRESHOLDS_STOP_2_OF_4|
|2026-10-22|S0_MANAGE_M2|FULL_NATIVE_24M / exactS0 settled6077107.23887483|efa7c723d9f0c5c1bdc8f491abf12921|2,044,863.63|70.64 / SETTLED_NATIVE_RECEIPT|614,360.75|FAIL_BOTH_THRESHOLDS_STOP_2_OF_4|

## Прогнозы, каталоги и проверки сохранённых данных

Для всех строк TOTAL/DD/fees не оценивались. Полные методы/изменения/метрики/контрпримеры — в соседних CSV/JSON; правильные losses не заменяются hit-rate или денежным результатом.

|Дата|Опыт|Что реально сделано / итог|Источник|
|---|---|---|---|
|2026-10-19|ADVERSE50_SCREEN|WITHDRAWN_BEFORE_NATIVE: 15crosses eachpartition,7positive8negative payoff signs; normalizedsums-2.504182%/-1.069702% BEFOREfees; classification80/86.7%negative insufficient|[stats-adverse-payoff-bound.md](../chop-pair-113/stats-adverse-payoff-bound.md)|
|2026-10-20|CORRIDOR_R0|ANALYSIS_NOT_ACTION_VALUE: 37.1302%alpha states needchange;15.5070%heldstates infeasible; no alternativefill/equity|[README.md](../sol-corridor-113/README.md)|
|2026-10-20|FAST_RND_simple|NO_ADDED_DIAGNOSTIC_INFORMATION: None beats prior+simple; no policy/OOF/native follow-up|[recognizer-comparison-results.md](../fast-rnd-20261020/recognizer-comparison-results.md)|
|2026-10-20|FAST_RND_stumpy|NO_ADDED_DIAGNOSTIC_INFORMATION: None beats prior+simple; no policy/OOF/native follow-up|[recognizer-comparison-results.md](../fast-rnd-20261020/recognizer-comparison-results.md)|
|2026-10-20|FAST_RND_minirocket|NO_ADDED_DIAGNOSTIC_INFORMATION: None beats prior+simple; no policy/OOF/native follow-up|[recognizer-comparison-results.md](../fast-rnd-20261020/recognizer-comparison-results.md)|
|2026-10-20|FAST_RND_rdst|NO_ADDED_DIAGNOSTIC_INFORMATION: None beats prior+simple; no policy/OOF/native follow-up|[recognizer-comparison-results.md](../fast-rnd-20261020/recognizer-comparison-results.md)|
|2026-10-20|FAST_RND_cnn_seeds7_42|NO_ADDED_DIAGNOSTIC_INFORMATION: None beats prior+simple; no policy/OOF/native follow-up|[recognizer-comparison-results.md](../fast-rnd-20261020/recognizer-comparison-results.md)|
|2026-10-20|FAST_RND_RESOURCE_ATTEMPTS|TECHNICAL_FAILURES_RETAINED_THEN_FIXED_RECIPE_COMPLETED: FailedMiniRocket/probes are not independent scientific variants; exactattemptcount not inferred|[minirocket-memory-r2-completion.md](../fast-rnd-20261020/minirocket-memory-r2-completion.md)|
|2026-10-21|EV02_SUPPORT|BTC_SUPPORT_PASS_SOL_FAIL: BTC50train/80check,15/21blocks; SOL5/6valid,0positiveCHECK; ordinarybranchavailabilityUNKNOWN|[ev02-result.md](../btc-sol-event-risk-20261021/ev02-result.md)|
|2026-10-21|EV03_METHODS|NO_ADDED_INFORMATION_STOP: LLrule.65098/logistic.72097/STUMPY.70793 allworse; no economicpolicy/native|[ev03-result.md](../btc-sol-event-risk-20261021/ev03-result.md)|
|2026-10-21|H24_CHECK_raw_control|FORECAST_GATE_FAIL: Allcalibratedworseprior; CNNactionable0; CNNvscontrolCIincludes0|[findings.md](../forecast-independent-20261021/findings.md)|
|2026-10-21|H24_CHECK_stumpy|FORECAST_GATE_FAIL: Allcalibratedworseprior; CNNactionable0; CNNvscontrolCIincludes0|[findings.md](../forecast-independent-20261021/findings.md)|
|2026-10-21|H24_CHECK_minirocket|FORECAST_GATE_FAIL: Allcalibratedworseprior; CNNactionable0; CNNvscontrolCIincludes0|[findings.md](../forecast-independent-20261021/findings.md)|
|2026-10-21|H24_CHECK_rdst|FORECAST_GATE_FAIL: Allcalibratedworseprior; CNNactionable0; CNNvscontrolCIincludes0|[findings.md](../forecast-independent-20261021/findings.md)|
|2026-10-21|H24_CHECK_cnn|FORECAST_GATE_FAIL: Allcalibratedworseprior; CNNactionable0; CNNvscontrolCIincludes0|[findings.md](../forecast-independent-20261021/findings.md)|
|2026-10-21|AI_A_UTC_INVALID|QUARANTINED: 102fit timezone-invalidattempt quarantined; no qualityused|[findings.md](../ai-cycle-20261021-01/findings.md)|
|2026-10-21|AI_A_UTC_VALID|NO_SKILL: joint750numericCatBoost6heads allNO_SKILL despiteweaklinearbeaten|[findings.md](../ai-cycle-20261021-01/findings.md)|
|2026-10-21|AI_B_KRONOS|UNASSESSED_RESOURCE: 96pilotpaths/6assetgenerations;projected823.97min>budget, fullqualityUNKNOWN|[findings.md](../ai-cycle-20261021-01/findings.md)|
|2026-10-21|AI_C_TS2VEC|NO_SKILL: ownerraisedbudget90→120min;6encoders36heads,all6NO_SKILL|[findings.md](../ai-cycle-20261021-01/findings.md)|
|2026-10-21..22|PATTERN_BASE|NO_SKILL_CHECK_NATIVE_NOT_ADMITTED: full-historyTCN/Kronosprojection/CNN+18CBheads,allretrievalfail; originalCNNQlongweakCIcross0|[findings.md](../btc-pattern-pilot-m2-20261021/findings.md)|
|2026-10-21..22|PATTERN_4H_CONTROL|NO_SKILL_CHECK_NATIVE_NOT_ADMITTED: 18additionalCatBoostheads; no incremental2TFadvantage|[findings.md](../btc-pattern-pilot-m2-20261021/findings.md)|
|2026-10-21..22|PATTERN_METRIC_OFF|NO_SKILL_CHECK_NATIVE_NOT_ADMITTED: metriccoefficient0 only; no forecastgatepass|[findings.md](../btc-pattern-pilot-m2-20261021/findings.md)|
|2026-10-21..22|PATTERN_Q_PRIOR_INIT|NO_SKILL_CHECK_NATIVE_NOT_ADMITTED: knownsyntheticQrepairpasses; marketDsignificantlyworsevsoriginalCNN|[findings.md](../btc-pattern-pilot-m2-20261021/findings.md)|
|2026-10-22|FORM00|NO_SKILL: corrected710invalidneighbors/support80h/completecanonicaltruthgates; stillNO_SKILL|[form00-findings.md](../btc-pattern-pilot-m2-20261021/form-signal-20261022/form00-findings.md)|
|2026-10-22|FORM01_CONTEXT|NO_SKILL: context-onlyshortQsignificantlyworseoriginalCNN; nooverallgate|[form01-02-findings.md](../btc-pattern-pilot-m2-20261021/form-signal-20261022/form01-02-findings.md)|
|2026-10-22|FORM02_FLAT780|NO_SKILL: noaveragingnumeric780vs204;pairedCIsallinclude0|[form01-02-findings.md](../btc-pattern-pilot-m2-20261021/form-signal-20261022/form01-02-findings.md)|
|2026-10-22|FORM03_SPATIAL|NO_SKILL: 2x8poolingpreservespositionbutalloverallNO_SKILL|[form-findings.md](../btc-pattern-pilot-m2-20261021/form-signal-20261022/form-findings.md)|
|2026-10-22|LLM_INAPP|NO_DEFINED_INCREMENTAL_IMPROVEMENT: PvspriorTPslightlybetter,SLworse; allprimary14dCIsinclude0;noincrementalbundleedge|[REPORT.md](../btc-pattern-pilot-m2-20261021/inapp-chatgpt-protocol-20261022/REPORT.md)|
|2026-10-22|EVENT_E1|NO_DEFINED_INCREMENTAL_IMPROVEMENT: phaseTP+1.18%/SL+0.77%worseprior;6primaryCIsinclude0;E2/E3skipped|[REPORT.md](../btc-pattern-pilot-m2-20261021/event-e1-20261022/REPORT.md)|
|2026-10-22|EVENT_D90|NO_DEFINED_INCREMENTAL_IMPROVEMENT: botherrorsworsepriorinall3folds;correctedcausalpoolnotearlierE1pool|[REPORT.md](../btc-pattern-pilot-m2-20261021/event-d90-20261022/REPORT.md)|
|2026-10-22|FULLWAVE_A|CATALOGUE_ONLY_FORECAST_BLOCKED: F1/F2pastindependentcycles2/5 below6; forecastingblocked; 27overlappingfullwavesnot27IIDcycles|[findings.md](../btc-pattern-pilot-m2-20261021/fullwave-stage-a-20261022/run/findings.md)|
|2026-10-22|LLM_ASTRA_RANK|NO_DEFINED_INCREMENTAL_IMPROVEMENT: noCI-backedwinner;TPnearequalnumericD1;4fallbacks~40%TPand58%SLgainvsnumeric8|[findings.md](../btc-pattern-pilot-m2-20261021/astra-rank-20261022/findings.md)|
|2026-10-22|PATTERN_PIPELINE_AUDIT|DEFECTS_IDENTIFIED_CORRECTED_IN_FORM00: knownsyntheticfailure/near-ties do not establishmarketedge; not additionalnative|[findings.md](../btc-pattern-pilot-m2-20261021/pipeline-audit-20261022/findings.md)|
|2026-10-22|EVENT_PRICE_VOLUME_AUDIT|ANALYSIS_ONLY: E1waslateractualtrial; thisproposalnotanotherforecastengine|[REPORT.md](../btc-pattern-pilot-m2-20261021/event-based-research-20261022/REPORT.md)|

## Старая lineage — не новые опыты этой недели

|Дата|Опыт|Тип / контроль|Source или publication*|TOTAL|DD % / метод|Fees|Статус|
|---|---|---|---|---:|---|---:|---|
|2026-10-09|HIST_CAP30M|HISTORICAL_FULL_NATIVE / Selective cap10m 3747041.97080334|d7d18cd|5,146,884.96|62.31 / NATIVE_CASH|1,144,089.97|OUTSIDE_WEEK_REUSED|
|2026-10-11|HIST_V3|HISTORICAL_FULL_NATIVE / cap30m 5146884.95718200|a9cbb737a5239d10b9ffcb97d55f9979|5,437,208.57|67.29 / NATIVE_CALLBACK_MARKED|1,091,093.08|OUTSIDE_WEEK_REUSED|
|2026-10-11|HIST_B25|HISTORICAL_FULL_NATIVE / V3 5437208.56951095|250020911a1ac671740cd3346c27f023|2,394,463.52|46.48 / NATIVE_CALLBACK_MARKED|534,532.86|OUTSIDE_WEEK_REUSED|
|2026-10-11|HIST_S10_15|HISTORICAL_FULL_NATIVE / V3 5437208.56951095|250020911a1ac671740cd3346c27f023|1,147,671.51|62.03 / NATIVE_CALLBACK_MARKED|385,186.53|OUTSIDE_WEEK_REUSED|
|2026-10-11|HIST_R2|HISTORICAL_FULL_NATIVE / V3 5437208.56951095|250020911a1ac671740cd3346c27f023|2,248,382.68|92.13 / NATIVE_CALLBACK_MARKED|530,522.98|OUTSIDE_WEEK_REUSED|
|2026-10-11|HIST_T3|HISTORICAL_FULL_NATIVE / V3 5437208.56951095|250020911a1ac671740cd3346c27f023|466,727.72|92.78 / NATIVE_CALLBACK_MARKED|605,085.68|OUTSIDE_WEEK_REUSED|
|2026-10-13 UTC|HIST_H1|HISTORICAL_FULL_NATIVE / V3 5437208.56951095|94e0e6cecbdef93ed3b1422ecfdffd26d|190,593.97|62.60 / NATIVE_CALLBACK_MARKED|65,995.57|OUTSIDE_WEEK_REUSED|
|2026-10-13 UTC|HIST_B1|HISTORICAL_FULL_NATIVE / V3 5437208.56951095|94e0e6cecbdef93ed3b1422ecfdffd26d|1,387,384.72|64.64 / NATIVE_CALLBACK_MARKED|511,337.13|OUTSIDE_WEEK_REUSED|
|BEFORE_2026-10-15|HIST_BTC20|HISTORICAL_FULL_NATIVE / cap30m 5146884.95718200|UNKNOWN|3,806,180.16|66.44 / NATIVE_CALLBACK_MARKED|UNKNOWN|OUTSIDE_WEEK_REUSED|
|2026-10-21..22|NOT_RUN_RECIPES|NOT_EXECUTED / relevantpriorrecipes|documented cancellation/gate dec|UNKNOWN|UNKNOWN / NOT_EVALUATED|UNKNOWN|NOT_RUN_NOT_EVIDENCE|

## Что помогало и что вредило

1. **Исправление исполнения и ценового reference помогло.** PLANREF дал TOTAL 6,005,487.81; добавление native TP IOC — 6,077,107.24 (+71,619.43), callback DD снизился с 70.47% до 66.32%. Прирост к старому V3 — 639,898.67. Blended split терял один календарный вход и прибыль. При этом нового дефекта исполнения, который обещал бы DD≤50%, не установлено.

2. **Замена исходного SOL на постоянную страховку разрушала прибыль.** BTC-only дал 280,748.52 против S0 6,077,107.24; постоянный SOL cover — 21.8–26.1 тыс.; I25 — около 8 тыс., I33 — около 2 тыс. У исходного SOL прибыльны 22 из 26 интервалов, net fill diagnostic +678,661.21. Это вклад в общей траектории капитала, а не самостоятельный SOL ROI: размеры будущих позиций меняются вместе с капиталом.

3. **Более сильное сокращение риска не обеспечивает меньшую DD.** cap50: DD 58.02%, TOTAL 3.314 млн; M1: 58.77%, 2.616 млн; M2: 70.64%, 2.045 млн. Старый V3 B25 прошёл собственный DD порог (46.48%), но TOTAL упал до 2.394 млн; правило дополнительно вдвое уменьшало будущие BTC entry multipliers. Это не готовая адаптация точного S0.

4. **Ловить убыточные контексты недостаточно для прибыльного stop.** В ADVERSE50 при пороге 1.9175212144% и срезании 50% доля negative contexts составила 80%/86.7%, но оптимистичный endpoint price payoff bound — −2.504182%/−1.069702% до затрат (7 положительных и 8 отрицательных эффектов в каждой части). Это нормированные price-context суммы, не native PnL. DD≥25% + собственный adverse≥2% — другой предикат; этот аналог не доказывает его эффективность.

5. **BTC reduction может оставить опасный несбалансированный SOL, но полезный SOL тоже восстанавливается.** На раннем худшем срезе M2 BTC short 0.173 имел положительный UPnL, SOL long 773.5 — отрицательный; ранний худший S0 также сочетал убыток SOL с прибылью BTC. У M2 не было fresh-cross claim для раннего SOL1. M1 снизил раннюю DD до 46.59%, но максимум переместился в май–август 2026 (58.77%). Срезы состояний не изолируют причинный эффект одной сделки.

6. **SOL-фильтр не решает остаточный BTC-only риск.** Исходная DD октября–ноября 2025 — 55.10%, оба endpoint BTC-only: native UPnL изменился с +225,132 до −938,216 при росте cash на 12,589. В апреле–июне 2025 DD 59.84% сочетала cash loss 407,280 с UPnL loss 140,386. SOL-only veto не может непосредственно ограничить эти состояния.

7. **AI/LLM пока не дали допущенную денежную политику.** FAST prior LL 1.100586 лучше всех; H24 prior лучше всех calibrated methods; A/C — NO_SKILL; CNN Q-long CI включает ноль; FORM/E1/D90 не прошли gate. Astra TP близок numeric D1, paired CI включают ноль. Эти отрицательные выводы относятся к выполненным рецептам; Kronos B остался UNASSESSED_RESOURCE, а не доказанно плохим по качеству.

ALPHA-C и corridor corrected нельзя выдавать за завершённые экономические варианты: terminal TOTAL/fees неизвестны. Но сохранённые prefix DD≥93.23% и ≥77.47% уже превышают 50%; неизвестный терминальный результат не отменяет наблюдавшуюся просадку. Две технические startup-попытки carry/corridor отдельно внесены в CSV/JSON, без дополнительного экономического варианта. У H1/B1 receipt launch UTC 13 октября имеет приоритет над Oct14 в имени job.

## Минимальная новая гипотеза и предел рекомендации

**Новый кандидат не выбран и не допущен.** Условная гипотеза: если защитное сокращение BTC отдельно обосновано, при открытом SOL сокращать SOL лишь пропорционально фактически исполненному BTC trim. Один фиксированный target за цикл; без новых входов, моделей, прав, continuous rebalance или второго PnL-движка. Это вопрос о рассогласовании остатков, а не рекомендация повторить исправленный M1.

За механизм: на раннем худшем M2 BTC short 0.173 с положительным UPnL против SOL long 773.5 с отрицательным; carry закончил убыточным остатком 7,000 SOL. Против: S0 законно сохраняет прибыльный SOL после BTC flat, 22 из 26 SOL-интервалов прибыльны; BTC-only теряет 95.38% TOTAL, cap50 — 45.46%. Сопряжённое сокращение может снова отнять SOL alpha. BTC-only DD 55.10% этим прямо не исправляется, а M1/M2 уже потеряли большую часть прибыли. Ожидаемые TOTAL/DD — **UNKNOWN**; достижения 50/90 не заявляются.

Минимальный будущий gate — по сохранённым actual fill/authorization состояниям отличить остаток, созданный защитным BTC trim, от законной исходной SOL-позиции и учесть прибыльные восстановления. Нет доступного причинного состояния или свидетельства бережного действия — отказ от гипотезы. Документ ничего дополнительно не запускает.

DD level 25% + adverse 2% отдельно находится у root/stats **under review** и здесь не выбран. Аналог ADVERSE50 уже показал отрицательный оптимистичный endpoint payoff при хорошей классификации; ранний SOL1 впоследствии дал +2,330.72 без funding. Нельзя объявлять 2% новым edge или скрывать цену отказа от восстановления.

Не повторять как новые идеи: постоянный SOL cover/insurance, blanket SOL cap, old B25 с иным future sizing, простой adverse stop только из доли пойманных losers, continuous cushion/corridor и M1/M2 fresh cross. Нужен отличающийся причинный механизм и свидетельство сохранения полезных profitable fallbacks. Root выбирает ONE после инвентаря/единственного precheck; разрешения на native нет.

Исторические native сохраняют NOT_FAITHFUL_DIAGNOSTIC: quote proxy/L2/slippage/historical margin не квалифицированы. Signed funding UNKNOWN; условный OHLC — не tick cap. Переносить суммы на Hyperliquid/live оснований нет. Root REPORT/ops/Project и source/pilot/services не изменены.
