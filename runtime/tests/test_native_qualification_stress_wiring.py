"""Engine-free stress parameter/wiring proof; never instantiate any native object."""
import ast
from pathlib import Path

SOURCE=Path(__file__).parents[1]/'coinmaster/research/native_baseline.py'
TREE=ast.parse(SOURCE.read_text())
FUNCTIONS={n.name:n for n in TREE.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def helpers():
 names=('qualification_stress_venue_kwargs','qualification_stress_metadata')
 module=ast.Module(body=[FUNCTIONS[n] for n in names],type_ignores=[])
 namespace={}
 exec(compile(module,str(SOURCE),'exec'),namespace)
 return namespace

def test_disabled_stress_preserves_absent_venue_override_and_never_calls_factory():
 h=helpers()
 def forbidden(**kwargs):raise AssertionError('default OFF must not construct a FillModel')
 assert h['qualification_stress_venue_kwargs'](False,fill_model_factory=forbidden)=={}

def test_enabled_stress_forwards_exact_installed_fillmodel_parameters_once():
 h=helpers();calls=[];sentinel=object()
 def factory(**kwargs):calls.append(kwargs);return sentinel
 assert h['qualification_stress_venue_kwargs'](True,fill_model_factory=factory)=={'fill_model':sentinel}
 assert calls==[dict(prob_fill_on_limit=1.0,prob_slippage=1.0,random_seed=0)]

def test_stress_metadata_is_explicit_diagnostic_with_unchanged_base_fees_liquidity():
 metadata=helpers()['qualification_stress_metadata']()
 assert metadata['parameters']==dict(prob_fill_on_limit=1.0,prob_slippage=1.0,random_seed=0)
 assert metadata['includes_limit_and_maker_fills'] is True
 assert metadata['liquidity_consumption'] is False
 assert metadata['fees']=='UNCHANGED_BASE_NATIVE_MAKER_TAKER'
 assert metadata['qualification_only'] is True and metadata['historical_market_liquidity_claim'] is False
 assert metadata['effect']=='ONE_ADVERSE_NATIVE_INSTRUMENT_TICK_PER_L1_FILL_BUY_PLUS_SELL_MINUS'

def test_complete_cli_to_native_venue_wiring_is_default_off_without_latency_or_liquidity_override():
 runner=FUNCTIONS['run_native_diagnostic'];cli=FUNCTIONS['run_research_v0_repairs_cli'];main=FUNCTIONS['main']
 def default(node,name):
  args=node.args.args;values=[None]*(len(args)-len(node.args.defaults))+node.args.defaults
  return next(ast.literal_eval(v) for a,v in zip(args,values) if a.arg==name)
 assert default(runner,'qualification_stress') is False
 kwdefaults=dict(zip((a.arg for a in cli.args.kwonlyargs),cli.args.kw_defaults))
 assert ast.literal_eval(kwdefaults['qualification_stress']) is False
 venues=[n for n in ast.walk(runner) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_venue']
 assert len(venues)==1
 venue=venues[0];ordinary={k.arg for k in venue.keywords if k.arg is not None}
 assert 'fill_model' not in ordinary and 'latency_model' not in ordinary and 'liquidity_consumption' not in ordinary
 expansions=[k.value for k in venue.keywords if k.arg is None]
 assert len(expansions)==1 and ast.unparse(expansions[0])=='qualification_stress_venue_kwargs(qualification_stress)'
 calls=[n for n in ast.walk(cli) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='run_native_diagnostic']
 assert len(calls)==1 and any(k.arg=='qualification_stress' and ast.unparse(k.value)=='qualification_stress' for k in calls[0].keywords)
 calls=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='run_research_v0_repairs_cli']
 assert len(calls)==1 and any(k.arg=='qualification_stress' and ast.unparse(k.value)=='args.qualification_stress' for k in calls[0].keywords)
 flags=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--qualification-stress']
 assert len(flags)==1 and any(k.arg=='action' and ast.literal_eval(k.value)=='store_true' for k in flags[0].keywords)
 config_branches=[n for n in ast.walk(runner) if isinstance(n,ast.If) and ast.unparse(n.test)=='qualification_stress']
 assert len(config_branches)==1
 assert 'full_config[\'native_qualification_stress\'] = qualification_stress_metadata()' in ast.unparse(config_branches[0])
