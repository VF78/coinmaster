# BACKTEST_SPEC_V1.md

Дата: 2026-02-12 (Europe/Madrid)
Статус: approved v1 inputs

## 1) Цель
Посчитать baseline ROI/expectancy стратегии на BTC perp (Hyperliquid) по фиксированным параметрам v1.

## 2) Период и данные
- Период теста: 2024-01-01 00:00 UTC → вчерашний день 23:59 UTC.
- Инструмент: BTC perp.
- Таймфреймы:
  - контекст: 4H / 1H,
  - триггер: 15m / 5m / 1m.
- Источник данных: Hyperliquid historical candles/trades (или эквивалентный достоверный источник с сопоставимыми свечами).

## 3) Логика входа (v1)
### Long
1. Режим поиска long активирован пользователем (bias=long).
2. Проверка 5m/15m/1H:
   - если есть engulfing + sweep локального минимума на текущей/поглощающей свече → вход.
3. Если п.2 не выполнен и цена растёт:
   - ждём inversion ближайшего значимого FVG на 1H/4H,
   - после прохода выше FVG ждём ретест и входим.

### Short
Зеркальная логика (bias=short, sweep локального максимума и inversion вниз).

## 4) Управление позицией (фиксировано)
- Risk per trade (BTC phase): 1.25% equity.
- Stop-loss: структура + ATR-буфер + max cap 0.70%.
- Частичная фиксация:
  - TP1 = 1.0R, закрыть 40%
  - TP2 = 2.2R, закрыть 35%
  - TP3 = 3.8R, закрыть 25%
- Hard-stop дня: при дневной просадке 20% закрыть все позиции и stop trading до следующего дня.

## 5) Транзакционные издержки (для baseline)
- Fee model baseline (Hyperliquid tier-0 ориентир):
  - taker: 0.045% / side,
  - maker: 0.015% / side.
- Рабочее blended-допущение v1: 0.03% / side.
- Slippage baseline: 0.03% / side.
- Чувствительность: прогнать сценарии slippage 0.02% / 0.05%.

## 6) KPI отчёта
- ROI total и CAGR-like annualized.
- Max Drawdown (equity), time-under-water.
- Profit Factor, Win Rate, Avg R per trade, Expectancy.
- Distribution:
  - доля сделок: стоп / TP1-only / TP2+ / TP3,
  - MAE/MFE.
- Stability:
  - по кварталам,
  - по волатильностным режимам.

## 7) Walk-forward
- Train window: 3 месяца.
- Test window: 1 месяц.
- Step: 1 месяц.
- Параметры входа фиксированные, адаптируются только пороги фильтров (если будет этап v1.1).

## 8) Критерии «go / no-go» для перехода к paper trading
- Expectancy > 0 после всех издержек.
- Max DD в допустимом диапазоне риск-политики.
- Нет деградации в большинстве out-of-sample окон.
- Отсутствие критической зависимости от 1-2 выбросных сделок.

## 9) Следующий этап (после BTC)
- При успешном BTC-тесте: добавить ETH и SOL с пониженным риском на сделку и портфельными лимитами.
