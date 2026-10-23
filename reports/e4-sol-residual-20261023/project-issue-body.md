# E4 + остаточный SOL — исследование завершено,50/90 НЕ достигнуто

Владелец поручил реализовать и проверить E4 с защитой остаточногоSOLпослеBTCflat, сохранив прибыльныеBTCfallback иordinaryBTC-TP→SOLrights. Пакет выполнен в isolatedresearchветках. **Done означает завершение исследования с отрицательным экономическим итогом. Новая стратегия в пилот/production не внедрялась, сервисы/ключи/ордера/deployment не менялись.**

[Полный отчёт/JSON/CSV](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/e4-sol-residual-20261023). Sourceoriginal[5bb4939](https://github.com/VF78/coinmaster/commit/5bb4939c2adbcfcabf835b9e2ed97634f6fba4da), corrected[bae093f](https://github.com/VF78/coinmaster/commit/bae093f9549bb523ae55e1c4e4676431bef8a889); exactGitHubrefsPASS. [Предыдущий пакет](https://github.com/VF78/coinmaster/tree/4f54c2cbf2821b0ed05cedd30c46d9e866304925/reports/b-50-90-next-20261023) сохранён.

Acceptance неизменен: globalsettledminuteDD≤50%,TOTAL≥5470396.514987347(≥90%чистойприбылиS0),0liquidations; затемMAX_TOTAL. [2024-09-01,2026-09-01),seed10000USDT,RESERVE0/DPoff; тежеBybit/fees/funding/margin/nativeexecution. S0/E4 не пересчитывались.

## Выполненные задачи

- [x] R00: exact source/data/control pins, отдельные canonicalVPScheckout/ветки, протокол до запуска и Project readback; старые результаты сохранены.
- [x] R01: defaultOFF residual/minuteflags; подтверждённый nativeBTCflat, прежние DD40/adverseSOL2%/half50%, одинnativeSOLriskexecutor, frozenremaining/ACK/cancel/latefill/addblock.
- [x] R02: focusednative/tests+independentreview.137initialPASS недостаточно покрыли дробныйBTCflat: найден P1 floatdust, добавлен faithfulreal fractional split→TP→SOLcarryfixture. Финальный144PASS+independentcorrectionGO, noopenP1. Старые findings не удалены.
- [x] R03: новыйP0 EXACТXS по21ownerchecks и independentfulltrace/fills/cash/funding/fees; sourceflagsOFFпуть сохранён. S0/E4 не пересчитывались.
- [x] R04: R1H1 иR2minute отдельнымиnativeengine/journal, полные1,051,199receiptsкаждый,0gaps/0liq/terminalflat; деньги валидны, R1policyошибка явно квалифицирована.
- [x] R05: до4-горасчёта оформлена одна необходимая корректировка новогоflatpredicate вnativeквантах, безepsilon/измененияBTCdomain/fallback/rights/экономическихпараметров. Четвёртыйслот переиспользован дляR2CcorrectedprimaryM1, sameconfigR2. Freshrepeatнепроводился;ниодногопроходящего50/90нет, бюджетзакрыт4/4.
- [x] R06: all4independentsaved-outputauditsPASS,56verifierhashes/166rootQA/finalreportpeerreviewPASS. JSON/CSVсTOTAL/ROI/DD/assetfill-net/maker-takerturnover+fees/bridge,40globalDDepisodes/96months/430closedcycles/actualriskfills, checkpoint/publication/Projectreadback.

ЗависимостиR00→R01→R02→R03→R04→R05→R06 выполнены. Полныхфизическихengine4/4,active0/reserved0, launchespermanentlyclosed. Никакихскрытыхretry/сеток/новыхмоделей/второгодвижка.

| Recipe | TOTAL USDT | S0profitretention% | GlobalDD% | Итог |
|---|---:|---:|---:|---|
| S0archive |6077107.23887483|100|66.2569148647|контрольнепересчитывался|
| E4archive |5631617.35953723|92.6572934712|57.5854104596|контрольнепересчитывался|
| XS/P0 |5406345.11636863|88.9442843830|58.9474368842|EXACTXSparity|
| R1 |5406345.11636863|88.9442843830|58.9474368842|Janfalse-negative изdomainfloatdust|
| R2 |2610652.32119763|42.8647824870|61.7586863916|частичноактивныйresidualguard,экономическийFAIL|
| R2Ccorrected |2610652.32119763|42.8647824870|61.7586863916|correctnativequantumguard,экономическийFAIL|

## Проверенные выводы

R1Janactualentry4.552+4.553minusTP5.237+1.934+1.934далdomain4.44e−16BTCприnative0lots. Новыйpredicateисправленчерезреальныйsize_incrementONLYпристрогомnativeflat/priorentry/closedparent/noownedwork;domainостатокнепереписан. R2 доисправления ужеимел2residualtrigger;необъявлятьегоцеликомнеактивным. R2CexactR2поfulltrace/nativefilledorders/cash/funding/4triggers/15riskfills: экономическийdelta0.

ЗащитафактическиуменьшилаOct3DDдо49.9363%иJan13SOL-onlyдо49.4068%.4decisions/15childfills/13500SOL,2residual2mixed,нетпозднихдоборовдоflat. НоJanSOL-cycleперешёлс+4502.1215до−22401.9375fillnetexfunding:сокращениепотерялочастьотскока. BTCcalendar/pricesall337fillsсохранены,292qtyизмененыиз-задругогокапиталаприпрежнихправилах. НоваяglobalDDJuly6→Aug19,6259005.7918654→2393526.03363737;наконцахBTC-only. SOLзащитанеустраняетэтотBTCпуть.

S0сохранён,новыйвариантдляdeployНЕвыбран. Следующиепроверки/измененияпилота—толькопосленовогосогласования. Цель50/90неподменяетсялокальнымулучшениемдвухпросадок. Текущеездоровьепилотаэтимofflineпакетомнепроверялось.

BenchmarkNOT_FAITHFUL_DIAGNOSTIC/1mCLOSEsyntheticquotes;settledDDнеtick/intraminute/liveгарантия,историянеfreshOOS. SignedassetfundingUNKNOWN/bridgeunallocated. P0resourcewrapperwarningсохранёнбезэкономическогоповтора;последующиеactualnativechildexit0/RSSUNKNOWN. ПродуктовыеправкитолькоcanonicalVPS,Macreadonlyexecutionmirror. Прежнееbodyсохраненовproject-previous-issue.json.
