# Предложение: ровно один дополнительный A05

Статус PROPOSED_NOT_APPROVED. Новых native/prefix запусков этот документ не разрешает. Исходный money-контракт и protocol5c5e2b41555ee4e5c1970c5c5dadd173cd10599e00158224b706cb0083f477a0 не меняются.

Причина: утверждённый engineering cap6 израсходован, 2COMPLETED/4FAILED. Последняя попытка остановилась на fixture API (`.clear()` у tuple), после доказанных ACKUNKNOWN/postOnly блокировок, до проверки native marginDENY. Закрытый ledger c0b84b39c5199671a258a8dcda6301ef3fd641f64be357e8c165be3aa0ffa424 остаётся неизменным.

Предлагается увеличить общий engineering предел **6→7 (+1)**. Это ровно один дополнительный native engine A05, включая setup/failure/repeat; резерва и автоматического повтора нет. Quotes/engine span≤1h, synthetic seed/config span25h≤48h. Предыдущие шесть строк и все четыре FAILED входят в общий предел7. После согласования — отдельный amended ledger с parent hash закрытого ledger, прежними шестью строками и единственной новой строкой7; до согласования он не создаётся как разрешённый.

Исправление только в fixture: действительная котировка без новых VenueMark после неизменённого max_mark_age_ns должна получить штатный отказ stock margin gate; реальные свежие VenueMark восстанавливают допуск. Policy/config/static/dynamic stores не мутируются. Сохраняются проверки обоих native ACK callbacks, текущих трёх TP, crossing WAIT, исходного GTC, one-attempt/caps/actual fills/real3TP/native flat/cash identity и реального STOPPED→DISPOSED. Никакого override `_tier_allows_increase=True`, fake fill или переноса закрытого BTC. Денежный package остаётся reviewed340f.

Exact source/diff/real-class engine-free verification/one-case proposed gate и независимое review должны быть frozen до owner consent. Root GO возможен только после прямого human+1 approval с сохранённым exact reply; proposed gate сам по себе не authority. Если новая попытка не проходит — stop, никакого следующего engine или экономического запуска.

Уже согласованный prefix cap **3 не увеличивается**: R2 OFF→C0→A0, [2024-09-01,2025-01-15)UTC, seed10000/reserve0, failures/pre-engine failures входят. Сейчас0/3 и HOLD. Только после actual A05PASS и source/config/data/component-review допускается engineering LIMITED_PASS с явным C0_NATIVE_FIXTURE=NOT_RUN, затем отдельный root GO для каждого prefix. Полная прежняя financial/accounting/coverage/ownership/real3TP/zeroLiq/terminalflat приёмка actual C0 обязательна до A0; UNKNOWN останавливает цепочку. Ранее согласованные 3 prefix не являются новым бюджетом.

A0 economic gates прежние: gain versus matched C0 >0 и >2max(0,incrementalfees), settled и coherent event DD≤50% и≤C0, dailyES20 всех136UTCдней≤C0, actual additional native BTC fill необходим для заявления о пользе. Цели исходного S0 ≥70%net intermediate, затем≥90% при DD≤50 остаются NOT_MET до соответствующих доказательств. Префикс неfull/OOS.

**Full/training/new market downloads/pilot/production/external orders/transfers — 0.** Public research source publication разрешена, deployment нет. Никаких изменений BTC entry core, SOL TP/cuts/rearm, плеча, fees/funding/data или допуска по марже.

Frozen implementation ready for consent:

- Source `763d985617abd7a7afef5eec13912303983d8837`, isolated branch `codex/hedge-rights-unlock-20261025`; monetary package byte-identical to reviewed340f.
- `a0-margin-fixture-repair.diff` SHA 38cb04cee8603b6a28c9d7015074576d273ab97d816362ad079fc460644132c1.
- `a0-margin-fixture-verification.json` SHA 9a8ae371d99f0f8640d73fe90c6b977e0b5becf1e034a89f9617ec076d954fa2:57 engine-free PASS; real immutable TierMarginPolicy/static+dynamic fallback/stale→fresh and both native callbacks checked.
- `a0-additional-A05-plan.json` SHA 73505b764d4740536ec2ec505c5c43b54027a881b111722b3623bb6fe28a6204; proposed gate SHA ca01ebbc43f432f4594a38beeeb73ec399b15edcbcf47872c6e1307a91056d07, root_go=false. Root source/input pin verification: no mismatch. Approval template is not consent.
- Independent final repair review: `a0-margin-fixture-repair-review.json/.md`; it must confirm no open P0/P1 before root GO. Review itself provides no budget.
- Publication status: local committed source, PUBLIC push blocked by automatic approval review before dispatch. Separate explicit destination consent requested for https://github.com/VF78/coinmaster and research branches; no deployment.

Final independent review763: P0=0/P1=0, PASS_FOR_HUMAN_CONSENT_ONLY; actual native marginDENY/recovery remain NOT_PROVEN. Initial e54 reply-type P1 preserved and closed; exact source/plan/gate verified.
