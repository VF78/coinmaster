from pathlib import Path
import json,csv,hashlib,ast
from decimal import Decimal as D
P=Path(__file__).resolve().parent
S=D('6077107.23887483');F=D('5470396.514987347')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
review=json.loads((P/'reviewer-result-validation.json').read_text())
rows=[dict(recipe='S0_ARCHIVE',status='IMMUTABLE_REFERENCE',TOTAL=str(S),ROI_percent=str((S/10000-1)*100),net_profit_retention_percent='100',settled_DD_percent='66.25691486468686414439256686',DD_qualification='COMPLETE_SETTLED_RECEIPTS',fills=621,BTC_fills=416,SOL_fills=205,fees='945927.73761825',funding_signed='UNKNOWN',pass_50_90=False)]
ref=P/'verifier-reference-fills.csv';agg={};turn=D(0)
with ref.open(newline='') as h:
 for v in csv.DictReader(h):
  side=v['liquidity_side'].lower();notional=D(v['filled_qty'])*D(v['avg_px']);fees=sum((D(x.rsplit(' ',1)[0]) for x in ast.literal_eval(v['commissions'])),D(0));agg[side+'_notional']=agg.get(side+'_notional',D(0))+notional;agg[side+'_fees']=agg.get(side+'_fees',D(0))+fees;turn+=notional
rows[0].update({k:str(v) for k,v in agg.items()});rows[0]['turnover']=str(turn);rows[0]['native_reference_csv_sha256']=sha(ref);rows[0]['fee_sum_exact']=sum((v for k,v in agg.items() if k.endswith('_fees')),D(0))==D(rows[0]['fees']);assert rows[0]['fee_sum_exact']
seen=set()
for p in sorted(P.glob('owner-*-receipt.json')):
 if 'before-coverage' in p.name:continue
 a=json.loads(p.read_text());name=a['recipe'];assert name not in seen;seen.add(name)
 r=review['runs'].get('B' if name=='BTC_REGIME_REENTRY_BAND_05' else name,{})
 t=D(a['total']);risk=D(a.get('settled_native_DD_percent',a['settled_post_quote_DD_percent']));cov=a['settled_observer_coverage']
 row=dict(recipe=name,status=a['status'],TOTAL=str(t),ROI_percent=str((t/10000-1)*100),net_profit_retention_percent=str((t-10000)/(S-10000)*100),settled_DD_percent=str(risk),DD_qualification=cov['qualification'],risk_receipts=cov['receipts'],risk_unavailable=cov['unavailable_intervening_native_mutation'],fills=a['fills'],BTC_fills=r.get('BTC_fills','PENDING_REVIEW'),SOL_fills=r.get('SOL_fills','PENDING_REVIEW'),fees=a['native_fees'],turnover=r.get('native_fill_turnover','PENDING_REVIEW'),funding_signed='UNKNOWN',funding_events=a['funding']['count'],liquidations=a['liquidation_count'],source=a['source_commit'],config_sha256=a['config_sha256'],artifact=a['artifact'],artifact_sha256=a['artifact_sha256'],receipt=str(p),receipt_sha256=sha(p),pass_50_90=(t>=F and risk<=50 and cov['complete']),callback_DD_percent=a['all_native_close_DD_percent'])
 f=Path(a['exports']['native-fill-audit.csv']['path']);agg={}
 with f.open(newline='') as h:
  for v in csv.DictReader(h):
   side=v['native_liquidity_side'].lower();agg[side+'_notional']=agg.get(side+'_notional',D(0))+D(v['notional']);agg[side+'_fees']=agg.get(side+'_fees',D(0))+D(v['commission'])
 row.update({k:str(v) for k,v in agg.items()});row['fee_sum_exact']=sum((v for k,v in agg.items() if k.endswith('_fees')),D(0))==D(a['native_fees']);assert row['fee_sum_exact']
 rows.append(row)
order=['S0_ARCHIVE','C0','H4_4H_E34_G050','H4_4H_E13_G050','H4_4H_E89_G050','H4_4H_E34_G100','H4_4H_E13_G100','H4_4H_E89_G100','BTC_REGIME_REENTRY_BAND_05'];rows.sort(key=lambda r:order.index(r['recipe']) if r['recipe'] in order else 99)
status='IN_PROGRESS' if len(rows)<10 else 'COMPLETE_BOUNDED_NATIVE_CYCLE'
out={'status':status,'criterion':{'max_DD_percent':'50','min_net_profit_retention_percent':'90','min_TOTAL_exact':str(F)},'funding_signed':'UNKNOWN_NOT_ZERO','results':rows};(P/'comparison.json').write_text(json.dumps(out,indent=2)+'\n')
keys=list(dict.fromkeys(k for r in rows for k in r))
with (P/'comparison.csv').open('w',newline='') as h:
 w=csv.DictWriter(h,keys,lineterminator='\n');w.writeheader();w.writerows(rows)
print(json.dumps({'status':status,'rows':len(rows),'pass_50_90':[r['recipe'] for r in rows if r['pass_50_90']]}))
