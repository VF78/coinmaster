# E4/C1: единый план и текущий результат

Статус: R&D активен, историческая попытка Q завершена (1/8), следующий R, live выключен. Основание — прямое указание владельца принять CODEX_E4_C1_FAST_PILOT_2026-10-28.md за основной план; SHA и полномочия закреплены в manifest.json. Это новая кампания, не продолжение закрытого C2 и не расход MethodA19.

## Что известно

C1 уже является E4+residual cut/restore. E4 вернул своевременное участие через закрытую H4 после REGIME при сохранённых D1 EMA34/ATR и дал5631617.35953723, settledDD57.58541046%. C1 уменьшил DD до51.80315157406654834417870238%, но TOTAL4388613.38225343. Комбинация нужной прибыли и допуска пока не получена. Уровни архива — ARCHIVE_SETTLED_REFERENCE; coherent eventDD и signed funding ещёUNKNOWN.

Цена C1 — не только комиссии:9cuts/3restores/6revoked credits,12interventionfills fees30498.04072762. Цена трёх пар cut→restore385696.0245 безfees, главным образом ноябрьBTC; эти суммы нельзя прибавлять кTOTAL. Ранний SOL cashflow влияет на будущий BTCsizing. Прежний C2bundle60%+completion+rearm остаётся отрицательным/непроверенным; сейчас другой DDдопуск и отдельные абляции.

Цель — около5631617 или выше, рабочий унаследованный нижний ориентир5470396.514987347; это не новый точный owner%-допуск. Для pilot candidate обе измеренные DD≤.5180315157406654834417870238; strict50% продолжается отдельно. Среди корректных вариантов максимизируемTOTAL, не выбираем меньшую прибыль ради меньшейDD. LegacyTPzero/reference и SOLalpha в этом MVP сохраняются и называются честно.

## Новый фактический результат Q

Один полный native запуск, actual child exit 0: TOTAL **4 800 260.20248922**, settled и coherent event DD **51.80315157406654834417870238%**. Прирост к C1 **411 646.82023579**, но до рабочего минимума не хватает **670 136.312498127**; Q не выбран для live. До первого BTC cut 06.06.2025 совпали 225 fills и 400881 receipts. Получены 7 cuts / 3 restores / 4 revokes; intervention fees 12369.60926835.

Независимая сверка фактических native cash transitions: seed10000 + fill cash deltas4738172.41324906 + signed funding52087.78924016 = TOTAL, residual0E-8. Проверены 1782 изменения cash без пропусков; retrospective settled copies исключены из мутаций. Исходный Q экспорт последних двух positions сохранён как некорректный; полная отдельная lifecycle PnL-сумма UNKNOWN, не подменяется cash-сверкой. Подробности и 24 месяца — evidence/Q-analysis.json и Q-*.

Для R узко исправлен только экспорт всех native lifecycle snapshots и signed funding, стратегия не менялась. Source2e90a6c, peer0P0/P1; R configc4b53b97. Повтор Q не нужен. Следующий шаг — frozen preflight R и один запуск в том же бюджете.

## Выполнение по порядку

1. Восстановить exactC1final78cb85a/E4bd04, config405ab/data7ab5/policyc954. Полный C1config уже извлечён из фактического отчёта, hash совпал. Новая isolatedVPSветкаcodex/e4-c1-fast-pilot-20261028; MethodA не cherry-pick.
2. Сохранённая выборка9групп/90H4 уже собрана в evidence/. R не доказанноno-op: есть более ранние price/DDкандидаты. Сильнейший — Jan13 20:00→20:01; численныеmargin/free/gross проходят; source-bound closure пройден: 13.01.2025 20:01 на 8 часов раньше фактического restore. Это доказательство допуска на старом пути, не новый ROI.
3. Первый кандидатQ: BTC cut25%, SOL50%; все остальные C1условия/права/clock/partials без изменений. Код и focusedтесты готовы; единственное замечание observerнаendboundary исправлено, peer0P0/P1; source72cc39c опубликован. До первогоBTCcut06.06.2025 экономический путь должен совпасть сC1, включая январь51.803%; Qнеобещаетstrict50.
4. После frozen source/config/input/observer review — один Qfullpath сdirectPopen/actualchildexit, registryclaim до запуска. Каждый вариант имеет собственныекапитал/fees/funding/qty/HWM. При causalDDвыше допуска TARGET_FAIL_DD и TOTALUNKNOWN, без искусственногоterminalPnl. Объявленноеотрицательноеcandidateсостояние не подменяетnativeошибку.
5. Если Qне проходит — Rтолько при доказанномраннемeligible, затем G по всеминтервалам. Не больше одного информативногосочетания, дельта выбрана до результата. При первом проходящемварианте заморозитьего и перейти кpilotqualification, безлишнего рекорда.
6. Параллельно подготовить existingengine/live wiring/restart/partial/reconciliation/stop. После выбораварианта — заранееописанный stress и validation на имеющихсяпоследующихданных; seenhistory неOOS. Неттребованияпроизвольныхнедельожидания.

## Один бюджет и точность результата

До4candidatefullpath, до2controlreproduction только при реальнойнесопоставимости, до2qualification: максимум8историческихпопыток, включаяошибки. Unit/nativecomponentfixtures отдельно счисломвызовов/wall, максимум2repairитерации наblocker. Старыеархивыне повторятьдляназванияметрики. Одинmanifest/registry/итог; безновыхсогласованийкаждойпроверки.

На каждомисторическомзапуске: TOTAL/ROI/retentionS0&E4, settled/eventDDtimestamps/minE, все24месяца/4окна, actualcuts/restores/revokes/blockedadds, nativefees/funding/cashreconciliation, liquidation иterminalstatus. Fundingизactualnativecashdeltas; bridge53801.142665296518712 неfunding. Новыйsignedfundingobserverиcoherentobserver — read-only, исходныеeconomicanchorbytesпроверяются. Ненулевойточныйнеобъяснённыйbridge остаётсяUNKNOWN, неtolerancePASS.

## Live и сохранённые результаты

LIVE_RELEASE.json пока DRAFT/live_order_capability=false: владелец уже указал Hyperliquid/аккаунтPRIVATE_ACCOUNT/бюджет≤PRIVATE_CAPUSDC; точныйrelease и6readinesschecks ещёне готовы. До mainnetнужны6readinesschecksизвложения, warmclosedH4/D1, globalH/parent/PLANREF/credit/rearm/TPrights/pendingpersist+reconciliation, managedreduceпутьприUNKNOWN, реальныеvenueordersemantics/minlots, изоляцияиstopreporting. Исследовательскийфлагнеподменяетlivecallbacks. Стоящее прямое разрешение владельца сохранено в .ops/OWNER_AUTHORIZATION.md; повторных согласований обычных действий нет. Последнее уточнение владельца: перед ордерами нужны итоговый алгоритм, проверенный на эталонном периоде, readiness/reconciliation, соблюдениеPRIVATE_CAPUSDC и его отдельное явное подтверждение стартаlive; работающие сервисы пока не менялись.

MethodA/CODE0сохранённаотдельномVPSworktree: base3f555d9+точныйSAFE_CHECKPOINT/WIPpatch, безновыхтестовилиnative; бюджет9/19 HOLD, слоты незаимствуются. Настоящие3TP/continuoushedge/общийSL/другиеальты остаютсяпоследующейотдельнойоптимизацией. Непроверенныйкод невыдаётсязаготовыйliveалгоритм.
