"""Actual audit consumers with split/interleaved rows; no native constructors."""
import ast
from datetime import datetime,UTC
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N

SOURCE=Path(__file__).parents[1]/"coinmaster/strategy/wave_overlay.py"


def actual():
    cls=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="WaveOverlayStrategy")
    names={"_entry_sizing_audit_for","_activate_selective_sol_rights"}
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    env=dict(QuoteTick=object)
    definition=ast.ClassDef(name="Actual",bases=[],keywords=[],body=methods,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[definition],type_ignores=[])),str(SOURCE),"exec"),env)
    obj=env["Actual"]()
    now=datetime(2024,9,2,tzinfo=UTC);ns=int(now.timestamp()*1_000_000_000)
    ep=N(id="episode-a",side=1,btc_deferred_right_reference_price=D(100),btc_deferred_right_touched=False,
         btc_initial_qty=7,btc_omitted_zero_levels={0},sol_right_fraction={0:1},sol_rights=set(),sol_right_decision_index={})
    obj._domain=N(episode=ep);obj.config=N(deposit_runtime=None,research_v0_selective_lifecycle_repairs=True,research_v0_execution_repairs=True)
    obj._forced_close_reason=None;obj._liquidating=False;obj._mandatory_sol_exit=None
    obj._bars=[N(close_time=now)];obj._current_btc=N(ts_event=ns);obj._current_sol=N(ts_event=ns)
    obj._last_accepted_session=ns;obj._latest_seen_session=ns
    advances=[];warnings=[];obj._advance_current_day=lambda:advances.append(True)
    obj.log=N(warning=warnings.append)
    row=dict(episode_id="episode-a",intent_id="parent-a",reference_btc_qty="10",
        net_submitted_btc_qty="5",confirmed_native_entry_qty="0")
    plan=dict(row,branch="PASSIVE_NET_ZERO_LEVELS",reference_wire_price="100",sol_right_activations=[])
    child=dict(row)
    foreign=dict(row,episode_id="episode-b",intent_id="parent-b")
    gate=dict(episode_id="episode-a",intent_id="parent-a",E="100",admission_allowed=True)
    obj.entry_sizing_audit=[plan,child,foreign,gate]
    tick=N(ts_event=ns,bid_price=N(as_decimal=lambda:D(101)),ask_price=N(as_decimal=lambda:D(102)))
    return obj,ep,plan,child,foreign,gate,tick,advances,warnings


def update_confirmed_from_actual_callback(obj):
    cls=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="WaveOverlayStrategy")
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="_apply_confirmed_domain_fill")
    statement=next(n for n in method.body if isinstance(n,ast.If) and "research_v0_execution_repairs" in ast.unparse(n.test) and "entry_sizing_audit" in ast.unparse(n.test))
    env=dict(self=obj,intent=N(action="BTC_ENTRY",episode_id="episode-a",id="parent-a"))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[statement],type_ignores=[])),str(SOURCE),"exec"),env)


def test_selective_activation_uses_own_plan_not_later_child_other_parent_or_gate():
    s,ep,plan,child,foreign,gate,tick,advances,warnings=actual()
    s._activate_selective_sol_rights(tick)
    assert ep.sol_rights=={0} and ep.sol_right_decision_index=={0:0}
    assert plan["sol_right_activations"]==[dict(timestamp_ns=str(tick.ts_event),levels=[0],confirmed_native_entry_qty="7")]
    assert "sol_right_activations" not in child and "sol_right_activations" not in foreign and "sol_right_activations" not in gate
    assert advances==[True] and not warnings
    s._activate_selective_sol_rights(tick)
    assert len(plan["sol_right_activations"])==1 and advances==[True]


def test_actual_confirmed_qty_updates_matching_plan_and_latest_same_parent_child_only():
    s,ep,plan,child,foreign,gate,*_=actual()
    update_confirmed_from_actual_callback(s)
    assert plan["confirmed_native_entry_qty"]==child["confirmed_native_entry_qty"]=="7"
    assert foreign["confirmed_native_entry_qty"]=="0"
    assert "confirmed_native_entry_qty" not in gate
    assert len(s.entry_sizing_audit)==4  # Ordinary evidence remains intact.


def test_ordinary_sizing_stays_supported_and_missing_plan_never_fabricates_schema():
    s,ep,plan,child,foreign,gate,tick,advances,warnings=actual()
    s.entry_sizing_audit=[child,foreign,gate]
    update_confirmed_from_actual_callback(s)
    assert child["confirmed_native_entry_qty"]=="7" and foreign["confirmed_native_entry_qty"]=="0"
    s._activate_selective_sol_rights(tick)
    assert ep.sol_rights=={0} and advances==[True]
    assert len(warnings)==1 and warnings[0].startswith("SELECTIVE_SOL_RIGHT_AUDIT_PLAN_UNKNOWN:episode-a:")
    assert all("sol_right_activations" not in row for row in s.entry_sizing_audit)
