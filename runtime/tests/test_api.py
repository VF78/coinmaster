from coinmaster.api.app import BASELINE_CONFIG, ControlStore, PreflightInput, StrategyConfig, create_app, fixture_report
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
