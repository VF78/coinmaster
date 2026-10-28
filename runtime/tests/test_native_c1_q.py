"""Q cut intensity only: native executions, both sides, rights and actual credit."""
from copy import deepcopy
from decimal import Decimal as D
import pytest
from test_native_residual_recovery import held,cut,observe
from test_native_episode_risk import run_ticks,tick
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.next_band import next_closed_bar,H4

@pytest.mark.parametrize("side",[1,-1])
@pytest.mark.parametrize("size,expected",[("1000",25000),("3",3000),("0",0)])
def test_q_native_btc_quarter_single_attempt_actual_credit_rights(side,size,expected):
 s,e,ep=held(side=side,cut_divisor=4)
 try:
  original=(deepcopy(ep.btc_tp_target_lots),ep.btc_planref_vwap,ep.h,deepcopy(ep.sol_add_filled_notional))
  price='55' if side==1 else '145'
  cut(s,e,price=price,size=size);t=s._c1_state
  assert (t['held_lots'],t['cut_lots'],t['target_lots'])==(100000,25000,75000)
  assert t['cut_filled']==t['credit']==expected
  assert ep.btc_open_qty==100-expected/1000
  assert sum(ep.btc_risk_retired_lots.values())==expected
  assert original==(ep.btc_tp_target_lots,ep.btc_planref_vwap,ep.h,ep.sol_add_filled_notional)
  assert not ep.sol_rights
  assert len([r for r in s.c1_audit if r['event']=='ATTEMPT_SUBMIT' and r['kind']=='CUT'])==1
  # Following quotes do not complete an unfilled/partial frozen cut.
  for ns in range(2000,2004):
   observe(s,ns,btc=price);run_ticks(e,[tick(BTC_PERP,ns,price)])
  assert t['cut_filled']==expected
  if expected:
   reclaim='80' if side==1 else '120';observe(s,2*H4,btc=reclaim)
   s._c1_closed_bar(next_closed_bar(BTC_PERP.id,4,D(reclaim),D(reclaim),D(reclaim),D(reclaim),2*H4).data)
   for n in range(1,6):
    observe(s,2*H4+n,btc=reclaim);run_ticks(e,[tick(BTC_PERP,2*H4+n,reclaim)])
   assert t['restore_filled']==expected and t['credit']==0 and ep.btc_open_qty==100
 finally:e.end();e.dispose()

@pytest.mark.parametrize("side",[1,-1])
def test_q_sol_cut_stays_half(side):
 s,e,ep=held(asset='SOL',side=side,cut_divisor=4)
 try:
  # Set BTC mark at entry, SOL adverse, so selected loss belongs to SOL.
  cut(s,e,asset='SOL',price='145' if side==1 else '55');t=s._c1_state
  assert t['instrument']==SOL_PERP.id
  assert (t['held_lots'],t['cut_lots'],t['target_lots'])==(1000,500,500)
  assert t['cut_filled']==t['credit']==500
 finally:e.end();e.dispose()

@pytest.mark.parametrize("side",[1,-1])
def test_c1_native_coherent_observer_noninterference(tmp_path,monkeypatch,side):
 import json
 from types import SimpleNamespace
 import test_native_residual_recovery as fixture
 from nautilus_trader.backtest.config import BacktestEngineConfig
 from nautilus_trader.backtest.engine import BacktestEngine
 from nautilus_trader.config import LoggingConfig
 from nautilus_trader.model.enums import AccountType,OmsType
 from nautilus_trader.model.objects import Money
 from coinmaster.research.native_fixture import SIM
 from coinmaster.research.paired_observer import CommittedNativeObserver
 traces=[]
 for enabled in (False,True):
  import itertools,uuid
  import coinmaster.domain.wave_overlay as domain
  ids=itertools.count(1)
  monkeypatch.setattr(domain,"uuid4",lambda:uuid.UUID(int=next(ids)))
  observer=CommittedNativeObserver(tmp_path/(str(enabled)+'.gz'),D(10000),(BTC_PERP,SOL_PERP)) if enabled else None
  if observer:observer.set_week([SimpleNamespace(open_time_ms=-60000,btc_mark={'close':'100'},sol_mark={'close':'100'})])
  def build(strategy):
   e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
   e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,default_leverage=D(1),modules=[observer] if observer else [])
   e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(strategy);return e
  monkeypatch.setattr(fixture,'native_engine',build)
  s,e,ep=fixture.held(side=side,cut_divisor=4)
  try:
   fixture.cut(s,e,price='55' if side==1 else '145',size='3')
   s._begin_forced_close('TEST_TERMINAL')
   for ns in range(3000,3010):run_ticks(e,[tick(BTC_PERP,ns),tick(SOL_PERP,ns)])
   e.end()
   proof=observer.finish_after_engine_end(3010) if observer else None
   traces.append(dict(fills=s.fill_audit,c1=s.c1_audit,cash=str(e.cache.account_for_venue(SIM).balance_total().as_decimal()),orders=[(str(o.client_order_id),str(o.status),str(o.quantity),str(o.filled_qty)) for o in e.cache.orders()]))
   if observer:
    assert proof['status']=='PASS',proof
    assert proof['native_unique_fills']==len(s.fill_audit)
    assert proof['terminal_actual_cash']==traces[-1]['cash']
    (tmp_path/('c1-parity-'+str(side)+'.json')).write_text(json.dumps(proof,indent=2))
  finally:
   if observer:observer.close()
   e.dispose()
 assert traces[0]==traces[1]
