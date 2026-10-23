import csv,json
from pathlib import Path
from datetime import datetime,timezone
import pyarrow.parquet as pq
R=Path(__file__).parent; OLD=R.parent/'sol-conditional-hedge-btc-band-20261023'; ROOT=Path('/Users/vf/Documents/ChatGPT/Coinmaster');DAY=86400000000000
rows=pq.read_table(ROOT/'runtime/var/data/normalized/bybit-BTCUSDT-daily.parquet').to_pylist();state={};ema=prev=atr=None;trs=[]
for b in rows:
 ns=(b['open_time_ms']+86400000)*1000000;c=float(b['close']);ema=c if ema is None else 2/35*c+33/35*ema
 if prev is not None:
  tr=max(float(b['high'])-float(b['low']),abs(float(b['high'])-prev),abs(float(b['low'])-prev))
  if atr is None:
   trs.append(tr)
   if len(trs)==14:atr=sum(trs)/14
  else:atr=(13*atr+tr)/14
 prev=c;side=1 if c>ema else -1;state[ns]=dict(side=side,ema=ema,atr=atr,close=c)
def ns(x):return int(datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()*1e9)
closed=[r for r in csv.DictReader((R/'owner-closed-bars.csv').open()) if r['symbol']=='BTCUSDT' and int(r['step_ns'])==DAY//6];out=[]
for i,w in enumerate(csv.DictReader((OLD/'owner-B-skip-delay.csv').open()),1):
 latch=ns(w['latch_start_utc']);end=ns(w['actual_next_entry_utc']);count=0;last_side=last_day=None;e4=ep=None;dailylog=[]
 for day,s in state.items():
  if not (latch//DAY*DAY<=day<end):continue
  count=count+1 if last_day is not None and day==last_day+DAY and s['side']==last_side else 1;last_day=day;last_side=s['side'];dist=s['side']*(s['close']-s['ema'])/s['atr'];dailylog.append(dict(day=day,side=s['side'],count=count,distance=dist))
  if ep is None and (dist>=.5 or count>=2 and dist>=.25):ep=day
 for b in closed:
  t=int(b['close_ns']);day=t//DAY*DAY;s=state.get(day)
  if latch<t<end and s and s['atr'] and s['side']*(float(b['close'])-s['ema'])/s['atr']>=.5:e4=t;break
 out.append(dict(wait=i,latch_time=latch,actual_next_entry=end,first_eligible_4h_release=e4,first_EP_release=ep,D1_chain=json.dumps(dailylog),eligibility='SAVED_B_PERMISSION_ONLY_NATIVE_EPISODE_QUOTE_ADMISSION_REVALIDATE',pending_inflight_increases='UNKNOWN_EXACT_CACHE_SNAPSHOT_NOT_EXPORTED'))
with (R/'owner-wait-precheck.csv').open('w',newline='') as f:w=csv.DictWriter(f,list(out[0]));w.writeheader();w.writerows(out)
print('WAIT',len(out),'E4 early',sum(bool(x['first_eligible_4h_release']) for x in out),'EP early',sum(bool(x['first_EP_release']) for x in out))
