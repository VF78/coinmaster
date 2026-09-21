from __future__ import annotations

import json
from dataclasses import asdict, fields

import pytest

from coinmaster.domain.wave_overlay import Candidate
from coinmaster.ops.stage_g_config import (
    ConfigurationError,
    candidate_content_hash,
    canonical_candidate_json,
    load_candidate,
    load_instance_config,
)


STAGE_G = """{"candidate":{"ema_period":34,"beta_days":270,"relative_days":65,"z_history_days":180,"wave_history_days":730,"wave_min_count":8,"wave_quantiles":[0.1,0.3,0.6],"btc_tp_fractions_initial_qty":[0.2125,0.2125,0.575],"btc_notional_multiplier":7.875,"max_parent_notional":10000000.0,"sol_size_multipliers_h":[1.75,2.625,3.5],"sol_entry_z":[1.25,2.5,3.75],"sol_exit_half_z":0.375,"sol_exit_all_z":0.125,"sol_max_holding_days":14,"btc_close_trail_fraction":0.03,"sol_timeout_preempts_add":false,"sol_late_entry_after_tp":true,"sol_overlay_enabled":true,"episode_fixed_beta":false}}"""


def _write_candidate(path, document: str = STAGE_G) -> None:
    path.write_text(document, encoding="utf-8")


def test_sealed_stage_g_candidate_is_exact_and_schema_exhaustive() -> None:
    path = __import__("pathlib").Path(__file__).resolve().parents[1] / "configs/stage-g-v1.json"
    loaded = load_candidate(path)
    assert loaded.candidate == Candidate(
        ema_period=34, beta_days=270, relative_days=65, z_history_days=180,
        wave_history_days=730, wave_min_count=8, wave_quantiles=(0.1, 0.3, 0.6),
        btc_tp_fractions_initial_qty=(0.2125, 0.2125, 0.575), btc_notional_multiplier=7.875,
        max_parent_notional=10_000_000.0, sol_size_multipliers_h=(1.75, 2.625, 3.5),
        sol_entry_z=(1.25, 2.5, 3.75), sol_exit_half_z=0.375, sol_exit_all_z=0.125,
        sol_max_holding_days=14, btc_close_trail_fraction=0.03,
        sol_timeout_preempts_add=False, sol_late_entry_after_tp=True,
        sol_overlay_enabled=True, episode_fixed_beta=False,
    )
    assert set(json.loads(path.read_text())["candidate"]) == {item.name for item in fields(Candidate)}


def test_candidate_hash_is_stable_and_content_only(tmp_path) -> None:
    path = tmp_path / "winner.json"
    _write_candidate(path)
    loaded = load_candidate(path)
    assert loaded.sha256 == candidate_content_hash(loaded.candidate)
    assert canonical_candidate_json(loaded.candidate) == canonical_candidate_json(Candidate(**asdict(loaded.candidate)))


@pytest.mark.parametrize("mutate", [
    lambda doc: doc.pop("ema_period"),
    lambda doc: doc.update({"unknown": 1}),
    lambda doc: doc.update({"btc_notional_multiplier": float("inf")}),
    lambda doc: doc.update({"ema_period": 0}),
    lambda doc: doc.update({"btc_notional_multiplier": 0}),
    lambda doc: doc.update({"max_parent_notional": -1}),
    lambda doc: doc.update({"sol_entry_z": [2.5, 1.25, 3.75]}),
    lambda doc: doc.update({"sol_entry_z": [1.25, 1.25, 3.75]}),
    lambda doc: doc.update({"sol_exit_half_z": -0.01}),
    lambda doc: doc.update({"sol_exit_all_z": 0.5}),
])
def test_candidate_loader_rejects_missing_extra_nonfinite_and_invalid_values(tmp_path, mutate) -> None:
    document = json.loads(STAGE_G)
    mutate(document["candidate"])
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_candidate(path)


def test_loaded_candidate_does_not_change_when_file_changes(tmp_path) -> None:
    path = tmp_path / "winner.json"
    _write_candidate(path)
    loaded = load_candidate(path)
    original = (loaded.candidate, loaded.sha256)
    changed = json.loads(STAGE_G)
    changed["candidate"]["ema_period"] = 35
    path.write_text(json.dumps(changed), encoding="utf-8")
    assert (loaded.candidate, loaded.sha256) == original


def test_instance_config_is_strict_and_resolves_paths_once(tmp_path) -> None:
    candidate_path = tmp_path / "stage-g.json"
    _write_candidate(candidate_path)
    instance_path = tmp_path / "instance.json"
    instance_path.write_text(json.dumps({
        "instance_id": "paper-stage-g", "venue": "BYBIT", "mode": "paper",
        "strategy_config": "stage-g.json", "state_db": "paper.sqlite",
        "trader_id": "COINMASTER-PAPER-G", "strategy_id": "stage-g-v1", "order_id_tag": "SG",
    }), encoding="utf-8")
    instance = load_instance_config(instance_path)
    assert instance.strategy_config == candidate_path.resolve()
    assert instance.state_db == (tmp_path / "paper.sqlite").resolve()
