"""Explicit analytical allocation of actual SOL fills; no separate native positions/cash."""
import argparse,json,csv,ast,hashlib
from decimal import Decimal as D
from collections import defaultdict,deque
from datetime import datetime,timezone
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--result',required=True);ap.add_argument('--label',required=True);a=ap.parse_args();p=Path('reports/btc-split-sol-cover-20261018');r=json.load(open(a.result));nf=defaultdict(deque)
for f in csv.DictReader(open(r['execution_artifacts']['fills']['path'])):
 ts=int(datetime.fromisoformat(f['ts_last']).timestamp())*1000000000;sym='BTC' if f['instrument_id'].startswith('BTC') else 'SOL';nf[ts,sym,D(f['filled_qty']),D(f['avg_px']).quantize(D('.000001'))].append(f['side'])
components={k:dict(q=D(0),price=D(0),unallocated_entry_fee=D(0),gross=D(0),entry_fees=D(0),exit_fees=D(0),entry_turnover=D(0),exit_turnover=D(0),entry_fills=0,exit_allocations=0) for k in ('CORE','TACTICAL')};records=[];tactical_current=None;native_q=D(0);unmatched=[]
for f in r['fill_audit']:
 if not f['instrument'].startswith('SOL'):continue
 q=D(f['qty']);px=D(f['px']);fee=D(f['commission']);ns=int(f['fill_ns']);side=nf[ns,'SOL',q,px.quantize(D('.000001'))].popleft();sign=1 if side=='BUY' else -1
 if f['action']=='SOL_ADD':
  kind='TACTICAL' if f['reason']=='SOL_COVER_TACTICAL' else 'CORE';c=components[kind];c['price']=(c['q']*c['price']+q*px)/(c['q']+q);c['q']+=q;c['unallocated_entry_fee']+=fee;c['entry_fees']+=fee;c['entry_turnover']+=q*px;c['entry_fills']+=1;native_q+=q
  if kind=='TACTICAL':
   if tactical_current is None:tactical_current=dict(start_ns=ns,side=side,entry_quantity=str(q),entry_notional=q*px,entry_price=str(px),entry_fills=1,entry_fee=fee,exit_fee=D(0),gross=D(0),allocated_entry_fee=D(0),exit_quantity=D(0),end_ns=None)
   else:
    tactical_current['entry_quantity']=str(D(tactical_current['entry_quantity'])+q);tactical_current['entry_notional']+=q*px;tactical_current['entry_price']=str(tactical_current['entry_notional']/D(tactical_current['entry_quantity']));tactical_current['entry_fee']+=fee;tactical_current['entry_fills']+=1
 else:
  remain=q;native_q-=q
  for kind in ('TACTICAL','CORE'):
   c=components[kind];take=min(remain,c['q'])
   if take<=0:continue
   allocation_fee=fee*take/q;entry_fee=c['unallocated_entry_fee']*take/c['q'];gross=take*(px-c['price'])*(-sign);c['q']-=take;c['unallocated_entry_fee']-=entry_fee;c['gross']+=gross;c['exit_fees']+=allocation_fee;c['exit_turnover']+=take*px;c['exit_allocations']+=1;remain-=take
   if kind=='TACTICAL':
    assert tactical_current is not None;tactical_current['exit_fee']+=allocation_fee;tactical_current['allocated_entry_fee']+=entry_fee;tactical_current['gross']+=gross;tactical_current['exit_quantity']+=take
    if c['q']==0:tactical_current['end_ns']=ns;tactical_current['net_ex_funding']=tactical_current['gross']-tactical_current['allocated_entry_fee']-tactical_current['exit_fee'];records.append(tactical_current);tactical_current=None
  assert remain==0,(f,remain)
 assert sum(c['q'] for c in components.values())==native_q
assert native_q==0 and tactical_current is None
for c in components.values():c['net_ex_funding']=c['gross']-c['entry_fees']-c['exit_fees'];assert c['q']==0
actual=json.load(open(p/f'comparison-analysis-{a.label}.json'))['confirmed_fill_weighted_average_attribution']['SOL'];assert abs(sum(c['gross'] for c in components.values())-D(actual['gross']))<D('.000001');assert sum(c['entry_fees']+c['exit_fees'] for c in components.values())==D(actual['actual_fees']);assert abs(sum(c['net_ex_funding'] for c in components.values())-D(actual['net_ex_funding']))<D('.000001')
for rec in records:
 for k in ('start_ns','end_ns'):rec[k.replace('_ns','_utc')]=datetime.fromtimestamp(rec[k]/1e9,timezone.utc).isoformat()
with (p/f'comparison-analysis-{a.label}-tactical-allocations.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]) if records else ['NO_TACTICAL_FILLS']);w.writeheader();w.writerows(records)
result=dict(label=a.label,components=components,tactical_cycles=len(records),tactical_wins=sum(x['net_ex_funding']>0 for x in records),tactical_losses=sum(x['net_ex_funding']<0 for x in records),tactical_worst=min((x['net_ex_funding'] for x in records),default=None),tactical_best=max((x['net_ex_funding'] for x in records),default=None),native_SOL_gross=actual['gross'],native_SOL_actual_fees=actual['actual_fees'],confirmed_fill_SOL_net_ex_funding=actual['net_ex_funding'],reconciled_to_actual_SOL_total=True,method='ENTRYreasonSOL_COVER_TACTICAL allocatedTACTICAL, allotherSOL_ADD CORE. Actualnativeclosingfillquantity allocatedTACTICALfirst thenCORE perplanpriority. RepeatednativeTACTICALentryfillsbeforebudgetflat areonecyclewithweightedremaininginventorycost. Percomponentactualfillweightedaverageentrycost; closefeesproportionaltoallocatednativecloseqty; entryfeesproportionaltoinventory. Single nativeNETTINGposition: allocationisanalyticalandnonunique, NOTnativepercomponentcash/PnL. No synthetic fills or totalROIadjustment.',funding='UNKNOWN; no componentfundingallocation or proxy zero',limits='ComponentresultdiffvsSOL50notisolatedcausalbenefit: BTC/COREquantitiescompounddifferently. Logical inventory allocationdoesnotestablishseparatenativepositions. ActualTOTAL/DD remainprimary.')
(p/f'comparison-analysis-{a.label}-components.json').write_text(json.dumps(result,indent=2,default=str)+'\n');print(json.dumps(result,indent=2,default=str))
