from coinmaster.research.native_optimizer import candidate_variants


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
