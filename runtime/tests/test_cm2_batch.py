"""Constructor-free batch proofs using standard-Python children only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from coinmaster.research import cm2_batch as batch
from coinmaster.research import cm2_runner as runner


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def fixture(self, count=3):
        budget = self.root/'budget.json'
        ledger = self.root/'trials.jsonl'
        lock = self.root/'lease.lock'
        cases=[]
        for i in range(count):
            request={'run_id':f'CASE{i}', 'stage':'broad', 'policy':{'x':i},
                'attempt_ledger':str(ledger),'budget_path':str(budget),'shared_lock_path':str(lock),
                'artifact_dir':str(self.root/f'case{i}')}
            raw=json.dumps(request).encode()
            p=self.root/f'request{i}.json';p.write_bytes(raw)
            cases.append({'run_id':request['run_id'],'request_path':str(p),
                'request_sha256':batch.digest_bytes(raw),'policy_sha256':batch.policy_digest(request['policy'])})
        own={'quota':count,'cases':cases,'max_workers':2,'min_available_memory_bytes':1,
             'budget_path':str(budget),'attempt_ledger':str(ledger),'shared_lock_path':str(lock)}
        manifest={'schema':'cm2-static-block-v1','root_GO':True,'global_reservation_ref':'ROOT#32',
            'block_id':'broad-first','stage':'broad','broad_block':'initial','reserved_attempts':count,'hosts':{'vps':own}}
        sha=batch.digest_bytes(json.dumps(manifest).encode())
        budget.write_text(json.dumps({'total_physical_cap':count,'stages':{'broad':{'cap':count,'initial_block':count}},
            'root_allocation_sha256':sha,'scope_version':'broad-first'}))
        return manifest,own,sha
    def test_allocation_and_collision_rejection(self):
        m,own,sha=self.fixture()
        _,requests=batch.validate_allocation(m,'vps',sha)
        self.assertEqual(len(requests),3)
        m['hosts']['mac']={**own,'cases':[own['cases'][0]],'quota':1}
        m['reserved_attempts']=4
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):
            batch.validate_allocation(m,'vps',sha)
    def test_pin_and_strict_budget(self):
        m,own,sha=self.fixture()
        Path(own['cases'][0]['request_path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'REQUEST_PIN'):
            batch.validate_allocation(m,'vps',sha)
        m,own,sha=self.fixture()
        p=Path(own['budget_path']);b=json.loads(p.read_text());b['total_physical_cap']=116;p.write_text(json.dumps(b))
        with self.assertRaisesRegex(ValueError,'STRICT_BLOCK'):
            batch.validate_allocation(m,'vps',sha)
    def test_concurrent_registration_never_exceeds_quota(self):
        m,own,sha=self.fixture(2)
        # Real process race over existing runner's fcntl-protected ledger.
        script='import json,sys;from coinmaster.research.cm2_runner import register_attempt;r=json.loads(sys.argv[1]);register_attempt(r,{})'
        base=json.loads(Path(own['cases'][0]['request_path']).read_text())
        children=[]
        for i in range(8):
            children.append(subprocess.Popen([sys.executable,'-B','-c',script,json.dumps({**base,'run_id':f'RACE{i}'})],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        statuses=[p.wait() for p in children]
        self.assertEqual(statuses.count(0),2)
        rows=[json.loads(x) for x in Path(own['attempt_ledger']).read_text().splitlines()]
        self.assertEqual(len(rows),2)
        with self.assertRaisesRegex(ValueError,'NO_REPLAY'):
            runner.register_attempt({**base,'run_id':rows[0]['run_id']},{})
    def test_spawn_failures_count_and_stop_after_two(self):
        m,own,sha=self.fixture(3)
        _,requests=batch.validate_allocation(m,'vps',sha)
        with patch.object(batch,'available_memory',return_value=10**12),patch.object(runner,'worker_process_spec',return_value=(['/absent/cm2-test-executable'],{},str(self.root))):
            result=batch.dispatch(requests,{},own,sha)
        rows=[json.loads(x) for x in Path(own['attempt_ledger']).read_text().splitlines()]
        self.assertEqual([r['status'] for r in rows],['STARTED','FAILED','STARTED','FAILED'])
        self.assertEqual(result['status'],'STOPPED_NEW_CLAIMS')
        self.assertFalse((self.root/'case2').exists())
        with self.assertRaisesRegex(ValueError,'NO_RESUME'):
            batch.dispatch(requests,{},own,sha)
    def test_out_of_order_children_exact_wait4(self):
        m,own,sha=self.fixture(3)
        _,requests=batch.validate_allocation(m,'vps',sha)
        def spec(request,fd,digest):
            delay={"CASE0":.4,"CASE1":.02,"CASE2":.03}[request['run_id']]
            return [sys.executable,'-B','-c',f'import time;time.sleep({delay})'],{},str(self.root)
        with patch.object(batch,'available_memory',return_value=10**12),patch.object(runner,'worker_process_spec',side_effect=spec):
            result=batch.dispatch(requests,{},own,sha)
        rows=[json.loads(x) for x in Path(own['attempt_ledger']).read_text().splitlines()]
        completed=[r for r in rows if r['status']=='COMPLETED']
        self.assertEqual([r['run_id'] for r in completed],['CASE1','CASE2','CASE0'])
        self.assertEqual(result['status'],'TERMINAL')
        self.assertTrue(all(r['true_child_peak_rss_bytes']>0 for r in completed))
    def test_memory_hold_no_attempt(self):
        m,own,sha=self.fixture()
        _,requests=batch.validate_allocation(m,'vps',sha)
        with patch.object(batch,'available_memory',return_value=0):
            result=batch.dispatch(requests,{},own,sha)
        self.assertFalse(Path(own['attempt_ledger']).exists())
        self.assertEqual(result['status'],'STOPPED_NEW_CLAIMS')
    def test_two_child_inherited_lease_survives_parent_death(self):
        lock=self.root/'lease.lock'
        ready=self.root/'ready'
        parent_code='''
import fcntl,os,pathlib,subprocess,sys,time
lock=pathlib.Path(sys.argv[1]).open('a+')
fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
pids=[]
for delay in (.3,1.3):
 p=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep('+str(delay)+')'],pass_fds=(lock.fileno(),),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 pids.append(p.pid)
pathlib.Path(sys.argv[2]).write_text(str(pids))
os._exit(0)
'''
        parent=subprocess.Popen([sys.executable,'-B','-c',parent_code,str(lock),str(ready)])
        parent.wait(timeout=3)
        self.assertTrue(ready.exists())
        with self.assertRaises(BlockingIOError): runner.acquire_shared_lease(lock)
        time.sleep(.5)
        # First child has exited; second child alone still owns inherited FD.
        with self.assertRaises(BlockingIOError): runner.acquire_shared_lease(lock)
        time.sleep(1)
        with runner.acquire_shared_lease(lock): pass


if __name__=='__main__': unittest.main()
