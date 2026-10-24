"""Genuine minute clock: CustomData funding precedes first quote, then native fills.

The observer never changes the data/command schedule; ON/OFF must match all
actual native parent/domain/orders/fills/fees/funding/cash through terminal flat.
"""
from decimal import Decimal as D
from types import SimpleNamespace
from pathlib import Path
import gzip,json,hashlib
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType,OmsType
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.objects import Money
from coinmaster.domain.wave_overlay import Candidate,Episode
from coinmaster.ledger.journal import NativeEventJournal
from coinmaster.research.native_fixture import SIM,BTC_PERP,SOL_PERP,perpetual,FundingInstruction,PerpetualFundingModule
from coinmaster.research.paired_observer import CommittedNativeObserver
from coinmaster.venues.marks import venue_mark
from test_native_paired_prefix import Probe,cfg,selected,prepare_day,marks
from test_native_episode_risk import tick,run_ticks

M=60_000_000_000


def fixture(tmp_path,enabled):
    journal=NativeEventJournal(str(tmp_path/'funding.sqlite'))
    funding=(FundingInstruction('btc-long-pay',BTC_PERP.id,D('.001'),8*M,D(100),'venue_mark_prior_minute'),
        FundingInstruction('sol-short-receive',SOL_PERP.id,D('.002'),8*M,D(100),'venue_mark_prior_minute'))
    modules=[PerpetualFundingModule(funding,journal)]
    observer=CommittedNativeObserver(tmp_path/'events.jsonl.gz',D(10000),(BTC_PERP,SOL_PERP),journal) if enabled else None
    if observer:
        observer.set_week([SimpleNamespace(open_time_ms=(i-1)*60000,btc_mark={'close':'100'},sol_mark={'close':'100'}) for i in range(1,13)])
        modules.append(observer)
    config=cfg(True,research_btc_real_u=True,research_btc_q_mode='CLEAN_Q',research_sol_off=True,
        research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,research_btc_split_discount=D('.005'))
    config=config.__replace__(candidate=Candidate(sol_overlay_enabled=False,btc_tp_fractions_initial_qty=(.2125,.2125,.575)))
    strategy=Probe(config)
    engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
    engine.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
        starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,
        default_leverage=D(1),liquidity_consumption=True,bar_execution=False,modules=modules)
    for inst in (BTC_PERP,SOL_PERP):
        engine.add_instrument(perpetual(inst.raw_symbol.value,inst.base_currency,str(inst.price_increment),
            str(inst.size_increment),str(inst.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')))
    engine.add_strategy(strategy)
    def minute(i,btc='100'):
        run_ticks(engine,[tick(BTC_PERP,i*M,btc),tick(SOL_PERP,i*M)])
    retained_proof=None
    try:
        minute(1);minute(2);prepare_day(strategy,2*M);marks(strategy,2*M)
        ep=strategy._domain.episode=Episode('funding-paired',1,10000,1,wave_levels=(0,0,.03),h=10000)
        intent=strategy._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
        strategy._submit_intent(intent,100,100,.01,0,ts_now=2*M)
        for i in (3,4,5):minute(i)
        selected(strategy,ns=5*M,a='.2')
        minute(6);minute(7)
        assert strategy._pair_qty(BTC_PERP.id)==D(50) and strategy._pair_qty(SOL_PERP.id)==D(10)
        before=observer._snapshot() if observer else None
        prior_epoch=observer.epoch if observer else None
        # This is the actual replay ordering that the earlier quote-first
        # fixture missed: modules settle CustomData T BEFORE first quote T.
        engine.add_data([venue_mark(BTC_PERP.id,D(100),8*M),venue_mark(SOL_PERP.id,D(100),8*M)],client_id=ClientId('FUNDING_MARKS'))
        engine.run(streaming=True);engine.clear_data()
        assert len(journal.funding_cash_audit())==2
        if observer:
            retained=observer.retained_prior
            assert retained is not None and retained.source_ns==7*M and retained.first_new_mutation_ns==8*M
            assert retained.state_epoch==prior_epoch==2
            assert retained.signature==before['signature']
            assert retained.state['positions']==before['positions']
            assert retained.state['cash']==before['cash']
            assert observer.last['cash']==before['cash']-D(3)
            retained_proof=dict(prior_source_ns=str(7*M),actual_prior_cash=str(before['cash']),
                actual_prior_position_sha256=before['position_hash'],actual_prior_epoch=prior_epoch,
                actual_post_funding_cash=str(observer.last['cash']),first_new_mutation_ns=str(8*M))
        # Same timestamp native BTC TP and SOL cap follow the funding mutation.
        minute(8,'101');minute(9,'101');minute(10,'101')
        strategy._begin_forced_close('TEST_NATIVE_TERMINAL')
        minute(11,'101');minute(12,'101');engine.end()
        report=observer.finish_after_engine_end(12*M) if observer else None
        assert strategy._pair is None and not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight()
        orders=[dict(id=str(o.client_order_id),type=o.order_type.name,side=o.side.name,quantity=str(o.quantity),
            filled=str(o.filled_qty),price=str(getattr(o,'price',None)),trigger=str(getattr(o,'trigger_price',None)),status=o.status.name,reduce_only=o.is_reduce_only) for o in engine.cache.orders()]
        trace=dict(parent='funding-paired',domain=dict(btc_open=ep.btc_open_qty,entry_exact=str(ep.btc_entry_qty_exact),
            target_lots=ep.btc_tp_target_lots,filled_lots=ep.btc_tp_filled_lots,consumed=sorted(ep.btc_filled_tps),sol_qty=ep.sol_qty),
            orders=orders,fills=strategy.fill_audit,paired=strategy._pair_report(),funding=journal.funding_cash_audit(),
            cash=str(engine.cache.account_for_venue(SIM).balance_total().as_decimal()))
        return trace,report,retained_proof
    finally:
        if observer:observer.close()
        engine.dispose();journal.close()


def test_funding_before_first_quote_retains_actual_prior_source_once_with_exact_parity(tmp_path):
    traces=[];report=None;retained=None
    for enabled in (False,True):
        folder=tmp_path/('on' if enabled else 'off');folder.mkdir()
        trace,report,retained=fixture(folder,enabled);traces.append(trace)
    assert traces[0]==traces[1]
    assert report['status']=='PASS',report
    assert report['native_funding_transitions']==2
    assert report['native_unique_fills']==len(traces[1]['fills'])
    assert report['settled_receipts']==11
    rows=[json.loads(x) for x in gzip.open(tmp_path/'on/events.jsonl.gz','rt')]
    receipt=next(x for x in rows if x['kind']=='SETTLED_PRE_NEXT_SOURCE_WATERMARK' and int(x['event_ns'])==7*M)
    assert receipt['cash']==retained['actual_prior_cash']
    assert receipt['native_positions_sha256']==retained['actual_prior_position_sha256']
    assert receipt['state_epoch']==retained['actual_prior_epoch']==2
    assert receipt['epoch']>=4  # Later receipt, explicitly earlier actual state epoch.
    assert receipt['prior_source_retention']['first_new_mutation_ns']==str(8*M)
    assert receipt['cash']!=retained['actual_post_funding_cash']
    assert any(x['kind']=='POST_FILL_COMMITTED_NATIVE' and int(x['event_ns'])==8*M for x in rows)
    quoted={x['event_ns'] for x in rows if x['kind']=='PREQUOTE_DIRECT_NATIVE'}
    settled={x['event_ns'] for x in rows if x['kind']=='SETTLED_PRE_NEXT_SOURCE_WATERMARK'}
    assert settled==quoted-{str(12*M)}
    proof=dict(status='PASS',clock='TRUE_M1_CUSTOM_MARK_FUNDING_BEFORE_FIRST_QUOTE_AND_SAME_T_NATIVE_FILL',
        retained_actual_snapshot=retained,late_receipt=receipt,native_orders=len(traces[1]['orders']),native_fills=len(traces[1]['fills']),
        native_funding=traces[1]['funding'],native_trace_sha256=hashlib.sha256(json.dumps(traces[1],sort_keys=True).encode()).hexdigest(),
        observer=report,parity='EXACT_PARENT_DOMAIN_NATIVE_ORDERS_FILLS_FEES_FUNDING_TERMINAL_CASH')
    (tmp_path/'funding-prior-watermark-proof.json').write_text(json.dumps(proof,indent=2))
