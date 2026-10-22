# H1: predeclared action cost gate

PRECHECK_NO_ECONOMIC_GO

Per hypothetical SECONDUNIT/P0: side*(endpoint_actualpx-entryreferencepx)-entry_feeprice-native_endpoint_feeprice. H1 feeprice=.00055*conditionalnextclose; S0 entryfeeprice=actualsecondcommission/qty. H1 noadd=0; HALF_ONLY secondunit=0. All105 equally weighted; no nativeqty, notional or capital weighting.

Primary = FIRST original actual ordinary BTC fill. Final exit is sensitivity only, not candidate execution.

| Equally weighted events | S0 mean % | H1 mean % | Half-only % | H1−S0 pp |
|---|---:|---:|---:|---:|
|all105|0.376810|0.245942|0|-0.130868|
|H1adds49|0.869055|0.527019|0|-0.342036|
|original_winners|1.683491|1.122636|0|-0.560855|
|original_losers|-1.174874|-0.795132|0|0.379741|

{"nonempty_months": 22, "H1_vs_S0_positive_months": 8, "H1_vs_S0_negative_months": 14, "H1_vs_HALF_ONLY_positive_months": 13, "H1_vs_HALF_ONLY_negative_months": 5}

Secondary final original endpoint all105: {"S0_proxy_percent": {"events": 105, "event_weighted_mean_percent": 0.8911061387421488, "median_percent": 1.3843456629391113, "positive": 57, "negative": 48, "zero": 0}, "H1_proxy_percent": {"events": 105, "event_weighted_mean_percent": 0.3164638466452762, "median_percent": 0.0, "positive": 30, "negative": 19, "zero": 56}, "HALF_ONLY_proxy_percent": {"events": 105, "event_weighted_mean_percent": 0.0, "median_percent": 0.0, "positive": 0, "negative": 0, "zero": 105}, "H1_minus_S0_pp": {"events": 105, "event_weighted_mean_percent": -0.5746422920968727, "median_percent": -0.4902425687589676, "positive": 38, "negative": 66, "zero": 1}}

No quantity weighting, dollar compounding, alternative equity/TOTAL/DD/PnL or extra price scan. Partial native TP quantities, candidate exitpath and signed funding UNKNOWN. All105 individual rows and monthly figures retained.

**PRECHECK_NO_ECONOMIC_GO.** По первому endpoint H1 хуже S0 на0.130868 процентного пункта среднего нормализованного результата второй единицы;8 положительных/14 отрицательных месяцев. H1 выше half-only0, но условие преимущества над обоими контролями не выполнено. Среди49 доборов39 хужеS0/9 лучше/1 равен. Диагностика проигравших улучшается, но ухудшение исходных победителей перекрывает её в этом equally-weighted proxy. Вторичный финальный endpoint также отрицателен относительноS0 (−0.574642п.п.) и не заменяет primary. Это не оценка альтернативного TOTAL/DD/PnL.
