"""Descriptive original E4 path only; no simulated position/cash/equity or engine."""
import csv,gzip,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).parent
P=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/b-50-90-next-20261023/E4/result/minute-native-settled-receipts.csv.gz')
def utc(ns): return datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat()
def asset(p):return p['instrument_id'].split('USDT')[0]
def side(p):return 1 if p['side']=='2' else -1
H=10000.; excursion=0; ex=None; previous={}; counters={'BTC':0,'SOL':0}; opened={}; pending={}; events=[]; excursions=[]; months={}; rows=0
with gzip.open(P,'rt') as f:
 for row in csv.DictReader(f):
  rows+=1;ns=int(row['source_quote_ns']); E=float(row['paired_close_equity']); month=utc(ns)[:7];m=months.setdefault(month,dict(receipts=0,raw_first_cycle_triggers=0,first_per_excursion=0,proxy_restores=0));m['receipts']+=1
  if E>=H:
   if ex:ex['recovery_ns']=ns;excursions.append(ex);ex=None
   H=E
  dd=1-E/H
  if dd>0 and ex is None:
   excursion+=1;ex=dict(id=excursion,peak=H,start_ns=ns,max_dd=dd,trough_ns=ns,events=[])
  if ex and dd>ex['max_dd']:ex['max_dd']=dd;ex['trough_ns']=ns
  ps={asset(p):p for p in json.loads(row['native_positions_and_mark_ohlc_json'])}
  for a in ['BTC','SOL']:
   p=ps.get(a);old=previous.get(a)
   if p is None:
    if a in pending:
     ev=pending.pop(a);ev.setdefault('original_cycle_end_ns',ns);ev.setdefault('original_first_quantity_decrease_ns',ns)
    opened.pop(a,None)
   elif old is None or p['side']!=old['side']:
    counters[a]+=1;opened[a]=ns
    if a in pending:
     ev=pending.pop(a);ev.setdefault('original_cycle_end_ns',ns);ev.setdefault('original_first_quantity_decrease_ns',ns)
   if p and a in pending:
    ev=pending[a];q=float(p['quantity']);mark=float(p['mark_ohlc']['close']);sg=side(p)
    if old and q<float(old['quantity'])-1e-10:ev.setdefault('original_first_quantity_decrease_ns',ns)
    signed=sg*(mark/ev['trigger_mark']-1)
    if signed>0:ev.setdefault('original_first_price_reclaim_ns',ns)
    if dd<=.35:ev.setdefault('original_first_DD35_ns',ns)
    # UTC4h boundary with 4h entirely post-trigger; trigger mark is NOT an actual cut VWAP.
    if ns%14400000000000==0 and ns-ev['ns']>=14400000000000 and dd<=.35 and signed>0:
     ev.setdefault('proxy_4h_DD35_reclaim_ns',ns)
    if ev.get('proxy_4h_DD35_reclaim_ns') and ns>ev['proxy_4h_DD35_reclaim_ns'] and dd<=.35 and signed>0 and 'proxy_next_quote_restore_ns' not in ev:
     ev['proxy_next_quote_restore_ns']=ns;ev['proxy_restore_mark']=mark;ev['signed_reentry_gap_plus_two_taker_fee_fraction']=sg*(mark/ev['trigger_mark']-1)+.0011;ev['original_reduction_before_proxy_restore']=ev.get('original_first_quantity_decrease_ns',ns+1)<=ns;m['proxy_restores']+=1
  if ex and dd>=.40:
   losses=[]
   for a,p in ps.items():
    sg=side(p);q=float(p['quantity']);avg=float(p['avg_px_open']);mark=float(p['mark_ohlc']['close']);upnl=sg*q*(mark-avg)
    if upnl<0:losses.append((upnl,a,p))
   if losses:
    upnl,a,p=min(losses);q=float(p['quantity']);mark=float(p['mark_ohlc']['close']);cap=max(0.,E-.50*H)/.05;N=q*mark
    if N>cap and -upnl>max(0.,E-.50*H) and not (a in pending and pending[a]['cycle']==counters[a]):
     ev=dict(event=len(events)+1,ns=ns,utc=utc(ns),asset=a,cycle=counters[a],cycle_open_ns=opened[a],excursion=ex['id'],excursion_trigger_ordinal=len(ex['events'])+1,H=H,E=E,DD=100*dd,own_UPnL=upnl,quantity=q,trigger_mark=mark,own_loss_over_current_mark_notional_percent=100*(-upnl/N),notional=N,cap_notional=cap,raw_cut_quantity=q-cap/mark,raw_cut_fraction=1-cap/N,eligibility='UNKNOWN_PENDING_ACK_ENTRY_TP_RIGHTS_NOT_IN_TRACE')
     events.append(ev);pending[a]=ev;ex['events'].append(ev['event']);m['raw_first_cycle_triggers']+=1;m['first_per_excursion']+=len(ex['events'])==1
  previous=ps
if ex:excursions.append(ex)
for ev in events:
 x=next(x for x in excursions if x['id']==ev['excursion']);ev['original_excursion_max_DD']=100*x['max_dd'];ev['original_excursion_recovery_ns']=x.get('recovery_ns');ev['original_excursion_below50']=x['max_dd']<.5
 ev['price_recovered_but_no_proxy_restore']=bool(ev.get('original_first_price_reclaim_ns')) and not ev.get('proxy_next_quote_restore_ns')
 ev['proxy_restore_validity']='UNKNOWN_ACTUAL_CUT_VWAP_ORDINARY_EXIT_CREDIT_RIGHTS_NATIVE_GATES'
keys=list(dict.fromkeys(k for ev in events for k in ev))
with (R/'owner-screen-gated-events.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(events)
with (R/'owner-screen-gated-monthly.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['month','receipts','raw_first_cycle_triggers','first_per_excursion','proxy_restores']);w.writeheader();w.writerows(dict(month=k,**v) for k,v in months.items())
summary=dict(status='DESCRIPTIVE_ORIGINAL_E4_ONLY_NOT_ELIGIBILITY_OR_COUNTERFACTUAL',source=str(P),source_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),rows=rows,months=len(months),native_cycles=counters,rule=dict(DD_trigger=.40,floor=.50,selected_leg_shock=.05,restore_DD=.35,restore_closedbar='4h',selected_leg='MOST_NEGATIVE_NATIVE_CURRENT_AVERAGE_UPNL',loss_dominance='ABS_NEGATIVE_OWN_UPNL_GREATER_THAN_REMAINING_E_MINUS_0_50H_CUSHION'),opportunities=len(events),first_per_excursion=sum(ev['excursion_trigger_ordinal']==1 for ev in events),original_below50_opportunities=sum(ev['original_excursion_below50'] for ev in events),proxy_restores=sum('proxy_next_quote_restore_ns' in ev for ev in events),proxy_restores_after_original_reduction=sum(ev.get('original_reduction_before_proxy_restore',False) for ev in events),price_recovered_but_no_proxy_restore=sum(ev['price_recovered_but_no_proxy_restore'] for ev in events),excursions_ge40=[x for x in excursions if x['max_dd']>=.4],events=events)
(R/'owner-screen-gated-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['events','excursions_ge40']},indent=2))
