"""Constructor-free contract checks for dust fixture; no engine calls."""
import ast
from decimal import Decimal as D
from pathlib import Path
import unittest
from coinmaster.research import cm2_fixture_dust as f
from coinmaster.strategy.cm2_execution import order_plan

class DustFixtureContractTest(unittest.TestCase):
    def test_explicit_interval_and_unknown_rejection(self):
        f.validate_request({"fixture_id":f.FIXTURE_ID,"start_ns":f.START_NS,"end_ns":f.END_NS})
        for key in ("fixture_id","start_ns","end_ns"):
            request={"fixture_id":f.FIXTURE_ID,"start_ns":f.START_NS,"end_ns":f.END_NS}
            request[key]=None
            with self.assertRaises(ValueError):f.validate_request(request)
        self.assertEqual(f.END_NS-f.START_NS,20*f.MINUTE_NS)

    def test_native_constructor_is_one_deferred_source_site(self):
        tree=ast.parse(Path(f.__file__).read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="BacktestEngine"]
        self.assertEqual(len(calls),1)
        self.assertFalse(any(isinstance(n,(ast.Import,ast.ImportFrom)) and
            any(a.name.startswith("nautilus") for a in n.names) for n in tree.body))
        self.assertIn("NOT_ALPHA",f.SCOPE)

    def test_mirrored_phase_plans_use_production_shrink(self):
        for sign in (D(1),D(-1)):
            p=order_plan(actual=sign*f.OPEN_QTY,target=D(0),pending=D(0),unknown=False,
                price=f.PRICE,step=D(".01"),min_qty=D(".01"),min_notional=D(10),
                max_child=f.CAP_QTY*f.PRICE)
            self.assertEqual(p.signed_quantity,-sign*f.EXPECTED_CHILD)
            self.assertEqual(sign*f.OPEN_QTY+p.signed_quantity,sign*D(".08"))
            close=order_plan(actual=sign*D(".08"),target=D(0),pending=D(0),unknown=False,
                price=f.PRICE,step=D(".01"),min_qty=D(".01"),min_notional=D(10),max_child=D(1000))
            self.assertEqual(close.signed_quantity,-sign*D(".08"))

    def test_schedule_keeps_native_cases_separate_and_dust_recoverable(self):
        self.assertEqual(len({row[0] for row in f.SCRIPT}),len(f.SCRIPT))
        self.assertEqual([r[1] for r in f.SCRIPT if r[4]],["LONG_PARTIAL_CHILD","SHORT_PARTIAL_CHILD"])
        self.assertEqual(f.sol_price(13),D(150))
        self.assertEqual(f.sol_price(14),D(100))
        self.assertEqual(f.sol_price(15),D(150))
        self.assertLess(max(r[0] for r in f.SCRIPT),20)
        self.assertEqual(len([r for r in f.SCRIPT if r[1].endswith("OPEN")]),5)

if __name__=="__main__":unittest.main()
