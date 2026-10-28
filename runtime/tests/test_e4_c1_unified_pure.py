"""Actual public-adapter source on pure fixtures; no native imports/constructors."""
import asyncio,time
from collections import deque
from dataclasses import dataclass,replace
from decimal import Decimal as D,InvalidOperation
from types import SimpleNamespace as N
import pytest
from coinmaster.ops.hl_info_receipt import InfoReceipt,IncompleteInfoReport,collect_info_receipt
from coinmaster.ops.hl_unified_account import spot_usdc,native_spot_usdc_dicts,default_dex_state,EQUITY_BASIS
from test_e4_c1_manage_only_pure import nodes,run_ast,code

ACCOUNT='0x'+'1'*40
INST='BTC-USD-PERP.HYPERLIQUID'


def state(size='0',pnl='-50'):
    summary={'accountValue':'-80','totalRawUsd':'-90','totalMarginUsed':'25','totalNtlPos':'100'}
    positions=[] if D(size)==0 else [{'position':{'coin':'BTC','szi':size,'entryPx':'100','positionValue':'100','unrealizedPnl':pnl,'leverage':{'type':'cross','value':5}}}]
    return {'marginSummary':summary,'crossMarginSummary':summary,'withdrawable':'-10','assetPositions':positions}


def spot(total='100',hold='0'):
    return {'balances':[{'coin':'USDC','total':total,'hold':hold,'token':0}]}


def money(value):return N(currency='USDC',as_decimal=lambda:D(value))


def account(total='100',hold='0'):
    return N(id='acct',base_currency=None,last_event=N(id='real-state'),balance_total=lambda currency:money(total),
        balance_free=lambda currency:money(D(total)-D(hold)),margin_init_for_currency=lambda currency:money(hold),margin_maint_for_currency=lambda currency:money(hold))


def position(size='1'):
    return N(instrument_id=INST,id='owned',ts_opened=1,is_long=D(size)>0,quantity=N(as_decimal=lambda:abs(D(size))),account_id='acct',strategy_id='strategy')


def money_source():
    env=dict(dataclass=dataclass,Decimal=D,InvalidOperation=InvalidOperation,USDC='USDC',InfoReceipt=InfoReceipt,IncompleteInfoReport=IncompleteInfoReport)
    run_ast(nodes('ops/hl_live_money.py',{'_amount','SelectedCrossAsset','LivePerpsMoneyView','live_perps_money_view','require_native_unified_projection','CheapPortfolioObservation','cheap_unified_observation','materialize_live_c1_input','prospective_cross_margin_ok','collect_selected_cross_assets'}),env)
    return N(**env)


@pytest.mark.parametrize('size,pnl',[('0','0'),('1','50'),('-1','-50')])
def test_unified_reported_spot_total_once_despite_meaningless_perp_summary_and_native_upnl(size,pnl):
    m=money_source();positions=() if D(size)==0 else (position(size),);hold='0' if not positions else '20'
    receipt=InfoReceipt(ACCOUNT,'',0,1000,(),tuple(row['position'] for row in state(size,pnl)['assetPositions']),(),(),account_role='user',abstraction='unifiedAccount',dex_abstraction=False,
        account_mode='unifiedAccount',spot_balances=tuple(spot('100',hold)['balances']),all_dex_states=(('',state(size,pnl)),),equity_basis=EQUITY_BASIS)
    view=m.live_perps_money_view(receipt,account_ref=ACCOUNT,dex='',account_id='acct',native_account=account('100',hold),native_positions=positions,now_ms=1000,native_revision=7)
    assert view.equity==D(100) and view.raw_usd==D(100) and view.margin_used==D(hold)
    assert view.equity_basis==EQUITY_BASIS and view.account_mode=='unifiedAccount'


def test_missing_or_zero_usdc_emits_explicit_zero_balance_and_hold_proxy():
    balance,margin=native_spot_usdc_dicts([])
    assert balance=={'currency':'USDC','total':'0','locked':'0','free':'0'}
    assert margin=={'currency':'USDC','initial':'0','maintenance':'0','instrument_id':None}
    assert spot_usdc({'balances':[]})==(D(0),D(0),D(0))


@pytest.mark.parametrize('raw',[{'balances':[{'coin':'USDC','total':'100','hold':'101'}]},
    {'balances':[{'coin':'USDC','total':'NaN','hold':'0'}]},
    {'balances':[{'coin':'USDC','total':'1','hold':'0'},{'coin':'USDC','total':'2','hold':'0'}]},
    {'balances':[{'coin':'HYPE','total':'1','hold':'0'}]}])
def test_unified_malformed_duplicate_or_other_collateral_is_unknown(raw):
    with pytest.raises(ValueError):spot_usdc(raw)


def test_foreign_dex_and_isolated_positions_deny_without_using_perp_capital():
    with pytest.raises(ValueError,match='FOREIGN_DEX'):default_dex_state([['',state()],['xyz',state('1')]])
    isolated=state('1');isolated['assetPositions'][0]['position']['leverage']['type']='isolated'
    with pytest.raises(ValueError,match='ISOLATED'):default_dex_state([['',isolated]])


def test_fee_funding_are_observed_reported_total_once_and_revision_or_age_invalidates():
    m=money_source();now=time.monotonic_ns()
    observation=m.cheap_unified_observation(spot('98.5'),[['',state()]],account_id='acct',native_account=account('98.5'),native_positions=(),strategy_id='strategy',revision=7,fill_epoch=2,ws_epoch=3,started_ns=now,completed_ns=now,available_ns=1000)
    assert observation.equity==D('98.5') and observation.equity_basis==EQUITY_BASIS
    with pytest.raises(ValueError,match='MOVED'):observation.require_current(now_ns=now+1,revision=8,fill_epoch=2,ws_epoch=3)
    with pytest.raises(ValueError,match='STALE'):observation.require_current(now_ns=now+9_000_000_001,revision=7,fill_epoch=2,ws_epoch=3)
    with pytest.raises(ValueError,match='UNATTRIBUTED_HOLD'):
        m.cheap_unified_observation(spot('100','20'),[['',state()]],account_id='acct',native_account=account('100','20'),native_positions=(),strategy_id='strategy',revision=7,fill_epoch=2,ws_epoch=3,started_ns=now,completed_ns=now,available_ns=1000)


def native_source():
    class Boundary:pass
    class Legacy:
        async def _update_account_state(self):self.legacy_http+=1
        def _handle_account_state(self,msg):self.legacy_ws+=1
    env=dict(asyncio=asyncio,time=time,deque=deque,IncompleteInfoReport=IncompleteInfoReport,
        QualifiedInfoBoundary=Boundary,HyperliquidExecutionClient=Legacy,
        AccountBalance=N(from_dict=lambda row:dict(row)),MarginBalance=N(from_dict=lambda row:dict(row)))
    run_ast(nodes('ops/hl_live_execution.py',{'ReadinessInfoBudget','QualifiedHyperliquidExecutionClient','finite_generation_reservation','InfoWeightBudget'}),env)
    return N(**env)


def native_owner(raw=None,mode='unifiedAccount'):
    e=native_source();owner=object.__new__(e.QualifiedHyperliquidExecutionClient)
    owner._cm_unified=True;owner._cm_unified_account_task=None;owner._cm_unified_refresh_task=None
    owner._cm_unified_native_started_ns=None;owner._cm_unified_generation_reservation=None;owner._cm_unified_native_charge=0
    owner._cm_inputs_budget=e.ReadinessInfoBudget();owner._cm_scope=N(account_ref=ACCOUNT);owner._cm_ws_epoch=2;owner._cm_ws_failure=None
    owner._cm_require_healthy=lambda:None;owner._cm_fail=lambda reason:setattr(owner,'_cm_ws_failure',reason)
    owner._clock=N(timestamp_ns=lambda:1_000_000_000);owner._cm_strategy=N(_live_inputs_dirty=False,_last_live_input_observation='old')
    owner.legacy_http=owner.legacy_ws=0;owner.http=[];owner.native_calls=0;owner.generated=[]
    async def info(body):owner.http.append(body);await asyncio.sleep(0);return mode
    async def native():
        owner.native_calls+=1;await asyncio.sleep(0)
        return [N(to_dict=lambda:dict(currency='USDC',total='100',locked='20',free='80'))] if raw is None else raw
    owner._cm_info=info;owner._client=N(request_spot_balances=native)
    owner.generate_account_state=lambda **kwargs:owner.generated.append(kwargs)
    return owner,e


def test_stock_public_spot_to_reported_accountstate_coalesces_and_classic_unchanged():
    owner,e=native_owner()
    async def run():await asyncio.gather(owner._update_account_state(),owner._update_account_state())
    asyncio.run(run())
    assert len(owner.http)==1 and owner.native_calls==1 and len(owner.generated)==1
    event=owner.generated[0]
    assert event['reported'] is True and event['balances'][0]['total']=='100' and event['margins'][0]['initial']=='20'
    assert event['margins'][0]['maintenance']=='20' and event['margins'][0]['instrument_id'] is None
    assert sum(item[1] for item in owner._cm_inputs_budget.spent)==28
    owner._cm_unified=False;asyncio.run(owner._update_account_state());owner._handle_account_state(object())
    assert owner.legacy_http==1 and owner.legacy_ws==1


def test_legacy_ws_account_heuristic_cannot_overwrite_unified_and_zero_clears():
    owner,e=native_owner(raw=[])
    async def run():
        owner._handle_account_state(N(total='999999-old-perp'))
        await owner._cm_unified_refresh_task
    asyncio.run(run())
    assert owner.legacy_ws==0 and owner.generated[0]['balances'][0]['total']=='0'
    assert owner.generated[0]['margins'][0]['initial']=='0' and owner._cm_strategy._last_live_input_observation is None


def test_wrong_mode_or_nonusdc_native_collateral_never_emits_qualified_state():
    owner,e=native_owner(mode='portfolioMargin')
    with pytest.raises(ValueError,match='MODE_MISMATCH'):asyncio.run(owner._update_account_state())
    assert owner.native_calls==0 and owner.generated==[] and sum(item[1] for item in owner._cm_inputs_budget.spent)==20
    owner,e=native_owner(raw=[N(to_dict=lambda:dict(currency='HYPE',total='1',locked='0',free='1'))])
    with pytest.raises(ValueError,match='OTHER_COLLATERAL'):asyncio.run(owner._update_account_state())
    assert owner.generated==[]


def test_unified_generation_max652_under700_classic600_and_prepaid_native_not_doublecharged():
    owner,e=native_owner()
    assert e.finite_generation_reservation(15)==600
    assert e.finite_generation_reservation(15,unified=True)==652
    with pytest.raises(ValueError,match='SCOPE'):e.finite_generation_reservation(16,unified=True)
    owner._cm_unified_generation_reservation=owner._cm_inputs_budget.reserve(592,time.monotonic())
    asyncio.run(owner._update_account_state())
    assert owner._cm_unified_native_charge==28 and len(owner._cm_inputs_budget.spent)==1
    assert owner._cm_inputs_budget.spent[0][1]==592


def test_unified_venue_admission_uses_real_side_limits_and_free_fees():
    m=money_source();assets=(m.SelectedCrossAsset('BTC',5,D(100),(D(2),D(1)),(D(40),D(20))),m.SelectedCrossAsset('SOL',5,D(10),(D(20),D(20)),(D(40),D(40))))
    view=m.LivePerpsMoneyView(ACCOUNT,'',1,D(100),D(80),D(20),D(100),assets,(),7,'unifiedAccount',EQUITY_BASIS,'HOLD_PROXY')
    args=dict(positions={},pending_openings=(),coin='BTC',side='BUY',max_gross_multiple=D(8))
    assert m.prospective_cross_margin_ok(view,quantity=D(1),**args)
    assert not m.prospective_cross_margin_ok(view,quantity=D(3),**args)
    assert not m.prospective_cross_margin_ok(replace(view,selected_assets=(replace(assets[0],available_to_trade=None),assets[1])),quantity=D(1),**args)


def instrument_dict(instrument='BTC-USD-PERP.HYPERLIQUID'):
    return {'type':'CryptoPerpetual','id':instrument,'raw_symbol':'BTC','base_currency':'BTC','quote_currency':'USD',
        'settlement_currency':'USDC','is_inverse':False,'min_notional':'10 USD','max_notional':None,
        'margin_init':'0','margin_maint':'0','maker_fee':'0','taker_fee':'0','price_increment':'0.1','size_increment':'0.001',
        'price_precision':1,'size_precision':3,'tick_scheme_name':None,'multiplier':'1','info':{'venue':'actual-shape'},'ts_event':1,'ts_init':2}


def provider_source():
    class Instrument:
        def __init__(self,values):self.values=dict(values)
        def to_dict(self):return dict(self.values)
        @classmethod
        def from_dict(cls,values):return cls(values)
    class Legacy(Instrument):pass
    class StockProvider:
        def __init__(self,*args,**kwargs):self.raw=[];self.cache=[];self.loads=0
        async def _load_instruments(self):
            self.loads+=1;self.raw=[Instrument(instrument_dict())]
            return [Legacy(instrument_dict())]
        def instruments_pyo3(self):return self.raw
        async def load_all_async(self):self.cache=await self._load_instruments()
    class DataFactory:pass
    from functools import lru_cache
    env={'Decimal':D,'lru_cache':lru_cache,'nautilus_pyo3':N(CryptoPerpetual=Instrument),'CryptoPerpetual':Legacy,
         'HyperliquidInstrumentProvider':StockProvider,'LiveDataClientFactory':DataFactory}
    run_ast(nodes('ops/hl_unified_instruments.py',{'TARGET_IDS','POLICY','normalize_unified_instrument_dict','normalize_unified_pyo3_instrument','normalize_unified_legacy_instrument','UnifiedHyperliquidInstrumentProvider'}),env)
    return N(**env,Instrument=Instrument,Legacy=Legacy)


def test_production_provider_public_rebuild_preserves_id_numeric_limits_zero_rates_and_refresh():
    p=provider_source();raw=p.Instrument(instrument_dict());normalized=p.normalize_unified_pyo3_instrument(raw)
    before=raw.to_dict();after=normalized.to_dict()
    assert before['quote_currency']=='USD' and after['quote_currency']=='USDC' and after['min_notional']=='10 USDC'
    assert {key:value for key,value in after.items() if key not in ('quote_currency','min_notional')}=={key:value for key,value in before.items() if key not in ('quote_currency','min_notional')}
    provider=p.UnifiedHyperliquidInstrumentProvider()
    asyncio.run(provider.load_all_async());asyncio.run(provider.load_all_async())
    assert provider.loads==2
    assert provider.instruments_pyo3()[0].to_dict()['quote_currency']=='USDC'
    assert provider.cache[0].to_dict()['quote_currency']=='USDC' and provider.cache[0].to_dict()['tick_scheme_name'] is None
    assert provider.raw[0].to_dict()['quote_currency']=='USD'  # Public rebuild, no rawcache mutation.


@pytest.mark.parametrize('key,value',[('margin_init','0.1'),('taker_fee','0.00045'),('settlement_currency','USDT'),('min_notional','10 EUR')])
def test_provider_rejects_nonstock_rates_foreign_denomination_instead_of_fx(key,value):
    p=provider_source();values=instrument_dict();values[key]=value
    with pytest.raises(ValueError):p.normalize_unified_pyo3_instrument(p.Instrument(values))


def test_unified_c1_native_pnl_must_be_actual_usdc_and_never_added_to_capital():
    m=money_source();now=time.monotonic_ns();position_=position('1')
    position_.unrealized_pnl=lambda price:N(currency='USDC',as_decimal=lambda:D(-50))
    instrument=N(make_price=lambda p:p,size_increment=N(as_decimal=lambda:D('0.001')),quote_currency='USDC',settlement_currency='USDC')
    observation=m.CheapPortfolioObservation(D(100),D(100),D(80),D(20),(('BTC',D(1)),),7,2,3,now,now,1000,'real-state','unifiedAccount',EQUITY_BASIS)
    kwargs=dict(native_positions=(position_,),native_marks={INST:N(price=D(50),ts_event=1000,ts_init=1000)},native_cache=N(instrument=lambda i:instrument),account_event_id='real-state',strategy_id='strategy',account_id='acct',decision_ns=1001,monotonic_ns=now+1,revision=7,fill_epoch=2,ws_epoch=3,max_mark_age_ns=100)
    value=m.materialize_live_c1_input(observation,**kwargs)
    assert value.equity==D(100) and value.positions[0].native_pnl==D(-50) and value.positions[0].pnl_currency=='USDC'
    assert value.equity_basis==EQUITY_BASIS
    instrument.quote_currency='USD'
    with pytest.raises(ValueError,match='PNL_CURRENCY'):m.materialize_live_c1_input(observation,**kwargs)


def test_actual_unified_discovery_then_full_vector_and_refund_and_directory_quarantine(code):
    m=money_source();calls=[];failure=[]
    async def read_http(body,**kwargs):
        calls.append(body['type']);kind=body['type']
        if kind=='perpDexs':return [None,{'name':'xyz'}]
        if kind=='frontendOpenOrders':return []
        if kind=='allDexsClearinghouseState':return [['',state()],['xyz',state()]]
        if kind=='spotClearinghouseState':return spot()
        if kind=='userRole':return {'role':'user'}
        if kind=='userAbstraction':return 'unifiedAccount'
        if kind=='userDexAbstraction':return False
        if kind=='userFillsByTime':return []
        if kind=='activeAssetData':return {'user':ACCOUNT,'coin':body['coin'],'leverage':{'type':'cross','value':5},'markPx':'100','maxTradeSzs':['5','5'],'availableToTrade':['100','100']}
        raise AssertionError(body)
    env=dict(asyncio=asyncio,time=time,deque=deque,IncompleteInfoReport=IncompleteInfoReport,collect_info_receipt=collect_info_receipt,
        collect_selected_cross_assets=m.collect_selected_cross_assets,qualified_mass_status=lambda *args,**kwargs:N(account_id='acct'),
        InstrumentId=N(from_str=lambda v:v),read_info_http=read_http,_native_order_fingerprint=lambda o:[])
    run_ast(nodes('ops/hl_live_execution.py',{'ReadinessInfoBudget','finite_generation_reservation','InfoWeightBudget','SingleAttemptInfoTransport','QualifiedInfoBoundary'}),env)
    owner=env['QualifiedInfoBoundary']();owner._cm_unified=True;owner._cm_inputs_enabled=True;owner._cm_unified_discovery=None
    owner._cm_ws_epoch=2;owner._cm_unified_generation_reservation=None;owner._cm_unified_native_charge=0
    owner._cm_bootstrapped=False;owner._cm_ws_phase='BUFFERING';owner._cm_ws_failure=None;owner._cm_info_usage=deque()
    owner._cm_inputs_budget=env['ReadinessInfoBudget']();owner._cm_require_healthy=lambda:None;owner._cm_fail=lambda reason:failure.append(reason)
    from test_e4_c1_manage_only_pure import config
    owner._cm_strategy=code.Strategy(config())
    scope=N(durable_orders=(),account_ref=ACCOUNT,dex='',anchor_ms=0,anchor_tid=None,owned_coins=frozenset({'BTC','SOL'}))
    owner._cm_scope=scope;owner._cm_owned_scope=lambda:(scope,7,(),frozenset(),())
    owner._cm_runtime=N(info_query_evidence=lambda *args:({},(),None,None))
    owner._cache=N(instrument=lambda i:object());owner._clock=N(timestamp_ns=lambda:10_000_000_000)
    owner.venue='HL';owner.account_id='acct';owner.id='client'
    owner._cm_info=env['SingleAttemptInfoTransport'](testnet=False,timeout=1)
    async def refresh():owner._cm_unified_native_charge=28
    owner._cm_refresh_native_account_for_generation=refresh
    assert asyncio.run(owner.generate_mass_status()).account_id=='acct'
    assert len(calls)==19 and calls.count('perpDexs')==1 and calls.count('allDexsClearinghouseState')==2 and calls.count('spotClearinghouseState')==2
    assert sum(item[1] for item in owner._cm_inputs_budget.spent)==452  # Discovery60 +collector364+native28.
    assert owner._cm_unified_generation_reservation is None and owner._cm_unified_discovery_current()
    with pytest.raises(ValueError,match='DIRECTORY_CHANGED'):owner._cm_validate_unified_dex_directory([['newdex',state()]])
    assert owner._cm_unified_discovery is None
    async def oversize(body,**kwargs):return [None]+[{'name':str(i)} for i in range(32)]
    env['read_info_http']=oversize
    # Advance only this fixture clock past the rolling window; gateway expires
    # actual charges normally, without a production budget reset or fakecredit.
    env['time']=N(monotonic=lambda:time.monotonic()+61,monotonic_ns=lambda:time.monotonic_ns()+61_000_000_000)
    with pytest.raises(ValueError,match='BOUND_UNKNOWN'):asyncio.run(owner.qualify_unified_prestart_orders())
    assert sum(item[1] for item in owner._cm_inputs_budget.spent)==20 and owner._cm_unified_discovery is None


@pytest.mark.parametrize('unified',[False,True])
def test_actual_public_virgin_dp_wrapper_initializes_observed_h_then55_and_rejects_reset(code,tmp_path,monkeypatch,unified):
    import ast,sys
    from types import ModuleType
    from test_e4_c1_manage_only_pure import ROOT
    from test_e4_c1_input_bridge_pure import fresh_init_fixture
    from coinmaster.domain.deposit_protection import DepositProtection,percent
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    if unified:
        s.config.live_account_mode='unifiedAccount';s.config.live_equity_basis=EQUITY_BASIS;s._live_account_mode='unifiedAccount'
        view=replace(view,account_mode='unifiedAccount',equity_basis=EQUITY_BASIS)
    try:
        s.initialize_clean_flat_c1_epoch(view,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,history_anchor_ms=0)
        cls=next(node for node in ast.parse((ROOT/'strategy/wave_overlay.py').read_text()).body if isinstance(node,ast.ClassDef) and node.name=='WaveOverlayStrategy')
        names={'apply_deposit_control','deposit_projection','_deposit_equity','_persist_deposit'}
        env={'percent':percent,'Decimal':D}
        run_ast([node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name in names],env)
        for name in names:monkeypatch.setattr(type(s),name,env[name],raising=False)
        m=money_source();module=ModuleType('coinmaster.ops.hl_live_money');module.CheapPortfolioObservation=m.CheapPortfolioObservation
        monkeypatch.setitem(sys.modules,module.__name__,module)
        s._deposit=DepositProtection();s._deposit_storage_failed=False;s._deposit_exit_started=False
        s.config.deposit_runtime=r;s.config.deposit_instance_id=r.owner;s.config.deposit_account_id='HYPERLIQUID-master'
        s.config.deposit_equity_reader=lambda strategy:strategy._validated_live_deposit_equity()
        s._live_inputs_dirty=False;s._live_input_ws_epoch=lambda:3;s._recovery_health=lambda:True
        s.clock=N(timestamp_ns=lambda:now+1);s.is_exiting=lambda:False
        ns=time.monotonic_ns()
        s._last_live_input_observation=m.CheapPortfolioObservation(D(82),D(82),D(82),D(0),(),r.native_revision(),0,3,ns,ns,now,'fresh-native',s._live_account_mode,EQUITY_BASIS if unified else 'HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1')
        assert s._deposit.high_water is None
        result=s.initialize_fresh_live_deposit_protection('explicit-fresh-dp')
        assert result['high_water_equity']=='82' and result['drawdown_limit_percent']==55 and result['threshold_equity']=='36.9'
        stored=r.deposit_protection_state(instance_id=r.owner,account_id='HYPERLIQUID-master')
        with pytest.raises(ValueError,match='VIRGIN_INITIALIZATION_ONLY'):s.initialize_fresh_live_deposit_protection('no-reset')
        assert r.deposit_protection_state(instance_id=r.owner,account_id='HYPERLIQUID-master')==stored
        assert not s.recovery_confirmed and not s._management_dispatch_enabled
    finally:r.close()
