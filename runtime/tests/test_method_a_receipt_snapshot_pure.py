"""Public native Cache/Order receipt serialization, no engine/matcher."""
import json,unittest
from types import SimpleNamespace as NS
from decimal import Decimal as D
from pathlib import Path
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.model.enums import OrderSide,TimeInForce
from nautilus_trader.model.identifiers import TraderId,StrategyId
from coinmaster.research.native_fixture import SOL_PERP,BTC_PERP
from coinmaster.research.method_a_margin import native_receipt_snapshot
from coinmaster.domain.wave_overlay import Intent

class ReceiptSnapshotPure(unittest.TestCase):
    def context(self):
        cache=Cache();cache.add_instrument(SOL_PERP);cache.add_instrument(BTC_PERP)
        sid=StrategyId("UNIT-001");clock=TestClock()
        factory=OrderFactory(TraderId("UNIT-001"),sid,clock)
        trader=NS(strategy_ids=lambda:[sid],actor_ids=lambda:[],exec_algorithm_ids=lambda:[])
        engine=NS(kernel=NS(exec_engine=NS(command_count=7,event_count=11),trader=trader))
        ep=NS(id="P",pending={})
        strategy=NS(cache=cache,id=sid,order_factory=factory,_domain=NS(episode=ep),
            config=NS(research_method_a_input_binding={"source":{"proof":"UNIT_ONLY"}}),
            _mr_episode=1,_mr_sequence=39,_pending_by_order={},_pair_orders={},
            _queued_intents=[],_mandatory_sol_exit=None,_liquidating=False,
            _forced_close_reason=None,is_exiting=lambda:False,_mr_failed=False)
        return strategy,engine

    def test_actual_native_initialized_foreign_order_is_never_omitted(self):
        s,e=self.context()
        foreign=OrderFactory(TraderId("UNIT-001"),StrategyId("FOREIGN-001"),TestClock())
        order=foreign.market(instrument_id=SOL_PERP.id,order_side=OrderSide.BUY,
            quantity=SOL_PERP.make_qty(D(".1")),time_in_force=TimeInForce.IOC)
        s.cache.add_order(order)
        before=order.to_dict()
        raw=native_receipt_snapshot(s,e,5)
        self.assertEqual(json.loads(json.dumps(raw)),raw)
        self.assertEqual(raw["native_orders"],[before])
        self.assertEqual(raw["native_init_events"],[type(order.init_event).to_dict(order.init_event)])
        self.assertEqual(raw["native_orders"][0]["status"],"INITIALIZED")
        self.assertEqual(order.to_dict(),before)
        self.assertFalse(raw["financial_qualification"])
        self.assertEqual(raw["complete_command_universe"],"UNKNOWN_REQUIRES_SEALED_SOURCE_PROOF")

    def test_unresolved_owner_and_pending_are_exported_with_no_zero_waiver(self):
        s,e=self.context()
        intent=Intent("I","P","SOL_ADD",None,1,quantity=.1)
        s._pending_by_order["MISSING-PENDING"]=intent
        s._pair_orders["MISSING-OWNER"]=dict(instrument=SOL_PERP.id,kind="SOL_CLOSE",parent="P",
            pending=dict(payload=(D(".1"),None,None),sequence=1),
            retiring=dict(native_right=D(".1"),terminal_event_id=None))
        s._domain.episode.pending["I"]=intent
        s._queued_intents=[(intent,None,3)]
        s._mandatory_sol_exit=(intent,None,4)
        raw=native_receipt_snapshot(s,e,9)
        self.assertEqual(raw["unresolved_ids"],["MISSING-OWNER","MISSING-PENDING"])
        self.assertFalse(raw["pending_by_order"][0]["resolved"])
        self.assertEqual(raw["paired_owners"][0]["owner"]["pending"]["payload"],["0.1",None,None])
        self.assertEqual(raw["domain_pending"]["I"]["action"],"SOL_ADD")
        self.assertEqual(len(raw["queued_intents"]),1)
        self.assertEqual(raw["mandatory_sol_exit"]["decision_index"],4)
        self.assertEqual(json.loads(json.dumps(raw)),raw)

    def test_actual_factory_counter_read_has_no_mutation(self):
        s,e=self.context()
        order=s.order_factory.market(instrument_id=BTC_PERP.id,order_side=OrderSide.BUY,
            quantity=BTC_PERP.make_qty(D(".001")),time_in_force=TimeInForce.IOC)
        s.cache.add_order(order)
        count=s.order_factory.get_client_order_id_count()
        raw=native_receipt_snapshot(s,e,2)
        self.assertEqual(raw["high_watermarks"],dict(exec_command_count=7,exec_event_count=11,
            factory_client_order_id_count=count,factory_order_list_id_count=0))
        self.assertEqual(s.order_factory.get_client_order_id_count(),count)
        self.assertEqual(raw["parent"],"P")
        self.assertEqual(raw["risk_episode_id"],"P:1")
        self.assertEqual(raw["risk_sequence_before_receipt"],39)

    def test_source_hook_precedes_first_run_and_snapshot_is_at_receipt(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/"tests/run_method_a_sol.py").read_text()
        self.assertLess(source.index("book.bind_receipt_source(engine)"),source.index("engine.run(streaming=True)"))
        source=(root/"coinmaster/research/method_a_margin.py").read_text()
        pre=source[source.index("    def pre_process(self,data):"):source.index("\n\ndef native_receipt_snapshot")]
        self.assertLess(pre.index("super().pre_process(data)"),pre.index("self.receipt_snapshot()"))
        self.assertIn("native_input_epoch=self.epochs[data.instrument_id]",pre)
        source=(root/"coinmaster/research/native_baseline.py").read_text()
        source=source[source.index("    research_native_book = None"):]
        self.assertLess(source.index("research_native_book.bind_receipt_source(engine)"),source.index("engine.run("))


    def test_episode_change_refreshes_only_audit_dedupe(self):
        from coinmaster.strategy.method_a_risk_native import MethodARiskResearch
        logs=[]
        p=dict(parent="P",p0=None,tp_lots={},close_sol=False,protection_since=None,
            entry_qty=D(0),entry_notional=D(0),atr=D(1),first_fill_ns=None)
        s=NS(config=NS(sol_id=SOL_PERP.id,research_native_book=None),_pair=p,_mr_episode=0,
            _mr_enabled=lambda:True,_pair_qty=lambda iid:D(0),_pair_sol_v2=lambda:False,
            _pair_work=lambda **kwargs:[],_pair_orders={},_pair_log=lambda *a,**kw:logs.append((a,kw)),
            cache=NS(instrument=lambda iid:SOL_PERP))
        MethodARiskResearch._pair_sol_boundary(s,"BEFORE_NATIVE_MATCHING_INPUT",1,True)
        MethodARiskResearch._pair_sol_boundary(s,"BEFORE_NATIVE_MATCHING_INPUT",2,True)
        self.assertEqual(len(logs),1)
        s._mr_episode=1
        MethodARiskResearch._pair_sol_boundary(s,"BEFORE_NATIVE_MATCHING_INPUT",3,True)
        self.assertEqual(len(logs),2)
        self.assertEqual(s._pair_sol_boundary_counts,dict(checks=3,strict=3,unknown=0))
        self.assertEqual(logs[0][1],logs[1][1])

    def test_full_cache_capture_is_once_at_first_receipt_of_new_episode(self):
        from coinmaster.research.method_a_margin import MethodABookWitness
        s,e=self.context()
        s._mr_episode=0
        book=NS(strategy=s,receipt_engine=e,receipt_ordinal=0,receipt_episode=None)
        old=MethodABookWitness.receipt_snapshot(book)
        self.assertEqual(old["availability"],"NOT_CAPTURED_NO_NEW_RISK_EPISODE")
        s._mr_episode=1
        new=MethodABookWitness.receipt_snapshot(book)
        self.assertEqual(new["previous_receipt_parent"],"P")
        self.assertEqual(new["previous_receipt_episode"],0)
        self.assertEqual(new["receipt_ordinal"],2)
        self.assertEqual(new["risk_episode_id"],"P:1")
        later=MethodABookWitness.receipt_snapshot(book)
        self.assertEqual(later["availability"],"NOT_CAPTURED_NO_NEW_RISK_EPISODE")
        self.assertEqual(book.receipt_ordinal,3)

    def test_unknown_owner_capture_is_unknown_and_does_not_throw(self):
        from coinmaster.research.method_a_margin import MethodABookWitness
        s,e=self.context()
        s._pair_orders["MALFORMED-OWNER"]={}
        book=NS(strategy=s,receipt_engine=e,receipt_ordinal=0,receipt_episode=("P",0))
        raw=MethodABookWitness.receipt_snapshot(book)
        self.assertEqual(raw["availability"],"UNKNOWN_COLLECTOR_EXCEPTION")
        self.assertEqual(raw["collection_error_type"],"KeyError")
        self.assertEqual(raw["risk_sequence_before_receipt"],39)
        self.assertEqual(raw["risk_episode_id"],"P:1")
        self.assertFalse(raw["financial_qualification"])
        self.assertEqual(json.loads(json.dumps(raw)),raw)
