import json

from coinmaster.research.bybit_minute import MINUTE_MS, _load_or_create


def test_resume_state_rejects_a_different_range(tmp_path) -> None:
    path = tmp_path / "execution.progress.json"
    path.write_text(json.dumps({"stream": "execution", "start_ms": 0, "end_ms": MINUTE_MS, "next_end_ms": 0, "raw": [], "completed": False}))
    try:
        _load_or_create(path, "execution", 0, 2 * MINUTE_MS)
    except ValueError as error:
        assert "conflicts" in str(error)
    else:
        raise AssertionError("resume range must be immutable")
