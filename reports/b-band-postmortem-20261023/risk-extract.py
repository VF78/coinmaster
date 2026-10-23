"""Bounded saved-stream diagnostic only; never executes strategy or reconstructs cash."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,gzip,json,hashlib
ROOT=Path(__file__).resolve().parents[2]; SRC=ROOT/'reports/sol-conditional-hedge-btc-band-20261023'; OUT=Path(__file__).parent
m=json.loads((SRC/'owner-analysis-manifest.json').read_text()); results={}; hashes=[]
def iso(t):return datetime.fromtimestamp(int(t)/1e9,timezone.utc).isoformat()
def out(n,x):(OUT/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for spec in m['inputs']:
 if spec['recipe'] not in ('S0','BTC_REGIME_REENTRY_BAND_05'):continue
 name=spec['recipe']; d=json.loads(Path(spec['artifact']).read_text()); risk=d['minute_risk_observations'];top=risk['settled_native_close_receipts']['curve']['top3_distinct_excursions']; targets={int(v['timestamp_ns']) for e in top for v in [e['peak'],e['trough'],e.get('recovery')] if v}; snaps={};exc=[];peak=D(10000);peakts=1725148800000000000;current=None; thresholds=(20,30,40,45,50);count=0
 for r in csv.DictReader(gzip.open(spec['settled_trace'],'rt')):
  count+=1;t=int(r['receipt_ns']);eq=D(r['paired_close_equity']); dd=(peak-eq)/peak*100
  if t in targets:snaps[str(t)]=r
  if eq>=peak:
   if current:current['recovery_ns']=t;current['recovery_utc']=iso(t);exc.append(current);current=None
   peak=eq;peakts=t
  else:
   if current is None:current=dict(peak_ns=peakts,peak_utc=iso(peakts),peak_equity=str(peak),maxdd_percent='0',thresholds={})
   if dd>D(current['maxdd_percent']):current.update(maxdd_percent=str(dd),trough_ns=t,trough_utc=iso(t),trough_equity=str(eq))
   for th in thresholds:
    if dd>=th and str(th) not in current['thresholds']:current['thresholds'][str(th)]=dict(r,utc=iso(t),drawdown_percent=str(dd))
 if current:exc.append(current)
 exc=[e for e in exc if D(e['maxdd_percent'])>=20];assert count==1051199;assert len(snaps)==len(targets)
 for e in top:
  for k in ('peak','trough','recovery'):
   if e.get(k):assert D(snaps[e[k]['timestamp_ns']]['paired_close_equity'])==D(e[k]['equity'])
 result=dict(top3=top,snapshots=snaps,excursions_ge20=exc,rows=count,liquidation_count=d['liquidation_count'],native_order_rejections=d['native_order_rejections'],conditional_margin_breach_count=risk['potential_conditional_intrabar_margin_breach_count'],conditional_OHLC=risk['curves']['conditional_ohlc_adverse']['top3_distinct_excursions'],conditional_upper_to_later_lower=risk['conditional_upper_to_later_lower_bound'],fill_events=[],denial_events=[],funding_signed_asset='UNKNOWN')
 # Saved native events around each independent interval, through recovery or end. No hypothetical deletions.
 for i,e in enumerate(top,1):
  a=int(e['peak']['timestamp_ns']);b=int((e.get('recovery') or {'timestamp_ns':'1788220800000000000'})['timestamp_ns'])
  result['fill_events'] += [dict(interval=i,utc=iso(f['fill_ns']),**f) for f in d['fill_audit'] if a-86400000000000<=int(f['fill_ns'])<=b]
  result['denial_events'] += [dict(interval=i,utc=iso(f['timestamp']),**f) for f in d['pre_submit_tier_margin_gate_blocks'] if a<=int(f['timestamp'])<=b]
 if name!='S0':
  # One scan native risk callback stream: match source marks for endpoint/threshold receipt snapshots.
  source_targets={int(r['source_quote_ns']) for r in snaps.values()}; source_targets.update(int(r['source_quote_ns']) for e in exc for r in e['thresholds'].values()); margin=[]
  for r in csv.DictReader(gzip.open(risk['trace_path'],'rt')):
   if r['phase']=='post_quote_paired_close' and int(r['close_available_ns']) in source_targets:margin.append(r)
  result['native_margin_at_source_callbacks']=margin
 results[name]=result;hashes.append(dict(recipe=name,artifact=spec['artifact'],artifact_sha256=sha(spec['artifact']),trace_sha256=sha(spec['settled_trace']),matches_existing_manifest=sha(spec['settled_trace'])==spec['settled_trace_sha256']))
 print(name,count,len(exc),'excursions >=20',flush=True)
out('risk-native-extract.json',results);out('risk-provenance.json',dict(inputs=hashes,method='One settled trace scan S0/B; one B callback risk scan; no engine. SHA256 checked saved pins; endpoint equity arithmetic exact Decimal.',script_sha256=sha(__file__)))
