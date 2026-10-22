"""One fixed D1 close-only catalogue. Metadata only: no targets or forecasts."""
from __future__ import annotations
import argparse, copy, json, math, os, resource, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .btc_pattern_data import DAY, HOUR, MINUTE, FOLDS, ms
from .btc_pattern_inapp import digest
from .research_rss import peak_rss_bytes

START, END, WARM = map(ms, ('2024-06-01','2026-05-01','2024-05-15'))
DELTA = math.log(1.10)
MANIFEST = 'bc660056af9117a246a1334837b7e42c9bb2d0635945a0346a4b088a459685ff'

def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')

def guard(began):
    if time.monotonic()-began > 1800: raise RuntimeError('WALL_LIMIT')
    if peak_rss_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)>6*1024**3: raise RuntimeError('RSS_LIMIT')

class Detector:
    def __init__(self):
        self.mode='UNDECIDED'; self.low=None; self.high=None; self.previous=None; self.pivots=[]
    def feed(self, bar, price):
        if not math.isfinite(price) or price<=0: raise ValueError('INVALID_CLOSE')
        if self.previous is not None and bar != self.previous+DAY: raise ValueError('D1_GAP')
        self.previous=bar; point=dict(bar=int(bar),price=float(price),log=math.log(price))
        if self.low is None: self.low=point; self.high=point; return None
        if self.mode=='UNDECIDED':
            if price<self.low['price']: self.low=point
            if price>self.high['price']: self.high=point
            up=math.log(price/self.low['price'])>=DELTA
            down=math.log(self.high['price']/price)>=DELTA
            if up and down: raise ValueError('AMBIGUOUS_INITIALISATION')
            if up: return self.confirm(self.low, point, 'LOW', 'UP')
            if down: return self.confirm(self.high, point, 'HIGH', 'DOWN')
        elif self.mode=='UP':
            if price>self.high['price']: self.high=point
            if math.log(self.high['price']/price)>=DELTA: return self.confirm(self.high,point,'HIGH','DOWN')
        else:
            if price<self.low['price']: self.low=point
            if math.log(price/self.low['price'])>=DELTA: return self.confirm(self.low,point,'LOW','UP')
        return None
    def confirm(self, extreme, current, kind, mode):
        pivot=dict(extreme,id=f'P{len(self.pivots):04}',kind=kind,confirmation=current['bar']+DAY,confirmation_bar=current['bar'],confirmation_price=current['price'],lag_days=(current['bar']-extreme['bar'])/DAY+1,initialisation=len(self.pivots)==0)
        self.pivots.append(pivot); self.mode=mode; self.low=current; self.high=current
        return pivot
    def snapshot(self, asof):
        piv=self.pivots
        return dict(asof=int(asof),mode=self.mode,support_start=WARM,known_pivot_ids=[p['id'] for p in piv],A=copy.deepcopy(piv[-2]) if len(piv)>=2 else None,B=copy.deepcopy(piv[-1]) if len(piv)>=2 else None,running_extreme=copy.deepcopy(self.high if self.mode=='UP' else self.low),status='UNDECIDED' if not piv else 'NO_CONFIRMED_B' if len(piv)<2 else 'C_D_UNKNOWN',C=None,D=None)

def max_nonoverlap(waves):
    chosen=[]; end=-1
    for w in sorted(waves,key=lambda w:(w['D'],w['A']['bar'])):
        if w['A']['bar']>end: chosen.append(w['id']); end=w['D']
    return chosen

def wave(a,b,c,i):
    s=1 if b['log']>a['log'] else -1
    return dict(id=f'W{i:04}',A=a,B=b,C=c,D=c['confirmation'],orientation=s,impulse_log=b['log']-a['log'],correction_log=c['log']-b['log'],impulse_days=(b['bar']-a['bar'])/DAY,correction_days=(c['bar']-b['bar'])/DAY,total_days=(c['confirmation']-a['bar'])/DAY,cross_A=s*(c['log']-a['log'])<0,left_truncated=a['bar']<START,full_in_period=a['bar']>=START and c['confirmation']<=END)

def support_counts(waves, query, cutoff):
    # Fixed-fold metadata only. Historical outcomes are never opened or computed.
    def mature(w):
        return w['full_in_period'] and max(w['D'],w['B']['confirmation']+MINUTE+72*HOUR)<=cutoff<=query['q'] and w.get('h1_complete',False)
    causal=[w for w in waves if mature(w)]
    strict=[w for w in causal if max(w['D'],w['B']['confirmation']+MINUTE+72*HOUR)<WARM]
    boundary=min(query['A']['bar'],query['q']-169*HOUR) if query['A'] else WARM
    cycle=[w for w in causal if max(w['D'],w['B']['confirmation']+MINUTE+72*HOUR)<boundary]
    return {name:dict(raw=len(rows),nonoverlap_upper_bound=len(max_nonoverlap(rows)),orientation=dict(Counter(str(w['orientation']) for w in rows))) for name,rows in [('OLD_STRICT',strict),('CAUSAL_WALK_FORWARD',causal),('CYCLE_DISJOINT',cycle)]}

def chart(path,times,prices,pivots,cut=None):
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(2200,1000),'white');d=ImageDraw.Draw(im);font=ImageFont.load_default(size=17)
    left,right,top,bottom=110,2150,90,900;lo,hi=min(prices)*.94,max(prices)*1.05
    x=lambda t:left+(t-times[0])/(times[-1]-times[0])*(right-left)
    y=lambda p:bottom-(p-lo)/(hi-lo)*(bottom-top)
    d.text((left,20),'BTC genuine completed UTC D1 closes | delta=log(1.10) | circle=pivot, square=confirmation',fill='black',font=font)
    for p in np.linspace(lo,hi,8):
        d.line((left,y(p),right,y(p)),fill='#e5e7eb');d.text((10,y(p)),f'{p:,.0f}',fill='black',font=font)
    if cut is not None:
        d.rectangle((x(cut),top,right,bottom),fill='#f1f2f4');d.text((x(cut)+5,top),'FUTURE / unavailable at prefix',fill='#6b7280',font=font)
    for j in range(1,len(times)):
        d.line((x(times[j-1]),y(prices[j-1]),x(times[j]),y(prices[j])),fill='#aeb4bc' if cut is not None and times[j]+DAY>cut else '#183e69',width=2)
    for pi,p in enumerate(pivots):
        known=cut is None or p['confirmation']<=cut
        color=('#157a5b' if p['kind']=='LOW' else '#ad374a') if known else '#bfc3c9'
        xx,yy=x(p['bar']),y(p['price']);d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=color)
        roles=' '.join(f'{letter}{wi}' for wi in range(max(0,pi-2),min(pi+1,len(pivots)-2)) for letter in ['ABC'[pi-wi]])
        d.text((xx+5,yy-35),p['id']+(' L' if p['kind']=='LOW' else ' H'),fill=color,font=font)
        d.text((xx+5,yy-17),roles,fill=color,font=ImageFont.load_default(size=12))
        xx,yy=x(p['confirmation_bar']),y(p['confirmation_price']);d.rectangle((xx-4,yy-4,xx+4,yy+4),fill=color)
    for t in times:
        dt=datetime.fromtimestamp(t/1000,timezone.utc)
        if dt.day==1 and dt.month%2==0:d.text((x(t)-35,bottom+25),dt.strftime('%Y-%m'),fill='black',font=font)
    im.save(path)

def preflight(prepared,old,results,protocol):
    manifest=json.loads((prepared/'manifest.json').read_text())
    if digest(prepared/'manifest.json')!=MANIFEST: raise ValueError('MANIFEST_DRIFT')
    if digest(prepared/'minutes.npy')!=manifest['artifacts']['minutes.npy']['sha256']:raise ValueError('MINUTES_DRIFT')
    import PIL
    return dict(status='READY_REQUIRES_ROOT_GO',pins={str(p):digest(p) for p in [prepared/'manifest.json',prepared/'minutes.npy',old,results,protocol,Path(__file__),Path(__file__).with_name('research_rss.py'),Path(__file__).with_name('btc_pattern_inapp.py')]},period_days=699,warmup_days=17,resource=dict(processes=1,threads=4,rss_bytes=6*1024**3,wall_seconds=1800,estimated_wall_seconds=30,estimated_rss_bytes=250*1024**2),dependencies=dict(numpy=np.__version__,pillow=PIL.__version__),market_computation=False)

def run(a):
    began=time.monotonic();pf=preflight(a.prepared,a.old,a.results,a.protocol)
    go=json.loads(a.go.read_text())
    if go.get('pins')!=pf['pins'] or go.get('stage')!='STAGE_A_ONLY' or go.get('approved') is not True: raise ValueError('EXACT_GO_REQUIRED')
    a.output.mkdir(parents=True,exist_ok=True)
    with (a.output/'ATTEMPT.json').open('x') as f:json.dump(dict(pid=os.getpid(),started=datetime.now(timezone.utc).isoformat(),pins=pf['pins'],no_retry=True),f)
    manifest=json.loads((a.prepared/'manifest.json').read_text());raw=np.load(a.prepared/'minutes.npy',mmap_mode='r')
    v=raw[(WARM-manifest['minute_start'])//MINUTE:(END-manifest['minute_start'])//MINUTE]
    if v.shape!=(716*1440,5):raise ValueError('RANGE_GAP')
    for chunk in np.array_split(v,32):
        if not np.isfinite(chunk).all() or (chunk[:,:4]<=0).any() or (chunk[:,4]<0).any() or (chunk[:,2]>np.minimum(chunk[:,0],chunk[:,3])).any() or (chunk[:,1]<np.maximum(chunk[:,0],chunk[:,3])).any():raise ValueError('INVALID_MINUTE')
        guard(began)
    bars=np.arange(WARM,END,DAY,dtype=np.int64);prices=v.reshape(-1,1440,5)[:,-1,3];det=Detector();snapshots={};queries=[]
    hourly=v.reshape(-1,60,5)[:,-1,3]
    for bar,p in zip(bars,prices):
        pivot=det.feed(int(bar),float(p));snap=det.snapshot(int(bar+DAY));snapshots[int(bar+DAY)]=snap
        if pivot is not None and pivot['confirmation']>=START and pivot['confirmation']<END:
            aa=copy.deepcopy(det.pivots[-2]) if len(det.pivots)>=2 else None;q=pivot['confirmation'];j=(q-WARM)//HOUR
            queries.append(dict(id=f'M{len(queries):04}',q=q,A=aa,B=copy.deepcopy(pivot),C=None,D=None,orientation=None if aa is None else (1 if pivot['log']>aa['log'] else -1),left_truncated=aa is None or aa['bar']<START,status='MISSING_CONTEXT' if aa is None else 'C_D_UNKNOWN',h1_complete=j>=24,raw24_h1=hourly[max(0,j-24):j].tolist(),h1_close_available_at=list(range(q-23*HOUR,q+1,HOUR)) if j>=24 else [],h72_maturity_time=q+MINUTE+72*HOUR,h72_mature_by_end=q+MINUTE+72*HOUR<=END,fold=next((name for name,cut,end in FOLDS if ms(cut)<=q<ms(end)),None),support_start=WARM))
    waves=[wave(*det.pivots[i:i+3],i) for i in range(len(det.pivots)-2)]
    for w in waves:w['h1_complete']=w['B']['confirmation']-24*HOUR>=WARM
    for q in queries:
        q['support']={name:support_counts(waves,q,ms(cut)) for name,cut,end in FOLDS if name==q['fold']}
    old=json.loads(a.old.read_text())['events'];scored={r['id'] for r in json.loads(a.results.read_text())['cases']};mapping=[]
    for e in old:
        asof=e['origin']//DAY*DAY;snap=snapshots.get(asof)
        mapping.append(dict(old_id=e['id'],scored_198=e['id'] in scored,origin=e['origin'],prefix=copy.deepcopy(snap),parent_query_id=next((q['id'] for q in reversed(queries) if q['q']<=e['origin']),None)))
    for q in queries:
        q['old_h1_children']=sum(m['parent_query_id']==q['id'] for m in mapping)
        q['old_scored_children']=sum(m['parent_query_id']==q['id'] and m['scored_198'] for m in mapping)
    for w in waves:
        parent=next((q for q in queries if q['q']==w['B']['confirmation']),None)
        w['old_h1_children']=None if parent is None else parent['old_h1_children']
        w['old_scored_children']=None if parent is None else parent['old_scored_children']
    if len(mapping)!=372 or len(scored)!=198 or sum(m['scored_198'] for m in mapping)!=198:raise ValueError('OLD_ID_DRIFT')
    dates=[dict(date=datetime.fromtimestamp(int(t)/1000,timezone.utc).strftime('%Y-%m-%d'),bar=int(t),available_at=int(t+DAY),close=float(p),prefix=snapshots[int(t+DAY)]) for t,p in zip(bars,prices) if t>=START]
    catalogue=dict(pivots=det.pivots,waves=waves,macro_queries=queries,daily_dates=dates,old_h1_mapping=mapping,terminal=det.snapshot(END),initialisation=dict(seed_bar=WARM,seed_price=float(prices[0]),status='INITIALISATION_NOT_COMPLETED_LEG'),forecast_contract_approved=False,targets_computed=False)
    write(a.output/'catalogue.json',catalogue);chart(a.output/'full-d1.png',bars,prices,det.pivots)
    selected=sorted(set([0,len(queries)//2,len(queries)-1])) if queries else []
    for i in selected:
        q=queries[i];chart(a.output/f"prefix-{q['id']}.png",bars,prices,det.pivots,q['q']);write(a.output/f"prefix-{q['id']}.json",snapshots[q['q']])
    full=[w for w in waves if w['full_in_period']];bound=max_nonoverlap(full)
    folds={}
    for name,cut,end in FOLDS:
        qq=[q for q in queries if q['fold']==name];ww=[w for w in full if ms(cut)<=w['B']['confirmation']<ms(end)]
        folds[name]=dict(queries=len(qq),full_cycles=len(ww),evaluation_nonoverlap_upper_bound=len(max_nonoverlap(ww)),orientation=dict(Counter(str(w['orientation']) for w in ww)),support=[dict(id=q['id'],**q['support'][name]) for q in qq])
    support_ok=all(q['support'][q['fold']]['CAUSAL_WALK_FORWARD']['nonoverlap_upper_bound']>=6 and all(q['support'][q['fold']]['CAUSAL_WALK_FORWARD']['orientation'].get(str(s),0)>=2 for s in (-1,1)) and q['h1_complete'] and q['h72_mature_by_end'] and not q['left_truncated'] for q in queries if q['fold'])
    evaluation=[w for w in full if any(ms(cut)<=w['B']['confirmation']<ms(end) for _,cut,end in FOLDS)]
    evaluation_bound=max_nonoverlap(evaluation)
    passed=support_ok and len(evaluation_bound)>=6 and all(sum(w['orientation']==s for w in evaluation)>=2 for s in (-1,1)) and all(f['queries']>0 for f in folds.values())
    summary=dict(status='CATALOGUE_ONLY / FORECAST_BLOCKED_INSUFFICIENT_CYCLES_OR_MATURITY' if not passed else 'CATALOGUE_ONLY / ENGINEERING_MINIMA_MET_REQUIRES_SEPARATE_STAGE_B_APPROVAL',dates=len(dates),pivots=len(det.pivots),waves=len(waves),full_in_period=len(full),left_truncated=sum(w['left_truncated'] for w in waves),cross_A=sum(w['cross_A'] for w in waves),macro_queries=len(queries),old_h1_ids=len(mapping),old_scored_ids=len(scored),orientation=dict(Counter(str(w['orientation']) for w in full)),calendar=dict(Counter(datetime.fromtimestamp(w['B']['confirmation']/1000,timezone.utc).strftime('%Y-%m') for w in full)),evaluation_support=dict(cycles=len(evaluation),nonoverlap_upper_bound=len(evaluation_bound),orientation=dict(Counter(str(w['orientation']) for w in evaluation))),nonoverlap=dict(upper_bound=len(bound),ids=bound,interpretation='support upper bound; not IID, not a scoring subset'),folds=folds,pins=pf['pins'],catalogue_sha256=digest(a.output/'catalogue.json'),targets_computed=False,forecast_contract_approved=False,elapsed_seconds=time.monotonic()-began,peak_rss_bytes=peak_rss_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    guard(began);write(a.output/'SUMMARY.json',summary)
    lines=['# Stage A fixed D1 catalogue','',summary['status'],'',f"699 daily dates; {len(det.pivots)} pivots; {len(waves)} triples; {len(full)} full in-period waves; {len(bound)} maximum nonoverlapping [A,D] intervals (support upper bound, not IID).",'', 'All 372 old H1 IDs / 198 scored IDs mapped to then-known state. Raw 24 H1 closes retained at each macro origin. No targets, neighbours, representations, forecasts or quality scores computed.','', 'OLD_STRICT inherits the May15 seed and has empty support. CAUSAL_WALK_FORWARD uses fixed fold fit cutoffs; historical D and q+60s+72h must mature by cutoff. CYCLE_DISJOINT is separately descriptive. Shared historical prices do not imply independent observations or approval of a forecast contract.','', 'Durations/amplitudes/confirmation lags and all cross-A, left-truncated and terminal right-censored states are in catalogue.json. The fixed detector is not forced to produce 100–200 day objects. No automatic threshold, date or ontology revision is permitted.','', 'Charts: full-d1.png; three deterministic earliest/middle/latest macro-prefix views show known pivots in colour and unavailable future in grey. Terminal state remains provisional; C/D are never imputed.','', 'Stage B remains unapproved. Engineering minima are not statistical power or economic evidence.']
    (a.output/'REPORT.md').write_text('\n'.join(lines)+'\n');return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['preflight','catalogue']);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--old',type=Path,required=True);p.add_argument('--results',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--go',type=Path);a=p.parse_args()
    if a.stage=='preflight':write(a.output,preflight(a.prepared,a.old,a.results,a.protocol))
    else:print(json.dumps(run(a)))
if __name__=='__main__':main()
