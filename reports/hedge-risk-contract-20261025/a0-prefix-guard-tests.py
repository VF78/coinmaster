"""Guard plumbing tests on temporary UNIT_TEST_ONLY bytes; no native/Popen."""
from pathlib import Path
import importlib.util,tempfile,json,copy
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a0_prefix_common',P/'a0-prefix-common.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
checks=[]
def must_deny(call,label):
    try:call()
    except (ValueError,KeyError,FileNotFoundError):checks.append(label);return
    raise AssertionError('Guard accepted '+label)
def main():
    original_job=c.JOB
    with tempfile.TemporaryDirectory(prefix='a0-guard-unit-',dir='/private/tmp') as temp:
        t=Path(temp);c.JOB=t/'UNIT_TEST_ONLY_JOB';c.JOB.mkdir();lp=t/'UNIT_TEST_ONLY_LEDGER.json';ledger={'attempts':[],'physical_max':3,'physical_started':0}
        def control(label):
            ns=c.JOB/label;result=ns/'result';result.mkdir(parents=True);aid='UNIT_TEST_ONLY_'+label
            report=result/(label+'.json');c.write(report,{'UNIT_TEST_ONLY':True,'physical_prefix_attempt':dict(attempt_id=aid,variant=label,source_commit=c.SOURCE,ledger=str(lp))})
            for name in (label+'-orders.csv',label+'-funding.sqlite','coherent-native-events.jsonl.gz'):(result/name).write_bytes(b'UNIT_TEST_ONLY_NO_NATIVE_ACCOUNT')
            manifest=ns/'completion-manifest.json';c.write(manifest,dict(status='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO',attempt_id=aid,variant=label,source_commit=c.SOURCE,actual_returncode=0,freeze_sha256='UNIT_FREEZE_'+label,artifacts=c.artifact_rows(ns,label)))
            supervisor=ns/'supervisor-receipt.json';c.write(supervisor,dict(ledger_status='COMPLETED',attempt_id=aid,variant=label,source_commit=c.SOURCE,actual_returncode=0,freeze_sha256='UNIT_FREEZE_'+label,completion_manifest_sha256=c.sha(manifest)))
            entry=dict(attempt_id=aid,status='COMPLETED',variant=label,source_commit=c.SOURCE,namespace=str(ns),freeze_sha256='UNIT_FREEZE_'+label,detail=dict(report=str(report),report_sha256=c.sha(report),actual_returncode=0,completion_manifest=str(manifest),completion_manifest_sha256=c.sha(manifest)))
            ledger['attempts'].append(entry);ledger['physical_started']+=1;c.write(lp,ledger)
            snapshot=t/(label+'-UNIT_SNAPSHOT.json');c.write(snapshot,ledger)
            q=dict(schema='CM_A0_FINANCIAL_QUALIFICATION_V1',decision='FINANCIAL_ACCEPTED_CONTROL',qualification='FINANCIALLY_QUALIFIED',accounting_qualified=True,label=label,attempt_id=aid,source_commit=c.SOURCE,report_path=str(report),report_sha256=c.sha(report),native_ledger_path=str(lp),native_ledger_sha256_at_qualification=c.sha(lp),ledger_snapshot=dict(path=str(snapshot),sha256=c.sha(snapshot)),completed_attempt_sha256=c.attempt_digest(entry),risk_analysis_path=str(t/(label+'-UNIT_RISK.json')),completion_manifest_path=str(manifest),completion_manifest_sha256=c.sha(manifest),supervisor_path=str(supervisor),supervisor_sha256=c.sha(supervisor),actual_returncode=0,financial_gates={key:'PASS' for key in c.FINANCIAL_GATES},terminal_open_positions=0,terminal_open_orders=0,model_liquidations=0,metric_contract_sha256=c.METRIC_CONTRACT,UNIT_TEST_ONLY=True)
            binding={k:q[k] for k in ('attempt_id','label','source_commit','report_path','report_sha256','native_ledger_path','completed_attempt_sha256','completion_manifest_path','completion_manifest_sha256','supervisor_path','supervisor_sha256')}
            risk=Path(q['risk_analysis_path']);c.write(risk,dict(qualification='VALID_ACCOUNTED_PREFIX',accounting_qualified=True,actual_returncode=0,metric_contract_sha256=c.METRIC_CONTRACT,physical_binding=binding,UNIT_TEST_ONLY=True));q['risk_analysis_sha256']=c.sha(risk)
            receipt=t/(label+'-UNIT_FINANCIAL_RECEIPT.json');c.write(receipt,q)
            return dict(label=label,path=str(receipt),sha256=c.sha(receipt)),q
        off,qoff=control('R2_OFF');g={'physical_prefix_max':3,'previous_financial_qualifications':[off]}
        c.verify_financial_qualifications(g,ledger,lp,'R2_C0');checks.append('C0 exactOFF financialPASS chain accepted inUNITONLYdata')
        must_deny(lambda:c.verify_financial_qualifications({},ledger,lp,'R2_C0'),'MissingfinancialreceiptblocksC0')
        def changed_receipt(field,value,tag):
            bad=copy.deepcopy(qoff);bad[field]=value;file=t/('UNIT_BAD_'+tag+'.json');c.write(file,bad);ref={'label':'R2_OFF','path':str(file),'sha256':c.sha(file)}
            must_deny(lambda:c.verify_financial_qualifications({'physical_prefix_max':3,'previous_financial_qualifications':[ref]},ledger,lp,'R2_C0'),tag)
        for field,value,tag in [('qualification','UNKNOWN','UNKNOWNqualification'),('label','R2_C0','Wrongreceiptlabel'),('report_sha256','wrong','WrongreportSHA'),('attempt_id','wrong','WrongattemptUUID'),('accounting_qualified',False,'Accountingfalse'),('actual_returncode',True,'BoolisnotactualOS0')]:changed_receipt(field,value,tag)
        badgates=copy.deepcopy(qoff['financial_gates']);badgates['native_3TP']='UNKNOWN';changed_receipt('financial_gates',badgates,'UNKNOWNfinancialgate')
        badgates=copy.deepcopy(qoff['financial_gates']);badgates.pop('ownership');changed_receipt('financial_gates',badgates,'Missingfinancialgate')
        bad=copy.deepcopy(off);bad['sha256']='wrong';must_deny(lambda:c.verify_financial_qualifications({'physical_prefix_max':3,'previous_financial_qualifications':[bad]},ledger,lp,'R2_C0'),'WrongreceiptSHA')
        mutated=copy.deepcopy(ledger);mutated['attempts'][0]['extra']='mutation';must_deny(lambda:c.verify_financial_qualifications(g,mutated,lp,'R2_C0'),'Currententrydiffersfromimmutablesnapshot')
        c0,qc0=control('R2_C0');assert qoff['native_ledger_sha256_at_qualification']!=c.sha(lp)
        c.verify_financial_qualifications({'physical_prefix_max':3,'previous_financial_qualifications':[off,c0]},ledger,lp,'R2_A0');checks.append('A0OFFplusC0financialPASS surviveappendmutatedledger/exactimmutableentries')
        must_deny(lambda:c.verify_financial_qualifications({'physical_prefix_max':3,'previous_financial_qualifications':[off]},ledger,lp,'R2_A0'),'A0missingC0receipt')
        must_deny(lambda:c.verify_financial_qualifications({'physical_prefix_max':3,'previous_financial_qualifications':[off,off]},ledger,lp,'R2_A0'),'Duplicatepriorreceiptlabels')
        root=t/'UNIT_ROOT_RECEIPT.json';c.write(root,{'UNIT_TEST_ONLY':True});freeze=t/'UNIT_WORKER_FREEZE.json'
        fg=dict(source_commit=c.SOURCE,protocol_sha256=c.PROTOCOL,variant='R2_OFF',physical_prefix_max=3,full=0,training=0,downloads=0,calendar='[2024-09-01T00:00:00Z,2025-01-15T00:00:00Z)',seed='10000',reserve='0',root_go=True,independent_review='PASS',engineering_acceptance='LIMITED_PASS',launch_gates='PASS',root_go_receipt=dict(path=str(root),sha256=c.sha(root)),engineering_acceptance_receipt=dict(path=str(root),sha256=c.sha(root)),previous_financial_qualifications=[])
        c.write(freeze,fg);loaded=c.load_freeze(freeze);wl=t/'UNIT_STARTED_LEDGER.json';ns=c.JOB/'R2_OFF'
        c.write(wl,{'attempts':[dict(attempt_id='UNIT_STARTED',status='STARTED',source_commit=c.SOURCE,variant='R2_OFF',namespace=str(ns),freeze_sha256=loaded['_freeze_sha256'])]})
        c.verify_worker_claim(wl,loaded,'R2_OFF',ns,'UNIT_STARTED');checks.append('WorkerbindsactualexactreadfreezeSHAtoSTARTEDclaim')
        fg['UNIT_TAMPER_AFTER_CLAIM']=True;c.write(freeze,fg)
        must_deny(lambda:c.verify_worker_claim(wl,c.load_freeze(freeze),'R2_OFF',ns,'UNIT_STARTED'),'Freezeeditedafterclaimblocksworkerbeforeengine')
        c.verify_financial_qualifications({'physical_prefix_max':3,'previous_financial_qualifications':[]},{'attempts':[]},lp,'R2_OFF');checks.append('OFFrequiresnoinventedfinancialreceipt')
    c.JOB=original_job
    actual=json.loads((P/'a0-prefix-ledger.json').read_text());assert actual['physical_started']==1 and len(actual['attempts'])==1 and actual['attempts'][0]['status']=='FAILED'
    proof=dict(status='PASS_ENGINE_FREE_CONSOLIDATED_GUARD_BATCH',checks=checks,test_check_count=len(checks),UNIT_TEST_ONLY_temporary_receipts=True,actual_financial_receipts_created=0,actual_prefix_attempts=1,actual_Popen=0,actual_engines=0,source_money=c.SOURCE,script_pins=[dict(path=str(P/name),sha256=c.sha(P/name)) for name in ('a0-prefix-common.py','a0-prefix-worker.py','a0-prefix-supervisor.py')])
    c.write(P/'a0-prefix-guard-verification.json',proof);print(json.dumps(proof))
if __name__=='__main__':main()
