"""Pure integer lot-invariant proof; no engine, prices, PnL or strategy imports.
Frozen verification domain: u,v=1..16; b=0..32; independent s=0..64.
Proposal frozen before execution: BTC floor unchanged, SOL ceiling uses ceil.
"""
from pathlib import Path
from decimal import Decimal
from math import gcd
import hashlib,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REPORT=ROOT/'runtime/var/research-jobs/b2-f0-paired-prefix-20261024/B2_PAIRED_APPROVED5/result/paired-prefix-B2.json'
EXPECTED='2368406ca61ef8ae4971f4ecaa88dbf22ee99a453df2e88038253e0e92852bb0'

def ceildiv(a,b):return (a+b-1)//b

def verify():
    raw=REPORT.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
    data=json.loads(raw);events=data['paired_prefix_audit']['events']
    first=next(e for e in events if e['event']=='ACTIVATION_SELECTED')
    v=int(Decimal(first['qref'])/Decimal('.001'))
    u=int(Decimal(first['intended_sol'])/Decimal('.1'))
    assert (u,v)==(1817,1037)
    selected=[e for e in events if 1726434480000000000<=int(e['timestamp_ns'])<=1726434600000000000 and e['event'] in ('ACTUAL_FILL','CACHE_POSITION','ACTUAL_BTC_DEBT_OPEN')]
    assert (v*1363)//u==777
    assert (u*777)//v==1361 and (v*1361)//u==776
    assert (u*776)//v==1359 and (v*1359)//u==775
    proposed_s=ceildiv(u*777,v)
    assert proposed_s==1362 and (v*proposed_s)//u>=777
    assert (v*(proposed_s-1))//u<777  # Actual extra one-lot reduction still incurs debt.
    checks=0;old_strict_steps=0
    for U in range(1,17):
      for V in range(1,17):
        for B in range(33):
          S=ceildiv(U*B,V)
          assert U*B<=V*S<U*B+V  # conservative BTC cover; <1 SOL-lot excess.
          assert min(B,(V*S)//U)==B  # correct cap fill creates no new BTC debt.
          old=(V*((U*B)//V))//U
          assert old<=B
          assert (old==B)==((U*B)%V==0)
          old_strict_steps+=old<B
          if B and S:assert (V*(S-1))//U<B
          checks+=1
        for actual_S in range(65):
          B=(V*actual_S)//U
          cap=ceildiv(U*B,V)
          assert cap<=actual_S  # reduction-only; never adds inventory.
          assert min(B,(V*cap)//U)==B
          assert ceildiv(U*min(B,(V*cap)//U),V)==cap  # idempotent mutual reconciliation.
          checks+=1
    out=dict(status='PASS_PURE_INTEGER_INVARIANTS_ONLY',economic_engine_runs=0,
      source_commit='3323f08c57ede411058f93d96acee88928c93481',report_sha256=EXPECTED,
      frozen_choices=dict(u_range=[1,16],v_range=[1,16],btc_lots_range=[0,32],independent_sol_lots_range=[0,64],
      proposal='BTC floor(v*s/u), monotone bmax; BTC-caused SOL cap ceil(u*b/v); exact integer cross-products'),
      checks=checks,old_floor_strict_decrease_states=old_strict_steps,
      actual_first=dict(u=u,v=v,gcd=gcd(u,v),btc_step='.001',sol_step='.1',post_tp_sol_lots=1363,
        old_btc_lots=[777,776,775],old_sol_caps=[1361,1359],proposed_sol_cap_lots=1362,
        proposed_covered_btc_lots=(v*1362)//u,extra_one_sol_lot_reduction_covered_btc=(v*1361)//u),
      first_trace=selected,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      limit='Not an execution, PnL, economic, live safety or approval proof; no product patch or new native run authorized.')
    target=HERE/'approved5-grid-invariant-check.json';target.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ('status','checks','old_floor_strict_decrease_states')}))

if __name__=='__main__':verify()
