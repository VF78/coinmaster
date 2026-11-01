"""Fixed joint case preconditions/config boundary; NO Engine/Strategy instances."""
from dataclasses import asdict
from decimal import Decimal as D
from datetime import datetime,timedelta,timezone
import importlib.util,json
from pathlib import Path
from types import SimpleNamespace as N
import pytest

# This disjoint fixture checkpoint is integrated after the main SOL writer.
# During independent development PYTHONPATH points at that writer's runtime;
# the leaf itself is always loaded from the exact file under review here.
path=Path(__file__).resolve().parents[1]/'coinmaster/research/cm2_reference_fixture.py'
spec=importlib.util.spec_from_file_location('joint_fixture_under_review',path)
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


def test_fixed_source_dislocation_k_and_regime_without_search():
    p=fixture.prepare_joint_plan()
    assert len(p['seed'])==730 and len(p['seed_paired_closes'])==61
    assert p['joint_first']['side']==-1 and p['joint_first']['side']*p['joint_first']['z']>=1.25
    assert p['joint_second']['side']==1 and p['joint_second']['z']<-.125
    assert D(p['joint_k'])==D('1.2259491786422409710857928492396890337631336118425')
    assert p['levels']==(0.0,0.06614947745329758,0.07864809858396286)
    sources=fixture.declared_joint_closes()
    assert all(type(b) is type(s) is str for _,b,s in sources)
    assert all(float(b)==r.btc_close and float(s)==r.sol_close for (_,b,s),r in zip(sources,p['seed']))
    assert p['seed_paired_closes'][-1][0]==fixture.START_NS
    assert all(b[0]-a[0]==fixture.DAY for a,b in zip(sources,sources[1:]))


def test_fixed_49h_quotes_closed_d1_ohlc_and_existing_pure_atr_reentry():
    from coinmaster.strategy.cm2_reference_policy import ReferenceBtcPolicy,ReferenceFlags
    from coinmaster.domain.wave_overlay import DailyBar
    f=fixture;p=f.prepare_joint_plan();end=f.fixture_interval(f.SOL_FIXTURE_ID)[1]
    prices=[f.joint_execution_price(i) for i in range((end-f.START_NS)//f.MINUTE)]
    assert len(prices)==49*60 and prices[1443]==D(60210) and prices[1445]==D(54500)
    assert prices[2878]==D(54500) and prices[2879:]==[D(65000)]*61
    days=[prices[:1440],prices[1440:2880]]
    assert [(x[0],max(x),min(x),x[-1]) for x in days]==[(D(60000),D(60000),D(60000),D(60000)),(D(60000),D(65000),D(54500),D(65000))]
    ref=ReferenceBtcPolicy(p['candidate'],flags=ReferenceFlags(True,True),btc_step=D('.00001'),
        trading_start_ns=f.START_NS,terminal_ns=end,max_quote_age_ns=120_000_000_000)
    ohlc={n:(hi,lo) for n,hi,lo in p['seed_ohlc']}
    for row in p['seed']:
        hi,lo=ohlc[int(row.close_time.timestamp()*1e9)]
        ref.accept_closed_day(row,receipt_ns=f.START_NS,btc_high=hi,btc_low=lo)
    start=datetime.fromtimestamp(f.START_NS/1e9,timezone.utc)
    features=[]
    for i,day in enumerate(days):
        row=DailyBar(start+timedelta(days=i),start+timedelta(days=i+1),start+timedelta(days=i+1),float(day[0]),float(day[-1]),149.)
        features.append(ref.accept_closed_day(row,receipt_ns=f.START_NS+(i+1)*f.DAY,btc_high=float(max(day)),btc_low=float(min(day))))
    assert [x.side for x in features]==[-1,1]
    # Existing market formula, no parent or trade decision injected.
    assert features[-1].side*(float(days[-1][-1])-ref._features.ema)>=.5*ref._atr_reentry()


@pytest.mark.parametrize('fixture_id',[fixture.FIXTURE_ID,fixture.TERMINAL_FIXTURE_ID,fixture.SOL_FIXTURE_ID])
def test_actual_shared_leaf_inputs_reach_real_strategy_config_before_pure_ctor(tmp_path,monkeypatch,fixture_id):
    from coinmaster.research import cm2_runner as runner
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder
    from coinmaster.strategy import cm2_native as native
    from coinmaster.strategy.cm2_reference_policy import ReferenceConfig,ReferenceFlags
    from coinmaster.strategy.cm2_sol_policy import SolConfig
    from nautilus_trader.model.data import BarType,BarSpecification
    from nautilus_trader.model.enums import BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    profile=load_current_hl_diagnostic(Path(__file__).parent/'fixtures/hl-current-20261029')
    joint=fixture_id==fixture.SOL_FIXTURE_ID
    plan=fixture.prepare_joint_plan() if joint else fixture.prepare_plan()
    end=fixture.fixture_interval(fixture_id)[1]
    cfg=runner.CM2RunConfig(ReferenceConfig('cm2-btc-reference-v1',plan['candidate'],ReferenceFlags(True,True)),sol_policy=SolConfig(enabled=True) if joint else None)
    journal=NativeEventJournal(str(tmp_path/'SYNTHETIC-CONFIG-ONLY.sqlite'))
    risk=NativeMinuteRiskRecorder(tmp_path/'SYNTHETIC-CONFIG-ONLY.csv.gz',D(10000),profile.instruments,dict(profile.selected_leverage),end,margin_policy=profile.margin_policy(120_000_000_000))
    bars={i.id:BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL) for i in profile.instruments}
    captured=[]
    class Boundary(BaseException):pass
    class PureSpy:
        def __init__(self,config):captured.append(config);raise Boundary('STOP_BEFORE_NATIVE_STRATEGY')
    monkeypatch.setattr(native,'CM2Strategy',PureSpy)
    try:
        kwargs=fixture.fixture_strategy_inputs(plan,profile,end_ns=end,journal=journal,
            mark_client=ClientId('TEST-MARK'),signal_client=ClientId('TEST-SIGNAL'),minute_bars=bars,risk=risk,observer=N())
        with pytest.raises(Boundary):runner.build_strategy(cfg,**kwargs)
        assert len(captured)==1 and isinstance(captured[0],native.CM2StrategyConfig)
        actual=captured[0]
        assert actual.policy.candidate.sol_overlay_enabled is False and actual.seed_days==plan['seed']
        assert actual.sol_policy==cfg.sol_policy and actual.terminal_close_at_ns==end
        if joint:
            assert actual.sol_policy.enabled and actual.seed_paired_closes==plan['seed_paired_closes']
            assert len(actual.seed_paired_closes)==61 and all(type(b) is type(s) is str for _,b,s in actual.seed_paired_closes)
        else:assert not actual.seed_paired_closes and actual.sol_policy is None
    finally:risk.close_writers();journal.close()


def test_joint_requires_enabled_typed_policy_before_engine_import():
    from coinmaster.strategy.cm2_reference_policy import ReferenceConfig,ReferenceFlags,selected_btc_candidate
    policy=asdict(ReferenceConfig('cm2-btc-reference-v1',selected_btc_candidate(),ReferenceFlags(True,True)))
    request=dict(policy=policy,fixture_id=fixture.SOL_FIXTURE_ID,start_ns=fixture.START_NS,end_ns=fixture.fixture_interval(fixture.SOL_FIXTURE_ID)[1])
    with pytest.raises(ValueError,match='JOINT_ENABLED_SOL_V1_REQUIRED'):fixture.run_fixture(request)


def test_artifact_failure_preserves_pending_native_export_without_pass(tmp_path,monkeypatch):
    from coinmaster.research import cm2_runner as runner
    def broken(*args):raise OSError('SYNTHETIC_CRC_FAILURE')
    monkeypatch.setattr(runner,'engineering_artifact_integrity',broken)
    result={'status':'NATIVE_EXPORTS_COMPLETE_JOINT_GATES_PENDING','checks':{k:False for k in fixture.joint_fixture_protocol()['mandatory']}}
    with pytest.raises(OSError,match='CRC_FAILURE'):fixture.finalize_joint_fixture(result,tmp_path,{},fixture.fixture_interval(fixture.SOL_FIXTURE_ID)[1])
    saved=json.loads((tmp_path/'fixture-result.json').read_text())
    assert saved['status']=='JOINT_ARTIFACT_OR_EVIDENCE_FAILED' and not any(saved['checks'].values())
    assert saved['joint_evidence_error']['type']=='OSError'


def test_legacy_protocols_keep_intervals_and_joint_does_not_claim_partial_late():
    f=fixture
    assert f.fixture_interval(f.FIXTURE_ID)==(f.START_NS,f.START_NS+4*f.DAY)
    assert f.fixture_interval(f.TERMINAL_FIXTURE_ID)==(f.START_NS,f.START_NS+f.DAY+f.HOUR)
    assert f.fixture_interval(f.SOL_FIXTURE_ID)==(f.START_NS,f.START_NS+2*f.DAY+f.HOUR)
    assert f.fixture_protocol(f.FIXTURE_ID)['schema']=='CM2_BTC_REFERENCE_ENGINEERING_F01_V1'
    assert f.fixture_protocol(f.TERMINAL_FIXTURE_ID)['schema']=='CM2_BTC_REFERENCE_ENGINEERING_TERMINAL_V1'
    assert {'actual_partial_fill','actual_late_fill_after_cancel'}.issubset(f.joint_fixture_protocol()['not_claimed'])
