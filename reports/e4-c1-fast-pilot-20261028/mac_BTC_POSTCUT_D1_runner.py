"""Exact frozen BTC_POSTCUT_D1 orchestration: preflight, then one registry-counted child."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import fcntl
import hashlib
import json
import os
import subprocess
import uuid

PROJECT = Path('/Users/vf/Documents/ChatGPT/Coinmaster')
MANAGER = PROJECT / 'research-worktrees/btc-pattern-pilot-m2-20261021'
REPORT = MANAGER / 'reports/e4-c1-fast-pilot-20261028'
JOB = PROJECT / 'runtime/var/research-jobs/e4-c1-fast-pilot-20261028'
SOURCE = JOB / 'source-BTC-POSTCUT-D1-fccd60c01e8c'
PACKET = SOURCE / 'reports/e4-c1-fast-pilot-20261028'
COMMIT = 'fccd60c01e8cae5e8258748b046f43f88a16bb79'
CONFIG = 'a2c7d88b5aff67399c0db849585bc5ad3625ce4e82068b3e29254d355c119253'

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def save(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(tmp, path)

def command():
    c = json.loads((PACKET / 'btc-postcut-d1-run-command.json').read_text())
    c['cwd'] = str(SOURCE / 'runtime')
    c['env']['PYTHONPATH'] = c['cwd']
    assert c['expected_config_sha256'] == CONFIG
    assert c['argv'][-6:] == ['--research-c1-btc-cut-divisor', '4', '--research-c1-restore-dd', '0.40', '--research-c1-first-fresh-h4', '--research-c1-btc-postcut-d1']
    assert c['qualification_stress'] is False and '--research-c1-global-cut-arm' not in c['argv']
    assert '/usr/bin/time' not in c['argv']
    return c

def verify_source():
    path = JOB / 'source-BTC-POSTCUT-D1-fccd60c01e8c.manifest.json'
    assert sha(path) == '15d4242335e218e89849552be1e539cd76f286dae8439637c7ee2dda6f4aa8f0'
    m = json.loads(path.read_text())
    assert m['commit'] == COMMIT and isinstance(m['files'], dict) and len(m['files']) == 172
    for rel, digest in m['files'].items():
        assert sha(SOURCE / rel) == digest, rel
    assert json.loads((PACKET / 'btc-postcut-d1-source-preparation.json').read_text())['base_commit'] == 'ff253cc852cb9d564186d1c97f3201429ba5978a'
    assert sha(PACKET / 'btc-postcut-d1-peer-review.json') == 'a6669f2e9e67e415bbdcc9913f42607c569296d0a69f3228b5391cd8ea7c7590'
    assert sha(PACKET / 'config-BTC-POSTCUT-D1.json') == CONFIG
    assert sha(REPORT / 'config-FIRST-FRESH-COMBO.json') == '0782684ce8906ee2ad07963f59f84be2c5e33019b13e263fa1c8f8fd1cfd975a'
    q = json.loads((PACKET / 'config-BTC-POSTCUT-D1.json').read_text())
    assert q['live_enabled'] is False and str(q['initial_total_usdt']) == '10000'
    delta = q['residual_recovery_research'].pop('btc_postcut_d1')
    assert delta == {'SOL':'UNCHANGED','applies':'ALL_BTC_RESTORES_BEFORE_ANY_TP_CANCEL_OR_SUBMIT','availability':'OBSERVED_AVAILABLE_LE_VALID_MONEY_SOURCE_LE_DECISION','open_at_least_last_actual_cut_fill':True,'source':'OBSERVED_MATCHING_BTC_DAILY_SIGNAL','waiting':'RETAIN_CONFIRMATION_CREDIT_NO_ATTEMPT'}
    assert q == json.loads((REPORT / 'config-FIRST-FRESH-COMBO.json').read_text())
    fixtures = json.loads((JOB / 'source-BTC-POSTCUT-D1-fccd60c01e8c.fixture-inputs.json').read_text())
    assert fixtures['source_commit'] == COMMIT and len(fixtures['input_pins']) == 3
    for rel, digest in fixtures['input_pins'].items():
        assert sha(SOURCE / rel) == digest, rel
    return m

def preflight():
    assert not (JOB / 'BTC_POSTCUT_D1').exists(), 'BTC_POSTCUT_D1_NAMESPACE_NOT_FRESH'
    m = verify_source()
    c = command()
    data = Path(c['data_root'])
    inputs = []
    for rel, digest in c['input_pins'].items():
        paths = list(dict.fromkeys(x for x in (data / rel, SOURCE / rel, PROJECT / rel) if x.is_file()))
        assert paths, rel
        for p in paths:
            assert sha(p) == digest, str(p)
            st = p.stat()
            inputs.append({'path': str(p), 'sha256': digest, 'size': st.st_size, 'mtime_ns': st.st_mtime_ns})
    probe = "import json,sys,importlib.metadata as m; import coinmaster; from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig as C; import msgspec; fs={f.name:f.default for f in msgspec.structs.fields(C)}; assert fs['research_c1_btc_cut_divisor']==2; assert fs['research_c1_first_fresh_h4'] is False; assert fs['research_c1_btc_postcut_d1'] is False; assert m.version('nautilus_trader')=='1.231.0'; print(json.dumps({'python':sys.version,'native':m.version('nautilus_trader'),'source':coinmaster.__file__,'default_divisor':fs['research_c1_btc_cut_divisor'],'engines':0}))"
    r = subprocess.run([c['argv'][0], '-c', probe], cwd=c['cwd'], env=c['env'], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr[-2000:]
    runtime = json.loads(r.stdout.strip().splitlines()[-1])
    assert Path(runtime['source']).resolve().is_relative_to(SOURCE.resolve())
    help_run = subprocess.run(c['argv'] + ['--help'], cwd=c['cwd'], env=c['env'], capture_output=True, text=True, timeout=30)
    assert help_run.returncode == 0 and '--research-c1-btc-postcut-d1' in help_run.stdout, help_run.stderr[-1000:]
    result = {'status': 'PREFLIGHT_PASS_NO_ENGINE', 'utc': now(), 'source_commit': COMMIT,
              'config_sha256': CONFIG, 'source_files_verified': len(m['files']), 'inputs': inputs,
              'runtime': runtime, 'engines_created': 0, 'argv': c['argv'], 'cwd': c['cwd'], 'env': c['env']}
    save(JOB / 'BTC_POSTCUT_D1-preflight.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'source_commit', 'config_sha256', 'source_files_verified', 'runtime')}))

def registry_update(change):
    path = REPORT / 'experiment_registry.csv'
    with Path(str(path) + '.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with path.open(newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fields = reader.fieldnames
        change(rows)
        tmp = path.with_suffix('.csv.tmp')
        with tmp.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, path)

def run_once():
    c = command()
    verify_source()
    pre = json.loads((JOB / 'BTC_POSTCUT_D1-preflight.json').read_text())
    assert pre['status'] == 'PREFLIGHT_PASS_NO_ENGINE' and pre['source_commit'] == COMMIT and pre['config_sha256'] == CONFIG
    for f in pre['inputs']:
        st = Path(f['path']).stat()
        assert (st.st_size, st.st_mtime_ns) == (f['size'], f['mtime_ns']), f['path']
    manifest = json.loads((REPORT / 'manifest.json').read_text())
    assert manifest['budget']['historical_max'] == 8
    assert manifest['budget']['candidate_max'] == 6 and manifest['budget']['conditional_control_max'] == 0
    assert manifest['budget_amendments'][-1]['donor_unattempted_slot'] == 'CONTROL_E4'
    assert manifest['runs']['BTC_POSTCUT_D1']['root_go'] is True
    assert manifest['runs']['BTC_POSTCUT_D1']['source_commit'] == COMMIT and manifest['runs']['BTC_POSTCUT_D1']['config_sha256'] == CONFIG
    attempt = manifest['runs']['BTC_POSTCUT_D1']['attempt_uuid']
    assert str(uuid.UUID(attempt)) == attempt
    namespace = JOB / 'BTC_POSTCUT_D1'
    assert not namespace.exists(), 'DO_NOT_REPEAT_BTC_POSTCUT_D1_OR_OVERWRITE_RESULTS'
    def claim(rows):
        spent = sum(int(r['historical_budget_count'] or 0) for r in rows)
        assert spent < 8
        assert sum(int(r['historical_budget_count'] or 0) for r in rows if r['category'] == 'CANDIDATE') < 6
        row = next(r for r in rows if r['id'] == 'BTC_POSTCUT_D1')
        assert int(row['historical_budget_count'] or 0) == 0
        assert not any(r['attempt_uuid'] == attempt for r in rows)
        row.update(status='CLAIMED', historical_budget_count=1, attempt_uuid=attempt, source_commit=COMMIT,
                   config_hash=CONFIG, data_hash=c['data_hash'], artifact_dir=str(namespace / 'result'),
                   notes='ONE approved BTC_POSTCUT_D1; fullpath; frozen source/input; no time-l; no auto-repeat')
    registry_update(claim)
    namespace.mkdir()
    (namespace / 'tmp').mkdir()
    gate = {'status': 'CLAIMED_BEFORE_POPEN', 'attempt_uuid': attempt, 'source_commit': COMMIT,
            'config_sha256': CONFIG, 'started_utc': now(), 'actual_native_child_pid': None,
            'actual_native_child_exit': None, 'argv': c['argv'], 'cwd': c['cwd'], 'historical_attempt': 6}
    save(namespace / 'execution.json', gate)
    try:
        with (namespace / 'native.log').open('wb') as log:
            child = subprocess.Popen(c['argv'], cwd=c['cwd'], env=c['env'], stdout=log, stderr=subprocess.STDOUT)
            gate['actual_native_child_pid'] = child.pid
            gate['status'] = 'RUNNING'
            save(namespace / 'execution.json', gate)
            def started(rows):
                next(r for r in rows if r['attempt_uuid'] == attempt)['status'] = 'RUNNING'
            registry_update(started)
            print(json.dumps({'status': 'RUNNING', 'attempt_uuid': attempt, 'native_child_pid': child.pid}), flush=True)
            rc = child.wait()
        gate.update(actual_native_child_exit=rc, finished_utc=now(), status='EXPORTED_PENDING_ANALYSIS' if rc == 0 else 'FAILED_NATIVE_EXIT')
    except Exception as exc:
        gate.update(status='FAILED_LAUNCH', finished_utc=now(), error_type=type(exc).__name__, error=str(exc))
    save(namespace / 'execution.json', gate)
    def done(rows):
        row = next(r for r in rows if r['attempt_uuid'] == attempt)
        row.update(status=gate['status'], native_child_exit='' if gate['actual_native_child_exit'] is None else str(gate['actual_native_child_exit']))
    registry_update(done)
    print(json.dumps(gate), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    assert args.preflight != args.run
    preflight() if args.preflight else run_once()
