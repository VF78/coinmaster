"""Actual first-held SQLite/scope/two sweeps/report/cashflow/verifier chain, no native imports."""
import asyncio,ast,hashlib,json,time,sys
from collections import defaultdict,deque
from dataclasses import dataclass,replace
from decimal import Decimal as D,InvalidOperation
from types import SimpleNamespace as N
import pytest
from coinmaster.domain.wave_overlay import Candidate,Episode,WaveOverlayState
from coinmaster.domain.deposit_protection import DepositProtection
from coinmaster.ops.hl_info_receipt import collect_info_receipt,InfoReceipt,IncompleteInfoReport
from coinmaster.ops.hl_unified_account import EQUITY_BASIS
from test_e4_c1_manage_only_pure import code,nodes,run_ast,ROOT,ACCOUNT,ACCOUNT_ID,ID,VENUE
from test_e4_c1_input_bridge_pure import fresh_init_fixture
from test_e4_c1_unified_pure import money_source,state,spot

class V(str):
    @property
    def name(self):return str(self)
def enums(*names):return N(**{name:V(name) for name in names})
SIDE=enums('BUY','SELL');STATUS=enums('DENIED','ACCEPTED','PARTIALLY_FILLED','FILLED','CANCELED')
TYPE=enums('MARKET','LIMIT');TIF=enums('IOC','GTC');LIQ=enums('MAKER','TAKER');POS=enums('LONG','SHORT')
@dataclass
class Q:
    value:D
    @classmethod
    def from_str(cls,value):return cls(D(value))
    def as_decimal(self):return self.value
    def __str__(self):return str(self.value)
class Cash(Q):
    currency='USDC'
    def __init__(self,value,currency='USDC'):super().__init__(D(value));self.currency=currency
class Fill:
    def __init__(self,*args,client_order_id):
        for key,value in zip(('account_id','instrument_id','venue_order_id','trade_id','order_side','last_qty','last_px','commission','liquidity_side','id','ts_event','ts_init'),args):setattr(self,key,value)
        self.client_order_id=client_order_id
class OrderReport:
    def __init__(self,*args,**kwargs):
        for key,value in zip(('account_id','instrument_id','venue_order_id','order_side','order_type','time_in_force','order_status','quantity','filled_qty','id','ts_accepted','ts_last','ts_init'),args):setattr(self,key,value)
        self.__dict__.update(kwargs)
class PositionReport:
    def __init__(self,*args,**kwargs):
        for key,value in zip(('account_id','instrument_id','position_side','quantity','id','ts_last','ts_init'),args):setattr(self,key,value)
        self.__dict__.update(kwargs)
class Mass:
    def __init__(self,client,account,venue,*unused):self.account_id=account;self.venue=venue
    def add_order_reports(self,rows):self.order_reports={str(r.client_order_id):r for r in rows}
    def add_fill_reports(self,rows):
        self.fill_reports=defaultdict(list)
        for row in rows:self.fill_reports[str(row.client_order_id)].append(row)
    def add_position_reports(self,rows):
        self.position_reports=defaultdict(list)
        for row in rows:self.position_reports[row.instrument_id].append(row)

@pytest.fixture
def chain(code,tmp_path):
    helper_env=code.management
    run_ast(nodes('ops/live_recovery.py',{'owned_fill_anchor_fingerprint','applied_owned_fill_anchor'}),helper_env)
    fake=sys.modules['coinmaster.ops.live_recovery']
    for name in ('owned_fill_anchor_fingerprint','applied_owned_fill_anchor'):setattr(fake,name,helper_env[name])
    s,r,initial,unused=fresh_init_fixture(code,tmp_path)
    m=money_source();code.env['LivePerpsMoneyView']=m.LivePerpsMoneyView
    code.env['OrderSide']=SIDE
    s._candidate=Candidate(**json.loads((ROOT.parent/'configs/hl-live-v3-dp50.candidate.json').read_text())['candidate'])
    s.config.live_account_mode='unifiedAccount';s.config.live_equity_basis=EQUITY_BASIS
    s._live_account_mode='unifiedAccount'
    s._deposit=DepositProtection(limit_percent=55)
    now=time.time_ns();start=now//1_000_000-1000
    assets=(m.SelectedCrossAsset('BTC',20,D(100),(D(100),D(100)),(D(1000),D(1000))),
        m.SelectedCrossAsset('SOL',20,D(200),(D(100),D(100)),(D(1000),D(1000))))
    initial=m.LivePerpsMoneyView(ACCOUNT,'',now//1_000_000,D(82),D(82),D(0),D(82),assets,(),r.native_revision(),account_mode='unifiedAccount',equity_basis=EQUITY_BASIS)
    s.initialize_clean_flat_c1_epoch(initial,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,
        history_anchor_ms=start,cashflow_page=dict(start_ms=start,end_ms=start+1,rows=[],complete=True,expected_cursor=None))
    s._active_c1_authorized=True;s._manage_only_preparation=False;s.recovery_confirmed=True
    s._domain=WaveOverlayState(s._candidate);s._domain.episode=Episode('episode',1,82,1,wave_levels=(.01,.02,.03))
    s._pending_by_order={};s._seen_trade_ids=set();s._c1_fill_epoch=2;s._live_inputs_dirty=False
    s._recovery_health=None;s._live_input_ws_epoch=lambda:4
    account=N(id=ACCOUNT_ID,base_currency=None,last_event=N(id='native-account'),
        balance_total=lambda currency:Cash(82),balance_free=lambda currency:Cash(62),
        margin_init_for_currency=lambda currency:Cash(20),margin_maint_for_currency=lambda currency:Cash(20))
    orders=[];rawfills=[];cloids={};statuses={}
    for index,quantity in enumerate(('4','6'),1):
        client='ENTRY'+str(index);cloid='0x'+str(index)*32;cloids[client]=cloid;oid=str(100+index);tid=str(100+index)
        intent=s._domain._intent(s._domain.episode,'BTC_ENTRY',1,None,quantity=float(quantity))
        r.record_submission(client_order_id=client,intent_id=intent.id,episode_id='episode',action='BTC_ENTRY',
            instrument_id=str(s.config.btc_id),quantity=quantity,reduce_only=False,strategy_state=s.on_save()[code.env['_KEY']],
            order_shape=dict(side='BUY',kind='MARKET',tif='IOC',post_only=False,price=None))
        ts=(start+100)*1_000_000  # Same genuine venue millisecond retains both IDs.
        event=Fill(ACCOUNT_ID,s.config.btc_id,oid,tid,SIDE.BUY,Q.from_str(quantity),Q.from_str('100'),
            Cash('.01'),LIQ.TAKER,'event'+tid,ts,ts+1000,client_order_id=client)
        r.record_native_fill(trade_id=tid,native_event_id=event.id,client_order_id=client,venue_order_id=oid,
            instrument_id=str(s.config.btc_id),order_side='BUY',quantity=quantity,price='100',
            commission_amount='.01',commission_currency='USDC',liquidity_side='TAKER',ts_event_ns=ts,ts_init_ns=ts+1000)
        s._domain.on_fill(intent.id,float(quantity),100,__import__('datetime').datetime.now(__import__('datetime').timezone.utc),None,decision_index=0)
        s._seen_trade_ids.add(tid)
        r.commit_applied_fills([tid],s.on_save()[code.env['_KEY']]);r.terminal_submission(client,s.on_save()[code.env['_KEY']])
        native=N(client_order_id=client,venue_order_id=oid,instrument_id=s.config.btc_id,strategy_id=str(s.id),
            account_id=ACCOUNT_ID,side=SIDE.BUY,quantity=Q.from_str(quantity),filled_qty=Q.from_str(quantity),
            is_reduce_only=False,is_closed=True,is_pending_cancel=False,is_post_only=False,has_price=False,
            order_type=TYPE.MARKET,time_in_force=TIF.IOC,status=STATUS.FILLED,trade_ids=[tid],events=[event])
        orders.append(native)
        rawfills.append(dict(tid=int(tid),oid=int(oid),coin='BTC',side='B',sz=quantity,px='100',fee='.01',feeToken='USDC',crossed=True,hash='0x'+tid,time=ts//1_000_000))
        statuses[cloid]=dict(status='order',order=dict(status='filled',statusTimestamp=start+101,
            order=dict(cloid=cloid,oid=int(oid),coin='BTC',side='B',origSz=quantity,sz='0',limitPx='100',
                reduceOnly=False,orderType='Limit',tif='Ioc',timestamp=start+50)))
    # Native journal baseline17, reached through existing event recording, not relaxed guards.
    while r.native_revision()<17:r.record_native_event('owned-status-'+str(r.native_revision()),'order')
    assert r.native_revision()==17
    position=N(instrument_id=s.config.btc_id,id='owned-position',is_long=True,quantity=Q.from_str('10'),
        strategy_id=str(s.id),account_id=ACCOUNT_ID,events=[o.events[0] for o in orders],ts_opened=(start+100)*1_000_000)
    instruments={coin:N(id=iid,size_precision=0,price_precision=0,size_increment=Q.from_str('1')) for coin,iid in [('BTC',s.config.btc_id),('SOL',s.config.sol_id)]}
    cache=N(orders=lambda venue=None:orders,positions_open=lambda:[position],orders_open=lambda:[],orders_inflight=lambda:[],
        account_for_venue=lambda venue:account,instrument=lambda iid:next(i for i in instruments.values() if i.id==iid))
    s.cache=cache
    pyo=N(ClientOrderId=str,hyperliquid_cloid_from_client_order_id=lambda client:cloids[client])
    env=dict(asyncio=asyncio,time=time,hashlib=hashlib,json=json,replace=replace,deque=deque,Decimal=D,
        IncompleteInfoReport=IncompleteInfoReport,nautilus_pyo3=pyo,OrderStatus=STATUS,OrderDenied=type('Denied',(),{}),
        InstrumentId=ID,RecoverableWaveOverlayStrategy=code.Strategy,live_perps_money_view=m.live_perps_money_view,
        durable_decision_checkpoint=code.env['durable_decision_checkpoint'])
    run_ast(nodes('ops/hl_live_execution.py',{'QualifiedInfoBoundary','SingleAttemptInfoTransport','_native_order_fingerprint','_proven_local_denial','bind_clean_flat_live_handover'}),env)
    report_env=dict(defaultdict=defaultdict,Decimal=D,InfoReceipt=InfoReceipt,IncompleteInfoReport=IncompleteInfoReport,
        nautilus_pyo3=pyo,USDC='USDC',UUID4=lambda:'pure-id',OrderSide=SIDE,OrderStatus=STATUS,OrderType=TYPE,
        TimeInForce=TIF,LiquiditySide=LIQ,PositionSide=POS,ClientOrderId=str,VenueOrderId=str,TradeId=str,
        Quantity=Q,Price=Q,Money=Cash,FillReport=Fill,OrderStatusReport=OrderReport,PositionStatusReport=PositionReport,ExecutionMassStatus=Mass)
    run_ast(nodes('ops/hl_qualified_reports.py',{'_precise','_same_generation','qualified_mass_status'}),report_env)
    Boundary=env['QualifiedInfoBoundary']
    class Client(Boundary):
        def recovery_healthy(self):return self._cm_ws_failure is None
        def _cm_transport_ok(self):return self._cm_ws_failure is None
        def request_effect_parity_refresh(self):return False
        def bind_recovery_revocation(self,fn):self.revoke=fn
        def bind_recovery_suspension(self,suspend,resume):self.suspend=suspend;self.resume=resume
        async def release_after_effect_parity(self,verify,**kwargs):
            self.verify_current_risk_epoch=verify
            assert await verify(self.mass) is True
    client=Client();client._cm_runtime=r;client._cm_scope=helper_env['NativeLiveRecoveryScope'](ACCOUNT,'',start,None,(),frozenset({'BTC','SOL'}))
    client._cm_bootstrapped=True;client._cm_inputs_enabled=True;client._cm_unified=True;client._cm_strategy=s
    client._cache=cache;client._msgbus=s.msgbus;client.trader_id=s.trader_id;client.venue=VENUE;client.account_id=ACCOUNT_ID
    client._clock=N(timestamp_ns=time.time_ns);client._cm_ws_epoch=4;client._cm_ws_failure=None
    client._cm_account_context={};client._cm_last_margin_assets=assets;client._cm_last_revision=17
    client._cm_generation_started_ns=time.monotonic_ns();client._cm_last_generation_bound=413
    client._cm_next_money_request=0
    calls=[];fault={}
    async def transport(body):
        calls.append(dict(body));kind=body['type']
        if kind=='frontendOpenOrders':return []
        if kind=='clearinghouseState':return state('10','0') if body.get('dex','')=='' else state('0','0')
        if kind=='spotClearinghouseState':return spot('82','20')
        if kind=='orderStatus':return statuses[body['oid']]
        if kind=='userFillsByTime':
            rows=[dict(f) for f in rawfills if body['startTime']<=f['time']<=body['endTime']]
            sweep=sum(q['type']=='userFillsByTime' for q in calls)
            if fault.get('missing_sweep')==sweep:rows=[f for f in rows if f['tid']!=101]
            if fault.get('raw_change'):
                key,value=fault['raw_change'];rows[0][key]=value
            if fault.get('saturated'):rows=[dict(rows[0]) for _ in range(2000)]
            return rows
        if kind=='userNonFundingLedgerUpdates':return []
        raise AssertionError(kind)
    async def source_read_info(body,**kwargs):return await transport(body)
    env['read_info_http']=source_read_info
    client._cm_info=env['SingleAttemptInfoTransport'](testnet=False,timeout=1)
    env['QualifiedInfoBoundary']=Boundary
    context=dict(master_role='user',mode='unifiedAccount',dex_abstraction=False,dex_names=('', 'xyz'),
        verified_at_ns=time.monotonic_ns(),mode_observed_at_ns=time.monotonic_ns())
    async def collect():
        scope,revision,native,applied,signature=client._cm_owned_scope()
        receipts=[]
        for end in (time.time_ns()//1_000_000-2,time.time_ns()//1_000_000-1):
            receipts.append(await collect_info_receipt(transport,account=ACCOUNT,dex='',anchor_ms=scope.anchor_ms,
                anchor_tid=scope.anchor_tid,fill_anchor_ms=scope.fill_anchor_ms,fill_anchor_fingerprint=scope.fill_anchor_fingerprint,
                end_ms=end,expected_orders={c:o for _,c,o in scope.durable_orders},owned_coins=scope.owned_coins,
                require_money_scope=True,account_mode='unifiedAccount',account_context=context,allow_fill_subdivision=False))
        mass=report_env['qualified_mass_status'](*receipts,expected_account_ref=ACCOUNT,expected_dex='',account_id=ACCOUNT_ID,
            client_id='client',venue=VENUE,instruments=instruments,durable_orders={k:(c,o) for k,c,o in scope.durable_orders},
            native_orders=native,applied_trade_ids=applied,ts_init=time.time_ns())
        client._cm_last_receipt=receipts[-1];client._cm_last_revision=revision;client.mass=mass
        client._cm_cashflow_page=await client._cm_collect_cashflow_page(transport)
        return scope,receipts,mass
    ctx=N(s=s,r=r,client=client,orders=orders,position=position,account=account,rawfills=rawfills,statuses=statuses,
        collect=collect,env=env,report_env=report_env,calls=calls,start=start,code=code,
        fault=fault,transport=transport,context=context)
    yield ctx
    r.close()

def publish(ctx):
    ctx.env['bind_clean_flat_live_handover'](ctx.client,ctx.s,ctx.r)
    asyncio.run(ctx.s._post_drain_verifier())

def test_complete_first_held_chain_two_sweeps_cashflow_revision17_and_money_publication(chain):
    c=chain;scope,receipts,mass=asyncio.run(c.collect())
    assert scope.anchor_ms==c.start and scope.fill_anchor_ms==c.start+100 and scope.anchor_tid==101
    assert c.client._cm_scope.anchor_tid is None # Local candidate is not promoted authority.
    assert all(r.start_ms==c.start and r.fill_anchor_fingerprint==scope.fill_anchor_fingerprint for r in receipts)
    assert [q['startTime'] for q in c.calls if q['type']=='userFillsByTime']==[c.start,c.start]
    assert c.r.db.execute('SELECT body FROM live_info_checkpoint').fetchone() is None
    publish(c)
    assert c.r.native_revision()==17 and c.s._validated_live_money().equity==D(82)
    assert c.s._validated_live_money().native_revision==17
    old=json.loads(c.r.db.execute('SELECT body FROM live_info_checkpoint').fetchone()[0])
    assert old['start_ms']==c.start and old['fill_anchor_ms']==c.start+100 and old['anchor_tid']==101
    assert len(old['fills'])==2 and c.r.c1_initialization()['history_anchor_ms']==c.start
    assert c.r.evidence_cursor('userNonFundingLedgerUpdates')['end_ms']>=c.start
    assert c.r.info_query_evidence({},c.r.applied_fill_ids(),anchor_proof=(101,scope.fill_anchor_ms,scope.fill_anchor_fingerprint))[1]

def no_promotion(c):
    assert c.r.db.execute('SELECT body FROM live_info_checkpoint').fetchone() is None
    if c.s._live_money_provider is not None:
        with pytest.raises((ValueError,RuntimeError)):c.s._validated_live_money()

@pytest.mark.parametrize('fault',['missing_details','foreign_account','foreign_instrument','unknown_ack','sql_fee','sql_liquidity','missing_event_id'])
def test_candidate_requires_complete_applied_owned_exact_native_details(chain,fault):
    c=chain
    if fault=='missing_details':c.r.db.execute("DELETE FROM paper_native_fill_details WHERE trade_id='101'")
    elif fault=='foreign_account':c.orders[0].account_id='foreign'
    elif fault=='foreign_instrument':c.r.db.execute("UPDATE paper_native_fill_details SET instrument_id='FOREIGN' WHERE trade_id='101'")
    elif fault=='unknown_ack':c.orders[0].venue_order_id=None
    elif fault=='sql_fee':c.r.db.execute("UPDATE paper_native_fill_details SET commission_amount='.02' WHERE trade_id='101'")
    elif fault=='sql_liquidity':c.r.db.execute("UPDATE paper_native_fill_details SET liquidity_side='MAKER' WHERE trade_id='101'")
    elif fault=='missing_event_id':c.r.db.execute("UPDATE paper_native_fill_details SET native_event_id=NULL WHERE trade_id='101'")
    c.r.db.commit()
    with pytest.raises((ValueError,TypeError)):asyncio.run(c.collect())
    no_promotion(c)

def test_unapplied_fill_not_selected_and_whole_chain_denies_uncommitted_prefix(chain):
    c=chain;c.r.db.execute("DELETE FROM paper_recovered_fills WHERE trade_id='101'");c.r.db.commit()
    scope,receipts,mass=asyncio.run(c.collect())
    assert scope.anchor_tid==102 and scope.fill_anchor_ms==c.start+100
    with pytest.raises(IncompleteInfoReport,match='LIVE_OWNED_FILL_PARITY_FAILED'):publish(c)
    no_promotion(c)

@pytest.mark.parametrize('sweep',[1,2])
def test_anchor_must_exist_in_each_actual_inclusive_sweep(chain,sweep):
    c=chain;c.fault['missing_sweep']=sweep
    with pytest.raises(IncompleteInfoReport,match='ANCHOR_NOT_RETAINED'):asyncio.run(c.collect())
    no_promotion(c)

@pytest.mark.parametrize('field,value',[('px','101'),('sz','3'),('fee','.02'),('feeToken','USD'),('crossed',False),('side','A'),('time',0)])
def test_both_raw_sweeps_cannot_override_native_anchor_economics(chain,field,value):
    c=chain;c.fault['raw_change']=(field,value)
    with pytest.raises((IncompleteInfoReport,ValueError)):asyncio.run(c.collect())
    no_promotion(c)

def test_saturated_page_denies_without_second_window_or_authority(chain):
    c=chain;c.fault['saturated']=True
    with pytest.raises(IncompleteInfoReport,match='SATURATED'):asyncio.run(c.collect())
    assert len([q for q in c.calls if q['type']=='userFillsByTime'])==1
    no_promotion(c)

@pytest.mark.parametrize('movement',['native_revision','oldest_deadline','ws_gap','policy','external_cashflow'])
def test_complete_chain_does_not_publish_after_final_generation_movement(chain,movement):
    c=chain;asyncio.run(c.collect())
    if movement=='native_revision':c.r.record_native_event('after-full','order')
    elif movement=='oldest_deadline':c.client._cm_generation_started_ns=time.monotonic_ns()-9_000_000_001
    elif movement=='ws_gap':c.client._cm_ws_failure='WS_GAP'
    elif movement=='policy':c.s.config.execution_policy_hash='changed'
    elif movement=='external_cashflow':
        c.client._cm_cashflow_page['rows']=[dict(time=c.client._cm_cashflow_page['end_ms'],hash='0xnewcash',delta=dict(type='deposit',usdc='1'))]
    with pytest.raises((IncompleteInfoReport,ValueError,RuntimeError)):publish(c)
    no_promotion(c)
    if movement=='external_cashflow':assert c.r.cashflow_quarantined()

@pytest.mark.parametrize('field,value',[('fill_anchor_ms',1),('fill_anchor_fingerprint','0'*64)])
def test_same_generation_binds_candidate_timestamp_and_native_fingerprint(chain,field,value):
    c=chain;scope,receipts,mass=asyncio.run(c.collect())
    second=replace(receipts[1],**{field:value})
    with pytest.raises(IncompleteInfoReport,match='GENERATION'):c.report_env['_same_generation'](receipts[0],second)
    no_promotion(c)

def test_original_legacy_anchor_time_contract_is_not_relaxed(chain):
    c=chain;scope,*unused=c.client._cm_owned_scope()
    with pytest.raises(IncompleteInfoReport,match='ANCHOR_NOT_RETAINED'):
        asyncio.run(collect_info_receipt(c.transport,account=ACCOUNT,dex='',anchor_ms=c.start,anchor_tid=101,
            end_ms=time.time_ns()//1_000_000,expected_orders={cloid:oid for _,cloid,oid in scope.durable_orders},
            owned_coins=scope.owned_coins,require_money_scope=True,account_mode='unifiedAccount',
            account_context=c.context,allow_fill_subdivision=False))
    no_promotion(c)

def test_restart_rederives_candidate_but_never_reuses_checkpoint_as_authority(chain):
    c=chain;scope,receipts,mass=asyncio.run(c.collect());publish(c)
    rebuilt=c.code.management['durable_management_scope'](c.r,ACCOUNT,'',lambda client:'unused')
    assert rebuilt.anchor_ms==c.start and rebuilt.anchor_tid is None and rebuilt.fill_anchor_ms is None
    c.client._cm_scope=rebuilt;c.client._cm_bootstrapped=False
    next_scope,*unused=c.client._cm_owned_scope()
    assert next_scope.anchor_ms==scope.anchor_ms and next_scope.fill_anchor_fingerprint==scope.fill_anchor_fingerprint
    old=json.loads(c.r.db.execute('SELECT body FROM live_info_checkpoint').fetchone()[0])
    assert c.r.info_query_evidence({},c.r.applied_fill_ids(),anchor_proof=(101,scope.fill_anchor_ms,'0'*64))==({},(),None,None)
    old['fill_anchor_ms']+=1
    c.r.db.execute('UPDATE live_info_checkpoint SET body=?',(json.dumps(old),));c.r.db.commit()
    with pytest.raises(ValueError,match='ARCHIVED_ANCHOR_INVALID'):
        c.r.info_query_evidence({},c.r.applied_fill_ids(),anchor_proof=(101,scope.fill_anchor_ms,scope.fill_anchor_fingerprint))
