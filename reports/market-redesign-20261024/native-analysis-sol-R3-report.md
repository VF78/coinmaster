# SOL paired-action screen: фактическое состояние R3

**STOP_SOL / INCONCLUSIVE: причинный risk gate не найден.** Выполнен тот же заранее объявленный screen на настоящем R3inventory. Нового SOLалгоритма, lifecycle replay или кандидата PnL/DD здесь нет. Все три размера дают положительную условную close-grid защиту, но отрицательную среднюю net action добавку в обоих годах. Устойчивого преимущества перед равным BTCtrim не установлено. Новая причинная гипотеза этими таблицами не подтверждена; новый опыт не предлагается. Полный бюджет3/3 уже закрыт, новых engine запусков **0**.

## Фактические данные и доступность

Вход — принятый root R3 native result/raw,354полных single-fill orders и354actual fill-audit records,83измеренных parent cycles. Native timestamps/qty/one-fill price сопоставлены с audit; native terminalBTC=0.000. Native fee/PnL/funding R3 не заменяются условными action cashflows. Ни E4BTCcalendar, ни его размеры не использовались для решения, где R3 держит позицию.

Из4380 закрытых H4timestamps исключены **2761BTCflat**,56без полного lag720,34с настоящим BTCfill ровно на decision timestamp (event ordering неизвестен). Получено **1529решений /77циклов**:698/37первый год и831/40второй. Все **1529signed native BTCqty** независимо совпали с реальной settled trace R3 на соответствующем source quote. Trace служит проверкой состояния, а не будущим признаком: features используют только actual fill timestamps<t; observer source/receipt сохраняются в исходном accepted trace. Сам trace уже прошёл отсутствие intervening native mutation.

С E4screen совпадают1505eligible timestamps, и во всех1505 actualQ другой;24timestamps новые,55старых отсутствуют. Эти различия — наблюдаемое изменение R3inventory, не перенос старого календаря. E4outputs сохранены без изменений.

Определения не менялись: SHA256 `sol-screen-design.json`=552e2b227407c89ee41473ebe08fd45869124ddc8ad60a2a233bda7ad1e16d4c.720синхронных простых H1returns строго доt (последний end=t−1h); закрытый H4return; ER24=24закрытыхH4increments,96h. Все bars имеют available_ns=close_ns. Положительные variance/covariance/beta/correlation обязательны, rho .58960… .88898. ERстраты <=.25/.25… .5/>.5:1005/468/56; adverse/nonadverse H4:758/771. Страты только описательные, gates из них не выбирались.

1529labels4h и1524labels24h (5неполных24h исключены). Фактический nativeflat пересекают77/424labels; ни один label не пересекает границу двух лет. Начальная наблюдаемая Q заморожена на outcome horizon; дальнейшие реальные TP/выходы внутри него намеренно не симулируются. Первый год [2024-09-01,2025-09-01), второй [2025-09-01,2026-09-01).

## Сравнение одинаковых действий

NB=abs(actualBTCqty)*closedBTCprice; betaSOLgivenBTC=cov/varBTC. SOLside противоположен actualBTC. OWNER_VOL=.5NB*sigmaBTC/sigmaSOL; HALF_MV=.5NB*cov/varSOL; HALF_FACTOR=.5NB/beta. Их estimated BTCfactor relief соответственно .5rho, .5rho² и .5NB: это разные размеры. Matched BTCtrim=NS*beta, все trims<=.5NB, незаметного clipping нет. NO_HEDGE incremental cashflow/fees=0.

Обе ноги условного SOL или BTCtrim действия taker.055%; fee=.00055*Naction*(2+assetreturn). Trim уменьшает BTC сейчас и восстанавливает ту же quantity на горизонте. Суммы перекрывающихся окон не складываются как прибыль. Старые BTCentryfees не начисляются повторно; slippage/funding/queue/L2 отсутствуют.

Средние в bp от NB. Net — incremental benefit относительно NO_HEDGE после actionfees, не суммарная стратегия. Tail — улучшение `min(0,min(H1-close combined change))` относительно того же frozenBTC reference; это не intraminuteMAE или native maxDD. Mean frozenBTC endpoint change:4h +4.937bp,24h +20.929bp; combined endpoint = этот reference + netbenefit.

|h|SOLsize|SOL net|Trim net|SOL fees|Trim fees|SOL tail|Trim tail|
|---:|---|---:|---:|---:|---:|---:|---:|
|4|OWNER_VOL|-5.400|-6.317|3.204|4.308|8.865|10.863|
|4|HALF_MV|-4.389|-5.037|2.536|3.397|7.694|8.554|
|4|HALF_FACTOR|-6.666|-7.969|4.078|5.500|9.192|13.869|
|24|OWNER_VOL|-13.608|-13.186|3.202|4.310|31.555|39.116|
|24|HALF_MV|-11.461|-10.867|2.536|3.401|26.911|30.531|
|24|HALF_FACTOR|-16.013|-15.966|4.073|5.501|34.016|50.586|

SOLдешевле matchedtrim на4h, но tailзащита слабее. На24h совокупный средний netхуже и tailслабее. По годам стоимость меняется: в первом году24hSOLдешевле trim, во втором дороже, поэтому единого превосходства нет. Отрицательный hedgecashflow сам по себе не объявлен провалом — стоимость рассматривается вместе с защитой.

|h|SOLsize|Net SOL год1|Net trim год1|Tail SOL год1|Tail trim год1|Net SOL год2|Net trim год2|Tail SOL год2|Tail trim год2|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
|4|OWNER_VOL|-4.928|-6.652|9.382|11.053|-5.796|-6.035|8.430|10.703|
|4|HALF_MV|-3.811|-5.081|8.022|8.264|-4.874|-5.000|7.418|8.798|
|4|HALF_FACTOR|-6.386|-8.757|9.306|14.881|-6.902|-7.306|9.097|13.019|
|24|OWNER_VOL|-14.398|-15.503|32.731|39.800|-12.941|-11.227|30.560|38.539|
|24|HALF_MV|-11.916|-12.579|27.448|29.303|-11.076|-9.421|26.456|31.570|
|24|HALF_FACTOR|-17.108|-18.999|34.273|54.624|-15.088|-13.403|33.799|47.175|

## Устойчивость и gate verdict

H4rows перекрываются и не независимы. Сначала усреднение внутри actualBTCcycle, затем равный вес77циклов:

|h|SOLsize|Cycle mean SOL net|Cycle mean trim net|Cycle mean SOL tail|Cycle mean trim tail|
|---:|---|---:|---:|---:|---:|
|4|OWNER_VOL|-9.277|-9.371|8.949|11.699|
|4|HALF_MV|-7.509|-7.510|7.798|9.285|
|4|HALF_FACTOR|-11.525|-11.773|9.198|14.803|
|24|OWNER_VOL|-24.260|-20.357|30.971|40.470|
|24|HALF_MV|-19.979|-16.755|26.577|31.816|
|24|HALF_FACTOR|-29.451|-24.797|33.095|51.866|

Будущий downside/upside — outcome, никогда causal feature. Детальные раздельные результаты сохранены в summary view=endpoint: SOLзащищает многие реализовавшиеся downsideокна ценой затрат в upsideокнах. Эти будущие labels не позволяют выбрать момент включения. ClosedH4/ER/correlation страты сохранены полностью, без отбора «лучшего» gate, новой сетки или возврата к ранее неудачным gates. Уже просмотренная история не является freshOOS.

Данные не подтверждают новый предиктивный riskevent или основание для SOLimplementation. Они также не связывают нынешний global DD Jul6→Aug19 с переносом старого положительного TP2 в цикле31; P+floor31 из этого screen не следует. **STOP_SOL:** сохранить честный отрицательный/неопределённый вывод; новый gate или lifecycle потребовали бы отдельной гипотезы и отдельного бюджета.

## Артефакты и воспроизведение

Только `native-analysis-sol-R3-*`: calculate.py (CLI), features.csv1529, outcomes.csv21371, summary.csv420, cycle-blocks.csv16744, meta.json с hashes/coverage/verification, report.md. Outcome USDT — условная добавка одного действия, не profit стратегии. Native actual R3TOTAL120718.40416503/DD68.6033754 остаются отдельными принятыми результатами; screen не объявляет альтернативный TOTAL/DD.

```sh
python3 reports/market-redesign-20261024/native-analysis-sol-R3-calculate.py --artifact /Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/market-redesign-20261024/R3/result/v0-selective-lifecycle-cap30m-btc-split50-d0.005-planref-v1-tp-ioc-E4-B-ATR0.5-btc-direction.json
```

CLI поддерживает --raw, --acceptance, --bars, --output-prefix; ожидает фактический acceptedR3 и пишет только native-analysis-sol-R3*. Один связный проход/проверка: actualfilledsingleorder/audit354, signedinventory/starttimes83, terminal0,1529traceQ equality, lag availability, NO_HEDGEzero, factorrelief identities и additive comparisons PASS. Никакой nativeengine, training, новая торговая гипотеза, order, deployment, source/ledger/shared edit или публикация не выполнялись.
