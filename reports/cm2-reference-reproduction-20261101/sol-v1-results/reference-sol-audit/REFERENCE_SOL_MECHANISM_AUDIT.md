# Reference SOL: что действительно заработало

Проверен именно **A10K**, source `5b56f7d02e09d4495ac018ec1ce701f6f0dfb737`: raw report `c01a9626…`, связанный saved native evidence `5553e5c3…`. Это25 фактических закрытых SOL inventory cycles/202 native fills. Никаких новых engine/tests, product edits, рыночного сканирования или пересылки финансовых файлов на VPS.

**Главное различие с Stage5/6 — отбор и жизненный цикл, а не ещё одно окно/порог.** Reference торгует остаточный SOL после заработанных BTC-level permissions, сохраняет экономический BTC episode после native BTC-flat и чаще закрывает SOL вместе с режимом BTC. Stage5/6 проверяли отдельные M5 crossing labels только при реально открытом BTC и сохраняли SOL после BTC-close/flip. Поэтому их NONE не опровергает механизм A; одновременно A не доказывает доходность этих новых labels.

## Фактический native результат

| Компонент | USDC |
|---|---:|
| Native gross realized SOL |721407.43990015|
| Native commissions SOL |−13960.92616950|
| Фактически зачисленный signed funding |+9034.49924311|
| Native SOL net,25 закрытых циклов |**716481.01297376**|

23 цикла положительны,2 отрицательны. Native position realized уже включает fees:707446.51373065; прибавление только фактического funding даёт net выше. Все25 joins native lifecycle realized + сохранённый cycle funding = cycle net имеют точный остаток0. Полные деньги каждого цикла находятся в [CSV](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOL_REVIEW/REFERENCE_SOL_MECHANISM_AUDIT_CYCLES.csv) и [JSON](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOL_REVIEW/REFERENCE_SOL_MECHANISM_AUDIT.json). Это суммы существующих native полей, не новый расчёт price-PnL.

Большой выигрыш сконцентрирован: цикл21 дал394729.58067237, **55.09%** всего SOL net; остальные24 вместе321751.43230139. LongSOL:13 циклов/+130486.90073368; shortSOL:12/+585994.11224008. Это одна уже изученная история, не независимое подтверждение будущего edge.

## Точные активные правила

1. **Разрешение и часы.** Paired D1 features: EMA34 для BTC side, beta270 log returns, relative65, mu/population sigma по180 предыдущим relative. SOL не торгуется по отдельному H4 alpha: `research_h4_ema=None`. H4 участвует в BTC reentry/C1. D1 domain повторно оценивается после фактических native reductions/terminal callbacks, поэтому SOL может начаться intraday по уже известному D1, когда заработано право. Это не непрерывный M5 crossing scanner.
2. **Права и отсутствие обязательного BTC inventory.** Actual BTC level reductions либо подтверждённые omitted-zero activations дают долевые persistent permissions. Native BTC TP-flat не уничтожает экономический episode. `sol_late_entry_after_tp=True`, open-only gate не включён. Все25 первых SOL ADD — level0;98 ADD состоят из87 level0/11 level1, level2 ни разу не исполнился. Независимый native-trace аудит установил **12 первых входов при BTC held и13 при BTC flat**; первоначальная интервальная проверка здесь доказывала8 flat и оставляла5 same-timestamp границ UNKNOWN, затем actor разрешил их actual committed events. Обязательный actualBTCheld gate запрещал бы эти13 состояний в траектории A. Но Stage5/6 использовали BTC-only control83-cycle, а A имеет84; нельзя без прямого join утверждать отсутствие именно этих13 timestamps среди Stage5 crossings.
3. **Z и направление.** SOL opposite economic BTC episode side. До первого SOL fill берётся current daily z; затем `z=(current relative−current mu)/sigma_first_actual_SOL_fill`. Beta/relative/mu продолжают обновляться ежедневно (`episode_fixed_beta=False`), **sigma фиксируется первым реальным SOL fill** до native SOL-flat. Stage5 использовал полностью новый daily sigma каждый день; его M5 relative менялся внутри дня. Эти два z lifecycle различаются.
4. **Размер и постепенность.** `H=(reference-or-initial BTC qty × actual BTC entry VWAP)/episode beta_entry`; level budget `H×(1.75,2.625,3.5)×earned fraction`, минус фактически использованные/retired credits. Whole original parent сначала проходит реальные admission/venue gates; только затем child≤1000SOL×fixed initialseed/10000. Неисполненный ADD budget может добираться **следующим D1**, максимум одна попытка уровня в D1. Поэтому заявленный parent не равен немедленно удерживаемому риску. Это не locked STD60 notional formula; переносить H-sizing в новый алгоритм нельзя.
5. **Выходы.** Known BTC D1 REGIME и BTC3% close-trail закрывают группу, опережая обычный SOL alpha. Отдельно14d от первого actual owned/fill проверяется на принятом D1; это не точный wall-clock timer. Z-half: signed_z≤.375, затем full≤.125 только после actual completion half и строго следующего D1 decision. SOL собственный price trail/z stop отсутствует. C1 actual cuts/restores используют существующие native права/credit, без независимой SOL alpha.
6. **Исполнение/стоимость.** Все202 SOL fills — actual IOC/taker, с текущей котировкой и настоящим FILLED. Обычные/timeout reductions продолжают accepted leaves через60s, mandatory REGIME/TRAIL могут продолжаться по тому же свежему book только после native terminal+position progress. Venue lot.01, taker.000432; нет выдуманного maker edge. Наблюдённый исторический funding известен ex post и не является прогнозом на входе.

Источник: [domain365–468](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOURCE_AUDIT/snapshots/reference/runtime/coinmaster/domain/wave_overlay.py:365), [fill rights/H475–563](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOURCE_AUDIT/snapshots/reference/runtime/coinmaster/domain/wave_overlay.py:475), [native episode latch624–657](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOURCE_AUDIT/snapshots/reference/runtime/coinmaster/domain/wave_overlay.py:624), [D1 queue1264–1380](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOURCE_AUDIT/snapshots/reference/runtime/coinmaster/strategy/wave_overlay.py:1264), [post-admission staging2008–2040](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOURCE_AUDIT/snapshots/reference/runtime/coinmaster/strategy/wave_overlay.py:2008), [native callbacks2640–2670](/Users/vf/Documents/ChatGPT/Coinmaster/research/cm2-clean-hedge-20261031/reference-reproduction-20261101/SOURCE_AUDIT/snapshots/reference/runtime/coinmaster/strategy/wave_overlay.py:2640). Exact SHA/blob и границы функций записаны в JSON; domain/strategy SHA совпадают с raw report source_hashes.

## Что фактически закрыло25 циклов

| Последняя причина | Циклов | Native net USDC |
|---|---:|---:|
|BTC REGIME|12|611715.86567499|
|BTC TRAIL|10|134989.93804037|
|SOL Z full|2|11274.13434642|
|SOL hard timeout|1|−41498.92508802|

Таким образом, **22/25 завершений — BTC economic-group exit**, не ожидаемая относительная сходимость. Только2 half fills и2 z-full fills во всём A. Медиана hold4d, максимум14.3354d: timeout был замечен на следующем D1 после14 elapsed days, затем13 actual1000SOL children вышли с шагом60s. Цикл, дошедший ровно до14d, мог получить TRAIL раньше timeout по source priority.

Stage5 median hold≈20d, tails до80.49d и25 right-censored labels, потому что отсутствовали group close/14d. Во второй эре spread convergence закрывала SOL с отрицательной ценовой доходностью: она могла быть вызвана BTC leg и daily recentering. Stage6 добавил другой выход — standalone SOL trailing stop0.03×locked K; все132 labels завершились им раньше z. Это не проверка reference BTC-group trail и не устранение различий в entry permission.

## Капитал и границы вывода

Direct native SOL contribution716481.01297376 —12.74% общей A net profit5625720.91989984. Раннее actual window до2025: SOL cash+50772.08755763, SOL endpoint UPNL−2010, итого+48762.08755763; BTC+19014.46898541, exact residual0. Shared actual equity затем меняет BTC sizes/HWM/C1 и H следующих SOL. **Вклад SOL в конечную разницу A vs BTC-only не равен716k**, и эффект отдельных правил из одного сохранённого прогона не идентифицирован.

A — прибыльная историческая alpha/staging, но не готовый непрерывный downside hedge: в худшем сохранённом DD SOL-вклад0; в другом окне SOL−83435.44387200 при BTC0. Правильный unrestricted-parent R3 с иной постепенностью потерял много на SOL — saved evidence подтверждает важность реально удерживаемого количества, но не даёт независимого чистого эффекта каждого правила.

**Следующее решение — признать различия механизма и остановить несопоставимое угадывание.** Из этих данных нельзя ни переносить Stage5/6 в продукт, ни обещать повтор A под locked K/no-SOL-interference. Любой будущий контракт должен явно решить market permissions и group-vs-independent exit lifecycle; K60, нативные деньги и BTC правила остаются неизменными. Нового кандидата/сетки/порогов этот аудит не предлагает.
