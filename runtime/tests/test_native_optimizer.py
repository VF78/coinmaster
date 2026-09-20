from coinmaster.research.native_optimizer import causal_v1_coarse_variants, causal_v1_refinement2_variants, causal_v1_refinement_variants, causal_v1_sensitivity_variants, candidate_variants


def test_compact_optimizer_grid_keeps_immutable_v0_and_only_varies_candidate_controls() -> None:
    variants = dict(candidate_variants())
    assert tuple(variants) == (
        "v0",
        "btc_notional_minus_10pct",
        "btc_notional_plus_10pct",
        "sol_z_minus_0125",
        "sol_z_plus_0125",
    )
    assert variants["v0"].btc_notional_multiplier == 9.0
    assert variants["btc_notional_minus_10pct"].btc_notional_multiplier == 8.1
    assert variants["btc_notional_plus_10pct"].btc_notional_multiplier == 9.9
    assert variants["sol_z_minus_0125"].sol_entry_z == (1.125, 2.375, 3.625)
    assert variants["sol_z_plus_0125"].sol_entry_z == (1.375, 2.625, 3.875)


def test_causal_v1_grid_is_btc_only_with_explicit_v0_and_bounded_refinement() -> None:
    coarse = dict(causal_v1_coarse_variants())
    assert tuple(candidate.btc_notional_multiplier for candidate in coarse.values()) == (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.5, 6.48, 9.0)
    assert coarse["v0"].btc_notional_multiplier == 9.0
    assert all(candidate.sol_entry_z == coarse["v0"].sol_entry_z for candidate in coarse.values())
    assert tuple(candidate.btc_notional_multiplier for _, candidate in causal_v1_refinement_variants(2.0)) == (1.8, 1.9, 2.1, 2.2)


def test_causal_v1_refinement2_is_the_exact_authorized_bracket_only() -> None:
    variants = causal_v1_refinement2_variants()
    assert tuple(candidate.btc_notional_multiplier for _, candidate in variants) == (2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9)
    assert all(candidate.sol_entry_z == variants[0][1].sol_entry_z for _, candidate in variants)


def test_causal_v1_sensitivity_is_control_plus_independent_authorized_axes() -> None:
    variants = dict(causal_v1_sensitivity_variants())
    assert len(variants) == 15
    assert variants["control_2.4"].btc_notional_multiplier == 2.4
    assert variants["sol_entry_z_shift_-0.125"].sol_entry_z == (1.125, 2.375, 3.625)
    assert variants["relative_days_60"].relative_days == 60
    assert variants["beta_days_285"].beta_days == 285
    assert variants["z_history_days_165"].z_history_days == 165
    assert variants["wave_history_days_745"].wave_history_days == 745
    assert variants["sol_max_holding_days_9"].sol_max_holding_days == 9
    control = variants["control_2.4"]
    assert all(sum(left != right for left, right in zip(candidate.__dict__.values(), control.__dict__.values())) == 1 for key, candidate in variants.items() if key != "control_2.4")
