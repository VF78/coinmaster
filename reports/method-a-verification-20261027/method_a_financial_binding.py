"""Stdlib-only completed-result binding. No native imports, launches or ledger writes."""
from pathlib import Path
import json
import prefix_common as c


def bind(path,expected_sha):
    gate_path=c.pinned(dict(path=str(Path(path).resolve()),sha256=expected_sha));g=json.loads(gate_path.read_text())
    assert g['schema']=='METHOD_A_FINANCIAL_READ_GATE_V1' and g['decision']=='ROOT_APPROVED_FINANCIAL_READ' and g['approved_by']=='/root'
    assert g['label'] in c.LABELS and g['source_commit']==c.SOURCE and g['completed_result_only'] is True
    assert g['metric']['sha256']==c.METRIC;c.pinned(g['metric']);c.pinned(g['financial_contract'])
    expected={'method_a_financial_binding.py','method_a_financial_reader.py'}
    assert {Path(ref['path']).name for ref in g['reader_pins']}==expected
    for ref in g['reader_pins']:assert c.pinned(ref).resolve()==Path(__file__).with_name(Path(ref['path']).name).resolve()
    freeze_path=c.pinned(g['freeze']);freeze=c.load_freeze(freeze_path)
    assert freeze['label']==g['label'] and freeze['source_commit']==c.SOURCE
    c.verify_authority(freeze,launch=True);inputs=c.verify_inputs(freeze)
    assert inputs['native_input_sha256']==freeze['native_input_sha256']
    assert inputs['public_profile_sha256']==freeze['public_profile_sha256']
    seal=json.loads(c.pinned(dict(path=freeze['source_seal_path'],sha256=freeze['source_seal_sha256'])).read_text())
    assert seal['source_commit']==c.SOURCE
    for entry in seal['files']:c.pinned(dict(path=str(Path(freeze['source_root'])/entry['path']),sha256=entry['sha256']))
    for entry in freeze['script_pins']:c.pinned(entry)
    common_pin=next(entry for entry in freeze['script_pins'] if Path(entry['path']).name=='prefix_common.py')
    assert c.sha(Path(c.__file__))==common_pin['sha256'],'EXECUTING_COMMON_DIFFERS_FROM_FROZEN_334'
    kwargs=json.loads(c.pinned(freeze['kwargs_payload']).read_text())
    assert kwargs['research_method_a_tp'] is (g['label']=='P1') and kwargs['research_method_a_observer'] is True
    assert kwargs['include_funding'] is True and kwargs['observe_minute_risk'] is True
    assert kwargs['candidate']['value']['sol_overlay_enabled'] is True
    ledger_path=Path(g['current_ledger_path']).resolve();ledger=json.loads(ledger_path.read_text())
    snapshot_path=c.pinned(g['ledger_snapshot']);snapshot=json.loads(snapshot_path.read_text())
    assert ledger['total_max']==snapshot['total_max']==17 and ledger['categories']['prefix']['max']==snapshot['categories']['prefix']['max']==6
    selected=[]
    for data in (ledger,snapshot):
        rows=[row for row in data['attempts'] if row['attempt_id']==g['attempt_id']]
        assert len(rows)==1;row=rows[0];selected.append(row)
        assert row['status']=='COMPLETED' and row['category']=='prefix' and row['label']==g['label'] and row['source_commit']==c.SOURCE
        assert c.canonical(row)==g['completed_attempt_sha256']
        assert type(row['detail']['actual_returncode']) is int and row['detail']['actual_returncode']==0
    row=selected[0];detail=row['detail'];namespace=Path(row['namespace']).resolve()
    assert namespace==Path(freeze['namespace']).resolve()
    report_path=c.pinned(g['report']).resolve();assert report_path==namespace/'result'/(g['label']+'.json')
    report=json.loads(report_path.read_text());link=report['physical_prefix_attempt']
    assert link==detail['physical_identity'] and link['attempt_id']==g['attempt_id'] and link['variant']==link['label']==g['label']
    assert link['source_commit']==c.SOURCE and link['category']=='prefix' and Path(link['ledger']).resolve()==ledger_path
    assert link['freeze_sha256']==g['freeze']['sha256']
    for key in ('source_seal_sha256','recipe_sha256','native_config_sha256','native_input_sha256','common_economic_identity_sha256'):
        assert link[key]==freeze[key]==row[key]
    for key in ('kwargs_sha256','full_bound_kwargs_sha256'):assert link[key]==freeze[key]
    assert link['public_profile_sha256']==inputs['public_profile_sha256']
    assert row['pid']==link['worker_pid'] and type(link['worker_pid']) is int and link['worker_pid']>0
    assert detail['report_sha256']==g['report']['sha256'] and Path(detail['report']).resolve()==report_path
    documents={}
    for name in ('completion_manifest','supervisor'):
        target=c.pinned(g[name]);value=json.loads(target.read_text());documents[name]=value
        assert value['attempt_id']==g['attempt_id'] and value['variant']==g['label'] and value['source_commit']==c.SOURCE
        assert value['physical_identity']==link and value['freeze_sha256']==link['freeze_sha256'] and value['worker_pid']==link['worker_pid']
        assert type(value['actual_returncode']) is int and value['actual_returncode']==0
        assert Path(value['report']).resolve()==report_path and value['report_sha256']==g['report']['sha256']
        assert Path(detail[name]).resolve()==target.resolve() and detail[name+'_sha256']==g[name]['sha256']
    manifest=documents['completion_manifest'];supervisor=documents['supervisor']
    assert manifest['status']=='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO' and supervisor['ledger_status']=='COMPLETED'
    assert Path(supervisor['completion_manifest']).resolve()==c.pinned(g['completion_manifest']).resolve()
    assert supervisor['completion_manifest_sha256']==g['completion_manifest']['sha256']
    expected_roles={entry['role']:entry for entry in c.artifacts(namespace,g['label'],report_path)}
    assert len(manifest['artifacts'])==4 and {entry['role']:entry for entry in manifest['artifacts']}==expected_roles
    assert g['roles']=={key:dict(path=entry['path'],sha256=entry['sha256']) for key,entry in expected_roles.items()}
    extras={'protection_profile':namespace/'result/method-a-native-protection.jsonl.gz','minute_risk':namespace/'result/minute-native-risk.csv.gz',
        'observer_profile':namespace/'native-observer-profile.json','raw_native':namespace/'result'/('method-a-'+g['label']+'-raw-native.json')}
    assert len(manifest['extra_evidence'])==4 and {entry['role'] for entry in manifest['extra_evidence']}==set(extras)
    for entry in manifest['extra_evidence']:assert c.pinned(dict(path=entry['path'],sha256=entry['sha256'])).resolve()==extras[entry['role']]
    profile=json.loads(extras['observer_profile'].read_text());assert profile==report['method_a_execution_profile']
    assert Path(profile['path']).resolve()==extras['protection_profile'] and profile['sha256']==c.sha(extras['protection_profile'])
    assert report['method_a_effective_config_sha256']==c.canonical(report['config'])==manifest['effective_config_sha256']
    assert report['config_hash']==manifest['source_config_hash_preserved']
    exit_receipt=json.loads(c.pinned(manifest['actual_exit_receipt']).read_text())
    assert exit_receipt['schema']=='METHOD_A_PREFIX_ACTUAL_OS_EXIT_V1' and exit_receipt['authority']=='ROOT_OBSERVED_CHILD_POPEN_WAIT'
    for key in ('attempt_id','variant','source_commit','worker_pid','freeze_sha256'):assert exit_receipt[key]==manifest[key]
    assert type(exit_receipt['actual_returncode']) is int and exit_receipt['actual_returncode']==0
    assert supervisor['actual_exit_receipt']==manifest['actual_exit_receipt']
    if g['label']=='P1':
        prior=json.loads(c.pinned(freeze['previous_financial_qualification']).read_text())
        assert prior['schema']=='CM_METHOD_A_FINANCIAL_QUALIFICATION_V1' and prior['label']=='P0' and prior['accounting_qualified'] is True
        assert prior['source_commit']==c.SOURCE and prior['native_input_sha256']==link['native_input_sha256']
        assert prior['common_economic_identity_sha256']==link['common_economic_identity_sha256'] and prior['public_profile_sha256']==link['public_profile_sha256']
        prior_freeze=json.loads(c.pinned(prior['freeze']).read_text())
        other=json.loads(c.pinned(prior_freeze['kwargs_payload']).read_text())
        for payload in (kwargs,other):
            payload['research_method_a_tp']=False;payload['artifact_label']='<CONTROL_LABEL>';payload['artifact_dir']='<ARTIFACT_NAMESPACE>'
        assert kwargs==other,'P0_P1_ECONOMIC_KWARGS_DRIFT'
    output=Path(g['output']).resolve();assert output.is_absolute() and not output.exists()
    binding=dict(attempt_id=g['attempt_id'],label=g['label'],source_commit=c.SOURCE,report_path=str(report_path),report_sha256=g['report']['sha256'],
        native_ledger_path=str(ledger_path),completed_attempt_sha256=g['completed_attempt_sha256'],physical_identity=link,artifact_roles=expected_roles,
        completion_manifest_path=str(c.pinned(g['completion_manifest']).resolve()),completion_manifest_sha256=g['completion_manifest']['sha256'],
        supervisor_path=str(c.pinned(g['supervisor']).resolve()),supervisor_sha256=g['supervisor']['sha256'])
    return dict(gate=g,freeze=freeze,report=report,profile=profile,roles={key:Path(entry['path']) for key,entry in expected_roles.items()},extras=extras,
        physical_binding=binding,output=output,root_gate_sha256=expected_sha)
