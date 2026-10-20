import csv
import gzip
import json
import pytest
from decimal import Decimal as D

from coinmaster.research.minute_risk import DrawdownTracker
from coinmaster.research.native_baseline import DAY_MS, MINUTE_MS, run_native_diagnostic
from test_native_baseline import write_streaming_fixture


def test_drawdown_tracker_ranks_distinct_excursions_and_seed_loss():
    curve=DrawdownTracker('10000')
    for t,v in enumerate(('10000','15000','7000','8000','6500','16000','20000','15000','21000','18000')):
        curve.add(t,v)
    result=curve.summary()
    assert result['minimum']['equity']=='6500'
    assert D(result['maximum_loss_below_seed_percent'])==D('35')
    first,second,third=result['top3_distinct_excursions']
    assert first['peak']['timestamp_ns']=='1' and first['trough']['timestamp_ns']=='4' and first['recovery']['timestamp_ns']=='5'
    assert second['peak']['timestamp_ns']=='6' and third['recovery'] is None
    assert len(curve.top)==3


@pytest.mark.parametrize("long", [True, False])
def test_native_observer_preserves_fills_account_and_avoids_preentry_extrema(tmp_path,monkeypatch,long):
    start,end=write_streaming_fixture(tmp_path,trading_days=1)
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    from nautilus_trader.model.enums import OrderSide
    original=WaveOverlayStrategy.on_quote_tick
    def scripted_quote(self,tick):
        original(self,tick)
        if tick.instrument_id!=self.config.btc_id:
            return
        minute=(tick.ts_event//1_000_000-start)//MINUTE_MS
        if minute in (1,2):
            instrument=self.cache.instrument(tick.instrument_id)
            order=self.order_factory.market(tick.instrument_id,OrderSide.BUY if (minute==1)==long else OrderSide.SELL,instrument.make_qty(D('1')))
            self.submit_order(order)
    monkeypatch.setattr(WaveOverlayStrategy,'on_quote_tick',scripted_quote)
    from coinmaster.research import native_baseline
    from coinmaster.research.native_fixture import BTC_PERP, FundingInstruction
    monkeypatch.setattr(native_baseline,'funding_with_prior_minute_marks',lambda *_: (FundingInstruction('observer-funding',BTC_PERP.id,D('0.01'),(start+2*MINUTE_MS)*1_000_000,D('100'),'synthetic_mid',True),))
    common=dict(include_funding=True,trading_start_ms=start,trading_end_ms=end,warmup_start_ms=0,weekly_batch_minutes=720)
    plain=run_native_diagnostic(tmp_path,artifact_label='plain',artifact_dir=tmp_path/'plain',**common)
    observed=run_native_diagnostic(tmp_path,artifact_label='observed',artifact_dir=tmp_path/'observed',observe_minute_risk=True,**common)
    for key in ('terminal_total','native_fees','fills','cash_account_series','interval_cash_account_series','liquidation_count','terminal_open_positions','config_hash','policy_hash'):
        assert plain[key]==observed[key],key
    assert observed['fills']==2
    # Strategy identity must preserve actual native IDs and order chronology.
    for kind in ('fills','orders'):
        a=next((tmp_path/'plain').glob(f'*-{kind}.csv')).read_text()
        b=next((tmp_path/'observed').glob(f'*-{kind}.csv')).read_text()
        # Native engine init_id is intentionally not part of identity parity.
        arows=list(csv.DictReader(a.splitlines()));brows=list(csv.DictReader(b.splitlines()))
        for records in (arows,brows):
            for row in records:row.pop('init_id',None)
        assert arows==brows
    trace=list(csv.DictReader(gzip.open(tmp_path/'observed'/'minute-native-risk.csv.gz','rt')))
    assert len(trace)==4320
    first_pre,first_post,next_pre=trace[0],trace[2],trace[3]
    assert first_pre['native_positions_and_mark_ohlc_json']=='[]'
    assert D(first_pre['conditional_adverse_equity'])==D('10000')
    assert len(json.loads(first_post['native_positions_and_mark_ohlc_json']))==1
    assert first_post['conditional_adverse_equity']=='NOT_APPLICABLE_POST_CLOSE_EXPOSURE'
    assert len(json.loads(next_pre['native_positions_and_mark_ohlc_json']))==1
    assert D(next_pre['conditional_adverse_equity'])<D(next_pre['paired_close_equity'])
    assert (D(next_pre['cash'])<D(first_post['cash']))==long  # native debit or credit
    assert observed['funding']['count']==plain['funding']['count']==1
    detail=json.loads(next_pre['native_positions_and_mark_ohlc_json'])[0]
    assert D(next_pre['conditional_adverse_equity'])==min(D(next_pre['cash']),D(first_post['cash']))+min(D(detail['low_native_pnl']),D(detail['high_native_pnl']))
    assert D(next_pre['conditional_high_mark_mm_upper'])>=D(next_pre['native_maintenance_margin'])
    assert observed['minute_risk_observations']['curves']['pre_quote_paired_close']['samples']==1441


def test_terminal_settlement_is_excluded_from_interval_native_drawdown(tmp_path,monkeypatch):
    start,end=write_streaming_fixture(tmp_path,trading_days=1)
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    from nautilus_trader.model.enums import OrderSide
    original=WaveOverlayStrategy.on_quote_tick
    def scripted_open(self,tick):
        original(self,tick)
        if tick.instrument_id==self.config.btc_id and tick.ts_event==(start+MINUTE_MS)*1_000_000:
            instrument=self.cache.instrument(tick.instrument_id)
            self.submit_order(self.order_factory.market(tick.instrument_id,OrderSide.BUY,instrument.make_qty(D('1'))))
    monkeypatch.setattr(WaveOverlayStrategy,'on_quote_tick',scripted_open)
    result=run_native_diagnostic(tmp_path,trading_start_ms=start,trading_end_ms=end,warmup_start_ms=0,artifact_dir=tmp_path/'observed',observe_minute_risk=True)
    assert result['fills']==2 and result['terminal_open_positions']==0
    summary=result['minute_risk_observations']
    trace=list(csv.DictReader(gzip.open(tmp_path/'observed'/'minute-native-risk.csv.gz','rt')))
    pre,btc_post,sol_post=trace[-3:]
    assert pre['phase']=='pre_quote_paired_close'
    assert len(json.loads(pre['native_positions_and_mark_ohlc_json']))==1
    assert btc_post['phase']=='post_boundary_post_btc_quote_paired_close'
    assert sol_post['phase']=='post_boundary_post_quote_paired_close'
    assert sol_post['native_positions_and_mark_ohlc_json']=='[]'
    assert D(sol_post['paired_close_equity'])<D(pre['paired_close_equity']) # exit fee is post-boundary
    assert len(summary['post_boundary_settlement_excluded_from_interval_curves'])==2
    assert summary['curves']['pre_quote_paired_close']['samples']==1441
    assert summary['curves']['post_btc_quote_paired_close']['samples']==1440
    assert summary['curves']['post_quote_paired_close']['samples']==1440
    assert summary['curves']['all_native_close_samples']['samples']==4319
    expected_min=min(D(row['paired_close_equity']) for row in trace if not row['phase'].startswith('post_boundary_'))
    assert D(summary['curves']['all_native_close_samples']['minimum']['equity'])==expected_min
    assert D(summary['curves']['all_native_close_samples']['minimum']['equity'])>D(sol_post['paired_close_equity'])
    assert summary['rows']==4320
    bound = summary["conditional_upper_to_later_lower_bound"]
    assert bound["samples"] == 1440
    assert bound["same_bar_extrema_order_assumed"] is False
    assert int(bound["maximum"]["trough"]["timestamp_ns"]) <= int(summary["end_exclusive_ns"])
    assert bound["maximum"]["peak"]["timestamp_ns"] is not None

def test_off_settled_receipt_matches_after_run_and_rejects_intervening_fill(tmp_path):
    from types import SimpleNamespace
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder, observed_strategy_type
    from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
    from test_native_episode_risk import NativeProbe, tick, run_ticks
    from test_wave_native_integration import lifecycle_config, native_engine
    from nautilus_trader.model.enums import OrderSide
    class Probe(NativeProbe):
        def on_quote_tick(self, quote):
            if quote.instrument_id==SOL_PERP.id and quote.ts_event in (60_000_000_000,120_000_000_000):
                self.submit_order(self.order_factory.market(quote.instrument_id,
                    OrderSide.BUY if quote.ts_event==60_000_000_000 else OrderSide.SELL,
                    SOL_PERP.make_qty(D("10"))))
    r=NativeMinuteRiskRecorder(tmp_path/"risk.csv.gz",D(10000),(BTC_PERP,SOL_PERP),
        {BTC_PERP.id:D(40),SOL_PERP.id:D(20)},999_000_000_000)
    s=observed_strategy_type(Probe,r)(lifecycle_config());e=native_engine(s)
    try:
        def bundle(t):
            return SimpleNamespace(open_time_ms=t//1_000_000-60000,
                btc_mark={k:"100" for k in ("open","high","low","close")},
                sol_mark={k:"100" for k in ("open","high","low","close")})
        t=60_000_000_000;r.set_week([bundle(t)])
        run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t)])
        actual=r._snapshot(s,t)
        # Native matching/fees are later than the quote callback.
        assert r.curves["post_quote_paired_close"].minimum["equity"]=="10000"
        assert actual[1]==actual[5]==D("9999")
        r.finalize_receipt(s,t);assert r.receipt_count==0
        r.finalize_receipt(s,t+1)
        assert r.receipt_count==1
        assert D(r.settled_curve.minimum["equity"])==actual[5]
        assert int(r.settled_curve.minimum["timestamp_ns"])==t+1
        t=120_000_000_000;r.set_week([bundle(t)])
        run_ticks(e,[tick(BTC_PERP,t),tick(SOL_PERP,t)])
        assert r._snapshot(s,t)[5]==D("9998") and not e.cache.positions_open()
        # An intervening later native fill makes the older mark unavailable.
        r.note_fill(t+1);r.finalize_receipt(s,t+2)
        assert r.receipt_count==1 and r.receipt_unavailable==1
        assert r.receipt_pending is None
    finally:r.file.close();r.receipt_file.close();e.end();e.dispose()
