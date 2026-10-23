from pathlib import Path
R=Path('/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023')
p=R/'runtime/coinmaster/strategy/residual_recovery.py';s=p.read_text().replace('self._c1_terminal_ids=set()','self._c1_terminal_ids=set();self.c1_denials={};self._c1_blocked_ids=set()')
s=s.replace("        if i is None or i.id not in self._c1_intents:self._c1_revoke(event.ts_event,'ACTUAL_ORDINARY_OR_MANDATORY_FILL')", "        if i is None or i.id not in self._c1_intents:self._c1_revoke(event.ts_event,'ACTUAL_ORDINARY_OR_MANDATORY_FILL')\n        else:self._c1_log('NATIVE_FILL_RECEIPT',event.ts_event,order_id=str(event.client_order_id),trade_id=str(event.trade_id),intent_id=i.id,quantity=str(event.last_qty),price=str(event.last_px),commission=str(event.commission))")
needle="        self._c1_log('PROPOSED_DECISION',ns,source_quote_ns=source"
s=s.replace(needle,"        if not all(gates.values()):\n            from datetime import datetime,timezone\n            key=str((ep.id,datetime.fromtimestamp(ns/1e9,timezone.utc).strftime('%Y-%m'),tuple(sorted(gates.items()))))\n            old=self.c1_denials.get(key)\n            if old is not None:old['count']+=1;old['last_ns']=ns;return\n            self.c1_denials[key]=dict(count=1,first_ns=ns,last_ns=ns,gates=gates,group=ep.id)\n"+needle)
s=s.replace("        self._discard_queued_intents(lambda i:i.action in ('BTC_ENTRY','SOL_ADD'))", "        self._discard_queued_intents(lambda i:self._c1_discard_increase(i,ns))")
s=s.replace("    def _c1_quote(self,tick):", "    def _c1_discard_increase(self,i,ns):\n        if i.action not in ('BTC_ENTRY','SOL_ADD'):return False\n        if i.id not in self._c1_blocked_ids:\n            self._c1_blocked_ids.add(i.id);self._c1_log('QUEUED_INCREASE_BLOCKED',ns,intent_id=i.id,action=i.action,rights=self._c1_rights())\n        return True\n\n    def _c1_quote(self,tick):")
p.write_text(s)
p=R/'runtime/coinmaster/research/native_baseline.py';s=p.read_text().replace('result["c1_audit"]=strategy.c1_audit','result["c1_audit"]=strategy.c1_audit\n            result["c1_denial_counts"]=strategy.c1_denials');p.write_text(s)
tests='''from decimal import Decimal as D
from copy import deepcopy
from types import SimpleNamespace
import pytest
from coinmaster.domain.wave_overlay import Candidate,Episode
from coinmaster.strategy.next_band import next_closed_bar,H4,DAY
from coinmaster.strategy.residual_recovery import CUT,RESTORE
from coinmaster.research.minute_risk import _native_account_money
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from test_native_next_band import cfg
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks
from test_native_btc_sizing import prepare_day
from test_wave_native_integration import native_engine,lifecycle_config

def held(asset='BTC',side=1,cls=NativeProbe):
 s=cls(cfg(research_wait_4h=True,research_residual_recovery=True,candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))))
 e=native_engine(s);run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)])
 prepare_day(s,2,side);ep=s._domain.episode=Episode('c1',side,10000,1,wave_levels=(.50,.60,.70),btc_planref_vwap=D(100))
 i=s._domain._intent(ep,'BTC_ENTRY',side,None,quantity=100)
 s._submit_intent(i,100,100,None,2,ts_now=2);run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
 s._split_parent=dict(episode_id=ep.id,closed=True,start_ns=2,management_reference_frozen_ns=3,planref_v1_beta=2.)
 if asset=='SOL':
  i=s._domain._intent(ep,'SOL_ADD',-side,0,quantity=100)
  s._submit_intent(i,100,100,.01,2,ts_now=5);run_ticks(e,[tick(SOL_PERP,6),tick(SOL_PERP,7)])
 return s,e,ep

def observe(s,ns,btc='55',sol='100',equity=None):
 details=[];E=_native_account_money(s.cache.account_for_venue(BTC_PERP.id.venue))
 for p in s.cache.positions_open():
  inst=s.cache.instrument(p.instrument_id);mark=D(btc if p.instrument_id==BTC_PERP.id else sol)
  E+=p.unrealized_pnl(inst.make_price(mark)).as_decimal()
  details.append(dict(instrument_id=str(p.instrument_id),side=str(p.side),quantity=str(p.quantity),avg_px_open=str(p.avg_px_open),mark_ohlc=dict(close=str(mark))))
 s._c1_observe(E if equity is None else D(equity),ns,ns-1,s._c1_fill_epoch,details)
 return E

def cut(s,e,asset='BTC',price='55',size='1000'):
 ns=1000;observe(s,ns,btc=price if asset=='BTC' else '100',sol=price if asset=='SOL' else '100')
 inst=BTC_PERP if asset=='BTC' else SOL_PERP
 for n in range(1,7):run_ticks(e,[tick(inst,ns+n,price,size)])
 return ns+6

@pytest.mark.parametrize('side',[1,-1])
def test_actual_halfcut_restore_native_money_original_btc_basis_rights_and_one_group(side):
 s,e,ep=held(side=side)
 try:
  original=(ep.btc_initial_qty,deepcopy(ep.btc_tp_target_lots),ep.btc_planref_vwap,ep.h,deepcopy(ep.sol_add_filled_notional))
  adverse='55' if side==1 else '145';cut(s,e,price=adverse)
  t=s._c1_state;assert t['state']=='HELD' and t['cut_filled']==50000 and t['credit']==50000
  assert ep.btc_open_qty==50 and not ep.sol_rights and sum(ep.btc_risk_retired_lots.values())==50000
  saved_targets=deepcopy(ep.btc_tp_target_lots)
  # Partial/incomplete4h candle, or one whose open precedes terminal, cannot confirm.
  observe(s,H4,btc='80' if side==1 else '120')
  s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(80),D(80),D(80),D(80),H4).data)
  assert t['confirmation'] is None
  restore='80' if side==1 else '120';observe(s,2*H4,btc=restore)
  s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(restore),D(restore),D(restore),D(restore),2*H4).data)
  assert t['confirmation'] is not None
  for n in range(1,6):run_ticks(e,[tick(BTC_PERP,2*H4+n,restore)])
  assert t['state']=='RELEASED' and t['restore_filled']==50000 and t['credit']==0
  assert ep.btc_open_qty==100 and sum(ep.btc_risk_retired_lots.values())==0 and not ep.sol_rights
  assert original==(ep.btc_initial_qty,saved_targets,ep.btc_planref_vwap,ep.h,ep.sol_add_filled_notional)
  observe(s,3*H4,btc=adverse);run_ticks(e,[tick(BTC_PERP,3*H4+1,adverse)])
  assert len([x for x in s.c1_audit if x['event']=='CLAIM'])==1
 finally:e.end();e.dispose()

def test_sol_original_consumption_clocks_sigma_preserved_and_increases_blocked():
 s,e,ep=held(asset='SOL',side=-1)
 try:
  # Remove BTC risk causally through its ordinary reduce, leaving original group SOL.
  i=s._domain._intent(ep,'BTC_REDUCE',1,2,quantity=100,reason='BTC_TP3');s._submit_intent(i,100,100,None,2,ts_now=10)
  run_ticks(e,[tick(BTC_PERP,11),tick(BTC_PERP,12)])
  original=(deepcopy(ep.sol_add_filled_notional),ep.sol_first_fill_at,ep.fixed_sigma,ep.sol_half_done,ep.h,ep.btc_planref_vwap)
  cut(s,e,asset='SOL',price='55')
  t=s._c1_state;assert t['instrument']==SOL_PERP.id and t['cut_filled']==500 and ep.sol_qty==50
  for action in ['BTC_ENTRY','SOL_ADD']:
   i=s._domain._intent(ep,action,1,0,quantity=1);s._submit_intent(i,55,55,.01,2,ts_now=2000)
   assert i.id not in ep.pending
  observe(s,2*H4,btc='100',sol='80');s._c1_closed_bar(next_closed_bar(SOL_PERP.id,4,D(80),D(80),D(80),D(80),2*H4).data)
  for n in range(1,6):run_ticks(e,[tick(SOL_PERP,2*H4+n,'80')])
  assert t['restore_filled']==500 and ep.sol_qty==100 and s._c1_sol_levels[ep.id]=={0:1000}
  assert original==(ep.sol_add_filled_notional,ep.sol_first_fill_at,ep.fixed_sigma,ep.sol_half_done,ep.h,ep.btc_planref_vwap)
 finally:e.end();e.dispose()

def test_inherited_cash_loss_strict_dominance_parent_busy_stale_and_denials_bounded():
 s,e,ep=held()
 try:
  observe(s,1000,btc='99',equity='5900');assert s._c1_state is None # open loss100 < cushion900
  s._split_parent['closed']=False
  for ns in range(1001,1010):observe(s,ns,btc='55')
  assert s._c1_state is None and len(s.c1_denials)==1 and next(iter(s.c1_denials.values()))['count']==9
  s._split_parent['closed']=True;observe(s,2000,btc='55');assert s._c1_state is not None
  c=s._c1_checkpoint
  assert s._c1_current_money(c['source']) is None
  assert s._c1_current_money(c['source']+s.config.max_mark_age_ns+1) is None
  s._c1_fill_epoch+=1;assert s._c1_current_money(2001) is None
 finally:e.end();e.dispose()

def test_partial_cut_actual_credit_ordinary_exit_revocation_no_extra_cut_or_restore():
 s,e,ep=held()
 try:
  cut(s,e,price='55',size='3');t=s._c1_state
  assert 0<t['cut_filled']<=50000 and t['credit']==t['cut_filled']
  count=t['cut_filled'];assert ep.btc_open_qty==float(D(100)-D(count)*D('.001'))
  i=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=1,reason='BTC_TP3')
  s._submit_intent(i,55,55,None,2,ts_now=2000)
  assert t['revoked'] and t['credit']==0
  for n in range(1,4):run_ticks(e,[tick(BTC_PERP,2000+n,'55')])
  assert t['restore_filled']==0
 finally:e.end();e.dispose()

def test_default_off_and_temporary_tp_cancel_is_not_ordinary_exit():
 assert not lifecycle_config().research_residual_recovery
 s,e,ep=held()
 try:
  i=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=10,limit_price=150,reason='BTC_TP3')
  s._submit_intent(i,100,100,None,2,ts_now=10);run_ticks(e,[tick(BTC_PERP,11)])
  cut(s,e);assert s._c1_state['credit']==50000 and not s._c1_state['revoked']
 finally:e.end();e.dispose()
'''
(R/'runtime/tests/test_native_residual_recovery.py').write_text(tests)
# Reuse separately approved precision regressions verbatim from source correction.
import subprocess
p=R/'runtime/tests/test_native_report_precision.py';p.write_bytes(subprocess.check_output(['git','-C',str(R),'show','6061446164cc32c27b3ea0e13e86c9cc56d955ac:runtime/tests/test_native_report_precision.py']))
print('Native C1 fixtures written, denial aggregation added')
