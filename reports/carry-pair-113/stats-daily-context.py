import csv,json,pathlib,hashlib
import numpy as np
import pyarrow.parquet as pq
P=pathlib.Path("reports/carry-pair-113");D=86400000
src="runtime/var/data/normalized/bybit-BTCUSDT-daily.parquet"
b=pq.read_table(src,columns=["open_time_ms","high","low","close"],use_threads=False).to_pandas();ts=b.open_time_ms.to_numpy()+D;c=b.close.to_numpy(dtype=float);h=b.high.to_numpy(dtype=float);l=b.low.to_numpy(dtype=float)
def ema(x,n):
 y=x.copy();al=2/(n+1)
 for i in range(1,len(x)):y[i]=al*x[i]+(1-al)*y[i-1]
 return y
def hyst(x):
 y=np.zeros(len(x),bool);state=False
 for i in range(1,len(x)):
  if x[i]==x[i-1]:state=bool(x[i])
  y[i]=state
 return y
e=ema(c,34);tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))));atr=ema(tr,14);side=np.where(c>=e,1,-1);flip=np.r_[0,np.diff(side)!=0];flips=np.array([sum(flip[max(0,i-6):i+1]) for i in range(len(c))]);near=abs(c-e)/atr<=1;slope=abs(e-np.roll(e,3))/atr<=.35
mask=hyst(near&slope);fmask=hyst(flips>=2);rr=list(csv.DictReader(open(P/"stats-native-census.csv")));cc={int(r["ms"]):r for r in csv.DictReader(open("reports/chop-pair-113/stats-coefficients.csv"))}
for r in rr:
 ms=int(r["ms"]);i=np.searchsorted(ts,ms,side="right")-1;assert ts[i]==ms
 r.update(CHOP_raw_flips2_near=bool(flips[i]>=2 and near[i]),completed_flips7=int(flips[i]),distance_ATR=float(abs(c[i]-e[i])/atr[i]),CHOP_near_slope=bool(mask[i]),CHOP_flips2=bool(fmask[i]),daily_EMA34=float(e[i]),daily_ATR14=float(atr[i]),daily_close=float(c[i]),daily_sign=int(side[i]),beta_at_flip=cc[ms]["beta"],rho_squared_at_flip=cc[ms]["rho_squared"])
 # first subsequent completed daily confirmation of opposite sign and first recross toward carried side
 sd=int(r["BTC_side"]);fut=np.arange(i+1,min(i+8,len(ts)));confirm=fut[side[fut]==-sd];recross=fut[side[fut]==sd];off=fut[~mask[fut]]
 for k,z in [("opposite_next_daily_confirm_ms",confirm),("carried_side_daily_recross_ms",recross),("near_slope_first_off_ms",off)]:r[k]=int(ts[z[0]]) if len(z) else ""
with open(P/"stats-opportunities.csv","w") as z:w=csv.DictWriter(z,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
res={"daily_source":src,"daily_sha256":hashlib.sha256(open(src,"rb").read()).hexdigest(),"rules":"PRIMARY fixed before counts: raw>=2signflips among7completedD inclcurrent AND abs(close-EMA34)<=ATR14, immediate currentbar, no hysteresis; other masks sensitivity only. Exact previous fixed EMA34/ATR14 near_slope with2-dayhysteresis; flips2 fixed sensitivity. Completed daily timestamp including signal close. No thresholds selected here.","counts":{}}
for period in ["calibration","later","all"]:
 rs=[r for r in rr if period=="all" or r["period"]==period];res["counts"][period]={}
 for m in ["CHOP_raw_flips2_near","CHOP_near_slope","CHOP_flips2"]:
  a=[r for r in rs if r[m]];res["counts"][period][m]={"BTC_residual":len(a),"original_pair":sum(float(r["SOL_qty"])>0 for r in a),"original_pair_dates":[r["utc"] for r in a if float(r["SOL_qty"])>0]}
(P/"stats-daily-context.json").write_text(json.dumps(res,indent=2)+"\n");print(json.dumps(res,indent=2))
