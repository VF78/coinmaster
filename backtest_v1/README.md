# BTC Perp Backtest (v1 contour)

Рабочий контур бэктеста стратегии v1 для Hyperliquid BTC perp.

## Что уже реализовано

- Загрузка данных:
  - `hyperliquid` (по умолчанию) через `candleSnapshot` с чанкингом,
  - `csv`,
  - `synthetic` fallback.
- Сигналы v1 (аппроксимация):
  - engulfing + local sweep на 5m/15m/1H,
  - FVG inversion + retest fallback на 1H/4H.
- Риск/позиция:
  - риск на сделку 1.25%,
  - stop = структура + ATR-буфер + cap 0.70%,
  - partial: 1.0R / 2.2R / 3.8R (40% / 35% / 25%),
  - daily hard-stop 20%.
- Выходы:
  - SL,
  - partial TP,
  - BE после TP1,
  - ATR trail после TP2,
  - full-exit по reverse signal или time-stop.
- Отчёт:
  - `trades.csv`, `equity_curve.csv`, `summary.csv`.

## Запуск

Из корня workspace:

```bash
python3 -m backtest_v1.run_backtest
```

## Выходные файлы

- `backtest_v1/out/trades.csv`
- `backtest_v1/out/equity_curve.csv`
- `backtest_v1/out/summary.csv`

## Важные замечания

- В Hyperliquid исторический диапазон может быть короче запрошенного. Скрипт печатает фактически использованный диапазон (`actual_start` / `actual_end`).
- Логика FVG/engulfing в коде — системная аппроксимация под бэктест; её можно ужесточать после ручной валидации на разметке.

## Следующий шаг

- Прогон walk-forward (3m train / 1m test / 1m step) + sensitivity по slippage/fees.
