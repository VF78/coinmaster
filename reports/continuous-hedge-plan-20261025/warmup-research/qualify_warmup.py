"""Offline reproducible qualification; never fetches or modifies original evidence."""
from pathlib import Path
from decimal import Decimal as D,localcontext
import argparse,csv,json,hashlib

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 here=Path(__file__).resolve().parent
 parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=Path('/tmp/cm-warmup-reproduce-20261025'));args=parser.parse_args()
 out=args.output_dir.resolve();assert out!=here,'Do not overwrite original evidence';out.mkdir(parents=True,exist_ok=True)
 raw=here/'bybit-sol-H1-attempt2.raw.json';meta=json.loads((here/'bybit-sol-warmup-attempt2.json').read_text());assert sha(raw)==meta['raw_sha256']
 data=json.loads(raw.read_bytes());assert data['retCode']==0 and data['result']['symbol']=='SOLUSDT' and data['result']['category']=='linear'
 rows=data['result']['list'];times=[int(r[0]) for r in rows];bars=sorted(rows,key=lambda r:int(r[0]));start=1723680000000;stop=1725148800000;H=3600000
 assert len(rows)==408 and len(set(times))==408 and [int(r[0]) for r in bars]==list(range(start,stop,H))
 for r in bars:
  assert len(r)==7
  o,h,l,c,v,t=map(D,r[1:]);assert all(x.is_finite() for x in (o,h,l,c,v,t)) and min(o,h,l,c)>0 and min(v,t)>=0 and l<=min(o,c)<=max(o,c)<=h
  assert int(r[0])%H==0 and int(r[0])+H<=stop
 h4=[]
 for i in range(0,408,4):
  g=bars[i:i+4];t=int(g[0][0]);assert t%(4*H)==0
  h4.append({'start_ms':t,'closed_at_ms':t+4*H,'open':g[0][1],'high':max(D(x[2]) for x in g),'low':min(D(x[3]) for x in g),'close':g[-1][4],'volume':sum(D(x[5]) for x in g),'turnover':sum(D(x[6]) for x in g)})
 assert len(h4)==102
 tr=[];atr=None;ar=[]
 with localcontext() as ctx:
  ctx.prec=50
  for k,b in enumerate(h4):
   previous=D(h4[k-1]['close']) if k else None
   v=b['high']-b['low'] if previous is None else max(b['high']-b['low'],abs(b['high']-previous),abs(b['low']-previous));tr.append(v)
   if k==13:atr=sum(tr,D(0))/D(14)
   elif k>13:atr=(D(13)*atr+v)/D(14)
   assert atr is None or (atr.is_finite() and atr>0)
   ar.append({'closed_at_ms':b['closed_at_ms'],'true_range':v,'wilder_atr14':atr if atr is not None else '', 'valid':int(atr is not None)})
 specs=[('bybit-sol-h1-qualified.csv',['start_ms','open','high','low','close','volume','turnover'],bars),('bybit-sol-h4-qualified.csv',list(h4[0]),[list(b.values()) for b in h4]),('bybit-sol-h4-atr14-research.csv',list(ar[0]),[list(b.values()) for b in ar])]
 results=[]
 for name,header,values in specs:
  target=out/name
  assert target.resolve()!= (here/name).resolve()
  with target.open('w',newline='') as f:w=csv.writer(f);w.writerow(header);w.writerows(values)
  with target.open() as f:new=list(csv.reader(f))
  with (here/name).open() as f:old=list(csv.reader(f))
  assert old[0]==new[0] and len(old)==len(new)
  for rowa,rowb in zip(old[1:],new[1:]):
   assert len(rowa)==len(rowb)
   assert all((a==b=='') or (a!='' and b!='' and D(a)==D(b)) for a,b in zip(rowa,rowb))
  results.append({'file':name,'rows':len(values),'semantic_decimal_equal':True,'byte_identical':sha(target)==sha(here/name),'original_sha256':sha(here/name),'reproduced_sha256':sha(target)})
 receipt={'result':'PASS','script_sha256':sha(Path(__file__).resolve()),'raw_sha256':sha(raw),'output_directory':str(out),'comparisons':results,'original_evidence_written':False,'new_fetches':0,'engines_created':0}
 (out/'reproduction-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
