# Joint SOL PREFIX S1: native accounting PASS, FULL pending

Квалифицирован только91-дневный PREFIX [2024-09-01,2024-12-01):131040 source rows,131039 settledWM,3months, full=False. Native flat,0orders/liquidations. Sourcec411. Это не FULL/ROI acceptance.

| Native показатель | BTC | SOL |
|---|---:|---:|
| Cycles | 12 | 1 |
| Fills | 50 | 2 |
| Realized, комиссии включены | 20399.50804270 | 885.58322715 |
| Комиссии справочно | 590.45159932 | 37.01127285 |
| Фактический signed funding | -644.12644055 | -0.76008666 |
| Native net | 19755.38160215 | 884.82314049 |

**Cash30640.20474264USDC** =seed10000+BTCnet19755.38160215+SOLnet884.82314049; residual0. Funding привязан только к тому же инструменту и единственному фактическому lifecycle. Все nativefees включены в realized один раз.

## SOL-факт

Один actualSOL BUY302.49,3октября00:00→5октября00:00, scoped exit `BTC_MARKET_REGIME`. K=1.3525692288588918104825495154156815007348050486126; actualBTCnotional57316.8193632/K=N042376.255603238802282926801613226502643324775947079; Q0302.49. Присутствует сохранённый observed zero-wave fact2октября00:02 с genuinePLANREF60811.2, а не initializedzero. D1z−1.66181936/σ0.09611627521838921 и source/available/decision clocks проверены; K/σ/permission одинаковы в открытии и выходе.

Native SOL realized885.58322715,actual funding−0.76008666 (6 postings),net884.82314049. Исторический цикл не содержит TPflatcarry; этот механизм наблюдён в E08, но не приписывается данному циклу.

## BTC и сопоставимость

12 BTC entry keys/50fills; все12 branches/q0/q1/role sequences совпадают с правильным savedBTC-onlyR3 FULL interior. SOL меняет общий actual capital, поэтому последующие BTC количества/комиссии законно меняются.

R3 qualifiedFULL nativeWM leftlimit наDec1: flatcash28463.40640027, joint−control **+2176.79834237**. Разложение: SOL+884.82314049, observedBTCcomponent+1291.97520188; это учётное разложение, не изолированный causal SOL-effect. Отдельный R3prefix engine не запускался.

Старый физически квалифицированный BTCprefix source4e cash28559.68460617 хранится только changed-source diagnostic: там был отвергнутый раннийH4phase. Primary comparison использует правильный source8857R3 interior.

Joint event maximumDD28.88635504383867849532545631%; settled28.79678347794819918559799851%. Полный риск/ROI вывод ожидает FULL; меньшее число циклов и прибыль одного эпизода не доказывают устойчивость новогоSOL правила.

## Provenance

- raw_sha256: `6f2150e4dd80e9fa28ee59d3c45aa8e2a01b018aeb2fbebdd6c0e4f850c748e4`
- qualification_sha256: `4325e83c81aaf44800f43594504a97872412a114190b0cb9b3414bc597d4c1a2`
- derived_report_sha256: `e146e5c6553163b05af51f137d9180ccc36f5e7894b283aa30c025d60481492a`
- derived_csv_sha256: `882e3c27b391a547eabca438ba26dfa4575e9eb85735378488cc157389ac9972`

JSON/CSV сохраняют nativeassetcycle money, permission/timings/carry и BTC differences. Старые отчёты не изменены. Analysisengine0,productedits0,Macfinance→VPS0; runningFULL artifacts не читались.
