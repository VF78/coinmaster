from coinmaster.research.bybit_data import FUNDING_MS, gaps, interval_evidence


def test_gap_report_exposes_off_schedule_funding_instead_of_hiding_it() -> None:
    start = 0
    report = gaps("funding_8h", "SOLUSDT", [start, start + FUNDING_MS, start + 12 * 60 * 60 * 1000], start, start + 2 * FUNDING_MS, FUNDING_MS)
    assert report.missing == []
    assert report.off_expected_schedule == [start + 12 * 60 * 60 * 1000]


def test_interval_evidence_reports_observations_without_declaring_a_schedule() -> None:
    assert interval_evidence([0, FUNDING_MS, FUNDING_MS + 4 * 60 * 60 * 1000]) == {str(FUNDING_MS): 1, str(4 * 60 * 60 * 1000): 1}
