from datetime import datetime, timedelta, timezone

from coinmaster.domain.wave_overlay import Candidate, DailyBar, Episode, Features, WaveOverlayState, batch_features_for, features_for, linear_quantile


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
    assert before == batch_features_for(source, Candidate())


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


def test_same_day_btc_fill_earns_sol_right_only_after_parent_terminal() -> None:
    source = bars(1)
    feature = Features(0, 1, 1.0, 1.0, 0.0, 1.0, 2.0)
    state = WaveOverlayState(Candidate())
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=10, btc_open_qty=10, btc_entry_vwap=source[0].btc_close / 1.02, h=100, wave_levels=(0.01, 9.0, 9.0))
    reductions = state.decide(source, [feature], 0, 10_000)
    assert [item.action for item in reductions] == ["BTC_REDUCE"]
    state.on_fill(reductions[0].id, 1.5, 102, source[0].close_time)
    state.on_parent_terminal(reductions[0].id)
    additions = state.decide(source, [feature], 0, 10_000)
    assert [(item.action, item.requested_notional) for item in additions] == [("SOL_ADD", 10 * source[0].btc_close / 1.02)]


def test_zero_fill_parent_retries_next_decision_not_same_decision() -> None:
    source = bars(2)
    feature = Features(0, 1, 1.0, 1.0, 0.0, 1.0, 2.0)
    state = WaveOverlayState(Candidate())
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=10, btc_open_qty=10, btc_entry_vwap=source[0].btc_close / 1.02, h=100, wave_levels=(0.01, 9.0, 9.0))
    first = state.decide(source, [feature, feature], 0, 10_000)[0]
    state.on_parent_terminal(first.id)
    assert state.decide(source, [feature, feature], 0, 10_000) == []
    retry = state.decide(source, [feature, feature], 1, 10_000)
    assert retry[0].action == "BTC_REDUCE"


def test_sol_timeout_exits_when_features_are_invalid() -> None:
    source = bars(16)
    invalid = Features(15, 1, None, None, None, None, None)
    state = WaveOverlayState(Candidate(sol_max_holding_days=14))
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_qty=7, sol_first_fill_at=source[0].close_time)
    intents = state.decide(source, [invalid] * len(source), 15, 10_000)
    assert [(item.action, item.quantity) for item in intents] == [("SOL_EXIT", 7)]
