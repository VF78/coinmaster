"""One bounded saved-artifact accounting pass. No imports of strategy/native engine."""
import csv, json, hashlib, datetime as dt, statistics, collections, ast
from decimal import Decimal as D, getcontext
from pathlib import Path
getcontext().prec = 40
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SRC = ROOT / 'reports/sol-conditional-hedge-btc-band-20261023'
B = 'BTC_REGIME_REENTRY_BAND_05'
inputs = {}
def read(path):
    p = SRC / path
    inputs[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return list(csv.DictReader(p.open()))
def write(name, rows):
    if not rows: return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / ('roi-' + name + '.csv')).open('w') as f:
        w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
def utc(ns): return dt.datetime.fromtimestamp(int(ns)/1e9,dt.timezone.utc).isoformat()
def ns(utc): return int(dt.datetime.fromisoformat(utc).timestamp()*1e9)
def dec(v): return D(str(v))
def pct(x,y): return (dec(x)/dec(y)-1)*100
comp = {r['recipe']:r for r in read('comparison.csv')}
s,b = comp['S0_ARCHIVE'],comp[B]
monthly = read('owner-monthly.csv'); windows=read('owner-windows.csv'); risk=read('owner-global-risk.csv');terminal=read('owner-terminal-settlement.csv')
episodes=read('owner-episode-comparison.csv'); sizing=read('owner-sizing-calendar.csv');waits=read('owner-B-skip-delay.csv')
signals=read('owner-BTC_REGIME_REENTRY_BAND_05-events/hedge-band-audit.csv')
fills=read('owner-BTC_REGIME_REENTRY_BAND_05-events/native-fill-audit.csv')
s0_fill_reports=read('verifier-reference-fills.csv')
b_fill_reports=read('owner-BTC_REGIME_REENTRY_BAND_05-events/native-fills.csv')
def commission_sum(row):
    amounts=[]
    for item in ast.literal_eval(row['commissions']):
        value,currency=item.rsplit(' ',1)
        assert currency=='USDT'
        amounts.append(dec(value))
    return sum(amounts,D(0))
native_split=[]
for recipe,source_rows in [('S0',s0_fill_reports),('B',b_fill_reports)]:
    for asset in ['BTC','SOL']:
        for liquidity in ['MAKER','TAKER']:
            selected=[row for row in source_rows if row['instrument_id'].startswith(asset) and row['liquidity_side']==liquidity]
            native_split.append(dict(recipe=recipe,asset=asset,liquidity=liquidity,native_filled_order_rows=len(selected),commissions_USDT=sum((commission_sum(row) for row in selected),D(0)),filled_qty_times_average_price_notional=sum((dec(row['filled_qty'])*dec(row['avg_px']) for row in selected),D(0)),basis='NATIVE_AGGREGATED_FILLED_ORDER_REPORT_ROWS_NOT_TICK_FILL_REPLAY',signed_asset_funding='UNKNOWN',native_asset_net='UNKNOWN_NOT_EXPORTED'))
write('S0-B-native-asset-liquidity',native_split)
write('native-order-notional-reconciliation',[dict(recipe=recipe,aggregated_native_report_notional=sum((row['filled_qty_times_average_price_notional'] for row in native_split if row['recipe']==recipe),D(0)),comparison_notional=reference['turnover'],native_report_minus_comparison=sum((row['filled_qty_times_average_price_notional'] for row in native_split if row['recipe']==recipe),D(0))-dec(reference['turnover']),qualification='B native report avg_px serialization has tiny Decimal residual vs exact native fill audit; preserve both, no tolerance/exact equality claim') for recipe,reference in [('S0',s),('B',b)]])
parents=read('owner-BTC_REGIME_REENTRY_BAND_05-events/split-parent-audit.csv')
entry=read('owner-BTC_REGIME_REENTRY_BAND_05-events/entry-sizing-audit.csv')
labelp=ROOT/'reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution-episodes.csv'
inputs[str(labelp.relative_to(ROOT))]=hashlib.sha256(labelp.read_bytes()).hexdigest()
labels=list(csv.DictReader(labelp.open())); labels={(r['symbol'],r['number']):r for r in labels}
for name in ['comparison.json','owner-mechanistic-findings.md','reviewer-result-validation.json']:
    p=SRC/name;inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
me=[r for r in episodes if r['recipe']==B and r['S0_asset']]
se={(r['S0_asset'],r['S0_episode_number']):r for r in episodes if r['recipe']=='S0'}
be={(r['S0_asset'],r['S0_episode_number']):r for r in me}
sz=[r for r in sizing if r['recipe']==B]
byday={utc(r['candidate_start_ns'])[:10]:r for r in sz}
original_days={r['start_utc'][:10] for r in labels.values() if r['symbol']=='BTC'}
fee=[]
for asset in ['BTC','SOL']:
    for liq in ['MAKER','TAKER']:
        rows=[r for r in fills if r['instrument'].startswith(asset) and r['native_liquidity_side']==liq]
        fee.append(dict(recipe=B,asset=asset,liquidity=liq,fills=len(rows),fees=sum((dec(r['commission']) for r in rows),D(0)),turnover=sum((dec(r['notional']) for r in rows),D(0)),signed_funding='UNKNOWN',asset_native_net='UNKNOWN_NOT_EXPORTED'))
write('fees-by-asset-liquidity',fee)
write('fill-actions',[dict(action=k[0],reason=k[1],fills=len(v),fees=sum((dec(r['commission']) for r in v),D(0)),turnover=sum((dec(r['notional']) for r in v),D(0))) for k,v in sorted((lambda z:z.items())(dict((k,[r for r in fills if (r['action'],r['reason'])==k]) for k in sorted({(r['action'],r['reason']) for r in fills}))))])
metrics=[]
for k in ['TOTAL','ROI_percent','net_profit_retention_percent','settled_DD_percent','fills','BTC_fills','SOL_fills','fees','turnover','maker_notional','taker_notional','maker_fees','taker_fees']:
    metrics.append(dict(metric=k,S0=s[k],B=b[k],B_minus_S0=dec(b[k])-dec(s[k]),B_over_S0=dec(b[k])/dec(s[k])))
write('metrics',metrics)
ms={r['month']:r for r in monthly if r['recipe']=='S0'};mb={r['month']:r for r in monthly if r['recipe']==B}
mo=[];previous_ratio=D(1);product=D(1);boundaryprod=D(1)
for month,x in ms.items():
    y=mb[month]; sr=dec(y['start_equity'])/dec(x['start_equity']);er=dec(y['end_equity'])/dec(x['end_equity']);f=er/sr;boundary=sr/previous_ratio;product*=f;boundaryprod*=boundary
    mo.append(dict(month=month,S0_start=x['start_equity'],B_start=y['start_equity'],S0_end=x['end_equity'],B_end=y['end_equity'],S0_return_percent=x['normalized_return_percent'],B_return_percent=y['normalized_return_percent'],return_difference_pp=dec(y['normalized_return_percent'])-dec(x['normalized_return_percent']),relative_growth_multiplier=f,relative_log_growth=f.ln(),relative_start_capital=sr,relative_end_capital=er,relative_month_boundary_multiplier=boundary,cumulative_relative_within_month_growth=product,cumulative_relative_boundary_growth=boundaryprod,S0_fees=x['native_fees'],B_fees=y['native_fees'],S0_turnover=x['native_turnover'],B_turnover=y['native_turnover'],S0_fills=x['native_fills'],B_fills=y['native_fills'],B_minus_S0_end=dec(y['end_equity'])-dec(x['end_equity'])))
    previous_ratio=er
write('monthly-divergence',mo)
write('windows',[dict(window=x['window'],S0_return_percent=x['normalized_return_percent'],B_return_percent=y['normalized_return_percent'],S0_start=x['start_equity'],B_start=y['start_equity'],S0_end=x['end_equity'],B_end=y['end_equity'],S0_DD=x['local_observed_DD_percent'],B_DD=y['local_observed_DD_percent']) for x in windows if x['recipe']=='S0' for y in windows if y['recipe']==B and y['window']==x['window']])
sig=[]
for r in signals:
    if not r['close']:continue
    a=dec(r['atr14']);dist=(dec(r['close'])-dec(r['ema']))/a; margin=abs(dist)-D('.5')
    sig.append(dict(utc=utc(r['timestamp_ns']),timestamp_ns=r['timestamp_ns'],event=r['event'],side=r['side'],close=r['close'],ema=r['ema'],atr14=r['atr14'],signed_distance_ATR=dist,absolute_distance_ATR=abs(dist),margin_over_05ATR=margin))
write('decision-inputs',sig)
wr=[]
for i,w in enumerate(waits,1):
    lo,hi=ns(w['latch_start_utc']),ns(w['actual_next_entry_utc']);numbers=json.loads(w['S0_episode_numbers']);samples=[r for r in sig if lo<=int(r['timestamp_ns'])<=hi]
    allow=[r for r in samples if r['event']=='B_ENTRY_ALLOWED'];assert len(allow)==1
    row=dict(wait_id=i,**w,delay_days=dec(w['delay_seconds'])/86400,allow_close=allow[0]['close'],allow_ema=allow[0]['ema'],allow_atr14=allow[0]['atr14'],allow_signed_distance_ATR=allow[0]['signed_distance_ATR'],weak_signed_distances_ATR=json.dumps([str(r['signed_distance_ATR']) for r in samples if r['event']=='WAIT_REGIME_REENTRY']),S0_cohort_outcomes_json=json.dumps([dict(number=n,start=be['BTC',n]['S0_start_utc'],end=be['BTC',n]['S0_end_utc'],historical_ex_funding_label=be['BTC',n]['S0_existing_confirmed_fill_diagnostic_ex_funding'],S0_portfolio_window_return=se['BTC',n]['candidate_fixed_S0_window_equity_return_percent'],B_portfolio_same_window_return=be['BTC',n]['candidate_fixed_S0_window_equity_return_percent']) for n in numbers]),qualification='Cohort evidence; overlapping windows not additive and no standalone avoided PnL')
    wr.append(row)
write('waits',wr)
# One fixed gate-timing precheck requested by coordinator; no branch replay.
timing=[]
for w in wr:
    samples=[a for a in sig if w['latch_start_utc']<=a['utc']<=w['actual_next_entry_utc']]
    first=next(a for a in samples if abs(dec(a['signed_distance_ATR']))>D('.25'))
    original=next(a for a in samples if a['event']=='B_ENTRY_ALLOWED')
    timing.append(dict(wait_id=w['wait_id'],latch_start=w['latch_start_utc'],first_saved_025_eligibility=first['utc'],first025_side=first['side'],first025_signed_distance=first['signed_distance_ATR'],actual_05_signal=original['utc'],actual05_side=original['side'],hours_earlier_gate_only=(ns(original['utc'])-ns(first['utc']))/3600000000000,side_changed_before_native05=first['side']!=original['side'],S0_episode_numbers=w['S0_episode_numbers'],qualification='FIXED_025_GATE_TIMING_ON_ORIGINAL_B_STATES_ONLY_NO_BRANCH_REPLAY_NO_FILL_OR_RETURN_PREDICTION'))
write('fixed025-gate-timing',timing)
(OUT/'roi-fixed025-gate-timing.json').write_text(json.dumps(dict(fixed_alternative='.25ATR; one comparison only',latches=len(timing),earlier=sum(a['hours_earlier_gate_only']>0 for a in timing),same=sum(a['hours_earlier_gate_only']==0 for a in timing),total_gate_hours_earlier=sum(a['hours_earlier_gate_only'] for a in timing),max_gate_hours_earlier=max(a['hours_earlier_gate_only'] for a in timing),side_changed=sum(a['side_changed_before_native05'] for a in timing),no_portfolio_economics=True,no_causal_branch_or_fill_validation=True),indent=2)+'\n')
missing=[]; winners=[]
for r in me:
    if r['S0_asset']!='BTC':continue
    n=r['S0_episode_number'];lab=labels['BTC',n];same=r['candidate_same_day_BTC_parent']=='True';st=ns(r['S0_start_utc']);en=ns(r['S0_end_utc']);later=[a for a in sz if int(a['candidate_start_ns'])>st];nextp=min(later,key=lambda a:int(a['candidate_start_ns'])) if later else None
    wait=next((w for w in wr if w['latch_start_utc']<=r['S0_start_utc']<w['actual_next_entry_utc']),None)
    inputday=[a for a in sig if a['utc'][:10]==r['S0_start_utc'][:10]]
    startb=dec(r['candidate_fixed_S0_window_native_equity_start']);starts=dec(se['BTC',n]['candidate_fixed_S0_window_native_equity_start'])
    row=dict(S0_number=n,S0_side=lab['side'],S0_start=r['S0_start_utc'],S0_end=r['S0_end_utc'],historical_ex_funding_label=lab['confirmed_fill_net_ex_funding'],same_day_B_parent=same,S0_Q=r['S0_filled_BTC_qty'],B_Q=r['candidate_filled_BTC_qty'],B_over_S0_entry_capital=startb/starts,B_portfolio_S0_window_return=r['candidate_fixed_S0_window_equity_return_percent'],S0_portfolio_S0_window_return=se['BTC',n]['candidate_fixed_S0_window_equity_return_percent'],wait_id=wait['wait_id'] if wait else '',absence_class='RECORDED_WAIT' if wait else ('SAME_DAY' if same else 'CHANGED_CALENDAR_OUTSIDE_WAIT'),decision_inputs_json=json.dumps(inputday,default=str),next_B_entry=utc(nextp['candidate_start_ns']) if nextp else '',next_entry_delay_hours=(dec(nextp['candidate_start_ns'])-st)/D('3600000000000') if nextp else '',next_B_side=nextp['candidate_side'] if nextp else '',next_is_linked_S0_trade='NO_TEMPORAL_NEIGHBOR_ONLY')
    if not same:missing.append(row)
    if dec(lab['confirmed_fill_net_ex_funding'])>0:winners.append(row)
write('missing-S0-BTC',missing);write('all-S0-BTC-winners',winners)
write('new-candidate-dates',[dict(utc=utc(r['candidate_start_ns']),**r) for r in sz if r['S0_same_UTC_day']=='False'])
sizeout=[]
for r in sz:
    if r['S0_same_UTC_day']!='True':continue
    n=next(n for (a,n),v in be.items() if a=='BTC' and v['S0_start_utc'][:10]==utc(r['candidate_start_ns'])[:10]);v=be['BTC',n];capital=dec(v['candidate_fixed_S0_window_native_equity_start'])/dec(se['BTC',n]['candidate_fixed_S0_window_native_equity_start']);qr=dec(r['quantity_ratio_same_day'])
    sizeout.append(dict(S0_number=n,utc=utc(r['candidate_start_ns']),**r,B_over_S0_native_equity_at_S0_entry=capital,quantity_ratio_over_equity_ratio=qr/capital,qualification='Same UTC day, not forced matched price/clock/exposure; remaining residual includes caps/admission/rounding/decision-time differences, not isolated leverage cause'))
write('sizing-capital',sizeout)
activity=[]
for month in ms:
    pmonth=[a for a in parents if utc(a['start_ns']).startswith(month)]
    actual=[a for a in fills if utc(a['fill_ns']).startswith(month)]
    rights=[a for row in entry for a in json.loads(row['sol_right_activations']) if utc(a['timestamp_ns']).startswith(month)]
    activity.append(dict(month=month,S0_BTC_starts=sum(k[0]=='BTC' and a['start_utc'].startswith(month) for k,a in labels.items()),B_BTC_starts=len(pmonth),B_new_calendar_starts=sum(a['S0_same_UTC_day']=='False' and utc(a['candidate_start_ns']).startswith(month) for a in sz),missing_S0_BTC_starts=sum(a['S0_start'].startswith(month) for a in missing),B_BTC_fills=sum(a['instrument'].startswith('BTC') for a in actual),B_SOL_fills=sum(a['instrument'].startswith('SOL') for a in actual),B_SOL_add_fills=sum(a['action']=='SOL_ADD' for a in actual),B_SOL_add_quantity=sum((dec(a['qty']) for a in actual if a['action']=='SOL_ADD'),D(0)),B_SOL_add_notional=sum((dec(a['notional']) for a in actual if a['action']=='SOL_ADD'),D(0)),B_right_activation_events=len(rights),B_right_activation_level_count=sum(len(a['levels']) for a in rights),qualification='Actual saved B entry-right events and native fill activity; S0 rights not exported here; quantities/rights are not profit attribution'))
write('native-month-activity',activity)
counter=[]
for key in [('SOL','1')]+[('BTC',str(n)) for n in [29,40,41,67,96]]:
    r=be[key];v=se[key];counter.append(dict(**r,S0_portfolio_same_window_return=v['candidate_fixed_S0_window_equity_return_percent'],S0_window_start_equity=v['candidate_fixed_S0_window_native_equity_start'],S0_window_end_equity=v['candidate_fixed_S0_window_native_equity_end'],qualification='SOL row calendar match is BTC parent test, not SOL fill-presence test; use actual SOL fills separately'))
write('counterexamples',counter)
checks={}
checks['B_fee_exact']=sum((dec(r['commission']) for r in fills),D(0))==dec(b['fees'])
checks['B_turnover_exact']=sum((dec(r['notional']) for r in fills),D(0))==dec(b['turnover'])
checks['B_fill_count']=len(fills)==int(b['fills'])==484
checks['S0_native_asset_counts']=len(s0_fill_reports)==621 and sum(row['instrument_id'].startswith('BTC') for row in s0_fill_reports)==416 and sum(row['instrument_id'].startswith('SOL') for row in s0_fill_reports)==205
checks['native_order_report_fees_exact']=sum((commission_sum(row) for row in s0_fill_reports),D(0))==dec(s['fees']) and sum((commission_sum(row) for row in b_fill_reports),D(0))==dec(b['fees'])
checks['B_native_asset_counts']=len(b_fill_reports)==484 and sum(row['instrument_id'].startswith('BTC') for row in b_fill_reports)==322 and sum(row['instrument_id'].startswith('SOL') for row in b_fill_reports)==162
checks['B_parents']=len(parents)==len(sz)==77
checks['waits_allow_and_refusals']=len(wr)==41 and sum(int(w['weak_daily_refusals']) for w in waits)==83 and len(sig)==124
checks['all_baseline_episodes']=len(me)==131 and len(se)==131
checks['missing_and_new']=len(missing)==54 and sum(r['absence_class']=='RECORDED_WAIT' for r in missing)==50 and len([r for r in sz if r['S0_same_UTC_day']=='False'])==26
checks['monthly_ratio_bridge']=abs(product*boundaryprod-dec(mb['2026-08']['end_equity'])/dec(ms['2026-08']['end_equity']))<D('1e-35')
checks['signal_band']=all((r['event']=='B_ENTRY_ALLOWED')==(dec(r['absolute_distance_ATR'])>D('.5')) for r in sig)
assert all(checks.values()),checks
summary=dict(source_pin='25a085f596292df58e51188dd91e996adbe5724c',report_start_HEAD='7fa5800',no_native_runs=True,baseline_total=s['TOTAL'],B_total=b['TOTAL'],total_gap=dec(b['TOTAL'])-dec(s['TOTAL']),goal_total=D('5470396.514987347'),goal_shortfall=D('5470396.514987347')-dec(b['TOTAL']),fee_saving=dec(s['fees'])-dec(b['fees']),unattributed_nonfee_terminal_difference=(dec(b['TOTAL'])+dec(b['fees']))-(dec(s['TOTAL'])+dec(s['fees'])),nonfee_qualification='Accounting residual, not gross strategy PnL; includes unknown signed funding and full path/capital/execution effects',within_month_relative_product=product,boundary_relative_product=boundaryprod,wait_days=sum((dec(r['delay_seconds'])/86400 for r in waits),D(0)),missing_winner_count=sum(dec(r['historical_ex_funding_label'])>0 for r in missing),missing_outside_wait=[r['S0_number'] for r in missing if r['absence_class']!='RECORDED_WAIT'],signed_asset_funding='UNKNOWN',native_asset_net='UNKNOWN_NOT_EXPORTED',selfchecks=checks,input_sha256=inputs)
(OUT/'roi-summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='input_sha256'},indent=2,default=str))
