"""One engine-free public input builder for the seven approved SOL cases.

No order, fill, account or strategy state is synthesized here. prepare_case
constructs only native public market data; launch permission is separate.
"""
from pathlib import Path
from decimal import Decimal as D
import hashlib,json
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.identifiers import ClientId
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.venues.marks import venue_mark
from coinmaster.venues.signals import daily_signal
from coinmaster.strategy.next_band import next_closed_bar
from run_method_a_m1 import seed,SEED_SHA256

ASSETS={'BTC':BTC_PERP,'SOL':SOL_PERP}
SCHEMA='coinmaster.method-a-public-case.v1'


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def load_case(path):
    case=json.loads(Path(path).read_text())
    if case.get('schema')!=SCHEMA or case.get('case_id') not in tuple('M'+str(i) for i in range(2,9)):
        raise ValueError('SOL_CASE_ID_OR_SCHEMA')
    if case.get('risk_mode') not in ('HEDGE','TRIM') or case.get('cancel_latency_ns') not in (0,2_000_000_000):
        raise ValueError('SOL_CASE_MODE_OR_LATENCY')
    if case.get('funding_history')!='KNOWN_ZERO_8H_FEATURE_ONLY_W30':raise ValueError('SOL_CASE_FUNDING_DECLARATION')
    if not isinstance(case.get('selection_rows'),list) or not isinstance(case.get('required_witnesses'),list):raise ValueError('SOL_CASE_DECLARED_INPUTS')
    rows=case.get('rows');previous=-1
    if not rows:raise ValueError('SOL_CASE_EMPTY')
    for row in rows:
        ns=row['ns']
        if type(ns)is not int or ns<0 or ns<previous:raise ValueError('SOL_CASE_CLOCK')
        previous=ns
        marks=row.get('marks',{})
        if marks and set(marks)!={'BTC','SOL'}:raise ValueError('SOL_CASE_PAIRED_MARKS')
        for value in marks.values():
            if not D(value).is_finite() or D(value)<=0:raise ValueError('SOL_CASE_MARK')
        session=row.get('daily_session')
        if session is not None:
            if session not in (729,730) or ns!=int(seed()[session].close_time.timestamp()*1_000_000_000):raise ValueError('SOL_CASE_DAILY_CLOCK')
        if row.get('sol_daily_close_override') is not None and (session is None or not case.get('sol_feature_construction')):raise ValueError('SOL_CASE_UNDECLARED_FEATURE_OVERRIDE')
        for quote in row.get('quotes',[]):
            if quote['asset'] not in ASSETS:raise ValueError('SOL_CASE_QUOTE_ASSET')
            values=[D(quote[k]) for k in ('bid','ask','bid_depth','ask_depth')]
            if any(not x.is_finite() or x<=0 for x in values) or values[0]>values[1]:raise ValueError('SOL_CASE_QUOTE')
    if rows[-1]['ns']-rows[0]['ns']>172_800_000_000_000:raise ValueError('SOL_CASE_MATCHING_WINDOW')
    return case


def native_inputs(row):
    ns=row['ns'];groups=[];marks=row.get('marks',{})
    if marks:groups.append((ClientId('BYBIT_MARK'),[venue_mark(ASSETS[a].id,D(marks[a]),ns) for a in ('BTC','SOL')],True))
    if row.get('daily_session') is not None:
        day=seed()[row['daily_session']];sol=D(str(day.sol_close))
        if row.get('sol_daily_close_override') is not None:sol=D(row['sol_daily_close_override'])
        groups.append((ClientId('BYBIT_SIGNAL'),[daily_signal(i.id,D(str(o)),D(str(c)),D(str(c)),D(str(c)),ns) for i,o,c in ((BTC_PERP,day.btc_open,day.btc_close),(SOL_PERP,sol,sol))],False))
    if row.get('h4_btc_close') is not None:
        close=D(row['h4_btc_close']);groups.append((ClientId('BYBIT_SIGNAL'),[next_closed_bar(BTC_PERP.id,4,D('100'),D('100'),close,close,ns)],False))
    quotes=[]
    for q in row.get('quotes',[]):
        i=ASSETS[q['asset']]
        quotes.append(QuoteTick(i.id,i.make_price(D(q['bid'])),i.make_price(D(q['ask'])),i.make_qty(D(q['bid_depth'])),i.make_qty(D(q['ask_depth'])),ns,ns))
    if quotes:groups.append((None,quotes,True))
    return groups


def prepare_case(path):
    case=load_case(path);records=[];epochs={'BTC':0,'SOL':0}
    for row in case['rows']:
        for client,group,sort in native_inputs(row):
            for event in group:
                data=getattr(event,'data',event)
                record=dict(type=type(data).__name__,client=None if client is None else str(client),sort=sort,instrument=str(data.instrument_id),ts_event=data.ts_event,ts_init=data.ts_init)
                for name in ('price','open','high','low','close','hours','bid_price','ask_price','bid_size','ask_size'):
                    if hasattr(data,name):record[name]=str(getattr(data,name))
                if isinstance(data,QuoteTick):
                    asset=next(a for a,i in ASSETS.items() if i.id==data.instrument_id);epochs[asset]+=1
                    record.update(native_input_epoch=epochs[asset],global_input_index=sum(epochs.values()))
                records.append(record)
    return dict(schema=SCHEMA,case_id=case['case_id'],recipe_sha256=canonical(case),seed_sha256=SEED_SHA256,public_inputs=records,native_input_sha256=canonical(records),quote_universe=epochs,quote_count=sum(epochs.values()),engine_constructors=0,ready_to_launch=False)
