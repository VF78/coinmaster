"""Descriptive closed-inventory fill cashflows. No strategy import/engine/replay."""
import ast, csv, json, hashlib
from pathlib import Path
from decimal import Decimal as D, getcontext
from datetime import datetime, timezone
getcontext().prec=45
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
OLD=ROOT/'reports/sol-conditional-hedge-btc-band-20261023'
hashes={}
def load(name):
    p=OLD/name;hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return list(csv.DictReader(p.open()))
def save(name,rows):
    with (OUT/('attribution-'+name+'.csv')).open('w') as f:
        w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def utc(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
def timestamp(s):
    if s.isdigit():return int(s)
    return int(datetime.fromisoformat(s).timestamp()*1e9)
def normalize(rows):
    result=[]
    for i,row in enumerate(rows):
        commissions=ast.literal_eval(row['commissions']);fee=D(0)
        for item in commissions:
            amount,currency=item.rsplit(' ',1);assert currency=='USDT';fee+=D(amount)
        q=D(row['filled_qty']);px=D(row['avg_px']);sign=1 if row['side']=='BUY' else -1
        assert row['side'] in ['BUY','SELL']
        result.append(dict(index=i,asset=row['instrument_id'].split('USDT')[0],ns=timestamp(row['ts_last']),utc=utc(timestamp(row['ts_last'])),qty=q,sign=sign,px=px,fee=fee,signed_quantity=sign*q,cashflow=-sign*q*px,reduce=row['is_reduce_only']=='True',client_order_id=row['client_order_id']))
    return sorted(result,key=lambda r:(r['ns'],r['index']))
S=normalize(load('verifier-reference-fills.csv'));B=normalize(load('owner-BTC_REGIME_REENTRY_BAND_05-events/native-fills.csv'))
comparison={r['recipe']:r for r in load('comparison.csv')}
calendar=load('owner-sizing-calendar.csv')
parents={name:sorted([r for r in calendar if r['recipe']==recipe],key=lambda r:int(r['candidate_start_ns'])) for name,recipe in [('S0','S0'),('B','BTC_REGIME_REENTRY_BAND_05')]}
checks={};assets=[];bridges=[]
for name,rows in [('S0',S),('B',B)]:
    total_net=D(0)
    for asset in ['BTC','SOL']:
        a=[r for r in rows if r['asset']==asset]
        q=sum((r['signed_quantity'] for r in a),D(0));gross=sum((r['cashflow'] for r in a),D(0));fees=sum((r['fee'] for r in a),D(0));net=gross-fees
        checks[name+'_'+asset+'_terminal_inventory_flat']=q==0
        assets.append(dict(recipe=name,asset=asset,native_filled_order_rows=len(a),signed_terminal_quantity=q,confirmed_fill_gross_cashflow=gross,native_fees=fees,confirmed_fill_net_ex_funding=net,basis='CLOSED_INVENTORY_SUM_SELL_NOTIONAL_MINUS_BUY_NOTIONAL_MINUS_COMMISSIONS',native_asset_net_export='NOT_EXPORTED',signed_asset_funding='UNKNOWN'))
        total_net+=net
    reference=comparison['S0_ARCHIVE' if name=='S0' else 'BTC_REGIME_REENTRY_BAND_05'];total=D(reference['TOTAL']);bridge=total-D(10000)-total_net
    checks[name+'_fee_exact']=sum((r['fee'] for r in rows),D(0))==D(reference['fees'])
    bridges.append(dict(recipe=name,native_TOTAL=total,seed=10000,net_profit=total-D(10000),confirmed_fill_net_ex_funding=total_net,unallocated_cash_bridge=bridge,signed_asset_funding='UNKNOWN',qualification='Residual is not identified funding; includes native funding and ledger/account/serialization basis until independently reconciled'))
save('asset-fill-cashflows',assets);save('cash-bridge',bridges)
episodes={}
for name,rows in [('S0',S),('B',B)]:
    groups=[];used=[];pp=parents[name]
    for i,parent in enumerate(pp):
        start=int(parent['candidate_start_ns']);end=int(pp[i+1]['candidate_start_ns']) if i+1<len(pp) else 10**30
        a=[r for r in rows if r['asset']=='BTC' and start<=r['ns']<end];used.extend(a)
        entries=[r for r in a if not r['reduce']];exits=[r for r in a if r['reduce']]
        Q=sum((r['qty'] for r in entries),D(0));gross=sum((r['cashflow'] for r in a),D(0));fees=sum((r['fee'] for r in a),D(0));net=gross-fees
        checks[name+'_parent_'+str(i+1)+'_flat']=sum((r['signed_quantity'] for r in a),D(0))==0
        checks[name+'_parent_'+str(i+1)+'_Q']=Q==D(parent['candidate_actual_filled_Q'])
        checks[name+'_parent_'+str(i+1)+'_no_direction_flip']=len(set(r['sign'] for r in entries))==1
        groups.append(dict(recipe=name,episode_number=i+1,episode_id=parent['candidate_episode_id'],start_utc=utc(start),end_utc=max(r['utc'] for r in exits),side=entries[0]['sign'],entry_Q=Q,exit_Q=sum((r['qty'] for r in exits),D(0)),entry_vwap=sum((r['qty']*r['px'] for r in entries),D(0))/Q,entry_fees=sum((r['fee'] for r in entries),D(0)),exit_fees=sum((r['fee'] for r in exits),D(0)),confirmed_fill_gross=gross,native_fees=fees,confirmed_fill_net_ex_funding=net,net_per_entry_unit=net/Q,entry_order_rows=len(entries),exit_order_rows=len(exits),attribution='ACTUAL_CLOSED_PARENT_CASHFLOW_NOT_COUNTERFACTUAL'))
    checks[name+'_all_BTC_fills_partitioned']=len(used)==sum(r['asset']=='BTC' for r in rows) and len(set(r['index'] for r in used))==len(used)
    checks[name+'_BTC_group_net_reconciles']=sum((r['confirmed_fill_net_ex_funding'] for r in groups),D(0))==next(r['confirmed_fill_net_ex_funding'] for r in assets if r['recipe']==name and r['asset']=='BTC')
    episodes[name]=groups
save('BTC-parent-ledger',episodes['S0']+episodes['B'])
byday={name:{r['start_utc'][:10]:r for r in rows} for name,rows in episodes.items()}
matched=[]
for day,s in byday['S0'].items():
    if day not in byday['B']:continue
    b=byday['B'][day];qs,qb=s['entry_Q'],b['entry_Q'];us,ub=s['net_per_entry_unit'],b['net_per_entry_unit'];qpart=(qb-qs)*(ub+us)/2;upart=(ub-us)*(qb+qs)/2;delta=b['confirmed_fill_net_ex_funding']-s['confirmed_fill_net_ex_funding']
    checks['matched_'+day+'_identity']=abs(delta-qpart-upart)<D('1e-32')
    matched.append(dict(entry_day=day,S0_episode=s['episode_number'],B_episode=b['episode_number'],S0_side=s['side'],B_side=b['side'],S0_Q=qs,B_Q=qb,S0_unit_net_ex_funding=us,B_unit_net_ex_funding=ub,S0_net_ex_funding=s['confirmed_fill_net_ex_funding'],B_net_ex_funding=b['confirmed_fill_net_ex_funding'],net_delta=delta,symmetric_Q_component=qpart,symmetric_unit_component=upart,identity_residual=delta-qpart-upart,qualification='DESCRIPTIVE_TWO_ACTUAL_PATHS_SAME_UTC_ENTRY_DAY_NOT_CAUSAL_POLICY_PNL'))
save('matched_entry_attribution',matched)
aggregate=dict(matched_days=len(matched),delta=sum((r['net_delta'] for r in matched),D(0)),symmetric_Q_component=sum((r['symmetric_Q_component'] for r in matched),D(0)),symmetric_unit_component=sum((r['symmetric_unit_component'] for r in matched),D(0)))
delayed=[]
for sd,bd in [('2025-01-03','2025-01-04'),('2026-03-13','2026-03-16'),('2026-03-20','2026-03-22'),('2026-07-18','2026-07-21'),('2026-08-18','2026-08-19')]:
    s,b=byday['S0'][sd],byday['B'][bd]
    delayed.append(dict(S0_start=s['start_utc'],B_start=b['start_utc'],S0_Q=s['entry_Q'],B_Q=b['entry_Q'],S0_net_ex_funding=s['confirmed_fill_net_ex_funding'],B_net_ex_funding=b['confirmed_fill_net_ex_funding'],S0_end=s['end_utc'],B_end=b['end_utc'],qualification='CITED_TEMPORAL_PAIR_TWO_ACTUAL_DISTINCT_EPISODES_NOT_DELAY_ONLY_CAUSAL_PNL'))
save('cited-delay-pairs',delayed)
cycles=[]
for name,rows in [('S0',S),('B',B)]:
    current=[];position=D(0);number=0
    for row in (r for r in rows if r['asset']=='SOL'):
        if position==0:number+=1
        if position!=0:assert position*row['signed_quantity']>=0 or abs(row['signed_quantity'])<=abs(position)
        current.append(row);position+=row['signed_quantity']
        if position==0:
            cycles.append(dict(recipe=name,cycle=number,start=current[0]['utc'],end=current[-1]['utc'],fill_order_rows=len(current),gross=sum((r['cashflow'] for r in current),D(0)),fees=sum((r['fee'] for r in current),D(0)),net_ex_funding=sum((r['cashflow']-r['fee'] for r in current),D(0)),qualification='ACTUAL_ZERO_TO_ZERO_SOL_INVENTORY_CYCLE_EX_FUNDING'));current=[]
    assert not current
save('SOL-cycles',cycles)
early=[r for r in cycles if '2024-12-23'<=r['start'][:10]<='2024-12-31']
save('early-SOL',early)
doc=Path('/Users/vf/Downloads/Codex_B_50_90_Next_Experiments_20261023.txt')
hashes[str(doc)]=hashlib.sha256(doc.read_bytes()).hexdigest()
def cents(x):return x.quantize(D('.01'))
docchecks=[]
def claim(label,actual,expected):
    ok=cents(actual)==D(expected)
    docchecks.append(dict(claim=label,measured_exact=actual,document_cents=expected,cents_match=ok,qualification='Exact Decimal ledger value compared only at document precision'))
    checks['document_'+label]=ok
for name,asset,value in [('S0','BTC','5345694.49'),('B','BTC','3946306.01'),('S0','SOL','678661.21'),('B','SOL','631950.99')]:claim(name+'_'+asset+'_net',next(r['confirmed_fill_net_ex_funding'] for r in assets if r['recipe']==name and r['asset']==asset),value)
delta_assets={asset:next(r['confirmed_fill_net_ex_funding'] for r in assets if r['recipe']=='B' and r['asset']==asset)-next(r['confirmed_fill_net_ex_funding'] for r in assets if r['recipe']=='S0' and r['asset']==asset) for asset in ['BTC','SOL']}
claim('BTC_net_delta',delta_assets['BTC'],'-1399388.48');claim('SOL_net_delta',delta_assets['SOL'],'-46710.21')
claim('unallocated_bridge_delta',bridges[1]['unallocated_cash_bridge']-bridges[0]['unallocated_cash_bridge'],'-8974.28')
claim('gross_cashflow_delta',sum((r['confirmed_fill_gross_cashflow']*(1 if r['recipe']=='B' else -1) for r in assets),D(0)),'-1799936.11')
for field,value in [('delta','-705981.09'),('symmetric_Q_component','-709196.21'),('symmetric_unit_component','3215.12')]:claim('matched_'+field,aggregate[field],value)
for i,(x,y) in enumerate([('46092.34','-5426.91'),('658351.95','-262204.15'),('772145.16','-504557.97'),('707107.22','-329339.68'),('252667.68','778571.68')]):
    claim('delay_'+str(i+1)+'_S0',delayed[i]['S0_net_ex_funding'],x);claim('delay_'+str(i+1)+'_B',delayed[i]['B_net_ex_funding'],y)
for name,value in [('S0','176722.78'),('B','49370.36')]:claim('early_SOL_'+name,sum((r['net_ex_funding'] for r in early if r['recipe']==name),D(0)),value)
claim('early_SOL_delta',sum((r['net_ex_funding']*(1 if r['recipe']=='B' else -1) for r in early),D(0)),'-127352.42')
save('document-claims',docchecks)
checks['matched_count_51']=len(matched)==51
checks['S0_BTC_parent_count_105']=len(episodes['S0'])==105
checks['B_BTC_parent_count_77']=len(episodes['B'])==77
checks['S0_SOL_cycles_reconcile']=sum((r['net_ex_funding'] for r in cycles if r['recipe']=='S0'),D(0))==next(r['confirmed_fill_net_ex_funding'] for r in assets if r['recipe']=='S0' and r['asset']=='SOL')
checks['B_SOL_cycles_reconcile']=sum((r['net_ex_funding'] for r in cycles if r['recipe']=='B'),D(0))==next(r['confirmed_fill_net_ex_funding'] for r in assets if r['recipe']=='B' and r['asset']=='SOL')
assert all(checks.values()),{k:v for k,v in checks.items() if not v}
summary=dict(source_S0='75ffc9c69e9d79c4da4cd0614634a3eeba48d716',source_B='25a085f596292df58e51188dd91e996adbe5724c',matched=aggregate,early_SOL={name:sum((r['net_ex_funding'] for r in early if r['recipe']==name),D(0)) for name in ['S0','B']},no_native_run=True,signed_asset_funding='UNKNOWN',selfchecks_passed=len(checks),selfchecks=checks,input_sha256=hashes)
(OUT/'attribution-summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['selfchecks','input_sha256']},indent=2,default=str))
