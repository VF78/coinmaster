# Broad saved-data discovery — 36 configurations, no confirmed candidate

Библиотека завершена: Stage I 16 rules×4h/24h=32 configurations; условный Stage II только B2/F0×8h/12h=4. Всего 7,352 episode/scenario rows. Это сохранённые данные и local attribution, не native/full/short backtests. Физических engine runs, product/pilot/production changes: 0.

Сырые положительные направления: B2 failed favorable break (capital + protection), P1 initial-fill underwater (protection), F0 carry control (protection). Ни один тест не подтверждён после Holm128: все adjusted p=1. Не заявлены candidateTOTAL/globalDD/70%-90% retention/native3TP или causal execution.

## Неизменная бухгалтерия и gates

C* terminal точно120718.40416503, q=0, actual persisted BTC funding4063.32156049, Decimal residual0. C* — settlement-equivalent pricecash, не native futures wallet cash при held position. Wraw=C*+actualq×raw completed mark — наблюдаемая reference attribution. Нового candidate capital/OMS/matching нет.

Размеры/J-budget известны на t; exact same quantity/side guard на e=t+60s, без future-min/re-sizing. Comparator cap — UNKNOWN/noaction при превышении held BTC, не clipping. Source/freeze hashes проверены перед START. Entry funding calendar ties0. Wraw_start всегда factual baseline after all actual flows at e, pre-hypothetical action. NOACTION одинаков во всех сценариях. Actual funding/native fill-prefix ambiguity имеет фиксированную одинаковую baseline bracket; BEFORE/AFTER меняет только hypothetical funding exposure.

Raw gates требуют все три когорты year1/year2/early и все четыре согласованных сценария 0/2bp×BEFORE_ALL/AFTER_ALL. Loss CVaR20 — mean largest ceil(.2n) неотрицательных worst losses FROM ENTRY START. Sampled peak-to-trough не подменяет критерий. Ниже показаны bp от NB_t, means относятся к2bp/BEFORE_ALL; qualification проверена во всех четырёх сценариях.

## Сырые положительные configurations

| Rule/h | n y1/y2/early | Mean H bp y1/y2/early | Mean H−trim bp y1/y2/early | min main CVaR gain vs baseline bp | Raw lanes | Route | raw p capital/protection | Holm128 |
|---|---:|---:|---:|---:|---|---|---:|---:|
| B2/4 | 19/19/9 | 0.921/11.627/10.455 | 11.374/6.739/21.321 | 65.597 | capital/protection | RETURN_AND_RISK | 0.438/0.009 | 1 |
| P1/4 | 34/35/15 | 0.014/-0.181/3.754 | 10.316/3.754/12.043 | 23.459 | protection | RETURN | 1.000/0.268 | 1 |
| F0/4 | 33/32/14 | -9.144/0.402/-9.924 | 3.941/0.463/10.150 | 41.687 | protection | RETURN | 1.000/0.990 | 1 |
| B2/8 | 19/19/9 | -3.443/8.940/17.257 | 3.002/9.571/28.200 | 50.379 | protection | RETURN | 1.000/0.845 | 1 |
| B2/12 | 19/19/9 | 0.568/1.775/19.146 | 5.666/1.048/28.728 | 76.706 | capital/protection | RETURN | 0.474/0.796 | 1 |
| F0/8 | 33/32/14 | -2.522/-11.473/29.137 | 1.967/0.519/24.454 | 51.005 | protection | RETURN | 1.000/1.000 | 1 |

Stage II выбор зафиксирован ДО labels: capital B2/4 имел лучший minimum main paired mean; protection F0/4 имел наибольший minimum main CVaR gain×coverage среди другого семейства. P1 положителен, но не выбран, не заменён постфактум. F0 — известный carry/protection control, не новая funding alpha. У B2/8 и12 protection проходит RETURN, несмотря на худший tail против trim в одной основной когорте; маршруты не смешаны между годами. B2/4 проходит оба маршрута.

Исходные B2/24 и F0/24 не проходят; F0/12 тоже не проходит. Stage II повторно использует историю, не OOS. Больше horizons/thresholds/sizes/TP tuning этим бюджетом не разрешено.

## Вся сетка, включая пустые и неудачные

min ΔtailN = minimum CVaR_N−CVaR_H по двум основным годам и всем4scenarios; min ΔtailT = CVaR_T−CVaR_H. Baseline-tail gain сам по себе недостаточен для qualification.

| Rule | h | n y1/y2/early | H mean bp y1/y2 | H−trim mean bp y1/y2 | min ΔtailN bp | min ΔtailT bp | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| A0 | 4 | 41/40/19 | -1.181/1.654 | 6.067/2.069 | 32.310 | -4.043 | CONTROL_RAW_PROTECTION |
| A0 | 24 | 41/40/19 | -29.172/-31.757 | -4.569/-16.943 | 92.925 | -26.500 | FAIL |
| A1 | 4 | 40/39/19 | -7.292/-8.033 | 8.350/-1.347 | 35.957 | -7.607 | FAIL |
| A1 | 24 | 40/39/19 | -37.179/-31.371 | -10.171/-14.980 | 81.350 | -23.688 | FAIL |
| B1 | 4 | 21/25/11 | -10.217/-8.261 | 0.684/-0.044 | 38.633 | -13.108 | FAIL |
| B1 | 24 | 21/25/11 | -21.630/-20.501 | 7.475/-9.090 | 58.549 | -42.834 | FAIL |
| B2 | 4 | 19/19/9 | 0.921/11.627 | 11.374/6.739 | 65.597 | 11.519 | RAW_CAPITAL+PROTECTION |
| B2 | 24 | 19/19/9 | -30.572/-19.559 | -9.584/-21.905 | 77.354 | -29.001 | FAIL |
| V1 | 4 | 19/23/10 | -17.787/-11.466 | -0.611/-2.872 | 9.760 | -28.359 | FAIL |
| V1 | 24 | 19/23/10 | -29.497/-4.225 | -0.154/-7.312 | 57.278 | -39.188 | FAIL |
| C1 | 4 | 37/39/17 | -15.299/-6.688 | 0.155/-0.879 | 26.911 | -9.527 | FAIL |
| C1 | 24 | 37/39/17 | -52.917/-34.612 | -24.734/-15.566 | 77.770 | -34.805 | FAIL |
| C2 | 4 | 0/0/0 | NA/NA | NA/NA | NA | NA | EMPTY |
| C2 | 24 | 0/0/0 | NA/NA | NA/NA | NA | NA | EMPTY |
| M1 | 4 | 12/9/5 | 7.802/-0.888 | 13.086/9.088 | 31.564 | -5.111 | SPARSE_DESCRIPTIVE |
| M1 | 24 | 12/9/5 | -19.696/-6.847 | -11.760/-2.473 | 88.560 | 9.705 | SPARSE_DESCRIPTIVE |
| L1 | 4 | 0/0/0 | NA/NA | NA/NA | NA | NA | EMPTY |
| L1 | 24 | 0/0/0 | NA/NA | NA/NA | NA | NA | EMPTY |
| P1 | 4 | 34/35/15 | 0.014/-0.181 | 10.316/3.754 | 23.459 | -9.029 | RAW_PROTECTION |
| P1 | 24 | 34/35/15 | -37.621/-18.554 | -8.718/-9.066 | 88.499 | -24.783 | FAIL |
| P2 | 4 | 32/33/14 | -22.850/-0.476 | -7.954/2.559 | 50.523 | -3.487 | FAIL |
| P2 | 24 | 32/33/14 | -39.233/-21.349 | -4.292/-8.344 | 94.426 | -20.660 | FAIL |
| R1 | 4 | 31/34/15 | -0.095/-13.192 | 8.160/-4.223 | 37.900 | -10.988 | FAIL |
| R1 | 24 | 31/34/15 | -45.658/-44.853 | -23.564/-14.667 | 55.742 | -30.851 | FAIL |
| R2 | 4 | 36/34/17 | -16.495/-3.717 | -0.983/0.295 | 38.857 | -15.619 | FAIL |
| R2 | 24 | 36/34/17 | -47.610/-12.307 | -18.658/-8.932 | 50.960 | -39.055 | FAIL |
| F0 | 4 | 33/32/14 | -9.144/0.402 | 3.941/0.463 | 41.687 | -10.217 | RAW_PROTECTION |
| F0 | 24 | 33/32/14 | -26.289/-29.727 | -12.894/-9.534 | 79.904 | -32.877 | FAIL |
| J1 | 4 | 32/25/15 | 2.075/-2.845 | 7.015/-0.822 | 38.550 | -9.117 | FAIL |
| J1 | 24 | 32/25/15 | -23.275/-29.753 | 1.057/-20.954 | 110.456 | -40.293 | FAIL |
| J2 | 4 | 24/18/9 | -24.106/-14.702 | -3.938/-2.114 | 25.709 | -19.023 | FAIL |
| J2 | 24 | 24/18/9 | -57.215/-23.930 | -18.447/-9.160 | 107.179 | -96.024 | FAIL |
| B2 | 8 | 19/19/9 | -3.443/8.940 | 3.002/9.571 | 50.379 | -36.911 | RAW_PROTECTION |
| B2 | 12 | 19/19/9 | 0.568/1.775 | 5.666/1.048 | 76.706 | -31.423 | RAW_CAPITAL+PROTECTION |
| F0 | 8 | 33/32/14 | -2.522/-11.473 | 1.967/0.519 | 51.005 | -19.930 | RAW_PROTECTION |
| F0 | 12 | 33/32/14 | -5.232/-13.646 | 2.075/-0.654 | 72.872 | -11.145 | FAIL |

## Coverage и известные controls

Все83actual R3 episodes сохранены. 81имеет held completed-H4 opportunity; cycles23/26 flat до следующего H4 и честно noaction. 1,618held raw states/1,584common-valid. Causal D1cov30_lag1D доступен с раннего сентября; первые4цикла не исключены H1lag720-фильтром. H1lag720 только provenance/control. A0 покрывает41/40year episodes и19early. У каждого rule первый valid opportunity/episode, без будущего best entry/re-add.

M1/4 и24 — raw protection positives, но SPARSE12/9/5: minimum10во втором году не выполнен, refinement не назначен. C2 иL1 пустые; thresholds/history не изменены ради событий. A0/4 — raw protection control, не true-SOL admission. A1,R1/R2,F0 сохраняют статус заранее зарегистрированных известных семейств. J2 не прошёл ни один horizon; emergency pure trim/held-only stress не выдан за full-controller proof, pending risk UNKNOWN.

## Экономические и execution ограничения

IDEAL_SYNCHRONOUS_PAIRED_ATTRIBUTION сокращает SOL вместе с observed BTC reductions на raw completed execution close того же timestamp. Это оптимистичная описательная paired assumption, не доказанная реактивная сделка/atomic actual3TP. Latency, partial/late fills, margin, capacity/L2 и полный pending/order risk UNKNOWN. Actual BTC adds остаются baseline и не увеличивают overlay.

Native exit cash/fees кредитованы пропорционально actual reductions; scheduled still-held BTC restoration платит taker; при actual flat BTC не переоткрывается. Hypothetical avoided BTC funding — market-reference attribution, не exact native avoided cash при callback/price-rounding ambiguity. Before/after не являются полной границей всех mixed callback orders. Raw-mark grid/bracketed group boundaries не доказывают intraminute coherent native/event DD. Старый #133 UNKNOWN_DATA_CLOCK_TERMINAL_ENDPOINT не переписан. CandidateTOTAL, reinvestment path, native3TP и восстановление S0capital здесь не вычислены.

## Проверка и использованный бюджет

Stage I independent prefix-event algebra:6,528endpoints/19,584loss metrics/58,752cost-funding components/336cohort means-CVaR/32all3×4gates. Max cash residual2.33e−10USDT, loss5.43e−12bp. Проверены B8192/stored IUT/2-route arithmetic; Stage I RNG draws отдельно не переигрывались.

Stage II independent algebra:824endpoints/2,472losses/7,416components/48cohort tables/4gates. Все36bootstrap cells×8192monthly draws/144contrasts p-CI независимо воспроизведены; combined Holm128 перепроверен. Max cash residual1.16e−10USDT, loss4.86e−12bp. Label/calculation functions в financial verifier не импортировались.

Financial corrections/failures0. Сохранены prelabel failures:лишняя скобка до data build и ошибочный verifier strict-flat assertion; feature money/outcomes ими не исправлялись. Before-review draft features/code/metadata сохранены. Frozen source/data/native artifacts не изменены.

32/32Stage I и4/4условного Stage II завершены, по одной connected verification PASS. Дополнительных configurations/engine/full/short/training/product runs0. Следующий native/full/short или parameter-search budget не открыт. Все36configurations, все сценарии, пустые cells и статистическая неопределённость сохранены, не только положительные.

Artifacts:discovery-combined-configurations.csv; discovery-stageI/II-episodes.csv; discovery-stageI/II-cohorts.csv; discovery-stageI/II-statistics.csv; discovery-stageI/II-verification.json; phase-ledger.json.
