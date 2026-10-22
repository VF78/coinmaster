"""Saved-output arithmetic only. No research imports, forecasts, fitting or data access.

Run with Python 3 from any directory. Reads only sibling D90 saved result,
protocol and preflight; writes only stats-* files beside this script.
"""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

OUT = Path(__file__).resolve().parent
SRC = OUT.parent / 'event-d90-20261022'
saved = {name: json.loads((SRC / name).read_text()) for name in
         ('RESULTS.json', 'PROTOCOL.json', 'PREFLIGHT.json')}
r = saved['RESULTS.json']
cases = r['cases']
assert len(cases) == 198
assert [c['id'] for c in cases] == saved['PREFLIGHT.json']['query_ids']
arms = ('prior', 'phase', 'daily90')
qs = (.2, .5, .8)
sls = (.75, 1, 1.5)

def pinball(y, p, q):
    return max(q * (y-p), (q-1) * (y-p))

def bucket(n):
    return '2' if n == 2 else '3-15' if n < 16 else '16-31' if n < 32 else '32-63' if n < 64 else '64+'

def write_csv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

tp, sl, query = [], [], []
for c in cases:
    d = c['forecasts']['daily90']
    p = c['forecasts']['prior']
    n, w = d['cell_count'], d['conditional_weight']
    assert abs(w - n/(n+32)) < 1e-15
    base = dict(id=c['id'], fold=c['fold'], state=c['daily90']['state'],
                month=datetime.fromtimestamp(c['origin']/1000, timezone.utc).strftime('%Y-%m'),
                cell_count=n, global_count=d['global_count'], conditional_weight=w,
                support_bucket=bucket(n))
    query.append(dict(**base, TP_delta=d['loss']['TP']-p['loss']['TP'],
                      SL_delta=d['loss']['SL']-p['loss']['SL']))
    for s, side in enumerate(('long', 'short')):
        for j, barrier in enumerate(sls):
            y = c['truth']['touch'][s][j]
            pp, pd = p['touch'][s][j], d['touch'][s][j]
            a = pd-pp
            row = dict(**base, side=side, SL=barrier, actual=y,
                       prior_p=pp, daily90_p=pd, adjustment=a,
                       adjustment_square=a*a, alignment=2*a*(pp-y),
                       prior_brier=(pp-y)**2, daily90_brier=(pd-y)**2,
                       delta=(pd-y)**2-(pp-y)**2)
            assert abs(row['delta']-row['adjustment_square']-row['alignment']) < 1e-15
            sl.append(row)
            yq = c['truth']['Q'][s][j][0]
            for k, q in enumerate(qs):
                losses = {arm: pinball(yq, c['forecasts'][arm]['Q'][s][j][k], q) for arm in arms}
                tp.append(dict(**base, side=side, SL=barrier, quantile=q, actual=yq,
                               prior_q=p['Q'][s][j][k], daily90_q=d['Q'][s][j][k],
                               prior_loss=losses['prior'], phase_loss=losses['phase'],
                               daily90_loss=losses['daily90'], delta=losses['daily90']-losses['prior']))

for arm in arms:
    assert abs(mean(x[arm+'_loss'] for x in tp)-r['metrics'][arm]['all_ID']['TP']) < 1e-13
assert abs(mean(x['delta'] for x in sl)-r['comparisons']['prior']['SL']['primary_14d']['mean']) < 1e-13

groups = [(), ('fold',), ('state',), ('side',), ('SL',), ('quantile',),
          ('fold','state'), ('fold','side'), ('fold','quantile'),
          ('side','SL','quantile'), ('fold','side','SL','quantile'),
          ('support_bucket',), ('month',)]
summary = []
for task, rows, divisor in [('TP', tp, 198*18), ('SL', sl, 198*6)]:
    for keys in groups:
        if task == 'SL' and 'quantile' in keys:
            keys = tuple(k for k in keys if k != 'quantile')
        # Duplicate SL group sets are suppressed below.
        bins = defaultdict(list)
        for x in rows:
            bins[tuple(x[k] for k in keys)].append(x)
        for values, xs in bins.items():
            item = dict(task=task, grouping='+'.join(keys) or 'all',
                        group='|'.join(map(str, values)) or 'all',
                        coordinate_observations=len(xs), query_count=len({x['id'] for x in xs}),
                        mean_delta=mean(x['delta'] for x in xs),
                        contribution_to_total=sum(x['delta'] for x in xs)/divisor,
                        mean_conditional_weight=mean(x['conditional_weight'] for x in xs),
                        min_cell_count=min(x['cell_count'] for x in xs),
                        max_cell_count=max(x['cell_count'] for x in xs))
            if task == 'SL':
                item.update(adjustment_square=mean(x['adjustment_square'] for x in xs),
                            alignment=mean(x['alignment'] for x in xs),
                            observed=mean(x['actual'] for x in xs),
                            prior_probability=mean(x['prior_p'] for x in xs),
                            daily90_probability=mean(x['daily90_p'] for x in xs))
            summary.append(item)
summary = list({(x['task'],x['grouping'],x['group']): x for x in summary}.values())

# Coordinate-wise variance decomposition avoids mixing distinct target base rates.
calibration = []
for keys in [('side','SL'), ('state','side','SL'), ('fold','side','SL'), ('fold','state','side','SL')]:
    bins = defaultdict(list)
    for x in sl:
        bins[tuple(x[k] for k in keys)].append(x)
    for values, xs in bins.items():
        ybar = mean(x['actual'] for x in xs)
        for arm, field in [('prior','prior_p'), ('daily90','daily90_p')]:
            pbar = mean(x[field] for x in xs)
            varp = mean((x[field]-pbar)**2 for x in xs)
            cov = mean((x[field]-pbar)*(x['actual']-ybar) for x in xs)
            brier = mean((x[field]-x['actual'])**2 for x in xs)
            reconstructed = ybar*(1-ybar) + (pbar-ybar)**2 + varp - 2*cov
            assert abs(brier-reconstructed) < 1e-14
            calibration.append(dict(grouping='+'.join(keys), group='|'.join(map(str,values)),
                                    arm=arm, count=len(xs), observed=ybar, probability=pbar,
                                    bias=pbar-ybar, bias_square=(pbar-ybar)**2,
                                    probability_variance=varp, covariance_with_outcome=cov,
                                    useful_alignment_credit=2*cov, brier=brier))

concentration = {}
for task in ('TP','SL'):
    v = [x[task+'_delta'] for x in query]
    gross_harm = sum(max(x,0) for x in v)
    harmful = sorted([x for x in query if x[task+'_delta']>0], key=lambda x:x[task+'_delta'], reverse=True)
    concentration[task] = dict(net_sum=sum(v), gross_harm=gross_harm,
                              gross_help=-sum(min(x,0) for x in v),
                              harmed_queries=len(harmful), helped_queries=sum(x<0 for x in v),
                              top10_harm_share=sum(x[task+'_delta'] for x in harmful[:10])/gross_harm,
                              top10_harmed_ids=[x['id'] for x in harmful[:10]])

write_csv('stats-query-deltas.csv', query)
write_csv('stats-tp-coordinates.csv', tp)
write_csv('stats-sl-decomposition.csv', sl)
write_csv('stats-calibration.csv', calibration)
fields = list(dict.fromkeys(k for x in summary for k in x))
write_csv('stats-group-summary.csv', [{k:x.get(k,'') for k in fields} for x in summary])
result = dict(schema='d90-saved-output-postmortem.v1',
              scope='198 saved IDs only; no forecasts/fits/targets/market or catalogue access',
              inputs={name:hashlib.sha256((SRC/name).read_bytes()).hexdigest() for name in saved},
              checks=dict(ids_match_preflight=True, TP_saved_metrics_reproduced=True,
                          SL_saved_delta_reproduced=True, Brier_identity_verified=True),
              source_gate=r['gate'], source_metrics={arm:r['metrics'][arm]['all_ID'] for arm in arms},
              brier_identity='delta=(daily90_p-prior_p)^2+2*(daily90_p-prior_p)*(prior_p-y)',
              variance_identity='Brier=ybar*(1-ybar)+(pbar-ybar)^2+Var(p)-2*Cov(p,y)',
              concentration=concentration, groups=summary,
              limitations=['All subgroup comparisons descriptive, posthoc and correlated.',
                           'No recalibration, new blend, forecast or inferential resampling.',
                           'State/calendar association does not prove a causal state effect.',
                           'Long horizon event counts are not independent cycle counts.'])
(OUT/'stats-results.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(dict(concentration=concentration, groups=[x for x in summary if x['grouping'] in ('all','fold','state','side','quantile','support_bucket')]), indent=2))
