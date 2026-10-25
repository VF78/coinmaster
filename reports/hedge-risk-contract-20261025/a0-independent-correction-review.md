# A0 focused correction review — 25.10.2026

**PASS_SOURCE_CORRECTION_PENDING_ROOT_GO_AND_NATIVE_EVIDENCE. Открытых P0=0/P1=0.** Source `340f90f6d0c9c46963f5dcc6f8c96bf015539fdc`. Исходный review сохранён без изменения.

A0-S01 закрыт: `_a0_targets_ready` требует authorized/required/accepted всех3 уровней текущего поколения, три собственных actual cache reduce-only ACCEPTED ордера с корректным order_generation и суммой leaves==held. При UNKNOWN/cancel/replacement ACK cap/grant не меняются. Живые TP остаются защитой, не debt. В A05 добавлена задержка реальных acceptance callbacks после native targetcancel/replacement, denial до ACK и последующая доставка исходных событий. Это план assertions, ещё не nativePASS.

A0-S02 закрыт: `_a0_stop` немедленно вызывает nativecancel A0-owned live/inflight release в том же ordinary stop callback, до возврата из-за historical p.closed. Уже pendingcancel/terminal не отменяются повторно. A03 теперь проходит partial/resting release→actualTP→запрос cancellation внутри fillcallback→преднамеренно задержанный transport/latefill→debt reconciliation; проверяет held≤cap, cap≤tp_cap, dead/attempted и единственный submit. Старая native history остаётся закрытой. Фактический lifecycle ещё NOT_RUN.

Те же6 IDs/6 constructors; correction не добавил engines. Каждый data window [0,3600e9]ns, один час; counting/root source gate сохранены. StockProbe по-прежнему вызывает настоящий `WaveOverlayStrategy._tier_allows_increase`; A05 stock stale/missing marksDENY сохранён. Новые monetary/margin модели не введены.

Frozen correction/plan/gate hashes совпали с заданием; hashes трёх исправленных sourcefiles совпали с gate sourcepins. Pure45PASS,815feedrows,31inputs/222sourcepins — отчёт исполнителя; reviewer tests/engines=0, полные старые inputs/suite повторно не аудировались. Diff ограничен A0rights/его runner/puretests; core/family/fees/sharedliquidity не менялись этим correction.

Проверенные SHA256:

- correction: `adfe09ddfaba4ef71711493455e8f338fa65f92ad7730271fce6e14b06023836`
- plan: `abae88c5c185fae8302141a205bd8a31efb6b5952937aa2721fb77379ad6fbc4`
- gate: `848c38fc1c15219998a89cd3601393b3a1949ee3233dbeaac2788e8d78b4b36c`

RootGO остаётся false. Review не даёт rootGO/native/prefix/full/deployment прав; actual cash/TP/stockmargin/latefill результаты остаются предметом ограниченного инженерного запуска под root gate. Записаны только новые correction-review JSON/MD; source/gate/ledgers не менялись.
