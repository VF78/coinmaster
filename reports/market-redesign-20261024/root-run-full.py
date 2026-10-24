"""Ledger one approved physical native attempt; does not model trading."""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS = Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/market-redesign-20261024')

def now():
    return datetime.now(timezone.utc).isoformat()

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=('R1', 'R2', 'R3'), required=True)
    args = parser.parse_args()
    ledger_path = HERE / 'run-ledger.json'
    ledger = json.loads(ledger_path.read_text())
    assert ledger['active_runs'] == 0 and ledger['full_launch_go']
    freeze_path = HERE / 'full-freeze.json'
    freeze = json.loads(freeze_path.read_text())
    assert hashlib.sha256(freeze_path.read_bytes()).hexdigest() == ledger['full_freeze_sha256']
    attempts = ledger['physical_full_attempts']
    assert len(attempts) < 3 and args.variant == freeze['ordered_variants'][len(attempts)]
    assert json.loads((HERE / 'short-batch2-acceptance.json').read_text())['status'] == 'ROOT_SHORT_ACCEPTANCE_PASS'
    if attempts:
        assert attempts[-1]['exit_code'] == 0
        previous = json.loads((HERE / f"root-{attempts[-1]['variant']}-acceptance.json").read_text())
        assert previous['mechanical_accounting_acceptance'] is True
    command = freeze['commands'][args.variant]
    root = Path(freeze['source']['frozen_mac_source'])
    for name, pin in freeze['source_file_sha256'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == pin, name
    for name, item in freeze['inputs'].items():
        assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() == item['sha256'], name
    config = json.loads(Path(command['expected_config']).read_text())
    assert hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == command['expected_config_canonical_sha256']
    result_dir = Path(command['argv'][command['argv'].index('--artifact-dir') + 1])
    assert not result_dir.exists(), 'Fresh native result namespace required'
    job = JOBS / args.variant
    journal_files_before = list(job.rglob('*.sqlite*')) if job.exists() else []
    assert not journal_files_before
    job.mkdir(exist_ok=True)
    Path(command['env']['TMPDIR']).mkdir(exist_ok=True)
    receipt = {**command, 'variant': args.variant, 'attempt_number': len(attempts)+1,
               'status': 'LAUNCHING', 'started_utc': now(), 'full_freeze_sha256': ledger['full_freeze_sha256'],
               'artifact_dir_existed_before_launch': False, 'journal_files_before_launch': [],
               'external_cash_flows_USDT': '0', 'external_flow_basis': freeze['external_flow_basis'],
               'mechanical_acceptance_pass': True, 'source_review_pass': True,
               'mechanical_basis': 'short-batch2-acceptance.json',
               'review_basis': 'review-90da864-closure.md + owner-observer-only.diff root inspection',
               'native_version': '1.231.0', 'direct_python_popen': True,
               'log': str(job / 'native.log')}
    receipt_path = HERE / f'root-{args.variant}-execution-receipt.json'
    attempts.append(receipt)
    ledger.update(status=f'{args.variant}_FULL_RUNNING', active_runs=1)
    write(receipt_path, receipt)
    write(ledger_path, ledger)
    begin = time.monotonic()
    with Path(receipt['log']).open('wb') as log:
        process = subprocess.Popen(command['argv'], cwd=command['cwd'], env=command['env'], stdout=log, stderr=subprocess.STDOUT)
        receipt.update(pid=process.pid, status='RUNNING', launched=True)
        write(receipt_path, receipt)
        write(ledger_path, ledger)
        print(json.dumps({'variant': args.variant, 'physical_attempt': receipt['attempt_number'], 'pid': process.pid, 'status': 'RUNNING'}), flush=True)
        code = process.wait()
    receipt.update(exit_code=code, native_process_exit_code=code, elapsed_seconds=time.monotonic()-begin, ended_utc=now(), status='PROCESS_COMPLETED_AWAIT_ACCOUNTING_ACCEPTANCE' if code == 0 else 'FAILED_STOP_NO_AUTO_RETRY')
    ledger.update(status=receipt['status'], active_runs=0)
    if code:
        ledger['full_launch_go'] = False
    write(receipt_path, receipt)
    write(ledger_path, ledger)
    print(json.dumps({'variant': args.variant, 'physical_attempt': receipt['attempt_number'], 'exit_code': code, 'seconds': receipt['elapsed_seconds'], 'status': receipt['status']}), flush=True)
    return code

if __name__ == '__main__':
    raise SystemExit(main())
