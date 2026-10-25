"""Exactly one physical Popen, claimed before launch. Never retries/advances variant."""
from pathlib import Path
import argparse,json,sys,os,subprocess,importlib.util,traceback
spec=importlib.util.spec_from_file_location('a0_prefix_common',Path(__file__).with_name('a0-prefix-common.py'));common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,required=True);ap.add_argument('--ledger',type=Path,required=True);ap.add_argument('--variant',choices=common.ORDER,required=True);ap.add_argument('--namespace',type=Path,required=True);mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',action='store_true');mode.add_argument('--launch',action='store_true');a=ap.parse_args()
    g=json.loads(a.freeze.read_text());g['_freeze_sha256']=common.sha(a.freeze)
    if a.prepare:
        common.verify_freeze(g,a.variant,a.namespace);sys.path.insert(0,str(Path(g['source_root'])/'runtime'));common.prepared_kwargs(g,a.variant,a.namespace/'result')
        print(json.dumps(dict(status='ENGINE_FREE_PREFIX_PREPARATION_PASS',variant=a.variant,root_go=g.get('root_go'),physical_attempts_claimed=0,engines_created=0)));return
    aid=common.claim(a.ledger,g,a.variant,a.namespace)
    receipt=dict(attempt_id=aid,variant=a.variant,source_commit=common.SOURCE,freeze=str(a.freeze.resolve()),freeze_sha256=common.sha(a.freeze),actual_returncode=None,ledger_status='STARTED',supervisor_pid=os.getpid(),started_utc=common.utc())
    receipt_path=a.namespace/'supervisor-receipt.json';rc=None
    try:
        if a.namespace.exists():raise ValueError('FRESH_PREFIX_NAMESPACE_REQUIRED')
        a.namespace.mkdir(parents=True);common.write(receipt_path,receipt)
        command=[g['python'],str(Path(g['worker']).resolve()),'--freeze',str(a.freeze.resolve()),'--ledger',str(a.ledger.resolve()),'--variant',a.variant,'--namespace',str(a.namespace.resolve()),'--worker-attempt',aid]
        env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','PYTHONPATH':str(Path(g['source_root'])/'runtime'),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONUNBUFFERED':'1','PYTHONDONTWRITEBYTECODE':'1','LANG':'en_US.UTF-8'}
        receipt['command']=command;receipt['environment']=env
        with (a.namespace/'native.log').open('wb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,cwd=g['source_root']);receipt['pid']=child.pid;common.write(receipt_path,receipt)
            print(json.dumps(dict(status='ONE_PHYSICAL_PREFIX_STARTED',attempt_id=aid,pid=child.pid)),flush=True);rc=child.wait()
        receipt['actual_returncode']=rc
        if rc!=0:raise RuntimeError('NATIVE_WORKER_NONZERO_EXIT:'+str(rc))
        proposal=json.loads((a.namespace/'native-completion-proposal.json').read_text())
        if proposal['attempt_id']!=aid or proposal['variant']!=a.variant or proposal['source_commit']!=common.SOURCE:raise ValueError('COMPLETION_IDENTITY_MISMATCH')
        artifacts=common.verify_rows(proposal['artifacts'],a.namespace,a.variant)
        manifest=dict(status='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO',attempt_id=aid,variant=a.variant,source_commit=common.SOURCE,actual_returncode=rc,freeze_sha256=receipt['freeze_sha256'],artifacts=artifacts,financial_acceptance='ROOT_REVIEW_REQUIRED')
        mp=a.namespace/'completion-manifest.json';common.write(mp,manifest)
        report=next(x for x in artifacts if x['role']=='report')
        common.finish(a.ledger,aid,'COMPLETED',dict(report=report['path'],report_sha256=report['sha256'],actual_returncode=rc,completion_manifest=str(mp),completion_manifest_sha256=common.sha(mp)))
        receipt.update(ledger_status='COMPLETED',finished_utc=common.utc(),completion_manifest=str(mp),completion_manifest_sha256=common.sha(mp));common.write(receipt_path,receipt);print(json.dumps(receipt),flush=True)
    except BaseException as error:
        receipt.update(actual_returncode=rc,ledger_status='FAILED',finished_utc=common.utc(),error_type=type(error).__name__,error=str(error))
        common.finish(a.ledger,aid,'FAILED',dict(actual_returncode=rc,error_type=type(error).__name__,error=str(error),where='SUPERVISOR_POPen_WORKER_OR_EXPORT'))
        if a.namespace.exists():common.write(receipt_path,receipt)
        else:common.write(a.ledger.with_name('a0-prefix-prelaunch-error-'+aid+'.json'),receipt)
        raise
if __name__=='__main__':main()
