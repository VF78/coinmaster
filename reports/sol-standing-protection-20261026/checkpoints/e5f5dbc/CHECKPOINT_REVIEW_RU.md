# CM137 — первый source/fixture checkpoint, до native review

Текущий source: **e5f5dbc9278a08e4245e3ee7ddc9f2b7bf349acd**, parent ровно **7f38278257624b321c9d88d9df962505b6f5bab0**. Canonical VPS branch codex/sol-standing-protection-20261026 — CLEAN. Изменены только 12 перечисленных в SOURCE_CHECKPOINT.json файлов; прочее дерево совпадает с base по git diff. Source не опубликован и не развёрнут. Неполные локальные drafts 9a8c28e/eb272d2 сохранены private refs; они не являются текущим checkpoint.

**Engineering 0/6, prefix 0/4, full0, root_go=false.** Новых BacktestEngine constructors и native fixture dispatch/Popen0. Все старые ledgers/results/dirty worktree сохранены. Следующий шаг — независимое review текущего diff/STOP coverage/driver, затем отдельный root GO на один E1.

## Что реализовано

- DefaultOFF research_sol_standing_protection: ordinarySOLTP уменьшает только право своего level; неизменные OID/цены/leaves сохраняются. Public modify делает total=actualfilled+desiredleaves; один pending command/OID, latest desired после реального ACK, native UUID/history/ownership checks. Нулевой live level отменяется отдельно; consumed TP не создаётся заново. Gap clock и existing nextquote guard сохранены.
- ANY genuine STOP fill немедленно ставит closing barrier ещё до partial-IOC terminal Cancel. После него нет новой SOL protection generation/modify. Partial native STOP остаётся PARTIAL_NATIVE_STOP/NO_GO; TIF IOC и существующий BTC_DEBT/SOL_CLOSE conservative route сохранены.
- Public callback routing SOL Updated/ModifyRejected дополняет прежний BTC route. NativeBookWitness читает exact SOL state перед matching input и transient state на settlement; не отправляет commands и не меняет caps/rights. В economic mode одинаковые boundary states объединяются, counters считают каждый вызов.
- Predecision observer работает при paired research независимо от A0 trading flag. Точная phase: AFTER_PAIR_RISK_AND_MD_RECONCILE_BEFORE_A0_CHECK. Есть native input identity/instrument/timestamps/book epoch, original first allocation/actual first/second filled-ever, old-order state, remaining right, held/cap/debt/pending/current TP, riskOFF/+60, bid/ask/cross, actual mark age/native margins/account facts. Missing=UNKNOWN. Ничего не приписывает hypothetical fill/profit.
- Observer пишет risk-cancel/riskOFF/первую BTC quote после+60 и logical WAIT/state transitions; raw price motion не создаёт новый record. 1000 изменений цены в object test дали 3 records. Верхний предел10000 прекращает опыт с ошибкой, без silent truncation. Actual existing stock guard записывается отдельно ACTUAL_NATIVE_STOCK_MARGIN_RESULT; predecision stock_margin_invoked=false/UNKNOWN правдив.
- DefaultOFF research_btc_trim_control: собственный BTC-only absolute cap, без SOL orders/credit/PairedCaps. Causal coefficients добавлены из тех же frozen CSV fields; прежние a/values/clocks не менялись. Intended hedge variance, factor/orthogonal/total risk и точный Fraction/isqrt lot floor зарегистрированы до branch code в TRIM_IMPLEMENTATION_SPEC.json. Nominal TRIM horizon B2=4h/F0=8h от eligible; C0 first-actual-SOL-fill clock не менялся. Ни restore, ни rearm, ни mid-engine variant swap.

Original a0_rights.py, standing_tp.py и domain/wave_overlay.py byte-identical. AST bodies sol_prices/sol_allocations/PairedCaps, legacy SOL protect, actual native margin guard и financial runner неизменны. Новый SOL readiness guard стоит в _a0_targets_ready, после исходной off_ns/+60 инициализации; отдельный тест сохраняет clock. Metric contract SHA ca815cbe3b8e163b16ccca8e388c9299125f74f0e1dd10beaa3ee15e4fe31102 неизменен.

## Проверено без engine

VPS: 97/97 pure/object/exact-algebra PASS, py_compile PASS. Frozen Mac: 97/97 PASS, old standing proof10groups PASS, E1–E5 real config/kwargs roundtrip + AST/provider checks PASS; native1.231.0,354 installed native file pins. Проверки конструктора: new pure files0, stdlib supervisor0, fixture driver ровно1 uncalled constructor в child.

Mac source: /Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-standing-protection-20261026/source-e5f5dbc/runtime — 271 readonly files. SOURCE_SEAL.json фиксирует archive/source files; MAC_PREFLIGHT.json фиксирует native API/config/kwargs/transport. Linux и Mac имеют 7 libm ULP различий только в synthetic seed bars; actual Mac config frozen отдельно, kwargs payload идентичен. Это fixture data, не экономическая data mutation.

Stdlib --prepare реально завершился OS0: PREPARED_ENGINE0_NO_ATTEMPT, root_go=false, physical_started0. До STARTED/Popen wrapper проверяет source/native pins, exact approval/protocol, ledger-before SHA, pinned preflight/source/config/kwargs/static transport и fresh namespace; child повторяет live config/kwargs/transport checks до constructor intent. Каждый будущий launch durably claims UUID до child Popen, сохраняет PID/actual OS rc и возвращается в root hold, без autonext/retry. Old hardcoded4-budget drivers не импортируются.

## Native coverage — всё ещё UNKNOWN

FIXTURE_MAP.json содержит полные fixed-role schedules/gates:
E1=C0zero с actual STOP qty ACK + full trigger fill; E2=C0cancel2s с healthyDEFER/flatpendingSTOP и последним expected-negative partial-IOCSTOP; E3=fixedTRIM; E4=fixedA0stress; E5=fixedA0zero integration. Все positive/negative matching assertions **NOT_RUN**. E2 разрешает только заранее названный PARTIAL_NATIVE_STOP после terminalpartial stage и требует actual native recovery flat/orders0/inflight0 до end; это expected-negative test, а не fault-free financial PASS. Любой такой fault в economicC0/A0 остаётся NO_GO.

In-market STOP ModifyRejected source-excluded только в заявленном unchanged-trigger/update0/no-interposed-SOL-input route при ANY-STOP-fill closing barrier. Более широкая latency/venue safety UNKNOWN. Native reachability/ACK order/flat still требуют actual E1–E5 и root acceptance; pure source proof не означает financial/native PASS.

## Передача review

E1-root-false-gate.json SHA 4b96b178fb3dc5c3c23b1dcf5ec263147feebd0e0b8f1a6c0834b4fa2ddcba74.
Engineering ledger SHA 29217b9acbe0fd41495edfd77c08d1ad3c43f049856946a746bd7f02412e1511.
Prefix ledger SHA aefb8326a54ef028dac750233a2c9fad2ff44ef5acce8ed0ddcaab97ee14febf.
E1-argv.json содержит exact prepare argv и будущий launch argv; launch сейчас НЕ разрешён. CHECKPOINT_INDEX.json перечисляет актуальные artifact SHA.

Economic interface: paired_prefix_audit.{control_role,predecision_records,predecision_coverage,sol_boundary_counts,events}; в events есть ACTUAL_NATIVE_STOCK_MARGIN_RESULT и SOL lifecycle/native-boundary events. Это embedded report audit, пятого financial artifact role нет. BTC_TRIM artifact_label=BTC_TRIM; selectors остаются exact R2 C0 плюс отдельный trim flag. Future OFF/C0/TRIM/A0 только после полного engineering acceptance и каждого rootGO; expected OFF20911.13611487. Финансовые деньги/DD/ES/funding rules не менялись; экономических результатов здесь нет.
