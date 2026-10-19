# ALPHA: наблюдённая просадка незавершённого native observer

**TOTAL/ROI/settled cash/native flat: UNKNOWN (`null`).** Итогового native JSON/CSV нет; последний mark equity не назван итоговыми деньгами.

- Input: `/var/lib/coinmaster-native-gui/data/runs/jobs/cm115-split-alpha-cushion-swap768-20261019c/result/minute-native-risk.csv.gz`; SHA256 `bac6800e8826b13222349426dee5267ac0e9e156b9a3b57f7b147e3b1a7a802b`, 92,640,304B.
- Фактически декодировано завершённых CSV-строк: **3,153,111**; включено native close samples **3,153,111**, post-boundary исключено 0.
- Период фактических наблюдений: 2024-09-01T00:01:00+00:00 → 2026-08-31T21:17:00+00:00.
- Последнее наблюдённое native E: **932.61441154** — **НЕ TOTAL**, не settlement и не flat proof.
- Максимальная наблюдённая DD, **только нижняя граница**: **93.22642696640473090566302551%**.
- Peak: 2024-09-11T14:00:00+00:00, E=12484.37563522.
- Trough: 2026-08-30T13:46:00+00:00, E=845.63830144.
- Уже наблюдалось строго >50%: **True**. Если да, последующее восстановление не может отменить уже пройденную глобальную HWM-просадку. Это не оценка доходности и не разрешение нового прогона.
- Clean validated gzip EOF: **False**. Ошибка/усечение: `{'type': 'EOFError', 'message': 'Compressed file ended before the end-of-stream marker was reached'}`. Незавершённый возвращённый хвост: 0B, не использован. Никаких пропусков не заполнено.

Метод: один forward gzip stream вместе с SHA исходных сжатых байтов, только native `paired_close_equity`, реальный порядок callback phases. HWM начинается с первого наблюдённого E; explicit post-boundary settlement rows исключены. CSV header, phase counts, native позиции в peak/trough/последней точке сохранены в JSON. Денежный учёт, цены, PnL или fills не реконструировались. Conditional OHLC не использовался вместо native minute E. Точного full-run global DD не заявляем независимо от EOF: финансовый экспорт завершённого движка отсутствует.

Ресурсы: 105.78s, peak RSS 18,048KiB; nice19/idle IO. Источник не изменён; новых engines/tests/стратегий/сервисных действий нет.
