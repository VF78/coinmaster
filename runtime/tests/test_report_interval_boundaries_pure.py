"""Reporting-only actual source functions, zero native imports/constructors."""
import ast,copy,gzip,json
from types import SimpleNamespace as N
from datetime import datetime,timedelta,timezone
from decimal import Decimal,localcontext,getcontext
from pathlib import Path
import pytest
SOURCE=Path(__file__).parents[1]/'coinmaster/research/native_baseline.py'
TREE=ast.parse(SOURCE.read_text());ENV=dict(datetime=datetime,timedelta=timedelta,timezone=timezone,Decimal=Decimal,localcontext=localcontext)
exec(compile(ast.Module(body=[n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name in ('monthly_returns','assert_report_boundaries','_reporting_checkpoints','_finalize_native_resources')],type_ignores=[]),'actual_reporting_only','exec'),ENV)
check=ENV['assert_report_boundaries'];schedule=ENV['_reporting_checkpoints'];monthly=ENV['monthly_returns']
def dt(value):return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
def labels(start,end):
 cursor=start.replace(day=1,hour=0,minute=0,second=0,microsecond=0);out=[]
 while cursor<end:
  out.append(cursor.strftime('%Y-%m'));cursor=(cursor+timedelta(days=32)).replace(day=1)
 return out

def report(start='2026-09-01',end='2026-10-28'):
 start,end=dt(start),dt(end)
 return dict(run_interval=dict(start=start.isoformat(),end_exclusive=end.isoformat(),initial_active_seed='10000'),
  summary=dict(monthly_returns=[dict(month=m,total='10000',**{'return':'0'}) for m in labels(start,end)],interval_cash_terminal_total='10000',drawdown_start=start.isoformat(),drawdown_trough=(end-timedelta(seconds=1)).isoformat()),
  fill_timestamps_ns=[int(end.timestamp()*1e9)],post_boundary_settlement=dict(convention='TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS',fill_count=1))

@pytest.mark.parametrize('start,end,count',[('2026-09-01','2026-10-28',2),('2024-09-01','2026-09-01',24),('2026-09-15','2026-10-15',2),('2026-09-15','2026-09-20',1),('2026-09-01','2026-10-01',1),('2026-12-15','2027-01-02',2)])
def test_exact_covered_calendar_months_including_partial_terminal_month(start,end,count):
 r=report(start,end);before=copy.deepcopy(r);precision=getcontext().prec;assert len(r['summary']['monthly_returns'])==count
 check(r);assert r==before and getcontext().prec==precision

@pytest.mark.parametrize('fault',['missing','duplicate','mislabel','out_of_order','outside_month','empty'])
def test_exact_labels_not_arbitrary_month_count(fault):
 r=report();months=r['summary']['monthly_returns']
 if fault=='missing':months.pop()
 elif fault=='duplicate':months[1]['month']=months[0]['month']
 elif fault=='mislabel':months[1]['month']='2026-11'
 elif fault=='out_of_order':months.reverse()
 elif fault=='outside_month':months[0]['month']='2026-08'
 else:months.clear()
 with pytest.raises(ValueError,match='MONTHLY_'):check(r)

@pytest.mark.parametrize('fault',['terminal_cash','compounding','drawdown','fill_outside','boundary_count','empty_interval'])
def test_original_financial_and_native_boundary_assertions_remain(fault):
 r=report()
 if fault=='terminal_cash':r['summary']['interval_cash_terminal_total']='10001'
 elif fault=='compounding':r['summary']['monthly_returns'][1]['return']='.01'
 elif fault=='drawdown':r['summary']['drawdown_trough']=r['run_interval']['end_exclusive']
 elif fault=='fill_outside':r['fill_timestamps_ns'][0]+=1
 elif fault=='boundary_count':r['post_boundary_settlement']['fill_count']=0
 else:r['run_interval']['end_exclusive']=r['run_interval']['start']
 with pytest.raises(ValueError):check(r)


def test_early_lockout_only_contiguous_in_interval_prefix_remains_supported():
 r=report();r.update(liquidation_count=1,liquidation_lockout=True);r['summary']['monthly_returns'].pop();check(r)
 r['summary']['monthly_returns'][0]['month']='2026-11'
 with pytest.raises(ValueError,match='MONTHLY_INTERVAL_COVERAGE'):check(r)


def test_checkpoints_stop_at_actual_partial_end_and_full24_schedule_unchanged():
 s,e=dt('2026-09-01'),dt('2026-10-28');points=schedule(s,e)
 assert points==(int(dt('2026-10-01').timestamp()*1e9),int(e.timestamp()*1e9)) and all(p<=int(e.timestamp()*1e9) for p in points)
 s,e=dt('2024-09-01'),dt('2026-09-01');points=schedule(s,e)
 assert len(points)==24 and points[-1]==int(e.timestamp()*1e9) and points[0]==int(dt('2024-10-01').timestamp()*1e9)
 assert schedule(dt('2026-09-15'),dt('2026-09-20'))==(int(dt('2026-09-20').timestamp()*1e9),)


def test_actual_monthly_returns_keeps_partial_october_and_insertion_order():
 values=[dict(timestamp='2026-09-01T00:00:00+00:00',total='10000'),dict(timestamp='2026-10-27T01:00:00+00:00',total='11000'),dict(timestamp='2026-10-27T01:00:00+00:00',total='10500')]
 months=monthly(values);assert [m['month'] for m in months]==['2026-09','2026-10'] and months[-1]['total']=='10500'
 r=report();r['summary']['monthly_returns']=months;r['summary']['interval_cash_terminal_total']='10500';check(r)


def test_exception_closes_actual_gzip_both_risk_streams_and_preserves_primary(tmp_path):
 tree=ast.parse((SOURCE.parent/'minute_risk.py').read_text())
 method=next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='close_writers')
 namespace={};exec(compile(ast.Module(body=[method],type_ignores=[]),'actual_minute_close_writers','exec'),namespace)
 paths=[tmp_path/'risk.gz',tmp_path/'receipts.gz'];writers=[gzip.open(path,'wt') for path in paths]
 for writer in writers:writer.write('header\n'+'value\n'*1000)
 recorder=N(file=writers[0],receipt_file=writers[1]);recorder.close_writers=lambda:namespace['close_writers'](recorder)
 calls=[];ENV['_quarantine_funding_attempt']=lambda path:calls.append('quarantined');ENV['_publish_clean_funding_attempt']=lambda *a:calls.append('published')
 error=ValueError('ORIGINAL_REPORT_ASSERTION')
 with pytest.raises(ValueError) as caught:
  try:raise error
  finally:ENV['_finalize_native_resources'](audit_archive=N(close=lambda:calls.append('archive')),risk_recorder=recorder,
   coherent_observer=N(close=lambda:calls.append('event')),engine=N(dispose=lambda:calls.append('disposed')),
   journal=N(close=lambda:calls.append('journal')),successful_run=False,journal_attempt_path=tmp_path/'attempt',journal_path=tmp_path/'clean',primary_error=error)
 assert caught.value is error and calls==['archive','event','disposed','journal','quarantined']
 for path in paths:
  with gzip.open(path,'rt') as reader:assert len(reader.readlines())==1001


def test_cleanup_failure_does_not_mask_primary_and_all_other_resources_close():
 calls=[]
 def fail():calls.append('bad');raise OSError('CLOSE_FAILED')
 ENV['_quarantine_funding_attempt']=lambda path:calls.append('quarantined')
 primary=ValueError('REPORT_FAILED')
 ENV['_finalize_native_resources'](audit_archive=N(close=fail),risk_recorder=N(close=lambda:calls.append('risk')),
  coherent_observer=N(close=lambda:calls.append('event')),engine=N(dispose=lambda:calls.append('engine')),
  journal=N(close=lambda:calls.append('journal')),successful_run=False,journal_attempt_path='attempt',journal_path='clean',primary_error=primary)
 assert calls==['bad','risk','event','engine','journal','quarantined'] and 'CLOSE_FAILED' in primary.__notes__[0]


def test_cleanup_error_without_primary_fails_and_quarantines_not_publishes():
 calls=[]
 def fail():raise OSError('GZIP_CLOSE_FAILED')
 ENV['_quarantine_funding_attempt']=lambda path:calls.append('quarantined');ENV['_publish_clean_funding_attempt']=lambda *a:calls.append('published')
 with pytest.raises(OSError,match='GZIP_CLOSE_FAILED'):
  ENV['_finalize_native_resources'](audit_archive=None,risk_recorder=N(close=fail),coherent_observer=None,engine=N(dispose=lambda:None),
   journal=N(close=lambda:calls.append('journal')),successful_run=True,journal_attempt_path='attempt',journal_path='clean')
 assert calls==['journal','quarantined']


def test_original_real_24month_precision_fixture_passes_unchanged():
 tree=ast.parse((SOURCE.parents[2]/'tests/test_native_report_precision.py').read_text());env={'json':json}
 assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REPORT' for t in n.targets))
 exec(compile(ast.Module(body=[assignment],type_ignores=[]),'unchanged_24month_precision_fixture','exec'),env)
 original=copy.deepcopy(env['REPORT']);check(env['REPORT']);assert env['REPORT']==original


def test_promotion_failure_closes_and_quarantines_without_masking_error():
 calls=[]
 def publish(*a):raise OSError('FUNDING_PROMOTION_FAILED')
 ENV['_publish_clean_funding_attempt']=publish;ENV['_quarantine_funding_attempt']=lambda path:calls.append('quarantined')
 with pytest.raises(OSError,match='FUNDING_PROMOTION_FAILED'):
  ENV['_finalize_native_resources'](audit_archive=None,risk_recorder=None,coherent_observer=None,engine=N(dispose=lambda:None),
   journal=N(close=lambda:calls.append('journal')),successful_run=True,journal_attempt_path='attempt',journal_path='clean')
 assert calls==['journal','quarantined']
