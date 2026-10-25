# Следующий шаг: A0 — сохранить исходное право BTC-добора

25.10.2026. Анализ выполнен без nativeдвижков, нового торгового кода, обучения или загрузок. Старые7/7 и11/12бюджеты остаются закрыты. Новое предложение прошло независимую проверку **для запроса согласования**, а не для выполнения.

## Что проверено

Исследованы все16 фактических B2/F0активаций(11F0/5B2),15инвалидаций и8настоящихSOLTP; primaryстресс-проверка — первыйTP каждой из4активаций, sensitivity30дней не заменяет заранее заданныйprimary90дней. Фактические native postTP/preBTCdebt состояния и coherentpeak сопоставлены поtradeID. Новый candidatewealth/ROI не моделировался.

| После первогоSOLTP | Stress90 сexitfees/fundingallowance | Headroom до50%отpeak | Только стресс-предпосылка |
|---|---:|---:|---|
| Sep14 |1618.36|6067.17|PASS|
| Oct25 |3431.56|4554.01|PASS|
| Dec26 |2359.90|828.87|FAIL|
| Jan7 |1516.08|3046.48|PASS|

Эти числа не дают разрешения удерживать будущий uncutBTC: после первых реальных cuts дальнейшая equityтраектория уже другая. Нужны собственныйactualnativecash, margin и новые fills. ДляOct25 гипотеза «подождать однуH4 и риск исчезнет» не сработала:481последовательных quote не пересеклиboundary; riskOFFпоexpiry позже nextH4+60sdeadline. A1 — замена fixedcoverage на stress/residualконтракт — пока не выбран и не реализован.

## Проверяемая возможность раннего капитала

В4 случаях послеriskOFF оставался исходный second-child: .488/.575/.440/.375BTC(Sep14/Oct10/Oct12/Nov16). Старый cancelACK известен доriskOFF во всех4. НаriskOFF+60s тотжеparent ещё держитBTC, ordinaryBTC TP/exit не было; первыеchildren заполнены полностью. В3 случаях исходныйpost-onlylimit не пересекаетquote. Sep14BUY60207.5 пересекаетask59638.9: толькоWAIT/deny, без сменыцены/TIF/taker.

Это реальная структурная предпосылка дляA0, а не доказательство прибыли. Доступностьprospectiveштатногоmargingate остаётсяUNKNOWN до новой nativeпроверки. ЭкспортIM/MM0 не заменяет маржу. При будущей реализации nativeUNKNOWN/отказ блокируют увеличение.

Дополнительно исправлена важная интерпретация исходника: realU `_split_check` немедленно возвращается при `_md_enabled()`. Genericdeadline/day-stop не является expiryэтогоправа. Реальныеguards — ordinaryTP, parentend/flip/пауза/ликвидация и собственное состояниеrealU. Первоначальная ошибочная интерпретация сохранена какsuperseded, не скрыта.

## Конкретный предлагаемый опыт

**A0:** послеriskOFF разрешить не более одной новойnativepost-onlyGTC по остатку **исходногоsecond-budget**, только при knowncancelACK/нетдругогоincrease/исходныйparentжив/ordinaryTPещёнебыло/свежийquote/штатныйmarginPASS. Не возвращать закрытыйBTC, не переносить недоисполненныйfirstIOC воsecond, не создаватьновыйparent. Capсчитатьот неизменённого pre-releaseabsoluteceiling; не переякориватьот уже поднятогоcap и не накапливатьgrantнаожидающихquote. SOLTP/STOP/debt/rearm не менять.

Предлагаемый BTCanchor длянового matchedопыта — R2LEGACY_QrealU: он сохраняет исходнуюsizingфункцию и имеет отдельный лучшийархивныйрезультат, чемCLEAN_Q. Это исследовательскийвыбор, не объявленныйwinner. R2paired пока запрещён текущимкодом и обязан пройтиновыйengineeringgate. ВоC0/A0 однозначноB2_F0, одинаковыйcore/source/feed; различается толькоA0flag. СвежийR2OFF отделяет изменениеcore от эффектахеджа. СтарыйR3OFF не подставляетсяв matchedсравнение.

Протоколпредлагает isolatedVPSimplementation от06f7577, **до6nativefixtures≤48h и до3prefixпопытокR2OFF→C0→A0** на[2024-09-01,2025-01-15)UTC; ошибкивходятвлимиты. Full/training/newdownloads0. Это ещё **НЕ УТВЕРЖДЕНО**; вопрос владельцу отправлен отдельно. Nativegate критически должен использовать настоящийstockmargin, без прежнегоfixturetierbypass.

A0сравнивается сmatchedC0 после всех nativefees/funding. Нужны приростTOTAL выше заранее заданного incrementalcosthurdle и settled+eventDD≤50%/нехужеC0; all136UTCdailyES20, actualownership/3TP/accounting/zeroLiq — отдельныегейты. Отсутствиефактическихrelease→механизмNOT_TESTED. Любойпровал не разрешает новыеавтоматическиепопытки илиfull.

Глобальные цели не изменяются:≥70%netS0 какintermediate, затем≥90%; TOTAL4256975.067212381/5470396.514987347USDT приsettled+eventDD≤50% иzeroLiq. Улучшенныйпрефикс не является доказательством этихдвухлетнихцелей. Пилот/production не трогаются.

Точные условия/границы: A0_CONTRACT_PROPOSED_RU.md и NATIVE_PROTOCOL_PROPOSED_RU.md. Воспроизводимые данные/ошибки/валидации — analysis/. Independentreview P0/P1open0; согласованиебюджета остаётся необходимым следующимшагом.
