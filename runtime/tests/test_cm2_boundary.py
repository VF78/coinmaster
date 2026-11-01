"""Native class methods only on plain fakes; no engine/account constructors."""
from collections import deque
from decimal import Decimal as D
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace as N
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_policy import Features,Snapshot,Config,State
from coinmaster.strategy.cm2_execution import ExecutionLimits
from coinmaster.research.cm2_runner import acquire_shared_lease,register_attempt,CM2RunConfig,worker_process_spec

class AdapterBoundaryTests(unittest.TestCase):
    def test_same_available_quote_is_not_executable(self):
        self_fake=N(_quotes={},_owned={},policy_state=State(),_restore_failed=False,
                    config=N(policy=Config(),trading_start_open_ns=0,terminal_close_at_ns=1000),
                    current_features=Features(100,100,True))
        self_fake._snapshot=lambda now: (_ for _ in ()).throw(RuntimeError("EXECUTION_BOUNDARY_ENTERED"))
        native_now=[100]
        self_fake.clock=N(timestamp_ns=lambda:native_now[0])
        price=N(as_decimal=lambda:D(100))
        CM2Strategy.on_quote_tick(self_fake,N(instrument_id="BTC",ts_event=100,bid_price=price,ask_price=price))
        native_now[0]=101
        with self.assertRaisesRegex(RuntimeError,"EXECUTION_BOUNDARY_ENTERED"):
            CM2Strategy.on_quote_tick(self_fake,N(instrument_id="BTC",ts_event=101,bid_price=price,ask_price=price))
    def test_previous_turnover_only(self):
        fake=N(_turnover={"BTC":deque(((100,D(1000)),(200,D(2000))),maxlen=2)},
               config=N(limits=ExecutionLimits(D("1e100"))))
        self.assertEqual(CM2Strategy._child_capacity(fake,"BTC",200),D(10))
        self.assertEqual(CM2Strategy._child_capacity(fake,"BTC",201),D(20))
        self.assertEqual(CM2Strategy._child_capacity(fake,"SOL",201),D(0))
    def test_aggregate_tier_crossing_rejected(self):
        class Tier:
            def margin_for(self,iid,quantity,now):
                if iid=="BTC" and quantity>D(10):
                    raise ValueError("SELECTED_LEVERAGE_EXCEEDS_AGGREGATE_TIER")
                return quantity*D(10),D(0),D(100)
        account=N(base_currency="USDC",balance_free=lambda currency:N(currency="USDC",as_decimal=lambda:D(10000)),
            balance_locked=lambda c:N(currency="USDC",as_decimal=lambda:D(0)),balance_total=lambda c:N(currency="USDC",as_decimal=lambda:D(10000)),
            margin_init=lambda i:None,margin_maint=lambda i:None,
            total_margin_init=lambda c:N(currency="USDC",as_decimal=lambda:D(0)),total_margin_maint=lambda c:N(currency="USDC",as_decimal=lambda:D(0)))
        fake=N(clock=N(timestamp_ns=lambda:1),policy_state=State(),config=N(policy=Config(),btc_id="BTC",sol_id="SOL",margin_policy=Tier(),limits=ExecutionLimits(D(1000)),exit_fee_rate=D(".000432")),
               cache=N(account_for_venue=lambda venue:account,instrument=lambda iid:N(settlement_currency="USDC")),_orders=lambda iid:[],pre_submit_gate_blocks=[])
        # IDs need venue for native boundary, while preserving deterministic keys.
        class ID(str):
            venue="SIM"
        btc=ID("BTC")
        s=Snapshot(D(10000),D(9),D(0),D(100),D(10))
        fake.config.btc_id=btc;fake.config.sol_id=ID("SOL")
        fake._latest_marks={i:N(ts_event=1) for i in (fake.config.btc_id,fake.config.sol_id)}
        fake._snapshot=lambda now:s
        self.assertFalse(CM2Strategy._admit(fake,btc,D(2),D(100),s,1))
        self.assertIn("AGGREGATE_TIER",fake.pre_submit_gate_blocks[-1]["reason"])

class DispatchTests(unittest.TestCase):
    def test_actual_child_flags_environment_and_own_cwd(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"own-artifacts"
            request={"artifact_dir":str(output),"_request_path":str(Path(td)/"request.json")}
            os.environ["CM2_TEST_SECRET_SENTINEL"]="must-not-inherit"
            try:
                command,env,cwd=worker_process_spec(request,99,"abc")
            finally:
                del os.environ["CM2_TEST_SECRET_SENTINEL"]
            self.assertEqual(command[1:3],["-B","-s"])
            self.assertNotIn("CM2_TEST_SECRET_SENTINEL",env)
            probe="import os,sys,json,site; print(json.dumps(dict(env=dict(os.environ),cwd=os.getcwd(),no_user_site=sys.flags.no_user_site,dont_write_bytecode=sys.flags.dont_write_bytecode,enable_user_site=site.ENABLE_USER_SITE)))"
            raw=subprocess.check_output([command[0],*command[1:3],"-c",probe],env=env,cwd=cwd,text=True)
            actual=json.loads(raw)
            self.assertTrue(actual["no_user_site"])
            self.assertTrue(actual["dont_write_bytecode"])
            self.assertFalse(actual["enable_user_site"])
            self.assertEqual(actual["cwd"],str(output.resolve()))
            self.assertEqual(actual["env"]["HOME"],str(output.resolve()/".worker-home"))
            self.assertNotIn("CM2_TEST_SECRET_SENTINEL",actual["env"])
            for name,value in (("TZ","UTC"),("PYTHONNOUSERSITE","1"),("PYTHONDONTWRITEBYTECODE","1"),
                               ("OMP_NUM_THREADS","1"),("OPENBLAS_NUM_THREADS","1"),("MKL_NUM_THREADS","1")):
                self.assertEqual(actual["env"][name],value)

    def test_busy_lease_consumes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"shared.lock"
            with acquire_shared_lease(path):
                with self.assertRaises(BlockingIOError): acquire_shared_lease(path)
            self.assertEqual(list(Path(td).iterdir()),[path])
    def test_child_inherited_fd_survives_parent_close(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"shared.lock"
            shared=acquire_shared_lease(path)
            child=subprocess.Popen([sys.executable,"-c","import sys; sys.stdin.read()"],stdin=subprocess.PIPE,
                                    pass_fds=(shared.fileno(),))
            try:
                shared.close()
                with self.assertRaises(BlockingIOError): acquire_shared_lease(path)
            finally:
                child.communicate(timeout=5)
            with acquire_shared_lease(path): pass
    def test_budget_failed_starts_count_and_replay_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ledger=root/"trials.jsonl";budget=root/"budget.json"
            budget.write_text(json.dumps({"scope_version":"v1","total_physical_cap":2,"stages":{"anchors":{"cap":1}}}))
            request={"budget_path":str(budget),"attempt_ledger":str(ledger),"run_id":"a","stage":"anchors"}
            register_attempt(request,{})
            with self.assertRaisesRegex(ValueError,"EXISTS"): register_attempt(request,{})
            with self.assertRaisesRegex(ValueError,"BUDGET"): register_attempt({**request,"run_id":"b"},{})
            self.assertEqual(len(ledger.read_text().splitlines()),1)
    def test_exact_pinned_prestart_warmup(self):
        root=Path(__file__).parents[2]/"reports/btc-split-sol-cover-20261018"
        seed=CM2RunConfig(Config(),root).seed(1725148800000000000)
        self.assertEqual(len(seed),169)
        self.assertEqual(seed[-1].closed_ns,1725148800000000000)

if __name__=="__main__": unittest.main()
