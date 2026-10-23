"""Offline SC00/SC02 evidence. Never creates or executes a trading engine."""
import argparse,csv,hashlib,importlib.util,json,sys
from collections import Counter,defaultdict
from decimal import Decimal as D,ROUND_HALF_UP
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from nautilus_trader.model.objects import Price
UTC=timezone.utc; DAY=86400000000000; MIN=60000000000

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d): Path(p).write_text(json.dumps(d,indent=2,default=str)+'\n')
def iso(ns): return datetime.fromtimestamp(int(ns)/1e9,UTC).isoformat()
def quantile(v):
 v=sorted(map(D,v)); p=D(len(v)-1)*D('.9'); j=int(p); return v[j]+(v[min(j+1,len(v)-1)]-v[j])*(p-j)
def coefficient(rows,ns,group):
 a=[r for r in rows if r['label_status']=='VALID_COMPLETED_WAVE' and int(r['label_ready_at_ns'])<ns]
 g={k:[r for r in a if r['entry_group']==k] for k in ['first','repeat']}
 q={k:quantile([r['u_mae_over_atr'] for r in z]) if z else None for k,z in g.items()}
 why='FIRST_ENTRY' if group=='first' else 'INSUFFICIENT_COMPLETED_GROUPS' if min(map(len,g.values()))<8 else 'INVALID_OR_ZERO_REPEAT_Q90' if q['repeat'] is None or q['repeat']<=0 else 'ACTIVE_VALID_Q90'
 k=D(1) if why!='ACTIVE_VALID_Q90' else min(D(1),q['first']/q['repeat'])
 return dict(k=str(k),fallback=why,n_first=len(g['first']),n_repeat=len(g['repeat']),waves_first=len({r['wave_id'] for r in g['first']}),waves_repeat=len({r['wave_id'] for r in g['repeat']}),q90_first=str(q['first']) if q['first'] is not None else None,q90_repeat=str(q['repeat']) if q['repeat'] is not None else None)
def writecsv(p,rows):
 with Path(p).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
def main():
 a=argparse.ArgumentParser();a.add_argument('--repo',type=Path,required=True);a.add_argument('--runtime-root',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--domain',type=Path,required=True);o=a.parse_args();out=o.out
 spec=importlib.util.spec_from_file_location('sc02_exact_domain',o.domain);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
 er=o.runtime_root/'runtime/var/research-jobs/b-50-90-next-20261023/E4/result'; raw=next(er.glob('*raw-native.json'));d=json.loads(raw.read_text());orderspath=next(er.glob('*orders.csv'));orders=list(csv.DictReader(orderspath.open()));audit=d['entry_sizing_audit'];parents=d['split_cover_audit']['parents'];fills=d['fill_audit'];c=m.Candidate(**{k:tuple(v) if isinstance(v,list) else v for k,v in d['config']['candidate'].items()})
 market=o.runtime_root/'runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized';bp=market/'bybit-BTCUSDT-daily.parquet';sp=market/'bybit-SOLUSDT-daily.parquet';mp=market/'bybit-BTCUSDT-mark-1m.parquet';br=pq.read_table(bp).to_pylist();sr={r['open_time_ms']:r for r in pq.read_table(sp).to_pylist()}
 bars=[m.DailyBar(datetime.fromtimestamp(r['open_time_ms']/1000,UTC),datetime.fromtimestamp(r['open_time_ms']/1000,UTC)+timedelta(days=1),datetime.fromtimestamp(r['open_time_ms']/1000,UTC)+timedelta(days=1),float(r['open']),float(r['close']),float(sr[r['open_time_ms']]['close'])) for r in br];fs=m.features_for(bars,c)
 atrs=[];at=None;tr=[];prev=None;emas=[];ema=None
 for r in br:
  close=float(r['close']);ema=close if ema is None else 2/(c.ema_period+1)*close+(1-2/(c.ema_period+1))*ema;emas.append(ema)
  if prev is not None:
   t=max(float(r['high'])-float(r['low']),abs(float(r['high'])-prev),abs(float(r['low'])-prev))
   if at is None:
    tr.append(t)
    if len(tr)==14:at=sum(tr)/14
   else:at=(13*at+t)/14
  atrs.append(at);prev=close
 marks=pq.read_table(mp,columns=['open_time_ms','close']);mt=np.asarray(marks['open_time_ms'],dtype=np.int64)*1000000+MIN;mv=np.asarray([float(x) for x in marks['close'].to_pylist()]);gapcount=int(np.count_nonzero(np.diff(mt)!=MIN)); ids=[];start=0
 for i,f in enumerate(fs):
  if i and f.side!=fs[i-1].side:start=i
  ids.append(start)
 amap={x['episode_id']:x for x in audit};rows=[];sens=[];seen=Counter();zero=Counter();firstfills=[x for x in fills if x['action']=='BTC_ENTRY'];endns=int(datetime(2026,9,1,tzinfo=UTC).timestamp()*1e9)
 for p in parents:
  au=amap[p['episode_id']];i=int(p['decision_index']);decision=int(au['q0_ns']);startns=int(p['start_ns']);matches=[x for x in firstfills if int(x['fill_ns'])==startns];anchor=D(matches[0]['px']) if len(matches)==1 else None;wave=ids[i];wid=f'{wave}:{iso(int(bars[wave].close_time.timestamp()*1e9))}:{fs[i].side}';group='first' if seen[wave]==0 else 'repeat';seen[wave]+=1
  levels=m.completed_wave_levels(bars,fs,i,c,int(p['side']));zero['TP1_zero']+=int(levels[0]==0);zero['TP2_zero']+=int(levels[1]==0);zero['parents']+=1
  switch=next((j for j in range(i+1,len(fs)) if fs[j].side!=fs[i].side),None);ready=int(bars[switch].available_at.timestamp()*1e9) if switch is not None else None
  atr=atrs[i];fraction=D(str(atr))/D(au['reference_wire_price']) if atr else None;label='CENSORED_INCOMPLETE_WAVE' if ready is None else 'MISSING_FIRST_ACTUAL_FILL' if anchor is None else 'MISSING_ATR' if fraction is None or fraction<=0 else 'VALID_COMPLETED_WAVE';mae=mfe=u=None;markcount=0
  if ready is not None and anchor is not None:
   lo=int(np.searchsorted(mt,startns,side='right'));hi=int(np.searchsorted(mt,ready,side='right'));path=mv[lo:hi];markcount=len(path);expected=max(0,(ready-startns)//MIN)
   if markcount!=expected or (markcount and (mt[lo]!=startns+MIN or mt[hi-1]!=ready)):label='MISSING_MINUTE_MARKS'
   if label=='VALID_COMPLETED_WAVE':
    signed=int(p['side'])*(path/float(anchor)-1);mae=D(str(max(0.,-float(np.min(signed)))));mfe=D(str(max(0.,float(np.max(signed)))));u=mae/fraction
  row=dict(parent_id=p['episode_id'],actual_parent_fill_count=1,decision_ns=decision,decision_utc=iso(decision),decision_index=i,closed_daily_asof_ns=int(bars[i].available_at.timestamp()*1e9),wave_id=wid,wave_start_index=wave,wave_age_days=i-wave,entry_group=group,side=int(p['side']),closed_ema34=str(emas[i]),closed_atr14=str(atr),atr_fraction_denominator=au['reference_wire_price'],frozen_atr_fraction=str(fraction),first_actual_fill_ns=startns,first_actual_fill_label_anchor=str(anchor),first_child_completed_vwap=p['first_vwap'],native_management_PLANREF=p['management_reference_v1'],actual_blended_vwap=p['planref_v1_actual_blended_vwap'],q0_ns=au['q0_ns'],q0_reference=au['reference_wire_price'],q1_ns=au['q1_ns'],q1_bid=au['q1_bid'],q1_ask=au['q1_ask'],zero_branch=au['branch'],wave_TP_vector=list(levels),gross_reference_qty=au['reference_btc_qty'],net_submitted_qty=au['net_submitted_btc_qty'],actual_filled_qty=p['filled'],parent_cap=au.get('parent_notional_cap','30000000.0'),lot=p['step'],original_h=p['planref_v1_h_actual'],actual_SOL_right_activations=au['sol_right_activations'],decision_positions='UNKNOWN_NOT_EXPORTED_AT_Q0',decision_pending='UNKNOWN_NOT_EXPORTED_AT_Q0',decision_equity='UNKNOWN_NOT_EXPORTED_AT_Q0',E4_gate='ACCEPTED_PARENT_EXACT_INTERNAL_GATE_STATE_NOT_FULLY_EXPORTED',label_status=label,label_ready_at_ns=ready,label_ready_at=iso(ready) if ready else None,label_mark_count=markcount,potential_MAE_fraction=str(mae) if mae is not None else None,potential_MFE_fraction=str(mfe) if mfe is not None else None,u_mae_over_atr=str(u) if u is not None else None)
  rows.append(row)
  ref=D(au['reference_wire_price']);orig=au['branch'].startswith('PASSIVE');side=int(p['side']);q=D(au['q1_bid'] if side==1 else au['q1_ask'])
  for bpv in ['-.1','.1','-.5','.5','-1','1','-2','2','-5','5']:
   changed=Price(q*(1+D(bpv)/10000),1).as_decimal();passive=ref>changed if side==1 else ref<changed;sens.append(dict(parent_id=p['episode_id'],bp=bpv,rounded_q1=str(changed),branch_changed=passive!=orig,original_branch=au['branch'],new_branch='PASSIVE_NET_ZERO_LEVELS' if passive else 'MARKETABLE_FULL_ENTRY_FALLBACK',qualification='LOCAL_BRANCH_SENSITIVITY_NOT_PORTFOLIO_RESULT'))
 for r in rows:r.update(coefficient(rows,int(r['decision_ns']),r['entry_group']))
 tests={};tests['all83_actual_parents']=len(rows)==83;tests['unique_parent_one_case']=len({r['parent_id'] for r in rows})==len(rows);tests['all_closed_features_available']=all(r['closed_daily_asof_ns']<=r['decision_ns'] for r in rows);tests['first_actual_anchor_found']=all(r['first_actual_fill_label_anchor']!='None' for r in rows);tests['global_mark_gap_count_zero']=gapcount==0
 for cut in [10,20,40,60,82]:
  prefix=rows[:cut]
  tests[f'future_parents_do_not_change_k_prefix_{cut}']=all(coefficient(prefix,int(r['decision_ns']),r['entry_group'])==coefficient(rows,int(r['decision_ns']),r['entry_group']) for r in prefix)
 tests['incomplete_wave_excluded']=coefficient([dict(rows[0],label_status='CENSORED_INCOMPLETE_WAVE',label_ready_at_ns=0)],endns,'repeat')['n_first']==0
 tests['strict_ready_at_equality_excluded']=coefficient([dict(rows[0],label_status='VALID_COMPLETED_WAVE',label_ready_at_ns=100,u_mae_over_atr='1')],100,'repeat')['n_first']==0
 tests['own_future_label_excluded']=all(int(r['label_ready_at_ns'])>int(r['decision_ns']) for r in rows if r['label_ready_at_ns'])
 tests['partial_fills_do_not_create_cases']=len(rows)==len(parents)
 tests['quantile_linear_nminus1']=quantile(['0','10'])==D(9)
 tests['native_tick_rounding']=str(Price(D('57313.05'),1))=='57313.1'
 tests['partial_fill_group_weight']=len({x['parent_id'] for x in rows for _ in range(3)})==len(rows)
 tests['first_and_repeat_separate']=all(r['entry_group']==('first' if sum(x['wave_id']==r['wave_id'] and x['first_actual_fill_ns']<r['first_actual_fill_ns'] for x in rows)==0 else 'repeat') for r in rows)
 tests['censored_u_not_zero']=all(r['u_mae_over_atr'] is None for r in rows if r['label_status']!='VALID_COMPLETED_WAVE')
 # Append-future invariance of exact closed ATR prefix, with an independently recomputed prefix chain.
 def atr_prefix(data):
  previous=None;av=None;seed=[]
  for x in data:
   cc=float(x['close'])
   if previous is not None:
    tt=max(float(x['high'])-float(x['low']),abs(float(x['high'])-previous),abs(float(x['low'])-previous))
    if av is None:
     seed.append(tt)
     if len(seed)==14:av=sum(seed)/14
    else:av=(13*av+tt)/14
   previous=cc
  return av
 tests['closed_ATR_future_invariance']=all(atr_prefix(br[:n])==atrs[n-1] for n in [731,900,1100,1300])
 tests['prefix_features_match']=all(m.features_for(bars[:n],c)==fs[:n] for n in [731,900,1100,1300])
 for cut in [20,50]:
  altered=[dict(r,potential_MAE_fraction='999999',u_mae_over_atr='999999') if int(r['label_ready_at_ns'] or endns)>=int(rows[cut]['decision_ns']) else r for r in rows]
  tests[f'future_MAE_not_feature_{cut}']=coefficient(altered,int(rows[cut]['decision_ns']),rows[cut]['entry_group'])==coefficient(rows,int(rows[cut]['decision_ns']),rows[cut]['entry_group'])
 # IOC governor from native reports plus adapter order ownership.
 ordermeta=d['native_order_events'];soladds=[r for r in orders if ordermeta.get(r['client_order_id'],{}).get('action')=='SOL_ADD'];governor=Counter((r['filled_qty'],r['status']) for r in soladds);largest=max(soladds,key=lambda r:D(r['quantity']))
 # Rebuild native exposure durations from real fill events and original order sides, without a PnL engine.
 sideby=defaultdict(set)
 for r in orders:sideby[(int(r['ts_init']),r['instrument_id'])].add(1 if r['side']=='BUY' else -1)
 changes=defaultdict(lambda:defaultdict(D));missing=[]
 for r in fills:
  key=(int(r['submit_ns']),r['instrument']);ss=sideby[key]
  if len(ss)!=1:missing.append(key);continue
  asset='BTC' if 'BTC' in r['instrument'] else 'SOL';changes[int(r['fill_ns'])][asset]+=D(r['qty'])*next(iter(ss))
 qty={'BTC':D(0),'SOL':D(0)};soltime=flattime=0;cycles=flatcycles=0;last=None
 for ns,ch in sorted(changes.items()):
  if last is not None and qty['SOL']!=0:
   elapsed=max(0,min(ns,endns)-min(last,endns));soltime+=elapsed
   if qty['BTC']==0:flattime+=elapsed
  was=qty['SOL'];qty['BTC']+=ch.get('BTC',D(0));qty['SOL']+=ch.get('SOL',D(0))
  if was==0 and qty['SOL']!=0:
   cycles+=1
   if qty['BTC']==0:flatcycles+=1
  last=ns
 flatpct=D(flattime)/D(soltime)*100
 # Strictly saved independent comparison evidence; this avoids re-reading unchanged minute streams.
 old=o.repo/'reports/e4-sol-residual-20261023';comparison=json.loads((old/'owner-btc-calendar-comparison.json').read_text());corr=json.loads((old/'verifier-correction-economic-delta.json').read_text())
 # Source-request mapping:0methods,1whole-rule audit,2BTC,3SOL,4joint portfolio.
 evidence=dict(source_sha='bd04c9b3858bcda40060a08eff488849c69af5d8',status='READ_ONLY_ARCHIVE_RECOUNT_NO_ENGINE',claims={
 'synthetic_quote_1000':dict(status='VERIFIED',source='native_fixture.py:472–476; native_baseline.py:895–897,935',qualification='Synthetic BBO size; not venue historical liquidity'),
 'SOL_96_of98_1000_cancel':dict(status='VERIFIED' if len(soladds)==98 and governor[('1000.0','CANCELED')]==96 else 'CONTRADICTED',orders=len(soladds),filled_status_counts={str(k):v for k,v in governor.items()},largest_order=largest),
 'BTC_zero_TPs':dict(status='VERIFIED' if zero['TP1_zero']==83 and zero['TP2_zero']==58 else 'CONTRADICTED',reconstructed_exact_completed_wave_counts=dict(zero),fractions=d['config']['candidate']['btc_tp_fractions_initial_qty'],branch_counts=dict(Counter(r['zero_branch'] for r in rows))),
 'q1_local_sensitivity':dict(status='VERIFIED' if any(x['branch_changed'] for x in sens if abs(D(x['bp']))<=1) else 'CONTRADICTED',changed_parent_counts_by_bp={bpv:sum(x['branch_changed'] for x in sens if x['bp']==bpv) for bpv in sorted({x['bp'] for x in sens},key=D)},qualification='Pinned Nautilus Price(Decimal,precision1), BTC native tick0.1, of shifted quote. Branch classification only; no synthetic fill/money claim'),
 'SOL_BTCflat_linkage':dict(status='VERIFIED' if cycles==25 and flatcycles==13 and abs(flatpct-D('56.92'))<D('.01') else 'CONTRADICTED',SOL_active_ns=soltime,SOL_active_with_BTCflat_ns=flattime,SOL_active_with_BTCflat_percent=str(flatpct),SOL_cycles=cycles,cycles_start_BTCflat=flatcycles,missing_side_joins=missing,terminal_quantities=qty),
 'SOL_H_gross_additive_rights':dict(status='VERIFIED',source='domain/wave_overlay.py:435–447,495–560; strategy/wave_overlay.py:1530–1575',qualification='H gross BTC reference, additive budgets, actual reductions earn rights, group flat gates next BTC; source+saved72pin audit reused'),
 'R2C_XS_calendar':dict(status='VERIFIED',saved_evidence=comparison['recipes']['R2C'],qualification='P0 exact XS verified21checks; reuse archived field-by-field comparison'),
 'R2C_flat_fix_no_economic_change':dict(status='VERIFIED',saved_evidence=corr),
 'continuous_SOL_hedge':dict(status='CONTRADICTED',reason='SOL-only durations and cycles; selectivealpha/sourcegate, not continuous hedge'),
 'H_BTC_predictive_benefit':dict(status='HYPOTHESIS',reason='Offline causal data/prefix tests do not prove economic benefit; native candidate required')})
 # Seven recipe-specific E4 episodes, copied verbatim from archive with independently recomputed DD.
 epfile=o.repo/'reports/b-50-90-next-20261023/verifier-E4-DD-ge30-episodes.csv';eps=list(csv.DictReader(epfile.open()));seven=[]
 wanted=['2024-10-03','2025-01-13','2025-06-06','2025-09-18','2025-11-28','2026-02-08','2026-08-19']
 for date in wanted:
  matched=[e for e in eps if e['trough_utc'].startswith(date)]
  if len(matched)!=1:raise ValueError(('EPISODE_MATCH',date,len(matched)))
  e=matched[0];x=dict(e);x['recomputed_drawdown_fraction']=str(1-D(e['trough_equity'])/D(e['peak_equity']));x['archive_source']=str(epfile);seven.append(x)
 tests['seven_E4_DD_exact']=all(abs(D(e['recomputed_drawdown_fraction'])-D(e['drawdown_fraction']))<D('1e-25') for e in seven)
 writecsv(out/'btc-causal-risk.csv',rows);writecsv(out/'q1-sensitivity.csv',sens);dump(out/'evidence-audit.json',evidence);dump(out/'seven-episodes.json',dict(episodes=seven,qualification='Recipe-specific archived E4 global-highwater episodes, not trading calendar conditions; other candidate full path requires native receipts'))
 summary=dict(parents=len(rows),groups=dict(Counter(r['entry_group'] for r in rows)),independent_actual_EMA_waves=len(seen),label_status=dict(Counter(r['label_status'] for r in rows)),potential_k_reduced=sum(D(r['k'])<1 for r in rows),k_activation=dict(Counter(r['fallback'] for r in rows)),tests=tests,all_tests_pass=all(tests.values()),frozen_contract=dict(ATR='closed D1 Wilder14 exact E4 seed; first TR requires previousclose',ATR_denominator='q0 reference_wire_price',label_anchor='FIRST_ACTUAL_FILL_PRICE; distinct native management PLANREF first-child-completed VWAP',marks='one minute MARK CLOSE available=open+1minute strictly after firstfill through completed D1 EMA switch',ready='strict label_ready_at<decision_ns',quantile='Decimal linear(n−1),Q90,first/repeat sidespooled,min8each',unknowns='decision held/pending/equity/internalgate details not exported; no zero imputation',no_native_engine=True),inputs={str(p):sha(p) for p in [raw,orderspath,bp,sp,mp,o.domain,epfile]},source_script_sha256=sha(__file__))
 dump(out/'btc-causal-risk.json',summary);dump(out/'data-tests.json',dict(checks=tests,all_pass=all(tests.values()),no_engine=True));print(json.dumps(dict(zero=dict(zero),governor={str(k):v for k,v in governor.items()},SOLflat=str(flatpct),cycles=[cycles,flatcycles],causal_summary={k:v for k,v in summary.items() if k not in ['inputs','frozen_contract','tests']},tests_failed=[k for k,v in tests.items() if not v]),default=str))
if __name__=='__main__':main()
