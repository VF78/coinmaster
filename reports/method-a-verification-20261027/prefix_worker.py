"""One root-claimed Method-A prefix child, or root-observed exit finalization.

No supervisor/ledger mutation. A returned report cannot self-certify OS exit0.
"""
from pathlib import Path
import argparse,importlib,json,os,sys,traceback
import prefix_common as common


def worker(g,ledger_path,attempt):
    common.verify_authority(g,launch=True);common.verify_claim(g,ledger_path,attempt)
    common.verify_prior_financial(g,ledger_path)
    source=common.verify_source(g);common.verify_inputs(g)
    kwargs,proof,_=common.prepare(g)
    for key in ('recipe_sha256','native_config_sha256','native_input_sha256','kwargs_sha256','full_bound_kwargs_sha256'):assert proof[key]==g[key]
    namespace=Path(g['namespace']).resolve();assert namespace.is_dir()
    result=namespace/'result';assert not result.exists();result.mkdir()
    from prefix_observer import PrefixEvidence,observed_strategy_type,recording_engine_factory
    import nautilus_trader
    assert nautilus_trader.__version__=='1.231.0'
    import nautilus_trader.backtest.engine as engine_module
    import coinmaster.strategy.wave_overlay as strategy_module
    from coinmaster.research.native_baseline import run_native_diagnostic,save_diagnostic_report
    from coinmaster.research.native_audit import audit_json_default
    evidence=PrefixEvidence(result/'method-a-native-protection.jsonl.gz')
    original_engine=engine_module.BacktestEngine;original_strategy=strategy_module.WaveOverlayStrategy
    strategy_module.WaveOverlayStrategy=observed_strategy_type(original_strategy,evidence)
    engine_module.BacktestEngine=recording_engine_factory(original_engine,evidence)
    native=None;profile=None
    try:
        native=run_native_diagnostic(**kwargs)
    finally:
        engine_module.BacktestEngine=original_engine;strategy_module.WaveOverlayStrategy=original_strategy
        profile=evidence.close();common.write(namespace/'native-observer-profile.json',profile)
    native=json.loads(json.dumps(native,default=audit_json_default,allow_nan=False))
    assert len(profile['actual_venue_registrations'])==1
    registration=profile['actual_venue_registrations'][0]
    assert registration['liquidity_consumption'] is False and registration['bar_execution'] is True
    assert 'CommittedNativeObserver' in registration['modules_before_observer']
    native['physical_prefix_attempt']=dict(attempt_id=attempt,variant=g['label'],label=g['label'],category='prefix',
        ledger=str(Path(ledger_path).resolve()),source_commit=common.SOURCE,source_seal_sha256=g['source_seal_sha256'],
        freeze_sha256=g['_freeze_sha256'],native_config_sha256=g['native_config_sha256'],kwargs_sha256=g['kwargs_sha256'],
        full_bound_kwargs_sha256=g['full_bound_kwargs_sha256'],native_input_sha256=g['native_input_sha256'],recipe_sha256=g['recipe_sha256'])
    native['method_a_execution_profile']=profile
    # Raw source hash is preserved. Existing baseline computes it before its
    # post-config metadata additions; expose a separate effective identity.
    native['method_a_effective_config_sha256']=common.canonical(native['config'])
    native['method_a_control_contract']=dict(label=g['label'],BTC_3TP='NOT_APPLICABLE_LEGACY_CONTROL' if g['label']=='P0' else 'ROOT_ACTUAL_METHOD_A_AND_NATIVE_PROFILE_REVIEW_REQUIRED',
        old_SOL='UNCHANGED_DIAGNOSTIC',financial_acceptance='ROOT_REVIEW_REQUIRED',metric_contract_sha256=common.METRIC)
    report=save_diagnostic_report(Path(g['data_root']),native,g['label'],result)
    roles=common.artifacts(namespace,g['label'],report)
    extras=[dict(role=role,path=str(path.resolve()),sha256=common.sha(path)) for role,path in (
        ('protection_profile',result/'method-a-native-protection.jsonl.gz'),('minute_risk',result/'minute-native-risk.csv.gz'),
        ('observer_profile',namespace/'native-observer-profile.json'),('raw_native',result/('method-a-'+g['label']+'-raw-native.json')))]
    proposal=dict(status='NATIVE_RETURNED_AND_EXPORTED_PENDING_ACTUAL_OS_RC',attempt_id=attempt,variant=g['label'],source_commit=common.SOURCE,
        freeze_sha256=g['_freeze_sha256'],worker_pid=os.getpid(),report=str(report.resolve()),report_sha256=common.sha(report),
        source_config_hash_preserved=native['config_hash'],effective_config_sha256=native['method_a_effective_config_sha256'],
        artifacts=roles,extra_evidence=extras,physical_identity=native['physical_prefix_attempt'],financial_acceptance='ROOT_REVIEW_REQUIRED')
    common.write(namespace/'native-completion-proposal.json',proposal)
    return proposal


def finalize(g,exit_ref):
    # This separate non-native route is invoked only AFTER root Popen.wait.
    receipt=json.loads(common.pinned(exit_ref).read_text());namespace=Path(g['namespace']).resolve()
    proposal=json.loads((namespace/'native-completion-proposal.json').read_text())
    assert receipt['schema']=='METHOD_A_PREFIX_ACTUAL_OS_EXIT_V1' and receipt['authority']=='ROOT_OBSERVED_CHILD_POPEN_WAIT'
    for key in ('attempt_id','variant','source_commit','worker_pid'):assert receipt[key]==proposal[key]
    assert type(receipt['actual_returncode']) is int and receipt['actual_returncode']==0
    assert proposal['freeze_sha256']==g['_freeze_sha256'] and proposal['variant']==g['label']
    for row in proposal['artifacts']+proposal['extra_evidence']:common.pinned(dict(path=row['path'],sha256=row['sha256']))
    manifest=dict(proposal,status='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO',actual_returncode=receipt['actual_returncode'],
        actual_exit_receipt=exit_ref,financial_acceptance='ROOT_REVIEW_REQUIRED')
    common.write(namespace/'completion-manifest.json',manifest)
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--freeze',required=True,type=Path)
    p.add_argument('--ledger',type=Path);p.add_argument('--attempt');p.add_argument('--finalize-exit-receipt',type=Path);p.add_argument('--exit-receipt-sha256')
    a=p.parse_args();g=common.load_freeze(a.freeze)
    try:
        if a.finalize_exit_receipt:
            result=finalize(g,dict(path=str(a.finalize_exit_receipt.resolve()),sha256=a.exit_receipt_sha256))
        else:
            assert a.ledger and a.attempt
            result=worker(g,a.ledger,a.attempt)
        print(json.dumps(dict(status=result['status'],attempt_id=result['attempt_id'],variant=result['variant'],report=result['report'])),flush=True)
    except BaseException as error:
        namespace=Path(g['namespace'])
        if namespace.is_dir():common.write(namespace/'prefix-worker-error.json',dict(attempt_id=a.attempt,error=repr(error),traceback=traceback.format_exc()))
        raise

if __name__=='__main__':main()
