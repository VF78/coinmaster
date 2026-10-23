"""270 fixed prior-day math-only beta probe; no native engine imports."""
import json,math,sys,hashlib
from pathlib import Path
import pyarrow.parquet as pq
OUT=Path('/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/sol-conditional-hedge-btc-band-20261023')
DATA=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/data/normalized')
r=json.loads(Path('/private/tmp/btc-audit-exact-s0-direction.json').read_text());p=r['split_cover_audit']['parents'][2]
cut=int(p['start_ns'])//86_400_000_000_000*86_400_000_000_000
closes=[]
for asset in ['BTCUSDT','SOLUSDT']:
 rows=pq.read_table(DATA/('bybit-'+asset+'-daily.parquet'),columns=['open_time_ms','close']).to_pylist()
 prior=[x for x in rows if (int(x['open_time_ms'])+86400000)*1000000<=cut][-271:]
 assert len(prior)==271
 closes.append([float(x['close']) for x in prior])
ratios=[[closes[1][i]/closes[1][i-1],closes[0][i]/closes[0][i-1]] for i in range(1,271)]
x={'ratios':ratios,'gross_qty':p['planref_v1_gross_reference_qty'],'blended':float(p['planref_v1_actual_blended_vwap']),'cut_ns':cut}
(OUT/'verifier-float-input.json').write_text(json.dumps(x)+'\n')
rs=[(math.log(a),math.log(b)) for a,b in ratios];sol=[a for a,b in rs];btc=[b for a,b in rs]
ms,mb=sum(sol)/270,sum(btc)/270;variance=sum((v-mb)**2 for v in btc)/270;cov=sum((s-ms)*(b-mb) for s,b in zip(sol,btc))/270;beta=cov/variance
h=x['gross_qty']*x['blended']/beta
result={'python':sys.version,'platform':sys.platform,'logs_hex':[[a.hex(),b.hex()] for a,b in rs],'means_hex':[ms.hex(),mb.hex()],'variance_hex':variance.hex(),'covariance_hex':cov.hex(),'beta':beta,'beta_hex':beta.hex(),'h':h,'h_hex':h.hex()}
(OUT/'verifier-float-mac.json').write_text(json.dumps(result,indent=2)+'\n')
print({k:v for k,v in result.items() if k!='logs_hex'})
