"""Actual recovery methods on pure fixtures/SQLite. No Nautilus imports/constructors."""
import ast
import asyncio
import hashlib
import json
import math
import sys
import time
from dataclasses import asdict,dataclass,fields,is_dataclass
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
from types import ModuleType,SimpleNamespace as N
import pytest
from coinmaster.domain.wave_overlay import Candidate,DailyBar,Episode,Intent
from coinmaster.ops.stage_g_config import canonical_candidate_json
from coinmaster.ops.paper import PaperRuntime,_journal_locked

ROOT=Path(__file__).parents[1]/'coinmaster'
VENUE=N(value='HYPERLIQUID')
ACCOUNT='0x'+'1'*40 # Synthetic fixture, never queried.
ACCOUNT_ID='SYNTHETIC_TEST_ACCOUNT'
NOW=1_000_000_000

class ID(str):
 venue=VENUE
 @classmethod
 def from_str(cls,value):return cls(value)
class Placeholder:pass
class Signal:
 def __init__(self,instrument_id,open_,high,low,close,ts_event,ts_init=None):
  self.instrument_id=instrument_id;self.open=open_;self.high=high;self.low=low;self.close=close
  self.ts_event=ts_event;self.ts_init=ts_event if ts_init is None else ts_init
class Next(Signal):
 def __init__(self,instrument_id,hours,open_,high,low,close,ts_event,ts_init=None):
  super().__init__(instrument_id,open_,high,low,close,ts_event,ts_init);self.hours=hours;self.open_time_ns=ts_event-hours*3_600_000_000_000
class Q:
 def __init__(self,value):self.value=D(value)
 def as_decimal(self):return self.value
 def __eq__(self,other):return isinstance(other,Q) and self.value==other.value


def nodes(path,names):
 tree=ast.parse((ROOT/path).read_text())
 found=[]
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:found.append(node)
  elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):found.append(node)
 return found

def run_ast(body,namespace):
 future=ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)
 module=ast.fix_missing_locations(ast.Module(body=[future,*body],type_ignores=[]))
 exec(compile(module,'actual_recovery_source','exec'),namespace)

@pytest.fixture
def code(monkeypatch):
 env=dict(asyncio=asyncio,hashlib=hashlib,json=json,math=math,time=time,Decimal=D,datetime=datetime,Path=Path,__file__=str(ROOT/"strategy/live_recovery.py"),
  fields=fields,is_dataclass=is_dataclass,DailyBar=DailyBar,Episode=Episode,Intent=Intent,
  InstrumentId=ID,BarType=Placeholder,Bar=Placeholder,DailySignalBar=Signal,NextClosedBar=Next,
  VenueMark=type('Mark',(),{}),canonical_candidate_json=canonical_candidate_json)
 names={'_SCHEMA','_KEY','_DATACLASSES','_FIELDS','_C1_SCHEMA','_C1_FIELDS','_PUBLIC_INPUT_FIELDS',
  'recovery_fields','recovery_policy_hash','checkpoint_structure','durable_decision_checkpoint','_encode','_decode'}
 run_ast(nodes('strategy/live_recovery.py',names),env)
 class FakeNativeBase:
  def __init__(self,config):
   self.config=config;self._candidate=Candidate();self.id='SYNTHETIC_STRATEGY';self.trader_id='SYNTHETIC_TRADER';self.msgbus=object()
   for name in env['_FIELDS']+env['_C1_FIELDS']:setattr(self,name,None)
   self._bars=[];self._domain=N(episode=Episode('episode',1,10000,1),locked_after_liquidation=False,_decision_index=17)
   self._forced_close_orders=set();self._pending_by_order={};self._seen_trade_ids={'10'};self._latest_marks={}
   self._c1_peak=D('15000');self._next_peak=D('16000');self._c1_fill_epoch=7
   self._c1_state=dict(group='episode',state='HELD',credit=3,cut_filled=3,bucket={0:1,1:2},revoked=False)
   self._next_last_bar={('BTC',4):14_400_000_000_000};self._next_bars=[];self.dispatched=[]
  def submit_order(self,order):
   # Actual source must durably reserve/checkpoint before crossing native API.
   assert any(r['client_order_id']==str(order.client_order_id) and r['state']=='SUBMITTING' for r in self._recovery_runtime.all_submissions())
   assert self._recovery_runtime.strategy_checkpoint()[1]==self._recovery_runtime.native_revision()
   self.dispatched.append(('REDUCE',str(order.client_order_id)))
  def cancel_order(self,order):
   assert self._recovery_runtime.db.execute("SELECT COUNT(*) FROM paper_command_audit WHERE status='MANAGE_SUBMITTING'").fetchone()[0]==1
   self.last_cancel_object=order
   self.dispatched.append(('CANCEL',str(order.client_order_id)))
 env['WaveOverlayStrategy']=FakeNativeBase
 run_ast(nodes('strategy/live_recovery.py',{'RecoverableWaveOverlayStrategy'}),env)
 module=ModuleType('coinmaster.strategy.live_recovery');module.__dict__.update(env);monkeypatch.setitem(sys.modules,module.__name__,module)
 management=dict(dataclass=dataclass,hashlib=hashlib,json=json,Decimal=D,time=time,PaperRuntime=PaperRuntime)
 run_ast(nodes('ops/live_recovery.py',{'NativeLiveRecoveryScope','ManagementCertificate','_management_order_evidence','management_cache_evidence','durable_management_scope','reserve_managed_action'}),management)
 module=ModuleType('coinmaster.ops.live_recovery');module.__dict__.update(management);monkeypatch.setitem(sys.modules,module.__name__,module)
 epoch=dict(env,PaperRuntime=PaperRuntime,_journal_locked=_journal_locked)
 run_ast(nodes('ops/hl_live_epoch.py',{'LiveEpochRuntime'}),epoch)
 return N(env=env,management=management,Runtime=epoch['LiveEpochRuntime'],Strategy=env['RecoverableWaveOverlayStrategy'])

def config():
 return N(research_residual_recovery=True,research_c1_btc_cut_divisor=2,research_c1_restore_dd=D('.35'),
  research_wait_4h=True,research_regime_reentry_band=D('.5'),research_btc_split50=True,
  btc_id=ID('BTC-USD-PERP.HYPERLIQUID'),sol_id=ID('SOL-USD-PERP.HYPERLIQUID'),
  max_mark_age_ns=120_000_000_000,execution_policy_hash='synthetic-policy',execution_policy_version='fixture')

def order(client='NEW',*,side='SELL',quantity='3',reduce=True,closed=False):
 return N(client_order_id=client,venue_order_id='100' if closed or client=='TP' else None,
  instrument_id=ID('BTC-USD-PERP.HYPERLIQUID'),strategy_id='SYNTHETIC_STRATEGY',account_id=ACCOUNT_ID,
  side=N(name=side),quantity=Q(quantity),filled_qty=Q(quantity if closed else '0'),is_reduce_only=reduce,
  is_closed=closed,is_pending_cancel=False,time_in_force=N(name='IOC'),order_type=N(name='MARKET'),
  status=N(name='FILLED' if closed else 'ACCEPTED'))

def setup(code,tmp_path):
 s=code.Strategy(config());s._domain.episode.btc_tp_target_lots={0:4,1:4,2:2};s._domain.episode.btc_risk_retired_lots={0:1,1:2}
 s._domain.episode.sol_rights={0};s._split_parent=dict(episode_id='episode',closed=True,actual_qty=D('10'))
 body=s.on_save();s.on_load(body);s.enable_manage_only_preparation()
 r=code.Runtime(tmp_path/'fixture.sqlite','synthetic-owner',10**20);r.acquire()
 r.acquire_live_account(ACCOUNT,'HYPERLIQUID',lock_root=tmp_path/'locks')
 s.attach_recovery_runtime(r)
 entry=order('ENTRY',side='BUY',quantity='10',reduce=False,closed=True)
 position=N(instrument_id=s.config.btc_id,id='OWNED_POSITION',strategy_id=str(s.id),account_id=ACCOUNT_ID,
  is_long=True,quantity=Q('10'),events=[N(client_order_id='ENTRY',trade_id='10')])
 s.cache=N(positions_open=lambda:[position],orders=lambda venue=None:[entry])
 r.record_submission(client_order_id='ENTRY',intent_id='entry',episode_id='episode',action='BTC_ENTRY',instrument_id=str(s.config.btc_id),quantity='10',reduce_only=False,strategy_state=s.on_save()[code.env['_KEY']])
 r.terminal_submission('ENTRY',s.on_save()[code.env['_KEY']])
 r.db.execute("INSERT INTO paper_recovered_fills VALUES ('10')")
 r.db.execute("INSERT INTO paper_native_fill_details(trade_id,client_order_id,instrument_id,quantity,price,ts_event_ns) VALUES ('10','ENTRY',?,'10','100',1000000)",(str(s.config.btc_id),));r.db.commit()
 assert r.persist_strategy_checkpoint(s.on_save()[code.env['_KEY']],r.native_revision())
 return s,r,entry,position

def certificate(code,s,r,healthy=lambda:True):
 positions,orders,signature=code.management['management_cache_evidence'](s.cache,VENUE)
 decision=hashlib.sha256(code.env['durable_decision_checkpoint'](s.on_save()[code.env['_KEY']])).hexdigest()
 return code.management['ManagementCertificate'](r.native_revision(),NOW+9_000_000_000,code.env['recovery_policy_hash'](s.config,s._candidate),signature,decision,positions,orders,NOW,healthy)

def test_exact_partial_rights_global_h_and_e4_clock_roundtrip_has_no_authority(code):
 s=code.Strategy(config());s._next_bars=[Next('BTC',4,D(100),D(110),D(90),D(105),14_400_000_000_000)]
 s._domain.episode.sol_rights={0};s._domain.episode.btc_risk_retired_lots={0:3}
 s._split_parent=dict(intent=Intent('pending','episode','BTC_ENTRY',None,1,quantity=10),closed=True)
 s._quote_ns={'old':999};source=s.on_save();restored=code.Strategy(config());restored.on_load(source)
 assert restored.on_save()==source
 assert restored._c1_peak==D(15000) and restored._next_peak==D(16000)
 assert restored._c1_state['credit']==3 and restored._c1_state['bucket']=={0:1,1:2}
 assert restored._domain.episode.sol_rights=={0} and restored._domain.episode.btc_risk_retired_lots=={0:3}
 assert restored._next_bars[0].hours==4 and restored._next_bars[0].open_time_ns==0
 assert restored._split_parent['intent'].id=='pending'
 assert not restored.recovery_confirmed and not restored._entries_enabled() and restored._quote_ns=={}
 assert restored._management_certificate is None and not restored._management_dispatch_enabled

@pytest.mark.parametrize('fault',['policy','schema','missing_state','candidate'])
def test_load_mismatch_revokes_management_instead_of_inventing_seed(code,fault):
 s=code.Strategy(config());body=json.loads(s.on_save()[code.env['_KEY']]);s._management_certificate=object()
 if fault=='policy':body['policy_sha256']='0'*64
 elif fault=='schema':body['schema']='unknown'
 elif fault=='candidate':body['candidate_sha256']='0'*64
 else:del body['state']['_c1_peak']
 with pytest.raises(ValueError):s.on_load({code.env['_KEY']:json.dumps(body).encode()})
 assert not s._checkpoint_policy_valid and s._management_certificate is None and not s.recovery_confirmed
 assert s._c1_peak==D(15000)

def test_default_off_capability_and_single_use_reservation_before_native_dispatch(code,tmp_path):
 s,r,entry,position=setup(code,tmp_path)
 try:
  s._management_certificate=certificate(code,s,r)
  with pytest.raises(RuntimeError,match='LIVE_ORDER_CAPABILITY_FALSE'):s.dispatch_manage_only('one','REDUCE',order(),now_ns=NOW)
  assert not s.dispatched and len(r.all_submissions())==1
  s._management_dispatch_enabled=True # Synthetic release boundary, never a live node.
  cert=s._management_certificate;s.dispatch_manage_only('one','REDUCE',order(),now_ns=NOW)
  assert s.dispatched==[('REDUCE','NEW')] and s._management_certificate is None
  assert r.native_revision()>cert.revision
  with pytest.raises(RuntimeError):s.dispatch_manage_only('two','REDUCE',order('NEW2'),now_ns=NOW)
  # A separately-held concurrent certificate from the same generation is stale.
  s._management_certificate=cert
  with pytest.raises(RuntimeError):s.dispatch_manage_only('two','REDUCE',order('NEW2'),now_ns=NOW)
  assert s.dispatched==[('REDUCE','NEW')]
  assert r.db.execute("SELECT status FROM paper_command_audit WHERE idempotency_key='one'").fetchone()[0]=='MANAGE_SUBMITTING'
 finally:r.close()

@pytest.mark.parametrize('fault',['wrong_side','too_large','foreign','increase','stale','revision','policy','checkpoint','transport'])
def test_unsafe_management_is_denied_and_consumes_certificate(code,tmp_path,fault):
 s,r,entry,position=setup(code,tmp_path)
 try:
  cert=certificate(code,s,r,healthy=lambda:fault!='transport');s._management_certificate=cert;s._management_dispatch_enabled=True
  o=order();now=NOW
  if fault=='wrong_side':o.side=N(name='BUY')
  elif fault=='too_large':o.quantity=Q('11')
  elif fault=='foreign':o.strategy_id='foreign'
  elif fault=='increase':o.is_reduce_only=False
  elif fault=='stale':now=NOW+9_000_000_001
  elif fault=='revision':r._bump_native_revision();r.db.commit()
  elif fault=='policy':s.config.research_c1_restore_dd=D('.40')
  elif fault=='checkpoint':s._c1_state['credit']=2
  with pytest.raises(RuntimeError):s.dispatch_manage_only('bad','REDUCE',o,now_ns=now)
  assert s._management_certificate is None and not s.dispatched and len(r.all_submissions())==1
 finally:r.close()

def test_cancel_unknown_ack_and_late_fill_do_not_clear_or_resubmit_reduce(code,tmp_path):
 s,r,entry,position=setup(code,tmp_path);tp=order('TP',side='SELL',quantity='2')
 try:
  r.record_submission(client_order_id='TP',intent_id='tp',episode_id='episode',action='BTC_REDUCE',instrument_id=str(s.config.btc_id),quantity='2',reduce_only=True,strategy_state=s.on_save()[code.env['_KEY']]);r.acknowledge_submission('TP')
  s.cache.orders=lambda venue=None:[entry,tp]
  s._management_certificate=certificate(code,s,r);s._management_dispatch_enabled=True
  s.dispatch_manage_only('cancel','CANCEL',tp,now_ns=NOW)
  assert s.dispatched==[('CANCEL','TP')]
  # Cancel request and a late partial fill are not terminal/native flat.
  position.quantity=Q('9');tp.filled_qty=Q('1');tp.status=N(name='PARTIALLY_FILLED')
  s._management_certificate=certificate(code,s,r)
  with pytest.raises(RuntimeError):s.dispatch_manage_only('reduce','REDUCE',order(),now_ns=NOW)
  assert r.db.execute("SELECT status FROM paper_command_audit WHERE idempotency_key='cancel'").fetchone()[0]=='MANAGE_SUBMITTING'
  assert not s.recovery_confirmed and not s._entries_enabled()
  # Only an explicit fresh full report of native terminal may retire reservation.
  tp.is_closed=True;tp.status=N(name='CANCELED');r.terminal_submission('TP',s.on_save()[code.env['_KEY']])
  r.reconcile_management_commands({'TP'},r.native_revision())
  s._management_certificate=certificate(code,s,r)
  s.dispatch_manage_only('reduce','REDUCE',order(),now_ns=NOW)
  assert s.dispatched==[('CANCEL','TP'),('REDUCE','NEW')]
 finally:r.close()

def test_durable_cursor_uses_saved_fill_not_now_and_unknown_reduce_survives_restart(code,tmp_path):
 s,r,entry,position=setup(code,tmp_path)
 try:
  scope=code.management['durable_management_scope'](r,ACCOUNT,'',lambda client:'fixture-'+client)
  assert scope.anchor_ms==1 and scope.anchor_tid==10 and len(scope.durable_orders)==1
  s._management_dispatch_enabled=True;s._management_certificate=certificate(code,s,r)
  s.dispatch_manage_only('reduce','REDUCE',order(),now_ns=NOW)
  r.close()
  r=code.Runtime(tmp_path/'fixture.sqlite','synthetic-owner',10**20);r.acquire();r.acquire_live_account(ACCOUNT,'HYPERLIQUID',lock_root=tmp_path/'locks')
  assert r.db.execute("SELECT status FROM paper_command_audit WHERE idempotency_key='reduce'").fetchone()[0]=='MANAGE_SUBMITTING'
  assert any(row['client_order_id']=='NEW' and row['state']=='SUBMITTING' for row in r.all_submissions())
  assert not r.reserve_management(command_id='new',kind='REDUCE',client_order_id='NEW2',instrument_id=str(s.config.btc_id),quantity='1',side='SELL',episode_id='episode',expected_revision=r.native_revision(),strategy_state=r.strategy_checkpoint()[0])
 finally:r.close()

def test_owned_decision_projection_preserves_global_h_identity(code):
 s=code.Strategy(config());old=code.env['durable_decision_checkpoint'](s.on_save()[code.env['_KEY']]);s._c1_peak=D(20000)
 assert code.env['durable_decision_checkpoint'](s.on_save()[code.env['_KEY']])!=old
 # Flat-epoch code must explicitly refuse retiring the C1 checkpoint.
 text=ast.unparse(next(n for n in nodes('ops/hl_live_epoch.py',{'LiveEpochRuntime'}) if isinstance(n,ast.ClassDef)))
 assert text.index('C1_E4_CHECKPOINT_REQUIRES_MANAGE_ONLY')<text.index('self._retired_checkpoint = checkpoint')

class Boundary:pass
class ReportError(RuntimeError):pass


def bind_fixture(code,s,r,entry,position,*,fault=None):
 scope=code.management['NativeLiveRecoveryScope'](ACCOUNT,'',1,10,(('ENTRY','fixture',100),),frozenset({'BTC','SOL'}))
 report=N(client_order_id=entry.client_order_id,instrument_id=entry.instrument_id,venue_order_id=entry.venue_order_id,quantity=entry.quantity,
  filled_qty=entry.filled_qty,order_status=entry.status,reduce_only=False,account_id=ACCOUNT_ID,order_side=entry.side)
 position_report=N(instrument_id=position.instrument_id,account_id=ACCOUNT_ID,position_side=N(name='LONG'),quantity=Q('10'))
 mass=N(account_id=ACCOUNT_ID,venue=VENUE,order_reports={'ENTRY':report},fill_reports={'ENTRY':[N(trade_id='10')]},position_reports={position.instrument_id:[position_report]})
 class Client(Boundary):
  def __init__(self):
   self._cm_scope=scope;self._cm_bootstrapped=False;self._cm_last_revision=r.native_revision()
   self._cm_last_receipt=N(account=ACCOUNT,dex='',end_ms=NOW//1_000_000,fill_anchor_proven=True)
   self._cache=s.cache;self._msgbus=s.msgbus;self.trader_id=s.trader_id;self.venue=VENUE;self.account_id=ACCOUNT_ID
   self._clock=N(timestamp_ns=lambda:NOW);self.healthy=False
  def recovery_healthy(self):return self.healthy
  def request_effect_parity_refresh(self):return False
  def bind_recovery_revocation(self,callback):self.revoke=callback
  def bind_recovery_suspension(self,suspend,resume):self.suspend=suspend;self.resume=resume
  async def release_after_effect_parity(self,verify,**kwargs):
   self.verify=verify;assert await verify(mass) is True;self.healthy=True
 client=Client()
 if fault=='stale':client._cm_last_receipt.end_ms=-10000
 elif fault=='revision':client._cm_last_revision-=1
 elif fault=='foreign_position':position.strategy_id='foreign'
 elif fault=='account':position.account_id='FOREIGN_ACCOUNT'
 elif fault=='missing_fill':mass.fill_reports={}
 elif fault=='policy':s.config.research_c1_restore_dd=D('.40')
 elif fault=='order_side':report.order_side=N(name='SELL')
 elif fault=='different_episode':position.events=[N(client_order_id='FOREIGN_EPISODE',trade_id='10')]
 elif fault=='smaller_venue':position_report.quantity=Q('7')
 elif fault=='wrong_position_side':position_report.position_side=N(name='SHORT')
 elif fault=='missing_position_report':mass.position_reports={}
 elif fault=='extra_native_position':
  extra=N(**vars(position));extra.instrument_id=s.config.sol_id;extra.id='EXTRA_POSITION';s.cache.positions_open=lambda:[position,extra]
 elif fault=='extra_position_report':mass.position_reports[s.config.sol_id]=[N(instrument_id=s.config.sol_id,account_id=ACCOUNT_ID,position_side=N(name='SHORT'),quantity=Q('1'))]
 elif fault=='duplicate_position_report':mass.position_reports[position.instrument_id].append(position_report)
 namespace=dict(RecoverableWaveOverlayStrategy=code.Strategy,QualifiedInfoBoundary=Boundary,
  InstrumentId=ID,IncompleteInfoReport=ReportError,Decimal=D,hashlib=hashlib,OrderStatus=N(DENIED=N(name="DENIED")),OrderDenied=Placeholder,
  durable_decision_checkpoint=code.env['durable_decision_checkpoint'])
 run_ast(nodes('ops/hl_live_execution.py',{'_proven_local_denial','bind_clean_flat_live_handover'}),namespace)
 namespace['bind_clean_flat_live_handover'](client,s,r,manage_only=True)
 return client,mass


def test_complete_owned_report_grants_only_ephemeral_manage_certificate(code,tmp_path):
 s,r,entry,position=setup(code,tmp_path)
 try:
  client,mass=bind_fixture(code,s,r,entry,position)
  asyncio.run(s._post_drain_verifier())
  assert client._cm_bootstrapped and s._management_certificate is not None
  assert not s.recovery_confirmed and not s._entries_enabled() and not s._management_dispatch_enabled
  client.revoke();assert s._management_certificate is None and not s.recovery_confirmed
 finally:r.close()

@pytest.mark.parametrize('fault',['stale','revision','foreign_position','account','missing_fill','policy','order_side','different_episode','smaller_venue','wrong_position_side','missing_position_report','extra_native_position','extra_position_report','duplicate_position_report'])
def test_management_report_mismatch_never_grants_authority(code,tmp_path,fault):
 s,r,entry,position=setup(code,tmp_path)
 try:
  client,mass=bind_fixture(code,s,r,entry,position,fault=fault)
  with pytest.raises((ReportError,RuntimeError,ValueError)):asyncio.run(s._post_drain_verifier())
  assert s._management_certificate is None and not s.recovery_confirmed and not s.dispatched
 finally:r.close()

@pytest.mark.parametrize('method',['submit_order','submit_order_list','modify_order','cancel_order','cancel_orders','cancel_all_orders','close_position','close_all_positions'])
def test_generic_native_methods_remain_blocked_for_c1_even_if_legacy_flag_is_true(code,method):
 s=code.Strategy(config());s.recovery_confirmed=True
 with pytest.raises(RuntimeError,match='MANAGE_ONLY_NORMAL_DISPATCH_FORBIDDEN'):getattr(s,method)(object())
 assert not s._entries_enabled()


def test_two_concurrent_certificates_cannot_collectively_reduce_same_held_position(code,tmp_path):
 from concurrent.futures import ThreadPoolExecutor
 from threading import Barrier
 s,r,entry,position=setup(code,tmp_path)
 try:
  other=code.Strategy(config());other.on_load(s.on_save());other.enable_manage_only_preparation();other.attach_recovery_runtime(r);other.cache=s.cache
  cert=certificate(code,s,r);s._management_certificate=cert;other._management_certificate=cert
  s._management_dispatch_enabled=other._management_dispatch_enabled=True
  barrier=Barrier(2)
  def send(pair):
   owner,name=pair;barrier.wait()
   try:owner.dispatch_manage_only(name,'REDUCE',order(name,quantity='7'),now_ns=NOW);return True
   except RuntimeError:return False
  with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(send,[(s,'A'),(other,'B')]))
  assert sorted(outcomes)==[False,True]
  assert len(s.dispatched)+len(other.dispatched)==1
  assert len(r.all_submissions())==2 # One old opening + exactly one new owned reduction.
 finally:r.close()


def test_c1_flat_epoch_refuses_retirement_and_keeps_global_h_checkpoint(code,tmp_path):
 from coinmaster.domain.deposit_protection import DepositProtection
 s,r,entry,position=setup(code,tmp_path)
 try:
  s._domain.episode=None;checkpoint=s.on_save()[code.env['_KEY']]
  assert r.persist_strategy_checkpoint(checkpoint,r.native_revision())
  protection=DepositProtection();protection.initialize(D(10000),86_400_000_000_000)
  r.save_deposit_protection(instance_id=r.owner,account_id='HYPERLIQUID-master',action='INITIALIZED',event_key='fixture',state=protection.durable(),ts_ns=86_400_000_000_000)
  body=dict(native_revision=r.native_revision(),reconciled=True,positions=[],orders=[],native_account_currency='USDC',native_account_total='10000')
  r.db.execute('INSERT OR REPLACE INTO paper_snapshot VALUES (1,?)',(json.dumps(body),));r.db.commit()
  with pytest.raises(RuntimeError,match='C1_E4_CHECKPOINT_REQUIRES_MANAGE_ONLY'):r.prepare_flat_epoch(release_commit='synthetic')
  assert r.strategy_checkpoint()[0]==checkpoint and len(r.all_submissions())==1
  assert code.env['_decode'](json.loads(checkpoint)['state']['_c1_peak'])==D(15000)
 finally:r.close()

@pytest.mark.parametrize('fault',['venue_order_id','instrument_id','account_id'])
def test_cancel_same_owned_client_id_cannot_substitute_uncertified_order(code,tmp_path,fault):
 s,r,entry,position=setup(code,tmp_path);tp=order('TP',quantity='2')
 try:
  r.record_submission(client_order_id='TP',intent_id='tp',episode_id='episode',action='BTC_REDUCE',instrument_id=str(s.config.btc_id),quantity='2',reduce_only=True,strategy_state=s.on_save()[code.env['_KEY']]);r.acknowledge_submission('TP')
  s.cache.orders=lambda venue=None:[entry,tp]
  substitute=N(**vars(tp))
  if fault=='venue_order_id':substitute.venue_order_id='999'
  elif fault=='instrument_id':substitute.instrument_id=s.config.sol_id
  else:substitute.account_id='FOREIGN_ACCOUNT'
  s._management_certificate=certificate(code,s,r);s._management_dispatch_enabled=True
  with pytest.raises(RuntimeError,match='MANAGEMENT_CANCEL_OWNERSHIP_UNKNOWN'):s.dispatch_manage_only('bad-cancel','CANCEL',substitute,now_ns=NOW)
  assert not s.dispatched and s._management_certificate is None
  assert not r.db.execute('SELECT 1 FROM paper_command_audit').fetchall()
 finally:r.close()


def test_cancel_dispatch_uses_certified_current_cache_object_instead_of_identical_caller_copy(code,tmp_path):
 s,r,entry,position=setup(code,tmp_path);tp=order('TP',quantity='2')
 try:
  r.record_submission(client_order_id='TP',intent_id='tp',episode_id='episode',action='BTC_REDUCE',instrument_id=str(s.config.btc_id),quantity='2',reduce_only=True,strategy_state=s.on_save()[code.env['_KEY']]);r.acknowledge_submission('TP')
  s.cache.orders=lambda venue=None:[entry,tp];copy=N(**vars(tp))
  s._management_certificate=certificate(code,s,r);s._management_dispatch_enabled=True
  s.dispatch_manage_only('cancel','CANCEL',copy,now_ns=NOW)
  assert s.last_cancel_object is tp and s.last_cancel_object is not copy
  assert s.dispatched==[('CANCEL','TP')]
 finally:r.close()
