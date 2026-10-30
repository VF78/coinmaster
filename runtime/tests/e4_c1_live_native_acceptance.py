"""Two credential-free connected native cases. Import/help never imports Nautilus.

This is a native event-routing fixture, NOT venue matching/execution evidence.
Run A then B in fresh processes. Root claims each physical attempt BEFORE launch.
No pytest collection entry points and no engine at import time.
"""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

BASE = None  # Caller supplies the newly frozen source, never an old-budget pin.
FRESH_NATIVE_INIT_API_WIRED = True
UNIFIED_SOURCE_WIRED = True  # Exact final source independently peer-qualified; synthetic fixture only.
ROOT_NATIVE_GO = False  # CLI --root-native-go plus exact new ledger claim required.
PARTIAL_PARENT_LIFECYCLE_QUALIFIED = True  # Root authorized exact final source qualification, not real START.
MAX_PHYSICAL_ATTEMPTS = 6
MAX_SYNTHETIC_SUBMIT_COMMANDS = 24
MAX_SYNTHETIC_CANCEL_COMMANDS = 48
MAX_CHILD_SECONDS = 420
KEY = "wave_overlay_live_recovery_v1"
MARKET_VECTOR_SHA256 = "5822faefcd9f2c9c4be742fefad58731089396dc9ef01dc4aa3c5b42c5a857e5"
MARKET_VECTOR_NAME = "e4_c1_live_native_acceptance_market_vector.json"
STOCK_MODEL_REFERENCE_SHA256 = "e0d83d6cd9438891cbf7b926fb054b88f2b4319710ee6382548268dd8999ec5f"
STOCK_INSTRUMENT_GEOMETRY_SHA256 = "9811bdb47f2e832706ddae9d20c6627ab02b5a66ad2075f53db5a71ebd6eb8db"
STOCK_INSTRUMENT_GEOMETRY = [{'coin': 'BTC', 'instrument_id': 'BTC-USD-PERP.HYPERLIQUID', 'raw_symbol': 'BTC', 'base_currency': 'BTC', 'quote_currency': 'USD', 'settlement_currency': 'USDC', 'is_inverse': False, 'price_increment': '0.1', 'size_increment': '0.00001', 'min_quantity': '0.00001', 'min_notional': '10', 'min_notional_currency': 'USD', 'margin_init': '0', 'margin_maint': '0', 'maker_fee': '0', 'taker_fee': '0', 'ts_event': 0, 'ts_init': 0}, {'coin': 'SOL', 'instrument_id': 'SOL-USD-PERP.HYPERLIQUID', 'raw_symbol': 'SOL', 'base_currency': 'SOL', 'quote_currency': 'USD', 'settlement_currency': 'USDC', 'is_inverse': False, 'price_increment': '0.01', 'size_increment': '0.01', 'min_quantity': '0.01', 'min_notional': '10', 'min_notional_currency': 'USD', 'margin_init': '0', 'margin_maint': '0', 'maker_fee': '0', 'taker_fee': '0', 'ts_event': 0, 'ts_init': 0}]
PRODUCT = (
    "ops/hl_live_worker.py", "ops/hl_live_execution.py", "ops/hl_live_money.py",
    "ops/hl_live_epoch.py", "ops/hl_info_receipt.py", "ops/hl_live_profile.py",
    "ops/hl_qualified_reports.py", "ops/live_recovery.py", "strategy/live_recovery.py",
    "strategy/residual_recovery.py", "strategy/c1_inputs.py", "strategy/wave_overlay.py",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()



def check_fake_order_status_abi():
    # Read installed Cython sources only; never import/construct native models.
    import re
    distribution=importlib.metadata.distribution("nautilus_trader")
    if distribution.version!="1.231.0":raise RuntimeError("PINNED_NATIVE_ABI_VERSION_REQUIRED")
    tree=ast.parse(Path(__file__).read_text())
    raw=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="raw_order")
    info=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=="info")
    branch=next(n for n in info.body if isinstance(n,ast.If) and ast.unparse(n.test)=="kind == 'orderStatus'")
    used={n.attr for part in (raw,branch) for n in ast.walk(part) if isinstance(n,ast.Attribute)
        and isinstance(n.value,ast.Name) and n.value.id=="order"}
    public=set();pins={}
    for name in ("base.pxd","base.pyx","limit.pxd"):
        path=Path(distribution.locate_file("nautilus_trader/model/orders/"+name)).resolve(strict=True)
        text=path.read_text();pins[name]=digest(path.read_bytes())
        public.update(re.findall(r"^    cdef readonly \S+ (\w+)",text,re.M))
        public.update(re.findall(r"^    def (\w+)\(self\)",text,re.M))
    missing=used-public
    if missing:raise RuntimeError("FAKE_ORDER_STATUS_NATIVE_ATTRIBUTE_MISSING:"+",".join(sorted(missing)))
    return dict(order_attributes=sorted(used),missing=[],installed_order_source_sha256=pins,
        mapping="FILLED enum first; other closed=>canceled; otherwise open",native_imports=0,native_constructors=0)


def check_account_updater_abi(root):
    # Pure source AST only: no Nautilus/product imports or constructors.
    def cls(path,name):
        return next(n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,ast.ClassDef) and n.name==name)
    def members(node):
        names={n.name for n in node.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        for n in node.body:
            if isinstance(n,ast.Assign):names.update(t.id for t in n.targets if isinstance(t,ast.Name))
        return names
    product=root/"runtime/coinmaster/ops/hl_live_execution.py"
    boundary=cls(product,"QualifiedInfoBoundary")
    collector=next(n for n in boundary.body if isinstance(n,ast.AsyncFunctionDef) and n.name=="_cm_collect_portfolio_observation")
    required={n.func.attr for n in ast.walk(collector) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
        and isinstance(n.func.value,ast.Name) and n.func.value.id=="self" and n.func.attr=="_update_account_state"}
    if required!={"_update_account_state"}:raise RuntimeError("PRODUCTION_CHEAP_COLLECTOR_UPDATER_ABI_CHANGED")
    fixture=cls(Path(__file__),"Client")
    scaffold=cls(root/"runtime/tests/test_live_native_report_recovery.py","FakeReportClient")
    if [ast.unparse(b) for b in fixture.bases]!=["FakeReportClient"]:raise RuntimeError("FIXTURE_CLIENT_MRO_CHANGED")
    if [ast.unparse(b) for b in scaffold.bases]!=["QualifiedInfoBoundary","LiveExecutionClient"]:raise RuntimeError("REPORT_CLIENT_MRO_CHANGED")
    distribution=importlib.metadata.distribution("nautilus_trader")
    if distribution.version!="1.231.0":raise RuntimeError("PINNED_NATIVE_ABI_VERSION_REQUIRED")
    installed=Path(distribution.locate_file("nautilus_trader/live/execution_client.py")).resolve(strict=True)
    live=cls(installed,"LiveExecutionClient")
    if [ast.unparse(b) for b in live.bases]!=["ExecutionClient"]:raise RuntimeError("INSTALLED_LIVE_CLIENT_MRO_CHANGED")
    effective=members(fixture)|members(scaffold)|members(boundary)|members(live)
    if not required<=effective:raise RuntimeError("FIXTURE_REQUIRED_ACCOUNT_UPDATER_UNBOUND")
    aliases={t.id:ast.unparse(n.value) for n in fixture.body if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Name)}
    for name in ("_update_account_state","_cm_collect_unified_native_account"):
        if aliases.get(name)!="execution.QualifiedHyperliquidExecutionClient."+name:raise RuntimeError("FIXTURE_ACCOUNT_UPDATER_MUST_BIND_ACTUAL_PRODUCTION_METHOD")
    return dict(required_methods=sorted(required),direct_production_alias_verified=True,
        fake_mro=["Client","FakeReportClient","QualifiedInfoBoundary","LiveExecutionClient","ExecutionClient"],
        installed_live_source_path=str(installed),installed_live_source_sha256=digest(installed.read_bytes()),
        inherited_update_present=("_update_account_state" in members(scaffold)|members(boundary)|members(live)),
        native_imports=0,native_constructors=0)


def check_submitted_lifecycle_abi(fixture_tree=None):
    # Inspect installed public API source only; never construct native models.
    import re
    tree=fixture_tree if fixture_tree is not None else ast.parse(Path(__file__).read_text())
    client=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=="Client")
    submit=next(n for n in client.body if isinstance(n,ast.AsyncFunctionDef) and n.name=="_submit_order")
    submitted=[(i,n.value) for i,n in enumerate(submit.body) if isinstance(n,ast.Expr)
        and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=="self.generate_order_submitted"]
    if len(submitted)!=1:raise RuntimeError("FIXTURE_PUBLIC_SUBMITTED_EXACTLY_ONCE_REQUIRED")
    index,call=submitted[0]
    expected={"strategy_id":"order.strategy_id","instrument_id":"order.instrument_id",
        "client_order_id":"order.client_order_id","ts_event":"self._clock.timestamp_ns()"}
    if call.args or {k.arg:ast.unparse(k.value) for k in call.keywords}!=expected:
        raise RuntimeError("FIXTURE_PUBLIC_SUBMITTED_STOCK_SIGNATURE_REQUIRED")
    boundaries=[i for i,n in enumerate(submit.body) if isinstance(n,ast.If) and
        (ast.unparse(n.test)=="self.drop_next_ack" or any(isinstance(x,ast.Call)
        and ast.unparse(x.func)=="self.generate_order_accepted" for x in ast.walk(n)))]
    if len(boundaries)!=2 or not all(index<i for i in boundaries):
        raise RuntimeError("FIXTURE_PUBLIC_SUBMITTED_BEFORE_LOSTACK_AND_ACCEPT_REQUIRED")
    distribution=importlib.metadata.distribution("nautilus_trader")
    if distribution.version!="1.231.0":raise RuntimeError("PINNED_NATIVE_ABI_VERSION_REQUIRED")
    paths={name:Path(distribution.locate_file(name)).resolve(strict=True) for name in
        ("nautilus_trader/execution/client.pyx","nautilus_trader/model/orders/base.pyx",
         "nautilus_trader/adapters/hyperliquid/execution.py")}
    native=paths["nautilus_trader/execution/client.pyx"].read_text()
    if not re.search(r"cpdef void generate_order_submitted\(\s*self,\s*StrategyId strategy_id,\s*InstrumentId instrument_id,\s*ClientOrderId client_order_id,\s*uint64_t ts_event,\s*\)",native):
        raise RuntimeError("INSTALLED_PUBLIC_SUBMITTED_SIGNATURE_CHANGED")
    block=native[native.index("cpdef void generate_order_submitted("):native.index("cpdef void generate_order_rejected(")]
    if "account_id=self.account_id" not in block or "self._send_order_event(submitted)" not in block:
        raise RuntimeError("INSTALLED_PUBLIC_SUBMITTED_ACCOUNT_BINDING_CHANGED")
    base=paths["nautilus_trader/model/orders/base.pyx"].read_text()
    if "self.account_id = event.account_id" not in base[base.index("cdef void _submitted("):base.index("cdef void _rejected(")]:
        raise RuntimeError("INSTALLED_ORDER_SUBMITTED_BINDING_CHANGED")
    scaffold=ast.parse((Path(__file__).resolve().parent/"test_live_native_report_recovery.py").read_text())
    cls=next(n for n in scaffold.body if isinstance(n,ast.ClassDef) and n.name=="FakeReportClient")
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="__init__")
    if not any(isinstance(n,ast.Call) and ast.unparse(n)=="self._set_account_id(ACCOUNT)" for n in ast.walk(init)):
        raise RuntimeError("FIXTURE_CLIENT_NATIVE_ACCOUNT_BINDING_REQUIRED")
    stock=ast.parse(paths["nautilus_trader/adapters/hyperliquid/execution.py"].read_text())
    method=next(n for n in ast.walk(stock) if isinstance(n,ast.AsyncFunctionDef) and n.name=="_submit_order")
    stock_call=next(n for n in method.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
        and ast.unparse(n.value.func)=="self.generate_order_submitted").value
    if {k.arg:ast.unparse(k.value) for k in stock_call.keywords}!=expected:
        raise RuntimeError("STOCK_HL_SUBMITTED_CALL_CHANGED")
    return dict(public_generator="generate_order_submitted",before_lost_ack_and_accept=True,
        installed_source_sha256={name:digest(path.read_bytes()) for name,path in paths.items()},
        native_client_account_binding=True,native_imports=0,native_constructors=0)


def load_actual_live_health_holder(root):
    # Exact production method AST and profile helper, stdlib imports only.
    import builtins
    import dis
    import re
    from decimal import Decimal
    source=root/"runtime/coinmaster/ops/hl_live_worker.py"
    module=ast.parse(source.read_text())
    owner=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=="HyperliquidLiveNode")
    names={"_entries_enabled","_live_health_current"}
    methods=[n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in methods}!=names:raise RuntimeError("ACTUAL_LIVE_HEALTH_METHODS_REQUIRED")
    profile=root/"runtime/coinmaster/ops/hl_live_profile.py"
    parity=next(n for n in ast.parse(profile.read_text()).body if isinstance(n,ast.FunctionDef)
        and n.name=="require_profile_deposit_parity")
    namespace={"Decimal":Decimal,"time":time,"__builtins__":builtins.__dict__}
    cls=ast.ClassDef(name="ActualLiveHealthHolder",bases=[],keywords=[],body=methods,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[parity,cls],type_ignores=[])),str(source),"exec"),namespace)
    holder=namespace["ActualLiveHealthHolder"]
    def globals_used(code):
        result={i.argval for i in dis.get_instructions(code) if i.opname=="LOAD_GLOBAL"}
        for value in code.co_consts:
            if hasattr(value,"co_code"):result|=globals_used(value)
        return result
    loaded={name:sorted(globals_used(getattr(holder,name).__code__)) for name in names}
    loaded["require_profile_deposit_parity"]=sorted(globals_used(namespace["require_profile_deposit_parity"].__code__))
    if any(name not in namespace and not hasattr(builtins,name) for values in loaded.values() for name in values):
        raise RuntimeError("ACTUAL_LIVE_HOLDER_UNBOUND_GLOBAL")
    required=sorted({n.attr for method in methods for n in ast.walk(method) if isinstance(n,ast.Attribute)
        and isinstance(n.value,ast.Name) and n.value.id=="self"})
    expected={"strategy","state","active_c1","_refresh_warmup_readiness","input_readiness","profile","gate","node","feed"}
    if set(required)!=expected:raise RuntimeError("ACTUAL_LIVE_HOLDER_ATTRIBUTE_CONTRACT_CHANGED")
    distribution=importlib.metadata.distribution("nautilus_trader")
    if distribution.version!="1.231.0":raise RuntimeError("PINNED_NATIVE_ABI_VERSION_REQUIRED")
    used={n.attr for method in methods for n in ast.walk(method) if isinstance(n,ast.Attribute)
        and isinstance(n.value,ast.Name) and n.value.id=="order"}
    public=set();pins={}
    for name in ("base.pxd","base.pyx","limit.pxd"):
        path=Path(distribution.locate_file("nautilus_trader/model/orders/"+name)).resolve(strict=True)
        text=path.read_text();pins[name]=digest(path.read_bytes())
        public.update(re.findall(r"^    cdef readonly \S+ (\w+)",text,re.M))
        public.update(re.findall(r"^    def (\w+)\(self\)",text,re.M))
    if used-public:raise RuntimeError("ACTUAL_LIVE_HOLDER_NATIVE_ORDER_ABI_MISSING:"+",".join(sorted(used-public)))
    # Same actual constructor binding statement must still exist in production.
    init=next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=="__init__")
    if not any(isinstance(n,ast.Call) and ast.unparse(n)=="state.bind_live_health(self._live_health_current)" for n in ast.walk(init)):
        raise RuntimeError("ACTUAL_PRODUCTION_LIVE_HEALTH_BINDING_CHANGED")
    return holder,dict(methods=sorted(names),LOAD_GLOBAL=loaded,required_attributes=required,
        actual_source_sha256=digest(source.read_bytes()),actual_profile_helper_sha256=digest(profile.read_bytes()),
        native_order_attributes=sorted(used),missing=[],installed_order_source_sha256=pins,
        native_imports=0,native_constructors=0)


class ObservationalDecisionTrace:
    """Bounded actual-call observer; no predicate invocation or return replacement."""
    def __init__(self, targets):
        from collections import deque
        self.targets=targets
        self.events=deque(maxlen=128)
        self.total=0
        self.limit=2048
        self.counts={}
        self.last_health=None
        self.previous=None
        self.observer_errors=0
        self.overwritten_events=0
        self.started_ns=None
        self.finished_ns=None
        self.callback_self_time_ns=0
        self.phase=None
        self.active_intervals=[]

    @staticmethod
    def code(value):
        import re
        value=str(value)
        return value if re.fullmatch(r"[A-Z][A-Z0-9_]{0,179}",value) else "NON_CODE_REDACTED"

    def _observe(self, frame, event, value):
        observed_started=None
        try:
            label=self.targets.get(frame.f_code)
            if label is None:return None
            if event=="call":frame.f_trace_lines=False
            if event not in ("call","return","exception"):return self._observe
            observed_started=time.monotonic_ns()
            key=label+":"+event
            self.counts[key]=min(self.limit,self.counts.get(key,0)+1)
            self.total=min(self.limit,self.total+1)
            row=dict(sequence=self.total,function=label,event=event,phase=self.phase,
                file=frame.f_code.co_filename,line=frame.f_lineno,first_line=frame.f_code.co_firstlineno)
            if event=="return":
                row["return_type"]=type(value).__name__
                if type(value) is bool:row["boolean"]=value
                elif type(value).__name__=="PaperHealth":
                    health=dict(safe_for_increase=value.safe_for_increase,
                        paused_new_entries=value.paused_new_entries,flatten_requested=value.flatten_requested,
                        warnings=[self.code(x) for x in value.warnings])
                    row["health"]=health;self.last_health=health
                elif value is None:row["returned_none"]=True
            elif event=="exception":
                row.update(exception_type=value[0].__name__,code=self.code(value[1]))
            if len(self.events)==self.events.maxlen:
                self.overwritten_events=min(self.limit,self.overwritten_events+1)
            self.events.append(row)
        except BaseException:
            self.observer_errors=min(self.limit,self.observer_errors+1)
        finally:
            try:
                if observed_started is not None:self.callback_self_time_ns+=max(0,time.monotonic_ns()-observed_started)
            except BaseException:pass
        return self._observe

    def __enter__(self):
        self.previous=sys.gettrace()
        self.started_ns=time.monotonic_ns()
        sys.settrace(self._observe)
        return self

    def __exit__(self,*unused):
        try:sys.settrace(self.previous)
        finally:
            self.finished_ns=time.monotonic_ns()
            self.active_intervals.append(dict(phase=self.phase,start_ns=self.started_ns,end_ns=self.finished_ns))
            self.active_intervals=self.active_intervals[-16:]
        return False

    def receipt(self):
        return dict(kind="ACTUAL_DECISION_CALLS_NO_REEVALUATION",events=list(self.events),
            calls_and_returns=dict(self.counts),observed_event_counter=self.total,aggregate_counter_limit=self.limit,
            counter_saturated=(self.total>=self.limit),rolling_observation_continued=True,
            retained_events=len(self.events),ring_limit=128,overwritten_counter=self.overwritten_events,
            records_dropped_from_ring=(self.overwritten_events>0),observer_errors=self.observer_errors,
            observer_active_interval_monotonic_ns=[self.started_ns,self.finished_ns],
            observer_active_intervals=self.active_intervals,
            observer_callback_self_time_ns=self.callback_self_time_ns,
            last_actual_health=self.last_health,previous_trace_restored=(sys.gettrace() is self.previous))


def preflight(args):
    if not all((args.root_native_go,UNIFIED_SOURCE_WIRED,FRESH_NATIVE_INIT_API_WIRED,PARTIAL_PARENT_LIFECYCLE_QUALIFIED)):
        raise RuntimeError("PREPARATION_ONLY_FINAL_UNIFIED_SOURCE_AND_ROOT_NATIVE_GO_REQUIRED")
    root = Path(__file__).resolve().parents[2]
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    if args.expected_source!=head:
        raise RuntimeError("FINAL_REVIEWED_SOURCE_PIN_REQUIRED")
    pins = {}
    # The entire tracked product/config tree is frozen, not a hand-picked list.
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", args.expected_source,
        "--", "runtime/coinmaster", "runtime/configs"], cwd=root, text=True).splitlines()
    helper = "runtime/tests/test_live_native_report_recovery.py"
    paths.extend((helper,"runtime/tests/test_hl_stageg_sandbox_lifecycle.py","runtime/tests/test_wave_native_integration.py"))
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--",
        "runtime/coinmaster", "runtime/configs"], cwd=root, text=True).splitlines()
    if untracked:
        raise RuntimeError("UNTRACKED_PRODUCT_SOURCE_CAN_SHADOW_FROZEN_IMPORTS")
    for name in paths:
        pinned = subprocess.check_output(["git", "show", args.expected_source + ":" + name], cwd=root)
        if (root / name).read_bytes() != pinned:
            raise RuntimeError("PRODUCT_SOURCE_NOT_FROZEN:" + name)
        pins[name] = digest(pinned)
    if any(name=="coinmaster" or name.startswith("coinmaster.") for name in sys.modules):
        raise RuntimeError("PRODUCT_PREIMPORTED_BEFORE_SOURCE_ISOLATION")
    # Authoritative frozen source wins over an editable/installed primary tree.
    sys.path[:0]=[str(root/"runtime"),str(root/"runtime/tests")]
    vector_path=Path(__file__).with_name(MARKET_VECTOR_NAME).resolve(strict=True)
    if vector_path.stat().st_size>1_048_576 or digest(vector_path.read_bytes())!=MARKET_VECTOR_SHA256:
        raise RuntimeError("FROZEN_FIRST_POSITIVE_MARKET_VECTOR_REQUIRED")
    pins["runtime/tests/"+MARKET_VECTOR_NAME]=MARKET_VECTOR_SHA256
    reference=Path(__file__).with_name("e4_c1_live_native_acceptance_currency_model.py")
    if digest(reference.read_bytes())!=STOCK_MODEL_REFERENCE_SHA256:
        raise RuntimeError("SUCCESSFUL_FROZEN_STOCK_MODEL_REFERENCE_MISMATCH")
    pins["runtime/tests/"+reference.name]=STOCK_MODEL_REFERENCE_SHA256
    geometry=json.loads(json.dumps(STOCK_INSTRUMENT_GEOMETRY))
    if digest(json.dumps(geometry,sort_keys=True,separators=(",",":")).encode())!=STOCK_INSTRUMENT_GEOMETRY_SHA256:
        raise RuntimeError("STOCK_GEOMETRY_JSON_MISMATCH")
    assert [row["coin"] for row in geometry]==["BTC","SOL"]
    for row in geometry:
        assert all(row[name]=="0" for name in ("margin_init","margin_maint","maker_fee","taker_fee"))
        assert row["instrument_id"]==row["coin"]+"-USD-PERP.HYPERLIQUID"
        assert row["quote_currency"]==row["min_notional_currency"]=="USD" and row["settlement_currency"]=="USDC"
        assert row["min_notional"]=="10" and row["min_quantity"]==row["size_increment"]
        assert row["is_inverse"] is False and row["ts_event"]==row["ts_init"]==0
    updater_abi=check_account_updater_abi(root)
    updater_abi["fake_order_status"]=check_fake_order_status_abi()
    updater_abi["submitted_lifecycle"]=check_submitted_lifecycle_abi()
    updater_abi["actual_live_health_holder"]=load_actual_live_health_holder(root)[1]
    fixture_hash = digest(Path(__file__).read_bytes())
    ledger_path = args.ledger.resolve(strict=True)
    ledger = json.loads(ledger_path.read_text())
    if ledger.get("ledger_path") != str(ledger_path):
        raise RuntimeError("ROOT_CANONICAL_LEDGER_PATH_REQUIRED")
    attempts = ledger["attempts"]
    if ledger.get("max_physical_attempts")!=MAX_PHYSICAL_ATTEMPTS:
        raise RuntimeError("ROOT_PHYSICAL_ATTEMPT_BUDGET_REQUIRED")
    if len(attempts) > MAX_PHYSICAL_ATTEMPTS:
        raise RuntimeError("NATIVE_ATTEMPT_CAP_EXCEEDED")
    matches = [a for a in attempts if a["attempt_id"] == args.attempt_id]
    if len(matches) != 1:
        raise RuntimeError("ROOT_LEDGER_CLAIM_REQUIRED")
    claim = matches[0]
    for field, value in dict(case=args.case, status="RUNNING", source_commit=args.expected_source,
                             fixture_sha256=fixture_hash, artifact_dir=str(args.artifact_dir.resolve()),
                             market_vector_sha256=MARKET_VECTOR_SHA256,market_vector_path=str(vector_path),
                             max_nodes=1,whole_child_wall_cap_seconds=MAX_CHILD_SECONDS,
                             max_synthetic_submit_commands=MAX_SYNTHETIC_SUBMIT_COMMANDS,
                             max_synthetic_cancel_commands=MAX_SYNTHETIC_CANCEL_COMMANDS,external_network_cap=0).items():
        if claim.get(field) != value:
            raise RuntimeError("ROOT_LEDGER_CLAIM_MISMATCH:" + field)
    if args.case == "B":
        prior = json.loads((args.artifact_dir / "A-result.json").read_text())
        if (prior["status"] != "PASS" or prior["source_commit"] != args.expected_source
            or prior.get("fixture_sha256")!=fixture_hash or prior.get("counts",{}).get("nodes_constructed")!=1
            or prior.get("counts",{}).get("external_network_attempts")!=0):
            raise RuntimeError("CASE_A_PASS_SAME_SOURCE_REQUIRED")
    claim_path=ledger_path.with_name(ledger_path.name+"."+args.attempt_id+".claim")
    with claim_path.open("x") as stream:
        stream.write(json.dumps(dict(attempt_id=args.attempt_id,artifact_dir=str(args.artifact_dir.resolve()),fixture_sha256=fixture_hash)))
    os.chmod(claim_path,0o600)
    return pins, fixture_hash, updater_abi


async def run(args, result):
    # Imports are deliberately below CLI/preflight. Nothing here is run for --help.
    from decimal import Decimal as D
    from types import SimpleNamespace
    import importlib.metadata
    import socket
    import urllib.request
    if importlib.metadata.version("nautilus_trader") != "1.231.0":
        raise RuntimeError("PINNED_NAUTILUS_1_231_0_REQUIRED")
    from nautilus_trader.common import Environment
    from nautilus_trader.config import LoggingConfig, LiveExecClientConfig
    from nautilus_trader.live.config import TradingNodeConfig, LiveExecEngineConfig, RoutingConfig
    from nautilus_trader.live.node import TradingNode
    from nautilus_trader.live.factories import LiveExecClientFactory
    from nautilus_trader.trading.strategy import Strategy
    from nautilus_trader.model.data import Bar, BarType, BarSpecification, QuoteTick
    from nautilus_trader.model.enums import (OrderSide, OrderType, OrderStatus, TimeInForce, LiquiditySide,
                                            BarAggregation, PriceType, AggregationSource)
    from nautilus_trader.model.identifiers import ClientOrderId, ClientId, InstrumentId, TradeId, VenueOrderId, Venue, Symbol
    from nautilus_trader.model.objects import Quantity, Price, Money, AccountBalance
    from nautilus_trader.model.currencies import BTC, SOL, USD, USDC
    from nautilus_trader.model.instruments import CryptoPerpetual
    from nautilus_trader.core import nautilus_pyo3
    from coinmaster.ops.hl_live_epoch import LiveEpochRuntime
    from coinmaster.ops.live_recovery import NativeLiveRecoveryScope, durable_management_scope
    from coinmaster.ops.hl_info_receipt import collect_info_receipt, IncompleteInfoReport
    from coinmaster.ops.hl_live_profile import INPUT_FLAGS, _validate_input_readiness_profile
    from coinmaster.ops.stage_g_config import load_candidate
    from coinmaster.ops.hl_live_execution import SingleAttemptInfoTransport, bind_clean_flat_live_handover
    import coinmaster.ops.hl_live_execution as execution
    from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
    from coinmaster.domain.wave_overlay import DailyBar
    from coinmaster.ops.hl_live_worker import LiveSubmissionHooks, HyperliquidLiveNode, require_live_order_approval
    from coinmaster.ops.stage_g_config import candidate_content_hash
    from coinmaster.ops.venue_data import binding_for_execution
    from coinmaster.ops.hl_closed_bars import normalize_hl_bar
    from coinmaster.venues.marks import VenueMark
    from datetime import datetime, timedelta, timezone
    from coinmaster.venues.marks import venue_mark_data_type
    # Verify production import origins before importing fixture scaffolding,
    # whose module globals include Sandbox instruments; they are NOT the stock contract.
    from coinmaster.ops import hl_unified_instruments as provider_module
    product_root = Path(__file__).resolve().parents[2]
    def verify_module_origin(module, relative):
        expected = (product_root/relative).resolve(strict=True)
        actual = Path(module.__file__).resolve(strict=True)
        if actual != expected or digest(actual.read_bytes()) != result["source_pins"][relative]:
            raise RuntimeError("IMPORTED_SOURCE_ORIGIN_OR_SHA_MISMATCH:"+relative)
    for name,module in list(sys.modules.items()):
        if name.startswith("coinmaster.") and getattr(module,"__file__",None):
            relative="runtime/"+name.replace(".","/")+".py"
            if relative in result["source_pins"]: verify_module_origin(module,relative)
    import test_live_native_report_recovery as scaffolding
    verify_module_origin(scaffolding,"runtime/tests/test_live_native_report_recovery.py")
    verify_module_origin(sys.modules["test_hl_stageg_sandbox_lifecycle"],"runtime/tests/test_hl_stageg_sandbox_lifecycle.py")
    FakeReportClient, ACCOUNT, ACCOUNT_REF = scaffolding.FakeReportClient, scaffolding.ACCOUNT, scaffolding.ACCOUNT_REF
    def actual_stock_instrument(row):
        # Exact stock geometry/zero rates already exercised by the CLOSED
        # successful currency MODEL. Do not relabel or mutate Sandbox objects.
        tick,step=row["price_increment"],row["size_increment"]
        raw=CryptoPerpetual(InstrumentId.from_str(row["instrument_id"]),Symbol(row["raw_symbol"]),
            {"BTC":BTC,"SOL":SOL}[row["base_currency"]],USD,USDC,False,
            len(tick.split(".")[1]),len(step.split(".")[1]),Price.from_str(tick),Quantity.from_str(step),0,0,
            min_quantity=Quantity.from_str(row["min_quantity"]),min_notional=Money(D(row["min_notional"]),USD),
            margin_init=D(row["margin_init"]),margin_maint=D(row["margin_maint"]),
            maker_fee=D(row["maker_fee"]),taker_fee=D(row["taker_fee"]))
        return provider_module.normalize_unified_legacy_instrument(raw)
    HL_BTC,HL_SOL=map(actual_stock_instrument,STOCK_INSTRUMENT_GEOMETRY)
    result["instrument_geometry_source"]=dict(reference_sha256=STOCK_MODEL_REFERENCE_SHA256,
        stock_json_sha256=STOCK_INSTRUMENT_GEOMETRY_SHA256,sandbox_instruments_used=False)

    result["native_version"] = "1.231.0"
    result["fixture_capital_tag"] = "SYNTHETIC_APPROVED_100_USDC_NOT_REAL_BUDGET"
    result["financial_source_mode"] = "unifiedAccount"
    result["commission_scope"] = "FIXED_SYNTHETIC_0.00027_USDC_NATIVE_EVENT_AMOUNT_NOT_VENUE_FEE_RATE_PROOF"
    result["financial_equity_basis"] = "HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1"
    counts = result["counts"]
    def forbidden(*unused, **kwargs):
        counts["external_network_attempts"] += 1
        raise RuntimeError("FIXTURE_EXTERNAL_NETWORK_FORBIDDEN")
    # The event loop already exists. All subsequent network connection attempts fail.
    old_connect, old_urlopen = socket.socket.connect, urllib.request.urlopen
    socket.socket.connect = forbidden
    urllib.request.urlopen = forbidden
    execution.urlopen = forbidden
    runtime = LiveEpochRuntime(args.artifact_dir / "native.sqlite", "e4-c1-native-fixture", 10**20)
    assert runtime._fresh_c1_epoch_active is False
    runtime.acquire()
    runtime.acquire_live_account(ACCOUNT_REF, "HYPERLIQUID", lock_root=args.artifact_dir/"account-locks")
    if args.case == "A":
        assert runtime.strategy_checkpoint() is None and runtime.c1_initialization() is None
        assert runtime.deposit_protection_state(instance_id=runtime.owner, account_id=str(ACCOUNT)) is None
        runtime.entry_control_command("pause-new-entries", "c1-init-prepare")
    venue_file=args.artifact_dir/("fake-venue.json" if args.case=="A" else "terminal-fake-venue.json")
    os.environ["CM_FAKE_VENUE_STATE"]=str(venue_file)
    if args.case=="A":
        with venue_file.open("x") as stream:json.dump(dict(partial=False,balance="100",hold="0"),stream)
    else:
        prior=json.loads((args.artifact_dir/"restart-proof.json").read_text())
        assert digest(venue_file.read_bytes())==prior["terminal_fake_venue_sha256"]
    os.environ["CM_FAKE_PRODUCTION_PARITY"] = "1"

    class Client(FakeReportClient):
        def __init__(self, *a):
            super().__init__(*a)
            venue_state=json.loads(venue_file.read_text())
            self.total = D(venue_state["balance"])
            self.hold = D(venue_state["hold"])
            outer = self
            class NativeSpotTransport:
                async def request_spot_balances(self):
                    counts["synthetic_native_spot_reads"] += 1
                    return [nautilus_pyo3.AccountBalance.from_dict(dict(currency="USDC",total=str(outer.total),
                        locked=str(outer.hold),free=str(outer.total-outer.hold)))]
            self._client = NativeSpotTransport()
            self.delay_account = False
            self.lost = set()
            self.drop_next_ack=False  # Root-approved lostACK belongs to final actual DP close.
            self.info_unknown = set()
            self.hold_cancel_ack=set()
            self.seen_commands = []
            self.seen_cancels = []
            self.oid = 7
        # EXACT production compatibility methods; only the unsigned native
        # read transport returns controlled native AccountBalance facts.
        _update_account_state = execution.QualifiedHyperliquidExecutionClient._update_account_state
        _cm_collect_unified_native_account = execution.QualifiedHyperliquidExecutionClient._cm_collect_unified_native_account
        async def account_state(self):
            await execution.QualifiedHyperliquidExecutionClient._update_account_state(self)
        async def _connect(self):
            await self.account_state()
        async def _query_account(self, command):
            counts["query_account_commands"] += 1
            if not self.delay_account:
                await self.account_state()
        async def _submit_order(self, command):
            if counts["synthetic_submit_commands"]>=MAX_SYNTHETIC_SUBMIT_COMMANDS:
                raise RuntimeError("SYNTHETIC_SUBMIT_COMMAND_CAP_REACHED")
            counts["synthetic_submit_commands"] += 1
            order = command.order
            # Match stock Hyperliquid: public native Submitted precedes transport/ACK.
            self.generate_order_submitted(strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,client_order_id=order.client_order_id,
                ts_event=self._clock.timestamp_ns())
            self.seen_commands.append(str(order.client_order_id))
            if self.drop_next_ack:
                self.drop_next_ack=False
                self.lost.add(str(order.client_order_id))
            if str(order.client_order_id) not in self.lost:
                self.oid += 1
                self.generate_order_accepted(order.strategy_id, order.instrument_id, order.client_order_id,
                    VenueOrderId(str(self.oid)), self._clock.timestamp_ns())
        async def _cancel_order(self, command):
            if counts["synthetic_cancel_commands"]>=MAX_SYNTHETIC_CANCEL_COMMANDS:
                raise RuntimeError("SYNTHETIC_CANCEL_COMMAND_CAP_REACHED")
            counts["synthetic_cancel_commands"] += 1
            name=str(command.client_order_id)
            self.seen_cancels.append(name)
            if name not in self.hold_cancel_ack:
                order=self._cache.order(command.client_order_id)
                assert order is not None
                self.generate_order_canceled(order.strategy_id,order.instrument_id,order.client_order_id,
                    order.venue_order_id,self._clock.timestamp_ns())
            # Entry-race/C1 barriers explicitly withhold ACK until scenario event.
        async def generate_mass_status(self, lookback_mins=None):
            try:
                return await execution.QualifiedInfoBoundary.generate_mass_status(self, lookback_mins)
            except BaseException as exc:
                import re
                code=str(exc)
                result["full_generation_inner_failure"]=dict(exception_type=type(exc).__name__,
                    code=code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,179}",code) else "NON_CODE_REDACTED",
                    private_traceback=traceback.format_exc())
                raise
        async def generate_order_status_reports(self, command):
            return []
        async def generate_fill_reports(self, command):
            return []
        async def generate_position_status_reports(self, command):
            return []

    clients = []
    class Factory(LiveExecClientFactory):
        @staticmethod
        def create(loop, name, config, msgbus, cache, clock):
            client = Client(loop, msgbus, cache, clock)
            clients.append(client)
            return client

    startup = []
    class Probe(RecoverableWaveOverlayStrategy):
        # Keep real on_start; intercept only public feed transports, never fabricate bars.
        def subscribe_bars(self, kind, *a, **kw):
            startup.append(("subscribe", str(kind), kw))
        def request_bars(self, kind, *a, **kw):
            startup.append(("request", str(kind), kw))
        def subscribe_quote_ticks(self, *a, **kw):
            pass
        def subscribe_data(self, *a, **kw):
            pass

    root = Path(__file__).resolve().parents[1]
    candidate = load_candidate(root / "configs/hl-live-v3-dp50.candidate.json").candidate
    selected_pin_names={"coinmaster/strategy/"+n+".py" for n in
        ("residual_recovery","wave_overlay","next_band","hedge_band","c1_inputs")}
    selected_pin_names|={"coinmaster/domain/wave_overlay.py"}
    selected_pin_names|={"coinmaster/ops/"+n+".py" for n in
        ("hl_unified_account","hl_unified_instruments","hl_live_execution","hl_info_receipt","hl_live_money","venue_data","hl_closed_bars")}
    selected_pin_names.add("coinmaster/strategy/live_recovery.py")
    profile=_validate_input_readiness_profile(root,dict(
        schema="coinmaster-live-selected-c1-v1",profile_id="E4_C1_ACTIVE_SELECTED",
        initial_capital_policy="ACTUAL_AVAILABLE_USDC_AT_FRESH_FLAT_INIT",candidate_sha256=candidate_content_hash(candidate),
        research_source="fccd60c01e8cae5e8258748b046f43f88a16bb79",
        economic_config_sha256="a2c7d88b5aff67399c0db849585bc5ad3625ce4e82068b3e29254d355c119253",
        strategy_flags=INPUT_FLAGS,manage_only_readiness=False,input_readiness=True,
        live_order_capability=True,owner_start_required=True,
        source_pins={name:digest((root/name).read_bytes()) for name in selected_pin_names},
        deposit_protection_percent=55,retained_equity_floor_fraction="0.45",
        initialization_intent="INITIALIZE_FRESH_C1_EPOCH" if args.case=="A" else None,
        account_mode="unifiedAccount",equity_basis=result["financial_equity_basis"]),candidate)
    # This is a deliberately SYNTHETIC ticket, never a real account/START artifact.
    ticket_root=args.artifact_dir/(args.case+"-synthetic-release")
    ticket_root.mkdir()
    account_sha=digest(ACCOUNT_REF.lower().encode())
    identity=dict(source_commit=args.expected_source,strategy_sha256=result["source_pins"]["runtime/coinmaster/strategy/live_recovery.py"],
        candidate_sha256=profile["candidate_sha256"],profile_sha256=profile["profile_sha256"],
        initial_capital_policy=profile["initial_capital_policy"],account_mode=profile["account_mode"],equity_basis=profile["equity_basis"],
        money_currency="USDC",research_source=profile["research_source"],economic_config_sha256=profile["economic_config_sha256"])
    ticket=dict(schema="coinmaster-live-order-approval-v2",instance_id="hl-stageg-live",
        release_commit=args.expected_source,master_address_sha256=account_sha,
        authorization="START_LIVE_E4_C1",start_approved=True,orders_approved=True,
        **{k:identity[k] for k in ("strategy_sha256","candidate_sha256","profile_sha256","initial_capital_policy","account_mode","equity_basis")})
    for name,value in (("live-release.json",identity),("approval.json",ticket),("fingerprint.json",dict(master_address_sha256=account_sha))):
        (ticket_root/name).write_text(json.dumps(value))
    require_live_order_approval(ticket_root/"approval.json",ticket_root/"fingerprint.json",ticket_root,profile=profile)
    result["synthetic_profile_sha256"]=profile["profile_sha256"]
    vector=json.loads(Path(__file__).with_name(MARKET_VECTOR_NAME).read_text())
    assert vector["economic_source"]==profile["research_source"]
    assert vector["economic_config_sha256"]==profile["economic_config_sha256"]
    assert vector["warmup_rows_per_asset"]==730
    DAY=86_400_000_000_000
    closed_ns=time.time_ns()//DAY*DAY
    shift_ns=closed_ns-vector["incoming_close_ms"]*1_000_000
    assert shift_ns%DAY==0
    warmup=[];band=[];previous=None
    for btc_row,sol_row in zip(vector["seed"]["BTC"],vector["seed"]["SOL"]):
        assert btc_row["open_time_ms"]==sol_row["open_time_ms"]
        open_ns=btc_row["open_time_ms"]*1_000_000+shift_ns
        close_ns=open_ns+DAY
        assert close_ns<closed_ns and (previous is None or close_ns==previous+DAY)
        previous=close_ns
        close=datetime.fromtimestamp(close_ns/1e9,timezone.utc)
        warmup.append(DailyBar(close-timedelta(days=1),close,close,float(btc_row["open"]),
            float(btc_row["close"]),float(sol_row["close"])))
        band.append((close_ns,float(btc_row["high"]),float(btc_row["low"])))
    assert len(warmup)==730 and previous+DAY==closed_ns
    result["warmup"]=dict(source="SYNTHETIC_FIXED_CONTROL_VALUES_ORIGIN_BYBIT_REFERENCE_NOT_HL_HISTORY",
        rows=730,vector_sha256=MARKET_VECTOR_SHA256,original_episode_id=vector["observed_first_entry_sizing"]["episode_id"],
        original_raw_sha256=vector["immutable_raw_sha256"],whole_UTC_shift_ns=shift_ns,
        closed_before_incoming_ns=closed_ns,seed_execution_events=0,
        original_quote_values_preserved=True,quote_timestamps_actual_LiveClock=True)
    hooks=LiveSubmissionHooks(runtime)
    flags = dict(profile["strategy_flags"])
    for k in ("research_c1_restore_dd", "research_regime_reentry_band", "research_btc_split_discount"):
        flags[k] = D(str(flags[k]))
    binding=binding_for_execution((HL_BTC.id,HL_SOL.id))
    result["live_data_binding"]=dict(venue=binding.venue,source_policy=binding.policy,
        binding_sha256=binding.identity,prices="SYNTHETIC_CONTROL_VECTOR_ONLY_NOT_HL_HISTORY")
    def bar(coin, aggregation):
        return binding.bar_type(0 if coin=="BTC" else 1,minute=aggregation==BarAggregation.MINUTE)
    strategy = Probe(WaveOverlayStrategyConfig(strategy_id="e4-c1-native-fixture", order_id_tag="E4C1",
        btc_id=HL_BTC.id, sol_id=HL_SOL.id,
        btc_bar_type=bar("BTC", BarAggregation.DAY), sol_bar_type=bar("SOL", BarAggregation.DAY),
        btc_signal_id=bar("BTC",BarAggregation.DAY).instrument_id,sol_signal_id=bar("SOL",BarAggregation.DAY).instrument_id,
        btc_mark_data_type=venue_mark_data_type(HL_BTC.id), sol_mark_data_type=venue_mark_data_type(HL_SOL.id),
        mark_client_id=ClientId("HYPERLIQUID"), active_seed=D("100"), candidate=candidate,
        entries_enabled=True, entries_gate=lambda:entry_gate_context._entries_enabled(),
        native_fill_sink=runtime.record_native_fill,
        seed_bars=tuple(warmup),research_band_daily_seed=tuple(band),
        live_start_approved=True,live_initial_capital_limit_usdc="0",
        live_initial_capital_policy=profile["initial_capital_policy"],
        max_mark_age_ns=120_000_000_000,
        event_sink=hooks.record_event,submission_sink=hooks,
        deposit_runtime=runtime, deposit_instance_id=runtime.owner, deposit_account_id=str(ACCOUNT),
        deposit_equity_reader=lambda s: s._validated_live_deposit_equity(),
        deposit_initialization_allowed=lambda: (strategy.recovery_confirmed or (runtime.c1_initialization() is not None and runtime.coherent_snapshot() and runtime.recovery_state()=="FLAT_RESTART")) and not runtime.all_submissions(),
        deposit_high_water_allowed=lambda:strategy._capital_high_water_allowed(),
        live_account_mode="unifiedAccount", live_equity_basis="HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1",
        execution_policy_hash="hl-mainnet-native-owned-v1", execution_policy_version="hl-mainnet-native-owned-v1",
        market_exit_time_in_force=TimeInForce.IOC, market_exit_reduce_only=True,
        **flags))
    strategy._input_readiness_preparation = True
    strategy._live_minute_bar_types = (bar("BTC", BarAggregation.MINUTE), bar("SOL", BarAggregation.MINUTE))
    strategy.attach_recovery_runtime(runtime)
    hooks.strategy=strategy
    ActualLiveHealthHolder,holder_abi=load_actual_live_health_holder(root.parent)
    holder=ActualLiveHealthHolder()
    holder.__dict__.update(strategy=strategy,state=runtime,active_c1=True,input_readiness=True,profile=profile,
        _refresh_warmup_readiness=lambda:None,gate=SimpleNamespace(attachable=True),node=None,
        feed=SimpleNamespace(status=lambda now:{name:{"state":"READY"} for name in ("synthetic-BTC-signal","synthetic-SOL-signal","synthetic-HL-quotes")}))
    assert all(hasattr(holder,name) for name in holder_abi["required_attributes"])
    entry_gate_context=holder
    runtime.bind_live_health(holder._live_health_current)
    assert runtime._live_health_provider.__self__ is holder
    result["actual_live_health_holder_abi"]=holder_abi
    # Only the finite synthetic feed/warmup transport readiness is supplied.
    # The actual worker gate still checks native money, DP, runtime health,
    # current recovery and actual Node.is_running. No gate=True substitution.
    if args.case == "B":
        strategy.on_load({KEY: runtime.strategy_checkpoint()[0]})
        assert runtime._fresh_c1_epoch_active is False
    else:
        # Same actual virgin preparation used by the worker. No checkpoint/H/rights seed.
        strategy._fresh_c1_init_intent = "INITIALIZE_FRESH_C1_EPOCH"

    config = TradingNodeConfig(environment=Environment.LIVE, trader_id="E4-C1-NATIVE-ACCEPTANCE",
        logging=LoggingConfig(log_level="ERROR"), exec_engine=LiveExecEngineConfig(reconciliation=False),
        exec_clients={"FAKE": LiveExecClientConfig(routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})))})
    node = None
    async def wait_for(predicate, reason):
        for _ in range(100):
            if predicate():
                return
            await asyncio.sleep(.01)
        raise AssertionError(reason)
    operative_observer=None
    async def gate(name, action):
        nonlocal operative_observer
        async def invoke():
            value=action()
            if hasattr(value,"__await__"):await value
        traced=args.case=="A" and runtime._fresh_c1_epoch_active
        if traced and operative_observer is None:operative_observer=make_operative_observer()
        try:
            if traced:
                operative_observer.phase=name
                with operative_observer:await invoke()
            else:await invoke()
            result["gates"][name] = dict(status="PASS")
        except Exception as exc:
            result["gates"][name] = dict(status="FAIL", reason=repr(exc), traceback=traceback.format_exc())
            if traced:
                try:result["operative_after_failure_snapshot"]=after_failure_snapshot()
                except BaseException as snapshot_error:
                    result["operative_after_failure_snapshot"]=dict(kind="AFTER_FAILURE_SNAPSHOT_UNAVAILABLE",
                        exception_type=type(snapshot_error).__name__)
            raise  # A failed prerequisite cannot be followed by further fixture commands.
        finally:
            if traced:result["operative_actual_decision_trace"]=operative_observer.receipt()
    def cloid(client):
        return str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(nautilus_pyo3.ClientOrderId(client)))
    async def settle():
        await asyncio.sleep(.05)
    def fills():
        return runtime.native_fill_details()
    market_marks={HL_BTC.id:D(vector["observed_first_entry_sizing"]["reference_wire_price"]),HL_SOL.id:D(vector["incoming"]["SOL"]["close"])}
    def state():
        positions = []
        notional = D(0)
        upnl = D(0)
        for p in node.cache.positions_open():
            mark = node.cache.instrument(p.instrument_id).make_price(market_marks[p.instrument_id])
            size = p.quantity.as_decimal() * (1 if p.is_long else -1)
            notional += abs(size) * mark.as_decimal()
            upnl += p.unrealized_pnl(mark).as_decimal()  # Native computation only.
            positions.append(dict(position=dict(coin="BTC", szi=str(size), entryPx=str(p.avg_px_open),
                leverage=dict(type="cross", value=10), positionValue=str(abs(size)*mark.as_decimal()),
                unrealizedPnl=str(p.unrealized_pnl(mark).as_decimal()))))
        # These are explicit synthetic venue cash inputs, never a custom PnL engine.
        # Unified money truth is the USDC spot/native total. Perp summary is NOT
        # combined with it; native UPNL remains a position diagnostic only.
        summary = dict(accountValue="0", totalRawUsd="0", totalMarginUsed="0", totalNtlPos=str(notional))
        return dict(assetPositions=positions, marginSummary=summary,
            crossMarginSummary=dict(summary), withdrawable="0")
    def raw_order(order):
        return dict(coin="BTC", oid=int(str(order.venue_order_id)), cloid=cloid(str(order.client_order_id)),
            side="B" if order.side == OrderSide.BUY else "A", origSz=str(order.quantity.as_decimal()),
            sz=str(order.quantity.as_decimal()-order.filled_qty.as_decimal()), reduceOnly=order.is_reduce_only,
            orderType="Limit", tif="Alo" if order.is_post_only else "Ioc" if order.time_in_force==TimeInForce.IOC else "Gtc",
            limitPx=str(order.price) if order.has_price else str(market_marks[order.instrument_id]), timestamp=order.ts_init//1_000_000)
    async def info(body, **unused):
        counts["synthetic_info_requests"] += 1
        kind = body["type"]
        if kind == "clearinghouseState": return state() if body.get("dex", "")=="" else {"assetPositions":[]}
        if kind == "userRole": return {"role":"user"} if body["user"]==ACCOUNT_REF else {"role":"agent","data":{"user":ACCOUNT_REF}}
        if kind == "userNonFundingLedgerUpdates":return []
        if kind == "userAbstraction": return "unifiedAccount"
        if kind == "spotClearinghouseState":
            return dict(balances=[dict(coin="USDC", token=0, total=str(client.total), hold=str(client.hold), entryNtl="0")])
        if kind == "userDexAbstraction": return False
        if kind == "perpDexs": return [None, {"name":"xyz"}]
        if kind == "activeAssetData":
            return dict(user=ACCOUNT_REF, coin=body["coin"], leverage=dict(type="cross", value=10),
                markPx=str(market_marks[HL_BTC.id if body["coin"]=="BTC" else HL_SOL.id]),
                availableToTrade=["1000","1000"],maxTradeSzs=["1","1"] if body["coin"]=="BTC" else ["100","100"])
        if kind == "frontendOpenOrders": return [] if body.get("dex","") else [raw_order(o) for o in node.cache.orders_open()]
        if kind == "orderStatus":
            found = [o for o in node.cache.orders() if cloid(str(o.client_order_id)) == body["oid"]]
            if not found or str(found[0].client_order_id) in client.info_unknown: return dict(status="unknownOid")
            order = found[0]
            if order.venue_order_id is None: return dict(status="unknownOid")
            return dict(status="order", order=dict(order=raw_order(order),
                status="filled" if order.status == OrderStatus.FILLED else "canceled" if order.is_closed else "open",
                statusTimestamp=max(order.ts_init, order.ts_last)//1_000_000))
        if kind == "userFillsByTime":
            rows = []
            for f in fills():
                ms = f["ts_event_ns"]//1_000_000
                if body["startTime"] <= ms <= body["endTime"]:
                    liquidity=f["liquidity_side"]
                    assert liquidity in ("MAKER","TAKER"),"PERSISTED_NATIVE_FILL_LIQUIDITY_UNKNOWN"
                    rows.append(dict(coin="BTC", oid=int(f["venue_order_id"]), tid=int(f["trade_id"]), time=ms,
                        side="B" if f["order_side"] == "BUY" else "A", sz=f["quantity"], px=f["price"],
                        fee=f["commission_amount"], feeToken="USDC", hash="0xfixture"+f["trade_id"], crossed=liquidity=="TAKER"))
            return rows
        raise AssertionError("UNEXPECTED_INFO:"+kind)

    async def emit_fill(order, tid, qty):
        liquidity=LiquiditySide.MAKER if order.is_post_only else LiquiditySide.TAKER
        current=node.cache.quote_tick(order.instrument_id)
        assert current is not None
        fill_price=order.price if order.is_post_only else current.ask_price if order.side==OrderSide.BUY else current.bid_price
        if order.is_post_only:
            quote=node.cache.quote_tick(order.instrument_id)
            assert quote is not None
            executable=quote.ask_price if order.side==OrderSide.BUY else quote.bid_price
            assert executable<=fill_price if order.side==OrderSide.BUY else executable>=fill_price
        client.generate_order_filled(order.strategy_id, order.instrument_id, order.client_order_id,
            order.venue_order_id, None, TradeId(tid), order.side, order.order_type,
            Quantity.from_str(qty), fill_price, HL_BTC.quote_currency, Money(D("0.00027"), USDC),
            liquidity, (client._clock.timestamp_ns()//1_000_000)*1_000_000)
        await settle()

    async def current_observation(expected_equity):
        rejected={}
        # Reuse only an actually current source observation; native timers may
        # already have completed this demand. Never change its timestamps/ID.
        def current():
            observation=strategy._last_live_input_observation
            if observation is None:rejected["getter_reason"]="PUBLICATION_NONE";return None
            if observation.equity!=D(expected_equity):rejected["getter_reason"]="PUBLISHED_EQUITY_MISMATCH";return None
            account=node.cache.account_for_venue(Venue("HYPERLIQUID"))
            if observation.native_account_event_id!=str(account.last_event.id):rejected["getter_reason"]="NATIVE_ACCOUNT_EVENT_MOVED";return None
            try:observation.require_current(now_ns=time.monotonic_ns(),revision=runtime.native_revision(),
                fill_epoch=strategy._c1_fill_epoch,ws_epoch=client._cm_ws_epoch)
            except IncompleteInfoReport as error:rejected["getter_reason"]=str(error)[:180];return None
            return observation
        observation=current()
        if observation is None:
            task=client._cm_money_task
            if task is not None and not task.done():await task
            observation=current()
        if observation is None:
            delay=max(0,client._cm_next_money_request-time.monotonic())
            assert delay<=6.1
            if delay:await asyncio.sleep(delay+.001)
            observation=current()
            if observation is None:
                accepted=client.request_portfolio_observation(strategy)
                task=client._cm_money_task
                # A normal native timer may have coalesced this same demand.
                assert accepted or (task is not None and not task.done()),"OBSERVATION_DEMAND_NOT_ADMITTED"
                await task
                observation=current()
        if observation is None:
            published=strategy._last_live_input_observation
            diagnostic=dict(source_reason=str(strategy._live_inputs_reason)[:240],getter=rejected,
                publication_present=published is not None,publication_type=type(published).__name__,
                dirty=bool(strategy._live_inputs_dirty),recovery_confirmed=bool(strategy.recovery_confirmed),
                ws_phase=str(client._cm_ws_phase)[:32],ws_failure=str(client._cm_ws_failure)[:120],
                updater_bound=callable(getattr(client,"_update_account_state",None)),
                native_revision=runtime.native_revision(),fill_epoch=strategy._c1_fill_epoch)
            result["observation_failure"]=diagnostic
            raise AssertionError("CURRENT_READONLY_OBSERVATION_UNAVAILABLE:"+json.dumps(diagnostic,sort_keys=True))
        assert strategy._validated_live_deposit_equity()==D(expected_equity)
        return observation

    def next_actual_full_bound():
        scope,_,native_orders,applied,_=client._cm_owned_scope()
        fingerprints={str(o.client_order_id):execution._native_order_fingerprint(o) for o in native_orders}
        cached,_,_,_=runtime.info_query_evidence(fingerprints,applied,anchor_proof=(
            scope.anchor_tid,scope.fill_anchor_ms,scope.fill_anchor_fingerprint)
            if scope.fill_anchor_ms is not None else None)
        fresh=len(scope.durable_orders)-len(cached)
        return execution.finite_generation_reservation(fresh,unified=True,
            dex_count=len(client._cm_unified_discovery["dex_names"]))

    def native_standing_baseline():
        positions=node.cache.positions_open()
        assert len(positions)==1 and positions[0].instrument_id==HL_BTC.id
        standing=[o for o in node.cache.orders_open() if o.instrument_id==HL_BTC.id and o.is_reduce_only
            and o.order_type==OrderType.LIMIT and o.venue_order_id is not None and not o.is_pending_cancel]
        held=positions[0].quantity.as_decimal()
        leaves=sum((o.quantity.as_decimal()-o.filled_qty.as_decimal() for o in standing),D(0))
        assert standing and leaves==held,"ACTUAL_STANDING_BASELINE_NOT_COMPLETE_NO_WAIT_ALLOWED"
        return standing,held

    async def await_actual_standing_ack(quote):
        started=time.monotonic()
        next_quote_driven=False
        before_increases={str(o.client_order_id) for o in node.cache.orders() if not o.is_reduce_only}
        last=[]
        while True:
            positions=node.cache.positions_open()
            held=positions[0].quantity.as_decimal() if len(positions)==1 and positions[0].instrument_id==HL_BTC.id else None
            rows={row["client_order_id"]:row for row in runtime.all_submissions()}
            candidates=[];last=[]
            for order in node.cache.orders():
                if order.instrument_id!=HL_BTC.id or not order.is_reduce_only or order.order_type!=OrderType.LIMIT:continue
                name=str(order.client_order_id);row=rows.get(name)
                event_names={type(event).__name__ for event in order.events}
                status=getattr(order.status,"name",str(order.status))
                terminal=status in ("DENIED","REJECTED")
                reason=next((getattr(event,"reason",None) for event in reversed(order.events)
                    if type(event).__name__ in ("OrderDenied","OrderRejected")),None)
                last.append(dict(client_order_id=name,status=status,durable_state=row.get("state") if row else None,
                    native_submitted="OrderSubmitted" in event_names,native_accepted="OrderAccepted" in event_names,
                    venue_order_id_present=order.venue_order_id is not None,account_bound=order.account_id is not None,
                    native_rejection_reason=str(reason)[:240] if reason is not None else None))
                if terminal:
                    result["standing_ack_boundary"]=dict(status="TERMINAL_REJECT",orders=last,
                        elapsed_seconds=time.monotonic()-started)
                    raise AssertionError("ACTUAL_STANDING_NATIVE_DENIED_OR_REJECTED")
                if (row is not None and row["state"]=="ACKED" and row["action"]=="BTC_REDUCE"
                    and "OrderSubmitted" in event_names and "OrderAccepted" in event_names
                    and order.venue_order_id is not None and order.account_id is not None
                    and not order.is_closed and not order.is_pending_cancel and not order.is_pending_update):
                    candidates.append(order)
            leaves=sum((order.quantity.as_decimal()-order.filled_qty.as_decimal() for order in candidates),D(0))
            # Source queues replacement TP at decision_ns+1; only a genuine NEXT quote releases it.
            old_protection=[o for o in node.cache.orders() if o.instrument_id==HL_BTC.id and o.is_reduce_only]
            queued_tp=any(item[0].action=="BTC_REDUCE" and str(item[0].reason or "").startswith("BTC_TP")
                for item in strategy._queued_intents)
            terminal_old=bool(old_protection) and all(o.is_closed and rows.get(str(o.client_order_id),{}).get("state")=="TERMINAL" for o in old_protection)
            canceled_old=any(getattr(o.status,"name",str(o.status))=="CANCELED" for o in old_protection)
            pending_protection=any(row["action"]=="BTC_REDUCE" and row["state"]!="TERMINAL" for row in rows.values())
            if (not next_quote_driven and queued_tp and terminal_old and canceled_old and not pending_protection
                and time.monotonic()-started<2):
                next_quote_driven=True
                await quote(HL_BTC.id,str(market_marks[HL_BTC.id]),half_spread=D("0"))
                assert {str(o.client_order_id) for o in node.cache.orders() if not o.is_reduce_only}==before_increases,"PROTECTION_DRAIN_MUST_NOT_CREATE_ENTRY"
                continue
            elapsed=time.monotonic()-started
            if candidates and held is not None and leaves==held and elapsed<=2:
                result["standing_ack_boundary"]=dict(status="ACTUAL_NATIVE_ACK_COMPLETE",orders=last,
                    elapsed_seconds=time.monotonic()-started,maximum_seconds=2,next_quote_driven=next_quote_driven)
                return
            elapsed=time.monotonic()-started
            if elapsed>=2:
                result["standing_ack_boundary"]=dict(status="ACK_TIMEOUT_NO_PROTECTED_WAIT",orders=last,
                    elapsed_seconds=elapsed,maximum_seconds=2,next_quote_driven=next_quote_driven)
                raise AssertionError("ACTUAL_STANDING_ACK_NOT_COMPLETE_WITHIN_2_SECONDS")
            await asyncio.sleep(min(.01,2-elapsed))

    async def protected_wait_for_actual_full(ordinary):
        assert client._cm_ws_failure is None
        # The P1 source route must park opening while the existing planner sends
        # genuine partial-position protection through the same public quote.
        await current_observation(str(client.total))
        before_increases=len([o for o in node.cache.orders() if not o.is_reduce_only])
        await ordinary["quote"](HL_BTC.id,vector["observed_first_entry_sizing"]["q1_bid"])
        assert len([o for o in node.cache.orders() if not o.is_reduce_only])==before_increases
        assert strategy._split_unfinished() and not strategy._split_parent["closed"]
        await await_actual_standing_ack(ordinary["quote"])
        standing,held=native_standing_baseline()
        wait_started_ns=time.monotonic_ns()
        started=time.monotonic();before=[list(row) for row in client._cm_inputs_budget.spent]
        counts["bounded_budget_waits"]+=1
        admitted=False;last_progress=started
        # At most124 real half-second checks; source forecasts use real NOW
        # only and may prune genuinely expired charges. Never query a future
        # clock, alter charge timestamps, reserve manually or reset the budget.
        for _ in range(124):
            now=time.monotonic();bound=next_actual_full_bound()
            try:strategy._current_owned_money();already_current=True
            except (ValueError,RuntimeError):already_current=False
            if already_current and client._cm_generation_started_ns>=wait_started_ns:
                admitted=True;break
            admitted=(client._cm_inputs_budget.remaining(now)>=bound and
                client._cm_inputs_budget.protects_held_schedule(now,additional=bound,
                    next_due=client._cm_next_money_request,sample_weight=client._cm_held_weight()))
            if admitted:break
            elapsed=now-started
            if elapsed>=60.9:break
            native_standing_baseline()
            # Public marks retain actual timestamps; no quote silently releases
            # parked opening, and no future bar/money generation is fabricated.
            if now-last_progress>=25:
                last_progress=now
                ns=strategy.clock.timestamp_ns()
                for iid,price in market_marks.items():strategy.on_data(VenueMark(iid,price,ns,ns))
                print(json.dumps(dict(progress="ACTUAL_PROTECTED_FULL_ADMISSION_WAIT",elapsed=elapsed)),flush=True)
            await asyncio.sleep(min(.5,60.9-elapsed))
        elapsed=time.monotonic()-started
        assert admitted and elapsed<=61,"PROTECTED_FULL_NOT_ADMITTED_WITHIN_APPROVED_WAIT"
        native_standing_baseline()
        result["early_protected_full_wait"]=dict(actual_seconds=elapsed,
            required_bound=bound,standing_order_ids=[str(o.client_order_id) for o in standing],
            native_held_baseline=str(held),before=before,after=[list(row) for row in client._cm_inputs_budget.spent],
            timestamps_patched=False,budget_reset=False)
        # The next full generation must actually succeed and carry a NEW span;
        # the old denied/expired generation never gains authority by waiting.
        return wait_started_ns

    async def full_for_split_increase(ordinary):
        try:strategy._current_owned_money();return
        except (ValueError,RuntimeError):pass
        task=client._cm_refresh_task
        if task is not None and not task.done():await task
        try:strategy._current_owned_money();return
        except (ValueError,RuntimeError):pass
        accepted=client.request_effect_parity_refresh()
        task=client._cm_refresh_task
        if accepted and task is not None:await task
        try:strategy._current_owned_money();return
        except (ValueError,RuntimeError):pass
        if client._cm_ws_failure is not None:
            import re
            reason=str(client._cm_ws_failure)
            result["full_refresh_failure"]=dict(phase="BEFORE_PROTECTED_BUDGET_WAIT",
                exception_type=type(client._cm_ws_failure).__name__,
                code=reason if re.fullmatch(r"[A-Z][A-Z0-9_]{0,179}",reason) else "NON_CODE_REDACTED",
                inner_failure=result.get("full_generation_inner_failure"),native_revision=runtime.native_revision())
        assert client._cm_ws_failure is None,"FULL_FAILED_FOR_REASON_OTHER_THAN_BUDGET"
        now=time.monotonic();bound=next_actual_full_bound()
        forecast=client._cm_inputs_budget.protects_held_schedule(now,additional=bound,
            next_due=client._cm_next_money_request,sample_weight=client._cm_held_weight())
        assert not forecast or client._cm_inputs_budget.remaining(now)<bound,"NON_BUDGET_FULL_FAILURE_MUST_NOT_BE_HIDDEN"
        waited_until=await protected_wait_for_actual_full(ordinary)
        task=client._cm_refresh_task
        if task is not None and not task.done():await task
        try:strategy._current_owned_money()
        except (ValueError,RuntimeError):
            assert client.request_effect_parity_refresh(),"REAL_FULL_RETRY_NOT_ADMITTED"
            await client._cm_refresh_task
        if not (client.recovery_healthy() and strategy.recovery_confirmed):
            result["full_refresh_failure"]=dict(reason_tag=str(client._cm_ws_failure)[:120],
                healthy=bool(client.recovery_healthy()),confirmed=bool(strategy.recovery_confirmed),
                native_revision=runtime.native_revision())
        assert client.recovery_healthy() and strategy.recovery_confirmed
        strategy._current_owned_money()
        assert client._cm_generation_started_ns>=waited_until
        assert time.monotonic_ns()-client._cm_generation_started_ns<=9_000_000_000

    def make_operative_observer():
        targets={}
        import inspect
        def add(value,label):
            value=inspect.unwrap(value) if value is not None else None
            code=getattr(value,"__code__",None)
            if code is not None:targets.setdefault(code,label)
        health=inspect.unwrap(runtime.health)
        assert health.__code__.co_name=="health"
        assert Path(health.__code__.co_filename).resolve()==root/"coinmaster/ops/hl_live_epoch.py"
        for name in ("_entries_enabled","_live_health_current"):
            add(getattr(holder,name),"actual_worker."+name)
        for cls in type(strategy).__mro__:
            for name in ("_entries_enabled","_entries_allowed","_feeds_fresh","_owned_chain_current",
                         "_current_owned_money","_validated_live_money","_validated_live_deposit_equity",
                         "_split_stop_requested","_submit_intent","_deposit_health","_deposit_check","_on_deposit_timer"):
                if name in cls.__dict__:add(cls.__dict__[name],cls.__name__+"."+name)
        for name in ("_live_context_current","_live_increase_headroom","_live_money_provider",
                     "_recovery_health","_live_input_ws_epoch"):
            add(getattr(strategy,name,None),"strategy_callback."+name)
        for obj,label,names in ((runtime,"runtime",("health",)),
            (client,"client",("_cm_context_current","recovery_healthy","_cm_transport_ok")),
            (client._cm_inputs_budget,"budget",("protects_held_schedule",))):
            for name in names:add(getattr(obj,name,None),label+"."+name)
        return ObservationalDecisionTrace(targets)

    def after_failure_snapshot():
        # AFTER failure: direct fields/read-only SQL, no guard re-evaluation.
        return dict(kind="AFTER_FAILURE_NOT_DECISION_TIME",
            fresh_process_marker=getattr(runtime,"_fresh_c1_epoch_active",None),
            provider_bound_to_actual_holder=(getattr(getattr(runtime,"_live_health_provider",None),"__self__",None) is holder),
            process_lock_present=getattr(runtime,"_process_lock_fd",None) is not None,
            account_lock_present=getattr(runtime,"_live_account_lock_fd",None) is not None,
            control=runtime.entry_control_state(),native_revision=runtime.native_revision(),
            financial_deadline_ns=getattr(strategy,"_live_financial_deadline_ns",None),
            financial_suspended=getattr(strategy,"_live_financial_suspended",None),
            recovery_confirmed=getattr(strategy,"recovery_confirmed",None),
            capital_basis_verified=getattr(strategy,"_capital_basis_verified",None),
            inputs_dirty=getattr(strategy,"_live_inputs_dirty",None),
            deposit_observed_equity=str(strategy._deposit.current_equity),
            deposit_observed_ns=strategy._deposit.observed_ns,
            deposit_high_water=str(strategy._deposit.high_water),
            deposit_latched=strategy._deposit.latched,
            deposit_daily_sample_missed=strategy._deposit.daily_sample_missed,
            deposit_storage_failed=strategy._deposit_storage_failed,
            last_actual_health=operative_observer.last_health if operative_observer is not None else None)

    async def paired_split_quote(quote,before,phase):
        # EXPLICIT_FIXTURE_GENUINE_PUBLICATION: preserve the ORIGINAL full proof.
        original_view=strategy._current_owned_money()[0]
        revision=runtime.native_revision();generation=client._cm_generation_started_ns
        deadline=strategy._live_financial_deadline_ns
        assert type(deadline) is int and time.monotonic_ns()<deadline,"ORIGINAL_FULL_DEADLINE_REQUIRED"
        assert original_view.native_revision==revision,"ORIGINAL_FULL_REVISION_REQUIRED"
        price=str(market_marks[HL_BTC.id])
        await quote(HL_BTC.id,price,half_spread=D("0"))  # Existing demand quote.
        new=[o for o in node.cache.orders() if str(o.client_order_id) not in before
            and not o.is_reduce_only and o.instrument_id==HL_BTC.id]
        witness=dict(kind="EXPLICIT_FIXTURE_GENUINE_PUBLICATION",phase=phase,
            existing_quote_already_created_entry=bool(new),extra_quotes=0)
        result.setdefault("explicit_paired_publication",[]).append(witness)
        if new:return  # Caller verifies count/quantity; legitimate post-submit revision may change.
        assert strategy._split_unfinished() and not strategy._split_parent["closed"],"SAME_PARENT_MUST_REMAIN_PARKED"
        native_standing_baseline()
        assert strategy._current_owned_money()[0] is original_view,"DEMAND_QUOTE_REVOKED_OR_CHANGED_FULL"
        assert (runtime.native_revision(),client._cm_generation_started_ns,strategy._live_financial_deadline_ns)==(revision,generation,deadline),"ORIGINAL_FULL_AUTHORITY_MOVED"
        task=client._cm_money_task
        assert task is not None,"SOURCE_CHEAP_PUBLICATION_NOT_ADMITTED"
        remaining=(deadline-time.monotonic_ns())/1_000_000_000
        assert remaining>0,"ORIGINAL_FULL_DEADLINE_EXPIRED"
        await asyncio.wait_for(asyncio.shield(task),timeout=remaining)
        current_view=strategy._current_owned_money()[0]
        strategy._validated_live_deposit_equity()
        observation=strategy._last_live_input_observation
        assert current_view is original_view and observation is not None,"CURRENT_PAIRED_PUBLICATION_REQUIRED"
        assert observation.native_revision==current_view.native_revision==revision==runtime.native_revision(),"PAIRED_REVISION_MOVED"
        assert client._cm_generation_started_ns==generation and strategy._live_financial_deadline_ns==deadline and time.monotonic_ns()<deadline,"ORIGINAL_FULL_AUTHORITY_EXPIRED_OR_MOVED"
        native_standing_baseline()
        # Since baseline4ca the entry predicate reads DP health without
        # observing cash. A23 (source5f10) relied on the old mutating predicate.
        # Deliver the ACTUAL existing production timer callback after genuine
        # paired cash publication, before the one next quote. No guard/state is
        # substituted, and UNKNOWN cannot be made healthy by this fixture.
        dp_before=dict(equity=None if strategy._deposit.current_equity is None else str(strategy._deposit.current_equity),
            observed_ns=strategy._deposit.observed_ns,high_water=str(strategy._deposit.high_water),
            latched=strategy._deposit.latched,daily_sample_missed=strategy._deposit.daily_sample_missed,
            storage_failed=strategy._deposit_storage_failed)
        marker=runtime.c1_initialization();saved_h=strategy._deposit.high_water
        command_counts=(counts["synthetic_submit_commands"],counts["synthetic_cancel_commands"])
        health_before=strategy._deposit_health()  # Exact read-only reason witness.
        strategy._on_deposit_timer(None)  # Production callback uses actual paired native cash.
        actual_equity=strategy._validated_live_deposit_equity()
        assert strategy._deposit.current_equity==actual_equity
        assert strategy._deposit.high_water==saved_h and runtime.c1_initialization()==marker
        assert (counts["synthetic_submit_commands"],counts["synthetic_cancel_commands"])==command_counts
        assert strategy._deposit.latched==dp_before["latched"] and strategy._deposit.daily_sample_missed==dp_before["daily_sample_missed"]
        assert (runtime.native_revision(),client._cm_generation_started_ns,strategy._live_financial_deadline_ns)==(revision,generation,deadline)
        assert time.monotonic_ns()<deadline and strategy._deposit_health()
        dp_after=dict(equity=str(strategy._deposit.current_equity),observed_ns=strategy._deposit.observed_ns,
            high_water=str(strategy._deposit.high_water),latched=strategy._deposit.latched,
            daily_sample_missed=strategy._deposit.daily_sample_missed,storage_failed=strategy._deposit_storage_failed)
        witness.update(paired_guards_current=True,original_generation_preserved=True,
            original_deadline_preserved=True,revision=revision,extra_quotes=1,
            deposit_observation=dict(callback="WaveOverlayStrategy._on_deposit_timer",event="SYNTHETIC_TIMER_DELIVERY_AFTER_REAL_PAIRED_PUBLICATION",
                health_before=health_before,health_after=strategy._deposit_health(),before=dp_before,after=dp_after,
                native_equity=str(actual_equity),HWM_and_initial_seed_preserved=True,synthetic_commands_unchanged=list(command_counts)))
        await quote(HL_BTC.id,price,half_spread=D("0"))  # ONE genuine NEXT quote.

    async def complete_actual_split(ordinary):
        quote=ordinary["quote"];entry=ordinary["entry"]
        p=strategy._split_parent
        assert p is not None and not p["closed"] and strategy._split_unfinished()
        first_remaining=entry.quantity.as_decimal()-entry.filled_qty.as_decimal()
        assert first_remaining>0
        before={str(o.client_order_id) for o in node.cache.orders()}
        await full_for_split_increase(ordinary)
        await paired_split_quote(quote,before,"FIRST_REMAINING")
        new=[o for o in node.cache.orders() if str(o.client_order_id) not in before
            and not o.is_reduce_only and o.instrument_id==HL_BTC.id]
        assert len(new)==1 and new[0].quantity.as_decimal()==first_remaining
        assert not strategy._split_parent["closed"],"FINANCIAL_PENDING_STOPPED_REAL_PARENT"
        await emit_fill(new[0],"103",str(new[0].quantity.as_decimal()))
        await full_for_split_increase(ordinary)
        before={str(o.client_order_id) for o in node.cache.orders()}
        await paired_split_quote(quote,before,"SECOND_CHILD")
        children=[o for o in node.cache.orders() if str(o.client_order_id) not in before and not o.is_reduce_only]
        assert len(children)==1
        child=children[0]
        assert child.order_type==OrderType.LIMIT and child.is_post_only and child.time_in_force==TimeInForce.GTC
        assert child.quantity.as_decimal()==p["quantity"]-p["filled"]
        # Native-rounded child price is the source; no hand-coded discount/lot.
        await quote(HL_BTC.id,str(child.price.as_decimal()),half_spread=D("0"))
        await emit_fill(child,"104",str(child.quantity.as_decimal()))
        assert p["closed"] and p["filled"]==p["quantity"] and not p["cancelled"]
        assert not strategy._split_unfinished()
        assert runtime.applied_fill_ids()==frozenset({"101","102","103","104"})
        assert runtime.strategy_checkpoint()[0]==strategy.on_save()[KEY]

    async def actual_mvp_target_protection(ordinary):
        # Full native fill104 asks the source to cancel prior partial-position TP.
        replan=tuple(strategy._split_parent.get("partial_tp_replan_pending",()))
        if replan:
            await wait_for(lambda:all(any(str(o.client_order_id)==name and o.is_closed for o in node.cache.orders())
                and any(row["client_order_id"]==name and row["state"]=="TERMINAL" for row in runtime.all_submissions())
                for name in replan),"ACTUAL_PARTIAL_TP_CANCEL_ACK_REQUIRED_BEFORE_FULL_REPLAN")
        await current_observation(str(client.total))
        # This genuine quote invokes the normal producer after its cancel barrier.
        await ordinary["quote"](HL_BTC.id,str(market_marks[HL_BTC.id]),half_spread=D("0"))
        source_intents=[i for i,_,_ in strategy._queued_intents]+list(strategy._pending_by_order.values())
        targets=list({i.id:i for i in source_intents if i.action=="BTC_REDUCE" and i.limit_price is not None}.values())
        assert targets,"ACTUAL_SOURCE_QUEUED_OR_WORKING_POSITIVE_TARGET_REQUIRED"
        side=strategy._domain.episode.side
        target=min(targets,key=lambda i:D(str(i.limit_price))) if side==1 else max(targets,key=lambda i:D(str(i.limit_price)))
        assert target.reason=="BTC_TP3" and target.episode_id==strategy._domain.episode.id
        assert HL_BTC.make_qty(D(str(target.quantity))).as_decimal()==node.cache.positions_open()[0].quantity.as_decimal()
        await current_observation(str(client.total))
        before={str(o.client_order_id) for o in node.cache.orders()}
        threshold=HL_BTC.make_price(D(str(target.limit_price))).as_decimal()
        await ordinary["quote"](HL_BTC.id,str(threshold),half_spread=D("0"))
        # Reuse the actual source-owned TP: a resting GTC is not converted into a duplicate IOC.
        owned=[o for o in node.cache.orders() if o.is_reduce_only and not o.is_closed
            and o.instrument_id==HL_BTC.id and getattr(strategy._pending_by_order.get(str(o.client_order_id)),"id",None)==target.id]
        assert len(owned)==1,"EXACTLY_ONE_ACTUAL_SOURCE_TP_REQUIRED"
        catchup=owned[0]
        assert catchup.side==(OrderSide.SELL if side==1 else OrderSide.BUY)
        if catchup.order_type==OrderType.LIMIT:
            assert catchup.time_in_force==TimeInForce.GTC and catchup.is_post_only
            assert catchup.price.as_decimal()==threshold
        else:
            assert catchup.order_type==OrderType.MARKET and catchup.time_in_force==TimeInForce.IOC and not catchup.is_post_only
        await wait_for(lambda:catchup.venue_order_id is not None and catchup.status==OrderStatus.ACCEPTED
            and {"OrderSubmitted","OrderAccepted"}<={type(e).__name__ for e in catchup.events},
            "ACTUAL_SOURCE_TP_NATIVE_ACK_REQUIRED")
        assert catchup.quantity.as_decimal()==HL_BTC.make_qty(D(str(target.quantity))).as_decimal()
        positive_count=sum(level>0 for level in strategy._domain.episode.wave_levels)
        assert positive_count==1
        lots=int(catchup.quantity.as_decimal()/HL_BTC.size_increment.as_decimal())
        partial_lots=lots//2
        assert partial_lots>0 and partial_lots<lots
        filled=D(partial_lots)*HL_BTC.size_increment.as_decimal()
        remaining=D(lots-partial_lots)*HL_BTC.size_increment.as_decimal()
        assert remaining*market_marks[HL_BTC.id]>=HL_BTC.min_notional.as_decimal()
        assert D((lots-partial_lots)//4)*HL_BTC.size_increment.as_decimal()*D("66000")>=HL_BTC.min_notional.as_decimal()
        if catchup.time_in_force==TimeInForce.IOC:
            client.hold_cancel_ack.add(str(catchup.client_order_id))
        await emit_fill(catchup,"201",str(filled))
        if catchup.time_in_force==TimeInForce.IOC:
            strategy.cancel_order(catchup)
            await settle()
            client.generate_order_canceled(catchup.strategy_id,catchup.instrument_id,catchup.client_order_id,
                catchup.venue_order_id,client._clock.timestamp_ns())
            await wait_for(lambda:catchup.is_closed,"ACTUAL_PARTIAL_IOC_TERMINAL_ACK_REQUIRED")
            assert catchup.is_closed and node.cache.positions_open()
            await current_observation(str(client.total))
            await ordinary["quote"](HL_BTC.id,vector["observed_first_entry_sizing"]["q1_bid"])
            await await_actual_standing_ack(ordinary["quote"])
        else:
            # A healthy source-owned GTC retains its genuine unfilled leaves.
            assert not catchup.is_closed and not catchup.is_pending_cancel
            assert catchup.quantity.as_decimal()-catchup.filled_qty.as_decimal()==node.cache.positions_open()[0].quantity.as_decimal()
            await current_observation(str(client.total))
        standing=[o for o in node.cache.orders_open() if o.is_reduce_only and o.order_type==OrderType.LIMIT]
        assert standing,"SOURCE_DID_NOT_REPLAN_ACTUAL_STANDING_POSITIVE_REMAINDER"
        assert all(o.venue_order_id is not None and o.is_post_only for o in standing)
        held=node.cache.positions_open()[0].quantity.as_decimal()
        coverage=sum((o.quantity.as_decimal()-o.filled_qty.as_decimal() for o in standing),D(0))
        assert coverage==held,"STANDING_NATIVE_REMAINDER_DOES_NOT_COVER_ACTUAL_HELD_BASELINE"
        result["actual_target_protection"]=dict(catchup_order_id=str(catchup.client_order_id),
            source_order_type=catchup.order_type.name,source_time_in_force=catchup.time_in_force.name,
            source_post_only=catchup.is_post_only,expected_native_liquidity=("MAKER" if catchup.is_post_only else "TAKER"),
            planner_limit_price=str(target.limit_price),native_target_price=str(threshold),
            standing_order_ids=[str(o.client_order_id) for o in standing],standing_quantity=str(coverage),
            native_held_baseline=str(held),positive_levels=positive_count,injected_fakevenue_events=True)

    async def actual_c1_cut_and_pre_d1_denial(ordinary):
        quote=ordinary["quote"];position=node.cache.positions_open()[0]
        # Explicit synthetic reported venue equity, never computed custom PnL.
        client.total=D("60")
        adverse=D("54000") if position.is_long else D("66000")
        await quote(HL_BTC.id,str(adverse))
        await current_observation("60")
        for order in node.cache.orders_open():client.hold_cancel_ack.add(str(order.client_order_id))
        before={str(o.client_order_id) for o in node.cache.orders()}
        await quote(HL_BTC.id,str(adverse))
        t=strategy._c1_state
        assert t is not None and t["instrument"]==HL_BTC.id and t["state"]=="CUT_RESOLVING"
        assert t["cut_lots"]==t["held_lots"]//4 and t["cut_lots"]>0
        assert not any(str(o.client_order_id) not in before and o.time_in_force==TimeInForce.IOC for o in node.cache.orders())
        pending=[o for o in node.cache.orders_open() if o.is_reduce_only]
        assert pending and all(str(o.client_order_id) in client.seen_cancels for o in pending)
        for order in pending:
            client.generate_order_canceled(order.strategy_id,order.instrument_id,order.client_order_id,
                order.venue_order_id,client._clock.timestamp_ns())
        await wait_for(lambda:all(o.is_closed and str(o.client_order_id) not in strategy._pending_by_order
            and any(row["client_order_id"]==str(o.client_order_id) and row["state"]=="TERMINAL" for row in runtime.all_submissions()) for o in pending)
            and not node.cache.orders_open() and not node.cache.orders_inflight(),
            "ACTUAL_C1_CANCEL_ACK_BARRIER_REQUIRED")
        await current_observation("60")
        await quote(HL_BTC.id,str(adverse))
        cuts=[o for o in node.cache.orders() if str(o.client_order_id) not in before and o.time_in_force==TimeInForce.IOC]
        assert len(cuts)==1 and cuts[0].is_reduce_only
        cut=cuts[0]
        await wait_for(lambda:cut.venue_order_id is not None and cut.status==OrderStatus.ACCEPTED
            and {"OrderSubmitted","OrderAccepted"}<={type(e).__name__ for e in cut.events},
            "ACTUAL_C1_CUT_NATIVE_ACK_REQUIRED")
        assert cut.quantity.as_decimal()==D(t["cut_lots"])*t["step"]
        assert cut.quantity.as_decimal()*adverse>=HL_BTC.min_notional.as_decimal()
        await emit_fill(cut,"301",str(cut.quantity.as_decimal()))
        assert t["state"]=="HELD" and t["cut_filled"]==t["cut_lots"] and t["credit"]>0
        await current_observation("60")
        before_increases=counts["synthetic_submit_commands"]
        now=strategy.clock.timestamp_ns();checkpoint=strategy._c1_checkpoint
        assert not strategy._c1_btc_postcut_d1_allowed(t,checkpoint,now)
        await quote(HL_BTC.id,str(adverse))
        assert not t["restore_submitted"]
        # Requeued owned TP reductions may be emitted; no opening restoration.
        assert not any(not o.is_reduce_only and o.ts_init>=now for o in node.cache.orders())
        result["pre_d1_denial"]=dict(native_decision_ns=now,last_cut_fill_ns=t["last_cut_fill_ns"],
            new_D1_supplied=False,future_bars_supplied=False,restore_submitted=False)

    async def actual_dp55_close_and_flat(ordinary):
        # Use actual scheduler/provider at both sides of exact45% retained floor.
        client.total=D("45.01")
        await current_observation("45.01")
        assert strategy._deposit_check() and not strategy._deposit.latched
        before={str(o.client_order_id) for o in node.cache.orders()}
        await wait_for(lambda:not node.cache.orders_inflight()
            and all(row["state"] in ("ACKED","TERMINAL") for row in runtime.all_submissions()),
            "EARLIER_NATIVE_SUBMITS_MUST_ACK_BEFORE_DP_LOST_ACK_INJECTION")
        client.drop_next_ack=True
        client.total=D("45")
        await current_observation("45")
        assert not strategy._deposit_check() and strategy._deposit.latched
        await wait_for(lambda:any(str(o.client_order_id) in strategy._deposit_exit_orders
            and str(o.client_order_id) not in before for o in node.cache.orders()),"ACTUAL_DP_MARKET_EXIT_DID_NOT_DISPATCH")
        closes=[o for o in node.cache.orders() if str(o.client_order_id) in strategy._deposit_exit_orders
            and str(o.client_order_id) not in before]
        assert len(closes)==1
        await resolve_actual_dp_close_lost_ack(closes[0],ordinary["quote"])
        # Public lifecycle hook finishes only actual native/durable terminalflat.
        strategy.post_market_exit()
        assert strategy._deposit.exit_state=="TRIPPED_FLAT"
        assert not runtime.pending_submissions() and all(r["state"]=="TERMINAL" for r in runtime.all_submissions())
        assert runtime.strategy_checkpoint()[0]==strategy.on_save()[KEY]
        # Paused terminal-flat native minute inputs exercise the production
        # boundary/strategy/closed-clock/durable checkpoint chain without adding
        # an economic decision or another engine. Pending clocks survive B.
        received=strategy.clock.timestamp_ns();minute=60_000_000_000
        minute_started=time.monotonic()
        print(json.dumps(dict(progress="ACTUAL_480_M1_NATIVE_CHECKPOINT_BURST_START",started_ns=time.time_ns())),flush=True)
        for coin in ("BTC","SOL"):
            for opened in range(closed_ns-240*minute,closed_ns,minute):
                price=Price.from_str(str(vector["incoming"][coin]["close"]))
                raw=Bar(bar(coin,BarAggregation.MINUTE),price,price,price,price,Quantity.from_str("0"),opened,opened)
                normalized=normalize_hl_bar(raw,received_ns=received,historical=True)
                strategy.on_historical_data(normalized)
        minute_wall=time.monotonic()-minute_started
        print(json.dumps(dict(progress="ACTUAL_480_M1_NATIVE_CHECKPOINT_BURST_COMPLETE",wall_seconds=minute_wall)),flush=True)
        state=strategy._live_signal_clock_state
        assert sum(row["hours"]==4 for row in state["pending_h4"])==2
        assert runtime.strategy_checkpoint()[0]==strategy.on_save()[KEY]
        result["native_minute_boundary"]=dict(rows=480,wall_seconds=minute_wall,per_bar_seconds=minute_wall/480,venue=binding.venue,source_policy=binding.policy,
            timestamp_input="OPEN",timestamp_runtime="CLOSE",actual_receipt_ns=received,
            economic_decisions=0,pending_h4=2,saved_clock_is_not_freshness=True)
        persist_actual_paused_flat_restart_proof()

    async def resolve_actual_dp_close_lost_ack(close,current_quote):
        # The ACTUAL DP pipeline must produce this order. The fixture never
        # creates/submits a close or invents a pending/forced-close owner.
        name=str(close.client_order_id)
        assert strategy._deposit.latched and name in strategy._deposit_exit_orders
        assert close.is_reduce_only and close.time_in_force==TimeInForce.IOC
        assert close.venue_order_id is None and not close.is_closed
        deadline=time.monotonic()+2
        while not ("OrderSubmitted" in {type(e).__name__ for e in close.events}
            and name in client.seen_commands and name in client.lost):
            if time.monotonic()>=deadline:
                raise AssertionError("ACTUAL_DP_SUBMITTED_UNKNOWN_ACK_BOUNDARY_REQUIRED")
            await asyncio.sleep(.01)
        assert client.seen_commands.count(name)==1
        assert "OrderAccepted" not in {type(e).__name__ for e in close.events}
        assert close.venue_order_id is None and not close.is_closed
        assert any(row["client_order_id"]==name and row["state"]=="SUBMITTING" for row in runtime.all_submissions())
        assert strategy._deposit_exit_orders=={name}
        before=counts["synthetic_submit_commands"]
        await current_quote(HL_BTC.id,str(market_marks[HL_BTC.id]))
        await current_quote(HL_BTC.id,str(market_marks[HL_BTC.id]))
        assert counts["synthetic_submit_commands"]==before and strategy._deposit_exit_orders=={name}
        # An actual changed fake transport epoch invokes production revocation;
        # late native ACK/fill callbacks still reconcile an already-owned close.
        client.socket_epoch+=1
        assert not client.recovery_healthy()
        assert client._cm_ws_failure is not None and not strategy.recovery_confirmed
        try:strategy._current_owned_money()
        except RuntimeError as error:assert str(error)=="RECOVERY_NOT_CONFIRMED"
        else:raise AssertionError("WS_REVOKED_OWNED_MONEY_AUTHORITY_REMAINED")
        try:strategy._validated_live_money()
        except ValueError as error:assert str(error)=="LIVE_MONEY_UNCONFIRMED"
        else:raise AssertionError("WS_REVOKED_LIVE_MONEY_AUTHORITY_REMAINED")
        assert strategy._management_dispatch_enabled is False
        certificate=strategy._management_certificate
        if certificate is not None:assert not certificate.transport_healthy()
        assert counts["synthetic_submit_commands"]==before
        client.oid+=1
        client.generate_order_accepted(close.strategy_id,close.instrument_id,close.client_order_id,
            VenueOrderId(str(client.oid)),client._clock.timestamp_ns())
        await settle()
        await wait_for(lambda:close.venue_order_id is not None,"ACTUAL_DP_LATE_ACK_REQUIRED_BEFORE_FILL")
        await emit_fill(close,"9001",str(close.quantity.as_decimal()))
        await wait_for(lambda:close.is_closed and not node.cache.positions_open(),"ACTUAL_DP_NATIVE_FILL_FLAT_REQUIRED")
        assert close.is_closed and not node.cache.positions_open()
        assert not node.cache.orders_open() and not node.cache.orders_inflight()
        assert not strategy.recovery_confirmed and counts["synthetic_submit_commands"]==before
        assert strategy._deposit.latched
        result["gates"]["actual_DP_close_lost_ACK_no_retry_reconnect_late_native_flat_no_resume"]=dict(status="PASS")

    def persist_actual_paused_flat_restart_proof():
        assert strategy._deposit.latched and strategy._deposit.limit_percent==55
        assert not node.cache.positions_open() and not node.cache.orders_open() and not node.cache.orders_inflight()
        assert not runtime.pending_submissions()
        runtime.entry_control_command("pause-new-entries","fixture-A-terminal-pause")
        checkpoint=runtime.strategy_checkpoint()
        assert checkpoint is not None and checkpoint[0]==strategy.on_save()[KEY]
        assert runtime.c1_initialization() is not None
        account=node.cache.account_for_venue(Venue("HYPERLIQUID"))
        terminal_venue=args.artifact_dir/"terminal-fake-venue.json"
        actual_total=account.balance_total(USDC).as_decimal()
        actual_hold=account.balance_locked(USDC).as_decimal()
        assert actual_total==client.total and actual_hold==client.hold
        with terminal_venue.open("x") as stream:
            json.dump(dict(partial=False,balance=str(actual_total),hold=str(actual_hold)),stream,sort_keys=True)
        proof=dict(source_commit=args.expected_source,fixture_sha256=result["fixture_sha256"],
            terminal_fake_venue_sha256=digest(terminal_venue.read_bytes()),
            checkpoint_sha256=digest(checkpoint[0]),canonical_checkpoint=json.loads(checkpoint[0]),
            initialization_marker=runtime.c1_initialization(),
            high_water=str(strategy._deposit.high_water),applied_fill_ids=sorted(runtime.applied_fill_ids()),
            last_reported_native_total=str(account.balance_total(USDC).as_decimal()),
            persisted_deposit=runtime.deposit_protection_state(instance_id=runtime.owner,account_id=str(ACCOUNT)))
        with (args.artifact_dir/"restart-proof.json").open("x") as stream:
            json.dump(proof,stream,sort_keys=True,indent=2)
        result["restart_proof_sha256"]=digest((args.artifact_dir/"restart-proof.json").read_bytes())

    try:
        counts["nodes_constructed"] += 1
        node = TradingNode(config=config, loop=asyncio.get_running_loop())
        entry_gate_context.node=node
        node.add_exec_client_factory("FAKE", Factory)
        node.build()
        node.cache.add_instrument(HL_BTC)
        node.cache.add_instrument(HL_SOL)
        node.trader.add_strategy(strategy)
        client = clients[0]
        assert str(HL_BTC.quote_currency) == "USDC" and str(HL_SOL.quote_currency) == "USDC"
        assert str(HL_BTC.settlement_currency) == "USDC" and str(HL_SOL.settlement_currency) == "USDC"
        if args.case == "A":
            scope = NativeLiveRecoveryScope(ACCOUNT_REF, "", time.time_ns()//1_000_000, None, (), frozenset({"BTC", "SOL"}))
            execution.read_info_http = info  # Only the network edge is fake.
            client.configure_info_boundary(scope, SingleAttemptInfoTransport(testnet=False, timeout=1), runtime.applied_fill_ids)
            client._cm_runtime = runtime
            client._cm_account_context=dict(agent_address="0x"+"2"*40,account_sha256=account_sha,signer_sha256=digest(b"synthetic-agent"))
            bind_clean_flat_live_handover(client, strategy, runtime, manage_only=False, monitor_interval_secs=60)
            # Source public metadata qualifier, fake unsigned role transport,
            # actual shared140 accounting and original monotonic provenance.
            # Not a real key/fingerprint/credential qualification claim.
            await client.qualify_account_context()
            assert client._cm_context_current()
            result["synthetic_component_context"]=dict(weight=140,
                original_verified_at_ns=client._cm_account_context["verified_at_ns"],
                real_credential_qualification=False)
        else:
            # Paused restart receives real native account events, but does not
            # manufacture missing historical native orders or release recovery.
            scope = durable_management_scope(runtime, ACCOUNT_REF, "", cloid)
            execution.read_info_http = info
            client.configure_info_boundary(scope, SingleAttemptInfoTransport(testnet=False, timeout=1), runtime.applied_fill_ids)
            client._cm_runtime=runtime;client._cm_strategy=strategy;client._cm_unified=True;client._cm_inputs_enabled=True
        await node.kernel.start_async()
        await settle()
        def startup_check():
            requests = [r for r in startup if r[0] == "request" and "MINUTE" in r[1]]
            assert len(requests) == 2, startup
            assert len([r for r in startup if r[0] == "subscribe" and "MINUTE" in r[1]]) == 2
            for _, _, kw in requests:
                assert int(kw["end"].timestamp()*1e9) == strategy._live_history_cutoff_ns
                assert kw["start"] < kw["end"]
        await gate("native_startup_closed_minute_requests", startup_check)
        if args.case == "B":
            expected = json.loads((args.artifact_dir/"restart-proof.json").read_text())
            def restart_check():
                assert expected["source_commit"]==args.expected_source
                assert expected["fixture_sha256"]==result["fixture_sha256"]
                prior=json.loads((args.artifact_dir/"A-result.json").read_text())
                assert digest((args.artifact_dir/"restart-proof.json").read_bytes())==prior["restart_proof_sha256"]
                persisted=runtime.strategy_checkpoint()
                assert persisted is not None
                loaded=strategy.on_save()[KEY]
                actual_document=json.loads(loaded)
                # Compare actual canonical serializer to actual A checkpoint,
                # never construct H/rights/clock state in the B fixture.
                assert digest(persisted[0])==expected["checkpoint_sha256"]==digest(loaded)
                assert actual_document==expected["canonical_checkpoint"]
                assert runtime.c1_initialization()==expected["initialization_marker"]
                dp=runtime.deposit_protection_state(instance_id=runtime.owner,account_id=str(ACCOUNT))
                assert dp==expected["persisted_deposit"]
                assert strategy.deposit_projection()["drawdown_limit_percent"]==55
                assert str(strategy._deposit.high_water)==expected["high_water"]
                assert strategy._deposit.latched is True
                assert strategy._fresh_c1_init_intent is None
                assert runtime.applied_fill_ids()==frozenset(expected["applied_fill_ids"])
                assert runtime.entry_control_state()=="PAUSED"
                assert not runtime.pending_submissions()
                assert not node.cache.positions_open() and not node.cache.orders_open() and not node.cache.orders_inflight()
                account=node.cache.account_for_venue(Venue("HYPERLIQUID"))
                assert account is not None and account.last_event is not None
                assert account.calculate_account_state is False
                assert str(account.balance_total(USDC).as_decimal())==expected["last_reported_native_total"]
                assert strategy.recovery_confirmed is False and strategy._management_certificate is None
                assert strategy._management_dispatch_enabled is False and not strategy._quote_ns
                assert strategy._last_live_input_observation is None and strategy._live_c1_input is None
                assert not strategy._entries_enabled()
                assert strategy._owned_effect_chain is None
                assert strategy._live_financial_deadline_ns is None
                assert counts["synthetic_submit_commands"]==counts["synthetic_cancel_commands"]==0
            await gate("paused_flat_restart_actual_canonical_H55_latch_rights_clocks_no_autoresume",restart_check)
            def incompatible_source_checkpoint_denied_without_financial_reset():
                before=(runtime.strategy_checkpoint(),runtime.c1_initialization(),runtime.deposit_protection_state(
                    instance_id=runtime.owner,account_id=str(ACCOUNT)),strategy._live_signal_clock_state.copy())
                foreign=json.loads(runtime.strategy_checkpoint()[0])
                foreign["policy_sha256"]=digest(b"BYBIT_NATIVE_CONFIRMED_LAST_1M_UTC240_H4_ACTUAL_AVAILABILITY_V1")
                try:strategy.on_load({KEY:json.dumps(foreign,sort_keys=True,separators=(",",":")).encode()})
                except ValueError as error:assert str(error)=="RECOVERY_POLICY_IDENTITY_MISMATCH"
                else:raise AssertionError("FOREIGN_SOURCE_CHECKPOINT_ACCEPTED")
                assert before==(runtime.strategy_checkpoint(),runtime.c1_initialization(),runtime.deposit_protection_state(
                    instance_id=runtime.owner,account_id=str(ACCOUNT)),strategy._live_signal_clock_state)
                assert str(strategy._deposit.high_water)==expected["high_water"] and strategy._deposit.latched
                assert counts["synthetic_submit_commands"]==counts["synthetic_cancel_commands"]==0
            await gate("foreign_bybit_source_checkpoint_denied_preserve_money_seed_HWM_watermarks",incompatible_source_checkpoint_denied_without_financial_reset)
            async def restart_cannot_reinitialize_or_grant_freshness():
                before=(digest(strategy.on_save()[KEY]),runtime.c1_initialization(),runtime.deposit_protection_state(
                    instance_id=runtime.owner,account_id=str(ACCOUNT)))
                try:strategy.initialize_fresh_live_deposit_protection("fixture-B-forbidden-reset")
                except (ValueError,RuntimeError):pass
                else:raise AssertionError("EXISTING_H_REINITIALIZED")
                try:strategy._validated_live_money()
                except (ValueError,RuntimeError):pass
                else:raise AssertionError("RESTART_SAVED_MONEY_GRANTED_FRESHNESS")
                assert before==(digest(strategy.on_save()[KEY]),runtime.c1_initialization(),runtime.deposit_protection_state(
                    instance_id=runtime.owner,account_id=str(ACCOUNT)))
                assert counts["synthetic_submit_commands"]==counts["synthetic_cancel_commands"]==0
            await gate("restart_existing_H_reset_denied_and_saved_money_has_no_authority",restart_cannot_reinitialize_or_grant_freshness)
            return

        async def fresh_init():
            assert strategy._post_drain_task is not None
            await strategy._post_drain_task  # Actual native on_start invokes the production full verifier.
            marker = runtime.c1_initialization()
            assert marker is not None and D(marker["initial_equity"]) == D("100")
            assert runtime._fresh_c1_epoch_active is True
            assert marker["history_anchor_ms"] == client._cm_scope.anchor_ms
            assert strategy._c1_peak == strategy._next_peak == D("100")
            assert strategy._c1_state is None and not strategy._c1_intents and not strategy._pending_by_order
            assert runtime.strategy_checkpoint()[0] == strategy.on_save()[KEY]
            assert runtime.entry_control_state() == "PAUSED" and strategy._management_dispatch_enabled is False
            assert not node.cache.positions_open() and not node.cache.orders_open() and not node.cache.orders_inflight()
            zero_fill_scope = durable_management_scope(runtime, ACCOUNT_REF, "", cloid)
            assert zero_fill_scope.anchor_ms == marker["history_anchor_ms"]
            initial_marker.update(marker)
            # A genuine current observation supplies the REAL production DP reader.
            await current_observation("100")
            assert strategy._validated_live_deposit_equity() == D("100")
        initial_marker = {}
        await gate("actual_virgin_native_flat_INIT_atomic_once_and_original_anchor", fresh_init)
        if not initial_marker:
            raise RuntimeError("FRESH_NATIVE_INIT_NOT_QUALIFIED_NO_FIXTURE_SEEDS")
        async def initialize_dp_control():
            assert strategy._deposit.high_water is None  # Never reset an existing anchor.
            strategy.initialize_fresh_live_deposit_protection("fixture-initialize-virgin-dp55")
            assert strategy._deposit.high_water == D("100") and strategy._deposit.threshold == D("45")
        await gate("public_virgin_DP55_wrapper_from_native_equity_never_existing_H_reset", initialize_dp_control)
        async def funding_evidence_never_native_cash_posts():
            account=node.cache.account_for_venue(Venue("HYPERLIQUID"))
            before=(account.balance_total(USDC).as_decimal(),account.balance_free(USDC).as_decimal(),account.last_event.id)
            prior=runtime.evidence_cursor("userFunding")
            now_ms=time.time_ns()//1_000_000
            row=dict(time=now_ms,hash="0xsynthetic-native-fixture-funding",delta=dict(coin="BTC",usdc="0.01"))
            cursor=dict(end_ms=now_ms)
            runtime.record_funding_page([row],expected_cursor=prior,next_cursor=cursor,complete=True)
            first=runtime.funding_projection()
            runtime.record_funding_page([row],expected_cursor=cursor,next_cursor=cursor,complete=True)
            assert runtime.funding_projection()==first
            assert D(first["funding"])==D("0.01")
            assert before==(account.balance_total(USDC).as_decimal(),account.balance_free(USDC).as_decimal(),account.last_event.id)
        await gate("synthetic_funding_evidence_dedup_native_reported_cash_never_posted_twice",funding_evidence_never_native_cash_posts)
        async def ordinary_entry_from_closed_daily_public_callbacks():
            # Canonical seed is configuration-only. No native order/fill callback
            # occurred during warmup, and no domain/ownership state is seeded.
            assert counts["synthetic_submit_commands"]==0 and strategy._domain.episode is None
            assert len(strategy._bars)==730 and not runtime.all_submissions()
            runtime.entry_control_command("resume-new-entries","fixture-active-callbacks")
            available=strategy.clock.timestamp_ns()
            for coin,iid in (("BTC",HL_BTC.id),("SOL",HL_SOL.id)):
                row=vector["incoming"][coin]
                strategy.on_data(VenueMark(iid,D(row["close"]),closed_ns,available))
            for coin,iid in (("BTC",strategy.config.btc_signal_id),("SOL",strategy.config.sol_signal_id)):
                row=vector["incoming"][coin]
                # Same native OPEN-stamped HL input boundary as the stock
                # transport; deterministic prices are synthetic controls only.
                raw=Bar(bar(coin,BarAggregation.DAY),Price.from_str(str(row["open"])),
                    Price.from_str(str(row["high"])),Price.from_str(str(row["low"])),
                    Price.from_str(str(row["close"])),Quantity.from_str("0"),closed_ns-DAY,available)
                strategy.on_bar(normalize_hl_bar(raw,received_ns=available))
            # Historic prices are signal-only. Current HL marks and quotes are
            # explicitly synthetic current observations, not shifted fill times.
            async def current_quote(iid,mid,*,half_spread=D("1")):
                now=strategy.clock.timestamp_ns()
                market_marks[iid]=D(mid)
                strategy.on_data(VenueMark(iid,D(mid),now,now))
                instrument=node.cache.instrument(iid)
                tick=QuoteTick(iid,instrument.make_price(D(mid)-half_spread),instrument.make_price(D(mid)+half_spread),
                    instrument.make_qty(D('1')),instrument.make_qty(D('1')),now,now)
                node.kernel.data_engine.process(tick)  # Public native market-data route updates the quote cache.
                strategy.on_quote_tick(tick)
                await settle()
            await current_quote(HL_SOL.id,vector["incoming"]["SOL"]["close"],half_spread=D("0"))
            await current_quote(HL_BTC.id,vector["observed_first_entry_sizing"]["reference_wire_price"],half_spread=D("0"))
            await current_quote(HL_BTC.id,vector["observed_first_entry_sizing"]["q1_bid"],half_spread=D("0"))
            entries=[o for o in node.cache.orders() if (strategy._pending_by_order.get(str(o.client_order_id)) is not None
                and strategy._pending_by_order[str(o.client_order_id)].action=="BTC_ENTRY")]
            assert len(entries)==1 and entries[0].order_type==OrderType.MARKET
            entry=entries[0]
            assert entry.time_in_force==TimeInForce.IOC and not entry.is_reduce_only
            assert str(entry.client_order_id) in client.seen_commands
            assert runtime.all_submissions() and strategy._domain.episode is not None
            assert entry.quantity.as_decimal()*market_marks[HL_BTC.id]>=HL_BTC.min_notional.as_decimal()
            assert strategy._domain.episode.side==-1 and sum(x>0 for x in strategy._domain.episode.wave_levels)==1
            assert entry.venue_order_id is not None
            return entry,current_quote
        ordinary={}
        async def ordinary_gate():
            ordinary["entry"],ordinary["quote"]=await ordinary_entry_from_closed_daily_public_callbacks()
        await gate("ACTIVE_same_core_public_closed_D1_q0_q1_actual_native_entry",ordinary_gate)
        async def actual_partial_cancel_late_fill_duplicate():
            entry=ordinary["entry"];step=HL_BTC.size_increment.as_decimal()
            lots=int(entry.quantity.as_decimal()/step)
            first_lots=lots*2//5;late_lots=lots//5
            assert first_lots>0 and late_lots>0 and first_lots+late_lots<lots
            await emit_fill(entry,"101",str(D(first_lots)*step))
            client.hold_cancel_ack.add(str(entry.client_order_id))
            strategy.cancel_order(entry)
            await settle()
            assert client.seen_cancels.count(str(entry.client_order_id))==1
            await emit_fill(entry,"102",str(D(late_lots)*step))
            client.generate_order_canceled(entry.strategy_id,entry.instrument_id,entry.client_order_id,
                entry.venue_order_id,client._clock.timestamp_ns())
            await settle()
            assert entry.is_closed and entry.filled_qty.as_decimal()==D(first_lots+late_lots)*step
            assert len(node.cache.positions_open())==1
            position=node.cache.positions_open()[0]
            assert position.quantity.as_decimal()==entry.filled_qty.as_decimal()
            assert runtime.applied_fill_ids()==frozenset({"101","102"}) and len(fills())==2
            assert runtime.strategy_checkpoint()[0]==strategy.on_save()[KEY]
            event=next(e for e in entry.events if str(getattr(e,"trade_id",""))=="102")
            before=(position.quantity.as_decimal(),len(fills()),runtime.native_revision())
            node.kernel.exec_engine.process(event)
            await settle()
            assert before==(position.quantity.as_decimal(),len(fills()),runtime.native_revision())
            assert counts["synthetic_submit_commands"]==1
            assert strategy._split_parent is not None and strategy._split_unfinished()
            ordinary["filled_first_lots"]=first_lots+late_lots
        await gate("ordinary_partial_IOC_late_cancel_fill_duplicate_native_checkpoint",actual_partial_cancel_late_fill_duplicate)
        if not PARTIAL_PARENT_LIFECYCLE_QUALIFIED:
            raise RuntimeError("STATIC_PARTIAL_PARENT_FINANCIAL_PENDING_GATE_OPEN_NO_NATIVE_GO")
        await gate("actual_split_remaining_and_postonly_second_child_complete",lambda:complete_actual_split(ordinary))
        await gate("actual_source_positive_TP_partial_fill_and_standing_protection",lambda:actual_mvp_target_protection(ordinary))
        await gate("actual_C1_cancel_ACK_quarter_cut_and_before_D1_restore_denial",lambda:actual_c1_cut_and_pre_d1_denial(ordinary))
        await gate("actual_DP55_provider_latch_native_close_and_terminal_flat",lambda:actual_dp55_close_and_flat(ordinary))
    finally:
        if node is not None:
            await node.kernel.stop_async()
            node.kernel.dispose()
        runtime.close()
        socket.socket.connect, urllib.request.urlopen = old_connect, old_urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("A", "B"), required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--root-native-go",action="store_true",help="Root-only reviewed-source authorization plus new exact ledger claim")
    args = parser.parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    result = dict(schema="e4-c1-connected-native-acceptance-v1", case=args.case,
        source_commit=args.expected_source, status="FAIL", matching_proof=False,
        gates={}, counts=dict(nodes_constructed=0, external_network_attempts=0,
            synthetic_submit_commands=0, synthetic_cancel_commands=0, query_account_commands=0,
            synthetic_info_requests=0,synthetic_native_spot_reads=0,bounded_budget_waits=0), started_ns=time.time_ns())
    try:
        pins, fixture_hash, updater_abi = preflight(args)
        result.update(source_pins=pins, fixture_sha256=fixture_hash,market_vector_sha256=MARKET_VECTOR_SHA256,preimport_updater_abi=updater_abi)
        async def bounded_run():
            remaining=MAX_CHILD_SECONDS-(time.time_ns()-result["started_ns"])/1e9
            if remaining<=0:raise RuntimeError(f"WHOLE_CHILD_WALL_CAP_{MAX_CHILD_SECONDS}S")
            await asyncio.wait_for(run(args,result),timeout=remaining)
        asyncio.run(bounded_run())
        assert result["counts"]["nodes_constructed"] == 1
        assert result["counts"]["external_network_attempts"] == 0
        if result["gates"] and all(g["status"] == "PASS" for g in result["gates"].values()):
            result["status"] = "PASS"
    except BaseException as exc:
        result.update(error=repr(exc), traceback=traceback.format_exc())
    result["finished_ns"] = time.time_ns()
    result["whole_child_wall_seconds"]=(result["finished_ns"]-result["started_ns"])/1e9
    (args.artifact_dir/(args.case+"-result.json")).write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(dict(case=args.case, status=result["status"], counts=result["counts"],
                         failed_gates=[n for n,g in result["gates"].items() if g["status"] != "PASS"])))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
