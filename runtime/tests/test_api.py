from coinmaster.api.app import BASELINE_CONFIG, ControlStore, StrategyConfig, create_app, fixture_report


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
