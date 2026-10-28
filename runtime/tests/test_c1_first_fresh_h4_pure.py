"""Actual C1 methods, pure native-interface doubles; no Nautilus constructors.
Two archived R windows prove scheduling mechanics, never COMBO counterfactual ROI.
"""
import ast
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import pytest
ROOT=Path(__file__).parents[1]/'coinmaster'
TREE=ast.parse((ROOT/'strategy/residual_recovery.py').read_text())
CLASS=next(n for n in TREE.body if isinstance(n,ast.ClassDef))
ENV=dict(D=D,H4=14_400_000_000_000,CUT='CUT',RESTORE='RESTORE',OrderSide=N(BUY='BUY',SELL='SELL'))
exec(compile(ast.Module(body=[CLASS],type_ignores=[]),'actual_C1','exec'),ENV)
H4=14_400_000_000_000;MINUTE=60_000_000_000
class ID(str):venue='TEST'
class Price(D):
 def as_decimal(self):return D(self)
def price(x):return Price(str(x))
class Owner(ENV['ResidualRecoveryResearch']):
 def __init__(self,window='OCT',enabled=True):
  oct=window=='OCT';self.close_ns=1728028800000000000 if oct else 1764259200000000000
  self.market='139.47' if oct else '90908';self.executable='139.45' if oct else '90866'
  self.dd=D('.3679014107580292346733937325' if oct else '.3894293228928525531484198648')
  self.config=N(research_c1_btc_cut_divisor=4,research_c1_restore_dd=D('.40'),research_c1_global_cut_arm=False,
   research_c1_first_fresh_h4=enabled,active_seed=D(10000),research_residual_recovery=True,research_wait_4h=True,
   research_regime_reentry_band=D('.5'),research_zero_retrace=False,research_sol_dominant=False,research_wait_persist=False,
   max_mark_age_ns=2*MINUTE,btc_id=ID('BTC'),sol_id=ID('SOL'),terminal_close_at_ns=None)
  self._c1_init();self._c1_fill_epoch=18 if oct else 380
  inst=self.config.sol_id if oct else self.config.btc_id;step=D('.1' if oct else '.001');lots=5000 if oct else 79592
  self._c1_state=dict(group='g',instrument=inst,side=1 if oct else -1,state='HELD',restore_submitted=False,
   native_position_id='owned',native_position_open_ns=1,cut_filled=lots,cut_value=D('135.30' if oct else '91057.1')*D(lots)*step,
   credit=lots,bucket={1:lots},step=step,last_cut_fill_ns=self.close_ns-2*H4,cut_terminal_ns=self.close_ns-2*H4+1,
   revoked=False,confirmation=None,claim_ns=1)
  self.account=N(last_event=N(ts_event=self.close_ns));self.orders=[];self.inflight=[];self._pending_by_order={};self._queued_intents=[]
  self.cache=N(account_for_venue=lambda _:self.account,orders_open=lambda:self.orders,orders_inflight=lambda:self.inflight,
    instrument=lambda _:N(min_quantity=None,min_notional=None))
  self._domain=N(episode=N(id='g'),_intent=lambda ep,action,side,level,**kw:N(id='restore',episode_id=ep.id,action=action,side=side,**kw))
  self._forced_close_reason=None;self._liquidating=False;self._mandatory_sol_exit=None;self._bars=[];self.cancelled=[];self.submitted=[]
 def _c1_rights(self):return {}
 def _c1_conflict(self):return False
 def _c1_harmless_tp(self,i):return True
 def _discard_queued_intents(self,predicate):pass
 def cancel_order(self,o):self.cancelled.append(o);o.is_pending_cancel=True
 def _entries_enabled(self):return True
 def _tier_allows_increase(self,*a):return True
 def _submit_intent(self,i,*a,**kw):
  self.submitted.append(i);self._pending_by_order['restore']=i;self._c1_state.setdefault('native_order_ids',{})[i.id]='restore'
 def bar(self,offset=0,close=None):
  ns=self.close_ns+offset
  return N(hours=4,instrument_id=self._c1_state['instrument'],ts_event=ns,ts_init=ns,open_time_ns=ns-H4,close=price(close or self.market))
 def quote(self,offset=MINUTE,value=None,instrument=None):
  return N(ts_event=self.close_ns+offset,instrument_id=instrument or self._c1_state['instrument'],ask_price=price(value or self.executable),bid_price=price(value or self.executable))
 def money(self,source=None,receipt=None,epoch=None,dd=None):
  self._c1_checkpoint=dict(source=self.close_ns if source is None else source,receipt=self.close_ns+MINUTE if receipt is None else receipt,
    epoch=self._c1_fill_epoch if epoch is None else epoch,DD=self.dd if dd is None else D(dd),E=D(6000),H=D(10000))
 def capture(self):
  # Funding AccountState at bar close invalidates prior-minute money.
  self.money(source=self.close_ns-MINUTE,receipt=self.close_ns-1,epoch=self._c1_fill_epoch-1)
  self._c1_closed_bar(self.bar());assert self._c1_state['confirmation'] is None
  assert self._c1_state['first_fresh_deferred']['identity']['fill_epoch']==self._c1_fill_epoch

@pytest.mark.parametrize('window',['OCT','NOV'])
def test_two_actual_funding_windows_promote_then_wait_real_cancel_ack_and_recheck(window):
 s=Owner(window);s.capture();s.money()
 tp=N(id='tp',action='BTC_REDUCE');o=N(client_order_id='tp',is_pending_cancel=False)
 s._pending_by_order['tp']=tp;s.orders=[o]
 s._c1_quote(s.quote());t=s._c1_state
 assert 'first_fresh_deferred' not in t and t['confirmation']['close_ns']==s.close_ns
 assert s.cancelled==[o] and not s.submitted and not t['restore_submitted']
 # No fresh receipt after ACK means no submit, and keeps promoted legacy token.
 s._pending_by_order.clear();s.orders.clear();s._c1_quote(s.quote(3*MINUTE));assert not s.submitted and t['confirmation']
 s.money(source=s.close_ns+3*MINUTE,receipt=s.close_ns+4*MINUTE)
 s._c1_quote(s.quote(4*MINUTE));assert len(s.submitted)==1 and t['restore_committed']==t['credit']

@pytest.mark.parametrize('fault',['stale','mixed','future','prebar','sameclock','otherinstrument'])
def test_no_valid_first_fresh_retains_market_candidate_without_permit(fault):
 s=Owner();s.capture();s.money();q=s.quote()
 if fault=='stale':q=s.quote(4*MINUTE)
 if fault=='mixed':s._c1_checkpoint['epoch']-=1
 if fault=='future':s._c1_checkpoint['receipt']=q.ts_event+1
 if fault=='prebar':s._c1_checkpoint['source']=s.close_ns-1;s.account.last_event.ts_event=s.close_ns-1
 if fault=='sameclock':q=s.quote(0);s.money(source=s.close_ns-1,receipt=s.close_ns)
 if fault=='otherinstrument':q=s.quote(instrument=s.config.btc_id)
 s._c1_quote(q)
 assert s._c1_state.get('first_fresh_deferred') and s._c1_state['confirmation'] is None and not s.submitted

@pytest.mark.parametrize('fault',['dd','price','epoch','group','credit','bucket','position','revoked'])
def test_first_fresh_denial_consumes_once_no_retry_until_new_h4(fault):
 s=Owner();s.capture();t=s._c1_state;s.money();q=s.quote()
 if fault=='dd':s._c1_checkpoint['DD']=D('.4000001')
 if fault=='price':q=s.quote(value='135.30')
 if fault=='epoch':s._c1_fill_epoch+=1;s.money()
 if fault=='group':s._domain.episode.id='other'
 if fault=='credit':t['credit']-=1
 if fault=='bucket':t['bucket'][1]-=1
 if fault=='position':t['native_position_id']='other'
 if fault=='revoked':s._c1_revoke(q.ts_event,'ORDINARY')
 s._c1_quote(q);assert not t.get('first_fresh_deferred') and t['confirmation'] is None and not s.submitted
 s.money();s._c1_closed_bar(s.bar());assert not t.get('first_fresh_deferred')


def test_new_bar_price_failure_invalidates_deferred_but_not_ordinary_confirmation():
 s=Owner();s.capture();s._c1_closed_bar(s.bar(H4,close='100'));assert not s._c1_state.get('first_fresh_deferred')
 token=dict(close_ns=1,open_ns=0,close=D(140));s._c1_state['confirmation']=token
 s._c1_closed_bar(s.bar(2*H4,close='100'));assert s._c1_state['confirmation'] is token


def test_capture_requires_whole_bar_after_cut_and_reclaim_and_no_existing_token():
 for fault in ['cut_inside','wrong_price','confirmed']:
  s=Owner();t=s._c1_state
  if fault=='cut_inside':t['cut_terminal_ns']=s.close_ns-H4
  if fault=='confirmed':t['confirmation']={'close_ns':1}
  s._c1_closed_bar(s.bar(close='100' if fault=='wrong_price' else None));assert not t.get('first_fresh_deferred')


def test_default_off_preserves_discard_and_fresh_legacy_bar_path():
 s=Owner(enabled=False);s._c1_closed_bar(s.bar());assert not s._c1_state.get('first_fresh_deferred') and s._c1_state['confirmation'] is None
 s.money(source=s.close_ns-2,receipt=s.close_ns-1);s.account.last_event.ts_event=s.close_ns-2
 s._c1_closed_bar(s.bar());assert s._c1_state['confirmation']['close_ns']==s.close_ns
 assert 'first_fresh_last_h4_ns' not in s._c1_state


def test_actual_runner_plumbing_is_default_off_and_validated_combo_only():
 tree=ast.parse((ROOT/'research/native_baseline.py').read_text())
 functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('run_research_v0_repairs_cli','run_native_baseline')]
 assert functions
 for fn in functions:
  args=fn.args.args+fn.args.kwonlyargs;defaults=[None]*(len(fn.args.args)-len(fn.args.defaults))+fn.args.defaults+fn.args.kw_defaults
  assert any(a.arg=='research_c1_first_fresh_h4' and isinstance(d,ast.Constant) and d.value is False for a,d in zip(args,defaults))
 assert 'FIRST_FRESH_REQUIRES_COMBO_Q_R_NO_G' in ast.unparse(tree)
 s=Owner();s.config.research_c1_btc_cut_divisor=2
 with pytest.raises(ValueError,match='FIRST_FRESH_REQUIRES_COMBO'):s._c1_init()


def test_native_admission_denial_consumes_promoted_token_without_spending_attempt():
 s=Owner();s.capture();s.money();s._tier_allows_increase=lambda *a:False
 s._c1_quote(s.quote());t=s._c1_state
 assert not t.get('first_fresh_deferred') and t['confirmation'] is None and not t['restore_submitted'] and not s.submitted
 s._tier_allows_increase=lambda *a:True;s._c1_quote(s.quote(MINUTE+1));assert not s.submitted


def test_delayed_bar_availability_is_strict_and_group_reset_has_no_deferred_leak():
 s=Owner();bar=s.bar();bar.ts_init+=MINUTE;s._c1_closed_bar(bar);s.money()
 s._c1_quote(s.quote());assert s._c1_state.get('first_fresh_deferred')
 s._c1_quote(s.quote(MINUTE+1));assert not s._c1_state.get('first_fresh_deferred') and s.submitted
 q=s.quote();s._c1_state=None;s._c1_quote(q);assert len(s.submitted)==1
