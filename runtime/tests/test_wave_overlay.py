from datetime import datetime, timedelta, timezone

from coinmaster.domain.wave_overlay import Candidate, DailyBar, WaveOverlayState, features_for, linear_quantile


UTC = timezone.utc


def bars(count: int = 600, start_day: int = 0):
    start = datetime(2023, 1, 1, tzinfo=UTC)
    result = []
    for offset in range(count):
        day = start_day + offset
        # Oscillation gives non-zero variance and numerous completed EMA waves.
        btc = 100 + day * 0.04 + (6 if (day // 20) % 2 else -6) + (day % 5) * 0.1
        sol = 30 + day * 0.02 + (btc - 100) * 0.30 + (3 if (day // 17) % 2 else -3) + (day % 7) * 0.1
        close = start + timedelta(days=day + 1)
        result.append(DailyBar(close - timedelta(days=1), close, close, btc - 0.2, btc, sol))
    return result


def test_linear_quantile_keeps_zero_waves() -> None:
    assert linear_quantile([0, 0, 1, 3], 0.5) == 0.5


def test_features_are_causal_and_z_excludes_current_value() -> None:
    source = bars()
    before = features_for(source, Candidate())
    after = features_for(source + bars(3, len(source)), Candidate())
    assert before == after[:len(before)]
    ready = next(item for item in before if item.z is not None)
    assert ready.sigma is not None and ready.sigma > 0


def test_episode_uses_confirmed_fills_and_fixed_sigma() -> None:
    source = bars()
    candidate = Candidate(wave_min_count=1)
    features = features_for(source, candidate)
    state = WaveOverlayState(candidate)
    index = next(i for i, feature in enumerate(features) if feature.beta is not None and 0.2 < feature.beta < 4)
    # Wave history may not be available at the first valid beta; find a causal entry candidate.
    while not state.decide(source, features, index, 10_000):
        index += 1
    entry = state.episode.pending.copy()
    intent = next(iter(entry.values()))
    assert state.episode.btc_initial_qty == 0
    state.on_fill(intent.id, 1, source[index].btc_open, source[index].close_time)
    assert state.episode.btc_initial_qty == 1
    state.on_parent_cancelled(intent.id)
    assert state.episode.h is not None
    state.on_liquidation()
    assert state.decide(source, features, index + 1, 10_000) == []
