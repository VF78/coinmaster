"""Read-only mode facts; UI view selection never starts/stops a trader."""
import subprocess
import time
import urllib.request
import json

def _service(unit):
    result = subprocess.run(["systemctl", "show", unit, "-p", "ActiveState", "-p", "MainPID"], capture_output=True, text=True, timeout=3, check=True)
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    active, pid = values.get("ActiveState"), int(values.get("MainPID", "0"))
    return {"state": "RUNNING" if active == "active" and pid > 0 else "STARTING" if active == "activating" else "INACTIVE" if active == "inactive" else "FAILED" if active == "failed" else "UNKNOWN"}

def execution_mode_state(service=_service, native_get=None):
    def native():
        with urllib.request.urlopen("http://127.0.0.1:18185/status", timeout=2) as response:
            raw = response.read(350001)
        if len(raw) > 350000: raise ValueError
        return json.loads(raw)
    try: sandbox = service("coinmaster-hl-stageg-testnet.service")
    except Exception: sandbox = {"state": "UNKNOWN"}
    try: live = service("coinmaster-hl-stageg-live.service")
    except Exception: live = {"state": "UNKNOWN"}
    live["run_epoch"] = None
    if live["state"] == "RUNNING":
        try:
            status = (native_get or native)()
            if status.get("instance_id") != "hl-stageg-live" or status.get("mode") != "live" or not status.get("run_epoch") or status.get("account_state") != "CURRENT" or status.get("recovery_required") is not False:
                raise ValueError
            live["run_epoch"] = status["run_epoch"]
            live["orders_enabled"] = status.get("orders_enabled") is True
        except Exception: live["state"] = "UNCONFIRMED"
    return {"observed_at_ns": time.time_ns(), "sandbox": sandbox, "live": live,
            "activate_enabled": False,
            "blockers": ["Funded account qualification and exact live-order approval are required.", "GUI activation permission is pending."],
            "stop_enabled": False, "stop_reason": "A verified stop with no open exposure is not yet available."}
