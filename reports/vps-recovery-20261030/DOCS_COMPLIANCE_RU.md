# Сверка эксплуатации с Nautilus и systemd

Официальная документация прочитана; параметры дополнительно сверены с кодом установленного Native1.231.0. Некоторые latest/nightly и даже tag-doc примеры описывают Rust/Python-v2. Они не копируются в Cython1.231.0 вслепую.

| Рекомендация / источник | Применение |
|---|---|
| [Штатный Cache](https://nautilustrader.io/docs/latest/concepts/cache/) и [точный CacheConfig1.231](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/v1.231.0/nautilus_trader/cache/config.py) | Используется поддержанный DatabaseConfig Redis backend; NativeCache сохраняет нативные ордера/positions/eventlineage. Свой второй OMS не создаётся. |
| [Порядок инициализации kernel](https://github.com/nautechsystems/nautilus_trader/blob/27a8e54e7ac3c57d6cbf8891f0283dfbaee97317/nautilus_trader/system/kernel.py) | ExecEngine.load_cache выполняется до trader/reconciliation/start. ExistingSQLite остаётся единственным actor restore; load_state/save_stateFalse предотвращают второй загрузчик стратегии. |
| [Штатная reconciliation](https://nautilustrader.io/docs/latest/concepts/execution/reconciliation/) | Восстановленный cache сопоставляется с реальной venue; пропуски/UNKNOWN/чужая история не превращаются в подтверждённое владение. Старые поля freshness сами не разрешают команду. |
| [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/) | Отдельный loopback6380/auth/AOFalways/noeviction. Redis async cache и SQLite не являются одной транзакцией; missingcriticalhistory должен отклоняться существующей точной parity. Скрытого repair--fix нет. |
| [systemd255Restart](https://www.freedesktop.org/software/systemd/man/255/systemd.service.html#Restart=) и [dependency semantics](https://www.freedesktop.org/software/systemd/man/255/systemd.unit.html#Requires=) | Restartonfailure/15s/StartLimitIntervalSec0. Wants+After Redis, без Requires/BindsTo каскадного stop. Нормальный manualstop не должен превращаться в автоматический торговый restart. |
| [Эксплуатационные callbacks](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/v1.231.0/docs/how_to/configure_live_trading.md) | Проверяется горячий путь callback; измеренный лишний полный checkpoint сериализует warmup557KB на quote. Оптимизация допустима только с точной эквивалентностью durabledecision, без throttle/потери риск-изменений. |

Никаких дополнительных stockpurgeтаймеров вслепую: существующая точная parity использует retainedorders/fills. Tick/bar caches уже ограничены штатными capacity10000. `persist_account_events=False` в установленном коде отключает **все** account backingwrites — это не режим «только последний account». Поэтому изменение не применяется под неверным предположением. Объём реального account history до256MiB не объявляется измеренным.

Важное обнаруженное несоответствие: точный pyo3SHA97f3dc49…321e не имеет connection_epoch. Официальный RustHLclient самостоятельно обрабатывает reconnect; PythonAPI предоставляет is_active/is_closed/wait_until_active. Старое требование нашего wrapper несовместимо с этим API и снимало возможность честной qualification. Исправление использует реальные publichealth и новый явный verifiedsnapshot контракт; localgeneration не выдаётся за nativecounter.

Полные параметры/тесты/пределы новой qualification фиксируются после исходников и nativeW/R, а не выводятся из чтения документации.
