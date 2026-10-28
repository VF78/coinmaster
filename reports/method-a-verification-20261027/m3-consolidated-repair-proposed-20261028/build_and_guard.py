"""Bounded stdlib input/diff/Decimal guards only; no strategy or engine imports."""
import copy, hashlib, json
from decimal import Decimal as D
from pathlib import Path
ROOT=Path('/private/tmp/cm_m3_repair_proposal')
SOURCE=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/method-a-verification-20261027/source-m3-6591609/reports/method-a-verification-20261027/m3-candidate/M3_DATA_PROPOSED.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(SOURCE)=='ae29a508bd34821b7d909ea07d40e22260290eb889422fcd72f4377de647d0fc'
old=json.loads(SOURCE.read_text()); new=copy.deepcopy(old)
patch=[]
for ns,field,value in [(66000000000,'bid_depth','116.874'),(67000000000,'bid_depth','116.251'),(72500000000,'ask_depth','.2'),(73000000000,'ask_depth','.2')]:
 i=next(i for i,r in enumerate(new['rows']) if r['ns']==ns); q=new['rows'][i]['quotes'][0]
 patch.append({'op':'replace','path':f'/rows/{i}/quotes/0/{field}','old':q[field],'value':value,'ns':ns}); q[field]=value
idx=next(i for i,r in enumerate(new['rows']) if r['ns']==68000000000)
quote={'asset':'BTC','bid':'107','ask':'107','bid_depth':'116.251','ask_depth':'1000'}
new['rows'][idx]['quotes'].insert(0,quote)
patch.append({'op':'add','path':f'/rows/{idx}/quotes/0','value':quote,'ns':68000000000,'reason':'Explicit retained-liquidity iteration before SOL CAP sizing; not a reset.'})
# Exact reversible input-diff guard. Preserves every nonpatched field, price, fee declaration, phase and witness.
reversed_new=copy.deepcopy(new); reversed_new['rows'][idx]['quotes'].pop(0)
for p in patch[:4]:
 _,_,i,_,j,key=p['path'].split('/'); reversed_new['rows'][int(i)]['quotes'][int(j)][key]=p['old']
assert reversed_new==old
count=lambda c:sum(2*bool(r.get('marks'))+2*('daily_session'in r)+('h4_btc_close'in r)+len(r.get('quotes',[])) for r in c['rows'])
assert count(old)==139 and count(new)==140
assert sum(len(r['quotes']) for r in old['rows'])==56 and sum(len(r['quotes']) for r in new['rows'])==57
# Arithmetic constraints, not matching/strategy simulation.
assert D('116.875')-D('116.874')==D('.001')
assert D('116.251')-D('.001')==D('116.250')
assert D('550')-D('116.875')-D('116.875')-D('116.250')==D('200')
assert D('210.9')-D('10')-D('68')==D('132.9')
assert D('132.9')-D('132.3')==D('.6')
assert D('.6')-D('.1')==D('.5')
assert D('.2')==D('.1')+D('.1') and D('.5')-D('.2')==D('.3')
assert 72000000000<72500000000<=73000000000<74000000000
assert 74100000000<75600000000<76500000000
assert D('473.439')==D('236.719')+D('236.720')
assert D('196.4')-D('.1')==D('196.3')
for r in new['rows']:
 for q in r['quotes']:
  for k in ('bid','ask','bid_depth','ask_depth'):assert D(q[k]).is_finite() and D(q[k])>0
  assert D(q['bid'])<=D(q['ask'])
  step=D('.001') if q['asset']=='BTC' else D('.1')
  assert all(D(q[k])%step==0 for k in ('bid_depth','ask_depth'))
(ROOT/'M3_DATA_CANDIDATE.json').write_text(json.dumps(new,indent=2)+'\n')
(ROOT/'PATCH.json').write_text(json.dumps({'source_sha256':sha(SOURCE),'patch':patch,'candidate_sha256':sha(ROOT/'M3_DATA_CANDIDATE.json'),'status':'PROPOSAL_ONLY_NATIVE_UNPROVEN_NO_RETRY_AUTHORITY'},indent=2)+'\n')
# Exhaustive static quote-side lookup: reports previous same-price advertised size; never computes fills.
coverage=[]; seen={}; qi=0; inputs=0
for r in old['rows']:
 inputs+=2*bool(r.get('marks'))+2*('daily_session'in r)+('h4_btc_close'in r)
 for q in r['quotes']:
  qi+=1;inputs+=1;sideinfo={}
  for side,depth in [('bid','bid_depth'),('ask','ask_depth')]:
   key=(q['asset'],side,q[side]);prev=seen.get(key)
   sideinfo[side]={'price':q[side],'depth':q[depth],'previous_same_price':prev,'same_size_as_previous_at_price':prev is not None and D(prev['depth'])==D(q[depth]),'fill_claim':'NONE_STATIC_INPUT_COVERAGE'}
   seen[key]={'quote_ordinal':qi,'ns':r['ns'],'depth':q[depth]}
  coverage.append({'quote_ordinal':qi,'public_input_ordinal':inputs,'ns':r['ns'],'phase':r['phase'],'asset':q['asset'],'sides':sideinfo})
assert len(coverage)==56 and inputs==139
(ROOT/'INPUT_COVERAGE.json').write_text(json.dumps({'rows':39,'quotes':56,'public_inputs':139,'quote_side_records':112,'note':'All original inputs counted by source builder schema:78 marks+4 daily+1 H4+56 quotes; static quote-side coverage does not establish strategy commands/fills.','quotes_audited':coverage},indent=2)+'\n')
files={name:sha(ROOT/name) for name in ['M3_DATA_CANDIDATE.json','PATCH.json','INPUT_COVERAGE.json']}
(ROOT/'GUARD_RESULT.json').write_text(json.dumps({'status':'PASS_PURE_INPUT_AND_ARITHMETIC_GUARDS_ONLY','native_constructors':0,'engine_runs':0,'product_changes':0,'source_unchanged':sha(SOURCE),'candidate_public_inputs':140,'candidate_quotes':57,'files':files},indent=2)+'\n')
print(json.dumps(files,indent=2))
