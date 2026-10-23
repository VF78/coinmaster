"""Summarize explicitly named completed audits only. No native trace reads."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,json,hashlib,sys,ast
P=Path(__file__).resolve().parent
def readcsv(path):return list(csv.DictReader(Path(path).open()))
def dumpcsv(name,rows):
    if not rows:return
    with (P/name).open('w') as f:
        w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader()
        w.writerows({k:json.dumps(v,sort_keys=True,default=str) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
recipes=sys.argv[1:]
assert recipes and all((P/('verifier-'+recipe+'-audit.json')).exists() for recipe in recipes)
summary=[];bridges=[];riskfills=[];snapshots=[];liquidity=[];liquiditychecks={}
for recipe in recipes:
    a=json.loads((P/('verifier-'+recipe+'-audit.json')).read_text());r=json.loads((P/('owner-'+recipe+'-receipt.json')).read_text());d=json.loads(Path(r['artifact']).read_text());raw=json.loads(Path(r['raw_artifact']).read_text())
    summary.append(dict(recipe=recipe,status=a['status'],checks=len(a['checks']),TOTAL=a['TOTAL'],retention_percent=a['retention_percent'],global_settled_DD_percent=a['risk']['global_settled_DD_percent'],fees=a['fees'],fills=a['fills'],BTC_fills=a['BTC_fills'],SOL_fills=a['SOL_fills'],liquidations=a['liquidations'],receipts=a['risk']['receipts'],missing=a['risk']['missing_source_minutes'],pass_50_90=a['pass_50_90'],BTC_max_loss_streak=a['maximum_loss_streak'].get('BTC',0),SOL_max_loss_streak=a['maximum_loss_streak'].get('SOL',0),unallocated_cash_bridge=a['unallocated_cash_bridge']))
    net=sum((D(x['confirmed_fill_net_ex_funding']) for x in a['assets']),D(0))
    bridges.append(dict(recipe=recipe,TOTAL=a['TOTAL'],seed='10000',net_profit=D(a['TOTAL'])-10000,confirmed_fill_net_ex_funding=net,unallocated_cash_bridge=a['unallocated_cash_bridge'],last_preterminal_native_equity=a['terminal']['last_preterminal_native_equity'],native_cash_before_terminal_settlement=a['terminal']['interval_cash_total_before_settlement'],observed_equity_to_TOTAL_bridge=a['terminal']['observed_equity_to_TOTAL_bridge'],actual_boundary_fees=a['terminal']['actual_boundary_fees'],signed_asset_funding='UNKNOWN'))
    fm=r['exports']['native-fill-audit.csv'];fp=Path(fm['path']);frows=readcsv(fp)
    feechecks=dict(frozen_native_audit_export=hashlib.sha256(fp.read_bytes()).hexdigest()==fm['sha256'],native_audit_count=len(frows)==a['fills'],all_liquidity_explicit=all(x['native_liquidity_side'] in ('MAKER','TAKER') for x in frows),all_commission_currency_USDT=all(x['commission_currency']=='USDT' for x in frows),native_fee_total=sum((D(x['commission']) for x in frows),D(0))==D(a['fees']),native_fill_notional_total=sum((D(x['notional']) for x in frows),D(0))==D(a['native_fill_audit_turnover']))
    for asset in ['BTC','SOL']:
        assetrows=[x for x in frows if x['instrument'].startswith(asset)]
        actualasset=next(x for x in a['assets'] if x['asset']==asset)
        feechecks[asset+'_actual_native_commission_exact']=sum((D(x['commission']) for x in assetrows),D(0))==D(actualasset['native_fees'])
        feechecks[asset+'_actual_native_count_exact']=len(assetrows)==actualasset['filled_order_rows']
        for side in ['MAKER','TAKER']:
            selected=[x for x in assetrows if x['native_liquidity_side']==side]
            liquidity.append(dict(recipe=recipe,asset=asset,native_liquidity_side=side,actual_native_fill_rows=len(selected),actual_native_notional=sum((D(x['notional']) for x in selected),D(0)),actual_native_commissions_USDT=sum((D(x['commission']) for x in selected),D(0)),basis='EXPLICIT_NATIVE_FILL_AUDIT_LIQUIDITY_SIDE_NOT_ORDER_TYPE',source_export_sha256=fm['sha256'],signed_asset_funding='UNKNOWN'))
    assert all(feechecks.values()),(recipe,feechecks)
    liquiditychecks[recipe]=dict(checks=feechecks,all_pass=True)
    a['native_liquidity_cost_checks']=feechecks
    a['native_liquidity_costs']=[row for row in liquidity if row['recipe']==recipe]
    (P/('verifier-'+recipe+'-audit.json')).write_text(json.dumps(a,indent=2,default=str)+'\n')
    nf={row['client_order_id']:row for row in readcsv(d['execution_artifacts']['fills']['path'])}
    for cid,event in raw['native_order_events'].items():
        if event['reason'] not in ['ZERO_RETRACE_RISK','SOL_DOMINANT_ADVERSE_RISK']:continue
        if cid not in nf:continue # Proposal/cancel without actual native fill is not a risk fill.
        native=nf[cid]
        audit=[x for x in d['fill_audit'] if x['reason']==event['reason'] and x['submit_ns']==event['submit_ns'] and x['instrument']==event['instrument']]
        assert audit,'Native risk order has no fill-audit receipt'
        fees=sum((D(x['commission']) for x in audit),D(0));q=sum((D(x['qty']) for x in audit),D(0));csvfee=sum((D(v.rsplit(' ',1)[0]) for v in ast.literal_eval(native['commissions'])),D(0))
        checks=dict(native_reduce_only=native['is_reduce_only']=='True',native_filled_Q_matches_audit=q==D(native['filled_qty']),native_fee_matches_audit=fees==csvfee)
        assert all(checks.values()),checks
        riskfills.append(dict(recipe=recipe,client_order_id=cid,reason=event['reason'],submit_ns=event['submit_ns'],native_last_fill_utc=native['ts_last'],instrument=native['instrument_id'],side=native['side'],actual_filled_Q=q,native_avg_px=native['avg_px'],actual_native_fees=fees,actual_native_audit_fill_rows=len(audit),checks=checks,qualification='ACTUAL_NATIVE_FILLED_REDUCE_ONLY_ORDER_NOT_PROPOSAL_OR_COUNTERFACTUAL'))
    for i,excursion in enumerate(a['risk']['excursions_ge_30percent'],1):
        for endpoint in ['peak','trough','recovery']:
            snap=excursion.get(endpoint+'_native_snapshot')
            if not snap:continue
            snapshots.append(dict(recipe=recipe,excursion=i,DD_percent=D(excursion['drawdown_fraction'])*100,endpoint=endpoint,receipt_utc=datetime.fromtimestamp(snap['receipt_ns']/1e9,timezone.utc).isoformat(),source_quote_utc=datetime.fromtimestamp(snap['source_quote_ns']/1e9,timezone.utc).isoformat(),cash=snap['cash'],native_equity=snap['equity'],positions=json.loads(snap['native_positions_and_mark_ohlc_json']),qualification='Native receipt equity/cash and native position snapshots; raw mark OHLC may require venue tick rounding, do not invent perasset settled PnL from raw closes'))
dumpcsv('verifier-completed-summary.csv',summary);dumpcsv('verifier-cash-bridges.csv',bridges);dumpcsv('verifier-actual-risk-fills.csv',riskfills);dumpcsv('verifier-DD-native-snapshots.csv',snapshots)
dumpcsv('verifier-liquidity-costs.csv',liquidity)
(P/'verifier-liquidity-checks.json').write_text(json.dumps(liquiditychecks,indent=2)+'\n')
files={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in P.glob('verifier-*') if x.is_file() and x.name!='verifier-file-manifest.json'}
(P/'verifier-file-manifest.json').write_text(json.dumps(dict(status='COMPLETED_SAVED_OUTPUTS_VERIFIED',completed_recipes=recipes,files=files),indent=2)+'\n')
print(json.dumps(dict(completed=recipes,actual_native_risk_orders=len(riskfills),snapshot_rows=len(snapshots),output_hashes=len(files)),indent=2))
