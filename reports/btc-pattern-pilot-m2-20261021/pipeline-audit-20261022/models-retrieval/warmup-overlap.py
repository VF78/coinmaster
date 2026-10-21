"""Count baseline saved neighbors overlapping the 20x4h engineered-volume warmup."""
import json,time
from pathlib import Path
import pandas as pd
HOUR=3600000
out=Path(__file__).parent;root=out.parents[3];start=time.monotonic()
p=root/'reports/btc-pattern-pilot-m2-20261021/neighbors.parquet';df=pd.read_parquet(p)
rows=[];examples=[]
for (fold,method),g in df.groupby(['fold','method']):
 hit=g.neighbor_label_end>g.query_input_start-80*HOUR
 rows.append(dict(fold=fold,method=method,neighbor_rows=len(g),affected_neighbor_rows=int(hit.sum()),queries=g['query'].nunique(),affected_queries=g.loc[hit,'query'].nunique(),max_overlap_hours=float(((g.neighbor_label_end-(g.query_input_start-80*HOUR))/HOUR)[hit].max()) if hit.any() else 0,uses_engineered_80h_dependency=method in ['TCN-knn','numeric-knn']))
 examples.append(g.loc[hit,['fold','method','query','neighbor','query_origin','neighbor_label_end','query_input_start']].head(1))
pd.concat(examples).to_csv(out/'overlap-examples.csv',index=False)
result=dict(source=str(p.relative_to(root)),source_rows=len(df),strict_extra_warmup_hours=80,counts=rows,execution=dict(wall_seconds=time.monotonic()-start,fits=0,market_predictions=0))
(out/'warmup-overlap.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
