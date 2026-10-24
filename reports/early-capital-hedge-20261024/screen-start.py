from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parent;L=R/'screen-ledger.json';j=json.loads(L.read_text());assert j['logical_outcome_screens_started']==0
for name,sha in j['sha256'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==sha,name
A=R.parent/'market-redesign-20261024/native-analysis-R3.json';a=json.loads(A.read_text());d=json.loads((R/'feature-contract-availability.json').read_text());pins={str(A):hashlib.sha256(A.read_bytes()).hexdigest()}
for p,s in d['source_sha256'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==s;pins[p]=s
for p,s in a['input_sha256'].items():
 if p.endswith('fills.csv') or p.endswith('raw-native.json') or p.endswith('settled-receipts.csv.gz'):
  assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==s;pins[p]=s
pins[str(R/'feature-contract-features.csv')]=j['sha256']['feature-contract-features.csv']
j.update(status='OUTCOME_PASS_STARTED_AFTER_HASH_VERIFICATION',outcome_pass_started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),logical_outcome_screens_started=1,outcomes='AUTHORIZED_NEW_LOCAL_LABELS_ONLY',input_sha256=pins)
L.write_text(json.dumps(j,indent=2)+'\n');print('START_LEDGER_WRITTEN; all frozen source/data hashes verified',len(pins))
