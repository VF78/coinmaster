"""R restores at DD40; all held credit, ownership and revoke-release semantics stay C1."""
from copy import deepcopy
from decimal import Decimal as D
import pytest
from test_native_residual_recovery import held,cut,observe
from test_native_episode_risk import NativeProbe,run_ticks,tick
from coinmaster.research.native_fixture import BTC_PERP
from coinmaster.strategy.next_band import next_closed_bar,H4


def confirm(s,side,ns=2*H4,equity='6400'):
 reclaim='80' if side==1 else '120'
 observe(s,ns,btc=reclaim,equity=equity)
 s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(reclaim),D(reclaim),D(reclaim),D(reclaim),ns).data)
 return reclaim

@pytest.mark.parametrize('side',[1,-1])
def test_r_both_restore_gates_admit_dd36_and_exact_actual_credit(side):
 s,e,ep=held(side=side,restore_dd=D('.40'))
 try:
  cut(s,e,price='55' if side==1 else '145');t=s._c1_state
  assert t['cut_lots']==50000 and t['target_lots']==50000
  rights=(deepcopy(ep.btc_tp_target_lots),ep.btc_planref_vwap,ep.h,deepcopy(ep.sol_add_filled_notional))
  reclaim=confirm(s,side);assert t['confirmation'] is not None
  for n in range(1,6):
   observe(s,2*H4+n,btc=reclaim,equity='6400');run_ticks(e,[tick(BTC_PERP,2*H4+n,reclaim)])
  assert t['restore_filled']==50000 and t['credit']==0 and ep.btc_open_qty==100
  assert sum(ep.btc_risk_retired_lots.values())==0 and not ep.sol_rights
  assert rights==(ep.btc_tp_target_lots,ep.btc_planref_vwap,ep.h,ep.sol_add_filled_notional)
  witness=next(x for x in s.c1_audit if x['event']=='ATTEMPT_SUBMIT' and x['kind']=='RESTORE')
  assert D('.35')<D(witness['DD'])<=D('.40')
 finally:e.end();e.dispose()

@pytest.mark.parametrize('side',[1,-1])
def test_r_quote_above40_clears_confirmation_and_does_not_restore_later_without_new_bar(side):
 s,e,ep=held(side=side,restore_dd=D('.40'))
 try:
  cut(s,e,price='55' if side==1 else '145');t=s._c1_state
  reclaim=confirm(s,side);assert t['confirmation']
  observe(s,2*H4+1,btc=reclaim,equity='5900');run_ticks(e,[tick(BTC_PERP,2*H4+1,reclaim)])
  assert t['confirmation'] is None and not t['restore_submitted'] and t['credit']==50000
  observe(s,2*H4+2,btc=reclaim,equity='6400');run_ticks(e,[tick(BTC_PERP,2*H4+2,reclaim)])
  assert not t['restore_submitted'] and t['restore_filled']==0
 finally:e.end();e.dispose()

@pytest.mark.parametrize('side',[1,-1])
def test_r_revoked_hold_release_stays35(side):
 s,e,ep=held(side=side,restore_dd=D('.40'))
 try:
  cut(s,e,price='55' if side==1 else '145');t=s._c1_state
  s._c1_revoke(2000,'TEST_REVOKE')
  observe(s,2001,btc='80' if side==1 else '120',equity='6400')
  assert t['state']=='REVOKED' and t['credit']==0
  observe(s,2002,btc='80' if side==1 else '120',equity='6500')
  assert t['state']=='RELEASED'
 finally:e.end();e.dispose()

@pytest.mark.parametrize('side',[1,-1])
def test_r_native_margin_denial_keeps_actual_credit_and_needs_new_bar(side):
 class Admission(NativeProbe):
  allow=True
  def _tier_allows_increase(self,*a):return self.allow
 s,e,ep=held(side=side,cls=Admission,restore_dd=D('.40'))
 try:
  cut(s,e,price='55' if side==1 else '145');t=s._c1_state
  reclaim=confirm(s,side);assert t['confirmation']
  s.allow=False
  for n in range(1,6):
   observe(s,2*H4+n,btc=reclaim,equity='6400');run_ticks(e,[tick(BTC_PERP,2*H4+n,reclaim)])
  assert t['state']=='HELD' and not t['restore_submitted'] and t['credit']==50000 and t['confirmation'] is None
  s.allow=True;observe(s,2*H4+100,btc=reclaim,equity='6400');run_ticks(e,[tick(BTC_PERP,2*H4+100,reclaim)])
  assert not t['restore_submitted'] and t['credit']==50000
 finally:e.end();e.dispose()
