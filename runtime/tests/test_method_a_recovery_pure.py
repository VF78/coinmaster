from fractions import Fraction as F
from itertools import combinations
from random import Random
from coinmaster.strategy.method_a_recovery import recovery_candidates

rng=Random(271027)

def floor(x): return x.numerator//x.denominator
def ceil(x): return -floor(-x)
def line_value(line,d): return line[0]*d+line[1]
def fit(fun,lo,hi):
    a=(fun(hi)-fun(lo))/(hi-lo) if hi!=lo else F(0)
    return a,fun(lo)-a*lo

def tier_mm(q,tiers):
    for cap,rate,ded in tiers:
        if q<=cap: return max(F(0),rate*q-ded)
    raise ValueError('unknown tier')

def cost(q,d,h,O,old,cp):
    reductions=old+[(d,cp)]
    r=min(sum(n for n,c in reductions),h+O-q)
    result=F(0)
    for n,c in sorted(reductions,key=lambda x:-x[1]):
        take=min(r,n);result+=take*c;r-=take
    return result

def intersect(bounds,line,strict=False):
    lo,hi=bounds;a,b=line
    if a==0: return None if (b>=0 if strict else b>0) else bounds
    root=-b/a
    if a>0: hi=min(hi,ceil(root)-1 if strict else floor(root))
    else: lo=max(lo,floor(root)+1 if strict else ceil(root))
    return None if lo>hi else (lo,hi)

examples=[]; nonempty=0
for case in range(500):
    h=rng.randrange(1,16);O=rng.randrange(3)
    old=[(rng.randrange(4),F(rng.randrange(1,8),10)) for _ in range(2)]
    cp=F(rng.randrange(1,8),10);R0=sum(n for n,c in old)
    cap=F(rng.randrange(1,2*(h+O)+1),2)
    tiers=[(cap,F(rng.randrange(1,7),10),F(rng.randrange(4),10)),
           (F(h+O+1),F(rng.randrange(1,7),10),F(rng.randrange(4),10))]
    scenarios=[(F(rng.randrange(-20,21),10),F(rng.randrange(-10,11),10)) for _ in range(5)]
    def state_line(q,scenario):
        a,b=scenario
        return a*q+b+tier_mm(q,tiers)
    def full(d):return max(state_line(h-d,s)+cp*d for s in scenarios)
    baseline=full(0)
    def route(d):
        return max(state_line(q,s)+cost(q,d,h,O,old,cp)
                   for q in range(max(0,h-R0-d),h+O+1) for s in scenarios)
    feasible=[d for d in range(h+1) if route(d)<=baseline and full(d)<baseline]
    brute=min(feasible,key=lambda d:(full(d),d)) if feasible else None

    qlines={(0,0),(0,h+O),(-1,h-R0),(-1,h)}
    cumulative=0;epsilon=0
    # The proposed CID's sorted place is fixed by cp. Ties have no cost effect.
    sorted_reds=sorted([(n,c,False) for n,c in old]+[(0,cp,True)],key=lambda x:-x[1])
    for n,c,proposed in sorted_reds:
        cumulative+=n;epsilon+=int(proposed)
        for offset in (-1,0,1):qlines.add((-epsilon,h+O-cumulative+offset))
    for c,rate,ded in tiers:
        for cut in (c,ded/rate):
            for q in (floor(cut)-1,floor(cut),ceil(cut),ceil(cut)+1):qlines.add((0,q))
    special={0,h}
    for left,right in combinations(qlines,2):
        if left[0]==right[0]:continue
        crossing=F(right[1]-left[1],left[0]-right[0])
        for d in (floor(crossing),ceil(crossing)):
            if 0<=d<=h:special.add(d)
    ordered=sorted(special);cells=[(d,d) for d in ordered]
    cells += [(a+1,b-1) for a,b in zip(ordered,ordered[1:]) if a+1<=b-1]
    compressed_feasible=set();candidates=set()
    for lo,hi in cells:
        valid=[qline for qline in qlines
               if max(0,h-R0-lo)<=line_value(qline,lo)<=h+O]
        bounds=(lo,hi)
        route_lines=[]
        for qline in valid:
            for s in scenarios:
                fun=lambda d:state_line(line_value(qline,d),s)+cost(line_value(qline,d),d,h,O,old,cp)
                affine=fit(fun,lo,hi)
                assert all(line_value(affine,d)==fun(d) for d in range(lo,hi+1))
                route_lines.append(affine)
                if bounds is not None:bounds=intersect(bounds,(affine[0],affine[1]-baseline))
        if bounds is None:continue
        # Full-step objective is max affine lines on this same cell.
        full_lines=[fit(lambda d:state_line(h-d,s)+cp*d,lo,hi) for s in scenarios]
        bounds_full=bounds
        for a,b in full_lines:
            if bounds_full is not None:bounds_full=intersect(bounds_full,(a,b-baseline),strict=True)
        if bounds_full is None:continue
        a,b=bounds_full
        compressed_feasible.update(range(a,b+1))
        candidates.update((a,b))
        for left,right in combinations(full_lines,2):
            if left[0]==right[0]:continue
            crossing=(right[1]-left[1])/(left[0]-right[0])
            for d in (floor(crossing),ceil(crossing)):
                if a<=d<=b:candidates.add(d)
    assert compressed_feasible==set(feasible),(case,compressed_feasible,feasible)
    compressed=min(candidates,key=lambda d:(full(d),d)) if candidates else None
    assert compressed==brute,(case,compressed,brute)
    fixed=[]
    for c,rate,ded in tiers:
        for cut in (c,ded/rate):
            fixed.extend((floor(cut)-1,floor(cut),ceil(cut),ceil(cut)+1))
    helper_intervals,helper_candidates=recovery_candidates(
        h=h,opening=O,old_reductions=old,proposed_cost=cp,fixed_q_points=fixed,
        route_constraints=lambda d,q:tuple((state_line(q,s)+cost(q,d,h,O,old,cp)-baseline,False) for s in scenarios),
        objective_values=lambda d:tuple(state_line(h-d,s)+cp*d for s in scenarios),
        initial_deficit=baseline)
    assert {d for a,b in helper_intervals for d in range(a,b+1)}==set(feasible)
    helper_best=min(helper_candidates,key=lambda d:(full(d),d)) if helper_candidates else None
    assert helper_best==brute,(case,helper_best,brute)
    nonempty+=brute is not None
    if brute is not None and 0<brute<h and len(examples)<3:
        examples.append((case,h,brute,str(full(brute)),str(baseline)))
print(f'PASS: 500 exact one-leg recovery searches vs every capacity and every partial fill; {nonempty} nonempty; arbitrary tier jumps and heterogeneous CID costs')
print('Interior examples (case,held,optimal_reduction,full_deficit,initial_deficit):',examples)
