"""Tiny metadata/interface tests only: no native imports, streams, financial calculations or result acceptance."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from financial_reader_binding import (PACKET, OLD, PINS, field, pinned, validate_roles,
    canonical_entry_sha, passing_receipt, load_root_gate, validate_predecision_coverage, PREDECISION_FACTS)

class BindingTests(unittest.TestCase):
    def test_frozen_metric_and_schema_hashes(self):
        self.assertEqual(hashlib.sha256((OLD/'metric-contract.json').read_bytes()).hexdigest(), PINS['metric'])
        self.assertEqual(hashlib.sha256((OLD/'financial-qualification-receipt-schema.json').read_bytes()).hexdigest(), PINS['financial_schema'])

    def test_real_accepted_OFF_metadata(self):
        receipt=json.loads((OLD.parent/'a0-financial-qualification-R2_OFF.json').read_text())
        passing_receipt(receipt)
        self.assertEqual(receipt['attempt_id'], '77b7a5cc-0e2a-43a3-a17e-56868728a7d5')
        self.assertEqual(receipt['report_sha256'], 'fe1245220d6efc96b01d677caebb4e39b5a3590b3451ee9f04a5fdf8ecbeaad1')

    def test_real_C0_rejection_is_not_a_receipt(self):
        rejected=json.loads((OLD.parent/'a0-financial-rejection-R2_C0.json').read_text())
        with self.assertRaises(ValueError): passing_receipt(rejected)
        self.assertEqual(rejected['decision'], 'ROOT_REJECT_C0_FINANCIAL_ADMISSION_NATIVE_3TP_FAIL')

    def test_false_OS_not_integer_zero(self):
        receipt=json.loads((OLD.parent/'a0-financial-qualification-R2_OFF.json').read_text())
        receipt['actual_returncode']=False
        with self.assertRaises(ValueError): passing_receipt(receipt)

    def test_unknown_TP_blocks_prior(self):
        receipt=json.loads((OLD.parent/'a0-financial-qualification-R2_OFF.json').read_text())
        receipt['financial_gates']['native_3TP']='UNKNOWN'
        with self.assertRaises(ValueError): passing_receipt(receipt)

    def test_explicit_field_no_wildcards(self):
        self.assertEqual(field({'a':{'b':'checkpoint'}}, ['a','b']), 'checkpoint')
        for path in ([], ['*'], ['a','c'], 'a.b'):
            with self.assertRaises(ValueError): field({'a':{'b':'checkpoint'}}, path)

    def test_snapshot_entry_unchanged_when_ledger_appends(self):
        entry={'attempt_id':'metadata-only-test', 'status':'COMPLETED', 'detail':{'report_sha256':'metadata-pin'}}
        before=canonical_entry_sha(entry)
        ledger={'attempts':[entry]}; ledger['attempts'].append({'attempt_id':'later-metadata-only'})
        self.assertEqual(before,canonical_entry_sha(ledger['attempts'][0]))
        changed=copy.deepcopy(entry);changed['detail']['report_sha256']='mutated'
        self.assertNotEqual(before,canonical_entry_sha(changed))

    def test_exact_roles_and_corrupt_pin(self):
        with tempfile.TemporaryDirectory(prefix='cm-financial-binding-') as td:
            roles={}
            for name in ('report','orders','funding','coherent'):
                p=Path(td)/name;p.write_text('metadata-only '+name)
                roles[name]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            completion={'artifacts':[dict(role=k,**v) for k,v in roles.items()]}
            self.assertEqual(set(validate_roles(roles,completion)),set(roles))
            missing=dict(roles);missing.pop('funding')
            with self.assertRaises(ValueError):validate_roles(missing,completion)
            duplicate=copy.deepcopy(completion);duplicate['artifacts'][1]['role']='report'
            with self.assertRaises(ValueError):validate_roles(roles,duplicate)
            Path(roles['funding']['path']).write_text('changedmetadata')
            with self.assertRaises(ValueError):pinned(roles['funding'])

    def test_nonapproved_blueprint_rejected(self):
        path=PACKET/'interface-root-gate-template.json'
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'ROOT_FINANCIAL_READ_GATE_REQUIRED'):load_root_gate(path,sha)

    def test_byte_equivalent_core_and_no_engine_import(self):
        proof=json.loads((PACKET/'interface-core-proof.json').read_text())
        for block in proof['blocks']:
            if 'byte_equivalent' in block:self.assertTrue(block['byte_equivalent']);self.assertEqual(block['old_sha256'],block['new_sha256'])
        for name in ('financial_reader.py','financial_reader_binding.py','financial_reader_rights.py'):
            tree=ast.parse((PACKET/name).read_text())
            imported=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Import): imported.extend(x.name for x in node.names)
                if isinstance(node,ast.ImportFrom): imported.append(node.module or '')
            self.assertFalse(any('nautilus' in x or 'coinmaster' in x for x in imported))
        text=(PACKET/'financial_reader.py').read_text()
        self.assertNotIn("--expected-source", text)
        self.assertIn("--gate-sha256",text)


    def predecision_fixture(self):
        # Tiny metadata-only coverage contract: no monetary values or simulated outcomes.
        mapping={name:['unfrozen_test_field',name] for name in PREDECISION_FACTS}
        gate={'attempt_id':'metadata-only', 'source_commit':'a'*40, 'label':'C0-example', 'phase':'metadata-phase',
            'roles':{'report':{'sha256':'report-metadata-sha'}},
            'predecision':{'producer_json_path':['paired_prefix_audit','predecision_records'],
                'record_stage':'after_md_reconcile_before_a0_check','field_map':mapping}}
        proof={'schema':'CM_SOL_STANDING_PREDECISION_COVERAGE_V1',
            'status':'ROOT_ACCEPTED_COMPLETE_OBSERVATIONAL_COVERAGE',
            **{k:gate[k] for k in ['attempt_id','source_commit','label','phase']},
            'report_sha256':'report-metadata-sha',
            'producer_json_path':gate['predecision']['producer_json_path'],
            'record_stage':gate['predecision']['record_stage'], 'independent_of_A0_trading_flag':True,
            'coverage_complete':True,'facts_capture_complete':True,'frozen_field_map':mapping,
            'captured_fact_names':list(PREDECISION_FACTS),
            'universes':{name:{'status':'COMPLETE','expected_ids':['metadata-'+name],
                'observed_ids':['metadata-'+name],'missing_ids':[],'extra_ids':[]}
                for name in ['risk_selections','risk_OFF','candidate_parents']},
            'timestamp_coverage':{'status':'COMPLETE','missing_or_unbound_records':0,'records':1,
                'first_event_ns':100,'last_event_ns':100},
            'missing_fact_reason_capture':'COMPLETE_EXPLICIT_REASONS',
            'margin_observation_policy':'RECORDED_UNKNOWN_ALLOWED_OWN_A0_GUARDS_AT_DISPATCH',
            'margin_example':{'stock_margin_invoked':False,'result':'UNKNOWN','missing_reason':'not_invoked_A0_disabled'},
            'structurally_admissible_original_rights':1,'measurement_status':'OBSERVATIONAL_COVERAGE_ONLY'}
        return gate, proof

    def test_predecision_margin_false_unknown_is_observationally_valid(self):
        gate,proof=self.predecision_fixture()
        result=validate_predecision_coverage(proof,gate)
        self.assertTrue(result['coverage_complete'])
        self.assertEqual(result['future_A0_margin_fill_profit'],'NOT_PREPROVEN_OWN_ACCOUNT_RUNTIME_GUARDS_REQUIRED')

    def test_predecision_cannot_be_replaced_by_empty_disabled_rights(self):
        gate,proof=self.predecision_fixture()
        for mutate in (
            lambda p:p.update(status='UNKNOWN'),
            lambda p:p.update(coverage_complete='UNKNOWN'),
            lambda p:p.update(independent_of_A0_trading_flag=False),
            lambda p:p.update(report_sha256='different-report'),
            lambda p:p.update(phase='different-phase'),
            lambda p:p['universes']['risk_OFF'].update(observed_ids=[]),
            lambda p:p.update(captured_fact_names=[]),
            lambda p:p['timestamp_coverage'].update(records=0,first_event_ns=None,last_event_ns=None),
        ):
            altered=copy.deepcopy(proof);mutate(altered)
            with self.assertRaises(ValueError):validate_predecision_coverage(altered,gate)
        with self.assertRaises(ValueError):validate_predecision_coverage({'rights_audit_complete':'PASS','a0_rights':[]},gate)

    def test_predecision_complete_zero_opportunity_not_incomplete_coverage(self):
        gate,proof=self.predecision_fixture()
        proof.update(structurally_admissible_original_rights=0,measurement_status='NO_STRUCTURAL_OPPORTUNITY')
        self.assertEqual(validate_predecision_coverage(proof,gate)['measurement_status'],'NO_STRUCTURAL_OPPORTUNITY')
        for universe in proof['universes'].values():universe.update(expected_ids=[],observed_ids=[])
        proof['timestamp_coverage'].update(records=0,first_event_ns=None,last_event_ns=None)
        proof['measurement_status']='NOT_TESTED'
        self.assertEqual(validate_predecision_coverage(proof,gate)['measurement_status'],'NOT_TESTED')
        proof['timestamp_coverage']['status']='UNKNOWN'
        with self.assertRaises(ValueError):validate_predecision_coverage(proof,gate)

if __name__=='__main__':unittest.main()
