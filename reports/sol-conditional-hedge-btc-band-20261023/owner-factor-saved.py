"""Explicit v2 section5.5 FIXED-STATE mark diagnostic, never native TOTAL/PnL."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,json,hashlib,bisect,collections
import numpy as np
import pyarrow.parquet as pq
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021');OUT=ROOT/'reports/sol-conditional-hedge-btc-band-20261023';BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023');END=1788220800000000000
marks={}
for asset in ('BTC','SOL'):
    p=BASE/'inputs/data/normalized'/('bybit-'+asset+'USDT-mark-1m.parquet');t=pq.read_table(p,columns=['open_time_ms','close']);marks[asset]=(t['open_time_ms'].to_numpy()+60000,t['close'])
def px(asset,ns):
    keys,values=marks[asset];ms=ns//1000000;i=int(np.searchsorted(keys,ms));assert i<len(keys) and int(keys[i])==ms,(asset,ns);return D(values[i].as_py())
def to_ns(value):return int(value) if value.isdigit() else int(datetime.fromisoformat(value).timestamp())*1000000000
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,rows):
    p=OUT/name;keys=sorted({k for r in rows for k in r})
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    return dict(path=str(p),rows=len(rows),sha256=sha(p))
rows=[];latency=[];freezes=[];inputs=[]
for period,gamma,is_x in ((34,'0.5',False),(13,'0.5',False),(89,'0.5',False),(34,'1',False),(13,'1',False),(89,'1',False),(89,'1',True)):
    recipe='X_H4_4H_E89_G100_B05' if is_x else f'H4_4H_E{period}_G'+('050' if gamma=='0.5' else '100');receipt=json.loads((OUT/('owner-'+recipe+'-receipt.json')).read_text());path=Path(receipt['artifact']);d=json.loads(path.read_text());raw=json.loads(path.with_name(path.stem+'-raw-native.json').read_text());a=d['hedge_band_audit'];signals=[x for x in a if x['event']=='H4_SIGNAL'];sigkeys=[int(x['timestamp_ns']) for x in signals];acts={int(x['timestamp_ns']):x for x in a if x['event']=='H4_ACTIVATION'};firsts={int(x['timestamp_ns']):int(x['timestamp_ns'])-int(x['delay_ns']) for x in a if x['event']=='H4_FIRST_FILL'}
    sidekeys=collections.defaultdict(set);fallback=collections.defaultdict(set)
    for r in csv.DictReader(Path(d['execution_artifacts']['fills']['path']).open()):
        ns=to_ns(r['ts_last']);side=1 if r['side']=='BUY' else -1;action=raw['native_order_events'].get(r['client_order_id'],{}).get('action');sidekeys[(r['instrument_id'],ns,action)].add(side);fallback[(r['instrument_id'],ns)].add(side)
    fills=[]
    for i,f in enumerate(d['fill_audit']):
        ns=int(f['fill_ns']);values=sidekeys.get((f['instrument'],ns,f['action']),set()) or fallback[(f['instrument'],ns)];assert len(values)==1,(recipe,i,values);fills.append((ns,i,f,next(iter(values))))
    fills.sort();ft=collections.defaultdict(list)
    for x in fills:ft[x[0]].append(x)
    boundaries=sorted(set(sigkeys+[ns for ns,i,f,s in fills if ns>=sigkeys[0]]+[END]));btc=sol=D(0);beta=None;active_start=None;fillcursor=0;fees_at=collections.defaultdict(lambda:D(0));sol_inventory_after={}
    for ns,i,f,s in fills:
        if f['instrument'].startswith('SOL'):fees_at[ns]+=D(f['commission'])
    for n,start in enumerate(boundaries):
        end=boundaries[n+1] if n+1<len(boundaries) else start
        while fillcursor<len(fills) and fills[fillcursor][0]<=start:
            fns,i,f,side=fills[fillcursor];q=D(f['qty'])*side
            if f['instrument'].startswith('BTC'):btc+=q
            else:
                old=sol;sol+=q
                if old==0 and sol!=0:
                    assert fns in firsts,(recipe,fns,'missing first-fill causal activation');active_start=firsts[fns];beta=D(str(acts[active_start]['beta0']))
                if sol==0:beta=None;active_start=None
                sol_inventory_after[fns]=abs(sol)
            fillcursor+=1
        k=bisect.bisect_right(sigkeys,start)-1;signal=signals[k];pb0,ps0,pb1,ps1=px('BTC',start),px('SOL',start),px('BTC',end),px('SOL',end);rb=pb1/pb0-1;rs=ps1/ps0-1
        factor=residual=reference=D(0)
        if sol!=0:
            assert beta is not None
            factor=sol*ps0*beta*rb;residual=sol*ps0*(rs-beta*rb)
            if btc!=0:reference=-(D(1) if btc>0 else D(-1))*abs(sol)*ps0*beta*rb
        rows.append(dict(recipe=recipe,native_signal_timestamp_ns=int(signal['timestamp_ns']),signal_side=signal['side'],segment_start_ns=start,segment_end_ns=end,segment_seconds=(end-start)/1e9,actual_BTC_signed_quantity=str(btc),actual_SOL_signed_quantity=str(sol),frozen_activation_ns=active_start,beta0=str(beta) if beta is not None else None,BTC_mark_start=str(pb0),BTC_mark_end=str(pb1),SOL_mark_start=str(ps0),SOL_mark_end=str(ps1),BTC_mark_return=str(rb),SOL_mark_return=str(rs),factor_mark_contribution=str(factor),residual_mark_contribution=str(residual),matched_beta_BTC_reduction_reference_same_actual_mask=str(reference),actual_SOL_native_fee_at_segment_start=str(fees_at[start]),mask_reason='ACTUAL_NATIVE_SOL_HELD' if sol else 'NATIVE_SOL_FLAT_ZERO_MASK',diagnostic_basis='FIXED_NATIVE_QUANTITY_PATH_MARK_DECOMPOSITION_NOT_NATIVE_TOTAL',native_asset_PnL='UNKNOWN_NOT_EXPORTED',signed_funding='UNKNOWN',execution_mark_slippage_attribution='NOT_INCLUDED_FIXED_STATE_MARK_DIAGNOSTIC'))
    assert sol==0 and btc==0,(recipe,btc,sol)
    assert set(sigkeys)=={r['native_signal_timestamp_ns'] for r in rows if r['recipe']==recipe}
    orderedacts=sorted(acts)
    for j,start in enumerate(orderedacts):
        x=acts[start];stop=orderedacts[j+1] if j+1<len(orderedacts) else END;beta0=D(str(x['beta0']));pb,ps=px('BTC',start),px('SOL',start);ratio=D(gamma)*pb/(beta0*ps);assert ratio==D(x['r0']),(recipe,start,ratio,x['r0']);freezes.append(dict(recipe=recipe,activation_ns=start,beta0=str(beta0),PB0=str(pb),PS0=str(ps),r0_recorded=x['r0'],r0_from_pinned_accepted_marks=str(ratio),exact_r0_match=True,deadline_ns=x['deadline_ns']))
        target=next((D(z['target']) for z in a if z['event']=='H4_TARGET' and start<=int(z['timestamp_ns'])<stop),None);first=next((z for z in a if z['event']=='H4_FIRST_FILL' and int(z['timestamp_ns'])-int(z['delay_ns'])==start),None);half=next((z for z in a if z['event']=='H4_HALF_INITIAL_TARGET_FILL' and int(z['timestamp_ns'])-int(z['delay_ns'])==start),None);children=[z for z in a if z['event']=='H4_NATIVE_CHILD' and z.get('activation_ns')==start];terminals=[z for z in a if z['event']=='H4_NATIVE_CHILD_TERMINAL' and z.get('activation_ns')==start];denials=[z for z in d['pre_submit_tier_margin_gate_blocks'] if z['action']=='SOL_ADD' and start<=int(z['timestamp'])<min(stop,int(x['deadline_ns']))];filled_max=max((v for t,v in sol_inventory_after.items() if start<=t<min(stop,int(x['deadline_ns']))),default=D(0));full=next((t for t,v in sorted(sol_inventory_after.items()) if target is not None and start<=t<min(stop,int(x['deadline_ns'])) and v>=target),None)
        latency.append(dict(recipe=recipe,activation_ns=start,deadline_ns=x['deadline_ns'],original_initial_target=str(target) if target is not None else 'UNKNOWN_NOT_LOGGED_ZERO_TARGET',first_fill_ns=first['timestamp_ns'] if first else None,time_to_first_fill_seconds=int(first['delay_ns'])/1e9 if first else None,time_to_50_percent_original_target_seconds=int(half['delay_ns'])/1e9 if half else None,time_to_full_original_target_seconds=(full-start)/1e9 if full is not None else None,first_actual_native_terminal_ns=terminals[0]['timestamp_ns'] if terminals else None,last_actual_native_terminal_ns=terminals[-1]['timestamp_ns'] if terminals else None,time_to_last_native_terminal_seconds=(int(terminals[-1]['timestamp_ns'])-start)/1e9 if terminals else None,maximum_actual_SOL_before_deadline=str(filled_max),initial_target_underfill=str(max(D(0),target-filled_max)) if target is not None else None,native_child_proposals=len(children),actual_native_terminal_receipts=len(terminals),local_pre_submit_denials=len(denials),outcome='INITIAL_TARGET_ACTUALLY_REACHED' if full is not None else ('NO_FILL_LOCAL_ADMISSION_DENIED' if denials and not first else 'UNFILLED_OR_PARTIAL_TARGET'),no_target_shrink_relabel_of_original_half=True))
    inputs.append(dict(recipe=recipe,artifact=str(path),artifact_sha256=sha(path),signals=len(signals),activation_count=len(acts)))
exports=dict(factor=write('owner-factor-diagnostic.csv',rows),activation_marks=write('owner-activation-mark-freeze.csv',freezes),latency=write('owner-hedge-latency-shortfall.csv',latency))
(OUT/'owner-factor-manifest.json').write_text(json.dumps(dict(inputs=inputs,exports=exports,diagnostic_only=True,not_native_alternative_TOTAL=True,formula='SOL_signed_Q*PS_start*(beta0*rBTC) + SOL_signed_Q*PS_start*(rSOL-beta0*rBTC); matched BTC reduction=-BTCside*abs(SOLQ)*PS_start*beta0*rBTC; exact same actual native held mask',price_source='Unchanged pinned Bybit mark1m parquet; exact close availability at native events, no price fetch',funding='UNKNOWN_NO_RECONSTRUCTED_NATIVE_ASSET_NET',all_native_H4_signals_included=True,quantity_path='Actual confirmed native fills, no simulated fill/cash or economic optimizer',limitations='Fixed-state recorded mark diagnostic excludes mark-vs-execution price and signed funding; never compare as autonomous native TOTAL.'),ensure_ascii=False,indent=2)+'\n');print('FACTOR_SAVED_EXPORTS',len(rows),'rows',len(latency),'activations',flush=True)
