"""Descriptive saved-native comparator/collector. No strategy imports or engine."""
import argparse,csv,gzip,hashlib,json,sqlite3
from itertools import zip_longest
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
START=1725148800000000000;END=1788220800000000000;MIN=60000000000
DROP={'episode_id','intent_id','id','init_id','client_order_id','venue_order_id','position_id','last_trade_id','event_id'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,default=str)+'\n')
def utc(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat()
def ns(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())*10**9
def sig(x):return hashlib.sha256(json.dumps(x,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def load(p):
 p=Path(p);f=next(p.glob('*raw-native.json'));return f,json.loads(f.read_text())
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items() if k not in DROP}
 if isinstance(x,list):return [clean(v) for v in x]
 return x
def project(x,template):
 if isinstance(template,dict):return {k:project(x.get(k),v) if isinstance(x,dict) and k in x else 'MISSING_EXPORTED_FIELD' for k,v in template.items()}
 if isinstance(template,list) and isinstance(x,list):return [project(v,template[min(i,len(template)-1)]) for i,v in enumerate(x)] if template else x
 return x
def fieldsdiff(a,b):
 if isinstance(a,dict) and isinstance(b,dict):return [k for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]
 return ['record_or_count']
def firstdiff(a,b):
 last=None;count=0;first=None
 for i,(x,y) in enumerate(zip_longest(a,b)):
  if x!=y:
   count+=1
   if first is None:first=dict(index=i,fields=fieldsdiff(x,y),baseline=x,candidate=y,preceding_common_state=last)
  else:last=dict(index=i,baseline=x,candidate=y)
 return dict(equal=count==0,baseline_rows=len(a),candidate_rows=len(b),changed_rows=count,first_divergence=first)
def eventtime(record):
 if not isinstance(record,dict):return None
 for k in ['fill_ns','receipt_ns','close_available_ns','q0_ns','start_ns','ts_event','submit_ns','ts_init','timestamp_ns','timestamp']:
  v=record.get(k)
  if v is None:continue
  try:return int(v)
  except (ValueError,TypeError):
   try:return ns(v)
   except (ValueError,TypeError,AttributeError):continue
 return None

def funding(p):
 with sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
  db.row_factory=sqlite3.Row;return clean([dict(x) for x in db.execute('SELECT * FROM funding_events ORDER BY ts_event,instrument_id,event_id')])
def artifactfile(folder,suffix):
 matches=list(Path(folder).glob('*'+suffix));return matches[0] if len(matches)==1 else None
def native_orders(p):
 f=artifactfile(p,'-orders.csv');return list(csv.DictReader(f.open())) if f else []
def sequence(d,k):
 x=d.get(k)
 if not isinstance(x,list):return None
 return clean(x)
def stream_compare(a,b,fields):
 if not Path(a).is_file() or not Path(b).is_file():return dict(equal=None,status='UNKNOWN_MISSING_NATIVE_STREAM',baseline_exists=Path(a).is_file(),candidate_exists=Path(b).is_file(),first_divergence=None)
 if Path(a).resolve()==Path(b).resolve():return dict(equal=True,basis='SAME_IMMUTABLE_ARTIFACT_IDENTITY_NOT_INDEPENDENT_PATH_TEST',compressed_sha256=sha(a),changed_rows=0,first_divergence=None)
 prev=None;first=None;changed=0;rows=0;ha=hashlib.sha256();hb=hashlib.sha256()
 def reader(p,h):
  if not Path(p).exists():return
  with gzip.open(p,'rb') as f:
   for line in f:h.update(line);yield line.decode()
 witha=csv.DictReader(reader(a,ha));withb=csv.DictReader(reader(b,hb))
 for i,(x,y) in enumerate(zip_longest(witha,withb)):
  rows+=1;xx={k:x.get(k,'UNKNOWN_MISSING_FIELD') for k in fields} if x else None;yy={k:y.get(k,'UNKNOWN_MISSING_FIELD') for k in fields} if y else None
  if xx!=yy:
   changed+=1
   if first is None:first=dict(index=i,fields=fieldsdiff(xx,yy),baseline=xx,candidate=yy,preceding_common_state=prev)
  else:prev=dict(index=i,state=xx)
 return dict(equal=changed==0,compared_rows=rows,changed_rows=changed,first_divergence=first,uncompressed_sha256_baseline=ha.hexdigest(),uncompressed_sha256_candidate=hb.hexdigest(),basis='Exact frozen exported strings, no widened tolerances; raw byte hash also retained')
def collect(folder,seven):
 """One full saved receipt traversal; native equity only, no deleted fill PnL."""
 raw,d=load(folder);p=Path(folder)/'minute-native-settled-receipts.csv.gz';peak=D(10000);peakns=START;globaldd=D(0);globalworst=None;exc=None;excursions=[];prevsource=None;gaps=0;rows=0;months={};windows=[];endpoints={};targets={ns(e[k]) for e in seven for k in ['peak_utc','trough_utc','recovery_utc'] if e[k]};last=None
 for e in seven:windows.append(dict(anchor_trough=e['trough_utc'],start_ns=ns(e['peak_utc']),end_inclusive_ns=ns(e['recovery_utc']) if e['recovery_utc'] else END,samples=0,local_peak=None,local_dd=D(0),continuous_global_dd=D(0),local_recovery=None))
 def snap(r):return dict(receipt_ns=int(r['receipt_ns']),source_quote_ns=int(r['source_quote_ns']),cash=r['cash'],equity=r['paired_close_equity'],held_native_positions=json.loads(r['native_positions_and_mark_ohlc_json']),pending='UNKNOWN_NOT_EXPORTED_IN_RECEIPT',unused_rights='UNKNOWN_NOT_EXPORTED_IN_RECEIPT',admission='UNKNOWN_NOT_EXPORTED_IN_RECEIPT')
 with gzip.open(p,'rt') as f:
  for r in csv.DictReader(f):
   t=int(r['receipt_ns']);source=int(r['source_quote_ns']);equity=D(r['paired_close_equity']);rows+=1
   if prevsource is None:gaps=max(0,(source-(START+MIN))//MIN)
   else:gaps+=max(0,(source-prevsource)//MIN-1)
   prevsource=source
   for target in list(targets):
    if t>=target:endpoints[utc(target)]=dict(target_ns=target,prior_native_receipt=last,first_native_receipt_at_or_after=snap(r));targets.remove(target)
   if equity>=peak:
    if exc:
     exc['recovery_utc']=utc(t);exc['recovery_equity']=str(equity)
     if D(exc['DD_percent'])>=30:excursions.append(exc)
     exc=None
    if equity>peak:peak=equity;peakns=t
   else:
    dd=(peak-equity)/peak*100
    if exc is None or dd>D(exc['DD_percent']):exc=dict(peak_utc=utc(peakns),peak_equity=str(peak),trough_utc=utc(t),trough_equity=str(equity),DD_percent=str(dd),recovery_utc=None,recovery_equity=None)
    if dd>globaldd:globaldd=dd;globalworst=dict(exc)
   for w in windows:
    if w['start_ns']<=t<=w['end_inclusive_ns']:
     w['samples']+=1
     if w['local_peak'] is None or equity>w['local_peak']:w['local_peak']=equity;w['local_peak_ns']=t
     ld=(w['local_peak']-equity)/w['local_peak']*100;gd=(peak-equity)/peak*100
     if ld>w['local_dd']:w['local_dd']=ld;w['local_worst']=dict(peak_utc=utc(w['local_peak_ns']),peak_equity=str(w['local_peak']),trough_utc=utc(t),trough_equity=str(equity));w['local_recovery']=None
     w['continuous_global_dd']=max(w['continuous_global_dd'],gd)
    if w.get('local_worst') and w['local_recovery'] is None and t>ns(w['local_worst']['trough_utc']) and equity>=D(w['local_worst']['peak_equity']):w['local_recovery']=dict(utc=utc(t),equity=str(equity))
   month=utc(source)[:7]  # Source quote calendar; delayed receipt is not backdated.
   if month not in months:months[month]=dict(month=month,start_equity=str(D(last['equity']) if last is not None else D(10000)),first_receipt_ns=t,last_equity=str(equity),last_receipt_ns=t,samples=0,peak=D(last['equity']) if last is not None else D(10000),local_DD_percent=D(0))
   mm=months[month];mm['samples']+=1;mm['last_equity']=str(equity);mm['last_receipt_ns']=t;mm['peak']=max(mm['peak'],equity);mm['local_DD_percent']=max(mm['local_DD_percent'],(mm['peak']-equity)/mm['peak']*100);last=snap(r)
 if exc and D(exc['DD_percent'])>=30:excursions.append(exc)
 for x in excursions:
  if globalworst and x['peak_utc']==globalworst['peak_utc'] and x['trough_utc']==globalworst['trough_utc']:globalworst=x
 gaps+=max(0,(END-MIN-prevsource)//MIN)
 # Fill-based descriptors are saved actual activity; never counterfactual PnL.
 fa=d['fill_audit']
 for w in windows:
  sel=[r for r in fa if w['start_ns']<=int(r['fill_ns'])<=w['end_inclusive_ns']];w['actual_native_fills']={a:sum(a in r['instrument'] for r in sel) for a in ['BTC','SOL']};w['actual_native_fees']=str(sum((D(r['commission']) for r in sel),D(0)));w['unused_rights']='UNKNOWN_FULL_BALANCES_NOT_EXPORTED';w['pending']='UNKNOWN_NOT_EXPORTED';w['lost_recoveries']='NOT_IDENTIFIED_CAUSALLY_BY_SAVED_PATH';w.pop('local_peak');w.pop('local_peak_ns',None)
 for w,e in zip(windows,seven):
  a=endpoints.get(e['peak_utc'],{}).get('first_native_receipt_at_or_after');b=endpoints.get(e['trough_utc'],{}).get('first_native_receipt_at_or_after')
  if a and b:
   dc=D(b['cash'])-D(a['cash']);de=D(b['equity'])-D(a['equity']);du=(D(b['equity'])-D(b['cash']))-(D(a['equity'])-D(a['cash']));w['fixed_endpoint_native_cash_bridge']=dict(delta_equity=str(de),delta_cash=str(dc),delta_aggregate_native_UPnL=str(du),identity_exact=de==dc+du,peak_native_snapshot=a,trough_native_snapshot=b,signed_asset_funding='UNKNOWN_NOT_UNALLOCATED_CASH_BRIDGE')
 for mm in months.values():mm['return_percent']=(D(mm['last_equity'])/D(mm['start_equity'])-1)*100
 return dict(global_settled_DD_percent=str(globaldd),global_peak_trough_recovery=globalworst,global_excursions_ge30=excursions,seven_fixed_E4_anchor_windows=windows,window_basis='inclusive frozen E4 peak→E4recovery; missing E4recovery→last causal preterminal observation, including delayed receipt at intervalend; local rebased DD distinct from continuous global DD; candidate own recovery searched through full saved period',boundary_snapshots=endpoints,monthly=list(months.values()),receipts=rows,missing_source_minutes=gaps,last_native_receipt=last,terminal_total=d['terminal_total'],native_fees=d['native_fees'],fill_count=d['fills'],terminal_lifecycle=d['terminal_lifecycle'],signed_asset_funding='UNKNOWN',cash_bridge='UNALLOCATED_NOT_CALLED_FUNDING',monthly_basis='SOURCE_QUOTE_UTC_CALENDAR; observed later native receipt; boundary start is preceding receipt equity',no_engine=True)
def write_collection(out,prefix,col):
 dump(out/('data-attribution-'+prefix+'.json'),col)
 for name,z in [('months',col['monthly']),('seven-windows',col['seven_fixed_E4_anchor_windows'])]:
  with (out/('data-attribution-'+prefix+'-'+name+'.csv')).open('w') as f:
   keys=list(dict.fromkeys(k for r in z for k in r));w=csv.DictWriter(f,keys);w.writeheader();w.writerows({k:json.dumps(v,default=str) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in z)

def reference(folder):
 raw,d=load(folder);paths=[raw,artifactfile(folder,'-orders.csv'),artifactfile(folder,'-fills.csv'),Path(folder)/'minute-native-settled-receipts.csv.gz',Path(folder)/'minute-native-risk.csv.gz']
 return dict(folder=str(folder),source_sha='bd04c9b3858bcda40060a08eff488849c69af5d8',raw_sha256=sha(raw),data_hash=d['data_hash'],policy_hash=d['policy_hash'],config_hash=d['config_hash'],terminal_total=d['terminal_total'],native_fees=d['native_fees'],fill_count=d['fills'],files={str(x):sha(x) for x in paths if x and x.exists()},expected_signatures={k:sig(clean(d.get(k))) for k in ['fill_audit','cash_account_series','entry_sizing_audit','split_cover_audit','terminal_lifecycle','post_boundary_settlement']},funding_signature=sig(funding(d['funding_journal'])) if Path(d.get('funding_journal','')).is_file() else 'UNKNOWN_NOT_LOCAL',pending_inventory='UNKNOWN_NOT_EXPORTED',complete_rights_balances='UNKNOWN_NOT_EXPORTED',complete_admission_vector='UNKNOWN_NOT_EXPORTED',qualification='Freeze exact old E4 references before candidate; no source/config equality assumption after explicit policy flag')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--candidate',type=Path);ap.add_argument('--seven',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--prefix',default='CONTROL');ap.add_argument('--freeze-only',action='store_true');ap.add_argument('--collect-only',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);seven=json.loads(a.seven.read_text())['episodes'];ref=reference(a.baseline);refpath=a.out/'data-execution-reference.json'
 if refpath.exists():
  frozen=json.loads(refpath.read_text())
  if frozen!=ref:raise ValueError('FROZEN_BASELINE_REFERENCE_CHANGED_PRESERVED_OLD_FREEZE')
 else:dump(refpath,ref)
 if a.freeze_only:print(json.dumps(dict(status='EXACT_E4_REFERENCE_FROZEN',files=len(ref['files']),no_engine=True)));return
 if not a.candidate:raise ValueError('--candidate required unless --freeze-only')
 if a.collect_only:
  col=collect(a.candidate,seven);write_collection(a.out,a.prefix,col);print(json.dumps(dict(status='SAVED_NATIVE_COLLECTION_COMPLETE',DD=col['global_settled_DD_percent'],months=len(col['monthly']),no_engine=True)));return
 bpath,b=load(a.baseline);cpath,c=load(a.candidate);checks={};events={}
 for key in ['fill_audit','cash_account_series','interval_cash_account_series','entry_sizing_audit']:
  x=sequence(b,key);y=sequence(c,key);events[key]=firstdiff(x,project(y,x)) if x is not None and y is not None else dict(equal=None,status='UNKNOWN_MISSING_EXPORTED_SEQUENCE')
 x=clean(b['split_cover_audit']['parents']);y=clean(c['split_cover_audit']['parents']);events['split_parents_H_VWAP']=firstdiff(x,project(y,x))
 economic_fields=['instrument_id','type','side','time_in_force','is_reduce_only','filled_qty','avg_px','ts_init','ts_last','price','commissions'];oldorders=native_orders(a.baseline);neworders=native_orders(a.candidate)
 events['native_orders_economic']=firstdiff([{k:r.get(k) for k in economic_fields} for r in oldorders],[{k:r.get(k) for k in economic_fields} for r in neworders])
 lifecycle=['quantity','filled_qty','status','ts_init','ts_last','instrument_id','side'];events['native_order_request_status']=firstdiff([{k:r.get(k) for k in lifecycle} for r in oldorders],[{k:r.get(k) for k in lifecycle} for r in neworders])
 events['settled_native_money_held_path']=stream_compare(a.baseline/'minute-native-settled-receipts.csv.gz',a.candidate/'minute-native-settled-receipts.csv.gz',['source_quote_ns','receipt_ns','fill_epoch','cash','paired_close_equity','native_positions_and_mark_ohlc_json'])
 events['native_risk_margin_path']=stream_compare(a.baseline/'minute-native-risk.csv.gz',a.candidate/'minute-native-risk.csv.gz',['bar_open_ms','close_available_ns','phase','cash','free_cash','native_initial_margin','native_maintenance_margin','paired_close_equity','native_positions_and_mark_ohlc_json'])
 for key in ['terminal_total','terminal_active','terminal_reserve','terminal_open_positions','native_fees','fills','liquidation_count','native_order_rejections','pre_submit_tier_margin_gate_blocks','terminal_lifecycle','post_boundary_settlement','data_hash','policy_hash']:checks[key]=dict(equal=b.get(key)==c.get(key),baseline=b.get(key,'UNKNOWN'),candidate=c.get(key,'UNKNOWN'))
 checks['config_hash']=dict(equal=b['config_hash']==c['config_hash'],baseline=b['config_hash'],candidate=c['config_hash'],qualification='Expected metadata/explicitpolicy flag differences visible; not economic mismatch alone')
 bf=Path(b.get('funding_journal',''));cf=Path(c.get('funding_journal',''))
 events['native_funding_journal']=firstdiff(funding(bf),funding(cf)) if bf.is_file() and cf.is_file() else dict(equal=None,status='UNKNOWN_FUNDING_JOURNAL_NOT_LOCAL')
 events['pre_submit_admission_blocks']=firstdiff(clean(b.get('pre_submit_tier_margin_gate_blocks',[])),clean(c.get('pre_submit_tier_margin_gate_blocks',[])))
 # Full rights/pending/admission claims remain unknown when archive cannot witness them.
 economic=['fill_audit','entry_sizing_audit','split_parents_H_VWAP','native_orders_economic','settled_native_money_held_path','native_risk_margin_path','native_funding_journal','pre_submit_admission_blocks'];scalar_same=all(v['equal'] for k,v in checks.items() if k!='config_hash');same=all(events[k]['equal'] is True for k in economic) and scalar_same;lifecycle_equal=events['native_order_request_status']['equal']
 report=dict(status='EXPORTED_ECONOMICS_MATCH_LIFECYCLE_DIFFERS' if same and not lifecycle_equal else 'EXPORTED_PATH_MATCH' if same else 'EXPORTED_PATH_DIVERGENCE',full_execution_equivalence='NOT_ESTABLISHED_BY_ARCHIVE_ALONE_PENDING_RIGHTS_ADMISSION_UNKNOWN',checks=checks,dimensions=events,expected_reference=ref,candidate_raw_path=str(cpath),candidate_raw_sha256=sha(cpath),checkpoint_sampling_qualification='Raw cash_account_series index/sampling differences are reported but not treated alone as economic divergence; full native receipt cash path and terminal cash are authoritative',unknowns=['complete pending inventory/rightsbalances/admission at every decision not exported by oldarchive; no equality inferred','native child FILLED vs oldpartialCANCELED is genuine lifecycle difference; not rewritten','source/config/engine/inputfreeze review remains root responsibility'],no_engine=True)
 ranked=[]
 for key in economic:
  f=events[key].get('first_divergence')
  if f:
   times=[eventtime(f.get(x)) for x in ['baseline','candidate']];times=[t for t in times if t is not None]
   if times:ranked.append((min(times),key,f))
 if ranked:
  t,key,f=min(ranked,key=lambda x:x[0]);report['first_actual_exported_economic_divergence']=dict(timestamp_ns=t,utc=utc(t),dimension=key,**f)
 else:report['first_actual_exported_economic_divergence']=None
 dump(a.out/('data-execution-equivalence-'+a.prefix+'.json'),report);col=collect(a.candidate,seven);dump(a.out/('data-attribution-'+a.prefix+'.json'),col)
 for name,z in [('months',col['monthly']),('seven-windows',col['seven_fixed_E4_anchor_windows'])]:
  with (a.out/('data-attribution-'+a.prefix+'-'+name+'.csv')).open('w') as f:
   keys=list(dict.fromkeys(k for r in z for k in r));w=csv.DictWriter(f,keys);w.writeheader();w.writerows({k:json.dumps(v,default=str) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in z)
 print(json.dumps(dict(status=report['status'],unknown_full_equivalence=True,DD=col['global_settled_DD_percent'],months=len(col['monthly']),no_engine=True)))
if __name__=='__main__':main()
