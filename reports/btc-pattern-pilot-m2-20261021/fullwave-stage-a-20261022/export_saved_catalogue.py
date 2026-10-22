"""Exports/visual QA from the sealed Stage A catalogue only; never reads prices or reruns detector."""
from pathlib import Path
import csv,hashlib,json,statistics
from collections import Counter
from datetime import datetime,timezone
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).parent/'run';cat=json.loads((ROOT/'catalogue.json').read_text());summary=json.loads((ROOT/'SUMMARY.json').read_text())
def iso(t):return datetime.fromtimestamp(t/1000,timezone.utc).isoformat()
def dumpcsv(name,rows):
    rows=list(rows)
    with (ROOT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
dumpcsv('pivots.csv',({k:(iso(v) if k in ('bar','confirmation','confirmation_bar') else v) for k,v in p.items()} for p in cat['pivots']))
wave_rows=[]
for w in cat['waves']:
    r={k:v for k,v in w.items() if k not in ('A','B','C','D')};r['D']=iso(w['D'])
    for role in 'ABC':
        for k in ('id','bar','price','confirmation','lag_days'):r[role+'_'+k]=iso(w[role][k]) if k in ('bar','confirmation') else w[role][k]
    r['A_C_days']=(w['C']['bar']-w['A']['bar'])/86400000;wave_rows.append(r)
dumpcsv('waves.csv',wave_rows)
# Fixed schema also retains descriptive non-fold queries with blank support.
qr=[]
for q in cat['macro_queries']:
    row=dict(id=q['id'],q=iso(q['q']),A=q['A']['id'] if q['A'] else '',B=q['B']['id'],fold=q['fold'] or '',left_truncated=q['left_truncated'],status=q['status'],h1_complete=q['h1_complete'],h72_mature_by_end=q['h72_mature_by_end'],old_h1_children=q['old_h1_children'],old_scored_children=q['old_scored_children'])
    for contract in ('OLD_STRICT','CAUSAL_WALK_FORWARD','CYCLE_DISJOINT'):
        support=q['support'].get(q['fold'],{}).get(contract,{})
        for k in ('raw','nonoverlap_upper_bound'):row[contract+'_'+k]=support.get(k,'')
    qr.append(row)
dumpcsv('macro-query-support.csv',qr)
dumpcsv('old-h1-mapping.csv',(dict(old_id=m['old_id'],scored_198=m['scored_198'],origin=iso(m['origin']),prefix_asof=iso(m['prefix']['asof']),mode=m['prefix']['mode'],status=m['prefix']['status'],known_A=m['prefix']['A']['id'] if m['prefix']['A'] else '',known_B=m['prefix']['B']['id'] if m['prefix']['B'] else '',parent_query_id=m['parent_query_id']) for m in cat['old_h1_mapping']))
full=[w for w in cat['waves'] if w['full_in_period']]
stats={}
for key,values in [('impulse_days',[w['impulse_days'] for w in full]),('correction_days',[w['correction_days'] for w in full]),('A_C_days',[(w['C']['bar']-w['A']['bar'])/86400000 for w in full]),('A_D_days',[w['total_days'] for w in full]),('confirmation_lag_days',[p['lag_days'] for p in cat['pivots']])]:
    stats[key]=dict(n=len(values),min=min(values),median=statistics.median(values),max=max(values),count_100_200_inclusive=sum(100<=v<=200 for v in values))
meta=dict(duration_stats_full_in_period=stats,terminal=cat['terminal'],all_h1_complete=all(q['h1_complete'] for q in cat['macro_queries']),h72_censored_ids=[q['id'] for q in cat['macro_queries'] if not q['h72_mature_by_end']],left_truncated_macro_ids=[q['id'] for q in cat['macro_queries'] if q['left_truncated']],cross_A_full=sum(w['cross_A'] for w in full),old_mapping_before_first_macro=sum(m['parent_query_id'] is None for m in cat['old_h1_mapping']))
(ROOT/'DERIVED_METADATA.json').write_text(json.dumps(meta,indent=2)+'\n')
# Re-render sealed daily data only, with leaders and collision-avoiding label placement.
dates=cat['daily_dates'];times=[r['bar'] for r in dates];prices=[r['close'] for r in dates]
def readable(name,cut=None):
    im=Image.new('RGB',(2600,1250),'white');d=ImageDraw.Draw(im);font=ImageFont.load_default(size=18);small=ImageFont.load_default(size=14)
    left,right,top,bottom=120,2530,120,1120;lo,hi=min(prices)*.93,max(prices)*1.06
    x=lambda t:left+(t-times[0])/(times[-1]-times[0])*(right-left)
    y=lambda p:bottom-(p-lo)/(hi-lo)*(bottom-top)
    d.text((left,20),'BTC completed UTC D1 closes | circle: pivot, square: confirmation close',fill='black',font=font)
    d.text((left,50),'699 dates, fixed delta=log(1.10); overlapping triples are not independent. Exact dates/prices: pivots.csv and waves.csv.',fill='#4b5563',font=font)
    for j in range(8):
        p=lo+(hi-lo)*j/7;d.line((left,y(p),right,y(p)),fill='#e5e7eb');d.text((10,y(p)),f'{p:,.0f}',fill='black',font=font)
    if cut is not None:
        d.rectangle((max(left,x(cut)),top,right,bottom),fill='#f1f2f4');d.text((max(left,x(cut))+10,top),'FUTURE / unavailable',fill='#6b7280',font=font)
    for i in range(1,len(times)):d.line((x(times[i-1]),y(prices[i-1]),x(times[i]),y(prices[i])),fill='#aeb4bc' if cut and times[i]+86400000>cut else '#183e69',width=2)
    occupied=[]
    for i,p in enumerate(cat['pivots']):
        if p['bar']<times[0]:continue
        color=('#157a5b' if p['kind']=='LOW' else '#ad374a') if cut is None or p['confirmation']<=cut else '#b5bac2'
        xx,yy=x(p['bar']),y(p['price']);d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=color)
        roles='' # Exact A/B/C memberships are exported in waves.csv; keep overview labels causal and readable.
        text=p['id']+' '+p['kind'];w=max(d.textbbox((0,0),text,font=font)[2],d.textbbox((0,0),roles,font=small)[2])+8;h=43
        lx=min(max(left,xx+8),right-w);ly=yy-48
        for shift in [0]+[v for k in range(1,25) for v in (-k*46,k*46)]:
            cy=min(max(top+25,ly+shift),bottom-h)
            box=(lx,cy,lx+w,cy+h)
            if all(box[2]+6<b[0] or box[0]>b[2]+6 or box[3]+6<b[1] or box[1]>b[3]+6 for b in occupied):break
        occupied.append(box);d.line((xx,yy,lx,cy+h/2),fill=color,width=1);d.rectangle(box,fill='white');d.text((lx+3,cy+2),text,fill=color,font=font);d.text((lx+3,cy+24),roles,fill=color,font=small)
        xx,yy=x(p['confirmation_bar']),y(p['confirmation_price']);d.rectangle((xx-4,yy-4,xx+4,yy+4),fill=color)
    for t in times:
        dt=datetime.fromtimestamp(t/1000,timezone.utc)
        if dt.day==1 and dt.month%2==0:d.text((x(t)-35,bottom+25),dt.strftime('%Y-%m'),fill='black',font=font)
    im.save(ROOT/name)
readable('full-d1-readable.png')
for q in [cat['macro_queries'][i] for i in sorted(set([0,len(cat['macro_queries'])//2,len(cat['macro_queries'])-1]))]:readable('prefix-'+q['id']+'-readable.png',q['q'])
receipt=dict(status='COMPLETE_EXIT0',source_checkpoint='b516de74c8e83e643b3d84263bfd08274506d32f',attempt=json.loads((ROOT/'ATTEMPT.json').read_text()),elapsed_seconds=summary['elapsed_seconds'],peak_rss_bytes=summary['peak_rss_bytes'],launches=1,retries=0,targets_computed=False,visuals_derived_from_sealed_catalogue_only=True,sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.is_file() and p.name!='EXECUTION_RECEIPT.json'})
(ROOT/'EXECUTION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(meta))
