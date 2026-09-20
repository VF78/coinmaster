import json

from coinmaster.research import native_optimizer
from coinmaster.research.native_optimizer import causal_v1_coarse_variants, causal_v1_refinement2_variants, causal_v1_refinement_variants, causal_v1_sensitivity_variants, candidate_variants
from coinmaster.domain.wave_overlay import Candidate


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


def test_stage_a_reuses_complete_candidate_tuples_and_only_extends_234_when_it_improves(tmp_path, monkeypatch) -> None:
    control_candidate = Candidate(btc_notional_multiplier=7.5)
    control = {
        "terminal_open_positions": 0,
        "liquidation_count": 0,
        "data_hash": "data",
        "policy_hash": "policy",
        "terminal_total": "10",
        "config": {"candidate": native_optimizer.asdict(control_candidate)},
    }
    control_path = tmp_path / "control.json"
    control_path.write_text(json.dumps(control))
    calls = []

    def fake_item(variant_id, candidate, _data_root, _stem):
        calls.append(native_optimizer._candidate_tuple_key(candidate))
        profile = candidate.sol_size_multipliers_h
        score = {2.0: 20, 3.5: 90, 5.0: 80, 6.5: 70}.get(candidate.btc_notional_multiplier, 10)
        if candidate.btc_notional_multiplier == 3.5 and profile == (1.5, 2.25, 3.0):
            score = 100
        if candidate.btc_notional_multiplier == 4.0 and profile == (1.5, 2.25, 3.0):
            score = 101
        if candidate.btc_notional_multiplier == 4.0 and profile == (1.75, 2.25, 3.0):
            score = 102
        if candidate.btc_notional_multiplier == 4.0 and profile == (2.0, 3.0, 4.0):
            score = 103
        return {
            "variant_id": variant_id,
            "candidate": native_optimizer.asdict(candidate),
            "candidate_hash": "fake",
            "status": "NOT_FAITHFUL_DIAGNOSTIC",
            "terminal_active": str(score),
            "terminal_reserve": "0",
            "terminal_total": str(score),
            "summary": {"roi": "0", "max_drawdown_percent": "0", "max_drawdown_amount": "0"},
            "fee_attribution": {"maker": {}, "taker": {}},
            "funding": {"signed_amount": "UNKNOWN", "count": 0},
            "fills": 0,
            "liquidation_count": 0,
            "native_fees": "0",
        }

    monkeypatch.setattr(native_optimizer, "_stage_a_item", fake_item)
    report = native_optimizer.run_stage_a_sizing(tmp_path, control_path)

    assert len(calls) == len(set(calls))
    reused = next(item for item in report["results"] if item["variant_id"] == "a2-btc-3.5-sol-1-1.5-2")
    assert reused["reused"] is True
    assert reused["reuse_provenance"]["variant_id"] == "a1-btc-3.5"
    assert any(item["variant_id"] == "a6-btc-4-sol-2.25-3.375-4.5" for item in report["results"])
    assert (tmp_path / "runs" / "native-stage-a-sizing-v1-top20.csv").exists()
    call_count = len(calls)
    resumed = native_optimizer.run_stage_a_sizing(tmp_path, control_path)
    assert len(resumed["results"]) == len(report["results"])
    assert len(calls) == call_count
    compact = native_optimizer.write_stage_a_compact_checkpoint(tmp_path, control_path)
    assert compact["result_count"] == 42
    assert compact["best"]["variant_id"] == report["best"]["variant_id"]
    checkpoint_path = tmp_path / "runs" / "native-stage-a-sizing-v1.partial.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint["results"].append({**checkpoint["results"][-1], "variant_id": "out-of-plan-resume-incident"})
    checkpoint_path.write_text(json.dumps(checkpoint))
    sealed = native_optimizer.run_stage_a_sizing(tmp_path, control_path)
    assert len(sealed["results"]) == 42
    assert all(item["variant_id"] != "out-of-plan-resume-incident" for item in sealed["results"])
    assert len(calls) == call_count
    corrected_target = checkpoint["results"][0]
    corrected = {**corrected_target, "execution_artifacts": {"fresh": {"path": "fresh.csv", "sha256": "fresh-hash"}}}
    correction_path = tmp_path / "runs" / "native-stage-a-sizing-v1-evidence-correction-v1.json"
    correction_path.write_text(json.dumps({
        "status": "SEALED_EVIDENCE_CORRECTION",
        "partial_sha256_before": native_optimizer.sha256_file(checkpoint_path),
        "replacements": {corrected_target["variant_id"]: corrected},
    }))
    corrected_resume = native_optimizer.run_stage_a_sizing(tmp_path, control_path)
    assert corrected_resume["local_evidence"]["correction"]["sha256"] == native_optimizer.sha256_file(correction_path)
    restored = next(item for item in corrected_resume["results"] if item["variant_id"] == corrected_target["variant_id"])
    assert restored["local_evidence"]["execution_artifacts"]["fresh"]["path"] == "fresh.csv"
    assert corrected_resume["local_evidence"]["excluded_resume_incident_count"] == 1
    assert len(calls) == call_count


def test_stage_a_migrates_existing_duplicate_tuple_to_explicit_reuse() -> None:
    candidate = native_optimizer.asdict(Candidate(btc_notional_multiplier=3.5))
    source = {"variant_id": "first", "candidate": candidate, "candidate_hash": "source", "terminal_active": "1", "terminal_reserve": "0", "terminal_total": "1", "fills": 1, "native_fees": "0", "funding": {}, "fee_attribution": {}}
    duplicate = {**source, "variant_id": "legacy-duplicate"}

    reconciled, changed = native_optimizer._stage_a_dedupe_existing([source, duplicate])

    assert changed is True
    assert reconciled[1]["reused"] is True
    assert reconciled[1]["reuse_provenance"]["variant_id"] == "first"
    assert native_optimizer._stage_a_dedupe_existing(reconciled)[1] is False
