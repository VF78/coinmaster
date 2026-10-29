"""Regression for the selected CLI versus direct native API cap discrepancy."""
import ast
from dataclasses import asdict, replace
from pathlib import Path
import sys
import pytest
from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research.effective_config import effective_research_candidate


def test_selected_archived_control_applies_original_cap_without_other_changes():
    archived = replace(Candidate(), max_parent_notional=10_000_000.0)
    effective = effective_research_candidate(archived, selective_lifecycle_repairs=True)
    expected = asdict(archived);expected["max_parent_notional"] = 30_000_000.0
    assert asdict(effective) == expected
    assert archived.max_parent_notional == 10_000_000.0


def test_unselected_candidate_preserves_control():
    archived = replace(Candidate(), max_parent_notional=10_000_000.0)
    assert effective_research_candidate(archived) is archived


def test_selected_effective_candidate_is_value_idempotent():
    once = effective_research_candidate(selective_lifecycle_repairs=True)
    assert effective_research_candidate(once, selective_lifecycle_repairs=True) == once


@pytest.mark.parametrize("entry, flag", [("run_native_diagnostic", "research_v0_selective_lifecycle_repairs"), ("run_research_v0_repairs_cli", "selective_lifecycle_repairs")])
def test_actual_entrypoint_candidate_assignment_uses_same_effective_factory(entry, flag):
    source = Path(__file__).parents[1] / "coinmaster/research/native_baseline.py"
    function = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == entry)
    statement = next(n for n in function.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "candidate" for t in n.targets))
    # Execute the actual candidate assignment only; never execute its engine function.
    for enabled, cap in [(False, 10_000_000.0), (True, 30_000_000.0)]:
        archived = replace(Candidate(), max_parent_notional=10_000_000.0)
        values = dict(research_sol_capital_staging_a=False,research_sol_market_budget_b=False,initial_active_seed=10000,candidate=archived, config={"candidate": asdict(archived)}, Candidate=Candidate, effective_research_candidate=effective_research_candidate, **{flag: enabled})
        exec(compile(ast.fix_missing_locations(ast.Module(body=[statement], type_ignores=[])), "actual_entrypoint_candidate_AST", "exec"), values)
        assert values["candidate"].max_parent_notional == cap
