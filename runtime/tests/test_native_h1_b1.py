from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from nautilus_trader.model.data import Bar, BarType, BarSpecification
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType, OrderSide, TimeInForce
from coinmaster.domain.wave_overlay import Episode, Candidate
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from test_wave_native_integration import lifecycle_config, native_engine
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_native_btc_sizing import prepare_day


def confirmation_types():
    return tuple(BarType.new_composite(i.id, BarSpecification(15 if m == 15 else 1, BarAggregation.MINUTE if m == 15 else BarAggregation.HOUR, PriceType.LAST),
                 AggregationSource.INTERNAL, 1, BarAggregation.MINUTE, AggregationSource.EXTERNAL)
                 for i in (BTC_PERP, SOL_PERP) for m in (15, 60))

def config(mode, **kw):
    return lifecycle_config(research_h1_b1=mode, research_confirmation_bars=confirmation_types(), **kw)

def bar(kind, ts, close, high=None, low=None):
    i = BTC_PERP if kind.instrument_id == BTC_PERP.id else SOL_PERP
    return Bar(kind, i.make_price(D(str(close))), i.make_price(D(str(high or close))),
               i.make_price(D(str(low or close))), i.make_price(D(str(close))), i.make_qty(0), ts, ts)

def offer_confirmation(strategy, key, token):
    strategy._confirmation_events[key]=token
    strategy._h1_confirmation_receipts[key]=(token[0],strategy._h1_sol_quote_sequence+1)

@pytest.mark.parametrize('mode', ['h1','b1'])
def test_selector_default_off_and_exclusive(mode):
    assert lifecycle_config().research_h1_b1 is None
    with pytest.raises(ValueError, match='SEPARATE_V3'):
        NativeProbe(config(mode, research_v3_risk='r2'))

@pytest.mark.parametrize('side', [1,-1])
def test_closed_confirmation_or_strictly_after_arm_no_ema_gate(side):
    s = NativeProbe(config('b1'))
    engine=native_engine(s)
    run_ticks(engine,[tick(BTC_PERP,4)])
    s._b1_candidate = dict(daily_ns=1, armed_ns=3, side=side, confirmed_ns=None)
    kind=s.config.research_confirmation_bars[0]
    s.on_bar(bar(kind, 2, 100, 101, 99))
    s.on_bar(bar(kind, 3, 102 if side==1 else 98))
    assert s._b1_candidate['confirmed_ns'] is None
    s.on_bar(bar(kind, 4, 103 if side==1 else 97))
    assert s._b1_candidate['confirmed_ns']==4
    s.on_bar(bar(kind, 4, 1000))
    assert s._confirmation_state[kind]['count']==3
    engine.dispose()


def setup_h1():
    s=NativeProbe(config('h1',candidate=Candidate(sol_overlay_enabled=False),max_mark_age_ns=100))
    engine=native_engine(s)
    run_ticks(engine,[tick(BTC_PERP,1)])
    s.submit_order(s.order_factory.market(BTC_PERP.id,OrderSide.BUY,BTC_PERP.make_qty(D('100')),time_in_force=TimeInForce.IOC))
    run_ticks(engine,[tick(BTC_PERP,2)])
    prepare_day(s,3)
    s._domain.episode=Episode('h1',1,10000,1,btc_entry_vwap=100,btc_initial_qty=100,btc_open_qty=100,h=10000,wave_levels=(.01,.02,.03))
    marks(s,3,'97','100')
    s._h1_check(3)
    return s,engine


def test_native_h1_stage1_partial_stage2_equal_actual_quantity_after_new_tp_confirmation_and_flat():
    s,e=setup_h1()
    try:
        offer_confirmation(s, (SOL_PERP.id,-1), (4,-1))
        run_ticks(e,[tick(SOL_PERP,4,size='10')])
        assert s._h1_cycle['first_qty']==D('10')
        assert s._domain.episode.sol_qty==10
        run_ticks(e,[tick(SOL_PERP,5)])
        assert s._h1_cycle['first_terminal']
        assert not s._h1_cycle['stage2_attempted']
        ep=s._domain.episode
        intent=s._domain._intent(ep,'BTC_REDUCE',-1,0,quantity=21.25)
        s._submit_intent(intent,103,103,.01,2,ts_now=6)
        run_ticks(e,[tick(BTC_PERP,6,'103')])
        assert s._h1_cycle['tp_ns']==6
        offer_confirmation(s, (SOL_PERP.id,-1), (6,-1))
        run_ticks(e,[tick(SOL_PERP,7)])
        assert not s._h1_cycle['stage2_attempted']
        offer_confirmation(s, (SOL_PERP.id,-1), (8,-1))
        run_ticks(e,[tick(SOL_PERP,8)])
        assert s._h1_cycle['stage2_attempted']
        assert ep.sol_qty==20
        run_ticks(e,[tick(SOL_PERP,9)])
        assert ep.sol_qty==20
        assert len([r for r in s.h1_b1_audit if r['event']=='H1_STAGE2'])==1
        final=s._domain._intent(ep,'BTC_REDUCE',-1,2,quantity=78.75)
        s._submit_intent(final,100,100,.01,2,ts_now=10)
        run_ticks(e,[tick(BTC_PERP,10),tick(SOL_PERP,11),tick(SOL_PERP,12),tick(SOL_PERP,13)])
        assert not e.cache.positions_open()
        assert not s._pending_by_order
        assert s._h1_cycle['closed']
        assert not s._mandatory_sol_exit
        assert s._domain.episode is ep and ep.btc_open_qty==0 and ep.sol_qty==0
        prepare_day(s,14,1)
        WaveOverlayStrategy._advance_current_day(s)
        assert s._domain.episode is ep
        assert not any(i.action=='BTC_ENTRY' for i,_,_ in s._queued_intents)
    finally:
        e.end();e.dispose()


def test_h1_unknown_ack_blocks_stage_two_and_b1_flat():
    s,e=setup_h1()
    try:
        ep=s._domain.episode
        intent=s._domain._intent(ep,'SOL_ADD',-1,0,quantity=10,reason='H1_STAGE1')
        s._h1_cycle.update(stage1_attempted=True,first_fill_ns=4,first_qty=D(10),tp_ns=5)
        s._pending_by_order['UNKNOWN_ACK']=intent
        offer_confirmation(s, (SOL_PERP.id,-1), (6,-1))
        s._h1_check(6)
        assert not s._h1_cycle['first_terminal']
        assert not s._h1_cycle['stage2_attempted']
        assert not s._b1_flat_resolved()
    finally:
        e.end();e.dispose()


def test_b1_candidate_daily_expiry_no_same_price_daily_ema_check():
    s=NativeProbe(config('b1'));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        prepare_day(s,2,-1)
        assert not s._b1_gate_daily()
        s._b1_candidate['confirmed_ns']=3
        prepare_day(s,4,-1)
        assert not s._b1_gate_daily()
        assert s._b1_candidate['confirmed_ns'] is None
        assert s._b1_candidate['side']==-1
    finally:
        e.end();e.dispose()


def test_pinned_native_composite_closed_real_minute_ohlc():
    class Probe(NativeProbe):
        def __init__(self,c):
            super().__init__(c);self.received=[]
        def on_bar(self,b):
            if any(b.bar_type == k.standard() or b.bar_type == k for k in self.config.research_confirmation_bars):
                self.received.append(b)
            super().on_bar(b)
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.cache.config import CacheConfig
    from nautilus_trader.data.config import DataEngineConfig
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.objects import Money
    from coinmaster.research.native_fixture import SIM
    s=Probe(config('b1',max_mark_age_ns=100))
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'), cache=CacheConfig(bar_capacity=128),
        data_engine=DataEngineConfig(time_bars_build_with_no_updates=False)))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
        starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,bar_execution=False)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    base=1725148800 * 1_000_000_000
    minute=BarType(BTC_PERP.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
    try:
        rows=[bar(minute,base+m*60_000_000_000,100+m,101+m,99+m) for m in range(1,122)]
        e.add_data(rows);e.run(streaming=True);e.clear_data()
        received=[b for b in s.received if b.bar_type.spec.aggregation==BarAggregation.MINUTE]
        assert len(received)==8
        assert received[0].ts_event==base+15*60_000_000_000
        assert float(received[0].close)==115
        assert float(received[0].high)==116
        assert float(received[0].low)==100
        assert float(received[1].close)==130
        hourly=[b for b in s.received if b.bar_type.spec.aggregation==BarAggregation.HOUR]
        assert len(hourly)==2
        assert hourly[0].ts_event==base+60*60_000_000_000
        assert float(hourly[0].close)==160 and float(hourly[0].high)==161
        assert float(hourly[1].close)==220
        assert all(b.ts_init==b.ts_event for b in s.received)
        assert not e.cache.positions_open() and not e.cache.orders_open()
    finally:
        e.end();e.dispose()

@pytest.mark.parametrize('reverse_order',[False,True])
def test_true_or_conflicting_same_boundary_tf_and_recovery_exit_priority(reverse_order):
    s,e=setup_h1()
    try:
        kinds=s.config.research_confirmation_bars
        run_ticks(e,[tick(SOL_PERP,3)])
        for k in kinds[2:]:
            s.on_bar(bar(k,3,100,101,99))
        run_ticks(e,[tick(SOL_PERP,4)])
        pair=[bar(kinds[2],4,98),bar(kinds[3],4,102)]
        for b in pair[::-1] if reverse_order else pair:
            s.on_bar(b)
        run_ticks(e,[tick(SOL_PERP,5)])
        assert s._domain.episode.sol_qty==48.5
        assert len([r for r in s.h1_b1_audit if r['event']=='H1_STAGE1'])==1
        cycle=s._h1_cycle
        cycle['tp_ns']=6
        marks(s,7,'99.5','100')
        offer_confirmation(s, (SOL_PERP.id,-1), (7,-1))
        offer_confirmation(s, (SOL_PERP.id,'1h',1), (7,1))
        run_ticks(e,[tick(SOL_PERP,7),tick(SOL_PERP,8),tick(SOL_PERP,9)])
        assert not cycle['stage2_attempted']
        assert cycle['closed']
        assert any(r['event']=='H1_EXIT' and r['reason']=='H1_RECOVERY' for r in s.h1_b1_audit)
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("reverse_order",[False,True])
def test_b1_native_entry_wait_actual_confirmation_fresh_quote_and_direction_sizing(monkeypatch,reverse_order):
    from coinmaster.domain import wave_overlay
    monkeypatch.setattr(wave_overlay,'completed_wave_levels',lambda *args:(.01,.02,.03))
    class Probe(NativeProbe):
        _advance_current_day=WaveOverlayStrategy._advance_current_day
    s=Probe(config('b1',max_mark_age_ns=100));e=native_engine(s)
    try:
        run_ticks(e,[tick(BTC_PERP,1)])
        prepare_day(s,2,1)
        s._advance_current_day()
        assert s._domain.episode is None and s._b1_candidate
        k=s.config.research_confirmation_bars[0]
        run_ticks(e,[tick(BTC_PERP,2)])
        s.on_bar(bar(k,2,100,101,99))
        k1h=s.config.research_confirmation_bars[1]
        s.on_bar(bar(k1h,2,100,101,99))
        run_ticks(e,[tick(BTC_PERP,3)])
        conflicting=[bar(k,3,102),bar(k1h,3,98)]
        for b in conflicting[::-1] if reverse_order else conflicting:
            s.on_bar(b)
        marks(s,4)
        run_ticks(e,[tick(BTC_PERP,4),tick(BTC_PERP,5)])
        ep=s._domain.episode
        assert ep.btc_sizing_multiplier==5.5
        assert ep.btc_entry_vwap==100
        assert ep.btc_reference_qty==550
        assert 0 < ep.btc_initial_qty <= ep.btc_reference_qty
        assert len([r for r in s.h1_b1_audit if r['event']=='B1_CONFIRMED_ENTRY'])==1
    finally:
        e.end();e.dispose()


def test_h1_old_confirm_disarm_and_fresh_recovery_required():
    s,e=setup_h1()
    try:
        offer_confirmation(s, (SOL_PERP.id,-1), (3,-1))
        run_ticks(e,[tick(SOL_PERP,4)])
        assert not s._h1_cycle['stage1_attempted']
        marks(s,5,'99','100');s._h1_check(5)
        assert s._h1_cycle is None
        marks(s,6,'97','100');s._h1_check(6)
        assert s._h1_cycle['armed_ns']==6
        offer_confirmation(s, (SOL_PERP.id,-1), (7,-1))
        run_ticks(e,[tick(SOL_PERP,7)])
        offer_confirmation(s, (SOL_PERP.id,'1h',1), (8,1))
        stale_ns=60_000_000_009
        marks(s,stale_ns,'99.5','100');run_ticks(e,[tick(SOL_PERP,stale_ns)])
        assert not s._h1_cycle['closed']
    finally:
        e.end();e.dispose()


def test_h1_actual_source_timer_quote_chronology_two_native_stages(tmp_path):
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.cache.config import CacheConfig
    from nautilus_trader.data.config import DataEngineConfig
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.objects import Money
    from coinmaster.research.native_fixture import SIM
    from coinmaster.venues.marks import venue_mark
    from nautilus_trader.model.identifiers import ClientId
    import json
    base=1725148800*1_000_000_000; cadence=60_000_000_000
    class Probe(NativeProbe):
        def __init__(self,c):
            super().__init__(c);self.timeline=[];self.started=False
        def on_bar(self,b):
            if b.bar_type.instrument_id==SOL_PERP.id:
                self.timeline.append(dict(event='BAR',close_ns=b.ts_event,receipt_ns=self.clock.timestamp_ns(),quote_sequence=getattr(self,'_h1_sol_quote_sequence',0)))
            super().on_bar(b)
        def on_quote_tick(self,q):
            if not self.started and q.instrument_id==BTC_PERP.id:
                self.started=True
                prepare_day(self,q.ts_event,1)
                ep=self._domain.episode=Episode('pipeline',1,10000,1,wave_levels=(.01,.1,.2))
                intent=self._domain._intent(ep,'BTC_ENTRY',1,None,requested_notional=10000)
                self._queued_intents.append((intent,.01,2))
                self._queued_intent_ready_ns[intent.id]=q.ts_event
            if q.instrument_id==SOL_PERP.id:
                self.timeline.append(dict(event='SOL_QUOTE',quote_ns=q.ts_event))
            super().on_quote_tick(q)
        def on_order_filled(self,event):
            self.timeline.append(dict(event='FILL',instrument=str(event.instrument_id),timestamp_ns=event.ts_event,quantity=str(event.last_qty)))
            super().on_order_filled(event)
    s=Probe(config('h1',max_mark_age_ns=cadence,candidate=Candidate(sol_overlay_enabled=False)))
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'),cache=CacheConfig(bar_capacity=128),data_engine=DataEngineConfig(time_bars_build_with_no_updates=False)))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,bar_execution=False)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    source=[];mark_rows=[];quotes=[]
    for m in range(1,122):
        ns=base+m*cadence;bp=D('100') if m<=2 else D('97') if m<=35 else D('103')
        sp=D('100') if m<=15 else D('100')-D(m-15)/10
        for i,p in ((BTC_PERP,bp),(SOL_PERP,sp)):
            k=BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
            source.append(bar(k,ns,p,p,p))
            mark_rows.append(venue_mark(i.id,p,ns))
            quotes.append(tick(i,ns,str(p)))
    try:
        e.add_data(source,sort=False);e.add_data(mark_rows,client_id=ClientId('TEST_MARKS'),sort=False);e.add_data(quotes,sort=False);e.sort_data();e.run(streaming=True);e.clear_data()
        proof={'timeline':s.timeline,'audit':s.h1_b1_audit}
        (tmp_path/'h1-native-routing-proof.json').write_text(json.dumps(proof,indent=2))
        # Pin causal ordering: quote at minute30 precedes closed30m bar receipt.
        close=base+30*cadence
        qidx=next(i for i,r in enumerate(s.timeline) if r['event']=='SOL_QUOTE' and r['quote_ns']==close)
        bidx=next(i for i,r in enumerate(s.timeline) if r['event']=='BAR' and r['close_ns']==close)
        assert qidx<bidx
        stages=[r for r in s.h1_b1_audit if r['event'] in {'H1_STAGE1','H1_STAGE2'}]
        assert [r['event'] for r in stages]==['H1_STAGE1','H1_STAGE2'], proof['audit']
        assert stages[0]['confirmation_ns']==close and stages[0]['timestamp_ns']==close+cadence
        assert stages[1]['confirmation_ns']==base+45*cadence and stages[1]['timestamp_ns']==base+46*cadence
        fills=[r for r in s.h1_b1_audit if r['event']=='H1_NATIVE_FILL' and r['action']=='SOL_ADD']
        assert len(fills)==2 and fills[0]['quantity']==fills[1]['quantity']
        assert s._h1_cycle['tp_ns']>s._h1_cycle['first_fill_ns']
        assert all(r['timestamp_ns']>r['confirmation_ns'] for r in stages)
        # Retained receipt next to ordinary implementation logs, no economic engine.
        from pathlib import Path
        out=Path('reports/h1-b1-113/implementation/h1-native-routing-proof.json')
        out.write_text(json.dumps(proof,indent=2)+'\n')
    finally:
        e.end();e.dispose()


def test_b1_actual_source_timer_quote_entry(monkeypatch):
    from coinmaster.domain import wave_overlay
    monkeypatch.setattr(wave_overlay,'completed_wave_levels',lambda *a:(.05,.1,.2))
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.cache.config import CacheConfig
    from nautilus_trader.data.config import DataEngineConfig
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.objects import Money
    from coinmaster.research.native_fixture import SIM
    from coinmaster.venues.marks import venue_mark
    from nautilus_trader.model.identifiers import ClientId
    import json
    from pathlib import Path
    base=1725148800*1_000_000_000;cadence=60_000_000_000
    class Probe(NativeProbe):
        _advance_current_day=WaveOverlayStrategy._advance_current_day
        def __init__(self,c):
            super().__init__(c);self.timeline=[];self.started=False
        def on_bar(self,b):
            if b.bar_type.instrument_id==BTC_PERP.id:
                self.timeline.append(dict(event='BAR',close_ns=b.ts_event,receipt_ns=self.clock.timestamp_ns()))
            super().on_bar(b)
        def on_quote_tick(self,q):
            if q.instrument_id==BTC_PERP.id:
                self.timeline.append(dict(event='BTC_QUOTE',quote_ns=q.ts_event))
                if not self.started:
                    self.started=True;prepare_day(self,q.ts_event,1);self._advance_current_day()
            super().on_quote_tick(q)
        def on_order_filled(self,event):
            self.timeline.append(dict(event='FILL',instrument=str(event.instrument_id),timestamp_ns=event.ts_event,quantity=str(event.last_qty)))
            super().on_order_filled(event)
    s=Probe(config('b1',max_mark_age_ns=cadence))
    e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'),cache=CacheConfig(bar_capacity=128),data_engine=DataEngineConfig(time_bars_build_with_no_updates=False)))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,bar_execution=False)
    e.add_instrument(BTC_PERP);e.add_instrument(SOL_PERP);e.add_strategy(s)
    source=[];mark_rows=[];quotes=[]
    for m in range(1,122):
        ns=base+m*cadence;bp=D('100') if m<=15 else D('100')+D(min(m-15,15))/10
        for i,p in ((BTC_PERP,bp),(SOL_PERP,D('100'))):
            k=BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL)
            source.append(bar(k,ns,p,p,p));mark_rows.append(venue_mark(i.id,p,ns));quotes.append(tick(i,ns,str(p)))
    try:
        e.add_data(source,sort=False);e.add_data(mark_rows,client_id=ClientId('TEST_MARKS'),sort=False);e.add_data(quotes,sort=False);e.sort_data();e.run(streaming=True);e.clear_data()
        close=base+30*cadence
        qidx=next(i for i,r in enumerate(s.timeline) if r['event']=='BTC_QUOTE' and r['quote_ns']==close)
        bidx=next(i for i,r in enumerate(s.timeline) if r['event']=='BAR' and r['close_ns']==close)
        assert qidx<bidx
        entries=[r for r in s.h1_b1_audit if r['event']=='B1_CONFIRMED_ENTRY']
        assert len(entries)==1
        assert entries[0]['confirmed_ns']==close and entries[0]['quote_ns']==close+cadence
        fills=[r for r in s.timeline if r['event']=='FILL' and r['instrument']==str(BTC_PERP.id)]
        assert fills and fills[0]['timestamp_ns']==close+2*cadence
        assert s._domain.episode.btc_entry_vwap==101.5
        assert s._domain.episode.btc_sizing_multiplier==5.5
        proof={'timeline':s.timeline,'audit':s.h1_b1_audit,'native_btc_entry_vwap':s._domain.episode.btc_entry_vwap}
        Path('reports/h1-b1-113/implementation/b1-native-routing-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    finally:
        e.end();e.dispose()

@pytest.mark.parametrize('age,first_quote,expected',[(0,True,True),(60_000_000_000,True,True),(60_000_000_001,True,False),(0,False,False),(-1,True,False)])
def test_h1_receipt_first_current_quote_and_age_bound(age,first_quote,expected):
    s=NativeProbe(config('h1'))
    key=(SOL_PERP.id,-1);close=100_000_000_000
    s._h1_sol_quote_sequence=2
    s._h1_confirmation_receipts[key]=(close,2 if first_quote else 1)
    assert s._h1_confirmation_is_current(key,(close,-1),close+age)==expected


@pytest.mark.parametrize("close,received,quoted,sequence,eligible,expected", [
    (100,99,101,2,2,False), (100,102,101,2,2,False),
    (100,100,100,2,2,True), (100,100,101,3,2,False),
    (100,100,60_000_000_100,2,2,True), (100,100,60_000_000_101,2,2,False),
])
def test_shared_receipt_no_future_close_no_backward_quote_no_second_quote(close,received,quoted,sequence,eligible,expected):
    assert WaveOverlayStrategy._confirmation_receipt_is_current(close,(received,eligible),sequence,quoted)==expected
