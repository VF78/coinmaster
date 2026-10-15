"""GUI activation must never send native trader commands."""
import ast
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native_gui_host.sh"


def test_deployment_smoke_has_no_trader_command_function_or_invocation():
    source = SCRIPT.read_text()
    assert "entry_control_smoke" not in source
    assert "stageg-control-" not in source
    assert "authenticated pause/read-back/resume" not in source


def test_api_smoke_only_checks_gets_and_nonexistent_post_collection():
    source = SCRIPT.read_text().split("api_smoke() {", 1)[1].split("wait_api_ready() {", 1)[0]
    python = source.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    tree = ast.parse(python)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "get"]
    mutations = []
    for call in calls:
        method = next((item.value for item in call.keywords if item.arg == "method"), None)
        if method is not None:
            mutations.append((ast.literal_eval(call.args[0]), ast.literal_eval(method)))
    # This collection has no mutation handler, so it can only return 405.
    assert mutations == [("/api/v1/instances/hl-stageg-testnet/controls", "POST")]
    assert "/api/v1/instances/hl-stageg-live" in python
    assert "assert body['account']['native_cash'] is None" in python
    assert "assert body['real_order_approval'] is False" in python


def test_inactive_live_fill_smoke_requires_unavailable_not_empty_history():
    source = SCRIPT.read_text()
    assert "if path == '/fills':" in source
    assert "assert status == 503, (endpoint, status)" in source
    assert "'Stage-G fill history is unavailable'" in source
    assert "'Stage-G fill journal is unavailable'" in source
    assert "assert status == 200, (endpoint, status)" in source
