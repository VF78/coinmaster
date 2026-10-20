#!/usr/bin/env python3
"""Reduce verified risk exports to chart input; no raw trace/engine reads."""
import csv,json,pathlib
R=pathlib.Path(__file__).resolve().parent
s=json.loads((R/'risk-statistics.json').read_text()); daily=list(csv.DictReader((R/'risk-daily-curve.csv').open()));monthly=list(csv.DictReader((R/'risk-monthly.csv').open()))
seed=float(monthly[0]['start_equity']);peak=seed;rows=[]
for r in daily:
 e=float(r['end_equity']);peak=max(peak,e);rows.append({'date':r['period'],'equity_usdt':e,'close_drawdown_pct':(1-e/peak)*100})
last=s['settlement_bridge'];top=s['top10_percent'][0]
out={'period_label':f'{daily[0]["period"]} to {daily[-1]["period"]} (source-bar dates)', 'daily':rows,'monthly':[{'month':r['period'],'return_pct':float(r['return_percent']),'terminal_settlement':i==len(monthly)-1} for i,r in enumerate(monthly)],'initial_equity_usdt':seed,'final_equity_usdt':rows[-1]['equity_usdt'],'native_max_drawdown_pct':float(s['all_native_max_DD_percent']),'native_max_drawdown_time':top['trough']['utc'][:16].replace('T',' ')+' UTC','equity_note':'Daily-close line is a lower bound; dot marks exact native intraday trough. Settlement final: 6,077,107.24 USDT.','funding_note':'Signed funding is UNKNOWN. Existing diagnostic run is not certified venue-faithful or eligible for ranking.','monthly_note':'* Final month uses pre-settlement marked equity; terminal settlement is excluded from calendar returns.','source_checks':s['checks'],'settlement_bridge':last}
(R/'charts-input.json').write_text(json.dumps(out,indent=2)+'\n')
