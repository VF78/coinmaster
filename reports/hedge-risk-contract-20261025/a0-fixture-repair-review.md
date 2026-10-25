# A0 fixture-only repair review — 25.10.2026

**PASS_FIXTURE_REPAIR_PENDING_ROOT_GO_AND_NATIVE_EVIDENCE; P0=0/P1=0.** Source `541e0c564a2bb79411809186113c78a4d3a80a5a`.

Минимальное исправление соответствует причине failedA01: start=-86400000ms закреплён в actual kwargs и helpercontext, поэтому при completedday2ns stock guard current−1day≥start выполняется. Guard не изменён/не обойдён. Причинные seed доступны не позднее2ns, максимум0ns;50purePASS исполнителя включает5 проверок AST реального guard=False. Quotes/engine data остаются [0,1h], config[-1day,+1h]=25h≤48h. Эти purechecks не доказывают native lifecycle.

Runner содержит ровно A02..A06, по одному counted constructor. FailedA01 остаётся physical1/FAILED/source340, без retry; пять оставшихся занимают physical2..6 в прежнем cap6. A01 shared registered sizing/stockmargin/cancelACK/OFF+60/originalGTC/partial-full/real3TP покрываются общим A02 и full-first A03/A04/A05. Исправленные targetACK/ordinaryTP immediatecancel/latefill assertions сохранены. StockProbe продолжает настоящий stock margin/freefunds gate. Следующего определённого противоречия setup/assertions при статическом чтении не найдено.

Сравнение непроизводных файлов runtime/coinmaster между340 и541 показало отсутствие изменений product source; отличаются только generated __pycache__ bytecode. Diff исправляет ровно два tests-файла. Reviewer не запускал tests/engines и не менял source/bytecode/ledgers/gate.

Точные freeze hashes проверены:

- repairdiff: `cf78b76b1fd1d60d330f6679e97aa406267aaa871bfbcb3f5e46e5ab21ab7e03`
- plan: `05165207eecbdd11ac47397051bad4e9819ec0d6fc8a8a91e63881127fec9e3a`
- gate: `9e86f41c307153fa905a1b06ca017a5c8cd1cb9f62b7db55bb64ee87e975f04c`

Ledger при review:1FAILED/HOLD, prefix0. RootGO остаётся false; review не разрешает запуск и не добавляет budget. Первичная ошибка, предыдущие reviews и snapshots сохранены. Native outcomes остаются NOT_RUN для исправленных fixtures.
