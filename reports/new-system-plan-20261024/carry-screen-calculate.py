#!/usr/bin/env python3
"""Saved-row funding addition only; no engine, lifecycle or new price outcomes."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
OLD=ROOT/'reports/market-redesign-20261024'
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized')
features=pd.read_csv(OLD/'native-analysis-sol-R3-features.csv'); original=pd.read_csv(OLD/'native-analysis-sol-R3-outcomes.csv')
assert len(features)==1529 and features.cycle.nunique()==77 and len(original)==21371
paths=[OUT/'carry-screen-design.json',Path(__file__),OLD/'native-analysis-sol-R3-features.csv',OLD/'native-analysis-sol-R3-outcomes.csv',OLD/'native-analysis-sol-R3-summary.csv']
coverage={};tables={}
for sym in ['BTC','SOL']:
 fp=DATA/f'bybit-{sym}USDT-funding.parquet';mp=DATA/f'bybit-{sym}USDT-mark-1m.parquet';paths += [fp,mp]
 f=pd.read_parquet(fp);m=pd.read_parquet(mp,columns=['open_time_ms','close'])
 ft=f.funding_time_ms.to_numpy(dtype=np.int64);rates=f.funding_rate.to_numpy(dtype=float)
 mt=m.open_time_ms.to_numpy(dtype=np.int64);marks=m.close.to_numpy(dtype=float)
 assert np.all(np.diff(ft)>0) and np.all(np.isfinite(rates)) and np.all(np.diff(mt)==60000)
 assert np.max(np.diff(ft))<=28800000
 relevant=(ft>=features.decision_ns.min()//1000000)&(ft<=original.decision_ns.max()//1000000+86400000)
 pos=np.searchsorted(mt,ft[relevant]-60000)
 assert np.all(pos<len(mt)) and np.all(mt[pos]==ft[relevant]-60000)
 cash_unit=np.full(len(ft),np.nan);cash_unit[relevant]=rates[relevant]*marks[pos]
 # Prefix sums only over relevant events; other events are not needed for outcomes.
 cs=np.cumsum(np.nan_to_num(cash_unit))
 coverage[sym]={'funding_rows':len(f),'mark_rows':len(m),'funding_first_ms':int(ft[0]),'funding_last_ms':int(ft[-1]),'observed_interval_hours_counts':{str(k/3600000):int(v) for k,v in zip(*np.unique(np.diff(ft),return_counts=True))},'relevant_events':int(relevant.sum()),'relevant_prior_marks_missing':0,'max_gap_hours':float(np.max(np.diff(ft))/3600000)}
 tables[sym]=(ft,rates,cash_unit,cs)
f=features.set_index('decision_ns');rows=original.copy()
rows['lag_SOLfunding_ns']=0;rows['lag_SOLfunding_rate']=0.;rows['lag_SOLcarry_bin']=''
for i,r in rows.iterrows():
 t=int(r.decision_ns)//1000000;ft,rate,_,_=tables['SOL'];k=np.searchsorted(ft,t,side='left')-1
 assert k>=0 and ft[k]<t
 rows.at[i,'lag_SOLfunding_ns']=ft[k]*1000000;rows.at[i,'lag_SOLfunding_rate']=rate[k]
 rows.at[i,'lag_SOLcarry_bin']='recipient' if int(r.side)*rate[k]>0 else 'payer_or_zero'
scenarios={'EE':(False,False),'IE':(True,False),'EI':(False,True),'II':(True,True)}
for code,(inc_entry,inc_exit) in scenarios.items():
 vals=[];ties=[];counts=[]
 for r in rows.itertuples():
  if r.kind=='NONE':vals.append(0.);ties.append(0);counts.append(0);continue
  sym='SOL' if r.kind=='SOL' else 'BTC';ft,rate,unit,cs=tables[sym]
  t=int(r.decision_ns)//1000000;end=t+int(r.horizon_h)*3600000
  left=np.searchsorted(ft,t,side='left' if inc_entry else 'right');right=np.searchsorted(ft,end,side='right' if inc_exit else 'left')
  assert right>=left and (right==left or np.all(np.isfinite(unit[left:right])))
  u=(cs[right-1] if right else 0.)-(cs[left-1] if left else 0.)
  ref=f.loc[int(r.decision_ns)];px=float(ref.SOLclose if sym=='SOL' else ref.BTCclose);qty=float(r.action_notional_USDT)/px
  vals.append(int(r.side)*qty*u);counts.append(right-left)
  ties.append(int(np.any(ft==t))+int(np.any(ft==end)))
 rows[f'funding_delta_{code}_USDT']=vals
 rows[f'funding_delta_{code}_bp']=np.array(vals)/rows.NB_USDT*10000
 rows[f'funding_events_{code}']=counts
 rows[f'entry_exit_funding_ties_{code}']=ties
 rows[f'net_plus_funding_{code}_bp']=rows.endpoint_net_action_benefit_bp+rows[f'funding_delta_{code}_bp']
rows['funding_boundary_min_bp']=rows[[f'funding_delta_{c}_bp' for c in scenarios]].min(axis=1)
rows['funding_boundary_max_bp']=rows[[f'funding_delta_{c}_bp' for c in scenarios]].max(axis=1)
rows['lag_SOLrate_exact_zero']=rows.lag_SOLfunding_rate==0
# Preserve every original price/fee label exactly as parsed: no price outcome recomputation.
assert rows[original.columns].equals(original)
assert (rows.lag_SOLfunding_ns<rows.decision_ns).all()
assert (rows.loc[rows.kind=='NONE',[f'funding_delta_{c}_bp' for c in scenarios]]==0).all().all()
rows.to_csv(OUT/'carry-screen-outcomes.csv',index=False)
# Add paired difference versus equal-factor trim, not standalone SOL return.
trim=rows[rows.kind=='BTC_TRIM'].copy();trim['pair_action']=trim.action.str.replace('TRIM_MATCH_','',regex=False)
paired=rows[rows.kind=='SOL'].merge(trim[['decision_ns','horizon_h','pair_action']+[f'net_plus_funding_{c}_bp' for c in scenarios]],left_on=['decision_ns','horizon_h','action'],right_on=['decision_ns','horizon_h','pair_action'],suffixes=('','_trim'),validate='one_to_one')
for c in scenarios:paired[f'paired_SOL_minus_trim_{c}_bp']=paired[f'net_plus_funding_{c}_bp']-paired[f'net_plus_funding_{c}_bp_trim']
metrics=['endpoint_net_action_benefit_bp','action_fee_bp','adverse_H1close_improvement_bp']+[f'funding_delta_{c}_bp' for c in scenarios]+[f'net_plus_funding_{c}_bp' for c in scenarios]+['funding_boundary_min_bp','funding_boundary_max_bp']
agg=[];blocks=[]
for view,extra in [('overall',[]),('lag_SOLcarry_bin',['lag_SOLcarry_bin']),('endpoint',['endpoint_stratum'])]:
 for period in ['all','first_year','second_year']:
  sub=rows if period=='all' else rows[rows.period==period]
  for key,g in sub.groupby(['horizon_h','action']+extra):
   common=dict(view=view,period=period,horizon_h=int(key[0]),action=key[1],stratum=key[2] if extra else 'ALL')
   z={**common,'n_H4_labels':len(g),'n_cycle_blocks':g.cycle.nunique(),'n_crosses_native_flat':int(g.crosses_observed_native_flat.sum()),'n_exact_zero_lag_rate':int(g.lag_SOLrate_exact_zero.sum())}
   z.update({'mean_'+m:float(g[m].mean()) for m in metrics})
   for c in scenarios:
    z[f'equal_cycle_net_plus_funding_{c}_bp']=float(g.groupby('cycle')[f'net_plus_funding_{c}_bp'].mean().mean())
    z[f'pct_funding_covers_fees_{c}']=float((g[f'funding_delta_{c}_bp']>=g.action_fee_bp).mean()*100)
   agg.append(z)
   for cy,gg in g.groupby('cycle'):blocks.append({**common,'cycle':int(cy),'n_H4_labels':len(gg),**{'mean_'+m:float(gg[m].mean()) for m in metrics}})
pd.DataFrame(agg).to_csv(OUT/'carry-screen-summary.csv',index=False);pd.DataFrame(blocks).to_csv(OUT/'carry-screen-cycle-blocks.csv',index=False)
pairagg=[]
for period in ['all','first_year','second_year']:
 s=paired if period=='all' else paired[paired.period==period]
 for key,g in s.groupby(['horizon_h','action','lag_SOLcarry_bin']):
  pairagg.append(dict(period=period,horizon_h=int(key[0]),action=key[1],lag_SOLcarry_bin=key[2],n_H4_labels=len(g),n_cycle_blocks=g.cycle.nunique(),**{f'mean_SOL_minus_trim_{c}_bp':float(g[f'paired_SOL_minus_trim_{c}_bp'].mean()) for c in scenarios},**{f'equal_cycle_SOL_minus_trim_{c}_bp':float(g.groupby('cycle')[f'paired_SOL_minus_trim_{c}_bp'].mean().mean()) for c in scenarios}))
pd.DataFrame(pairagg).to_csv(OUT/'carry-screen-paired.csv',index=False)
# One independent verification on representative signed cash rows, separate from prefix arithmetic.
checks=0
for ix in np.linspace(0,len(rows)-1,80,dtype=int):
 r=rows.iloc[ix]
 if r.kind=='NONE':continue
 sym='SOL' if r.kind=='SOL' else 'BTC';ft,rate,unit,cs=tables[sym];t=int(r.decision_ns)//1000000;end=t+int(r.horizon_h)*3600000
 ref=f.loc[int(r.decision_ns)];q=float(r.action_notional_USDT)/float(ref.SOLclose if sym=='SOL' else ref.BTCclose)
 for c,(ie,ixit) in scenarios.items():
  mask=((ft>=t) if ie else (ft>t))&((ft<=end) if ixit else (ft<end))
  direct=int(r.side)*q*float(unit[mask].sum())
  assert abs(direct-r[f'funding_delta_{c}_USDT'])<1e-8;checks+=1
meta=dict(status='STOP_CARRY_NO_STABLE_FEE_COVER_OR_CYCLE_PAIRED_EDGE',result='Lag-recipient actual future funding is small versus roundtrip fees; negative net outcomes both years for all three sizes and boundary scenarios, cycle-weighted paired advantage unstable.',source_rows=len(original),feature_states=len(features),cycle_blocks=features.cycle.nunique(),coverage=coverage,verification=dict(original_price_fee_columns_unchanged=True,strictly_lagged_features=True,no_hedge_zero=True,independent_direct_sum_checks=checks),input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},engine_launches=0,full_attempts=0,training_attempts=0,limitations=['Frozen hypothetical quantity for horizon, not candidate lifecycle; crosses native flat retained and flagged.','Prior-minute raw mark matches native fixture convention but is not exact venue settlement mark/native tick-rounded mark.','Four entry/exit settlement tie scenarios are alternatives; no favorable timing assumed.','Observed funding gaps max8h; full normalized market calendar used rather than old held-position SQLite. Exact historical venue interval schedule completeness not independently proven.','Past settled rate is not advertised/predicted next rate; no assumption future rate was known.','Funding-added endpoint only; original H1close tail score unchanged, no funding-adjusted tail/DD recomputation.','Overlapping decisions/cycle means descriptive; viewed history is not fresh OOS.'])
(OUT/'carry-screen-meta.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({'rows':len(rows),'paired':len(paired),'independent_checks':checks,'coverage':coverage},indent=2))
