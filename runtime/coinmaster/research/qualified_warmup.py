"""Separate causal ATR feed from pinned genuine H1 warmup and frozen M1.

Only three ATR columns change. No BTC signals, sizing, funding or old inputs mutate.
Nominal close timestamps do not establish historical publication latency.
"""
from pathlib import Path
from decimal import Decimal as D, localcontext
import csv
import hashlib
import json

PINS={
 "raw":"2afa407a476e5b52ea6b1296f39be5f941445d07a586ad4e2f6ad190fc9204c0",
 "h1":"fea6a295447c317f2e665cbe77aba135ba99daefc5fb05957cf44821edaa1b72",
 "h4":"8c414684e54bb834b43e187c7acd5332df50b21835749d6e5e17220ccfc9f991",
 "stitch":"1ff950b6d0a34377ec4efca19d24db6854a36d8b58c5ab4181a7d3c27fb78fc2",
 "builder":"47704f6ca1a998ef464ba7b0237d5e32d2330f92702d3c05d00df426a0b34cf3",
 "m1":"fd5392f14c42599b54723c5a257a22b4d35729366f9b4ff76033998a6cb655b8",
 "old_feed":"2fcd030c495f15a28ff4ff2ef6d931a018e5a2dd9cf142a56ac6582f941734e1",
}
HOUR_MS=3600000
H4_MS=4*HOUR_MS
MINUTE_NS=60000000000

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):
    with Path(path).open(newline="") as f: return list(csv.DictReader(f))

def check_bar(row):
    values={k:D(str(row[k])) for k in ("open","high","low","close")}
    if not all(x.is_finite() and x>0 for x in values.values()) or not values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']:
        raise ValueError("WARMUP_NONFINITE_OR_INVALID_OHLC")
    return values

def aggregate(source, step_ms, count):
    if len(source)%count: raise ValueError("WARMUP_INCOMPLETE_BAR")
    previous=None; result=[]
    for row in source:
        t=int(row['open_time_ms']);check_bar(row)
        if t%step_ms or previous is not None and t!=previous+step_ms:
            raise ValueError("WARMUP_GAP_DUPLICATE_OR_ALIGNMENT")
        previous=t
    for i in range(0,len(source),count):
        group=source[i:i+count];t=int(group[0]['open_time_ms'])
        if t%H4_MS: raise ValueError("WARMUP_H4_ALIGNMENT")
        result.append(dict(start_ms=t,closed_at_ms=t+H4_MS,open=D(str(group[0]['open'])),high=max(D(str(r['high'])) for r in group),low=min(D(str(r['low'])) for r in group),close=D(str(group[-1]['close']))))
    return result

def atr_rows(bars):
    result=[];trs=[];previous=None;atr=None;last=None
    with localcontext() as ctx:
        ctx.prec=50
        for bar in bars:
            v=check_bar(bar);end=int(bar['closed_at_ms'])
            if end%H4_MS or last is not None and end!=last+H4_MS:
                raise ValueError("WARMUP_H4_GAP_DUPLICATE_OR_FUTURE")
            tr=v['high']-v['low'] if previous is None else max(v['high']-v['low'],abs(v['high']-previous),abs(v['low']-previous))
            trs.append(tr)
            if len(trs)==14: atr=sum(trs,D(0))/D(14)
            elif len(trs)>14: atr=(13*atr+tr)/14
            result.append({**bar,'true_range':tr,'atr14':atr});previous=v['close'];last=end
    return result

def build_qualified_feed(paths, output):
    """paths includes every pinned prerequisite; never downloads or runs an engine."""
    pins={k:sha(paths[k]) for k in PINS}
    if pins!=PINS: raise ValueError("QUALIFIED_WARMUP_INPUT_PIN_MISMATCH")
    h1=rows(paths['h1'])
    if len(h1)!=408: raise ValueError("EXACT_408_H1_REQUIRED")
    warm=aggregate([dict(open_time_ms=r['start_ms'],**{k:r[k] for k in ('open','high','low','close')}) for r in h1],HOUR_MS,4)
    qualified=rows(paths['h4'])
    fields=('start_ms','closed_at_ms','open','high','low','close')
    if len(warm)!=102 or any(any(D(str(a[k]))!=D(b[k]) for k in fields) for a,b in zip(warm,qualified)):
        raise ValueError("H1_TO_QUALIFIED_H4_MISMATCH")
    import pyarrow.parquet as pq
    m1=pq.read_table(paths['m1'],columns=['open_time_ms','open','high','low','close']).to_pylist()
    continuation=aggregate(m1,60000,240)
    stitched=atr_rows(warm+continuation)
    proof=rows(paths['stitch'])
    if len(proof)!=109 or any(any(D(str(a[k]))!=D(b[k]) for k in fields+('true_range',) if b[k]) or (a['atr14'] is None)!=(not b['atr14']) or b['atr14'] and a['atr14']!=D(b['atr14']) for a,b in zip(stitched,proof)):
        raise ValueError("QUALIFIED_109_H4_STITCH_MISMATCH")
    old=rows(paths['old_feed']);updated=[]
    lookup={int(r['closed_at_ms'])*1000000:r for r in stitched}
    if len(old)!=len(continuation): raise ValueError("FEED_H4_COVERAGE_MISMATCH")
    for row,bar in zip(old,continuation):
        t=int(row['decision_ns'])
        if t!=int(bar['closed_at_ms'])*1000000 or D(row['sol_close'])!=bar['close']:
            raise ValueError("FEED_M1_H4_CLOCK_OR_CLOSE_MISMATCH")
        atr=lookup[t]['atr14']
        updated.append({**row,'sol_atr_h4_14':str(atr),'sol_atr_valid':'1','atr_last_h4_end_ns':str(t)})
    output=Path(output)
    if output.exists(): raise ValueError("NEW_QUALIFIED_FEED_PATH_REQUIRED")
    with output.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(old[0]),lineterminator='\n');writer.writeheader();writer.writerows(updated)
    return dict(status='QUALIFIED_SEPARATE_FEED',rows=len(updated),warmup_h1=408,warmup_h4=102,stitch_h4=109,input_pins=pins,new_feed_sha256=sha(output),old_feed_unchanged=sha(paths['old_feed'])==PINS['old_feed'],changed_columns=['sol_atr_h4_14','sol_atr_valid','atr_last_h4_end_ns'],sep2_04_atr=str(lookup[1725249600000000000]['atr14']),clock='available=t/ATRend=t/ordernotbefore=t+60s',publication_latency='UNKNOWN',engines_created=0)

def load_qualified_feed(path,digest,start_ns,end_ns):
    from coinmaster.research.paired_signal_feed import load_paired_signal_feed,H4
    selected=load_paired_signal_feed(Path(path),digest,start_ns,end_ns)
    expected=((start_ns+H4-1)//H4)*H4
    if selected[0].decision_ns!=expected or selected[-1].decision_ns!=((end_ns-1)//H4)*H4:
        raise ValueError("QUALIFIED_FEED_MISSING_BOUNDARY_H4")
    for row in selected:
        if not all(x.is_finite() and x>0 for x in (row.btc_close,row.sol_close)) or not row.valid:
            raise ValueError("QUALIFIED_FEED_NO_ADMISSION_INVALID_OR_MISSING_DATA")
    return selected
