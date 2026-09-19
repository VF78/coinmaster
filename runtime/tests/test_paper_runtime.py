import pytest
from coinmaster.ops.paper import PaperRuntime


def test_paper_runtime_is_wal_durable_idempotent_and_fail_closed(tmp_path) -> None:
    path = tmp_path / "paper.sqlite"
    first = PaperRuntime(path, "owner-a", 10)
    first.acquire()
    assert first.health(0).safe_for_increase is False
    first.snapshot(ts_ns=5, positions=[], orders=[], funding_event_ids=["f1"])
    assert first.command("pause-new-entries", "pause-1") is True
    assert first.command("pause-new-entries", "pause-1") is False
    assert first.health(10).safe_for_increase is False
    first.close()
    reopened = PaperRuntime(path, "owner-b", 10)
    assert reopened.health(16).warnings == ("STALE_DATA",)
    with pytest.raises(RuntimeError, match="PAPER_OWNER_LOCKED"): reopened.acquire()
    reopened.close()
