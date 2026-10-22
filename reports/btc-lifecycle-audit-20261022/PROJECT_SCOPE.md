## Дополнение — BTC lifecycle audit 22.10.2026

Завершён ANALYSIS ONLY по exactS0: entry/split/PLANREF, post-entry priceMAE,3TP/zero-allocations/nativefills/SOLrights, actualREGIME/TRAIL/reentry, applicable17-row experiment matrix и ограниченный поиск улучшений. ИсходныеcoreSHA сверены с scientific75ffc9c69e9d79c4da4cd0614634a3eeba48d716; native621fillaudit SHAe7854784...verified.

105BTC (53L/52S),210entryfills/155reductions. Exactzero-price reductions0; совпадений сfirstfill/completion0.45passiveplans omit76zeroallocations, не76 мгновенныхfills.73genericfallback всеprice-/diagnosticnetpositive, median23ч34мин; zeroformulamappingFULL UNKNOWN.13positiveTP2IOC через60с послеEARLY_TPcompletion(2–72минпослепервоговхода),7netnegative, все13sum−1817,86exfunding; entireTPIOCcomparison+71619,43TOTAL. Не удалять убыточныеfillsпостфактум.

FirsthourMAE median profitable0,2132%/losing0,2450%, распределенияперекрываются;15m profitable0,1251%>losing0,0825%.24h цензура17/21, completeonlyмедианы1,0269/0,9937. Wholecurrentnativeavg winnerMAEp903,2804/max7,7683%. Фиксированный lossSL отсутствует; dailytrail3p.p.армитсяпослеbest_f>3%;REGIME48/TRAIL2конечныхинтервала. Не выдавать MAE distribution за новыеSLresults.

Структурная гипотеза: daily-CLOSE waveMFE против 1m-CLOSE TPexecution. Принудительно3positiveTP/fee-floor — экономическое изменение, неbugfix; старыйfloorTOTAL−725275 приfees−35026, selectivealreadyinS0. EMAconfirmationB1/intradaytrailT3/permanentcutM1M2 не решили цель. Новое превосходствоTP/SLUNKNOWN.

Предложено: один all105decision/fill/TP-prefix census→один fixed jointTP/SLprecheck (completedwavepostentryresolution/remainingBTCprofitgiveback), затемfreezeONEpolicy. Только послеownerconsent≤2native: candidate, repeatлишьесли50/90PASS; noS0rerun/grid. Adaptiveentryoffset отдельнаяпоследующаягипотеза, не смешивать. Ниprecheckнаrawpaths,ниэтиnativeзапускинезапущены.

Готово: sourceaudit+105CSV+JSON+17-rowexperimentmatrix+primarysources+REPORT, root14count/arithmetic/scopechecksPASS. Торговойкод/пилот/production/режим/ордеранеизменялись. Новыхnative/backtest/replay/training/forecast/optimizer0. GoalDD<=50/TOTAL>=5470396.514987347 НЕдостигнута/необъявлена. Аналитическая задача закрыта, будущиеизмененияожидаютсогласования.

[Отчёт и артефакты](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/btc-lifecycle-audit-20261022).
