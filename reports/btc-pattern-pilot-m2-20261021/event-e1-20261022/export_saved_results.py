"""Reproduce report/CSV exports from the frozen RESULTS.json only."""
import csv, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
r=json.loads((ROOT/'RESULTS.json').read_text());cases=r['cases'];n=len(cases)
arms=('prior','state','clock','phase');sides=('long','short');stops=(.75,1.,1.5)

def csvwrite(name,rows):
    with (ROOT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

rows=[]
for c in cases:
    for a in arms:
        f=c['forecasts'][a];z=dict(id=c['id'],origin=c['origin'],fold=c['fold'],input_start=c['input_start'],label_end=c['label_end'],arm=a,supported=f['supported'],fallback=f['fallback'],display=f['display']['status'],truth_D=c['truth']['D'],TP_loss=f['loss']['TP'],SL_loss=f['loss']['SL'])
        for d in range(3):z[f'D_prob_{d}']=f['D'][d]
        for s,side in enumerate(sides):
            for j,sl in enumerate(stops):
                key=f'{side}_sl{sl:g}'
                for k,q in enumerate((20,50,80)):z[f'{key}_q{q}']=f['Q'][s][j][k]
                z[f'{key}_touch_predicted']=f['touch'][s][j];z[f'{key}_touch_truth']=c['truth']['touch'][s][j]
                z[f'{key}_MFE_lower']=c['truth']['Q'][s][j][0];z[f'{key}_MFE_upper']=c['truth']['Q'][s][j][1]
        rows.append(z)
csvwrite('case_arm_forecasts.csv',rows)
accuracy=[]
for a in arms:
    for s,side in enumerate(sides):
        for j,sl in enumerate(stops):
            for k,quantile in enumerate((20,50,80)):
                vals=[(c['forecasts'][a]['Q'][s][j][k],c['truth']['Q'][s][j]) for c in cases]
                positive=[(p,b) for p,b in vals if p>0]
                lo=sum(b[0]>=p for p,b in positive);hi=sum(b[1]>=p for p,b in positive);den=len(positive)
                accuracy.append(dict(arm=a,side=side,SL=sl,TP=k+1,quantile=quantile,common_IDs=n,positive_denominator=den,zero_level_count=n-den,attained_lower=lo,attained_upper=hi,reach_lower=lo/den if den else '',reach_upper=hi/den if den else '',SL_touch_predicted=sum(c['forecasts'][a]['touch'][s][j] for c in cases)/n,SL_touch_observed=sum(c['truth']['touch'][s][j] for c in cases)/n))
csvwrite('accuracy.csv',accuracy)
comparisons=[]
for comparator,tasks in r['comparisons'].items():
    for metric,intervals in tasks.items():
        for interval,ci in intervals.items():
            comparisons.append(dict(comparator=comparator,metric=metric,interval=interval,days=ci['days'],phase_minus_control=ci['mean'],lower=ci['lower'],upper=ci['upper'],F1=ci['fold_means']['F1'],F2=ci['fold_means']['F2'],F3=ci['fold_means']['F3'],pass_rule=ci['pass_rule']))
csvwrite('comparisons.csv',comparisons)
prior=r['metrics']['prior']['all_ID'];phase=r['metrics']['phase']['all_ID'];relative={k:(phase[k]/prior[k]-1)*100 for k in ('TP','SL')}
lines=['# E1: no demonstrated incremental forecast value','',
'**E1_NO_DEFINED_IMPROVEMENT.** Phase-aligned analogues fail the frozen gate: neither co-primary metric improves reliably against each of prior, state and matched-clock controls. All six primary 14-day paired confidence intervals include zero. E2/E3: **SKIPPED_GATE_FAILED**.','',
'The full 699-day catalogue covers 2024-06-01 through 2026-05-01 (exclusive), with 372 confirmed event queries. The original three evaluation folds contribute **198 common mature IDs**: F1=64, F2=67, F3=67. The catalogue retains horizon-censored and unfinished events. Every arm scores those same 198 IDs, including fallback and NO_TRADE; supported coverage is 100% for all arms and fallback count is zero.','',
'| Arm | TP pinball ↓ | Full72h SL-touch Brier ↓ | NO_TRADE |','|---|---:|---:|---:|']
for a in arms:
    m=r['metrics'][a];lines.append(f"| {a} | {m['all_ID']['TP']:.9f} | {m['all_ID']['SL']:.9f} | {m['NO_TRADE']} |")
lines+=['',f"Relative to the empirical event prior, phase TP pinball is **{relative['TP']:+.2f}% worse** and SL-touch Brier is **{relative['SL']:+.2f}% worse**. These are relative changes in forecast errors, not percentage-point changes in reach rates.",'',
'## Fixed SL=1σ72 accuracy on all 198 IDs','',
'TP1/TP2/TP3 are predicted q20/q50/q80 levels of MFE before SL. Percentages below are positive-level reaches before SL; each cell shows conservative lower–upper intraminute bounds and its denominator. Levels differ by forecast arm, so reach rates alone do not measure forecast superiority. Proper losses above compare forecast accuracy on the same target population. All SL=1 TP levels are positive: zero-level count=0 in every cell.','',
'| Arm | Side | TP1 lower–upper (N) | TP2 lower–upper (N) | TP3 lower–upper (N) | SL-touch predicted | SL-touch observed |','|---|---|---:|---:|---:|---:|---:|']
for a in arms:
    for side in sides:
        rr=[v for v in accuracy if v['arm']==a and v['side']==side and v['SL']==1.]
        cells=[f"{v['reach_lower']:.2%}–{v['reach_upper']:.2%} ({v['positive_denominator']})" for v in rr]
        lines.append('| '+a+' | '+side+' | '+' | '.join(cells)+f" | {rr[0]['SL_touch_predicted']:.2%} | {rr[0]['SL_touch_observed']:.2%} |")
lines+=['',
'SL-touch means the adverse barrier was touched anywhere in the full 72 hours, irrespective of TP exits. It is not an actual traded stopout. TP reach bounds are separate marginal path targets, not the success rate of a joint partial-exit trade. Full .75/1/1.5 SL results, positive denominators, zero-level mass, calibration bins and row losses remain in RESULTS.json and accuracy.csv.','',
'## Frozen paired comparisons','',
'Negative deltas favor phase. The gate requires both co-primary metrics against every control: upper95% CI<0, improvements in at least two of three folds, at least two occupied blocks per fold, plus ≥90% supported coverage for every learned arm.','',
'| Comparator | Metric | Phase−control | 14d 95% CI | 28d 95% CI | Primary pass |','|---|---|---:|---|---|---|']
for control in ('prior','state','clock'):
    for metric in ('TP','SL'):
        q=r['comparisons'][control][metric];a=q['primary_14d'];b=q['sensitivity_28d']
        lines.append(f"| {control} | {metric} | {a['mean']:+.9f} | [{a['lower']:+.9f}, {a['upper']:+.9f}] | [{b['lower']:+.9f}, {b['upper']:+.9f}] | {a['pass_rule']} |")
lines+=['',
'Intervals use within-fold occupied UTC blocks, 1,000 draws and seed7. All three folds have 9/10/9 occupied 14-day blocks respectively. This remains exploratory evidence on previously studied DEVELOPMENT. Event-selected query IDs compare conditional information; they do not identify an advantage of event timing or sampling over a common calendar population.','',
'No economic return, ROI, drawdown, cost-adjusted trading benefit or native execution performance was evaluated. No neural/API/LLM forecasts, new training, parameter search, CHECK/VPS/pilot changes, or market rerun were performed. E2 and E3 were skipped because the preregistered improvement gate failed.','',
'## Reproducibility','',
'`export_saved_results.py` reads only the immutable saved RESULTS.json and regenerates this report, case_arm_forecasts.csv (792 case×arm rows with all18Q/6SL and truth/IDs), accuracy.csv (all side/SL/TP reach bounds), and comparisons.csv. It does not load prices, targets, models or the evaluator. Protocol, catalogue, source/test pins and single-run completion evidence are saved alongside these files.']
(ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
receipt=json.loads((ROOT/'COMPLETION_RECEIPT.json').read_text());receipt['report_export']='SAVED_RESULTS_ONLY';receipt['E2_E3']='SKIPPED_GATE_FAILED'
receipt['artifacts']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.is_file() and p.name!='COMPLETION_RECEIPT.json'}
(ROOT/'COMPLETION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(source_results_sha256=hashlib.sha256((ROOT/'RESULTS.json').read_bytes()).hexdigest(),case_arm_rows=len(rows),accuracy_rows=len(accuracy),comparison_rows=len(comparisons),phase_relative_error_percent=relative)))
