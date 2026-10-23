"""Validate saved factual arithmetic only. Does not import or run a trading engine."""
from pathlib import Path
from decimal import Decimal, localcontext
import csv, hashlib, json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
checks=[]
def check(name, condition):
    checks.append({'name':name,'pass':bool(condition)})
    if not condition: raise AssertionError(name)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
with localcontext() as ctx:
    ctx.prec=60
    D=Decimal
    rows=list(csv.DictReader((OUT/'experiment-frontier.csv').open()))
    seed=D('10000');s0=D('6077107.23887483');floor=seed+D('.9')*(s0-seed)
    check('profit floor',floor==D('5470396.514987347'))
    check('comparable candidates',len(rows)==15)
    for r in rows:
        total,dd=D(r['TOTAL']),D(r['DD_percent'])
        retention=(total-seed)/(s0-seed)*100
        check(r['id']+' retention',abs(retention-D(r['net_profit_retained_percent']))<D('1e-23'))
        passed=dd<=50 and total>=floor
        check(r['id']+' constrained acceptance',str(passed)==r['passes_50_90'])
        dominators=[q['id'] for q in rows if D(q['TOTAL'])>=total and D(q['DD_percent'])<=dd and (D(q['TOTAL'])>total or D(q['DD_percent'])<dd)]
        check(r['id']+' Pareto membership',str(not dominators)==r['pareto_nondominated'])
        check(r['id']+' dominance exact',set(dominators)==set(filter(None,r['dominated_by'].split(';'))))
    check('no winner',not any(r['passes_50_90']=='True' for r in rows))
    check('frontier',set(r['id'] for r in rows if r['pareto_nondominated']=='True')=={'S0','E4','S'})
    vals={r['id']:D(r['TOTAL']) for r in rows}
    check('E4 remaining profit headroom',vals['E4']-floor==D('161220.844549883'))
    check('E4 Z interaction',vals['XZ']-vals['E4']-vals['Z']+vals['B']==D('1350163.68353756'))
    check('E4 S interaction',vals['XS']-vals['E4']-vals['S']+vals['B']==D('241136.25156338'))
    ep=json.loads((OUT/'drawdown-floor-diagnostics.json').read_text())
    for r in ep['rows']:
        h,w=D(r['peak']),D(r['trough'])
        check('endpoint bridge '+str(r['rank']),h-w==-(D(r['cash_delta'])+D(r['UPnL_delta'])))
        check('endpoint DD '+str(r['rank']),abs((h-w)/h*100-D(r['DD_percent']))<D('1e-23'))
        check('endpoint floor gap '+str(r['rank']),max(D(0),h*D('.5')-w)==D(r['gap_to_50pct_floor_at_same_peak']))
    exact=ROOT/'reports/fast-rnd-20261020/s0-completion.json'
    x=json.loads(exact.read_text())
    check('exact source',x['head']=='75ffc9c69e9d79c4da4cd0614634a3eeba48d716')
    check('S0 archived identity',D(x['terminal_total'])==s0)
    check('S0 active config',x['config_hash']=='22e1eefe8f9c71669e52a8e44b7acbdfd5f177d6ef4ae2118e9df566a05c6edc')
    scope=json.loads((OUT/'scope.json').read_text())
    check('no new economic runs',scope['native_runs_started']==scope['S0_reruns']==0)
    check('no pilot/source changes',scope['pilot_changes']==scope['source_changes']==0)
    calc=json.loads((OUT/'method-calculations.json').read_text())
    check('beta basis gross not net', 'S0_full_SOL_commonfactor_over_gross_reference_BTC_at_entry_reference' in calc and 'S0_full_SOL_commonfactor_over_initial_BTC_if_all_levels_filled' not in calc)
result={'status':'PASS','checks':checks,'count':len(checks),'basis':'saved paths and factual arithmetic; no new portfolio result, no new native engine, no training','inputs':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'experiment-frontier.csv',OUT/'method-calculations.json',OUT/'drawdown-floor-diagnostics.json',exact]},'script_sha256':sha(Path(__file__))}
(OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'count':result['count'],'new_native_runs':0}))
