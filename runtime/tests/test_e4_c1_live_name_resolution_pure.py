"""Static live-origin names and real stdlib import resolution; no native imports."""
import ast
import builtins
import hashlib
from pathlib import Path
import symtable
from types import SimpleNamespace
import pytest
from coinmaster.domain.wave_overlay import Candidate

ROOT=Path(__file__).parents[1]
LIVE_ORIGINS=(
    'coinmaster/ops/hl_live_worker.py','coinmaster/ops/hl_live_execution.py',
    'coinmaster/ops/hl_live_money.py','coinmaster/ops/hl_live_epoch.py',
    'coinmaster/ops/hl_info_receipt.py','coinmaster/ops/hl_live_profile.py',
    'coinmaster/ops/hl_unified_account.py','coinmaster/ops/hl_unified_instruments.py',
    'coinmaster/ops/hl_qualified_reports.py','coinmaster/ops/live_recovery.py',
    'coinmaster/strategy/live_recovery.py','coinmaster/strategy/wave_overlay.py',
    'coinmaster/strategy/split_cover.py','coinmaster/strategy/residual_recovery.py',
    'coinmaster/strategy/c1_inputs.py','coinmaster/domain/wave_overlay.py',
    'tests/test_live_native_report_recovery.py','tests/test_hl_stageg_sandbox_lifecycle.py',
)

def undefined_global_names(path):
    # stdlib-only F821-equivalent global lookup for these fixed18 Python origins.
    # No source-module import, exec, native extension, constructors or network.
    table=symtable.symtable(path.read_text(),str(path),'exec')
    bound={symbol.get_name() for symbol in table.get_symbols()
           if symbol.is_imported() or symbol.is_assigned() or symbol.is_namespace()}
    allowed=bound|set(dir(builtins))|{'__file__','__name__','__package__','__doc__','__annotations__','__builtins__'}
    failures=[]
    def visit(scope):
        for symbol in scope.get_symbols():
            if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in allowed:
                failures.append((scope.get_name(),symbol.get_name()))
        for child in scope.get_children():visit(child)
    visit(table)
    return sorted(set(failures))

@pytest.mark.parametrize('relative',LIVE_ORIGINS)
def test_actual_live_origin_has_no_undefined_global_name(relative):
    assert undefined_global_names(ROOT/relative)==[]

def policy_namespace(*,omit_path_import=False):
    source=ROOT/'coinmaster/strategy/live_recovery.py'
    body=[]
    stdlib={'__future__','asyncio','hashlib','json','math','time','dataclasses','datetime','decimal','pathlib'}
    for node in ast.parse(source.read_text()).body:
        if isinstance(node,ast.Import) and all(alias.name.split('.')[0] in stdlib for alias in node.names):
            body.append(node)
        elif isinstance(node,ast.ImportFrom) and (node.module in stdlib or node.module=='coinmaster.ops.stage_g_config'):
            if omit_path_import and node.module=='pathlib':continue
            body.append(node)
        elif isinstance(node,ast.FunctionDef) and node.name in ('_encode','recovery_policy_hash'):
            body.append(node)
    namespace={'__file__':str(source)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(source),'exec'),namespace)
    return namespace

def test_policy_hash_resolves_Path_from_actual_module_import_not_injected_global():
    namespace=policy_namespace()
    assert namespace['Path'].__module__=='pathlib'
    value=namespace['recovery_policy_hash'](SimpleNamespace(research_residual_recovery=True),Candidate())
    assert len(value)==64 and all(ch in '0123456789abcdef' for ch in value)
    # Demonstrates the regression catches the A2 binding error, unlike injected-Path fixtures.
    missing=policy_namespace(omit_path_import=True)
    assert 'Path' not in missing
    with pytest.raises(NameError,match='Path'):
        missing['recovery_policy_hash'](SimpleNamespace(research_residual_recovery=True),Candidate())

def test_fixed_static_checker_detects_missing_Path_without_loading_module(tmp_path):
    path=tmp_path/'missing.py'
    path.write_text('def policy():\n    return Path(__file__)\n')
    assert undefined_global_names(path)==[('policy','Path')]
