"""No native engine/Strategy constructors: exact domain journal continuity."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore,KEY,canonical
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_policy import Config,State,PairedHourBuilder,decide
from coinmaster.strategy.cm2_execution import ExecutionLimits
from nautilus_trader.model.identifiers import InstrumentId,ClientOrderId
from runtime.tests.test_cm2_policy import feat,snap

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.store=NativeCheckpointStore(NS(db=self.db))
    def tearDown(self): self.db.close()
    def fake(self):
        btc=InstrumentId.from_str('BTCUSDC.HYPERLIQUID');sol=InstrumentId.from_str('SOLUSDC.HYPERLIQUID')
        self.cash=D(10000);self.positions=[];self.orders=[]
        self.continuity={"seed":"10000","native_HWM":{"peak":"11000","count":17},"seq":50}
        account=NS(id='SIM-001',base_currency='USDC',balance_total=lambda c:NS(as_decimal=lambda:self.cash),
            balance_free=lambda c:NS(as_decimal=lambda:self.cash),balance_locked=lambda c:NS(as_decimal=lambda:D(0)),
            margins_init=lambda:{},margins_maint=lambda:{})
        obj=NS(id='CM2-001',config=NS(btc_id=btc,sol_id=sol,policy=Config(),execution_policy_hash='exec',
            trading_start_open_ns=1,terminal_close_at_ns=100,checkpoint_store=self.store,
            exit_fee_rate=D('.000432'),limits=ExecutionLimits(D(1000000)),margin_policy=NS(),
            continuity_reader=lambda:deepcopy(self.continuity)),
            cache=NS(account_for_venue=lambda v:account,positions_open=lambda:self.positions,
                     orders_open=lambda:self.orders,orders_inflight=lambda:[]),
            _seed_hours_sha256='pinned-warmup',_retained_audit_chain='retained-chain',_admission_sources={'policy':'frozen-source'},fill_audit=[],cm2_audit=[],_order_audit={},
            policy_state=State(direction=1,parent=7,btc_target=D(20),unhedged_btc_target=D(20),
                               btc_intent='RISK_TRIM',safety_cap=D(20)),
            current_features=feat(),hours=[],hour_builder=PairedHourBuilder(),
            _owned={'oid':{'instrument_id':btc,'client_order_id':ClientOrderId('oid'),
                'submit_ns':1,'terminal':False,'acked':False}},_seen_trade_ids={'fill-a'},
            _last_child={btc:2},_entry_fees=D('.432'),_btc_cost_qty=D(20),
            _parent_funding=D('-1.2'),_funding_last=D('-3'),_parent_cost_known=True,
            _liquidating=False,_risk_unknown=False,orphan_started_ns=None,
            _checkpoint_revision=(self.store.read()[0] if self.store.read() else 0),_checkpoint_loaded=False,_restore_failed=False,
            _quotes={},_latest_marks={},_turnover={btc:[(1,D(1000000))]},clock=NS(timestamp_ns=lambda:10))
        for name in ('_checkpoint_identity','_native_checkpoint_binding','_feed_checkpoint_binding','_checkpoint_document','on_save','on_load'):
            setattr(obj,name,lambda *args,_name=name:getattr(CM2Strategy,_name)(obj,*args))
        return obj
    def test_cas_idempotent_and_conflict(self):
        self.assertEqual(self.store.persist(b'one',0),1)
        changes=self.db.total_changes
        self.assertEqual(self.store.persist(b'one',1),1)
        self.assertEqual(self.db.total_changes,changes)
        self.assertIsNone(self.store.persist(b'two',0))
        self.assertEqual(self.store.read(),(1,b'one'))
        self.assertEqual(self.store.persist(b'two',1),2)
    def test_integrity_and_foreign_transaction_fail_closed(self):
        self.store.persist(b'one',0)
        self.db.execute('UPDATE cm2_domain_checkpoint SET body=?',(b'corrupt',));self.db.commit()
        with self.assertRaisesRegex(ValueError,'INTEGRITY'): self.store.read()
        self.db.execute('BEGIN')
        with self.assertRaisesRegex(ValueError,'FOREIGN_TRANSACTION'): self.store.persist(b'two',1)
        self.db.rollback()
    def test_durable_reopen_same_bytes(self):
        with TemporaryDirectory() as path:
            connection=sqlite3.connect(Path(path)/'native.sqlite')
            store=NativeCheckpointStore(NS(db=connection));store.persist(b'proof',0);connection.close()
            connection=sqlite3.connect(Path(path)/'native.sqlite')
            self.assertEqual(NativeCheckpointStore(NS(db=connection)).read(),(1,b'proof'));connection.close()
    def test_roundtrip_idempotent_keeps_native_HWM_seed_parent_and_seen_fills(self):
        obj=self.fake();before=deepcopy(self.continuity)
        saved=obj.on_save();revision=obj._checkpoint_revision
        obj.policy_state=State();obj._entry_fees=D(999);obj._seen_trade_ids=set()
        obj.on_load(saved)
        self.assertEqual(obj.policy_state.parent,7)
        self.assertEqual(obj.policy_state.btc_target,D(20))
        self.assertEqual(obj._entry_fees,D('.432'))
        self.assertEqual(obj._seen_trade_ids,{'fill-a'})
        self.assertEqual(self.continuity,before)
        self.assertEqual(obj._turnover,{obj.config.btc_id:[(1,D(1000000))]})
        self.assertTrue(obj._checkpoint_loaded)
        obj.on_load(saved)
        self.assertEqual(obj.on_save(),saved)
        self.assertEqual(obj._checkpoint_revision,revision)
        # Duplicate fill returns at the real adapter's idempotence gate.
        CM2Strategy.on_order_filled(obj,NS(trade_id='fill-a'))
        self.assertEqual(obj._entry_fees,D('.432'))
    def test_source_and_configuration_mismatch(self):
        for source in (True,False):
            obj=self.fake();saved=obj.on_save()
            if source: obj._admission_sources={'policy':'different'}
            else: obj.config.policy=replace(obj.config.policy,load=5)
            with self.assertRaisesRegex(ValueError,'SOURCE_CONFIG'):obj.on_load(saved)
            self.assertTrue(obj._restore_failed)
    def test_seed_HWM_or_sequence_mismatch(self):
        for field,value in (('seed','20000'),('native_HWM',{'peak':'9000','count':17}),('seq',51)):
            obj=self.fake();saved=obj.on_save();self.continuity[field]=value
            with self.assertRaisesRegex(ValueError,'SEED_HWM'):obj.on_load(saved)
    def test_native_cash_inventory_orders_mismatch(self):
        for which in ('cash','position','order'):
            obj=self.fake();saved=obj.on_save()
            if which=='cash':self.cash=D(9999)
            elif which=='position':self.positions=[NS(id='p',instrument_id=obj.config.btc_id,side='LONG',quantity='1',avg_px_open='1000')]
            else:self.orders=[NS(client_order_id='late',instrument_id=obj.config.btc_id,side='BUY',status='6',quantity='1',leaves_qty='1')]
            with self.assertRaisesRegex(ValueError,'NATIVE_CACHE'):obj.on_load(saved)
    def test_stale_or_missing_durable_checkpoint_rejected(self):
        obj=self.fake();saved=obj.on_save()
        self.store.persist(b'newer',obj._checkpoint_revision)
        with self.assertRaisesRegex(ValueError,'DURABLE_LATEST'):obj.on_load(saved)
        self.db.execute('DELETE FROM cm2_domain_checkpoint');self.db.commit()
        with self.assertRaisesRegex(ValueError,'DURABLE_LATEST'):obj.on_load(saved)
    def test_no_partial_application_on_integrity_or_retained_audit_mismatch(self):
        obj=self.fake();saved=obj.on_save();parent=obj.policy_state.parent
        obj.fill_audit.append({'unmatched':'event'})
        with self.assertRaisesRegex(ValueError,'AUDIT_CONTINUITY'):obj.on_load(saved)
        self.assertEqual(obj.policy_state.parent,parent)
        with self.assertRaisesRegex(ValueError,'STATE_KEYS'):obj.on_load({'bad':b'{}'})
        self.assertTrue(obj._restore_failed)
    def test_advanced_clock_or_changed_capacity_feed_rejected(self):
        for clock in (True,False):
            obj=self.fake();saved=obj.on_save()
            if clock: obj.clock=NS(timestamp_ns=lambda:11)
            else: obj._turnover[obj.config.btc_id].append((2,D(2000000)))
            with self.assertRaisesRegex(ValueError,'CLOCK_OR_RETAINED_FEED'):obj.on_load(saved)
            self.assertTrue(obj._restore_failed)
    def test_checkpoint_zero_cap_late_entry_does_not_adopt_new_parent(self):
        for d in (1,-1):
            obj=self.fake()
            obj.policy_state=State(parent=7,btc_intent="RISK_TRIM",safety_cap=D(0))
            saved=obj.on_save();obj.policy_state=State();obj.on_load(saved)
            decision=decide(Config(),feat(),snap(btc_qty=D(d)),obj.policy_state)
            self.assertEqual(decision.btc_target,D(0))
            self.assertEqual(decision.state.parent,7)
            self.assertEqual(decision.state.safety_cap,D(0))
            self.assertTrue(decision.state.draining)
    def test_failed_load_lockout_survives_explicit_save_and_latest_replay(self):
        obj=self.fake();saved=obj.on_save()
        with self.assertRaisesRegex(ValueError,'STATE_KEYS'):obj.on_load({'bad':b'{}'})
        self.assertTrue(obj._restore_failed)
        locked=obj.on_save()
        self.assertNotEqual(locked,saved)
        obj.on_load(locked)
        self.assertTrue(obj._restore_failed)
        action=decide(Config(),feat(),snap(),obj.policy_state,terminal=obj._restore_failed)
        self.assertEqual(action.btc_target,D(0))
        self.assertTrue(action.state.draining)
    def test_retained_audit_chain_mismatch_rejected(self):
        obj=self.fake();saved=obj.on_save();obj._retained_audit_chain='different-chain'
        with self.assertRaisesRegex(ValueError,'AUDIT_CONTINUITY'):obj.on_load(saved)
        self.assertTrue(obj._restore_failed)
    def test_actor_public_save_load_contract_available(self):
        from nautilus_trader.common.actor import Actor
        self.assertIn('on_save',Actor.save.__doc__)
        self.assertIn('on_load',Actor.load.__doc__)

if __name__=='__main__':unittest.main()
