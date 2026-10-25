"""Only synthetic temporary budget files. No native/Popen/real amendment."""
from pathlib import Path
import importlib.util,tempfile,json,copy
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a0_prefix_common',P/'a0-prefix-common.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
def main():
 checks=[];original_job=c.JOB;original_parent=c.FAILED_INITIAL_PARENT_SHA
 def deny(call,tag):
  try:call()
  except (ValueError,KeyError,FileNotFoundError):checks.append(tag);return
  raise AssertionError('Accepted '+tag)
 with tempfile.TemporaryDirectory(prefix='a0-amend4-UNIT-',dir='/private/tmp') as temp:
  t=Path(temp);c.JOB=t/'UNIT_JOB';c.JOB.mkdir();parent={'physical_max':3,'physical_started':1,'protocol_sha256':c.PROTOCOL,'attempts':[{'attempt_id':'UNIT_OLD_FAILED_OFF','status':'FAILED','variant':'R2_OFF','source_commit':c.SOURCE,'physical_index':1}]};pp=t/'UNIT_PARENT.json';c.write(pp,parent);c.FAILED_INITIAL_PARENT_SHA=c.sha(pp)
  l=copy.deepcopy(parent);l.update(physical_max=4,parent_prefix_ledger_sha256=c.FAILED_INITIAL_PARENT_SHA);lp=t/'UNIT_DERIVED_LEDGER.json';c.write(lp,l)
  r=t/'UNIT_ROOT_RECEIPT.json';c.write(r,{'UNIT_TEST_ONLY':True})
  g=dict(source_commit=c.SOURCE,protocol_sha256=c.PROTOCOL,variant='R2_OFF',prefix_phase='AMEND4',phase_namespace_root=str(c.JOB/'prefix-amend4'),physical_prefix_max=4,full=0,training=0,downloads=0,calendar='[2024-09-01T00:00:00Z,2025-01-15T00:00:00Z)',seed='10000',reserve='0',root_go=True,independent_review='PASS',engineering_acceptance='LIMITED_PASS',launch_gates='PASS',root_go_receipt=dict(path=str(r),sha256=c.sha(r)),engineering_acceptance_receipt=dict(path=str(r),sha256=c.sha(r)),parent_prefix_ledger=dict(path=str(pp),sha256=c.FAILED_INITIAL_PARENT_SHA),previous_financial_qualifications=[],previous_accepted_attempt_ids=[],_freeze_sha256='UNIT_FREEZE')
  ns=c.JOB/'prefix-amend4'/'R2_OFF'
  deny(lambda:c.claim(lp,g,'R2_OFF',ns),'Noowneramendmentblocksphase4')
  approval=dict(status='APPROVED_BY_OWNER',source_commit=c.SOURCE,protocol_sha256=c.PROTOCOL,parent_prefix_ledger_sha256=c.FAILED_INITIAL_PARENT_SHA,authorized_prefix_total=4,additional_prefix_attempts=1,prefix_phase='AMEND4',new_phase_variants=list(c.ORDER),full=0,training=0,downloads=0,exact_owner_reply='UNIT TEST ONLY NO REAL APPROVAL')
  ap=t/'UNIT_APPROVAL.json';c.write(ap,approval);g['prefix_budget_amendment']=dict(path=str(ap),sha256=c.sha(ap))
  no=copy.deepcopy(g);no['root_go']=False;deny(lambda:c.claim(lp,no,'R2_OFF',ns),'OwneralonewithoutROOTGOblocks')
  for value in (None,False,4,' '):
   q=dict(approval);q['exact_owner_reply']=value;c.write(ap,q);g['prefix_budget_amendment']['sha256']=c.sha(ap);deny(lambda:c.claim(lp,g,'R2_OFF',ns),'Invalidtypedownerreply:'+repr(value))
  c.write(ap,approval);g['prefix_budget_amendment']['sha256']=c.sha(ap)
  deny(lambda:c.claim(lp,g,'R2_OFF',c.JOB/'R2_OFF'),'Originalfailednamespacecannotbereused')
  aid=c.claim(lp,g,'R2_OFF',ns);new=json.loads(lp.read_text());assert new['physical_started']==2 and new['attempts'][:1]==parent['attempts'] and new['attempts'][1]['physical_index']==2 and new['attempts'][1]['phase_index']==1 and new['attempts'][1]['prefix_phase']=='AMEND4';checks.append('Newphasephysical2preservesfailedrow1exact')
  c.verify_worker_claim(lp,g,'R2_OFF',ns,aid);checks.append('Workerrechecksimmutableparentandphysicalphaseindex')
  badparent=copy.deepcopy(new);badparent['attempts'][0]['status']='COMPLETED';c.write(lp,badparent)
  deny(lambda:c.verify_worker_claim(lp,g,'R2_OFF',ns,aid),'Parenttamperbetweenclaimandworkerblocks')
  c.write(lp,new)
  c.finish(lp,aid,'FAILED',{'UNIT_TEST_ONLY':True})
  deny(lambda:c.claim(lp,g,'R2_OFF',ns),'NEWphaseFAILEDcannotretryorreset')
  nextg=copy.deepcopy(g);nextg['variant']='R2_C0';deny(lambda:c.claim(lp,nextg,'R2_C0',c.JOB/'prefix-amend4'/'R2_C0'),'NEWphaseFAILEDcannotadvanceC0')
  corrupted=json.loads(lp.read_text());corrupted['attempts'][0]['status']='COMPLETED';c.write(lp,corrupted);deny(lambda:c.claim(lp,g,'R2_OFF',ns),'Oldfailedrowcannotbereclassified')
  atcap=copy.deepcopy(parent);atcap.update(physical_max=4,physical_started=4,parent_prefix_ledger_sha256=c.FAILED_INITIAL_PARENT_SHA)
  atcap['attempts'] += [dict(attempt_id='UNIT_CAP_'+str(i),status='COMPLETED',prefix_phase='AMEND4',physical_index=i,source_commit=c.SOURCE) for i in (2,3,4)];c.write(lp,atcap)
  deny(lambda:c.claim(lp,g,'R2_OFF',ns),'HardTOTAL4ceilingblocksanyfifth')
  assert c.sha(pp)==c.FAILED_INITIAL_PARENT_SHA
 c.JOB=original_job;c.FAILED_INITIAL_PARENT_SHA=original_parent
 current=json.loads((P/'a0-prefix-ledger.json').read_text());assert current['physical_max']==3 and current['physical_started']==1 and current['attempts'][0]['status']=='FAILED'
 assert c.sha(P/'a0-prefix-ledger.json')==original_parent and not (P/'a0-prefix-amended-four-ledger.json').exists()
 out=dict(status='PASS_ENGINE_FREE_ONLY_NO_REAL_AMENDMENT',checks=checks,check_count=len(checks),actual_prefix_spent=1,actual_prefix_max=3,actual_budget_changed=False,actual_engines=0,actual_Popen=0,actual_parent_sha256=original_parent,temporary_fake_approval_only=True)
 c.write(P/'a0-prefix-amend4-guard-verification.json',out);print(json.dumps(out))
if __name__=='__main__':main()
