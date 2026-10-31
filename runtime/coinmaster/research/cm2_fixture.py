"""One-engine, nine-hour, test-only native CM2 connected execution fixture.

No engine/model/account is constructed on import. Synthetic signal events are
explicit execution test inputs, never economic evidence or a ranked backtest.
"""
from decimal import Decimal as D
import json
from pathlib import Path
from coinmaster.strategy.cm2_policy import Config,Features,HOUR_NS,MINUTE_NS
from coinmaster.research.cm2_fixture_validation import canceled_native_order,fixture_progress

FIXTURE_ID="cm2-connected-native-v1"
START_NS=1725148800000000000
END_NS=START_NS+9*HOUR_NS

def run_fixture(request):
    if request.get("fixture_id")!=FIXTURE_ID or request.get("start_ns")!=START_NS or request.get("end_ns")!=END_NS:
        raise ValueError("CM2_EXPLICIT_BOUNDED_FIXTURE_CONTRACT_REQUIRED")
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.backtest.models import LimitOrderPartialFillModel
    from nautilus_trader.core.data import Data
    from nautilus_trader.model.data import CustomData,DataType,BarType,BarSpecification
    from nautilus_trader.model.enums import AccountType,OmsType,OrderType,TimeInForce,BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    from nautilus_trader.model.objects import Money
    from coinmaster.strategy.cm2_native import CM2Strategy,CM2StrategyConfig,minute_turnover
    from coinmaster.strategy.cm2_execution import ExecutionLimits
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic,zero_impact_venue_options
    from coinmaster.research.native_fixture import (
        FundingInstruction,PerpetualFundingModule,BybitTierMarginModule,instrument_quote)
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.venues.marks import venue_mark,venue_mark_data_type
    from coinmaster.research.native_accounting import native_position_lifecycles
    from coinmaster.research.paired_observer import CommittedNativeObserver
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder,observed_neutral_strategy_type

    class FeatureEvent(Data):
        def __init__(self,value): self.value=value
        @property
        def ts_event(self): return self.value.available_ns
        @property
        def ts_init(self): return self.value.available_ns
    feature_type=DataType(FeatureEvent)
    class FixtureStrategy(CM2Strategy):
        used_partial_limit=False
        def on_start(self):
            super().on_start()
            self.subscribe_data(feature_type,client_id=ClientId("CM2_FIXTURE"))
        def on_data(self,data):
            value=getattr(data,"data",data)
            if isinstance(value,FeatureEvent):
                self.current_features=value.value
            else:
                super().on_data(data)
        def _make_order(self,iid,side,quantity,reducing,price):
            if iid==self.config.sol_id and not reducing and not self.used_partial_limit:
                self.used_partial_limit=True
                return self.order_factory.limit(instrument_id=iid,order_side=side,quantity=quantity,
                    price=self.cache.instrument(iid).make_price(price),
                    time_in_force=TimeInForce.IOC,reduce_only=False)
            return super()._make_order(iid,side,quantity,reducing,price)
    class FixturePartialModel(ZeroImpactFullFillDiagnostic):
        def __init__(self):
            super().__init__()
            self.stock_partial=LimitOrderPartialFillModel()
        def get_orderbook_for_fill_simulation(self,instrument,order,best_bid,best_ask):
            if order.order_type==OrderType.LIMIT:
                return self.stock_partial.get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)
            return super().get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)

    output=Path(request["artifact_dir"])
    output.mkdir(parents=True,exist_ok=True)
    journal_path=output/"fixture-funding.sqlite"
    if journal_path.exists():
        raise ValueError("FRESH_FIXTURE_JOURNAL_REQUIRED")
    profile=load_current_hl_diagnostic(Path(request["current_hl_execution_inputs"]))
    btc,sol=profile.instruments
    seed=D(10000)
    selected=dict(profile.selected_leverage)
    policy=profile.margin_policy(120_000_000_000)
    journal=NativeEventJournal(str(journal_path))
    # Fixed, explicitly synthetic funding instructions, settled by existing module.
    funding=(
        FundingInstruction("cm2-fixture-btc-a",btc.id,D(".0001"),START_NS+150*MINUTE_NS,D(1000)),
        FundingInstruction("cm2-fixture-sol-a",sol.id,D(".0001"),START_NS+150*MINUTE_NS,D(100)),
        FundingInstruction("cm2-fixture-btc-b",btc.id,D(".0001"),START_NS+450*MINUTE_NS,D(880)),
        FundingInstruction("cm2-fixture-sol-b",sol.id,D(".0001"),START_NS+450*MINUTE_NS,D(110)))
    observer=CommittedNativeObserver(output/"fixture-coherent-native-events.jsonl.gz",seed,(btc,sol),journal,END_NS)
    modules=[PerpetualFundingModule(funding,journal),
             BybitTierMarginModule((),tuple(profile.selected_leverage),120_000_000_000,
                                   margin_policy=profile.margin_policy(120_000_000_000),
                                   settlement_currency=btc.settlement_currency),observer]
    recorder=NativeMinuteRiskRecorder(output/"fixture-minute-native-risk.csv.gz",seed,(btc,sol),
        selected,END_NS,margin_policy=profile.margin_policy(120_000_000_000))
    ObservedFixture=observed_neutral_strategy_type(FixtureStrategy,recorder)
    # Exactly ONE physical native constructor in this fixture.
    engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"),run_analysis=False))
    try:
        engine.add_venue(venue=btc.id.venue,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
            starting_balances=[Money(seed,btc.settlement_currency)],base_currency=btc.settlement_currency,
            default_leverage=D(1),leverages=selected,modules=modules,bar_execution=False,
            **zero_impact_venue_options(FixturePartialModel()))
        for instrument in (btc,sol): engine.add_instrument(instrument)
        minute_types={i.id:BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
                      for i in (btc,sol)}
        def funding_reader(iid):
            return sum((D(row[5]) for row in journal.funding_cash_audit() if row[1]==str(iid)),D(0))
        strategy=ObservedFixture(CM2StrategyConfig(btc_id=btc.id,sol_id=sol.id,
            btc_bar_type=minute_types[btc.id],sol_bar_type=minute_types[sol.id],
            btc_mark_data_type=venue_mark_data_type(btc.id),sol_mark_data_type=venue_mark_data_type(sol.id),
            mark_client_id=ClientId("CM2_FIXTURE"),policy=Config(core=.5,hedge_fraction=.75),
            limits=ExecutionLimits(D("1e100")),margin_policy=policy,
            trading_start_open_ns=START_NS,terminal_close_at_ns=END_NS,
            funding_reader=funding_reader))
        engine.add_strategy(strategy)
        def fixed_features(hour):
            # All fixture values are available only when delivered by native bus.
            scripts={
                0:(1010,1005,990,-2,-.02),
                1:(1000,1010,990,-2,-.02),
                2:(1000,1010,990,-2,-.02),
                3:(1070,1080,990,-2,-.02),
                4:(950,1010,960,0,.01),
                5:(950,1010,960,2,.02),
                6:(880,970,870,2,.02),
                7:(880,970,870,2,.02),
                8:(980,990,870,0,-.01)}
            close,hi,lo,z,r=scripts[hour]
            t=START_NS+hour*HOUR_NS
            return Features(t,t,True,close=close,channel_high=hi,channel_low=lo,atr=10,
                beta=1,beta_guard=1,rho=1,residual_z=z,btc_return6=r,
                common_loss=.02,residual_loss=.001,hedge_valid=True)
        features_stream=[CustomData(feature_type,FeatureEvent(fixed_features(h))) for h in range(9)]
        marks=[];quotes=[];bundles=[]
        from types import SimpleNamespace
        for minute in range(1,541):
            ns=START_NS+minute*MINUTE_NS
            bp=D(1000) if minute<180 else D(1070) if minute<240 else D(950) if minute<360 else D(880) if minute<480 else D(980)
            sp=D(100) if minute<180 else D(90) if minute<240 else D(105) if minute<420 else D(110) if minute<480 else D(100)
            marks.extend((minute_turnover(btc.id,D("1e9"),ns),minute_turnover(sol.id,D("1e9"),ns),
                          venue_mark(btc.id,bp,ns),venue_mark(sol.id,sp,ns)))
            quotes.extend((instrument_quote(btc,bp,bp,ns,size="100000"),
                           instrument_quote(sol,sp,sp,ns,size="100000")))
            def bar(px): return {key:str(px) for key in ("open","high","low","close")}
            bundles.append(SimpleNamespace(open_time_ms=(ns-MINUTE_NS)//1_000_000,btc_mark=bar(bp),sol_mark=bar(sp)))
        observer.set_week(bundles)
        recorder.set_week(bundles)
        engine.add_data(features_stream,client_id=ClientId("CM2_FIXTURE"),sort=False)
        engine.add_data(marks,client_id=ClientId("CM2_FIXTURE"),sort=False)
        engine.add_data(quotes,sort=False)
        engine.sort_data()
        engine.run()
        engine.end()
        coherent=observer.finish_after_engine_end(END_NS)
        minute_summary=recorder.close()
        state=strategy.reporting_state()
        fills=state["fill_audit"]
        orders=engine.cache.orders()
        partial=[o for o in orders if D(0)<o.filled_qty.as_decimal()<o.quantity.as_decimal()]
        # Independent terminal double-entry arithmetic at flat:
        # long buy=-q*p, sell=+q*p; short reverses naturally. No trajectory simulator.
        gross=-sum(((D(1) if f["order_side"]=="BUY" else D(-1))*D(f["qty"])*D(f["px"]) for f in fills),D(0))
        expected_fees=sum((Money(D(f["qty"])*D(f["px"])*D(".000432"),btc.settlement_currency).as_decimal() for f in fills),D(0))
        native_fees=sum((D(f["commission"]) for f in fills),D(0))
        signed_funding=sum((D(row[5]) for row in journal.funding_cash_audit()),D(0))
        cash=engine.cache.account_for_venue(btc.id.venue).balance_total(btc.settlement_currency).as_decimal()
        expected_cash=seed+gross-expected_fees+signed_funding
        reasons={f["reason"] for f in fills}
        sides={f["order_side"] for f in fills if f["instrument"]==str(btc.id)}
        progress=fixture_progress(fills,strategy.cm2_audit)
        checks={"native_terminal_flat":not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight(),
                "native_partial_fill":bool(partial),
                "native_partial_terminal_canceled":any(canceled_native_order(o) for o in partial),
                "both_btc_sides":sides=={"BUY","SELL"},
                "actual_positive_harvest":progress["actual_long_positive_harvest"] and progress["actual_short_positive_harvest"],
                "actual_sol_fill":any(f["instrument"]==str(sol.id) for f in fills),
                "actual_funding":len(journal.funding_cash_audit())==4,
                "exact_independent_fees":native_fees==expected_fees,
                "exact_independent_terminal_cash":cash==expected_cash,
                "multiple_actual_parents":strategy.policy_state.parent>=2,
                "coherent_observer":coherent["status"]=="PASS",
                "first_fixed_funding":sum((D(row[5]) for row in journal.funding_cash_audit()[:2]),D(0))==D(-1),
                "minute_watermarks":minute_summary["rows"]==540*3,
                "ordinary_sol_first_staging":progress["confirmed_sol_before_long_harvest"],
                **{key:value for key,value in progress.items() if type(value) is bool}}
        report={"fixture_id":FIXTURE_ID,"execution_model_id":"CM2_FIXTURE_NATIVE_STOCK_LIMIT_PARTIAL_PLUS_QUALIFIED_MARKET_FULLFILL",
            "ranking_eligible":False,"engine_constructors":1,"interval":{"start_ns":START_NS,"end_ns":END_NS},
            "checks":checks,"actual_progress_evidence":progress,"status":"PASS" if all(checks.values()) else "FAIL",
            "manual_arithmetic":{"seed":str(seed),"gross_closed_fill_double_entry":str(gross),
                "expected_fees_from_fixed_rate":str(expected_fees),"native_fees":str(native_fees),"fee_rounding":"PER_FILL_NATIVE_COMMISSION_CURRENCY_MONEY_QUANTUM_NO_TOLERANCE_CHANGE",
                "signed_native_funding":str(signed_funding),"expected_cash":str(expected_cash),"native_cash":str(cash),
                "first_funding_expected":"-1","first_funding_actual":str(sum((D(row[5]) for row in journal.funding_cash_audit()[:2]),D(0)))},
            "native_partial_orders":[{"client_order_id":str(o.client_order_id),"status":str(o.status),
                "requested":str(o.quantity),"filled":str(o.filled_qty)} for o in partial],
            "actual_native_fill_audit":fills,"native_adapter":state,"coherent_native_observer":coherent,
            "minute_native_risk":minute_summary,"native_lifecycles":native_position_lifecycles(engine.cache),
            "coverage_unknown":["CANCEL_FILL_RACE_NATIVE_NOT_FORCED","DENIED_UNKNOWN_ACK_NATIVE_NOT_FORCED",
                                "RESTART_REPLAY_NATIVE_NOT_TESTED"],
            "coverage_pure":["PENDING_CANCEL_RECONCILE","UNKNOWN_ACK_FREEZE","DUPLICATE_HOUR_EVENT",
                             "NEXT_QUOTE_AVAILABILITY","BOTH_FILL_ORDER_FACTOR_SAFETY"]}
        (output/"engineering-report.json").write_text(json.dumps(report,sort_keys=True,default=str)+"\n")
        if not all(checks.values()): raise ValueError("CM2_NATIVE_ENGINEERING_CHECKS_FAILED")
        return report
    finally:
        engine.dispose()
        observer.file.close()
        recorder.close_writers()
        journal.close()
