from coinmaster.api.execution_modes import execution_mode_state

def test_mode_view_independent_services_and_native_identity():
    def service(unit):
        return {"state":"RUNNING" if "testnet" in unit else "INACTIVE"}
    result = execution_mode_state(service)
    assert result["sandbox"]["state"] == "RUNNING"
    assert result["live"]["state"] == "INACTIVE"
    assert result["activate_enabled"] is False and result["stop_enabled"] is False

def test_systemd_active_requires_native_live_identity():
    result = execution_mode_state(lambda _: {"state":"RUNNING"}, lambda: {"instance_id":"hl-stageg-testnet","mode":"sandbox","run_epoch":"other"})
    assert result["live"]["state"] == "UNCONFIRMED" and result["live"]["run_epoch"] is None
    valid = execution_mode_state(lambda _: {"state":"RUNNING"}, lambda: {"instance_id":"hl-stageg-live","mode":"live","run_epoch":"native-live","orders_enabled":False,"account_state":"CURRENT","recovery_required":False})
    assert valid["live"]["state"] == "RUNNING" and valid["live"]["run_epoch"] == "native-live"
    assert valid["live"]["orders_enabled"] is False
