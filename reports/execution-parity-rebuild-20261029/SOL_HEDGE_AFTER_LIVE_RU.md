# Настоящий SOL-хедж BTC — после запуска и стабилизации live A

Project2: https://github.com/VF78/coinmaster/issues/138 — Todo.

Статус: отложено по прямому указанию владельца30.10.2026. Зависимость: #101 — запуск и первичная стабилизация A. Эта задача не блокирует A и не разрешает сейчас новый торговый код или native-прогоны. Текущий бюджет: native/prefix/full0.

Основание: CODEX_SOL_EXECUTION_RESET_2026-10-30.md, §6; SHA256 `1b3fb18e1baebed7d66ffae203f406beb9a52e4c6527b599bfc41c85b39db584`. Арифметика приложенных check_arithmetic.py/arithmetic_checks.json воспроизводится; это проверка формул и опубликованных чисел, не новая калибровка или бэктест.

## Требуемый контракт

1. Parent — фактическая BTC-позиция; SOL противоположного знака. При BTCflat targetSOL=0; остаток во время закрытия измерять. После BTCfill/cut/flip пересчитывать target. SOLTP сам по себе не обязан сокращать BTC. Допуск не зависит от фиктивных/omitted BTC TP и накопленных TP rights.
2. Сохранить редкость старого causal z: зоны1.25/2.5/3.75, подтверждение на закрытом H4: d*rBTC<0 и d*(rSOL-beta*rBTC)<0. Защитный beta —180 закрытых H4 доходностей, prior-only; legacy z остаётся отдельным признаком. Реальный warmup включает начало benchmark; отсутствие optional z не выключает защиту существующей позиции.
3. Target inventory: x_mv=abs(BTC_notional)*max(0,Cov(rBTC,rSOL)/Var(rSOL)). Это не abs(BTC)/beta. Уровни .50/.75/1.00 заменяют target, не суммируют бюджеты. Подтвердить коэффициенты exactconfig до freeze. Отрицательные/неизвестные оценки не подменять положительной константой.
4. Учитывать actual/pending, margin tiers/minlots и запрет net-beta flip. Pending SOL не считается уже полученной защитой. Отправлять только delta до target.
5. Проверять held-risk: C=E-.50*H; причинные сценарии BTCadverse, basis divergence, rebound; costs и signed funding ровно один раз. Сравнить допустимый SOL с BTCtrim. При малом числе сценариев достаточно одномерной piecewise-linear задачи. Infeasible обозначать явно, не создавать гигантский SOL. Приоритет risk reduction перед новыми входами.
6. Partial harvest с реальным net contribution и отдельным protective exit по premise/basis/risk. Первым вариантом могут быть существующие half/full relative exits плюс protective STOP. Если выбраны3TP — реальные уровни/ордера, заранее зафиксированная отдельная exit-policy. Никаких zero-price/fake fills. Rearm лишь на новом закрытом баре и новой возможности; no-trade band покрывает costs/lotnoise.
7. Native ACK/fill/cancel/partial semantics, идемпотентность после рестарта и UNKNOWN→reconcile. BTCclose/flip приоритетнее discretionary SOLincrease. Измерять orphanlatency, tail-risk пары, покрытие BTCadverse, цену хеджа на BTCwinners и ранний капитал; standaloneSOLprofit не доказывает качество хеджа.

## Порядок и приёмка после live

Сначала заморозить минимальный policy, причинные данные/warmup, сценарии, costs и числовой бюджет. Затем focused pure/Cache/Order/restart проверки, один независимый review. Экономика только native Nautilus с тем же corrected common profile, что A; исходные FAILED и UNKNOWN сохраняются. Fixed-path диагностика не объявляется ROI. Не добавлять ML/RL/новый движок/параметрический sweep.

Контроль A: TOTAL5635720.91989984USDC, settled+coherentDD51.4383711874%, 0liq на [2024-09-01,2026-09-01), seed10000. Цель нового SOL: TOTAL>=5500000 и обе DD<=50%, желательно30–50%; предел допустимости и бюджет утвердить перед экспериментом. Проверить также реальный малый капитал без повторного запроса суммы.

Уже испытанный B5e1a899b — другая бюджетная policy: rawTOTAL883181.30709990/DD74.76431633%, financialgateFAIL. Он не доказывает результат предлагаемого здесь residual-confirmed covariance hedge. Никаких новых прогонов старого B по этой задаче.
