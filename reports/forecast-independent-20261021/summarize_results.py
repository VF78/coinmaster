"""Summarize saved CHECK result JSON only; no models, labels, or new inference."""
import argparse,csv,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=True,parents=True)
 families=['control','stumpy','minirocket','rdst','cnn'];metrics=['lower_pinball','upper_pinball','direction_logloss','direction_brier','direction_accuracy'];results={f:json.loads((a.results/f/'result.json').read_text()) for f in families}
 with (a.output/'metrics-by-asset-month.csv').open('w',newline='') as file:
  w=csv.writer(file);w.writerow(['family','stage','asset','month','n',*metrics])
  for f,r in results.items():
   for stage in ['raw','calibrated','prefix_prior']:
    v=r[stage]['all'];w.writerow([f,stage,'ALL','ALL',v['n'],*[v[k] for k in metrics]])
    for key,v in r[stage]['groups'].items():
     asset,month=key.split(':');w.writerow([f,stage,['BTCUSDT','SOLUSDT'][int(asset)],month,v['n'],*[v[k] for k in metrics]])
 lines=['# Frozen independent forecasting CHECK results','', 'One CHECK evaluation per frozen method on BTCUSDT/SOLUSDT Bybit linear execution OHLCV, 2026-04-01 through 2026-10-20 UTC. Each method has 9,696 mature forecasts and 48 explicitly censored forecasts. Hourly origins, next-minute entry, 24-hour horizon; no PnL engine.','', 'All calibrated methods underperformed the TRAIN-prefix prior on aggregate forecast loss and direction log loss. CNN had the lowest calibrated pinball among fitted models, but its paired 14-day confidence interval versus the calibrated raw-feature control crosses zero and its actionable coverage is zero. These results do not establish a useful trading edge.','', '| Method | Raw lower pinball | Cal lower pinball | Raw / cal direction log loss | Direction accuracy | Actionable / 9696 |','|---|---:|---:|---:|---:|---:|']
 for f,r in results.items():
  raw=r['raw']['all'];cal=r['calibrated']['all'];lines.append(f"| {f} | {raw['lower_pinball']:.6f} | {cal['lower_pinball']:.6f} | {raw['direction_logloss']:.6f} / {cal['direction_logloss']:.6f} | {cal['direction_accuracy']:.2%} | {r['coverage']['actionable']} |")
 prior=results['control']['prefix_prior']['all'];lines += [f"| TRAIN-prefix prior | {prior['lower_pinball']:.6f} | — | {prior['direction_logloss']:.6f} | {prior['direction_accuracy']:.2%} | — |",'', 'Lower losses are better. March calibration improved some direction losses but increased every method’s aggregate lower pinball relative to its raw prediction. The frozen raw JSON field `vs_raw_control` actually compares calibrated predictions against calibrated raw-feature control; it is named `vs_calibrated_control` in the export summary.','', '| Method minus calibrated control | Lower pinball difference | Paired 14-day 95% CI |','|---|---:|---|']
 for f in families[1:]:
  v=results[f]['vs_raw_control'];ci=v['paired14day_CI95'];lines.append(f"| {f} | {v['mean_lower_pinball_difference']:+.6f} | [{ci[0]:+.6f}, {ci[1]:+.6f}] |")
 lines += ['', 'Negative differences favor the method. STUMPY and CNN intervals include zero; MiniRocket and RDST are worse than control on this comparison. Overlapping 24-hour forecasts are summarized using 15 paired 14-day blocks with 1,000 fixed-seed bootstrap draws; this is a finite CHECK sample.','', '| Method | Asset | Actionable N | TP1 lower–upper hit | TP2 lower–upper hit | TP3 lower–upper hit |','|---|---|---:|---:|---:|---:|']
 for f,r in results.items():
  for asset,v in r['actionable_touch_summary'].items():
   vals=['—' if t['lower_hit_frequency'] is None else f"{t['lower_hit_frequency']:.1%}–{t['upper_hit_frequency']:.1%}" for t in v['targets']];lines.append('| '+' | '.join([f,asset,str(v['n']),*vals])+' |')
 lines += ['', 'TP levels are learned MFE quantiles (.2/.5/.8) anchored to actual entry; hit bounds account for stop/target ordering within minute bars. Small actionable samples are descriptive. Continuous calibrated targets would imply nominal exceedance 80/50/20%; actual zero masses/ties and execution paths prevent interpreting these as guaranteed hit probabilities. Each method’s quantile-tie-coverage.json retains strict and nonstrict exceedance and exact zero/tie counts.','', 'All-origin asset/month metrics are in metrics-by-asset-month.csv; original full results, every forecast row, observed target bounds, probabilities, censor flags, receipts, hashes and deterministic examples are retained. A missing first-actionable example means no qualifying forecast for that asset/method, rather than a missing successful example. No model, calibration or selection was changed after CHECK.']
 (a.output/'findings.md').write_text('\n'.join(lines)+'\n');print('SAVED_JSON_SUMMARY_PASS')
if __name__=='__main__':main()
