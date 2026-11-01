from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as N
import ast,json,hashlib,importlib.util,sys
P=Path(__file__).resolve().parents[1];R=P/'SOL_REVIEW';newroot=R/'AUDIT_DEFER_SOURCE_7ca19646/runtime';oldroot=R/'V1_JOINT_SOURCE_c4118505/runtime';full=P/'MAC_PREP/frozen-cm2-c4118505/runtime';receipt=json.loads((R/'AUDIT_DEFER_7ca19646_RECEIPT.json').read_text());proof=[]
def check(name,c):
 if not c:raise ValueError(name)
 proof.append({'case':name,'passed':True})
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for x in receipt['files']:check('HASH:'+x['path'],sha(newroot/x['path'].removeprefix('runtime/'))==x['sha256'])
def source(p):
 text=p.read_text();tree=ast.parse(text);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CM2Strategy');fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_native_btc_capital');return tree,cls,fn
a,ac,af=source(oldroot/'coinmaster/strategy/cm2_native.py');b,bc,bf=source(newroot/'coinmaster/strategy/cm2_native.py');bc.body[bc.body.index(bf)]=af;check('ENTIRE_ACTOR_AST_IDENTICAL_EXCEPT_ONE_METHOD',ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False))
def result(f):return next(n.value for n in f.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='result' for x in n.targets))
x,y=result(af),result(bf);check('ALL_NONAUDIT_RETURN_FIELDS_AST_IDENTICAL',{k.arg:ast.dump(k.value,include_attributes=False) for k in x.keywords if k.arg!='btc_attribution_audit'}=={k.arg:ast.dump(k.value,include_attributes=False) for k in y.keywords if k.arg!='btc_attribution_audit'})
check('ALL_RAISED_KNOWNNESS_GUARDS_AST_IDENTICAL',[ast.dump(n,include_attributes=False) for n in ast.walk(af) if isinstance(n,ast.Raise)]==[ast.dump(n,include_attributes=False) for n in ast.walk(bf) if isinstance(n,ast.Raise)])
spec=importlib.util.spec_from_file_location('pure_native_exposure',full/'coinmaster/strategy/cm2_execution.py');ex=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ex;spec.loader.exec_module(ex)
ns={'D':D,'ZERO':D(0),'FRESH_NS':120_000_000_000,'N':N,'NativeExposure':ex.NativeExposure};functions=[]
for fn,name in [(af,'old_capital'),(bf,'new_capital')]:
 import copy
 f=copy.deepcopy(fn);f.name=name;functions.append(f)
t=ast.parse((newroot/'tests/test_cm2_audit_defer_pure.py').read_text());functions+=[n for n in t.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('ID','native_facts')];exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),'exact_frozen_methods_and_pure_facts','exec'),ns)
for side,held in [(1,True),(-1,True),(1,False)]:
 old,_,_,oc,on,_,_=ns['native_facts'](side,held);new,_,_,nc,nn,_,_=ns['native_facts'](side,held,True);before=ns['old_capital'](old,100);after=ns['new_capital'](new,100);check('TRADING_FRAME_GETTERS_NOTES_IDENTICAL:'+str((side,held)),{k:v for k,v in before.items() if k!='btc_attribution_audit'}=={k:v for k,v in after.items() if k!='btc_attribution_audit'} and [c for c in oc if c[0]!='realized']==nc and on==nn and not any(c[0]=='realized' for c in nc));audit=after['btc_attribution_audit'];check('DEFERRED_NONE_NOT_ZERO:'+str((side,held)),audit['status']=='DEFERRED_TO_NATIVE_TERMINAL_RECONCILIATION' and all(audit[k] is None for k in ('btc_realized','btc_derived_sizing_audit','unallocated_bridge')) and audit['trading_input'] is False)
for failure in ['SOL_funding_unknown','cash_currency_unknown']:
 messages=[]
 for fn in [ns['old_capital'],ns['new_capital']]:
  f,b,so,_,_,_,fv=ns['native_facts']()
  if failure=='SOL_funding_unknown':fv[so]=None
  else:f.cache.account_for_venue('V').balance_total=lambda c:N(currency='OTHER',as_decimal=lambda:D(10000))
  try:fn(f,100);raise AssertionError('EXPECTED_UNKNOWN')
  except ValueError as e:messages.append(str(e))
 check('GUARD_ERRORS_SAME:'+failure,len(messages)==2 and messages[0]==messages[1])
for path,h in receipt['preserved_financial_sources'].items():check('PRESERVED_TERMINAL_AUTHORITY:'+path,sha(full/'coinmaster'/path)==h)
check('NO_NATIVE_MODULE_IMPORTED',not any(x.startswith('nautilus_trader') for x in sys.modules))
out={'status':'INDEPENDENT_EXACT_AUDIT_DEFER_CHECKS_PASS','commit':receipt['commit'],'checks':proof,'native_engines':0,'native_Strategy_constructors':0,'source_edits':0,'financial_qualification_from_mocks':False};(R/'AUDIT_DEFER_INDEPENDENT_PROOFS_7ca19646.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'checks':len(proof),'Native':0},indent=2))
