"""One already-claimed prefix process. No order/cash model outside native source."""
from pathlib import Path
import argparse,json,sys,importlib.util,traceback
COMMON=Path(__file__).with_name('a0-prefix-common.py')
spec=importlib.util.spec_from_file_location('a0_prefix_common',COMMON);common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',type=Path,required=True);ap.add_argument('--ledger',type=Path,required=True);ap.add_argument('--variant',choices=common.ORDER,required=True);ap.add_argument('--namespace',type=Path,required=True);ap.add_argument('--worker-attempt',required=True);a=ap.parse_args()
    g=common.load_freeze(a.freeze)
    common.verify_worker_claim(a.ledger,g,a.variant,a.namespace,a.worker_attempt)
    try:
        common.verify_freeze(g,a.variant,a.namespace)
        result=a.namespace/'result'
        if result.exists():raise ValueError('FRESH_NATIVE_RESULT_JOURNAL_REQUIRED')
        result.mkdir()
        sys.path.insert(0,str(Path(g['source_root'])/'runtime'))
        import nautilus_trader
        if nautilus_trader.__version__!='1.231.0':raise ValueError('EXACT_NATIVE_ENGINE_REQUIRED')
        from coinmaster.research.native_baseline import run_native_diagnostic,save_diagnostic_report
        from coinmaster.research.native_audit import audit_json_default
        kwargs=common.prepared_kwargs(g,a.variant,result)
        native=run_native_diagnostic(**kwargs)
        native=json.loads(json.dumps(native,default=audit_json_default))
        native['physical_prefix_attempt']=dict(attempt_id=a.worker_attempt,variant=a.variant,ledger=str(a.ledger.resolve()),source_commit=common.SOURCE)
        path=save_diagnostic_report(Path(g['data_root']),native,a.variant,result)
        manifest=dict(status='NATIVE_RETURNED_AND_EXPORTED_PENDING_ACTUAL_OS_RC',attempt_id=a.worker_attempt,variant=a.variant,source_commit=common.SOURCE,artifacts=common.artifact_rows(a.namespace,a.variant),report=str(path),report_sha256=common.sha(path),financial_acceptance='ROOT_REVIEW_REQUIRED')
        common.write(a.namespace/'native-completion-proposal.json',manifest)
        print(json.dumps(dict(status=manifest['status'],attempt_id=a.worker_attempt,report=str(path))),flush=True)
    except BaseException as error:
        common.write(a.namespace/'worker-error.json',dict(attempt_id=a.worker_attempt,error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc()))
        raise
if __name__=='__main__':main()
