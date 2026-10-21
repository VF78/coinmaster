#!/usr/bin/env python3
"""Plot persisted first-actionable examples only; never import model/data code.
Requires explicit --root-go after CHECK exports are complete. Outputs two asset
figures as PNG/PDF/SVG, an HTML link index and a provenance receipt.
"""
import argparse, hashlib, json, math, os
from datetime import datetime, timezone
from pathlib import Path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root-go', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('exports', type=Path, nargs='+')
    a = p.parse_args()
    if not a.root_go:
        p.error('--root-go required; no outcome exports opened')
    if a.output.exists():
        raise ValueError('OUTPUT_DIRECTORY_EXISTS')
    os.environ.setdefault('MPLCONFIGDIR', str(a.output.parent/'report-mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    evidence, records, identities = {}, [], set()
    def load(path):
        evidence[str(path.resolve())] = sha(path)
        return json.loads(path.read_text())
    for directory in a.exports:
        r = load(directory/'result.json')
        if r.get('status') not in ('ONE_FROZEN_CHECK_EVALUATION_COMPLETE','INCOMPLETE_RESOURCE'):
            raise ValueError('COMPLETED_EXPORTS_REQUIRED')
        identities.add((r.get('protocol_sha256'),r.get('dataset_manifest_sha256')))
        records.append((directory,r))
    if len(identities)!=1 or any(v is None for pair in identities for v in pair):
        raise ValueError('MIXED_OR_MISSING_IDENTITIES')
    if len({r['family'] for _,r in records})!=len(records):
        raise ValueError('DUPLICATE_METHOD')
    order = {'control':0,'stumpy':1,'minirocket':2,'rdst':3,'cnn':4}
    records.sort(key=lambda v:order[v[1]['family']])
    a.output.mkdir(parents=True)
    missing, links = [], []
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    for asset in ('BTCUSDT','SOLUSDT'):
        fig, axes = plt.subplots(len(records),2,figsize=(16,3.4*len(records)),squeeze=False,width_ratios=[1,3.5],layout='constrained')
        for i,(directory,r) in enumerate(records):
            left,right = axes[i]; left.set_axis_off()
            e = next((v for v in r.get('deterministic_examples',[]) if v['asset']==asset),None)
            label = r['family']
            if e is None:
                right.set_axis_off(); right.text(.05,.5,f'{label}: '+('INCOMPLETE_RESOURCE; no predictive conclusion' if r['status']=='INCOMPLETE_RESOURCE' else 'No actionable origin; no substitute example'),transform=right.transAxes)
                continue
            image = directory/f'example-{asset}.png'
            if image.exists():
                evidence[str(image.resolve())]=sha(image); left.imshow(plt.imread(image),cmap='gray',interpolation='nearest',aspect='auto'); left.set_title(f'{label}: past input (normalized)')
            else:
                missing.append(str(image)); left.text(.1,.5,'Past chart export missing')
            path = directory/f'example-path-{asset}.json'
            if not path.exists():
                missing.append(str(path)); right.text(.05,.5,'Actual minute-path companion missing',transform=right.transAxes); continue
            obj = load(path); rows=np.asarray(obj['minutes'],dtype=float)
            if obj.get('row')!=e['row'] or rows.shape!=(1440,5) or len(obj.get('source_sha256',''))!=64:
                raise ValueError('PATH_IDENTITY_OR_SHAPE')
            if not np.isfinite(rows).all() or not (rows[:,1:]>0).all() or not np.array_equal(rows[:,0],e['entry_ms']+np.arange(1440)*60000):
                raise ValueError('PATH_MINUTE_CONTRACT')
            if not ((rows[:,3]<=np.minimum(rows[:,1],rows[:,4]))&(rows[:,2]>=np.maximum(rows[:,1],rows[:,4]))).all():
                raise ValueError('PATH_OHLC_CONTRACT')
            hours=np.arange(1440)/60
            right.vlines(hours,rows[:,3],rows[:,2],color='#abc0d2',lw=.45,label='Observed minute range')
            right.plot(hours+1/60,rows[:,4],color='#264d70',lw=.8,label='Observed close')
            ambiguous=obj.get('ambiguous_minute_ms')
            if not isinstance(ambiguous,list) or any(t<e['entry_ms'] or t>=e['expiry_ms'] for t in ambiguous):
                raise ValueError('AMBIGUITY_EXPORT_REQUIRED')
            for j,t in enumerate(ambiguous):
                h=(t-e['entry_ms'])/3600000; right.axvspan(h,h+1/60,color='#bd5c92',alpha=.65,label='Unresolved TP/SL order' if j==0 else None)
            levels=[('Entry',e['entry'],'#222'),('Reference',e['reference'],'#777'),('SL',e['entry_SL'],'#bb3c3a')]+[(f'TP{j+1}',v,'#35754b') for j,v in enumerate(e['entry_TP'])]
            for name,price,color in levels:
                right.axhline(price,color=color,ls='--',lw=.8,label=f'{name} {price:.8g}')
            date=datetime.fromtimestamp(e['origin_ms']/1000,timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            right.set(title=f'{label} | {date} | '+('LONG' if e['side']==1 else 'SHORT')+' | first actionable origin',xlabel='Hours from next-minute entry',ylabel='Price (USDT)',xlim=(0,24))
            right.grid(alpha=.15); right.legend(loc='upper left',bbox_to_anchor=(1.01,1),fontsize=8,frameon=False)
        fig.suptitle(f'{asset}: frozen 24h forecasts and subsequently observed paths',fontsize=15)
        fig.supxlabel('Past images contain only signal-time inputs. Full 24h paths include post-stop context; later prices do not establish qualifying TP hits. Pink marks exported order ambiguity.\nTP1/2/3 are MFE q .2/.5/.8: nominal 80/50/20 exceedance requires continuous calibrated targets; ties/zeros and execution invalidate a direct hit-probability interpretation.',fontsize=9)
        for ext in ('png','pdf','svg'):
            target=a.output/f'first-actionable-{asset}.{ext}'; fig.savefig(target,dpi=160,bbox_inches='tight'); links.append(target.name)
        plt.close(fig)
    index='<meta charset="utf-8"><title>Forecast figures</title><h1>Actual first-actionable examples</h1>'+''.join(f'<p><a href="{name}">{name}</a></p>' for name in links)
    (a.output/'figures.html').write_text(index)
    (a.output/'receipt.json').write_text(json.dumps({'matplotlib':matplotlib.__version__,'input_sha256':evidence,'output_sha256':{n:sha(a.output/n) for n in links},'missing_exports':missing,'no_model_label_or_PnL_recomputation':True},indent=2))

if __name__=='__main__':
    main()
