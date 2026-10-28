"""G protocol fixtures execute actual C1 methods; zero native object constructors."""
import ast
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import pytest

ROOT=Path(__file__).parents[1]/'coinmaster'
TREE=ast.parse((ROOT/'strategy/residual_recovery.py').read_text())
CLASS=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='ResidualRecoveryResearch')
ENV={'D':D,'H4':14_400_000_000_000,'CUT':'C1_RESIDUAL_CUT','RESTORE':'C1_RESIDUAL_RESTORE'}
exec(compile(ast.Module(body=[CLASS],type_ignores=[]),'actual_residual_recovery_methods','exec'),ENV)

class ID(str):venue='TEST'
class Owner(ENV['ResidualRecoveryResearch']):
 def __init__(self,enabled=True,held=10,episode=True):
  self.config=N(research_c1_btc_cut_divisor=2,research_c1_restore_dd=D('.35'),research_c1_global_cut_arm=enabled,
   active_seed=D(10000),research_residual_recovery=True,research_wait_4h=True,research_regime_reentry_band=D('.5'),
   research_zero_retrace=False,research_sol_dominant=False,research_wait_persist=False,max_mark_age_ns=50,btc_id=ID('BTC'),sol_id=ID('SOL'))
  self.account=N(last_event=N(ts_event=0));self.inflight=[];self.open_orders=[];self.own_positions=[]
  self.position=N(quantity=N(as_decimal=lambda:D(held)),is_long=True,id='native-owned',ts_opened=1,
   unrealized_pnl=lambda price:N(as_decimal=lambda:D(-3000)))
  self.cache=N(account_for_venue=lambda venue:self.account,orders_inflight=lambda:self.inflight,
   orders_open=lambda:self.open_orders,positions_open=lambda:self.own_positions,
   instrument=lambda inst:N(size_increment=N(as_decimal=lambda:D(1)),make_price=lambda mark:mark))
  ep=N(id='group-1') if episode else None
  self._domain=N(episode=ep,_ensure_btc_targets=lambda ep:None)
  self._split_parent=dict(episode_id='group-1',closed=True)
  self._pending_by_order={};self._queued_intents=[]
  self._c1_init()
 def _split_unfinished(self):return False
 def _c1_conflict(self):return False
 def _hb_position(self,inst):return self.position if inst==self.config.btc_id else None
 def _c1_rights(self):return {}
 def observe(self,equity='6000',source=100,receipt=101,epoch=None,account_ns=None):
  self.account.last_event.ts_event=source if account_ns is None else account_ns
  details=[dict(instrument_id='BTC',mark_ohlc=dict(close='100'))] if self._domain.episode else []
  self._c1_observe(D(equity),receipt,source,self._c1_fill_epoch if epoch is None else epoch,details)


def test_positive_economic_claim_consumes_before_submit_and_keeps_c1_frozen_half_target():
 s=Owner();s.observe();t=s._c1_state
 assert t['state']=='CUT_RESOLVING' and t['cut_lots']==5 and t['target_lots']==5
 assert not t['cut_submitted'] and not s._c1_global_cut_armed
 with pytest.raises(ValueError,match='G_CUT_ARM_COMMIT_INVALID'):s._c1_consume_global_cut_arm(1)
 observe=next(n for n in CLASS.body if isinstance(n,ast.FunctionDef) and n.name=='_c1_observe')
 text=ast.unparse(observe)
 assert text.index('self._c1_consume_global_cut_arm(cut_lots)')<text.index("self._c1_state = dict(group=ep.id")


def test_zero_lot_proposal_does_not_claim_or_consume_arm():
 s=Owner(held=1);s.observe()
 assert s._c1_state is None and s._c1_global_cut_armed
 assert not any(r['event']=='CLAIM' for r in s.c1_audit)

@pytest.mark.parametrize('filled',[0,2,5])
def test_zero_partial_full_terminal_revoke_group_month_do_not_rearm(filled):
 s=Owner();s.observe();t=s._c1_state;t['cut_filled']=filled;t['credit']=filled
 s._c1_intents['cut']='CUT';s._c1_terminal(N(id='cut',episode_id='group-1'),102)
 assert not s._c1_global_cut_armed
 s._c1_revoke(103,'ORDINARY_EXIT');assert not s._c1_global_cut_armed
 s._domain.episode=None;s.observe(source=200,receipt=201)
 assert s._c1_state is None and not s._c1_global_cut_armed
 # Arbitrary later month cannot reset an account-wide latch while DD stays40.
 s.observe(source=1_900_000_000_000_000_000,receipt=1_900_000_000_000_000_001)
 assert not s._c1_global_cut_armed


def test_restore_terminal_cannot_rearm_and_original_parent_once_rule_survives_rearm():
 s=Owner();s.observe();t=s._c1_state;t['credit']=2
 s._c1_intents['restore']='RESTORE';s._c1_terminal(N(id='restore',episode_id='group-1'),102)
 assert t['state']=='RELEASED' and not s._c1_global_cut_armed
 s.observe(equity='6500',source=200,receipt=201)
 assert s._c1_global_cut_armed
 s.observe(source=202,receipt=203)
 assert sum(r['event']=='CLAIM' for r in s.c1_audit)==1 # Same parent remains spent.

@pytest.mark.parametrize('fault',['stale','mixed_epoch','account_after_source'])
def test_stale_or_mixed_money_cannot_rearm(fault):
 s=Owner(episode=False);s._c1_consume_global_cut_arm(5)
 if fault=='stale':s.observe(equity='7000',source=100,receipt=200)
 elif fault=='mixed_epoch':
  s._c1_fill_epoch=1;s.observe(equity='7000',source=100,receipt=101,epoch=0)
 else:s.observe(equity='7000',source=100,receipt=101,account_ns=101)
 assert not s._c1_global_cut_armed
 s.observe(equity='6500',source=300,receipt=301)
 assert s._c1_global_cut_armed and s._c1_peak==D(10000)

@pytest.mark.parametrize('pending',['own','inflight'])
def test_dd35_with_unresolved_blocks_then_ack_requires_new_actual_source(pending):
 s=Owner(episode=False);s._c1_consume_global_cut_arm(5)
 if pending=='own':s._c1_intents['cut']='CUT';s._pending_by_order['oid']=N(id='cut')
 else:s.inflight.append(N())
 s.observe(equity='6500',source=100,receipt=101)
 assert not s._c1_global_cut_armed and s._c1_global_rearm_blocked_source==100
 s._pending_by_order.clear();s.inflight.clear()
 s._c1_update_global_cut_arm(102) # ACK alone cannot reuse old recovery receipt.
 assert not s._c1_global_cut_armed
 s.observe(equity='6500',source=102,receipt=103)
 assert s._c1_global_cut_armed


def test_healthy_accepted_standing_limit_is_not_unresolved_c1_or_inflight():
 s=Owner(episode=False);s._c1_consume_global_cut_arm(5)
 s.open_orders=[N(status='ACCEPTED')];s._pending_by_order['tp']=N(id='ordinary-tp')
 s.observe(equity='6500',source=100,receipt=101)
 assert s._c1_global_cut_armed


def test_default_off_has_no_new_gate_or_changed_half_claim_and_no_arm_effect():
 s=Owner(enabled=False);s.observe();t=s._c1_state
 assert t['cut_lots']==5 and t['target_lots']==5 and s._c1_global_cut_armed
 proposed=next(r for r in s.c1_audit if r['event']=='PROPOSED_DECISION')
 assert 'global_cut_armed' not in proposed['gates']
 s._c1_global_cut_armed=False;s.observe(equity='6500',source=200,receipt=201)
 assert not s._c1_global_cut_armed # Disabled G does not affect even injected arm state.


def test_g_standalone_cli_and_default_off_metadata_wiring():
 tree=ast.parse((ROOT/'research/native_baseline.py').read_text())
 functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
 runner=functions['run_native_diagnostic'];cli=functions['run_research_v0_repairs_cli'];main=functions['main']
 args=runner.args.args;values=[None]*(len(args)-len(runner.args.defaults))+runner.args.defaults
 assert next(ast.literal_eval(v) for a,v in zip(args,values) if a.arg=='research_c1_global_cut_arm') is False
 assert ast.literal_eval(dict(zip((a.arg for a in cli.args.kwonlyargs),cli.args.kw_defaults))['research_c1_global_cut_arm']) is False
 assert 'G_STANDALONE_REQUIRES_C1_HALF_RESTORE35' in ast.unparse(runner)
 assert 'research_c1_global_cut_arm=args.research_c1_global_cut_arm' in ast.unparse(main)
 assert 'research_c1_global_cut_arm=research_c1_global_cut_arm' in ast.unparse(cli)
 assert 'unresolved_c1_pending_or_native_inflight_blocks=True' in ast.unparse(runner)

@pytest.mark.parametrize('enabled',[False,True])
def test_next_parent_cut_is_blocked_only_by_enabled_unrearmed_account_arm(enabled):
 s=Owner(enabled=enabled);s.observe()
 s._domain.episode=None;s.observe(source=200,receipt=201) # Actual old-group flat/reset path.
 s._domain.episode=N(id='group-2');s._split_parent=dict(episode_id='group-2',closed=True)
 s.observe(source=202,receipt=203)
 assert (s._c1_state is None)==enabled
 assert sum(r['event']=='CLAIM' for r in s.c1_audit)==(1 if enabled else 2)
 if enabled:
  assert any(not row['gates']['global_cut_armed'] for row in s.c1_denials.values())
