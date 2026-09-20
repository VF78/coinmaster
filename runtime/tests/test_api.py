from coinmaster.api.app import BASELINE_CONFIG, ControlStore, PreflightInput, StrategyConfig, _catalog_entry, immutable_research_reference, create_app, fixture_report
from coinmaster.research.catalog import RESEARCH_CATALOG
import pytest


def test_api_openapi_and_immutable_configuration(tmp_path) -> None:
    app = create_app(str(tmp_path / "control.sqlite"), "test-token")
    assert "/api/v1/runs" in app.openapi()["paths"]
    store = ControlStore(str(tmp_path / "control.sqlite"))
    config = store.save_config(StrategyConfig.model_validate(BASELINE_CONFIG))
    assert store.get_config(config.id).config_hash == config.config_hash


def test_fixture_report_is_native_synthetic_evidence_only() -> None:
    report = fixture_report()
    assert report == {
        "terminal_total_usdt": "15632.05000000",
        "fills": 5,
        "label": "SYNTHETIC_P1_FIXTURE",
        "ranking_eligible": False,
    }


def test_preflight_requires_explicit_valid_beta_and_three_sol_levels() -> None:
    missing = PreflightInput(venue="bybit", btc_notional="90000", sol_multipliers=[1, 1.5, 2])
    assert missing.beta is None
    supplied = PreflightInput(venue="bybit", btc_notional="90000", beta="1.5", selected_leverage="20", sol_multipliers=[1, 1.5, 2])
    assert supplied.beta == "1.5" and len(supplied.sol_multipliers) == 3
    with pytest.raises(ValueError):
        PreflightInput(venue="bybit", btc_notional="90000", beta="0", sol_multipliers=[1, 1.5, 2])


def test_research_catalog_is_read_only_and_backtest_is_an_artifact_reference(tmp_path) -> None:
    app = create_app(str(tmp_path / "control.sqlite"), "test-token")
    assert "/api/v1/research/catalog" in app.openapi()["paths"]
    selected = _catalog_entry(next(item for item in RESEARCH_CATALOG if item["selected"]))
    assert selected["id"] == "bybit-reporting-v2-selected-7.5"
    assert selected["classification"] == "NOT_FAITHFUL_DIAGNOSTIC"
    assert selected["artifact_state"] in {"VERIFIED_LOCAL", "ARTIFACT_NOT_LOCAL"}
    evidence, report = immutable_research_reference()
    assert "NO_NEW_BACKTEST_COMPUTE" in evidence
    assert report["catalog_id"] == selected["id"]
