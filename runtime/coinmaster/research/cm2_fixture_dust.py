"""ENGINEERING ONLY: native SOL residual-dust planner edge, not CM2 alpha.
Import/validation is constructor-free. Actual execution requires separate root GO.
"""
from dataclasses import asdict
from decimal import Decimal as D
import json
from pathlib import Path

FIXTURE_ID = "cm2-residual-dust-native-v1"
START_NS = 1725148800000000000
MINUTE_NS = 60_000_000_000
END_NS = START_NS + 20*MINUTE_NS
PRICE = D("141.3")
SEED = D(10000)
OPEN_QTY = D("8.48")
CAP_QTY = D("8.46")
EXPECTED_CHILD = D("8.40")
SCOPE = "ENGINEERING_TESTONLY_SOL_DRIVER_NOT_ALPHA_HEDGE_STRUCTURAL_OR_WINNER"
# minute, tag, target, cap quantity, stock partial-order shape
SCRIPT = (
    (1,"LONG_OPEN",OPEN_QTY,D(100),False),
    (2,"LONG_CHILD",D(0),CAP_QTY,False),
    (3,"LONG_CLOSE",D(0),D(100),False),
    (4,"SHORT_OPEN",-OPEN_QTY,D(100),False),
    (5,"SHORT_CHILD",D(0),CAP_QTY,False),
    (6,"SHORT_CLOSE",D(0),D(100),False),
    (7,"LONG_PARTIAL_OPEN",OPEN_QTY,D(100),False),
    (8,"LONG_PARTIAL_CHILD",D(0),CAP_QTY,True),
    (9,"LONG_PARTIAL_CLOSE",D(0),D(100),False),
    (10,"SHORT_PARTIAL_OPEN",-OPEN_QTY,D(100),False),
    (11,"SHORT_PARTIAL_CHILD",D(0),CAP_QTY,True),
    (12,"SHORT_PARTIAL_CLOSE",D(0),D(100),False),
    (13,"DUST_OPEN",D(".08"),D(100),False),
    (14,"PREEXISTING_DUST_HOLD",D(0),D(100),False),
    (15,"RECOVERED_DUST_CLOSE",D(0),D(100),False),
)

def sol_price(minute):
    return D(150) if minute in (13,15,16,17,18,19,20) else D(100) if minute==14 else PRICE

def validate_request(request):
    if (request.get("fixture_id"),request.get("start_ns"),request.get("end_ns")) != (FIXTURE_ID,START_NS,END_NS):
        raise ValueError("CM2_EXPLICIT_DUST_20M_CONTRACT_REQUIRED")

def run_fixture(request):
    validate_request(request)
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.models import LimitOrderPartialFillModel, LatencyModel
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.core.data import Data
    from nautilus_trader.model.data import CustomData,DataType,BarType,BarSpecification
    from nautilus_trader.model.enums import AccountType,OmsType,OrderType,OrderSide,OrderStatus,TimeInForce,BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    from nautilus_trader.model.objects import Money
    from coinmaster.strategy.cm2_native import CM2Strategy,CM2StrategyConfig
    from coinmaster.strategy.cm2_policy import Config
    from coinmaster.strategy.cm2_execution import ExecutionLimits,order_plan
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic,zero_impact_venue_options
    from coinmaster.research.native_fixture import BybitTierMarginModule,instrument_quote
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.venues.marks import venue_mark,venue_mark_data_type
    from coinmaster.research.native_accounting import native_position_lifecycles
    from coinmaster.research.paired_observer import CommittedNativeObserver
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder,observed_neutral_strategy_type
    from types import SimpleNamespace

    out=Path(request["artifact_dir"]);out.mkdir(parents=True,exist_ok=True)
    if (out/"fixture-funding.sqlite").exists():raise ValueError("FRESH_DUST_JOURNAL_REQUIRED")
    profile=load_current_hl_diagnostic(Path(request["current_hl_execution_inputs"]))
    btc,sol=profile.instruments
    if sol.size_increment.as_decimal()!=D(".01") or sol.min_notional.as_decimal()!=10:
        raise ValueError("DUST_EXPECTED_PUBLIC_SOL_LOT_AND_FLOOR_REQUIRED")
    journal=NativeEventJournal(str(out/"fixture-funding.sqlite"))
    observer=CommittedNativeObserver(out/"fixture-coherent-native-events.jsonl.gz",SEED,(btc,sol),journal,END_NS)
    recorder=NativeMinuteRiskRecorder(out/"fixture-minute-native-risk.csv.gz",SEED,(btc,sol),
        dict(profile.selected_leverage),END_NS,margin_policy=profile.margin_policy(120_000_000_000))

    class Control(Data):
        def __init__(self,ns,row=None,capture=None):self.ns=ns;self.row=row;self.capture=capture
        @property
        def ts_event(self):return self.ns
        @property
        def ts_init(self):return self.ns
    control_type=DataType(Control)

    class PartialModel(ZeroImpactFullFillDiagnostic):
        def __init__(self):super().__init__();self.stock=LimitOrderPartialFillModel()
        def get_orderbook_for_fill_simulation(self,instrument,order,best_bid,best_ask):
            if order.order_type==OrderType.LIMIT:
                return self.stock.get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)
            return super().get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)

    class Driver(CM2Strategy):
        def __init__(self,config):
            super().__init__(config);self.plans={};self.samples={};self.ids={};self.events=[]
        def on_start(self):
            super().on_start();self.subscribe_data(control_type,client_id=ClientId("CM2_DUST"))
        def on_quote_tick(self,tick):
            # TESTONLY driver replaces policy dispatch; real native fills/ACKs retained.
            self._quotes[tick.instrument_id]=tick
        def actual(self):
            p=self._position(sol.id)
            return (p.quantity.as_decimal()*(D(1) if p.side.name=="LONG" else D(-1))) if p else D(0)
        def on_data(self,data):
            value=getattr(data,"data",data)
            if not isinstance(value,Control):return super().on_data(data)
            if value.capture:
                self.samples[value.capture]={"actual":str(self.actual()),"open_orders":len(self._orders(sol.id))}
            if value.row is None:return
            minute,tag,target,cap,partial=value.row
            quote=self._quotes[sol.id];actual=self.actual()
            price=(quote.ask_price if target>actual else quote.bid_price).as_decimal()
            pending=sum(((D(1) if o.side==OrderSide.BUY else D(-1))*o.leaves_qty.as_decimal()
                         for o in self._orders(sol.id)),D(0))
            plan=order_plan(actual=actual,target=target,pending=pending,unknown=False,price=price,
                step=sol.size_increment.as_decimal(),min_qty=sol.min_quantity.as_decimal() if sol.min_quantity else sol.size_increment.as_decimal(),
                max_child=cap*price,min_notional=sol.min_notional.as_decimal(),emergency=tag=="PREEXISTING_DUST_HOLD")
            self.plans[tag]={"actual_before":str(actual),"target":str(target),"price":str(price),
                             "cap":str(cap*price),"plan":asdict(plan),"test_only":True}
            if plan.action!="SUBMIT":return
            q=plan.signed_quantity;side=OrderSide.BUY if q>0 else OrderSide.SELL
            reducing=actual*q<0;quantity=sol.make_qty(abs(q))
            order=(self.order_factory.limit(instrument_id=sol.id,order_side=side,quantity=quantity,
                price=sol.make_price(price),time_in_force=TimeInForce.IOC,reduce_only=reducing,post_only=False)
                if partial else self._make_order(sol.id,side,quantity,reducing,price))
            oid=str(order.client_order_id);self.ids[tag]=oid
            self._owned[oid]={"instrument_id":sol.id,"client_order_id":order.client_order_id,
                "submit_ns":value.ns,"terminal":False,"acked":False}
            self._order_audit[oid]={"admission":{"intent":"FIXTURE_SENTINEL","parent":0,"test_only":True},
                "reason":tag,"action":"SOL","reduce_only":reducing}
            self.submit_order(order)
        def on_order_canceled(self,event):
            self.events.append({"kind":"CANCELED","client_order_id":str(event.client_order_id),"event_id":str(event.id),"ts_ns":str(event.ts_event)})
            super().on_order_canceled(event)

    modules=[BybitTierMarginModule((),tuple(profile.selected_leverage),120_000_000_000,
        margin_policy=profile.margin_policy(120_000_000_000),settlement_currency=btc.settlement_currency),observer]
    Observed=observed_neutral_strategy_type(Driver,recorder)
    engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"),run_analysis=False))
    strategy=None
    try:
        engine.add_venue(venue=btc.id.venue,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
            starting_balances=[Money(SEED,btc.settlement_currency)],base_currency=btc.settlement_currency,
            default_leverage=D(1),leverages=dict(profile.selected_leverage),modules=modules,bar_execution=False,
            use_message_queue=True,latency_model=LatencyModel(base_latency_nanos=0),
            **zero_impact_venue_options(PartialModel()))
        for instrument in (btc,sol):engine.add_instrument(instrument)
        bars={i.id:BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL) for i in (btc,sol)}
        strategy=Observed(CM2StrategyConfig(btc_id=btc.id,sol_id=sol.id,btc_bar_type=bars[btc.id],sol_bar_type=bars[sol.id],
            btc_mark_data_type=venue_mark_data_type(btc.id),sol_mark_data_type=venue_mark_data_type(sol.id),
            mark_client_id=ClientId("CM2_DUST"),policy=Config(),limits=ExecutionLimits(D(100000)),
            margin_policy=profile.margin_policy(120_000_000_000),trading_start_open_ns=START_NS,
            terminal_close_at_ns=END_NS,funding_reader=lambda iid:D(0),execution_policy_hash=FIXTURE_ID))
        engine.add_strategy(strategy)
        controls=[];marks=[];quotes=[];bundles=[]
        for row in SCRIPT:
            ns=START_NS+row[0]*MINUTE_NS
            controls.extend([CustomData(control_type,Control(ns+1,row=row)),
                CustomData(control_type,Control(ns+2)),CustomData(control_type,Control(ns+3,capture=row[1]))])
        for minute in range(1,21):
            ns=START_NS+minute*MINUTE_NS;sp=sol_price(minute)
            marks.extend([venue_mark(btc.id,D(1000),ns),venue_mark(sol.id,sp,ns)])
            quotes.extend([instrument_quote(btc,D(1000),D(1000),ns,size="100000"),
                           instrument_quote(sol,sp,sp,ns,size="100000")])
            def bar(p):return {k:str(p) for k in ("open","high","low","close")}
            bundles.append(SimpleNamespace(open_time_ms=(ns-MINUTE_NS)//1_000_000,btc_mark=bar(D(1000)),sol_mark=bar(sp)))
        observer.set_week(bundles);recorder.set_week(bundles)
        engine.add_data(controls,client_id=ClientId("CM2_DUST"),sort=False)
        engine.add_data(marks,client_id=ClientId("CM2_DUST"),sort=False)
        engine.add_data(quotes,sort=False);engine.sort_data();engine.run();engine.end()
        coherent=observer.finish_after_engine_end(END_NS);risk=recorder.close()
        fills=strategy.fill_audit;orders={str(o.client_order_id):o for o in engine.cache.orders()}
        samples=strategy.samples;plans=strategy.plans
        def quantity(tag):return D(samples[tag]["actual"])
        def bytag(tag):return [f for f in fills if f["client_order_id"]==strategy.ids.get(tag)]
        def partial_ok(tag,sign):
            o=orders[strategy.ids[tag]];fs=bytag(tag);held=quantity(tag)
            return (o.status==OrderStatus.CANCELED and D(0)<o.filled_qty.as_decimal()<EXPECTED_CHILD
                and o.quantity.as_decimal()==EXPECTED_CHILD and o.is_reduce_only
                and bool(fs) and sum((D(f["qty"]) for f in fs),D(0))==o.filled_qty.as_decimal()
                and held==sign*(OPEN_QTY-o.filled_qty.as_decimal()) and abs(held)*PRICE>=10
                and any(e["client_order_id"]==str(o.client_order_id) for e in strategy.events))
        checks={}
        for prefix,sign in (("LONG",D(1)),("SHORT",D(-1))):
            checks[prefix+"_native_open"]=quantity(prefix+"_OPEN")==sign*OPEN_QTY
            checks[prefix+"_planned_child_shrunk"]=D(plans[prefix+"_CHILD"]["plan"]["signed_quantity"])==-sign*EXPECTED_CHILD
            checks[prefix+"_actual_child_and_legal_remainder"]=(len(bytag(prefix+"_CHILD"))==1
                and D(bytag(prefix+"_CHILD")[0]["qty"])==EXPECTED_CHILD and quantity(prefix+"_CHILD")==sign*D(".08"))
            checks[prefix+"_actual_fullclose"]=quantity(prefix+"_CLOSE")==0 and bool(bytag(prefix+"_CLOSE"))
            checks[prefix+"_stock_partial_actual"]=partial_ok(prefix+"_PARTIAL_CHILD",sign)
            checks[prefix+"_partial_residual_fullclose"]=quantity(prefix+"_PARTIAL_CLOSE")==0 and bool(bytag(prefix+"_PARTIAL_CLOSE"))
        fees=sum((D(f["commission"]) for f in fills),D(0))
        expected_fees=sum((Money(D(f["qty"])*D(f["px"])*D(".000432"),btc.settlement_currency).as_decimal() for f in fills),D(0))
        cash=engine.cache.account_for_venue(btc.id.venue).balance_total(btc.settlement_currency).as_decimal()
        gross=-sum(((D(1) if f["order_side"]=="BUY" else D(-1))*D(f["qty"])*D(f["px"]) for f in fills),D(0))
        checks.update(preexisting_dust_HOLD_no_order=plans["PREEXISTING_DUST_HOLD"]["plan"]["reason"]=="VENUE_MIN_NOTIONAL_INCLUDING_REDUCE_ONLY"
            and "PREEXISTING_DUST_HOLD" not in strategy.ids and quantity("PREEXISTING_DUST_HOLD")==D(".08"),
            recovered_dust_native_fullclose=quantity("RECOVERED_DUST_CLOSE")==0,
            all_fill_ids_unique=len({f["trade_id"] for f in fills})==len(fills),
            native_terminal_flat=not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight(),
            exact_fixed_zero_gross=gross==0,exact_fees=fees==expected_fees,exact_cash=cash==SEED-expected_fees,
            coherent_native_observer=coherent["status"]=="PASS",minute_watermarks=risk["rows"]==20*3,
            zero_funding_no_coverage=not journal.funding_cash_audit())
        report={"fixture_id":FIXTURE_ID,"scope":SCOPE,"status":"PASS" if all(checks.values()) else "FAIL",
            "engine_constructors":1,"ranking_eligible":False,"checks":checks,"interval":{"start_ns":START_NS,"end_ns":END_NS},
            "fixture_timing_model":{"base_latency_ns":0,"scope":"SYNTHETIC_NOT_BENCHMARK"},
            "native_adapter":strategy.reporting_state(),"actual_native_fill_audit":fills,
            "native_orders":[{"id":oid,"status":o.status.name,"requested":str(o.quantity),"filled":str(o.filled_qty)} for oid,o in orders.items()],
            "native_lifecycles":native_position_lifecycles(engine.cache),"plans":plans,"snapshots":samples,
            "native_cancel_events":strategy.events,"coherent_native_observer":coherent,"minute_native_risk":risk,
            "manual_arithmetic":{"seed":str(SEED),"fixed_expected_gross":"0","observed_gross":str(gross),
                "native_fees":str(fees),"expected_fees":str(expected_fees),"native_cash":str(cash),"funding":"0"},
            "coverage_unknown":["ALPHA_AND_HEDGE_NOT_EXERCISED","FUNDING_NOT_EXERCISED","OS_RESTART_NOT_EXERCISED",
                "PRODUCTION_QUOTE_CALLBACK_ADMISSION_NOT_EXERCISED","FUTURE_PRICE_COLLAPSE_DUST_NOT_REPAIRED"]}
        (out/"engineering-report.json").write_text(json.dumps(report,sort_keys=True,default=str)+"\n")
        if not all(checks.values()):raise ValueError("CM2_DUST_ENGINEERING_CHECKS_FAILED")
        return report
    except BaseException as error:
        # No flatten/end/fill/finalization on failure; retain aborted-prefix facts.
        evidence={"status":"FAILED_PARTIAL_NATIVE_EVIDENCE","fixture_id":FIXTURE_ID,
            "checks":"UNKNOWN_ABORTED_PREFIX","error":{"type":type(error).__name__,"message":str(error)}}
        if strategy is not None:
            for key,reader in (("native_adapter",strategy.reporting_state),("plans",lambda:strategy.plans),("snapshots",lambda:strategy.samples)):
                try:evidence[key]=reader()
                except Exception as e:evidence[key]={"status":"UNKNOWN_EXPORT_FAILED","error":str(e)}
        try:
            with (out/"engineering-partial-failure.json").open("x") as f:json.dump(evidence,f,default=str)
        except Exception:pass
        raise
    finally:
        engine.dispose();observer.file.close();recorder.close_writers();journal.close()
