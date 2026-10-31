"""Native-constructor-free regressions for current CM2 child rights."""
from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace as NS
import unittest
from coinmaster.strategy.cm2_policy import (
    Config,State,HOUR_NS,decide,btc_child_permission,reconcile_btc_intent,positive_harvest)
from runtime.tests.test_cm2_policy import feat,snap,state

class ChildAdmissionTests(unittest.TestCase):
    def test_unknown_confirmed_trim_never_restores_at_loss_both_sides(self):
        for d in (1,-1):
            s=snap(btc_qty=D(d*40))
            st=state(direction=d,btc_target=s.btc_qty,unhedged_btc_target=s.btc_qty,
                     stop=800 if d>0 else 1200,extreme=1000)
            a=decide(Config(),feat(hedge_valid=False),s,st)
            self.assertEqual(a.btc_target,D(d*20))
            for i in (1,2):
                f=feat(t=(200+i)*HOUR_NS,close=980 if d>0 else 1020,channel_high=1030,channel_low=970)
                s=replace(s,btc_qty=D(d*20),btc_mark=D(str(f.close)))
                a=decide(Config(),f,s,a.state)
            self.assertEqual(a.btc_target,s.btc_qty)
            self.assertEqual(a.state.unhedged_btc_target,s.btc_qty)
    def test_adverse_same_hour_add_revoked_and_late_fill_reduced(self):
        for d in (1,-1):
            f=feat(close=1020 if d>0 else 980)
            s=snap(btc_qty=D(d*20),btc_mark=D(980 if d>0 else 1020))
            st=state(direction=d,btc_target=D(d*40),unhedged_btc_target=D(d*40),
                     btc_intent="FAVORABLE_ADD",intent_hour=f.closed_ns,last_hour=f.closed_ns)
            a=decide(Config(),f,s,st)
            self.assertEqual(a.btc_target,s.btc_qty)
            self.assertTrue(a.cancel_increases)
            late=replace(s,btc_qty=D(d*25))
            b=decide(Config(),f,late,a.state)
            self.assertEqual(b.btc_target,D(d*20))
            self.assertEqual(b.state.btc_intent,"RISK_TRIM")
    def test_untagged_target_is_no_permission_to_grow(self):
        a=decide(Config(),feat(),snap(),state(last_hour=200*HOUR_NS,btc_target=D(40)))
        self.assertEqual(a.btc_target,D(1))
        self.assertTrue(a.cancel_increases)
    def test_favorable_remaining_child_permitted_current_quote_only(self):
        for d in (1,-1):
            f=feat(close=1020 if d>0 else 980)
            st=state(direction=d,btc_target=D(d*40),btc_intent="FAVORABLE_ADD",intent_hour=f.closed_ns)
            s=snap(btc_qty=D(d*20))
            self.assertTrue(btc_child_permission(Config(),f,s,st,now_ns=f.closed_ns+1,
                executable_price=D(1001 if d>0 else 999))[0])
            self.assertFalse(btc_child_permission(Config(),f,s,st,now_ns=f.closed_ns+1,
                executable_price=D(999 if d>0 else 1001))[0])
            self.assertFalse(btc_child_permission(Config(),f,replace(s,btc_vwap=None),st,
                now_ns=f.closed_ns+1,executable_price=D(1100))[0])
    def test_authentic_initial_entry_residual_equality_never_adverse(self):
        for d in (1,-1):
            f=feat(close=1020 if d>0 else 980)
            s=snap(btc_qty=D(d*20))
            st=state(direction=d,btc_target=D(d*40),btc_intent="INITIAL_ENTRY",intent_hour=f.closed_ns)
            self.assertTrue(btc_child_permission(Config(),f,s,st,now_ns=f.closed_ns+1,executable_price=D(1000))[0])
            self.assertFalse(btc_child_permission(Config(),f,s,st,now_ns=f.closed_ns+1,
                executable_price=D(990 if d>0 else 1010))[0])
            self.assertFalse(btc_child_permission(Config(),f,s,replace(st,btc_intent="FAVORABLE_ADD"),
                now_ns=f.closed_ns+1,executable_price=D(1000))[0])
    def test_entry_residual_expires_instead_of_restoring_next_hour(self):
        f=feat(close=1020)
        a=decide(Config(),f,snap(btc_qty=D(0)),State())
        s=snap(btc_qty=D(2),btc_mark=D(1001))
        next_f=feat(t=201*HOUR_NS,close=1000,channel_high=1025)
        b=decide(Config(),next_f,s,a.state)
        self.assertEqual(b.btc_target,D(2))
    def test_same_timestamp_stale_missing_feature_block_ordinaries(self):
        f=feat(close=1020)
        for intent in ("FAVORABLE_ADD","POSITIVE_HARVEST"):
            st=state(btc_target=D(2),btc_intent=intent,intent_hour=f.closed_ns)
            for now in (f.available_ns,f.closed_ns+HOUR_NS+1):
                self.assertFalse(btc_child_permission(Config(),f,snap(btc_mark=D(1200)),st,
                    now_ns=now,executable_price=D(1200))[0])
        a=decide(Config(),f,snap(),state(),now_ns=f.closed_ns+HOUR_NS+1)
        self.assertEqual(a.btc_target,D('.5'))
        self.assertTrue(a.cancel_increases)
    def test_harvest_rechecks_executable_and_does_not_consume_unfilled_right(self):
        f=feat(close=1070)
        s=snap(btc_qty=D(40),btc_mark=D(1070))
        a=decide(Config(),f,s,state(btc_target=D(40),unhedged_btc_target=D(40),initial_r=30))
        self.assertEqual(a.btc_target,D(30))
        self.assertFalse(a.state.harvested)
        self.assertEqual(a.state.harvest_target,D(30))
        later=replace(s,btc_mark=D(990))
        self.assertFalse(positive_harvest(later))
        b=decide(Config(),f,later,a.state)
        self.assertEqual(b.btc_target,D(40))
        self.assertTrue(b.cancel_increases)
        self.assertFalse(b.state.harvested)
        self.assertIsNone(b.state.harvest_target)
        checked,allowed,_=reconcile_btc_intent(Config(),f,s,a.state,
            now_ns=f.closed_ns+1,executable_price=D(990))
        self.assertFalse(allowed)
        self.assertEqual(checked.btc_target,D(40))
    def test_harvest_partial_consumes_once_complete_uses_native_inventory(self):
        f=feat(close=1250)
        s=snap(btc_mark=D(1250))
        a=decide(Config(),f,s,state())
        partial=replace(s,btc_qty=D('.9'),btc_mark=D(990),btc_pending=D('-.1'))
        b=decide(Config(),f,partial,a.state)
        self.assertTrue(b.state.harvested)
        self.assertEqual(b.btc_target,D('.9'))
        done=replace(s,btc_qty=D('.75'))
        c=decide(Config(),f,done,a.state)
        self.assertTrue(c.state.harvested)
        self.assertIsNone(c.state.harvest_target)
        self.assertEqual(c.btc_target,D('.75'))
    def test_unknown_after_partial_harvest_consumes_once(self):
        f=feat(close=1250)
        a=decide(Config(),f,snap(btc_mark=D(1250)),state())
        b=decide(Config(),replace(f,hedge_valid=False),snap(btc_qty=D('.9')),a.state)
        self.assertTrue(b.state.harvested)
    def test_harvest_cannot_add_and_safety_stop_remains_immediate(self):
        f=feat(close=1250)
        a=decide(Config(),f,snap(btc_mark=D(1250)),state())
        f2=feat(t=201*HOUR_NS,close=900)
        b=decide(Config(),f2,snap(btc_mark=D(900)),a.state)
        self.assertTrue(b.state.draining)
        self.assertEqual(b.btc_target,D(0))
    def test_btc_trim_release_never_restores_confirmed_reduction(self):
        cfg=Config(mode="btc_trim")
        f=feat(residual_z=-2,btc_return6=-.02)
        s=snap()
        a=decide(cfg,f,s,state(activate_count=1))
        held=a.btc_target
        for i in (1,2,3):
            f2=feat(t=(200+i)*HOUR_NS,close=990,residual_z=0,btc_return6=.01)
            a=decide(cfg,f2,replace(s,btc_qty=held,btc_mark=D(990)),a.state)
        self.assertEqual(a.btc_target,held)
    def test_unsafe_pending_canceled_on_other_symbol_callback_without_engine(self):
        from coinmaster.strategy.cm2_native import CM2Strategy
        f=feat(close=1020)
        s=snap(btc_mark=D(980),btc_pending=D(1))
        st=state(btc_target=D(2),unhedged_btc_target=D(2),btc_intent="FAVORABLE_ADD",
                 intent_hour=f.closed_ns,last_hour=f.closed_ns)
        class Price:
            def as_decimal(self): return D(980)
        order=NS(client_order_id="owned")
        canceled=[]
        class Increment:
            def as_decimal(self): return D('.01')
            def __str__(self): return '.01'
        instrument=NS(size_increment=Increment(),min_quantity=Increment(),min_notional=None)
        fake=NS(config=NS(btc_id="BTC",sol_id="SOL",policy=Config(),trading_start_open_ns=0,
                          terminal_close_at_ns=10**25,limits=NS(child_interval_ns=60_000_000_000),execution_policy_hash="fixture",checkpoint_store=None),
            _quotes={},current_features=f,policy_state=st,_liquidating=False,_restore_failed=False,_snapshot=lambda now:s,
            cache=NS(instrument=lambda iid:instrument),_orders=lambda iid:[order] if iid=="BTC" else [],
            _order_audit={"owned":{"admission":{"intent":"FAVORABLE_ADD"}}},
            cancel_order=lambda o:canceled.append(o),child_permission_audit=[],_admission_sources={},
            orphan_started_ns=None,orphan_intervals=[],_child_capacity=lambda iid,now:D(1000),target_blockers={})
        fake._permission_context=lambda *args:CM2Strategy._permission_context(fake,*args)
        fake._persist_checkpoint=lambda:None
        tick=NS(instrument_id="SOL",ts_event=f.closed_ns+1,bid_price=Price(),ask_price=Price())
        CM2Strategy.on_quote_tick(fake,tick)
        self.assertEqual(canceled,[order])
        self.assertEqual(fake.policy_state.btc_target,D(1))
        # Equality cancels OLD rights but cannot consume the new completed hour.
        fake.policy_state=st
        fake._owned={"owned":{}}
        next_f=feat(t=201*HOUR_NS,close=1020)
        fake.current_features=next_f
        canceled.clear()
        CM2Strategy.on_quote_tick(fake,NS(instrument_id="SOL",ts_event=next_f.available_ns,
            bid_price=Price(),ask_price=Price()))
        self.assertEqual(canceled,[order])
        self.assertEqual(fake.policy_state.last_hour,f.closed_ns)
        fresh=decide(Config(),next_f,replace(s,btc_mark=D(1020),btc_pending=D(0)),
            fake.policy_state,now_ns=next_f.available_ns+1)
        self.assertEqual(fresh.reason,"FAVORABLE_BREAKOUT_TARGET")
        self.assertGreater(fresh.btc_target,D(1))
    def test_harvest_and_matched_trim_have_sequential_finite_budgets(self):
        for d in (1,-1):
            cfg=Config(core=.5,mode="btc_trim")
            f=feat(close=1070 if d>0 else 930,residual_z=-d*2,btc_return6=-d*.02)
            q=D(d*40)
            s=snap(btc_qty=q,btc_mark=D(str(f.close)))
            st=state(direction=d,btc_target=q,unhedged_btc_target=q,hedge_active=True,
                     activate_count=2,initial_r=30,stop=800 if d>0 else 1200)
            a=decide(cfg,f,s,st)
            self.assertEqual(a.btc_target,D(d*20))
            self.assertEqual(a.state.harvest_target,D(d*20))
            self.assertEqual(a.state.btc_intent,"POSITIVE_HARVEST")
            # Repeated unfilled callbacks neither multiply nor consume budget.
            for i in (1,2):
                next_f=replace(f,closed_ns=f.closed_ns+i*HOUR_NS,available_ns=f.available_ns+i*HOUR_NS)
                a=decide(cfg,next_f,s,a.state)
                self.assertEqual(a.btc_target,D(d*20))
                self.assertFalse(a.state.harvested)
            s=replace(s,btc_qty=D(d*20))
            f=replace(f,closed_ns=f.closed_ns+3*HOUR_NS,available_ns=f.available_ns+3*HOUR_NS)
            b=decide(cfg,f,s,a.state)
            self.assertTrue(b.state.harvested)
            held=b.btc_target
            for i in (1,2):
                b=decide(cfg,replace(f,closed_ns=f.closed_ns+i*HOUR_NS,available_ns=f.available_ns+i*HOUR_NS),
                         replace(s,btc_qty=held),b.state)
                self.assertEqual(b.btc_target,held)
    def test_flat_revoked_entry_late_first_fill_preserves_explicit_zero_cap(self):
        for d in (1,-1):
            f=feat(close=1020 if d>0 else 980)
            entry=decide(Config(),f,snap(btc_qty=D(0)),State())
            revoked=decide(Config(),f,snap(btc_qty=D(0),data_known=False),entry.state)
            self.assertEqual(revoked.btc_target,D(0))
            self.assertEqual(revoked.state.safety_cap,D(0))
            late=decide(Config(),f,snap(btc_qty=D(d),btc_mark=D(1000)),revoked.state)
            self.assertEqual(late.state.parent,0)
            self.assertTrue(late.state.draining)
            self.assertEqual(late.btc_target,D(0))
            self.assertEqual(late.state.safety_cap,D(0))
    def test_native_late_harvest_fill_consumes_once_and_foreign_parent_drains(self):
        from coinmaster.strategy.cm2_native import CM2Strategy
        from nautilus_trader.model.enums import OrderSide
        class ID(str): venue="SIM"
        btc=ID("BTC")
        def event(identity):
            return NS(trade_id=identity,client_order_id="late",instrument_id=btc,
                commission=NS(as_decimal=lambda:D('.2'),currency="USDC"),order_side=OrderSide.SELL,position_id="native-position",
                last_qty=NS(as_decimal=lambda:D(5)),last_px=NS(as_decimal=lambda:D(990)),
                liquidity_side="TAKER",ts_event=200*HOUR_NS+1)
        for original_parent in (1,0,None):
            st=state(btc_target=D(40),unhedged_btc_target=D(40),btc_intent="RISK_TRIM",last_hour=200*HOUR_NS)
            fake=NS(policy_state=st,_seen_trade_ids=set(),_order_audit={"late":{
                "admission":{"parent":original_parent,"intent":"POSITIVE_HARVEST"},"reduce_only":True}},
                fill_audit=[],config=NS(btc_id=btc,execution_policy_hash="fixture"),
                _sync_funding=lambda:None,_entry_fees=D('.4'),_btc_cost_qty=D(40),_parent_funding=D(0),
                _parent_cost_known=True,_liquidating=False,_restore_failed=False,_terminal_event=lambda *a,**k:None,
                _persist_checkpoint=lambda:None,_chain_audit=lambda *a:None)
            position=NS(entry=OrderSide.BUY,quantity=NS(as_decimal=lambda:D(35)),avg_px_open=1000)
            instrument=NS(settlement_currency="USDC",price_increment=NS(as_decimal=lambda:D('.1')))
            fake.cache=NS(position=lambda pid:position,instrument=lambda iid:instrument)
            fake._actual_harvest_fill_geometry=lambda event,foreign:CM2Strategy._actual_harvest_fill_geometry(fake,event,foreign)
            CM2Strategy.on_order_filled(fake,event("actual-native-like-id"))
            self.assertEqual(fake.policy_state.harvested,original_parent==1)
            self.assertTrue(fake.policy_state.draining)
            self.assertTrue(fake.fill_audit[0]["original_intent_revoked_at_fill"])
            self.assertTrue(fake._restore_failed)
            self.assertEqual(fake.fill_audit[0]["actual_harvest_geometry"]["status"],"FAIL" if original_parent==1 else "UNKNOWN")
            if fake._restore_failed:
                flat=decide(Config(),feat(),snap(btc_qty=D(0)),fake.policy_state,terminal=fake._restore_failed)
                fresh=decide(Config(),feat(t=201*HOUR_NS,close=1020),snap(btc_qty=D(0)),flat.state,
                    terminal=fake._restore_failed)
                self.assertEqual(fresh.btc_target,D(0))
                self.assertEqual(fresh.reason,"TERMINAL_FLAT")
                # The actual adapter passes the quarantine flag to the policy,
                # independent of the configured future terminal boundary.
                from unittest.mock import patch
                fake._quotes={};fake.current_features=feat()
                fake.config.policy=Config();fake.config.trading_start_open_ns=0
                fake.config.terminal_close_at_ns=10**25
                fake._snapshot=lambda now:snap(btc_qty=D(0))
                with patch("coinmaster.strategy.cm2_native.decide",side_effect=RuntimeError("AT_POLICY_GATE")) as gate:
                    with self.assertRaisesRegex(RuntimeError,"AT_POLICY_GATE"):
                        CM2Strategy.on_quote_tick(fake,NS(instrument_id=btc,ts_event=200*HOUR_NS+1))
                self.assertIs(gate.call_args.kwargs["terminal"],True)
            once=(fake._entry_fees,fake._parent_funding,fake._btc_cost_qty,len(fake.fill_audit),fake.policy_state)
            CM2Strategy.on_order_filled(fake,event("actual-native-like-id"))
            self.assertEqual(once,(fake._entry_fees,fake._parent_funding,fake._btc_cost_qty,len(fake.fill_audit),fake.policy_state))
            if original_parent==1:
                later=decide(Config(),feat(t=201*HOUR_NS,close=1070),
                    snap(btc_qty=D(35),btc_mark=D(1070)),fake.policy_state)
                self.assertTrue(later.state.harvested)
                self.assertEqual(later.btc_target,D(0))
    def test_fresh_start_populated_cache_rejected_without_engine(self):
        from coinmaster.strategy.cm2_native import CM2Strategy
        for field in ("positions_open","orders_open","orders_inflight"):
            cache=NS(**{name:(lambda value=name: [object()] if value==field else [])
                for name in ("positions_open","orders_open","orders_inflight")})
            with self.assertRaisesRegex(ValueError,"FRESH_START"):
                CM2Strategy.on_start(NS(cache=cache,_checkpoint_loaded=False))

if __name__ == '__main__': unittest.main()
