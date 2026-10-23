import json
from pathlib import Path
from decimal import Decimal as D, ROUND_FLOOR
import pyarrow.parquet as pq
OUT=Path(__file__).resolve().parent
prep=json.loads((OUT/'owner-run-preparation.json').read_text());job=next(x for x in prep['jobs'] if x['recipe']=='SOL')
p=Path(job['data_root'])/'normalized/bybit-SOLUSDT-execution-1m.parquet'
art=next(Path(job['artifact_dir']).glob('*raw-native.json'));raw=json.loads(art.read_text());events=[r for r in raw['next_band_audit'] if r.get('event')=='SB_ADD_ADMISSION']
times=[int(r['timestamp_ns'])//1000000-60000 for r in events]
rows=pq.read_table(p,filters=[('open_time_ms','in',times)]).to_pylist();assert len(rows)==13
lookup={int(r['open_time_ms']):r for r in rows};saved=[]
for e in events:
 r=lookup[int(e['timestamp_ns'])//1000000-60000];quote=(D(r['close'])/D('.01')).to_integral_value(rounding=ROUND_FLOOR)*D('.01')
 post=D(e['equity'])-D(e['requested'])*quote*D(e['sol_fee'])-D(e['btc_reserve'])-(D(e['sol_qty'])+D(e['requested']))*(D(e['sol_atr'])+D(e['sol_fee'])*(D(e['sol_mark'])+D(e['sol_atr'])))
 saved.append(dict(timestamp_ns=e['timestamp_ns'],source_open_time_ms=r['open_time_ms'],source_close=r['close'],executable_quote=str(quote),raw_mark=e['sol_mark'],calculated_post_stress=str(post),saved_post_stress=e['post_stress_equity'],exact_match=post==D(e['post_stress_equity']),budget_denied=e['allowed'] is False))
result=dict(source=str(p),pinned_sha256=job['input_pins']['normalized/bybit-SOLUSDT-execution-1m.parquet'],source_rows_returned=len(rows),causal_mapping='completed bar open_time_ms+60000 gives native quote timestamp_ns',rows=saved,all_exact=all(r['exact_match'] for r in saved),no_engine=True)
(OUT/'verifier-SOL-admission-quotes.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'all_exact':result['all_exact'],'rows':saved},indent=2))
