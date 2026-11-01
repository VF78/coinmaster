"""Two actual pre-GO interface regressions; no native Engine/Strategy instances."""
from copy import deepcopy
from dataclasses import asdict,dataclass
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import pytest
from coinmaster.research import cm2_reference_control_worker as control,cm2_runner as runner
from coinmaster.strategy.cm2_reference_policy import ReferenceConfig,ReferenceFlags,selected_btc_candidate
from coinmaster.strategy.cm2_order_contract import MODEL_ID


def test_original_control_api_strings_preserved_only_seed_is_decimal(tmp_path):
    prepared={**deepcopy(control.FIXED),'candidate':deepcopy(control.CANDIDATE),
        'data_root':str(tmp_path/'data'),'artifact_dir':str(tmp_path/'old-artifact'),
        'current_hl_execution_inputs':str(tmp_path/'profile'),'artifact_label':'PREPARED',
        'trading_start_ms':1725148800000,'trading_end_ms':1733011200000,'warmup_start_ms':1662076800000}
    request={'run_id':'SYNTHETIC_TYPED_ONLY'}
    result=control.materialize(prepared,request,artifact_dir=tmp_path/'fresh')
    assert type(result['initial_active_seed']) is D and result['initial_active_seed']==D(10000)
    for key,value in {'research_regime_reentry_band':'0.5','research_c1_restore_dd':'0.40',
            'research_btc_split_discount':'0.0025','research_h4_gamma':'0.5'}.items():
        assert type(result[key]) is str and result[key]==value
    assert result['research_c1_first_fresh_h4'] is True and result['research_c1_btc_postcut_d1'] is True
    assert result['candidate'].sol_overlay_enabled is False
    assert all(type(result[k]) is type(Path()) for k in control.PATH_FIELDS)
    assert prepared['initial_active_seed']=='10000'  # input kwargs are never mutated


@dataclass
class Policy:
    version:str='SYNTHETIC_CALLER_PROBE_ONLY'


@dataclass
class Fees:
    venue:str='hyperliquid'
    hyperliquid_maker:str='0.000144'
    hyperliquid_taker:str='0.000432'


@pytest.mark.parametrize('extra_wrapper',[False,True])
def test_actual_full_probe_strict_immediate_caller_and_no_engine(tmp_path,monkeypatch,extra_wrapper):
    import nautilus_trader.backtest.engine as native_engine
    from coinmaster.research import native_baseline as nb
    forbidden=[];closed=[];observed_proxy=[]
    class NoEngine:
        @staticmethod
        def add_venue(*a,**k):raise AssertionError('NO_NATIVE_VENUE')
        def __new__(cls,*a,**k):forbidden.append(1);raise AssertionError('NO_NATIVE_ENGINE')
    monkeypatch.setattr(native_engine,'BacktestEngine',NoEngine)
    def indirect(factory):return factory()
    def exact_api(**kwargs):
        # These are synthetic API locals, never market/account values. The
        # actual full_api_boundary_probe must inspect exactly THIS frame.
        qualification_mode=kwargs['qualification_mode'];qualification_quantity_model=kwargs['qualification_quantity_model']
        qualification_instrument_metadata=kwargs['qualification_instrument_metadata']
        qualification_deposit_runtime=kwargs['qualification_deposit_runtime']
        qualification_deposit_equity_reader=kwargs['qualification_deposit_equity_reader']
        qualification_deposit_account_id=kwargs['qualification_deposit_account_id']
        current_hl=N(instruments=(N(settlement_currency='USDC',id='BTC'),N(settlement_currency='USDC',id='SOL')),evidence={'synthetic':True})
        policy=Policy();fee_policy=Fees();initial_active_seed=kwargs['initial_active_seed']
        trading_start_ms=kwargs['trading_start_ms'];trading_end_ms=kwargs['trading_end_ms'];warmup_start_ms=kwargs['warmup_start_ms']
        selected_leverage=(('BTC',D(40)),('SOL',D(20)));research_cm2=kwargs['research_cm2']
        journal=N(close=lambda:closed.append(1));factory=native_engine.BacktestEngine
        observed_proxy.append(factory.add_venue is NoEngine.add_venue)
        return indirect(factory) if extra_wrapper else factory()
    monkeypatch.setattr(nb,'run_native_diagnostic',exact_api)
    policy=ReferenceConfig('cm2-btc-reference-v1',selected_btc_candidate(),ReferenceFlags(True,True))
    request={'run_id':'SYNTHETIC_CALLER_ONLY','data_root':str(tmp_path/'data'),'artifact_dir':str(tmp_path/'case'),
        'current_hl_execution_inputs':str(tmp_path/'profile'),'initial_active_seed':'10000','policy':asdict(policy),
        'start_ns':1725148800000000000,'end_ns':1733011200000000000,'request_execution_model_id':MODEL_ID}
    probe=tmp_path/'probe'
    if extra_wrapper:
        with pytest.raises(ValueError,match='UNEXPECTED_ENGINE_BOUNDARY_CALLER'):runner.full_api_boundary_probe(request,probe)
        assert not (probe/'api-boundary-proof.json').exists()
    else:
        proof=runner.full_api_boundary_probe(request,probe)
        assert proof['boundary_calls']==1 and proof['native_engine_constructions']==0
        assert proof['captured']['actual_cm2_policy']['version']==policy.version
        assert closed==[1]
    assert not forbidden and observed_proxy==[True]
    assert native_engine.BacktestEngine is NoEngine  # restored even on strict caller denial
