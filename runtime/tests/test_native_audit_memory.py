"""Real native archival/parity diagnostics; no historical replay."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest
from coinmaster.research.native_audit import NativeAuditArchive, CashRows, FillTimes, audit_json_default
from test_native_sol_corridor import setup, original, advance, close, stress
from test_native_episode_risk import run_ticks, tick
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from nautilus_trader.analysis.reporter import ReportProvider


def frames(path):
    return pd.read_csv(path).sort_values("client_order_id").reset_index(drop=True)


def test_native_archive_orders_fills_cash_fees_rights_and_exact_duplicate(tmp_path):
    results=[]
    for archived in (False, True):
        s,e,ep=setup()
        audit=NativeAuditArchive(tmp_path/"audit.sqlite",s) if archived else None
        seen=[]
        try:
            def boundary(ts):
                if audit:
                    expected=[o.to_dict() for o in e.cache.orders() if o.is_closed and str(o.client_order_id) not in s._pending_by_order]
                    audit.capture(e,ts)
                    for row in expected:
                        stored=audit.db.execute("SELECT payload FROM native WHERE kind='order' AND id=?", (row["client_order_id"],)).fetchone()
                        assert json.loads(stored[0])==row
                seen.append((str(s._v3_equity()),str(s._rf_peak),str(ep.sol_qty),
                    dict(ep.sol_add_filled_notional),dict(ep.sol_risk_retired_notional),
                    sorted(s._pending_by_order),s._rf_fill_epoch,s._rf_dirty))
            original(s,e,ep,20,ts=30);advance(s,e,31);boundary(31)
            # Both real positions remain live; order cleanup must not alter them.
            assert len(e.cache.positions_open())==2
            stress(s,a="1",u=".1");advance(s,e,32);advance(s,e,33);boundary(33)
            # Mutable acceptance context survives archival, and exact duplicate
            # native receipt is still filtered after its terminal order is gone.
            if audit:
                body=audit.db.execute("SELECT payload FROM native WHERE kind='order_event' AND json_extract(payload,'$.type')='OrderFilled' LIMIT 1").fetchone()[0]
                from nautilus_trader.model.events import OrderFilled
                event=OrderFilled.from_dict(json.loads(body));before=s._rf_fill_epoch
                s.on_order_filled(event)
                assert s._rf_fill_epoch==before
                assert str(event.client_order_id) in s._order_audit
            close(s,e)
            boundary(100000000000000)
            fees=sum(D(row["commission"]) for row in s.fill_audit)
            cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
            fills=list(s.fill_audit)
            if audit:
                audit.capture(e,100000000000001,final=True);audit.freeze()
                paths=[tmp_path/"archived-orders.csv",tmp_path/"archived-fills.csv"]
                audit.export_orders(paths[0]);audit.export_orders(paths[1],True)
                account_rows=list(CashRows(audit))
                times=sorted(FillTimes(audit))
                assert not e.cache.orders() and not e.cache.positions()
                assert len(e.cache.account_for_venue(BTC_PERP.id.venue).events)==1
                descriptor=json.loads(json.dumps(s.fill_audit,default=audit_json_default))
                assert descriptor["rows"]==len(fills) and descriptor["sha256"]==hashlib.sha256(audit.path.read_bytes()).hexdigest()
            else:
                paths=[tmp_path/"native-orders.csv",tmp_path/"native-fills.csv"]
                e.trader.generate_orders_report().to_csv(paths[0])
                e.trader.generate_order_fills_report().to_csv(paths[1])
                account=e.trader.generate_account_report(BTC_PERP.id.venue)
                account_rows=[dict(timestamp=str(t),active=str(total),reserve="0",total=str(total)) for t,total in account["total"].items()]
                times=sorted(o.ts_last for o in e.cache.orders() if o.filled_qty.as_decimal()>0)
            results.append((seen,fills,cash,fees,account_rows,times,dict(s._order_audit),[frames(p) for p in paths]))
        finally:
            if audit:audit.close()
            e.end();e.dispose()
    assert results[0][:-1]==results[1][:-1]
    for expected,actual in zip(results[0][-1],results[1][-1]):
        pd.testing.assert_frame_equal(expected.drop(columns=["init_id"]),actual.drop(columns=["init_id"]),check_dtype=False)


def test_mutable_context_and_rows_exact_disk_membership(tmp_path):
    from types import SimpleNamespace
    s=SimpleNamespace(risk_first_sol_audit=[],fill_audit=[],_order_audit={},_seen_trade_ids=set())
    a=NativeAuditArchive(tmp_path/"context.sqlite",s)
    try:
        s._order_audit["one"]={"accept_ns":None}
        row=s._order_audit.get("one")
        row["accept_ns"]="321"
        a.contexts.flush();a.db.commit();a.contexts.current.clear()
        assert s._order_audit["one"]=={"accept_ns":"321"}
        s._seen_trade_ids.add("old");a.db.commit()
        assert "old" in s._seen_trade_ids and "new" not in s._seen_trade_ids
        for i in range(20):s.fill_audit.append({"native":i})
        a.freeze()
        assert list(s.fill_audit)==[{"native":i} for i in range(20)]
    finally:a.close()

@pytest.mark.parametrize("name",[
    "test_native_risk_cancel_latepartial_retires_only_unfilled_no_IOC_resurrection",
    "test_final_receipt_strictly_after_fill_and_never_backdated",
    "test_healthy_original_native_partial_half_full_two_episode_OFF_ON_parity",
])
def test_native_existing_lifecycle_with_archive(name,tmp_path,monkeypatch):
    import test_native_sol_corridor as native
    active={}
    originals={key:getattr(native,key) for key in ("setup","alpha_setup","advance","engine")}
    def wrap_setup(which):
        def run(*args,**kwargs):
            s,e,ep=originals[which](*args,**kwargs)
            if id(e) not in active:
                active[id(e)]=NativeAuditArchive(tmp_path/(which+str(len(active))+".sqlite"),s)
            return s,e,ep
        return run
    def advance_with_archive(s,e,ts,*args,**kwargs):
        result=originals["advance"](s,e,ts,*args,**kwargs)
        active[id(e)].capture(e,ts)
        return result
    def engine_with_archive(s,*args,**kwargs):
        e=originals["engine"](s,*args,**kwargs)
        active[id(e)]=NativeAuditArchive(tmp_path/("engine"+str(len(active))+".sqlite"),s)
        def full_native_orders():
            from nautilus_trader.model.orders import OrderUnpacker
            from nautilus_trader.model import events
            cached={str(o.client_order_id):o for o in e.cache.orders()}
            for (body,) in active[id(e)].db.execute("SELECT payload FROM native WHERE kind='order'"):
                row=json.loads(body);oid=row["client_order_id"]
                if oid in cached:continue
                native_events=[]
                for (payload,) in active[id(e)].db.execute(
                    "SELECT payload FROM native WHERE kind='order_event' AND json_extract(payload,'$.client_order_id')=? ORDER BY seq",(oid,)):
                    values=json.loads(payload)
                    native_events.append(getattr(events,values["type"]).from_dict(values))
                order=OrderUnpacker.from_init(native_events[0])
                for event in native_events[1:]:order.apply(event)
                assert order.to_dict()==row
                cached[oid]=order
            return [cached[key] for key in sorted(cached)]
        s._test_full_native_orders=full_native_orders
        return e
    monkeypatch.setattr(native,"engine",engine_with_archive)
    monkeypatch.setattr(native,"setup",wrap_setup("setup"))
    monkeypatch.setattr(native,"alpha_setup",wrap_setup("alpha_setup"))
    monkeypatch.setattr(native,"advance",advance_with_archive)
    try:getattr(native,name)()
    finally:
        for archive in active.values():archive.close()


def test_native_Q2_pending_unknown_and_open_order_survive_archive(tmp_path):
    from nautilus_trader.model.enums import OrderSide,TimeInForce
    s,e,ep=setup()
    a=NativeAuditArchive(tmp_path/"pending.sqlite",s)
    try:
        intent=s._domain._intent(ep,"BTC_ENTRY",ep.side,None,quantity=10)
        order=s.order_factory.limit(BTC_PERP.id,OrderSide.BUY,BTC_PERP.make_qty(10),
            BTC_PERP.make_price(1),time_in_force=TimeInForce.GTC)
        key=str(order.client_order_id)
        s._pending_by_order[key]=intent
        s.submit_order(order)
        run_ticks(e,[tick(BTC_PERP,10)])
        s._pending_by_order["UNKNOWN_NATIVE_ACK"]=intent
        a.capture(e,11)
        assert e.cache.order(order.client_order_id) is order and order.is_open
        assert s._pending_by_order[key] is intent and s._pending_by_order["UNKNOWN_NATIVE_ACK"] is intent
        actual,lo,hi,unknown=s._corridor_btc_endpoints(e.cache.positions_open()[0],10)
        assert unknown and hi==actual+10 and lo==actual
        parent=s._split_parent
        parent.update(closed=False,quantity=D(100),filled=D(50),cancelled=D(0))
        assert s._split_cover_margin_reserve(BTC_PERP.id,D(50),10)==100
    finally:a.close();e.end();e.dispose()


def test_archival_commit_failure_does_not_purge_native(tmp_path,monkeypatch):
    s,e,ep=setup()
    a=NativeAuditArchive(tmp_path/"failure.sqlite",s)
    try:
        original(s,e,ep,20,ts=30);advance(s,e,31)
        orders=list(e.cache.orders());cash=s._v3_equity()
        def fail():raise OSError("INJECTED_ARCHIVE_FAILURE")
        monkeypatch.setattr(a.contexts,"flush",fail)
        with pytest.raises(OSError,match="INJECTED_ARCHIVE_FAILURE"):
            a.capture(e,31)
        assert e.cache.orders()==orders and s._v3_equity()==cash
        a.db.rollback()
    finally:a.close();e.end();e.dispose()


@pytest.mark.parametrize("fault",["inner","outer","loop"])
def test_production_archive_failure_preserves_real_native_artifacts(tmp_path,monkeypatch,fault):
    from dataclasses import asdict
    from datetime import datetime,UTC
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research import native_baseline as nb
    from coinmaster.domain.wave_overlay import Candidate
    import pyarrow as pa
    import pyarrow.parquet as pq
    import sqlite3
    start,_=write_streaming_fixture(tmp_path,trading_days=1)
    shift=nb.TRADING_START_MS-start
    for path in (tmp_path/"normalized").glob("*.parquet"):
        rows=pq.read_table(path).to_pylist()
        for row in rows:row["open_time_ms"]+=shift
        pq.write_table(pa.Table.from_pylist(rows),path)
    options=dict(trading_start_ms=nb.TRADING_START_MS,trading_end_ms=nb.TRADING_START_MS+2*nb.MINUTE_MS,
        warmup_start_ms=shift,research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,
        research_v0_selective_lifecycle_repairs=True,research_btc_direction_sizing=True,
        research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_sol_risk_first="alpha-corridor-v1",observe_minute_risk=True,include_funding=False)
    target=tmp_path/"production"
    def fail(*args,**kwargs):raise ValueError("INJECTED_"+fault)
    if fault=="inner":
        monkeypatch.setattr(nb,"assert_report_boundaries",fail)
    elif fault=="loop":
        real_capture=NativeAuditArchive.capture
        def completed_batch_then_fail(self,*args,**kwargs):
            real_capture(self,*args,**kwargs)
            fail()
        monkeypatch.setattr(NativeAuditArchive,"capture",completed_batch_then_fail)
    if fault!="outer":
        with pytest.raises(ValueError,match="INJECTED_"+fault):
            nb.run_native_diagnostic(tmp_path,candidate=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000),artifact_dir=target,**options)
    else:
        policy=nb.ExecutionPolicy();fees=nb.FixedBaseFeePolicy()
        config={**nb.BASELINE_CONFIG,"candidate":asdict(Candidate()),"execution_policy":asdict(policy),
            "fixed_base_fee_policy":asdict(fees),"fee_policy_hash":fees.hash,"tp_fee_floor_v1":False,
            "run_interval":{"start":datetime.fromtimestamp(nb.TRADING_START_MS/1000,UTC).isoformat(),
                "end_exclusive":datetime.fromtimestamp(nb.TRADING_END_MS/1000,UTC).isoformat(),"initial_active_seed":"10000"}}
        manifest=tmp_path/"bybit-1m/manifest.json"
        control={"status":"NOT_FAITHFUL_DIAGNOSTIC","config":config,"policy":asdict(policy),
            "summary":{"terminal_total":"3386491.65211338"},"data_hash":hashlib.sha256(
                json.dumps(json.loads(manifest.read_text()),sort_keys=True,separators=(",",":")).encode()).hexdigest()}
        cp=tmp_path/"control.json";cp.write_text(json.dumps(control))
        real_run=nb.run_native_diagnostic;real_sha=nb.sha256_file
        def bounded(*args,**kw):
            kw.update(options)
            kw["candidate"]=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000)
            return real_run(*args,**kw)
        def only_outer(path):
            if Path(path)==cp:fail()
            return real_sha(path)
        monkeypatch.setattr(nb,"run_native_diagnostic",bounded)
        monkeypatch.setattr(nb,"sha256_file",only_outer)
        with pytest.raises(ValueError,match="INJECTED_outer"):
            nb.run_research_v0_repairs_cli(tmp_path,target,cp)
    db=next(target.glob("*-native-audit.sqlite"))
    connection=sqlite3.connect(f"file:{db}?mode=ro",uri=True)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    assert connection.execute("SELECT count(*) FROM native WHERE kind='account'").fetchone()[0]>0
    connection.close()
    if fault=="loop":
        assert not list(target.glob("*-raw-native.json"))
    else:
        raw=json.loads(next(target.glob("*-raw-native.json")).read_text())
        assert raw["native_risk_first_audit"]["schema"]=="coinmaster.native-audit.sqlite.v1"
        assert raw["native_risk_first_audit"]["sha256"]==hashlib.sha256(db.read_bytes()).hexdigest()
        for artifact in raw["execution_artifacts"].values():
            assert Path(artifact["path"]).exists()
            assert artifact["sha256"]==hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest()


def test_real_native_partition_parity_and_closed_lifecycle_inventory(tmp_path):
    from test_native_sol_corridor import Observed,config,engine,Episode
    from test_native_episode_risk import marks
    class Load(Observed):
        generated=0;target=0
        def _conditional_check(self,q):pass
        def on_quote_tick(self,q):
            super().on_quote_tick(q)
            if q.instrument_id!=SOL_PERP.id or self.generated>=self.target:return
            add=self.generated%2==0
            i=self._domain._intent(self._domain.episode,"SOL_ADD" if add else "SOL_EXIT",
                -1 if add else 1,None,quantity=.1,reason="CONDITIONAL_NET_ADD" if add else "CONDITIONAL_NET_EXIT")
            if add:self._conditional["original_attempts"][i.id]=()
            self._conditional_physical=True
            try:self._submit_intent(i,100,100,None,0,ts_now=q.ts_event)
            finally:self._conditional_physical=False
            self.generated+=1
    outputs=[]
    for partition in (7,60,400):
        s=Load(config());e=engine(s,rate="1000000/00:00:01")
        a=NativeAuditArchive(tmp_path/f"partition-{partition}.sqlite",s)
        try:
            run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)]);marks(s,2)
            s._domain.episode=Episode("storage-load",1,10000,1,h=10000);s._conditional_state(2);s.target=400
            while s.generated<s.target:
                first=s.generated+10
                run_ticks(e,[tick(SOL_PERP,t) for t in range(first,first+min(partition,s.target-s.generated))])
                a.capture(e,s.generated+10)
            assert a.count("position")+a.count("position_snapshot")==200
            assert a.count("order")==400 and a.count("account")==401
            assert not e.cache.orders() and not e.cache.positions() and not s._pending_by_order
            assert len(s._domain.episode.pending)==0
            cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
            assert cash==D(9996)
            outputs.append((list(s.fill_audit),list(CashRows(a)),cash,s._rf_peak))
        finally:a.close();e.end();e.dispose()
    assert outputs[0]==outputs[1]==outputs[2]


def test_closed_NETTING_position_keeps_forced_or_unresolved_native_refs(tmp_path):
    from nautilus_trader.model.enums import OrderSide,TimeInForce
    s,e,ep=setup()
    a=NativeAuditArchive(tmp_path/"refs.sqlite",s)
    try:
        original(s,e,ep,20,ts=30);advance(s,e,31);close(s,e)
        position=next(p for p in e.cache.positions_closed() if p.instrument_id==SOL_PERP.id)
        order=s.order_factory.limit(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(.1),
            SOL_PERP.make_price(1),time_in_force=TimeInForce.GTC,reduce_only=True)
        e.cache.add_order(order)
        s._forced_close_orders.add(str(order.client_order_id))
        a.capture(e,100000000000000)
        assert e.cache.position(position.id) is position
        assert e.cache.order(order.client_order_id) is order
    finally:a.close();e.end();e.dispose()

