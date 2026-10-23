"""Read saved native receipts only. No execution, fill simulation, or PnL ledger."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import csv,gzip,json,hashlib,bisect,collections
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021')
OUT=ROOT/'reports/sol-conditional-hedge-btc-band-20261023'
BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023')
DAY=86400000000000
START=1725148800000000000;END=1788220800000000000

def ns(s):return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()*1e9)
def iso(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat() if n is not None else None
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def writecsv(name,rows):
    path=OUT/name;keys=sorted({k for r in rows for k in r})
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,sort_keys=True,separators=(',',':')) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    return dict(path=str(path),rows=len(rows),sha256=sha(path))
WIN=[('A',ns('2024-09-01'),ns('2024-10-04')),('B',ns('2025-04-11'),ns('2025-06-07')),('C',ns('2025-10-22'),ns('2025-11-29')),('D',ns('2026-07-06'),ns('2026-08-19'))]
E=[('E1',WIN[0][2],WIN[1][1]),('E2',WIN[1][2],WIN[2][1]),('E3',WIN[2][2],WIN[3][1]),('E4',WIN[3][2],END)]
MONTH=[]
y,m=2024,9
for _ in range(24):
    a=ns(f'{y:04}-{m:02}-01');yy,mm=(y+1,1) if m==12 else (y,m+1);b=ns(f'{yy:04}-{mm:02}-01');MONTH.append((f'{y:04}-{m:02}',a,b));y,m=yy,mm
refpath=ROOT/'reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution-episodes.csv'
REF=list(csv.DictReader(refpath.open()));p0path=next(x for x in (BASE/'P0/result').glob('*.json') if x.name.endswith('direction.json'));p0=json.loads(p0path.read_text())
assert [int(p['start_ns']) for p in p0['split_cover_audit']['parents']]==[int(r['start_ns']) for r in REF if r['symbol']=='BTC']
S0P={int(p['start_ns'])//DAY:p for p in p0['split_cover_audit']['parents']}
paths=[('S0',p0path)]
for name in ('C0','H4_4H_E34_G050','BTC_REGIME_REENTRY_BAND_05','H4_4H_E13_G050','H4_4H_E89_G050','H4_4H_E34_G100','H4_4H_E13_G100','H4_4H_E89_G100','X_H4_4H_E89_G100_B05'):
    p=OUT/('owner-'+name+'-receipt.json')
    if p.exists():paths.append((name,Path(json.loads(p.read_text())['artifact'])))
monthly=[];windows=[];globals_out=[];episodes=[];signalrows=[];actionrows=[];coverage=[];bdelay=[];manifest=[]

class Window:
    def __init__(self,label,a,b):
        self.label,self.a,self.b=label,a,b;self.started=False;self.samples=0;self.maxdd=D(0);self.recovery=None;self.trough=None;self.cov=collections.Counter();self.factor_sum=0.;self.factor_seconds=0.;self.factor_min=None;self.factor_max=None;self.trough_cov={};self.underwater=0;self.uw_start=None;self.longest_uw=0
    def add(self,t,eq,prev,prevts,dt,c):
        if self.a<=t<self.b:
            if not self.started:self.started=True;self.base=prev;self.peak=prev;self.peakts=prevts;self.min=prev;self.mints=prevts;self.start_sample=prevts
            self.samples+=1;self.end=eq;self.end_sample=t
            if eq<self.min:self.min=eq;self.mints=t
            self.cov.update({k:v*dt for k,v in c.items() if k!='factor'})
            if c.get('factor') is not None:
                v=c['factor'];self.factor_sum+=v*dt;self.factor_seconds+=dt;self.factor_min=v if self.factor_min is None else min(self.factor_min,v);self.factor_max=v if self.factor_max is None else max(self.factor_max,v)
            if eq>self.peak:self.peak=eq;self.peakts=t
            if eq<self.peak:
                self.underwater+=dt
                if self.uw_start is None:self.uw_start=self.peakts
            elif self.uw_start is not None:
                self.longest_uw=max(self.longest_uw,(t-self.uw_start)/1e9);self.uw_start=None
            dd=(self.peak-eq)/self.peak*100 if self.peak>0 else D(0)
            if dd>self.maxdd:self.maxdd=dd;self.ddpeak=self.peak;self.ddpeakts=self.peakts;self.trough=t;self.trough_eq=eq;self.recovery=None;self.trough_cov=dict(self.cov)
        if self.trough is not None and self.recovery is None and t>self.trough and eq>=self.ddpeak:self.recovery=t
    def result(self,recipe,missing):
        if not self.started:return dict(recipe=recipe,window=self.label,status='NO_SAVED_SAMPLES')
        return dict(recipe=recipe,window=self.label,start_utc=iso(self.a),end_exclusive_utc=iso(self.b),basis='ACTUAL_LATER_NATIVE_SETTLED_RECEIPT_TIMESTAMP',local_rebasing=True,global_peak_reset=False,start_equity=str(self.base),start_receipt_utc=iso(self.start_sample),end_equity=str(self.end),end_receipt_utc=iso(self.end_sample),normalized_return_percent=str((self.end/self.base-1)*100) if self.base else None,local_observed_DD_percent=str(self.maxdd),peak_to_trough_amount=str(self.ddpeak-self.trough_eq) if self.trough else '0',peak_utc=iso(self.ddpeakts) if self.trough else None,trough_utc=iso(self.trough),recovery_utc=iso(self.recovery),recovery_seconds_after_trough=(self.recovery-self.trough)/1e9 if self.recovery and self.trough else None,minimum_equity=str(self.min),minimum_equity_utc=iso(self.mints),maximum_equity=str(self.peak),maximum_equity_utc=iso(self.peakts),underwater_observed_seconds=self.underwater,longest_observed_underwater_seconds=max(self.longest_uw,(self.end_sample-self.uw_start)/1e9 if self.uw_start is not None else 0),samples=self.samples,global_missing_settled_receipts=missing,DD_qualification='OBSERVED_LOWER_BOUND_MISSING_RECEIPTS' if missing else 'COMPLETE_NATIVE_SETTLED_RECEIPTS',native_asset_net_PnL='UNKNOWN_NOT_EXPORTED_PER_ASSET',signed_asset_funding='UNKNOWN')

for recipe,path in paths:
    d=json.loads(path.read_text());risk=d['minute_risk_observations']['settled_native_close_receipts'];trace=Path(risk['trace_path']);missing=risk['unavailable_intervening_native_mutation'];parents=d['split_cover_audit']['parents'];P={int(p['start_ns'])//DAY:p for p in parents};basekeys=sorted(int(p['start_ns']) for p in parents);betas=[p.get('planref_v1_beta') for p in parents]
    audit=d.get('hedge_band_audit',[]);acts={int(a['timestamp_ns']):a for a in audit if a['event']=='H4_ACTIVATION'}
    firstfill=sorted((int(a['timestamp_ns']),int(a['timestamp_ns'])-int(a['delay_ns'])) for a in audit if a['event']=='H4_FIRST_FILL')
    ffkeys=[a for a,b in firstfill]
    w=[Window(*x) for x in WIN+E];gw=Window('GLOBAL',START,END+1);mw=[Window(*x) for x in MONTH];probe_keys=sorted(set([int(x['start_ns'])-1 for x in REF]+[int(x['end_ns'])+1 for x in REF]));probes={};qi=0
    ws=sorted(w,key=lambda x:x.a);wstarts=[x.a for x in ws];mstarts=[x.a for x in mw]
    prev=D(10000);prevts=START;prev_source=START;rows=0
    for row in csv.DictReader(gzip.open(trace,'rt')):
        t=int(row['receipt_ns']);source=int(row['source_quote_ns']);eq=D(row['paired_close_equity']);dt=min(60,max(0,(source-prev_source)/1e9));rows+=1
        while qi<len(probe_keys) and probe_keys[qi]<t:probes[probe_keys[qi]]=(prev,prevts);qi+=1
        pos=json.loads(row['native_positions_and_mark_ohlc_json']);assets={('BTC' if x['instrument_id'].startswith('BTC') else 'SOL'):x for x in pos};c=dict(btc_held_seconds=int('BTC' in assets),sol_held_seconds=int('SOL' in assets),standalone_sol_seconds=int('SOL' in assets and 'BTC' not in assets),btc_with_sol_seconds=int('BTC' in assets and 'SOL' in assets),opposite_sides_seconds=int('BTC' in assets and 'SOL' in assets and assets['BTC']['side']!=assets['SOL']['side']),factor=None)
        if 'BTC' in assets:
            if 'SOL' not in assets:c['factor']=0.
            else:
                if (recipe.startswith('H4') or recipe.startswith('X')):
                    k=bisect.bisect_right(ffkeys,source)-1;beta=acts.get(firstfill[k][1],{}).get('beta0') if k>=0 else None
                else:
                    k=bisect.bisect_right(basekeys,source)-1;beta=betas[k] if k>=0 else None
                if beta is not None and float(beta)>0:
                    bn=D(assets['BTC']['quantity'])*D(assets['BTC']['mark_ohlc']['close']);sn=D(assets['SOL']['quantity'])*D(assets['SOL']['mark_ohlc']['close']);c['factor']=float(D(str(beta))*sn/bn)*(1 if assets['BTC']['side']!=assets['SOL']['side'] else -1)
        gw.add(t,eq,prev,prevts,dt,c)
        wi=bisect.bisect_right(wstarts,t)-1;mi=bisect.bisect_right(mstarts,t)-1
        if wi>=0:ws[wi].add(t,eq,prev,prevts,dt,c)
        if mi>=0:mw[mi].add(t,eq,prev,prevts,dt,{})
        for prior in ws[:max(0,wi)]:
            if prior.trough is not None and prior.recovery is None and eq>=prior.ddpeak:prior.recovery=t
        prev,prevts,prev_source=eq,t,source
    while qi<len(probe_keys):probes[probe_keys[qi]]=(prev,prevts);qi+=1
    gr=gw.result(recipe,missing);gr['local_rebasing']=False;gr['global_peak_reset']=False;gr['native_primary_global_DD_percent']=risk['curve']['top3_distinct_excursions'][0]['drawdown_peak_percent'];assert D(gr['local_observed_DD_percent'])==D(gr['native_primary_global_DD_percent']),(recipe,gr)
    globals_out.append(gr)
    fills=d['fill_audit'];cashmonthly={x['month']:x for x in d['summary']['monthly_returns']}
    for x in w:
        r=x.result(recipe,missing);fs=[f for f in fills if x.a<=int(f['fill_ns'])<x.b];r.update(prior_liquidation_flat_lockout=any(f['action']=='LIQUIDATION_CLOSE' and int(f['fill_ns'])<x.a for f in fills),native_fills=len(fs),native_fees=str(sum((D(f['commission']) for f in fs),D(0))),native_turnover=str(sum((D(f['notional']) for f in fs),D(0))),liquidation_count_in_window=sum(f['action']=='LIQUIDATION_CLOSE' for f in fs));windows.append(r)
        coverage.append(dict(recipe=recipe,window=x.label,beta_basis='H4_ACTIVATION_DAILY_BETA270_AT_ACTUAL_FIRST_FILL' if (recipe.startswith('H4') or recipe.startswith('X')) else 'BTC_PARENT_FROZEN_DAILY_BETA270_DIAGNOSTIC',time_basis='OBSERVED_NATIVE_RECEIPT_SOURCE_MARK_POSITIONS_CAPPED_60SEC_PER_SAMPLE',global_missing_settled_receipts=missing,**dict(x.cov),mean_beta_factor_coverage=x.factor_sum/x.factor_seconds if x.factor_seconds else None,minimum_beta_factor_coverage=x.factor_min,maximum_beta_factor_coverage=x.factor_max,beta_factor_known_seconds=x.factor_seconds,coverage_before_local_trough=x.trough_cov,coverage_is_not_PnL_or_guaranteed_protection=True))
    for x in mw:
        r=x.result(recipe,missing);cash=cashmonthly.get(x.label,{});fs=[f for f in fills if x.a<=int(f['fill_ns'])<x.b];r.update(month=x.label,native_cash_return_percent=str(D(cash['return'])*100) if cash else None,native_cash_end_total=cash.get('total'),native_fills=len(fs),native_fees=str(sum((D(f['commission']) for f in fs),D(0))),native_turnover=str(sum((D(f['notional']) for f in fs),D(0))));monthly.append(r)
    for ref in REF:
        a,b=int(ref['start_ns']),int(ref['end_ns']);day=a//DAY;candidate=P.get(day) if ref['symbol']=='BTC' else None;s0=S0P.get(day) if ref['symbol']=='BTC' else None;e0,t0=probes[a-1];e1,t1=probes[b+1];num=int(ref['number']);counter=(ref['symbol']=='SOL' and num==1) or (ref['symbol']=='BTC' and num in (29,40,41,67,96));winner=D(ref['confirmed_fill_net_ex_funding'])>0
        episodes.append(dict(recipe=recipe,S0_asset=ref['symbol'],S0_episode_number=num,S0_start_utc=ref['start_utc'],S0_end_utc=ref['end_utc'],mandatory_counterexample=counter,all_S0_winner_included=winner,S0_existing_confirmed_fill_diagnostic_ex_funding=ref['confirmed_fill_net_ex_funding'],S0_label_source=str(refpath),native_asset_PnL='UNKNOWN_NOT_EXPORTED',signed_asset_funding='UNKNOWN',candidate_same_day_BTC_parent=candidate is not None,candidate_episode_id=candidate.get('episode_id') if candidate else None,candidate_start_ns=candidate.get('start_ns') if candidate else None,candidate_filled_BTC_qty=candidate.get('filled') if candidate else None,S0_filled_BTC_qty=s0.get('filled') if s0 else None,calendar_match_basis='SAME_UTC_ENTRY_DAY_NO_FORCED_SIZE_OR_CALENDAR',candidate_fixed_S0_window_native_equity_start=str(e0),candidate_fixed_S0_window_native_equity_end=str(e1),candidate_fixed_S0_window_equity_return_percent=str((e1/e0-1)*100) if e0 else None,native_equity_endpoint_age_seconds=max((a-t0)/1e9,(b-t1)/1e9),fixed_window_diagnostic_not_asset_PnL=True,global_missing_settled_receipts=missing))
    for p in parents:
        if int(p['start_ns'])//DAY not in S0P:episodes.append(dict(recipe=recipe,candidate_episode_id=p['episode_id'],candidate_start_ns=p['start_ns'],candidate_filled_BTC_qty=p['filled'],candidate_side=p['side'],calendar_change='NEW_CANDIDATE_DAY_NOT_S0_ENTRY',native_asset_PnL='UNKNOWN_NOT_EXPORTED',signed_asset_funding='UNKNOWN'))
    for i,a in enumerate(audit):
        item=dict(recipe=recipe,source_kind='native_hedge_band_audit',source_index=i,**a)
        if a['event'] in ('H4_SIGNAL','H4_ACTIVATION','H4_ACTIVATION_INVALID','WAIT_REGIME_REENTRY','B_ENTRY_ALLOWED'):signalrows.append(item)
        else:
            if a['event']=='H4_NATIVE_CHILD':item['semantics']='PRE_SUBMIT_PROPOSAL_NOT_PROOF_OF_NATIVE_ACCEPTANCE'
            actionrows.append(item)
    for i,a in enumerate(fills):actionrows.append(dict(recipe=recipe,source_kind='native_fill_audit',source_index=i,**a))
    for i,a in enumerate(d['pre_submit_tier_margin_gate_blocks']):actionrows.append(dict(recipe=recipe,source_kind='native_local_pre_submit_denial',source_index=i,**a))
    if recipe=='BTC_REGIME_REENTRY_BAND_05':
        entries=[(int(p['start_ns']),p) for p in parents]
        for i,a in enumerate(audit):
            if a['event']!='WAIT_REGIME_REENTRY' or 'side' in a:continue
            start=int(a['timestamp_ns']);nextentry=next(((t,p) for t,p in entries if t>=start),None);stop=nextentry[0] if nextentry else END;gates=[x for x in audit[i+1:] if start<=int(x['timestamp_ns'])<=stop and 'side' in x];refrows=[x for x in REF if x['symbol']=='BTC' and start<=int(x['start_ns'])<stop];bdelay.append(dict(latch_start_utc=iso(start),actual_next_entry_utc=iso(stop) if nextentry else None,delay_seconds=(stop-start)/1e9,actual_new_side=nextentry[1]['side'] if nextentry else None,weak_daily_refusals=sum(x['event']=='WAIT_REGIME_REENTRY' for x in gates),latest_accepted_side=gates[-1].get('side') if gates else None,S0_entries_in_wait_interval=len(refrows),S0_winners_in_wait_interval=sum(D(x['confirmed_fill_net_ex_funding'])>0 for x in refrows),S0_losses_in_wait_interval=sum(D(x['confirmed_fill_net_ex_funding'])<0 for x in refrows),S0_episode_numbers=[x['number'] for x in refrows],not_standalone_dollar_savings='Calendar/capital change; diagnostic cohort counts only, no summed S0 PnL claim'))
    manifest.append(dict(recipe=recipe,artifact=str(path),artifact_sha256=sha(path),settled_trace=str(trace),settled_trace_sha256=sha(trace),settled_rows_streamed=rows,missing_settled_receipts=missing,source_hashes=d.get('source_hashes'),config_sha256=d['config_hash']))
    print(recipe,'saved native receipt analysis rows',rows,flush=True)
exports={name:writecsv(name,rows) for name,rows in [('owner-monthly.csv',monthly),('owner-global-risk.csv',globals_out),('owner-windows.csv',windows),('owner-episode-comparison.csv',episodes),('owner-signal-events.csv',signalrows),('owner-action-audit.csv',actionrows),('owner-coverage.csv',coverage),('owner-B-skip-delay.csv',bdelay)]}
(OUT/'owner-analysis-manifest.json').write_text(json.dumps(dict(inputs=manifest,reference_episode_labels=dict(path=str(refpath),sha256=sha(refpath),S0_BTC_exact_start_matches=105),exports=exports,method='One bounded saved-native-receipt stream per recipe; no new engine, no PnL ledger. A-D local diagnostic rebasing; E1-E4 disjoint complements kept separate. Global native observer curve untouched. Monthly receipt equity separate original native cash monthly returns. All S0 winners/counterexamples included, candidate calendar and quantities not forced.',limitations=['Missing settled receipts qualify DD as observed lower bound. No interpolation/backdating of monetary equity.','Perasset native settled PnL and signed perasset funding UNKNOWN; existing S0 confirmed-fill diagnostics used as historical labels only.','Coverage integrates observed native receipt positions capped60seconds; does not prove intraminute inventory path or protective effectiveness.','Fixed S0 episode-window account equity diagnostics include all assets and capital/calendar effects; not candidate asset PnL.']),ensure_ascii=False,indent=2)+'\n')
print('OFFLINE_EXPORTS_COMPLETE',len(paths),'recipes',flush=True)
