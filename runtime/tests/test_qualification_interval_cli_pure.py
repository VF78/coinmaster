"""Actual repair wrapper/CLI with fake diagnostic callee; native imports0."""
import argparse,ast,hashlib,json,sys
from dataclasses import dataclass,asdict,replace
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import pytest
ROOT=Path(__file__).parents[1]
SOURCE=ROOT/'coinmaster/research/native_baseline.py';TREE=ast.parse(SOURCE.read_text())
BASE=ast.literal_eval(next(n.value for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BASELINE_CONFIG' for t in n.targets)))
WARM=1662076800000;START=1725148800000;END=1788220800000
QSTART=1788220800000;QEND=1793145600000;QWARM=1725148800000

def environment():
 env=dict(__name__=__name__,Path=Path,Decimal=Decimal,datetime=datetime,timezone=timezone,dataclass=dataclass,asdict=asdict,replace=replace,
  json=json,hashlib=hashlib,argparse=argparse,BASELINE_CONFIG=BASE,WARMUP_START_MS=WARM,TRADING_START_MS=START,TRADING_END_MS=END,WEEK_MINUTES=10080,DAY_MS=86400000,sha256_file=lambda f:hashlib.sha256(f.read_bytes()).hexdigest())
 nodes=[n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name in ('ExecutionPolicy','FixedBaseFeePolicy')]
 nodes += [n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name in ('run_research_v0_repairs_cli','main')]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_native_wrapper_and_main','exec'),env)
 return env

def fixture(env,tmp_path,real_control=False):
 data=tmp_path/'data';(data/'bybit-1m').mkdir(parents=True);m={'pure_fixture':True};(data/'bybit-1m/manifest.json').write_text(json.dumps(m))
 config=json.loads((ROOT.parent/'reports/e4-c1-fast-pilot-20261028/config-BTC-POSTCUT-D1.json').read_text())
 control=dict(status='NOT_FAITHFUL_DIAGNOSTIC',summary={'terminal_total':'3386491.65211338'},config=config,policy=config['execution_policy'],data_hash=hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest())
 file=tmp_path/'control.json'
 if real_control:
  original=Path('/tmp/cm-e4-c1-archived-control-v0.json')
  if not original.is_file():pytest.skip('Requires immutable archived v0 fixture SHA d6a29d6e, supplied separately; no synthetic control acceptance')
  assert hashlib.sha256(original.read_bytes()).hexdigest()=='d6a29d6e0e9ac586b911f2802cbe89602a05d2c0d73026d08ed76082a8a934f9'
  file.write_bytes(original.read_bytes())
 else:file.write_text(json.dumps(control))
 seen=[];env['saved_reports']=[]
 env['run_native_diagnostic']=lambda *a,**kw:seen.append((a,kw)) or {}
 env['sha256_file']=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
 env['save_diagnostic_report']=lambda data,report,label,out:env['saved_reports'].append(report) or out/'result.json'
 return data,file,seen

@pytest.mark.parametrize('custom',[False,True])
def test_actual_wrapper_omits_default_interval_and_forwards_exact_optional_values(tmp_path,custom):
 env=environment();data,control,seen=fixture(env,tmp_path,real_control=custom)
 extra=dict(trading_start_ms=QSTART,trading_end_ms=QEND,warmup_start_ms=QWARM,qualification_data_hash=hashlib.sha256(json.dumps({'pure_fixture':True},sort_keys=True,separators=(',',':')).encode()).hexdigest()) if custom else {}
 env['run_research_v0_repairs_cli'](data,tmp_path/'result',control,**extra)
 assert len(seen)==1;args,kw=seen[0]
 assert args==(data,) and kw['initial_active_seed']==Decimal('10000') and kw['include_funding'] is True
 for name in ('trading_start_ms','trading_end_ms','warmup_start_ms'):
  if custom:assert kw[name]==extra[name]
  else:assert name not in kw
 assert kw['qualification_stress'] is False
 if custom:
  context=env['saved_reports'][0]['qualification_context'];assert context['fresh_native_account'] is True and context['archived_control_matched_interval'] is False and context['ranking_against_archived_control'] is False
 else:assert 'qualification_context' not in env['saved_reports'][0]


def test_actual_main_forwards_cli_values_without_constructing_diagnostic(tmp_path):
 env=environment();calls=[]
 def fake_cli(*a,**kw):
  calls.append((a,kw));out=tmp_path/'out.json';out.write_text('{}');return out
 env['run_research_v0_repairs_cli']=fake_cli
 original=sys.argv
 try:
  sys.argv=['pure','--research-v0-execution-repairs','--control-report',str(tmp_path/'control'),'--artifact-dir',str(tmp_path/'result'),
   '--trading-start-ms',str(QSTART),'--trading-end-ms',str(QEND),'--warmup-start-ms',str(QWARM),'--qualification-data-hash','a'*64]
  env['main']()
 finally:sys.argv=original
 kw=calls[0][1];assert (kw['trading_start_ms'],kw['trading_end_ms'],kw['warmup_start_ms'])==(QSTART,QEND,QWARM)
 assert kw['qualification_stress'] is False


def test_explicit_interval_cannot_be_silently_ignored_outside_repair_cli():
 env=environment();original=sys.argv
 try:
  sys.argv=['pure','--trading-start-ms',str(QSTART)]
  with pytest.raises(SystemExit) as error:env['main']()
  assert error.value.code==2
 finally:sys.argv=original


def test_exact_qual_dates_and_warmup_are_utc_730_days():
 assert datetime.fromtimestamp(QSTART/1000,timezone.utc).isoformat()=='2026-09-01T00:00:00+00:00'
 assert datetime.fromtimestamp(QEND/1000,timezone.utc).isoformat()=='2026-10-28T00:00:00+00:00'
 assert QSTART-QWARM==730*86400000


def test_public_diagnostic_and_stress_bodies_are_unmodified_from_frozen_candidate():
 import subprocess
 old=ast.parse(subprocess.check_output(['git','show','fccd60c01e8cae5e8258748b046f43f88a16bb79:runtime/coinmaster/research/native_baseline.py'],cwd=ROOT.parent,text=True))
 for name in ('run_native_diagnostic','qualification_stress_metadata','qualification_stress_venue_kwargs'):
  before=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
  after=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name==name)
  assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)


@pytest.mark.parametrize('bundle',[dict(trading_start_ms=QSTART),dict(trading_start_ms=QSTART,trading_end_ms=QEND,warmup_start_ms=QWARM),dict(qualification_data_hash='a'*64)])
def test_incomplete_bundle_rejects_before_artifact_or_diagnostic(tmp_path,bundle):
 env=environment();data,control,seen=fixture(env,tmp_path)
 with pytest.raises(ValueError,match='QUALIFICATION_REQUIRES_COMPLETE'):env['run_research_v0_repairs_cli'](data,tmp_path/'result',control,**bundle)
 assert not seen and not (tmp_path/'result').exists()

@pytest.mark.parametrize('fault',['data_pin','archived_control','UTC','warmup','end_order','warmup_after_start','pin_format'])
def test_wrong_newpin_or_changed_oldcontrol_or_invalid_interval_rejects(tmp_path,fault):
 env=environment();data,control,seen=fixture(env,tmp_path,real_control=True)
 pin=hashlib.sha256(json.dumps({'pure_fixture':True},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 args=dict(trading_start_ms=QSTART,trading_end_ms=QEND,warmup_start_ms=QWARM,qualification_data_hash=pin)
 if fault=='data_pin':args['qualification_data_hash']='a'*64
 if fault=='archived_control':control.write_text(control.read_text()+' ')
 if fault=='UTC':args['trading_start_ms']+=1
 if fault=='warmup':args['warmup_start_ms']+=86400000
 if fault=='end_order':args['trading_end_ms']=QSTART
 if fault=='warmup_after_start':args['warmup_start_ms']=QSTART+86400000
 if fault=='pin_format':args['qualification_data_hash']='z'*64
 with pytest.raises(ValueError,match='QUALIFICATION_'):env['run_research_v0_repairs_cli'](data,tmp_path/'result',control,**args)
 assert not seen and not (tmp_path/'result').exists()


def test_default_still_requires_same_control_dataset(tmp_path):
 env=environment();data,control,seen=fixture(env,tmp_path)
 (data/'bybit-1m/manifest.json').write_text('{}')
 with pytest.raises(ValueError,match='CONTROL_V0_DATA_HASH_MISMATCH'):env['run_research_v0_repairs_cli'](data,tmp_path/'result',control)
 assert not seen
