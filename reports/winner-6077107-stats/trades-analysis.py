"""Archived winner descriptive statistics only; reuse archived fill-attribution money."""
import ast,csv,hashlib,json,statistics,math
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict,deque
from datetime import datetime,timezone
OUT=Path('reports/winner-6077107-stats'); OUT.mkdir(exist_ok=True)
P=Path('reports/btc-split-sol-cover-20261018'); label='btc025-planref-tp-ioc'
ref=json.loads(Path('reports/carry-pair-run-113/control-reference.json').read_text()); raw=Path(ref['raw_path']); r=json.loads(raw.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(raw)==ref['raw_sha256']; assert D(r['terminal_total'])==D('6077107.23887483')
nf=Path(r['execution_artifacts']['fills']['path']); assert sha(nf)==r['execution_artifacts']['fills']['sha256']
native=list(csv.DictReader(nf.open())); audits=r['fill_audit']; assert len(native)==len(audits)==621
summary_path=P/f'comparison-analysis-{label}.json'; prior=json.loads(summary_path.read_text()); assert D(prior['terminal_total'])==D(r['terminal_total'])
def utc(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
def dump(name,x):(OUT/name).write_text(json.dumps(x,indent=2,default=str,allow_nan=False)+'\n')
def writecsv(name,rows):
 if not rows:return
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows({k:json.dumps(v,default=str) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
# Same exact nativeCSV multi-key association as existing helper; no execution or PnL simulation.
lookup=defaultdict(deque)
for n in native:
 ns=int(datetime.fromisoformat(n['ts_last']).timestamp())*10**9
 lookup[(ns,n['instrument_id'],D(n['filled_qty']),D(n['avg_px']).quantize(D('.000001')))].append(n)
matched=[]
for i,a in enumerate(audits):
 key=(int(a['fill_ns']),a['instrument'],D(a['qty']),D(a['px']).quantize(D('.000001')))
 assert lookup[key];n=lookup[key].popleft();assert sum(D(c.split()[0]) for c in ast.literal_eval(n['commissions']))==D(a['commission']);assert n['liquidity_side']==a['native_liquidity_side']
 matched.append(dict(a,native=n,audit_index=i))
assert not any(lookup.values())
# Quantity conservation validates native flat boundaries; monetary results are reused, never recalculated.
cycles={'BTC':[],'SOL':[]}; current={}; qty=defaultdict(D)
for f in matched:
 asset='BTC' if f['instrument'].startswith('BTC') else 'SOL';q=D(f['qty']);sgn=1 if f['native']['side']=='BUY' else -1;old=qty[asset]
 if old==0:
  current[asset]={'start_ns':int(f['fill_ns']),'side':'LONG' if sgn>0 else 'SHORT','fills':[],'entry_fills':[],'exit_fills':[]}
 c=current[asset];c['fills'].append(f)
 if old==0 or old*sgn>0:c['entry_fills'].append(f)
 else:
  assert q<=abs(old),'Unexpected reversal crossing zero';c['exit_fills'].append(f)
 qty[asset]+=sgn*q
 if qty[asset]==0:
  c['end_ns']=int(f['fill_ns']);cycles[asset].append(c);del current[asset]
assert not current and not any(qty.values())
trades=[];proof={}
for asset in ['BTC','SOL']:
 path=P/f'comparison-analysis-{label}-{asset.lower()}-fill-attribution.csv';books=list(csv.DictReader(path.open()));cs=cycles[asset];assert len(books)==len(cs)
 for i,(b,c) in enumerate(zip(books,cs),1):
  assert int(b['start_ns'])==c['start_ns'];en=c['entry_fills'];ex=c['exit_fills'];eq=sum((D(f['qty']) for f in en),D(0));xq=sum((D(f['qty']) for f in ex),D(0));assert eq==xq==D(b['entry_qty']);assert sum(D(f['qty'])*D(f['px']) for f in en)==D(b['entry_notional']);assert sum(D(f['commission']) for f in en)==D(b['entry_fees']);assert sum(D(f['commission']) for f in ex)==D(b['exit_fees']);assert len(en)==int(b['entry_count'])
  if asset=='BTC':assert ast.literal_eval(b['exit_times'])==[int(f['fill_ns']) for f in ex]
  else:assert int(b['end_ns'])==c['end_ns'];assert len(ex)==int(b['exit_count']);assert b['side']==('BUY' if c['side']=='LONG' else 'SELL')
  gross=D(b['gross']);fees=D(b['entry_fees'])+D(b['exit_fees']);net=D(b['net_ex_funding']);assert gross-fees==net
  xn=sum(D(f['qty'])*D(f['px']) for f in ex)
  t=dict(asset=asset,trade_number=i,side=c['side'],start_ns=c['start_ns'],end_ns=c['end_ns'],entry_utc=utc(c['start_ns']),exit_utc=utc(c['end_ns']),duration_seconds=(c['end_ns']-c['start_ns'])//10**9,entry_qty=eq,exit_qty=xq,entry_notional=D(b['entry_notional']),entry_vwap=D(b['entry_notional'])/eq,exit_notional=xn,exit_vwap=xn/xq,entry_fees=D(b['entry_fees']),exit_fees=D(b['exit_fees']),fees=fees,gross=gross,net_ex_funding=net,net_return_on_cumulative_entry_notional_percent=net/D(b['entry_notional'])*100,gross_return_on_cumulative_entry_notional_percent=gross/D(b['entry_notional'])*100,entry_fill_count=len(en),exit_fill_count=len(ex),exit_reasons=dict(Counter(f['reason'] for f in ex)),final_exit_reason=ex[-1]['reason'],final_exit_action=ex[-1]['action'],partial_exit_fill_count=len(ex)-1,final_exit_order_id=ex[-1]['native']['client_order_id'],funding='UNKNOWN_NOT_ALLOCATED')
  trades.append(t)
 proof[asset]=dict(native_flat_to_flat_trades=len(cs),archived_attribution_rows=len(books),source=str(path),source_sha256=sha(path),all_starts_ends_quantity_entrynotional_fees_counts_match=True)
 assert abs(sum(t['gross'] for t in trades if t['asset']==asset)-D(prior['confirmed_fill_weighted_average_attribution'][asset]['gross']))<D('.00000001')
assert proof['BTC']['native_flat_to_flat_trades']==105
assert sum(t['fees'] for t in trades)==D(r['native_fees'])
def pctile(v,p):
 v=sorted(float(x) for x in v)
 if not v:return None
 i=(len(v)-1)*p;lo=math.floor(i);hi=math.ceil(i);return v[lo]+(v[hi]-v[lo])*(i-lo)
def dist(v):
 v=[float(x) for x in v]
 return dict(n=len(v),mean=statistics.mean(v),median=statistics.median(v),population_std=statistics.pstdev(v),p10=pctile(v,.1),p90=pctile(v,.9),min=min(v),max=max(v)) if v else None
def pf(v):
 pos=sum((x for x in v if x>0),D(0));neg=sum((x for x in v if x<0),D(0));return dict(winning_sum=pos,losing_sum=neg,profit_factor=pos/-neg if neg<0 else None,undefined_reason=None if neg<0 else 'NO_LOSSES')
def streaks(ts):
 out=[]
 for t in sorted(ts,key=lambda t:(t['end_ns'],t['start_ns'],t['asset'])):
  sign='WIN' if t['net_ex_funding']>0 else 'LOSS' if t['net_ex_funding']<0 else 'BREAK_EVEN'
  if not out or out[-1]['outcome']!=sign:out.append(dict(outcome=sign,length=0,first_entry_utc=t['entry_utc'],first_exit_utc=t['exit_utc'],last_exit_utc=t['exit_utc'],net_ex_funding=D(0),trades=[]))
  s=out[-1];s['length']+=1;s['last_exit_utc']=t['exit_utc'];s['net_ex_funding']+=t['net_ex_funding'];s['trades'].append(f"{t['asset']}-{t['trade_number']}")
 return dict(order='By final native closing fill timestamp; overlapping trades can overlap in time; BE breaks streaks',series=out,by_outcome={sign:dict(series_count=sum(s['outcome']==sign for s in out),length_distribution=dict(Counter(s['length'] for s in out if s['outcome']==sign)),longest_length=max((s['length'] for s in out if s['outcome']==sign),default=0),longest=[s for s in out if s['outcome']==sign and s['length']==max((s['length'] for s in out if s['outcome']==sign),default=0)],worst_series=min((s for s in out if s['outcome']==sign),key=lambda s:s['net_ex_funding'],default=None)) for sign in ['WIN','LOSS','BREAK_EVEN']})
def stats(ts):
 net=[t['net_ex_funding'] for t in ts];gross=[t['gross'] for t in ts];N=len(ts)
 return dict(trades=N,wins=sum(x>0 for x in net),losses=sum(x<0 for x in net),break_even=sum(x==0 for x in net),win_percent=D(sum(x>0 for x in net))/D(N)*100 if N else None,gross_total=sum(gross,D(0)),fees=sum((t['fees'] for t in ts),D(0)),net_ex_funding=sum(net,D(0)),gross_profit_factor=pf(gross),net_profit_factor=pf(net),trade_pnl_ex_funding=dist(net),winning_trade_pnl_ex_funding=dist(x for x in net if x>0),losing_trade_pnl_ex_funding=dist(x for x in net if x<0),entrynotional_return_percent=dist(t['net_return_on_cumulative_entry_notional_percent'] for t in ts),holding_duration_seconds=dist(t['duration_seconds'] for t in ts),entry_quantity=dist(t['entry_qty'] for t in ts),entry_notional=dist(t['entry_notional'] for t in ts),cumulative_entry_notional=sum((t['entry_notional'] for t in ts),D(0)),size_weighted_return_percent=sum(net,D(0))/sum((t['entry_notional'] for t in ts),D(0))*100 if N else None,streaks=streaks(ts),top10_winners=sorted([t for t in ts if t['net_ex_funding']>0],key=lambda t:t['net_ex_funding'],reverse=True)[:10],top10_losers=sorted([t for t in ts if t['net_ex_funding']<0],key=lambda t:t['net_ex_funding'])[:10])
groups={'ALL':stats(trades)}
for asset in ['BTC','SOL']:
 for side in ['ALL','LONG','SHORT']:
  ts=[t for t in trades if t['asset']==asset and (side=='ALL' or t['side']==side)];groups[asset+'_'+side]=stats(ts)
monthly=[]
for asset in ['BTC','SOL']:
 months=sorted(set(t['exit_utc'][:7] for t in trades if t['asset']==asset))
 for m in months:
  ts=[t for t in trades if t['asset']==asset and t['exit_utc'].startswith(m)];monthly.append(dict(asset=asset,exit_month_utc=m,trades=len(ts),wins=sum(t['net_ex_funding']>0 for t in ts),losses=sum(t['net_ex_funding']<0 for t in ts),gross=sum(t['gross'] for t in ts),entry_fees=sum(t['entry_fees'] for t in ts),exit_fees=sum(t['exit_fees'] for t in ts),fees=sum(t['fees'] for t in ts),net_ex_funding=sum(t['net_ex_funding'] for t in ts),basis='All entire-trade fees/PnL assigned final exit month, not calendar native equity return'))
fillgroups=defaultdict(list)
for f in matched:
 asset='BTC' if f['instrument'].startswith('BTC') else 'SOL'
 for key in [asset,asset+'_ACTION_'+f['action'],asset+'_REASON_'+f['reason'],asset+'_LIQUIDITY_'+f['native']['liquidity_side'],asset+'_ACTION_REASON_LEVEL_'+f['action']+'_'+f['reason']+'_'+(f['level'] or 'NA')]:fillgroups[key].append(f)
fill_stats={k:dict(count=len(fs),qty=sum(D(f['qty']) for f in fs),notional=sum(D(f['notional']) for f in fs),fees=sum(D(f['commission']) for f in fs)) for k,fs in fillgroups.items()}
exitcounts=[]
for asset in ['BTC','SOL']:
 ats=[t for t in trades if t['asset']==asset]
 for reason in sorted({f['reason'] for c in cycles[asset] for f in c['exit_fills']}):
  fs=[f for c in cycles[asset] for f in c['exit_fills'] if f['reason']==reason]; finals=[t for t in ats if t['final_exit_reason']==reason];exitcounts.append(dict(asset=asset,reason=reason,exit_fills=len(fs),partial_exit_fills=len(fs)-len(finals),final_flattening_fills=len(finals),trades_with_reason=sum(reason in t['exit_reasons'] for t in ats),reason_fill_fees=sum(D(f['commission']) for f in fs)))
residual=D(r['terminal_total'])-D('10000')-sum(t['net_ex_funding'] for t in trades)
proof.update(raw_path=str(raw),raw_sha256=sha(raw),native_fills_path=str(nf),native_fills_sha256=sha(nf),matched_fills=len(matched),native_fees_conserved=True,existing_helper='scripts/analyze_split_cover_results.py',existing_helper_sha256=sha(Path('scripts/analyze_split_cover_results.py')),summary_path=str(summary_path),summary_sha256=sha(summary_path),terminal_flat=True)
limitations=['Per-trade gross/net reused from archived actual-native weighted-average fill attribution, not native settled per-asset cash/PnL export.','Signed funding UNKNOWN; native TOTAL minus seed minus confirmed fill net is unallocated, not automatically funding.','Trade means continuous per-asset native flat-to-flat inventory: additions and partial TP exits are not additional trades. All 105 BTC parent books exactly match native flat-to-flat cycles.','Return denominator is cumulative entry notional, including additions/re-additions. This is not return on equity or capital/margin allocation. Asset returns are not additive.','Size-weighted return = SUM(trade net ex funding)/SUM(cumulative trade entry notional)*100.','Distribution statistics use float descriptive arithmetic; monetary conservation uses Decimal. Quantiles use linear interpolation at (n-1)*p; standard deviation is population.','Monthly closed-trade tables assign entire trade and its entry/exit fees to final exit month; do not equal calendar account equity PnL.','Native CSV fill side/liquidity/order IDs are matched one-to-one with audited time/instrument/qty/rounded-price; exact audit prices/notional/commissions used for money.','No native backtest/optimizer/trading code/config/service changes. No raw full-minute gzip read by this report.','Partial exit fill means a native fill after which inventory remains; several fills at one timestamp may implement one strategy close decision, so these are not counts of distinct exit decisions.', 'Side-specific streaks are within the filtered side subset; intervening trades on the opposite side are omitted, not counted as breaks.', 'SOL timeout/rights/anchor provenance is known only where archived audit explicitly records it; fill reasons alone do not prove full rights ledger or why no order occurred.']
rights=[dict(episode_id=e['episode_id'],q0_ns=e['q0_ns'],omitted_zero_levels=e.get('omitted_zero_levels'),reference_target_lots=e.get('reference_target_lots'),sol_right_activations=e.get('sol_right_activations')) for e in r['entry_sizing_audit']]
writecsv('trades-archived-sol-rights.csv',rights)
sol_audit=dict(cover_audit_event_count=len(r['split_cover_audit']['cover']),entry_sizing_rows=len(rights),explicit_zero_level_activation_event_count=sum(len(x['sol_right_activations'] or []) for x in rights),activation_level_occurrences=dict(Counter(str(level) for x in rights for event in (x['sol_right_activations'] or []) for level in event.get('levels',[]))),limits='Archived entry_sizing_audit records explicit zero-level activations; positive-level actual BTC reduction fills observable separately. cover event list is empty. No complete rights spent/released/timeout decision ledger exported; not inferable from fill reasons.',hard_timeout_trades=[t for t in trades if t['asset']=='SOL' and 'SOL_HARD_TIMEOUT' in t['exit_reasons']])
result=dict(sol_audit=sol_audit,post_boundary_settlement=r['post_boundary_settlement'],winner_terminal_TOTAL=r['terminal_total'],seed='10000',trade_definition='Continuous actual native perasset flat-to-flat',groups=groups,monthly_closed_trade=monthly,fill_statistics=fill_stats,exit_reason_partial_vs_final=exitcounts,reconciliation=dict(confirmed_fill_net_ex_funding=sum(t['net_ex_funding'] for t in trades),seed_plus_confirmed_fill_net=D('10000')+sum(t['net_ex_funding'] for t in trades),native_terminal_TOTAL=r['terminal_total'],unallocated_native_cash_difference=residual,unallocated_difference_explanation='UNKNOWN_NOT_AUTOMATICALLY_FUNDING',signed_funding='UNKNOWN',native_settled_perasset_PnL='UNKNOWN_NOT_EXPORTED'),proof=proof,limitations=limitations)
writecsv('trades-ledger.csv',trades);writecsv('trades-monthly-closed.csv',monthly);writecsv('trades-exit-reasons.csv',exitcounts);dump('trades-statistics.json',result);dump('trades-proof.json',proof)
# Realized trade attribution cumulative only, explicitly not account equity/drawdown.
ledger=[];acc=defaultdict(D)
for t in sorted(trades,key=lambda t:(t['end_ns'],t['asset'])):
 acc[t['asset']]+=t['net_ex_funding'];ledger.append(dict(exit_utc=t['exit_utc'],asset=t['asset'],trade_number=t['trade_number'],trade_net_ex_funding=t['net_ex_funding'],cumulative_BTC_net_ex_funding=acc['BTC'],cumulative_SOL_net_ex_funding=acc['SOL'],cumulative_combined_net_ex_funding=sum(acc.values()),basis='Closed-trade attribution only; NOT native equity or cash curve'))
writecsv('trades-cumulative-attribution.csv',ledger)
lines=['# Exact winner: detailed archived trade statistics','','Native terminal TOTAL **6,077,107.23887483 USDT**, seed 10,000. Numbers below describe confirmed fills and exclude unallocated funding.','','## Trade summary','','| Group | Trades | Wins | Losses | BE | Win % | Gross | Fees | Net ex funding | Net PF |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for k,s in groups.items():lines.append(f"| {k} | {s['trades']} | {s['wins']} | {s['losses']} | {s['break_even']} | {s['win_percent']:.4f} | {s['gross_total']:,.8f} | {s['fees']:,.8f} | {s['net_ex_funding']:,.8f} | {s['net_profit_factor']['profit_factor']} |")
lines+=['','Gross/net profit factors respectively: '+ '; '.join(k+' '+str(v['gross_profit_factor']['profit_factor'])+'/'+str(v['net_profit_factor']['profit_factor']) for k,v in groups.items())+'.','', 'Trade ledger includes one final boundary settlement at 2026-09-01 00:00 UTC. Its final BTC close fee is 9,527.33973961 USDT. This trade-level total is distinct from end-exclusive calendar equity returns.']
lines+=['','## Distributions and size-normalized returns','','Duration starts at first native fill and ends at final flattening fill; entry additions do not restart the clock. Entry return denominator sums every opening fill notional.','', '| Group | Net mean | Net median | Net SD | Net P10 | Net P90 | Return mean % | Return median % | Weighted % | Hold median hours | Hold P90 hours |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for k,s in groups.items():
 p=s['trade_pnl_ex_funding'];v=s['entrynotional_return_percent'];h=s['holding_duration_seconds'];lines.append(f"| {k} | {p['mean']:,.2f} | {p['median']:,.2f} | {p['population_std']:,.2f} | {p['p10']:,.2f} | {p['p90']:,.2f} | {v['mean']:.6f} | {v['median']:.6f} | {s['size_weighted_return_percent']:.6f} | {h['median']/3600:.4f} | {h['p90']/3600:.4f} |")
lines+=['','## Consecutive outcomes','','Streaks sorted by final closing timestamp; BE breaks a streak. Combined streaks mix overlapping asset exposures. Full series, length distributions and longest dates/PnL are in JSON.']
for k,s in groups.items():
 lines+=['',f'### {k}']
 for sign in ['WIN','LOSS']:
  st=s['streaks']['by_outcome'][sign];lines+=[f"- {sign}: {st['series_count']} series; lengths {st['length_distribution']}; longest {st['longest_length']} trades."]
  for z in st['longest']:lines += [f"  - {z['first_exit_utc']} → {z['last_exit_utc']}; sum net ex funding {z['net_ex_funding']}; trades {', '.join(z['trades'])}."]
for asset in ['BTC','SOL']:
 lines+=['',f'## {asset}: ten largest winners and ten largest losers','','Entire continuous trade amounts; quantity is cumulative entry/exit quantity, not peak quantity. Exit VWAP is quantity-weighted across all exit fills.']
 for kind in ['top10_winners','top10_losers']:
  lines+=['',f'### {kind}','','| # | Side | Entry UTC | Final exit UTC | Qty | Entry VWAP | Exit VWAP | Fees | Gross | Net ex funding | Hold h | Exit reasons |','|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
  for t in groups[asset+'_ALL'][kind]:lines.append(f"| {t['trade_number']} | {t['side']} | {t['entry_utc']} | {t['exit_utc']} | {t['entry_qty']} | {t['entry_vwap']:.6f} | {t['exit_vwap']:.6f} | {t['fees']:.8f} | {t['gross']:.8f} | {t['net_ex_funding']:.8f} | {t['duration_seconds']/3600:.4f} | {t['exit_reasons']} |")
lines+=['','## Exit fills: partial reductions versus final flat','','| Asset | Reason | Fill rows | Partial reductions | Final flattenings | Trades with reason |','|---|---|---:|---:|---:|---:|']
for e in exitcounts:lines.append(f"| {e['asset']} | {e['reason']} | {e['exit_fills']} | {e['partial_exit_fills']} | {e['final_flattening_fills']} | {e['trades_with_reason']} |")
lines+=['','## SOL timeout and rights evidence','',f"Exactly one continuous SOL trade hard-times out: SOL-24, LONG, 2026-05-20 00:00 UTC → 2026-06-03 00:11 UTC (14 days 11 minutes). Twelve entries and twelve closing native fills represent one trade. Gross -119,480; fees 1,045.836; net ex funding -120,525.836 USDT; entry-notional return -11.92734646%.",'',f"Archived cover events: {sol_audit['cover_audit_event_count']}; explicit entry-sizing zero-level activation events: {sol_audit['explicit_zero_level_activation_event_count']}; activation level occurrences: {sol_audit['activation_level_occurrences']}. Existing explicit rows exported to trades-archived-sol-rights.csv. Full spent/released/timeout rights decision ledger UNKNOWN, so no stronger rights-causality claim."]
lines+=['','## Monthly closed-trade attribution','','Every trade is assigned to its final exit month; fees include all its opening and closing fills, even in earlier months. This table is distinct from calendar account equity PnL.','','| Asset | Exit month | Trades | Wins | Losses | Gross | Fees | Net ex funding |','|---|---|---:|---:|---:|---:|---:|---:|']
for m in monthly:lines.append(f"| {m['asset']} | {m['exit_month_utc']} | {m['trades']} | {m['wins']} | {m['losses']} | {m['gross']:.8f} | {m['fees']:.8f} | {m['net_ex_funding']:.8f} |")
lines+=['','## Fill counts, turnover and fees','','| Category | Count | Notional | Fees |','|---|---:|---:|---:|']
for k,s in fill_stats.items():lines.append(f"| {k} | {s['count']} | {s['notional']} | {s['fees']} |")
lines+=['','## Reconciliation and evidence','',f"Seed + fill-attributed net ex funding = {result['reconciliation']['seed_plus_confirmed_fill_net']}. Native terminal TOTAL = {r['terminal_total']}. Difference **{residual} USDT**, explanation **UNKNOWN**; do not label this signed funding.",'',f"Native raw SHA-256 `{sha(raw)}`; native fills SHA-256 `{sha(nf)}`. All 621 fill rows match archived native CSV one-to-one, fees conserve to {r['native_fees']}; terminal quantity zero. BTC **105** native flat-to-flat trades equal 105 strategy parent books; SOL **{len(cycles['SOL'])}** native flat-to-flat trades.",'','## Definitions and limitations','']+['- '+x for x in limitations]+['','Files: trades-ledger.csv (complete trade ledger); trades-statistics.json (all perasset/side metrics, top10 and streak series); trades-monthly-closed.csv; trades-exit-reasons.csv; trades-cumulative-attribution.csv (not account equity); trades-proof.json.']
(OUT/'trades-report.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'counts':{a:len(cs) for a,cs in cycles.items()},'groups':{k:{z:s[z] for z in ['trades','wins','losses','win_percent','gross_total','fees','net_ex_funding','size_weighted_return_percent']} for k,s in groups.items()},'reconciliation':result['reconciliation']},default=str))
