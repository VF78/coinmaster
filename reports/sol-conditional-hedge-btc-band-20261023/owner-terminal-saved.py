from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib
OUT=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/sol-conditional-hedge-btc-band-20261023');END=1788220800000000000
m=json.loads((OUT/'owner-analysis-manifest.json').read_text());g=list(csv.DictReader((OUT/'owner-global-risk.csv').open()));by={x['recipe']:x for x in g};rows=[]
for item in m['inputs']:
    d=json.loads(Path(item['artifact']).read_text());p=d['post_boundary_settlement'];row=by[item['recipe']];fees=sum((D(x['commission']) for x in d['fill_audit'] if int(x['fill_ns'])>=END),D(0));bridge=D(d['terminal_total'])-D(row['end_equity']);row.update(end_equity_basis='PRETERMINAL_LAST_ACCEPTED_NATIVE_SETTLED_RECEIPT_AT_CAUSAL_SOURCE_MARKS',native_TOTAL_after_post_boundary_settlement=d['terminal_total'],observed_equity_to_terminal_cash_bridge=str(bridge),terminal_settlement_csv='owner-terminal-settlement.csv')
    rows.append(dict(recipe=item['recipe'],last_observed_native_equity=row['end_equity'],last_observed_receipt_utc=row['end_receipt_utc'],last_observed_equity_basis=row['end_equity_basis'],native_cash_before_terminal_settlement=p['interval_cash_total_before_settlement'],native_TOTAL_after_settlement=d['terminal_total'],observed_equity_to_terminal_cash_bridge=str(bridge),native_cash_change_during_terminal_settlement=str(D(d['terminal_total'])-D(p['interval_cash_total_before_settlement'])),actual_native_boundary_fill_count=p['fill_count'],actual_native_boundary_fill_fees=str(fees),terminal_boundary=p['boundary_timestamp'],convention=p['convention'],monthly_and_window_values='TRADING_INTERVAL_NATIVE_OBSERVATIONS_PRETERMINAL_SETTLEMENT',bridge_qualification='Native account/observation bridge includes execution-vs-mark basis and fees; not an independent PnL attribution',signed_asset_funding='UNKNOWN'))
for name,data in [('owner-global-risk.csv',g),('owner-terminal-settlement.csv',rows)]:
    p=OUT/name
    with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=sorted({k for x in data for k in x}));w.writeheader();w.writerows(data)
    m['exports'][name]=dict(path=str(p),rows=len(data),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
m['terminal_endpoint_contract']='Risk GLOBAL/window/monthly interval endpoint equities are preterminal native observations. Native TOTAL is post-boundary settled native cash; owner-terminal-settlement.csv explicitly preserves the bridge, native interval cash and actual boundary close fees. No silent equality/substitution.'
(OUT/'owner-analysis-manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
