import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).parents[1]
def helper():
    tree=ast.parse((ROOT/"coinmaster/research/native_fixture.py").read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="quote")
    values=dict(Decimal=Decimal,InstrumentId=object,QuoteTick=lambda *a:a,Price=SimpleNamespace(from_str=str),Quantity=SimpleNamespace(from_str=str),SOL_PERP=SimpleNamespace(id="SOL"))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),"actual_quote_source","exec"),values)
    return values["quote"]

@pytest.mark.parametrize("asset,precision,expected",[("BTC",3,"1000.000"),("SOL",1,"1000.0"),("BTC",5,"1000.00000"),("SOL",2,"1000.00")])
def test_actual_quote_size_precision(asset,precision,expected):
    q=helper();actual=q(asset,"100","101",123,size_precision=precision)
    assert actual[3:5]==(expected,expected)
    assert Decimal(expected)==1000
    if (asset,precision) in (("BTC",3),("SOL",1)):
        assert actual==q(asset,"100","101",123)

@pytest.mark.parametrize("bad",[-1,True,1.5])
def test_invalid_precision_denied(bad):
    with pytest.raises(ValueError):helper()("BTC","100","101",123,size_precision=bad)

def test_both_native_research_producers_forward_actual_metadata():
    tree=ast.parse((ROOT/"coinmaster/research/native_baseline.py").read_text())
    producers=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in ("stressed_quote","native_quote")]
    assert len(producers)==2
    for fn in producers:
        calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="quote"]
        assert len(calls)==1
        assert any(k.arg=="size_precision" and ast.unparse(k.value)=="instrument.size_precision" for k in calls[0].keywords)
