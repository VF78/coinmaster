Материалы полного аудита CM2 SOL V1

- [Итог и дальнейший план](README.md)
- [Финансовая квалификация полного прогона](cases/FULL/committed-wm-qualification-v1/QUALIFICATION.json)
- [Полный фактический анализ BTC/SOL](audits/SOL_FULL_NATIVE_ANALYSIS.md) · [JSON](audits/SOL_FULL_NATIVE_ANALYSIS.json)
- [Все 16 SOL-эпизодов](audits/SOL_FULL_NATIVE_SOL_CYCLES.csv)
- [Все 85 просадок BTC и покрытие SOL](audits/SOL_FULL_DRAWDOWN_PRESENCE.md) · [319 контрольных точек](audits/SOL_FULL_DRAWDOWN_PRESENCE_ALL85.csv)
- [Причины провала модели SOL V1](audits/SOL_V1_FULL_MODEL_DIAGNOSIS.md)
- [BTC: различия 83 эпизодов](audits/SOL_FULL_BTC_CYCLE_DIFF.csv) · [исполнения](audits/SOL_FULL_BTC_FILL_DIFF.csv)
- [Префикс и full: ограничения буквальной идентичности](audits/SOL_PREFIX_FULL_INVARIANCE.json)
- [Ускорение аудита: проверка на сохранённых Native-результатах](audits/SOL_AUDIT_DEFER_PREFIX_EQUIVALENCE.md) · [наблюдаемые состояния](audits/SOL_AUDIT_DEFER_PREFIX_EQUIVALENCE_EXPORTED_STATE.json)
- [Почему расходится внутренний pickle-хеш](audits/NATIVE_POSITION_PICKLE_CROSSRUN_IDENTITY_README.md)
- [Неизменяемый K60](volatility/IMMUTABLE_CONTRACT.json) · [все 15 запрошенных комбинаций дат/окон](volatility/REQUESTED_15_ROWS.csv) · [исследование](volatility/RESULT.md)
- [Исходная экономика SOL эталона](reference-sol-audit/REFERENCE_SOL_NATIVE_ECONOMICS.md)
- [Все файлы, исходные SHA и оставленные локально крупные артефакты](PUBLICATION_MANIFEST.json)

Исходный полный прогон выполнен на c411; текущая публичная версия 2fdaab92 содержит только дополнительное исправление медленного аудита. Синтетический E08 доказывает наблюдённые операции и не является показателем ROI. Предыдущие BTC-only результаты и неудачные варианты сохранены в соседнем каталоге ../results/.
