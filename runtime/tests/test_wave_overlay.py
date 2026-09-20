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


def test_resting_btc_targets_do_not_block_opposite_regime_close() -> None:
    source = bars(1)
    state = WaveOverlayState(Candidate(wave_min_count=1))
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=10, btc_open_qty=10, btc_entry_vwap=100, h=100, wave_levels=(0.01, 0.02, 0.03))
    targets = state.plan_confirmed_btc_targets()
    assert len(targets) == 3
    assert set(item.id for item in targets) == state.episode.resting_reductions
    opposite = Features(0, -1, 1.0, 0.0, 0.0, 1.0, 0.0)
    closes = state.decide(source, [opposite], 0, 10_000)
    assert [(item.action, item.reason) for item in closes] == [("CLOSE_ALL", "REGIME")]


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


def test_same_day_add_precedes_coincident_timeout_then_exit_after_fill() -> None:
    source = bars(16)
    feature = Features(15, 1, 1.0, 1.0, 0.0, 1.0, 4.0)
    state = WaveOverlayState(Candidate(sol_max_holding_days=14))
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_qty=7, sol_first_fill_at=source[0].close_time, sol_rights={0})
    add = state.decide(source, [feature] * len(source), 15, 10_000)
    assert [item.action for item in add] == ["SOL_ADD"]
    state.on_parent_terminal(add[0].id)
    assert [item.action for item in state.decide(source, [feature] * len(source), 15, 10_000)] == ["SOL_EXIT"]


def test_timeout_preemption_toggle_blocks_a_coincident_sol_add() -> None:
    source = bars(16)
    feature = Features(15, 1, 1.0, 1.0, 0.0, 1.0, 4.0)
    state = WaveOverlayState(Candidate(sol_max_holding_days=14, sol_timeout_preempts_add=True))
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_qty=7, sol_first_fill_at=source[0].close_time, sol_rights={0})
    assert [item.action for item in state.decide(source, [feature] * len(source), 15, 10_000)] == ["SOL_EXIT"]


def test_sol_overlay_toggle_keeps_btc_episode_but_emits_no_sol_add() -> None:
    source = bars(1)
    feature = Features(0, 1, 1.0, 1.0, 0.0, 1.0, 4.0)
    state = WaveOverlayState(Candidate(sol_overlay_enabled=False))
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_rights={0})
    assert state.decide(source, [feature], 0, 10_000) == []


def test_episode_fixed_beta_uses_entry_beta_with_rolling_z_distribution() -> None:
    source = bars(2)
    # The supplied rolling relative is neutral, while the entry beta makes the
    # current two-bar relative positive enough to cross the test threshold.
    feature = Features(1, 1, 1.0, 0.0, 0.0, 1.0, 0.0)
    state = WaveOverlayState(Candidate(relative_days=1, sol_entry_z=(0.001, 9, 9), episode_fixed_beta=True))
    state.episode = Episode("episode", 1, 10_000, 0.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_rights={0})
    assert [item.action for item in state.decide(source, [feature, feature], 1, 10_000)] == ["SOL_ADD"]


def test_episode_fixed_beta_ignores_a_stored_sigma_and_uses_current_rolling_sigma() -> None:
    source = bars(2)
    feature = Features(1, 1, 1.0, 0.0, 0.0, 1.0, 0.0)
    candidate = Candidate(relative_days=1, sol_entry_z=(0.001, 9, 9), episode_fixed_beta=True)
    first = WaveOverlayState(candidate)
    first.episode = Episode("first", 1, 10_000, 0.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_rights={0}, fixed_sigma=0.000001)
    second = WaveOverlayState(candidate)
    second.episode = Episode("second", 1, 10_000, 0.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_rights={0}, fixed_sigma=9999)
    assert [item.action for item in first.decide(source, [feature, feature], 1, 10_000)] == ["SOL_ADD"]
    assert [item.action for item in second.decide(source, [feature, feature], 1, 10_000)] == ["SOL_ADD"]


def test_strict_tp_cycle_allows_only_the_right_decision_cycle() -> None:
    source = bars(2)
    feature = Features(0, 1, 1.0, 1.0, 0.0, 1.0, 4.0)
    candidate = Candidate(sol_late_entry_after_tp=False)
    same_cycle = WaveOverlayState(candidate)
    same_cycle.episode = Episode("same", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_rights={0}, sol_right_decision_index={0: 0})
    assert [item.action for item in same_cycle.decide(source, [feature, feature], 0, 10_000)] == ["SOL_ADD"]
    later = WaveOverlayState(candidate)
    later.episode = Episode("later", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_rights={0}, sol_right_decision_index={0: 0})
    assert later.decide(source, [feature, feature], 1, 10_000) == []


def test_invalid_current_beta_blocks_sol_add_but_not_timeout_exit() -> None:
    source = bars(16)
    invalid = Features(15, 1, None, 1.0, 0.0, 1.0, 4.0)
    state = WaveOverlayState(Candidate(sol_max_holding_days=14))
    state.episode = Episode("episode", 1, 10_000, 1.0, btc_initial_qty=1, btc_open_qty=1, btc_entry_vwap=100, h=100, sol_qty=7, sol_first_fill_at=source[0].close_time, sol_rights={0})
    assert [item.action for item in state.decide(source, [invalid] * len(source), 15, 10_000)] == ["SOL_EXIT"]


def test_regime_reason_permits_same_cycle_reentry_but_trail_does_not() -> None:
    state = WaveOverlayState(Candidate())
    state.episode = Episode("episode", 1, 1, 1, close_reason="REGIME")
    assert state.on_group_flat() == "REGIME"
    state.episode = Episode("episode", 1, 1, 1, close_reason="TRAIL")
    assert state.on_group_flat() == "TRAIL"


def test_group_flat_clears_episode_so_the_next_daily_decision_can_reenter() -> None:
    source = bars(600)
    candidate = Candidate(wave_min_count=1)
    features = features_for(source, candidate)
    state = WaveOverlayState(candidate)
    index = next(index for index, feature in enumerate(features) if feature.beta is not None and 0.2 < feature.beta < 4 and state.decide(source, features, index, 10_000))
    state.episode.close_reason = "REGIME"  # type: ignore[union-attr]
    assert state.on_group_flat() == "REGIME"
    assert state.episode is None
    assert state.decide(source, features, index + 1, 10_000)[0].action == "BTC_ENTRY"


def test_z_requires_exact_previous_calendar_window_including_invalid_values() -> None:
    source = bars(8)
    # Flat BTC makes beta invalid and inserts None rather than retaining an
    # older valid relative observation.
    flat = [DailyBar(item.open_time, item.close_time, item.available_at, 100, 100, item.sol_close) for item in source]
    candidate = Candidate(beta_days=2, relative_days=1, z_history_days=2)
    assert features_for(flat, candidate) == batch_features_for(flat, candidate)
    assert all(item.z is None for item in features_for(flat, candidate))
