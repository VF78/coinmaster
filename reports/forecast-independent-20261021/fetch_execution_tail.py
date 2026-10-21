"""Bounded public-only execution OHLCV tail retrieval; no labels/models."""
import csv,hashlib,json,time,urllib.request,urllib.error,resource
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
START=1788220800000
END=1792540800000
STEP=60000
ROOT=Path('runtime/var/research-datasets/forecast-independent-20261021-v1/execution-tail')
ROOT.mkdir(parents=True,exist_ok=True)
def now():return datetime.now(timezone.utc).isoformat()
def save(path,obj):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(path)
def digest(path):return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
summary={'schema':'coinmaster.forecast.execution-tail.v1','source':'https://api.bybit.com/v5/market/kline','category':'linear','interval':'1','start_ms':START,'end_exclusive_ms':END,'captured_started_at':now(),'symbols':{},'no_models_labels_or_engines':True}
for symbol in ['BTCUSDT','SOLUSDT']:
 directory=ROOT/symbol;directory.mkdir(exist_ok=True);rawdir=directory/'raw';rawdir.mkdir(exist_ok=True)
 checkpoint=directory/'progress.json'
 state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {'symbol':symbol,'start_ms':START,'end_exclusive_ms':END,'next_end_ms':END-1,'pages':[],'errors':[],'completed':False}
 assert state['start_ms']==START and state['end_exclusive_ms']==END and state['symbol']==symbol
 while not state['completed']:
  cursor=state['next_end_ms'];url=f'https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=1&start={START}&end={cursor}&limit=1000'
  for attempt in range(3):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Coinmaster-public-forecast-inventory/1'}),timeout=20) as response:
     status=response.status;body=response.read(2*1024*1024)
    payload=json.loads(body)
    if payload.get('retCode')!=0:raise RuntimeError(f'Bybit retCode={payload.get("retCode")} retMsg={payload.get("retMsg")}')
    rows=payload.get('result',{}).get('list',[])
    if payload['result'].get('symbol')!=symbol or payload['result'].get('category')!='linear':raise RuntimeError('SOURCE_IDENTITY_MISMATCH')
    break
   except (urllib.error.URLError,TimeoutError) as error:
    transient=not isinstance(error,urllib.error.HTTPError) or error.code in (408,429,500,502,503,504)
    state['errors'].append({'at':now(),'url':url,'attempt':attempt+1,'error':str(error),'transient':transient});save(checkpoint,state)
    if not transient or attempt==2:raise
    time.sleep(2**attempt)
  if not rows:raise RuntimeError('EMPTY_PAGE_BEFORE_REQUESTED_START')
  timestamps=[int(r[0]) for r in rows]
  if len(set(timestamps))!=len(timestamps) or timestamps!=sorted(timestamps,reverse=True):raise RuntimeError('INVALID_PAGE_ORDER_OR_DUPLICATES')
  if max(timestamps)>cursor or min(timestamps)<START or any(t%STEP for t in timestamps):raise RuntimeError('PAGE_OUT_OF_RANGE_OR_GRID')
  filename=f'{len(state["pages"]):04d}-{hashlib.sha256(body).hexdigest()}.json';path=rawdir/filename
  if path.exists() and path.read_bytes()!=body:raise RuntimeError('RAW_HASH_COLLISION')
  path.write_bytes(body)
  state['pages'].append({'path':str(path),'sha256':digest(path),'url':url,'http_status':status,'received_at':now(),'rows':len(rows),'min_open_ms':min(timestamps),'max_open_ms':max(timestamps),'server_time_ms':payload.get('time')})
  oldest=min(timestamps)
  if oldest>=cursor:raise RuntimeError('NONPROGRESSING_PAGE')
  state['next_end_ms']=oldest-1;state['completed']=oldest<=START;save(checkpoint,state)
  if len(state['pages'])%20==0 or state['completed']:print(json.dumps({'symbol':symbol,'pages':len(state['pages']),'completed':state['completed']}),flush=True)
  time.sleep(.15)
 rows_by_time={};duplicates=0
 for page in state['pages']:
  path=Path(page['path'])
  if digest(path)!=page['sha256']:raise RuntimeError('RAW_HASH_DRIFT')
  for row in json.loads(path.read_bytes())['result']['list']:
   timestamp=int(row[0])
   if timestamp in rows_by_time:duplicates+=1
   rows_by_time[timestamp]=row
 if duplicates:raise RuntimeError('DUPLICATE_MINUTES')
 expected=(END-START)//STEP
 if len(rows_by_time)!=expected:raise RuntimeError(f'ROW_COUNT_MISMATCH {len(rows_by_time)} expected {expected}')
 output=directory/'execution-1m.csv'
 with output.open('w',newline='') as stream:
  writer=csv.writer(stream);writer.writerow(['open_time_ms','open','high','low','close','volume','turnover'])
  for timestamp in range(START,END,STEP):
   if timestamp not in rows_by_time:raise RuntimeError(f'MISSING_MINUTE {timestamp}')
   row=rows_by_time[timestamp]
   if len(row)!=7:raise RuntimeError('BAD_FIELD_COUNT')
   o,h,l,c,v,turn=map(Decimal,row[1:])
   if not all(x.is_finite() for x in (o,h,l,c,v,turn)) or min(o,h,l,c)<=0 or min(v,turn)<0 or l>min(o,c) or h<max(o,c) or l>h:raise RuntimeError(f'INVALID_OHLCV {timestamp}')
   if timestamp+STEP>END:raise RuntimeError('UNCLOSED_BAR')
   writer.writerow([timestamp,*row[1:]])
 summary['symbols'][symbol]={'status':'VERIFIED_COMPLETE','rows':expected,'pages':len(state['pages']),'first_open_ms':START,'last_open_ms':END-STEP,'available_last_close_ms':END,'missing':0,'duplicates':duplicates,'alignment_errors':0,'normalized_csv':str(output),'normalized_sha256':digest(output),'bytes':output.stat().st_size,'progress_sha256':digest(checkpoint),'response_errors':state['errors']}
 save(ROOT/'manifest.json',summary)
 del rows_by_time
summary['completed_at']=now();summary['source_script_sha256']=digest(Path(__file__));save(ROOT/'manifest.json',summary)
print(json.dumps({'status':'COMPLETE','manifest':str(ROOT/'manifest.json'),'sha256':digest(ROOT/'manifest.json'),'symbols':summary['symbols']}),flush=True)
