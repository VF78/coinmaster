"""Independent draft review: synthetic source only, no Nautilus import/constructor.

Load a frozen stdlib-only child by absolute path, never through coinmaster.
Failing regression assertions are retained as concrete review evidence.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

DRAFT = Path(os.environ.get('CONTROL_REVIEW_DRAFT', str(Path(__file__).resolve().parents[1] / 'coinmaster/research/cm2_reference_control_worker.py')))
spec = importlib.util.spec_from_file_location('reviewed_control_bootstrap', DRAFT)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class ImportBoundary(BaseException):
    """Stops before even importing the native engine module."""


class BootstrapReview(unittest.TestCase):
    def setUp(self):
        # Every execute check models a fresh child even in a larger test suite.
        module_scope = patch.dict(sys.modules)
        module_scope.start()
        self.addCleanup(module_scope.stop)
        for name in list(sys.modules):
            if name == 'coinmaster' or name.startswith('coinmaster.'):
                del sys.modules[name]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'frozen'
        self.runtime = self.source / 'runtime'
        self.runtime.mkdir(parents=True)
        entries = []
        for number in range(91):
            relative = f'runtime/coinmaster/synthetic_{number}.py'
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            content = b'# synthetic public-source fixture, no native imports\n'
            target.write_bytes(content)
            blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
            entries.append(dict(path=relative, bytes=len(content), git_blob_sha1=blob))
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps(dict(commit=worker.REFERENCE_COMMIT, entries=entries)))
        self.prepared = self.root / 'prepared.json'
        self.kwargs = copy.deepcopy(worker.FIXED)
        self.kwargs.update(data_root=str(self.root / 'data'), candidate=copy.deepcopy(worker.CANDIDATE),
            trading_start_ms=1725148800000, trading_end_ms=1733011200000, warmup_start_ms=1662076800000,
            artifact_label='PREPARED', artifact_dir=str(self.root / 'unused'),
            current_hl_execution_inputs=str(self.root / 'profile'))
        self.request = dict(source_family=worker.FAMILY, execution_source_commit=worker.REFERENCE_COMMIT,
            execution_source_root=str(self.source), execution_source_manifest=str(self.manifest),
            execution_source_manifest_sha256=worker.sha(self.manifest), prepared_control_kwargs=str(self.prepared),
            start_ns=1725148800000000000, end_ns=1733011200000000000,
            data_root=self.kwargs['data_root'], current_hl_execution_inputs=self.kwargs['current_hl_execution_inputs'],
            artifact_dir=str(self.root / 'output'), run_id='SYNTHETIC_REVIEW_ONLY',
            shared_lock_path=str(self.root / 'lease'), orchestrator_source_root='/synthetic/orchestrator',
            orchestrator_source_commit='synthetic')
        self.request.update(stage='synthetic_review', attempt_ledger=str(self.root / 'ledger.jsonl'))
        self.request_digest = 'a' * 64
        self.verified_sources = {str((self.source / e['path']).resolve()): e for e in entries}
        self.save_kwargs()

    def save_kwargs(self):
        self.prepared.write_text(json.dumps(self.kwargs))
        self.request['prepared_control_kwargs_sha256'] = worker.sha(self.prepared)

    def test_wrong_prepared_sha_denied(self):
        self.request['prepared_control_kwargs_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'KWARGS_HASH_MISMATCH'):
            worker.validate_binding(self.request)

    def test_wrong_family_denied(self):
        self.request['source_family'] = 'CM2BTCREF'
        with self.assertRaisesRegex(ValueError, 'SOURCE_FAMILY_REQUIRED'):
            worker.validate_binding(self.request)

    def test_changed_manifest_blob_denied(self):
        (self.runtime / 'coinmaster/synthetic_0.py').write_text('# changed\n')
        with self.assertRaisesRegex(ValueError, 'PUBLIC_BLOB_MISMATCH'):
            worker.validate_binding(self.request)

    def test_unknown_kwarg_denied(self):
        self.kwargs['unknown_economic_switch'] = True
        self.save_kwargs()
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_OR_MISSING_KWARG'):
            worker.validate_binding(self.request)

    def test_candidate_bool_must_not_accept_integer(self):
        self.kwargs['candidate']['sol_overlay_enabled'] = 0
        self.save_kwargs()
        with self.assertRaises(ValueError):
            worker.validate_binding(self.request)

    def test_trading_timestamp_must_not_accept_float(self):
        self.kwargs['trading_start_ms'] = float(self.kwargs['trading_start_ms'])
        self.save_kwargs()
        with self.assertRaises(ValueError):
            worker.validate_binding(self.request)

    def test_origin_outside_frozen_root_denied(self):
        fake = types.SimpleNamespace(__file__='/synthetic/current/coinmaster/bad.py')
        with patch.dict(sys.modules, {'coinmaster.review_synthetic': fake}):
            with self.assertRaisesRegex(ValueError, 'MIXED_COINMASTER_ORIGINS'):
                worker.origins(self.runtime, self.verified_sources)

    def test_unmanifested_coinmaster_source_must_not_be_accepted(self):
        extra = self.runtime / 'coinmaster/unverified_extra.py'
        extra.write_text('# not in the blob manifest\n')
        fake = types.SimpleNamespace(__file__=str(extra))
        with patch.dict(sys.modules, {'coinmaster.review_synthetic': fake}):
            with self.assertRaises(ValueError):
                worker.origins(self.runtime, self.verified_sources)

    def execute_stopping_at_first_native_import(self, descriptor):
        import builtins
        original_import = builtins.__import__
        def intercept(name, *args, **kwargs):
            if name.startswith('nautilus_trader'):
                raise ImportBoundary(name)
            return original_import(name, *args, **kwargs)
        with patch.dict(os.environ, {'PYTHONPATH': str(self.runtime)}):
            with patch('builtins.__import__', side_effect=intercept):
                worker.execute(self.request, lease_fd=descriptor, request_sha256=self.request_digest)

    def test_second_engine_call_rejected_before_constructor(self):
        # Compile only the reviewed proxy class, with a synthetic boundary
        # replacing its native target. No native package is imported.
        tree = ast.parse(DRAFT.read_text())
        execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
        proxy = next(n for n in execute.body if isinstance(n, ast.ClassDef) and n.name == 'OneEngine')
        target_calls = []
        class SyntheticBoundary:
            add_venue = object()
            def __new__(cls, *args, **kwargs):
                target_calls.append('BOUNDARY_ONLY')
                raise ImportBoundary('SYNTHETIC_NO_CONSTRUCTOR')
        calls = []
        environment = dict(original=SyntheticBoundary, calls=calls, probe_dir=None, require=worker.require)
        exec(compile(ast.Module(body=[proxy], type_ignores=[]), '<reviewed-proxy-only>', 'exec'), environment)
        self.assertIs(environment['OneEngine'].add_venue, SyntheticBoundary.add_venue)
        with self.assertRaises(ImportBoundary):
            environment['OneEngine']()
        self.assertEqual(calls, ['RESERVED_BEFORE_CONSTRUCTOR'])
        with self.assertRaisesRegex(ValueError, 'EXACTLY_ONE_ENGINE'):
            environment['OneEngine']()
        self.assertEqual(target_calls, ['BOUNDARY_ONLY'])

    def save_claim(self, **changes):
        output = Path(self.request['artifact_dir'])
        output.mkdir(exist_ok=True)
        claim = dict(status='STARTED', run_id=self.request['run_id'], stage=self.request['stage'],
            request_sha256=self.request_digest, scope_version='SYNTHETIC_REVIEW_ONLY')
        claim.update(changes)
        (output / 'ATTEMPT_STARTED.json').write_text(json.dumps(claim))
        Path(self.request['attempt_ledger']).write_text(json.dumps({k: v for k, v in claim.items() if k != 'request_sha256'}) + '\n')

    def test_wrong_started_request_hash_denied_before_native_import(self):
        self.save_claim(request_sha256='b' * 64)
        with Path(self.request['shared_lock_path']).open('w') as stream:
            with self.assertRaisesRegex(ValueError, 'STARTED_CLAIM_MISMATCH'):
                self.execute_stopping_at_first_native_import(stream.fileno())

    def test_missing_started_ledger_denied_before_native_import(self):
        self.save_claim()
        Path(self.request['attempt_ledger']).write_text('')
        with Path(self.request['shared_lock_path']).open('w') as stream:
            with self.assertRaisesRegex(ValueError, 'STARTED_LEDGER_MISMATCH'):
                self.execute_stopping_at_first_native_import(stream.fileno())

    def test_exact_claim_reaches_intercepted_import_only(self):
        self.save_claim()
        with Path(self.request['shared_lock_path']).open('w') as stream:
            with self.assertRaises(ImportBoundary):
                self.execute_stopping_at_first_native_import(stream.fileno())

    def test_manifested_loaded_source_blob_change_denied(self):
        target = self.runtime / 'coinmaster/synthetic_0.py'
        target.write_text('# changed after initial validation\n')
        fake = types.SimpleNamespace(__file__=str(target))
        with patch.dict(sys.modules, {'coinmaster.review_synthetic': fake}):
            with self.assertRaisesRegex(ValueError, 'IMPORTED_SOURCE_BLOB_MISMATCH'):
                worker.origins(self.runtime, self.verified_sources)

    def test_wrong_lease_inode_denied_before_native_import(self):
        Path(self.request['shared_lock_path']).touch()
        with (self.root / 'other').open('w') as stream:
            with self.assertRaisesRegex(ValueError, 'LEASE_INODE_MISMATCH'):
                self.execute_stopping_at_first_native_import(stream.fileno())

    def test_missing_started_claim_denied_before_native_import(self):
        # Existing valid lease, absent ATTEMPT_STARTED.json. ImportBoundary is
        # a failure: it proves the child passed the required admission boundary.
        with Path(self.request['shared_lock_path']).open('w') as stream:
            try:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.execute_stopping_at_first_native_import(stream.fileno())
            except ImportBoundary:
                self.fail('Missing STARTED claim reached first native import; import intercepted, constructors zero')


if __name__ == '__main__':
    unittest.main(verbosity=2)
