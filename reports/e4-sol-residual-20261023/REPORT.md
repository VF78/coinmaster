# E4 + защита остаточного SOL

Пакет в работе, полных native-прогонов ещё нет. [PLAN](PLAN.md) и [protocol](protocol.json) фиксируют R1/R2 до расчёта. [Project #123](https://github.com/VF78/coinmaster/issues/123) переиспользован, фактический In Progress подтверждён. Предыдущий отрицательный пакет не переписывается.

R1 расширяет старую защиту S на подтверждённый native BTCflat. R2 с теми же DD40/adverseSOL2%/halfactual50% проверяет полную реальную минутную пару вместо часовой задержки. Прибыльные BTC-fallback и обычные BTC-TP→SOL-права сохраняются. Пилот/production/services/deployment/secrets/orders исключены.

Контроли [S0/E4/XS](controls.json) сохранены. Acceptance TOTAL≥5470396.514987347 и global settled-minute DD≤50%,0liquidations, полные native receipts. Пока экономический результат неизвестен; адресные тесты и review не заменяют полный портфельный расчёт.

Первый новый P0 должен точно воспроизвести XS при отключённых новых flags. Максимум4 физических попытки: P0,R1,R2,pass-only repeat. S0/E4 не пересчитываются, широкой оптимизации нет. Все последующие размеры и издержки считает единственный native Nautilus BacktestEngine.

Saved-path [precheck](precheck.md) показывает границы: старый XS имел раннюю DD52.5801% при ещё открытомBTC и январскую SOL-only DD58.9474%. Поэтому одна flat eligibility не даёт доказательства цели. Данные не доказывают minute witnesses без нового причинного исполнения.
