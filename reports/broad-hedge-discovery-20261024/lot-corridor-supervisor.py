"""One authorized physical attempt, durable claim before Popen; no auto restart."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys


def write_json(path, value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as f:
        json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,required=True)
    ap.add_argument('--ledger',type=Path,required=True);ap.add_argument('--variant',choices=['OFF','B2','B2_F0'],required=True)
    ap.add_argument('--namespace',type=Path,required=True);ap.add_argument('--worker-attempt')
    args=ap.parse_args();f=json.loads(args.freeze.read_text())
    sys.path.insert(0,str(Path(f['source_root'])/'runtime'))
    from coinmaster.research.paired_prefix_run import claim_attempt,finish_attempt,verify_freeze,prepare_native_call,execute_prepared_call,sha
    result=args.namespace/'result'
    if args.worker_attempt:
        attempt=args.worker_attempt
        entry=next(a for a in json.loads(args.ledger.read_text())['attempts'] if a['attempt_id']==attempt)
        if entry['status']!='STARTED' or entry['source_commit']!=f['source_commit'] or entry['variant']!=args.variant:
            raise ValueError('ACTUAL_DURABLE_CLAIM_REQUIRED')
        try:
            verify_freeze(f)
            if result.exists():raise ValueError('FRESH_RESULT_DIRECTORY_REQUIRED')
            result.mkdir()
            import nautilus_trader
            if nautilus_trader.__version__!='1.231.0':raise ValueError('PINNED_NATIVE_ENGINE_VERSION_REQUIRED')
            from coinmaster.research.native_baseline import save_diagnostic_report
            from coinmaster.research.native_audit import audit_json_default
            native=execute_prepared_call(prepare_native_call(f,args.variant,result))
            native=json.loads(json.dumps(native,default=audit_json_default))
            native['physical_prefix_attempt']=dict(attempt_id=attempt,variant=args.variant,ledger=str(args.ledger),source_commit=f['source_commit'])
            path=save_diagnostic_report(Path(f['data_root']),native,'paired-prefix-'+args.variant,result)
            finish_attempt(args.ledger,attempt,'COMPLETED',dict(report=str(path),report_sha256=sha(path),coherent_observer=native['coherent_native_observer']['status'],paired_failures=native['paired_prefix_audit']['failures']))
        except BaseException as error:
            finish_attempt(args.ledger,attempt,'FAILED',dict(error_type=type(error).__name__,error=str(error)));raise
        return
    # Default entry is the only launcher. Child-start/import/export failures all
    # follow this durable physical claim. It is never retried automatically.
    if args.namespace.exists():raise ValueError('FRESH_NAMESPACE_REQUIRED')
    attempt=claim_attempt(args.ledger,f,args.variant,result)
    receipt=dict(attempt_id=attempt,source_commit=f['source_commit'],variant=args.variant,
        freeze=str(args.freeze),freeze_sha256=sha(args.freeze),supervisor_sha256=sha(__file__),actual_returncode=None)
    try:
        args.namespace.mkdir(parents=True)
        receipt_path=args.namespace/'supervisor-receipt.json';write_json(receipt_path,receipt)
        env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','PYTHONPATH':str(Path(f['source_root'])/'runtime'),
             'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONUNBUFFERED':'1'}
        command=[sys.executable,str(Path(__file__).resolve()),'--freeze',str(args.freeze.resolve()),'--ledger',str(args.ledger.resolve()),'--variant',args.variant,'--namespace',str(args.namespace.resolve()),'--worker-attempt',attempt]
        with (args.namespace/'native.log').open('wb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,cwd=f['source_root'])
            receipt.update(pid=child.pid,supervisor_pid=os.getpid());write_json(receipt_path,receipt)
            print(json.dumps(dict(status='PHYSICAL_ATTEMPT_STARTED_SUPERVISOR_WAITING',attempt_id=attempt,pid=child.pid)),flush=True)
            rc=child.wait()
        receipt['actual_returncode']=rc
        current=next(a for a in json.loads(args.ledger.read_text())['attempts'] if a['attempt_id']==attempt)
        if current['status']=='STARTED':finish_attempt(args.ledger,attempt,'FAILED',dict(error='WORKER_EXIT_WITHOUT_DURABLE_COMPLETION',actual_returncode=rc))
        receipt['ledger_status']=next(a for a in json.loads(args.ledger.read_text())['attempts'] if a['attempt_id']==attempt)['status']
        write_json(receipt_path,receipt);print(json.dumps(receipt),flush=True)
        raise SystemExit(rc)
    except SystemExit:raise
    except BaseException as error:
        current=next(a for a in json.loads(args.ledger.read_text())['attempts'] if a['attempt_id']==attempt)
        if current['status']=='STARTED':finish_attempt(args.ledger,attempt,'FAILED',dict(error_type=type(error).__name__,error=str(error),where='SUPERVISOR_OR_POPEN'))
        raise


if __name__=='__main__':main()
