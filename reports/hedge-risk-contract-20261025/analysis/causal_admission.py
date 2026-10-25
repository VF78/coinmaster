"""Saved-artifact analysis only. No product/engine imports; no candidate wealth path."""
import json,csv,gzip,hashlib
from pathlib import Path
from decimal import Decimal as D, getcontext
from datetime import datetime,timezone
from collections import Counter
import pandas as pd
getcontext().prec=40
ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster')
OUT=Path(__file__).resolve().parent
P=ROOT/'runtime/var/research-jobs/paired-lot-corridor-20261025/B2_F0_PHYSICAL7/result'
SRC=ROOT/'runtime/var/research-jobs/continuous-hedge-preflight-20261025/source-06f7577/runtime/coinmaster/strategy'
DAY=86400*10**9; H4=4*3600*10**9
pins={}
def pin(p):
 pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return p
def read(p):return json.loads(pin(p).read_text())
contract=read(OUT/'frozen-cheap-contract.json');read(OUT/'contract-amendment-precalculation.json')
a=read(P/'paired-prefix-B2_F0.json')
orders=list(csv.DictReader(pin(P/'paired-prefix-B2_F0-orders.csv').open()))
for n in ['split_cover.py','paired_prefix.py','wave_overlay.py','market_redesign.py']:pin(SRC/n)
events=a['paired_prefix_audit']['events'];parents={x['episode_id']:x for x in a['split_cover_audit']['parents']}
acts=[];cur=None
for i,e in enumerate(events):
 if e['event']=='ACTIVATION_SELECTED':
  cur={'activation_index':len(acts)+1,'event_index':i,'signal':e,'events':[]};acts.append(cur)
 if cur:cur['events'].append(e)
 # active instance is released before next activation; parent terminal tracked separately
assert len(acts)==16
fills=a['fill_audit']
def utc(n):return datetime.fromtimestamp(int(n)/1e9,timezone.utc).isoformat()
def ftime(f):return int(f['fill_ns'])
A=[]; tpmap={}; ts=set()
for act in acts:
 s=act['signal']; es=act['events'];par=parents[s['parent']];st=int(s['timestamp_ns'])
 inv=next((e for e in es if e['event']=='RISK_INVALID_OR_EXPIRED'),None)
 tp=[e for e in es if e['event']=='ACTUAL_FILL' and e['kind']=='TP']
 entry=next(e for e in es if e['event']=='ACTUAL_FILL' and e['kind']=='ENTRY')
 terminal=next((e for e in es if e['event']=='PARENT_NATIVE_TERMINAL_FLAT' and e['parent']==s['parent']),None)
 row={'activation':act['activation_index'],'branch':s['branch'],'parent':s['parent'],'activation_utc':utc(st),'entry_utc':utc(entry['timestamp_ns']),'invalidation_utc':utc(inv['timestamp_ns']) if inv else None,'TP_count':len(tp),'original_Q0':par['quantity'],'parent_start_utc':utc(par['start_ns']),'generic_deadline_metadata_not_effective_realU':utc(par['deadline_ns']),'effective_expiry':'NO_GENERIC_TIME_EXPIRY_REAL_U_GTC; first BTC TP/ordinary exit/flat/pause/native terminal stops','saved_split_stop_reason':par.get('stop_reason'),'saved_parent_closed':par['closed'],'source_event_index':act['event_index']}
 if inv:
  t=int(inv['timestamp_ns']);bf=[f for f in fills if 'BTC' in f['instrument'] and int(par['start_ns'])<=ftime(f)<=t]
  fe=sum((D(f['qty']) for f in bf if f['action']=='BTC_ENTRY'),D(0));de=sum((D(f['qty']) for f in bf if f['action']!='BTC_ENTRY'),D(0));b=fe-de;q0=D(par['quantity']);ordinary=[f for f in bf if f['action']!='BTC_ENTRY' and not f['reason'].startswith('PAIRED')]
  debt=[f for f in bf if f['reason'].startswith('PAIRED') and f['action']!='BTC_ENTRY']
  rights=max(D(0),q0-fe);cap=max(D(0),q0-de-b)
  phase='REAL_U_ORIGINAL_LIMIT_GTC_NO_MARKET_FALLBACK'
  hard=False # Generic day stop bypassed by _md_enabled effective path
  factual='NO_UNFILLED_RIGHT' if rights==0 else 'FORBIDDEN_HARD_UTC_STOP' if hard else 'FORBIDDEN_FLAT' if b<=0 else 'FORBIDDEN_ORDINARY_BTC_EXIT' if ordinary else 'POTENTIAL_UNFILLED_RIGHT_REQUIRES_NEW_EXPLICIT_REVERSIBLE_LOCK_CONTRACT'
  child=[o for o in orders if o['instrument_id'].startswith('BTC') and o['is_reduce_only']=='False' and int(par['start_ns'])<=int(o['ts_init'])<=t and o['type']=='LIMIT']
  row.update(decision_ns=t,decision_utc=utc(t),F_ever=str(fe),D_permanent=str(de),B_current=str(b),remaining_original_unfilled=str(rights),original_cap_less_closed_and_held=str(cap),prior_ordinary_BTC_exits=len(ordinary),prior_paired_protective_reductions=len(debt),phase=phase,factual_unfilled_right=factual,original_limit_orders=[{k:o[k] for k in ['client_order_id','price','quantity','filled_qty','status','ts_init','ts_last','time_in_force']} for o in child],quote_eligibility='UNKNOWN_NO_BID_ASK_ACK_STATE_AT_RISK_OFF',native_margin='UNKNOWN',restore_admission='NOT_ADMITTED_EXISTING_MONOTONE_STOP_IS_PERMANENT')
 else:row.update(factual_unfilled_right='UNKNOWN_NO_ACTUAL_RISK_OFF_BEFORE_OWNER_RELEASE',restore_admission='NOT_ADMITTED')
 A.append(row)
 for k,e in enumerate(tp):
  t=int(e['timestamp_ns']);ts.add(t);tpmap.setdefault(t,[]).append((act,e,k,inv,terminal))
# One coherent stream pass: only retain targeted snapshots, maintain actual prior peak.
snaps={};pre={};peak=D('10000');stream=pin(P/'coherent-native-events.jsonl.gz');n=0
for line in gzip.open(stream,'rt'):
 r=json.loads(line);n+=1;eq=None if r['equity'] is None else D(r['equity']);t=int(r['event_ns'])
 if t in ts and r['kind']=='PRE_FILL_LAST_COMMITTED_NATIVE_COPY':pre[r['native_id']]=r
 if t in ts and r['kind']=='POST_FILL_COMMITTED_NATIVE':snaps.setdefault(t,[]).append({'row':r,'prior_peak':str(peak)})
 if eq is not None:peak=max(peak,eq)
# SIMPLE close-to-close daily returns; close belongs to completed bar end.
daily={};fund={}
for asset in ['BTC','SOL']:
 d=pd.read_parquet(pin(ROOT/f'runtime/var/data/normalized/bybit-{asset}USDT-daily.parquet'))
 vals=[(int(r.open_time_ms)*10**6,D(str(r.close))) for r in d.itertuples()]
 daily[asset]={vals[i][0]+DAY:vals[i][1]/vals[i-1][1]-1 for i in range(1,len(vals)) if vals[i][0]-vals[i-1][0]==DAY}
 f=pd.read_parquet(pin(ROOT/f'runtime/var/data/normalized/bybit-{asset}USDT-funding.parquet'))
 fd={}
 for r in f.itertuples():
  t=int(r.funding_time_ms)*10**6;fd.setdefault(t//DAY,[]).append((t,abs(D(str(r.funding_rate)))))
 fund[asset]=fd
B=[]
for t,items in tpmap.items():
 for act,e,k,inv,terminal in items:
  f=[f for f in fills if ftime(f)==t and f['reason']=='PAIRED_TP' and D(f['qty'])==D(e['qty']) and D(f['px'])==D(e['price'])]
  oo=next(o for o in orders if o['client_order_id']==e['order_id'])
  candidates=[v for v in snaps.get(t,[]) if f and v['row']['native_id']==oo['last_trade_id']]
  # Pair by exact decrease shown in pre/post receipts via native trade id is checked below.
  row={'activation':act['activation_index'],'branch':act['signal']['branch'],'TP_ordinal':k+1,'primary_first_TP':k==0,'TP_ns':t,'TP_utc':utc(t),'order_id':e['order_id'],'candidate_path_limit':'Later TPs use already-cut actual BTC; no retained-candidate path inferred'}
  # Single actual native fill at these stamps; require exact source audit match and singleton.
  if len(f)!=1 or len(candidates)!=1:
   row.update(status='UNKNOWN_NOT_ADMITTED',missing=['unique actual fill/post-fill snapshot']);B.append(row);continue
  r=candidates[0]['row'];E=D(r['equity']);Pprior=D(candidates[0]['prior_peak']);head=max(D(0),E-D('.5')*Pprior)
  pos={('BTC' if 'BTC' in p['instrument_id'] else 'SOL'):p for p in r['positions']}
  N={asset:(D(pos[asset]['quantity'])*D(pos[asset]['native_price'])*(1 if pos[asset]['side']=='LONG' else -1)) if asset in pos else D(0) for asset in ['BTC','SOL']}
  # A genuinely flat SOL position after TP is known zero, not missing.
  fee=D('.00055')*sum(map(abs,N.values()));cutoff=(t//DAY)*DAY-DAY
  ends=sorted(set(daily['BTC'])&set(daily['SOL']));ends=[z for z in ends if z<=cutoff]
  stress={};missing=[]
  for w in [90,30]:
   window=ends[-w:];valid=len(window)==w and all(window[i]-window[i-1]==DAY for i in range(1,len(window)))
   if not valid:missing.append(f'D1_{w}_contiguous');stress[str(w)]={'status':'UNKNOWN'};continue
   market=max(D(0),max(-N['BTC']*daily['BTC'][z]-N['SOL']*daily['SOL'][z] for z in window))
   days=[(z-DAY)//DAY for z in window];allow=[];ok=True
   for day in days:
    vv=D(0)
    for asset in ['BTC','SOL']:
     ff=fund[asset].get(day,[])
     if len(ff)!=3 or any(x[0]>=t for x in ff):ok=False
     vv+=abs(N[asset])*sum((v for _,v in ff),D(0))
    allow.append(vv)
   funding=max(allow) if ok else None
   if not ok:missing.append(f'funding_{w}_complete_3_per_day')
   loss=market+fee+funding if funding is not None else None
   stress[str(w)]={'first_return_end_utc':utc(window[0]),'last_return_end_utc':utc(window[-1]),'market_stress':str(market),'future_exit_fee':str(fee),'past_daily_funding_charge_allowance':str(funding) if funding is not None else 'UNKNOWN','total_stress':str(loss) if loss is not None else 'UNKNOWN','headroom_pass':loss<=head if loss is not None else 'UNKNOWN'}
  deadline=(t//H4+1)*H4+60*10**9;off=int(inv['timestamp_ns']) if inv else None
  # Existing actual risk event includes boundary invalidation OR branch expiry: distinguish.
  branch_exp=int(next(x for x in act['events'] if x['event']=='ACTUAL_FILL' and x['kind']=='ENTRY')['timestamp_ns'])+(4 if act['signal']['branch']=='B2' else 8)*3600*10**9
  release='ACTUAL_RISK_OFF_BY_DEADLINE' if off and t<off<=deadline else 'ACTUAL_RISK_OFF_AFTER_DEADLINE' if off and off>deadline else 'UNKNOWN_OWNER_RELEASED_WITHOUT_RISK_OFF'
  if off and off<=t:release='ACTUAL_ALREADY_OFF'
  pr=pre[r['native_id']]; prepos={p['instrument_id']:p for p in pr['positions']}; postsol=next((D(p['quantity']) for p in r['positions'] if 'SOL' in p['instrument_id']),D(0)); presol=next(D(p['quantity']) for p in pr['positions'] if 'SOL' in p['instrument_id']); assert presol-postsol==D(e['qty']); assert next(D(p['quantity']) for p in pr['positions'] if 'BTC' in p['instrument_id'])==next(D(p['quantity']) for p in r['positions'] if 'BTC' in p['instrument_id'])
  row.update(native_postTP_identity_proof=True,pre_sequence=pr['sequence'],E_actual=str(E),P_prior_coherent=str(Pprior),headroom=str(head),signed_marked_notionals={z:str(v) for z,v in N.items()},observer_sequence=r['sequence'],observer_epoch=r['epoch'],observer_native_id=r['native_id'],mark_available_ns=r['mark_available_ns'],cash_identity=E==D(r['cash'])+sum((D(p['native_upnl']) for p in r['positions']),D(0)),stress=stress,critical_missing=missing,market_stress_admission='PASS_PREREQUISITE_ONLY' if not missing and stress['90']['headroom_pass'] is True else 'NOT_ADMITTED',native_margin_admission='UNKNOWN_SEPARATE',next_H4_plus60_utc=utc(deadline),actual_risk_off_utc=utc(off) if off else None,actual_risk_off_reason='BOUNDARY_BEFORE_BRANCH_EXPIRY' if off and off<branch_exp else 'BOUNDARY_OR_BRANCH_EXPIRY' if off else 'UNKNOWN',release_timing=release,release_limit='Observed actual owner risk state only; after intervening debt cut candidate continuing state UNKNOWN',retention_admission='NOT_ADMITTED_NATIVE_MARGIN_AND_CONTINUING_STATE_UNKNOWN')
  B.append(row)
assert len(B)==8
result={'task':contract['task'],'frozen_contract_sha256':pins[str(OUT/'frozen-cheap-contract.json')],'A_all_activations':A,'B_all_actual_TPs':B,'counts':{'activations':len(A),'invalidations':sum(x['invalidation_utc'] is not None for x in A),'branches':dict(Counter(x['branch'] for x in A)),'right_cohorts':dict(Counter(x['factual_unfilled_right'] for x in A)),'all_TPs':len(B),'primary_first_TPs':sum(x['primary_first_TP'] for x in B),'stress_primary_admission':dict(Counter(x['market_stress_admission'] for x in B if x['primary_first_TP'])),'C_primary_release':dict(Counter(x['release_timing'] for x in B if x['primary_first_TP']))},'data_availability':{'postTP_predebt_actual_states':'PRESENT_ALL8','prior_coherent_event_peak':'PRESENT_SINGLE_STREAM_SCAN','quote_bid_ask_ACK_margin_at_riskOFF':'UNKNOWN','causal_future_retained_candidate_equity':'NOT_COMPUTED','riskOFF_events':'ONLY_WHILE_ACTUAL_OWNER_ALIVE; boundary/expiry conflated at expiry','native_stream_rows_read':n},'failed_hypotheses':['RiskOFF alone restores original BTC rights: false under current permanent monotone stop and original expiry/TP constraints','All SOL TPs safely permit retained BTC: not established; stress is only a market prerequisite, native margin/continuation missing','Later actual TPs give an uncut BTC candidate path: false; BTC already reduced','Immediate SOL TP creates realized wealth credit for retaining BTC: not used'], 'engines':0,'downloads':0,'product_changes':0,'pins':pins}
(OUT/'causal-admission-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result['counts'],indent=2))
