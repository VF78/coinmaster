# Native component closure review — 25.10.2026

**Компоненты подтверждены; общий статус HOLD, prefix НЕ ДОПУЩЕН.** Ledger SHA `c0b84b39c5199671a258a8dcda6301ef3fd641f64be357e8c165be3aa0ffa424`:6/6 закрыты,2COMPLETED/4FAILED,active0/authorizedremaining0. Prefix0/3HOLD.

Physical2/rc0 подтверждает stock positive admission, partialFIRST10, originalS0=158.125 без возврата missingFIRST, lockedcap7.575→grant165.700, nativeoriginalGTC98.5/secondfills158.125, настоящие3TP, accountidentity/naturalflat/orders0. Ранние disposal warnings сохранены, cleanlifecycle этому процессу не приписывается.

Physical4/rc0 подтверждает oldlate1 и новые actual releasefills2+3 с nativeIDs, cap/oneattempt/ordinaryTP immediatecancel и lateexcess correction; после correction held126.099=cap126.099 и право dead. Native3TP/accountidentity/naturalflat/orders0 подтверждены; actual STOPPED→DISPOSED lifecycle clean. По raw snapshots actual positive TP fills сопоставлены всем уровням0/1/2 для2и4.

Physical6 **остаётся FAILED/rc1**. До tuple.clear ошибки raw native доказывает CURRENT_THREE_TP_ACK_UNKNOWN1→доставка реальногоACK→POST_ONLY_CROSS1, grants0/submits0/actualreleases0, lockedcap158.125. Это только component evidence. Stock marginDENY и fresh recovery не достигнуты/NOT_PROVEN, поэтому инженерного допуска нет. C0 standalone nativefixture также NOT_RUN; прежнее условное contractdisposition не отменяет criticalmargin gate.

Actual TierMarginPolicy содержит static `_marks` tuple и отдельный dynamic `_dynamic_marks` dict. `margin_for` использует любой допустимый источник. Proposed missing/stale fault должен учитывать оба, сохранить реальную policy/profile/leverage/maxage и восстановиться через настоящий update_mark. Нужен engine-free proof реального класса до запроса отдельно утверждённого+1; gate=True/mock не подходит. Exact repair ещё не рассмотрен.

Ранний a0-engineering-component-results.json описывает5attempts и не является текущим budgettruth; authority — закрытый ledger6 и closedresults. Reviewer не запускал tests/engines/streams, не менял source/ledgers/gates. Никакого дополнительногоengine/rootGO/prefix/full/deployment этот review не разрешает. Все failures/предыдущие reviews сохранены.
