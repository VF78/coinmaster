# Воспроизведение экспорта и границы повторного scoring

Этот каталог хранит завершённое ограниченное сравнение. Экспорт читает только frozen result, freeze, seals, сырые ответы и архив; новые прогнозы, обучение, рыночные данные и scoring не запускаются.

Из корня worktree:

```sh
/Users/vf/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 reports/btc-pattern-pilot-m2-20261021/inapp-chatgpt-protocol-20261022/export_report.py
```

Достаточен Python 3 standard library. Экспорт заново создаёт REPORT.md, summary.json, cases.csv и forecast-details.csv и этот README; frozen/evaluation-results.json не изменяется. CSV содержат 72 и 432 строки данных соответственно, плюс заголовок. Строки упорядочены по origin, затем P/C/prior, long/short, SL=.75/1/1.5.

Проверки перед экспортом: result SHA256=bb056b3e297b93cb5e28238895b5e2501b698811582bceb2fa3a9eef80a7e72d; freeze SHA256=7ea0cd8c624ef72cab364dbc337f4d7d4895fa0c2c33baadce67cd82ee435755 совпадает с evaluation seal; 10 debug и 48 evaluation сырых ответов проверяются по SHA256 из seals; prompt/schema и все 87 packet/chart файлов в архиве также соответствуют freeze. Итог PASS и SHA256 архива отражены в summary.json. Проверки используют исключения assert, поэтому не запускать Python с -O.

Архив входов frozen-input-packets.tar.gz имеет SHA256=39dc8a6764e07b337cae1c866471222f91f646f7e77bdcc3a770126e6a86e81b. Он сохраняет исходные packet.json и chart.png; сырые ответы отдельно находятся в raw-responses/. Freeze содержит хеши пакетов, prompt/schema, source и шести prepared-массивов. Исходный freeze закреплён до раскрытия truth; статус READY в нём исторический, итоговый статус находится в evaluation-results.json. PROTOCOL_PROPOSAL.md также сохраняет исходную формулировку предложения, а не текущий статус завершённого опыта.

Повторный scoring — отдельная операция, здесь она не выполнялась. Для него нужен исходный закреплённый prepared-набор, включая metadata.npy и minutes.npy, а для полной проверки происхождения — все шесть массивов из source_hashes, исходный manifest (SHA256 bc660056af9117a246a1334837b7e42c9bb2d0635945a0346a4b088a459685ff), source и зависимости с точными версиями. Архив packet/chart и ответы сами по себе не содержат все будущие минутные пути и не заменяют prepared. Предыдущий bootstrap seed=7 не фиксирует генерацию языковой модели; backend snapshot, sampling seed и temperature не закреплены интерфейсом. Повторный вызов forecaster не является точным воспроизведением.

Для отдельного разрешённого повторного scoring следует создать свежий scratch-каталог с копиями freeze/seal и ответов, проверить исходные SHA256 и prepared source_hashes, восстановить пути prepared и response_path в производных копиях и пересчитать freeze_sha256 в производной seal. Исходные файлы и их хеши сохраняются; изменения путей документируются как relocation, не новый запуск. У scratch-копии не должно быть evaluation-results.json: scorer намеренно отвергает существующий результат с RESULT_ALREADY_EXISTS. Из worktree root с PYTHONPATH=runtime вызывается модуль coinmaster.research.btc_pattern_inapp, команда score-after-seal --freeze <scratch/freeze.json>. Нельзя запускать эту команду на оригинальном freeze и нельзя удалять/перезаписывать исходный результат. Сравниваются числовые поля и cases производного результата с закреплённым результатом; абсолютные пути receipt могут различаться. Для повторного bootstrap требуется NumPy; версии среды должны быть записаны отдельно.

Текущий отчёт — экспорт единственного уже выполненного scoring. FEASIBILITY_PASS означает валидный формат/покрытие; exploratory_signal=false и window_bundle_incremental=false. Финансовой оценки, будущего запуска и допуска к эксплуатации этот каталог не предоставляет.
