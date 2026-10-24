"""Engine-free guard validation on the preserved failed physical OFF raw file.

Validation here does not promote that FAILED attempt or synthesize an export.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import hashlib,json,os
import pytest
from coinmaster.research.native_baseline import _interval_month_labels,assert_report_boundaries


@pytest.mark.parametrize('start,end,labels',[
 ('2024-09-01T00:00:00+00:00','2025-01-15T00:00:00+00:00',['2024-09','2024-10','2024-11','2024-12','2025-01']),
 ('2024-09-15T00:00:00+00:00','2024-11-01T00:00:00+00:00',['2024-09','2024-10']),
 ('2024-09-01T00:00:00+00:00','2024-10-01T00:00:00+00:00',['2024-09']),
 ('2024-09-01T00:00:00+00:00','2024-10-01T00:00:01+00:00',['2024-09','2024-10'])])
def test_half_open_calendar_intersections_include_only_actual_partial_months(start,end,labels):
    assert _interval_month_labels(datetime.fromisoformat(start),datetime.fromisoformat(end))==labels


def test_original_full_interval_still_has_exact24_ordered_months():
    labels=_interval_month_labels(datetime.fromisoformat('2024-09-01T00:00:00+00:00'),datetime.fromisoformat('2026-09-01T00:00:00+00:00'))
    assert len(labels)==24 and labels[0]=='2024-09' and labels[-1]=='2026-08'


@pytest.fixture
def actual_saved_raw():
    value=os.environ.get('COINMASTER_SAVED_PREFIX_RAW_REPORT')
    if not value:pytest.skip('requires explicitly supplied preserved failed OFF raw artifact')
    path=Path(value);before=path.read_bytes()
    assert hashlib.sha256(before).hexdigest()=='44e1257c22972f50c9158d150ae0b4df100ad87520432039e1e6deefc4c2afa3'
    report=json.loads(before)
    assert report['raw_audit_state']=='NATIVE_COMPLETE_PACKAGING_NOT_VALIDATED'
    yield report
    assert path.read_bytes()==before


def test_actual_failed_off_raw_passes_calendar_guard_without_money_or_state_edit(actual_saved_raw):
    before=deepcopy(actual_saved_raw)
    assert_report_boundaries(actual_saved_raw)
    assert actual_saved_raw==before
    assert len(actual_saved_raw['summary']['monthly_returns'])==5
    assert actual_saved_raw['coherent_native_observer']['status']=='UNKNOWN'


@pytest.mark.parametrize('defect,expected',[
 ('missing_partial','MONTHLY_ROW_COUNT'),('reorder','MONTHLY_ORDERED_INTERVAL_LABELS'),
 ('duplicate','MONTHLY_ORDERED_INTERVAL_LABELS'),('cash','MONTHLY_INTERVAL_CASH'),
 ('return','MONTHLY_COMPOUNDING'),('out_of_interval_fill','FILL_OUTSIDE')])
def test_actual_raw_all_existing_guards_and_ordered_labels_stay_strict(actual_saved_raw,defect,expected):
    report=deepcopy(actual_saved_raw);months=report['summary']['monthly_returns']
    if defect=='missing_partial':months.pop()
    elif defect=='reorder':months[0],months[1]=months[1],months[0]
    elif defect=='duplicate':months[1]['month']=months[0]['month']
    elif defect=='cash':months[-1]['total']='19544.08357286'
    elif defect=='return':months[-1]['return']='0.083950686600870553331150758'
    elif defect=='out_of_interval_fill':report['fill_timestamps_ns'].append(1736899200000000001)
    with pytest.raises(ValueError,match=expected):assert_report_boundaries(report)
