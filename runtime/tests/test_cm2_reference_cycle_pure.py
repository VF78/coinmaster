"""Causal BTC cycle/C1 supplied-event fixtures only, no native construction."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
import json
import pytest
from coinmaster.domain.wave_overlay import DailyBar
from coinmaster.strategy.cm2_checkpoint import canonical,decode
from coinmaster.strategy.cm2_reference_policy import (ReferenceBtcPolicy,ReferenceFlags,
    ReferenceConfig,selected_btc_candidate,BtcParent,DAY,HOUR)

UTC=timezone.utc
START=datetime(2023,1,1,tzinfo=UTC)
T0=int(START.timestamp()*1e9)


def row(day,close=100):
    t=START+timedelta(days=day)
    return DailyBar(t,t+timedelta(days=1),t+timedelta(days=1),close,close,30)


def policy():
    return ReferenceBtcPolicy(selected_btc_candidate(),flags=ReferenceFlags(True,True),
        btc_step=D('.01'),trading_start_ns=T0,terminal_ns=T0+2000*DAY,
        max_quote_age_ns=120_000_000_000,initial_btc_equity=D(10000))


def entered(*,side=1,partial=False):
    p=policy();p.accept_closed_day(row(0),receipt_ns=T0+DAY,btc_high=101,btc_low=99)
    p._parent=BtcParent('p',side,0,1.25,(.01,.02,.03),10000)
    p.observe_entry_q0('p',quote_ns=T0+DAY+1,executable_price=D(100),canonical_wire_price=D(100))
    p.select_entry_q1('p',quote_ns=T0+DAY+60_000_000_001,bid=D(100),ask=D(100))
    p.begin_split('p',now_ns=T0+DAY+60_000_000_001)
    p.apply_fill('p',trade_id='entry',kind='ENTRY',quantity=D(50 if partial else 100),price=D(100),event_ns=T0+DAY+60_000_000_002)
    if partial:p.stop_entry_remainder('p',reason='PAUSE')
    return p


def observe(p,source,*,equity=6000,pnl=-2000,qty=100,revision=None):
    p.observe_committed_btc(source_ns=source,receipt_ns=source+1,
        revision=p.btc_revision if revision is None else revision,
        equity=D(equity),open_pnl=D(pnl),native_qty=D(qty),position_id='native-btc',
        position_open_ns=T0+DAY,btc_competing_owner=False)


def cut(p):
    source=T0+DAY+120_000_000_000;observe(p,source)
    assert p.c1.cut_lots==2500
    assert p.c1_plan(now_ns=source+1,executable_price=D(80),native_held_quantity=D(100),native_btc_owners_clear=True) is None
    plan=p.c1_plan(now_ns=source+2,executable_price=D(80),native_held_quantity=D(100),native_btc_owners_clear=True)
    assert (plan.kind,plan.quantity,plan.side)==('CUT',D(25),-1)
    p.commit_c1_submission('CUT',now_ns=source+2)
    p.apply_fill('p',trade_id='cut',kind='CUT',quantity=D(25),price=D(80),event_ns=source+2)
    p.c1_terminal('CUT',now_ns=source+2)
    return source+2


def test_frozen_config_rejects_old_version_silent_candidate_or_flags():
    cfg=ReferenceConfig('cm2-btc-reference-v1',selected_btc_candidate(),ReferenceFlags(True,True))
    assert cfg.emergency_drawdown_fraction is None
    for version,candidate,flags in [('cm2-v2',cfg.candidate,cfg.flags),
            (cfg.version,replace(cfg.candidate,ema_period=21),cfg.flags),
            (cfg.version,cfg.candidate,ReferenceFlags(False,True))]:
        with pytest.raises(ValueError):ReferenceConfig(version,candidate,flags)


def test_c1_cut_is_actual_quarter_credit_and_retires_fixed_tp_rights():
    p=entered();cut(p)
    assert p.c1.credit==2500 and p.c1.state=='HELD'
    assert p.parent.risk_retired_lots=={0:532,1:531,2:1437}
    assert [x.quantity for x in p.confirmed_targets('p')]==[D('15.93'),D('15.94'),D('43.13')]
    assert p.c1_plan(now_ns=T0+DAY+121_000_000_000,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=True) is None


def test_stopped_partial_split_is_terminal_for_c1_but_not_positive_ioc():
    p=entered(partial=True)
    assert p.parent.split_terminal and p.parent.filled_quantity==50
    observe(p,T0+DAY+120_000_000_000,qty=50)
    assert p.c1 is not None and p.c1.cut_lots==1250
    assert not any(x.positive_ioc_candidate for x in p.confirmed_targets('p'))


def test_pending_or_invalid_receipt_never_creates_c1_claim_or_cut_credit():
    p=entered();source=T0+DAY+120_000_000_000
    p.observe_committed_btc(source_ns=source,receipt_ns=source,revision=p.btc_revision,
        equity=D(6000),open_pnl=D(-2000),native_qty=D(100),position_id='btc',position_open_ns=T0,btc_competing_owner=False)
    assert p.c1 is None
    observe(p,source,revision=p.btc_revision+1);assert p.c1 is None
    observe(p,source);assert p.c1.credit==0
    assert p.c1_plan(now_ns=source+2,executable_price=D(80),native_held_quantity=D(100),native_btc_owners_clear=False).kind=='CANCEL'
    assert p.c1.credit==0 and not p.c1.cut_submitted


def test_actual_ordinary_btc_fill_revokes_cut_credit_and_sols_have_no_input():
    p=entered();cut(p)
    p.apply_fill('p',trade_id='ordinary-tp',kind='TP',quantity=D(1),price=D(101),event_ns=T0+DAY+130_000_000_000,level=0)
    assert p.c1.revoked and p.c1.credit==0
    observe(p,T0+DAY+180_000_000_000,equity=6400,qty=74)
    assert p.c1.state=='REVOKED'
    observe(p,T0+DAY+240_000_000_000,equity=6500,qty=74)
    assert p.c1.state=='RELEASED'


def test_postcut_h4_firstfresh_and_full_postcut_d1_are_distinct_restore_gates():
    p=entered();cut(p)
    h4_open=T0+DAY+4*HOUR;h4_close=h4_open+4*HOUR
    p.accept_closed_btc_h4(open_ns=h4_open,close_ns=h4_close,available_ns=h4_close,
        receipt_ns=h4_close,close=D(90))
    assert p.c1.deferred_h4 is not None and p.c1.confirmation is None
    observe(p,h4_close,equity=6500,pnl=-1000,qty=75)
    # Later quote consumes first-fresh candidate. D1 opened before actual cut;
    # confirmation alone cannot restore until a FULL postcut D1 exists.
    assert p.c1_plan(now_ns=h4_close+2,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=True) is None
    assert p.c1.deferred_h4 is None and p.c1.confirmation is not None
    p.accept_closed_day(row(1,101),receipt_ns=T0+2*DAY,btc_high=102,btc_low=100)
    observe(p,T0+2*DAY,equity=6500,pnl=-1000,qty=75)
    assert p.c1_plan(now_ns=T0+2*DAY+2,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=True) is None
    p.accept_closed_day(row(2,102),receipt_ns=T0+3*DAY,btc_high=103,btc_low=101)
    observe(p,T0+3*DAY,equity=6500,pnl=-1000,qty=75)
    # source equals D1 close, receipt is later. No extra minute embargo.
    plan=p.c1_plan(now_ns=T0+3*DAY+2,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=True)
    assert (plan.kind,plan.quantity)==('RESTORE',D(25))
    p.commit_c1_submission('RESTORE',now_ns=T0+3*DAY+2)
    p.apply_fill('p',trade_id='restore',kind='RESTORE',quantity=D(25),price=D(90),event_ns=T0+3*DAY+2)
    p.c1_terminal('RESTORE',now_ns=T0+3*DAY+2)
    assert p.c1.credit==0 and p.c1.state=='RELEASED'
    assert p.parent.risk_retired_lots=={0:0,1:0,2:0}
    assert sum(x.quantity for x in p.confirmed_targets('p'))==100


def test_firstfresh_denial_consumes_candidate_without_later_reuse():
    p=entered();cut(p);end=T0+DAY+8*HOUR
    p.accept_closed_btc_h4(open_ns=end-4*HOUR,close_ns=end,available_ns=end,receipt_ns=end,close=D(90))
    observe(p,end,equity=5900,qty=75)
    p.c1_plan(now_ns=end+2,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=True)
    assert p.c1.deferred_h4 is None and p.c1.confirmation is None
    observe(p,end+60_000_000_000,equity=6500,qty=75)
    p.c1_plan(now_ns=end+60_000_000_002,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=True)
    assert p.c1.confirmation is None


def test_pure_state_json_roundtrip_keeps_partial_credit_and_dedup_identity():
    p=entered();cut(p)
    before=p.snapshot_state();body=canonical(before)
    restored=policy();restored.restore_state(decode(json.loads(body)))
    assert canonical(restored.snapshot_state())==body
    assert not restored.apply_fill('p',trade_id='cut',kind='CUT',quantity=D(25),price=D(80),event_ns=T0+DAY+120_000_000_002)
    assert restored.c1.credit==2500


def test_tp_flat_cannot_reset_without_explicit_btc_market_close_permission():
    p=entered()
    for i,q in enumerate(('21.25','21.25','57.50')):
        p.apply_fill('p',trade_id='tp'+str(i),kind='TP',quantity=D(q),price=D(103),event_ns=T0+DAY+120_000_000_000,level=i)
    with pytest.raises(ValueError):p.confirm_btc_close('p',receipt_ns=T0+DAY+120_000_000_001,native_btc_flat=True,native_btc_owners_terminal=True)
    assert p.parent is not None


def test_btc_close_does_not_take_sol_inputs_and_trail_waits_next_d1():
    p=entered();p._parent.close_reason='TRAIL'
    p.confirm_btc_close('p',receipt_ns=T0+DAY+120_000_000_000,native_btc_flat=True,native_btc_owners_terminal=True)
    assert p.parent is None
    # Warmup takes precedence here; pure lifecycle still records exact block.
    assert p._trail_block_index==0
    assert 'sol' not in str(__import__('inspect').signature(p.confirm_btc_close)).lower()


def test_regime_wait_requires_genuine_ohlc_then_fresh_h4_permission():
    p=policy()
    for i in range(35):p.accept_closed_day(row(i),receipt_ns=T0+(i+1)*DAY,btc_high=101,btc_low=99)
    p._wait_regime=True;p._regime_latch_ns=T0+35*DAY
    assert not p.reentry_allowed()  # D1 distance from first-seeded EMA is zero.
    p.accept_closed_btc_h4(open_ns=T0+35*DAY,close_ns=T0+35*DAY+4*HOUR,
        available_ns=T0+35*DAY+4*HOUR,receipt_ns=T0+35*DAY+4*HOUR,close=D(100+2*p.signals[-1].side))
    assert p.reentry_allowed()  # Observed exact-float EMA side, one ATR favorable H4.


def test_firstfresh_h4_denial_is_consumed_before_harmless_tp_cancel_ack():
    p=entered();cut(p);end=T0+DAY+8*HOUR
    p.accept_closed_btc_h4(open_ns=end-4*HOUR,close_ns=end,available_ns=end,receipt_ns=end,close=D(90))
    observe(p,end,equity=5900,qty=75)
    p.c1_plan(now_ns=end+2,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=False)
    assert p.c1.deferred_h4 is None and p.c1.confirmation is None
    observe(p,end+60_000_000_000,equity=6500,qty=75)
    p.c1_plan(now_ns=end+60_000_000_002,executable_price=D(90),native_held_quantity=D(75),native_btc_owners_clear=True)
    assert p.c1.confirmation is None


def test_global_h4_watermark_survives_json_and_cannot_relabel_old_reentry_release():
    p=policy()
    for i in range(35):p.accept_closed_day(row(i),receipt_ns=T0+(i+1)*DAY,btc_high=101,btc_low=99)
    p._wait_regime=True;p._regime_latch_ns=T0+35*DAY
    end=T0+35*DAY+4*HOUR;price=D(100+2*p.signals[-1].side)
    p.accept_closed_btc_h4(open_ns=end-4*HOUR,close_ns=end,available_ns=end,receipt_ns=end,close=price)
    assert p.reentry_allowed()
    p.accept_closed_day(row(35),receipt_ns=T0+36*DAY,btc_high=101,btc_low=99)
    assert not p.reentry_allowed()
    restored=policy();restored.restore_state(decode(json.loads(canonical(p.snapshot_state()))))
    restored.accept_closed_btc_h4(open_ns=end-4*HOUR,close_ns=end,available_ns=end,receipt_ns=T0+36*DAY,close=price)
    assert not restored.reentry_allowed()
    assert restored._last_h4_ns==end
