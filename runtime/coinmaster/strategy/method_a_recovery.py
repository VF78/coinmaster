"""Engine-free exact integer parametric recovery helper.

Callbacks must implement the declared raw affine screening law, in a stable
scenario/constraint order. Native Money rounding requires extra supplied cuts.
No engine/account/order imports and no economic simulation.
"""
from fractions import Fraction as F
from itertools import combinations

def floor(value):
    value=F(value)
    return value.numerator//value.denominator

def ceil(value):return -floor(-F(value))

def val(line,d):return line[0]*d+line[1]

def _fit(left,right,lo,hi):
    left,right=F(left),F(right)
    slope=(right-left)/(hi-lo) if hi!=lo else F(0)
    return slope,left-slope*lo

def _intersect(interval,line,strict):
    """Intersect integer interval with a*d+b <= 0 (or < 0)."""
    lo,hi=interval;a,b=line
    if not a:
        return None if (b>=0 if strict else b>0) else interval
    root=-b/a
    if a>0:hi=min(hi,ceil(root)-1 if strict else floor(root))
    else:lo=max(lo,floor(root)+1 if strict else ceil(root))
    return None if lo>hi else (lo,hi)

def recovery_candidates(*, h, opening, old_reductions, proposed_cost,
                        fixed_q_points, route_constraints, objective_values,
                        initial_deficit, legal_intervals=None, extra_d_cuts=()):
    """Return (all route/improvement-feasible integer intervals, optimum candidates).

    h/opening: nonnegative integer lots. old_reductions: (capacity,cost/lot).
    fixed_q_points: every fixed tier/MMzero integer-neighbor q point, at all
      scenarios for the selected leg. Include any further piecewise-law cuts.
    route_constraints(d,q): stable tuple of (value, strict), requiring value<=0
      or value<0. Enumerate ALL scenarios and ALL fixed-other-leg candidate
      points inside this callback. E.g. deficit-initial_deficit, strict=False.
    objective_values(d): stable tuple of every full-step deficit line value;
      objective=max(values). Full-step strict improvement is also enforced.
    legal_intervals: exact native-normalized legal capacities; default [0,h].

    On each returned cell, callbacks must be affine per the moving-cut theorem.
    Tier boundaries must be included in fixed_q_points. Existing old/new
    generation-max capacity changes need extra_d_cuts or an extended model.
    """
    if type(h)is not int or type(opening)is not int or min(h,opening)<0:
        raise ValueError('integer nonnegative h/opening required')
    if any(type(n)is not int for n,c in old_reductions):
        raise ValueError('old capacity must be exact integer lots')
    old=[(n,F(c),False) for n,c in old_reductions]
    if any(n<0 or c<0 for n,c,_ in old) or F(proposed_cost)<0:
        raise ValueError('nonnegative capacities/costs required')
    R=sum(n for n,_,_ in old)
    qlines={(0,0),(0,h+opening),(-1,h-R),(-1,h)}
    cumulative=epsilon=0
    for n,c,new in sorted(old+[(0,F(proposed_cost),True)],key=lambda x:-x[1]):
        cumulative+=n;epsilon+=int(new)
        for neighbor in (-1,0,1):
            qlines.add((-epsilon,h+opening-cumulative+neighbor))
    for q in fixed_q_points:
        if type(q)is not int:raise ValueError('fixed q point must be exact integer lot')
        qlines.add((0,q))
    special={0,h}
    for left,right in combinations(qlines,2):
        if left[0]==right[0]:continue
        crossing=F(right[1]-left[1],left[0]-right[0])
        special.update(d for d in (floor(crossing),ceil(crossing)) if 0<=d<=h)
    for cut in extra_d_cuts:
        special.update(d for d in (floor(cut),ceil(cut)) if 0<=d<=h)
    legal_intervals=[(0,h)] if legal_intervals is None else legal_intervals
    for lo,hi in legal_intervals:
        special.update(d for d in (lo,hi) if 0<=d<=h)
    ordered=sorted(special)
    cells=[(d,d) for d in ordered]
    cells.extend((a+1,b-1) for a,b in zip(ordered,ordered[1:]) if a+1<=b-1)
    feasible=[];candidates=set()
    for cell_lo,cell_hi in cells:
        for legal_lo,legal_hi in legal_intervals:
            lo,hi=max(cell_lo,legal_lo,0),min(cell_hi,legal_hi,h)
            if lo>hi:continue
            interval=(lo,hi)
            valid=[line for line in qlines if max(0,h-R-lo)<=val(line,lo)<=h+opening]
            for qline in valid:
                left=tuple(route_constraints(lo,val(qline,lo)))
                right=tuple(route_constraints(hi,val(qline,hi)))
                if len(left)!=len(right):raise ValueError('unstable route constraints')
                for (a,strict_a),(b,strict_b) in zip(left,right):
                    if strict_a!=strict_b:raise ValueError('unstable constraint strictness')
                    if interval is not None:
                        interval=_intersect(interval,_fit(a,b,lo,hi),strict_a)
            if interval is None:continue
            left,right=tuple(objective_values(lo)),tuple(objective_values(hi))
            if not left or len(left)!=len(right):raise ValueError('unstable/empty objective')
            lines=[_fit(a,b,lo,hi) for a,b in zip(left,right)]
            for a,b in lines:
                if interval is not None:
                    interval=_intersect(interval,(a,b-F(initial_deficit)),True)
            if interval is None:continue
            a,b=interval;feasible.append(interval);candidates.update(interval)
            for left,right in combinations(lines,2):
                if left[0]==right[0]:continue
                crossing=(right[1]-left[1])/(left[0]-right[0])
                candidates.update(d for d in (floor(crossing),ceil(crossing)) if a<=d<=b)
    return tuple(sorted(set(feasible))),tuple(sorted(candidates))
