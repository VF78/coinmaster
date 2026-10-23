"""Hash and close saved owner outputs only. Never creates an engine or modifies source."""
import csv,hashlib,json
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/b-50-90-next-20261023')
SOURCE='bd04c9b3858bcda40060a08eff488849c69af5d8'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def ref(p):return dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size)
def save(name,d):(R/name).write_text(json.dumps(d,indent=2)+'\n')
now=datetime.now(timezone.utc).isoformat()
b=json.load((R/'owner-run-budget.json').open());assert b['started']==b['completed']==len(b['attempts'])==8 and b['current_engine'] is None and b['reserved']==0
assert b['conditional_authorized']==0
receipts=[]
for attempt in b['attempts']:
 recipe=attempt['recipe'];rc=json.load((R/f'owner-{recipe}-receipt.json').open())
 assert rc['source_commit']==SOURCE and all(rc['mechanical_checks'].values()) and rc['status']=='VALID_NATIVE_COMPLETED'
 assert rc['settled_observer_coverage']['complete'] and rc['settled_observer_coverage']['receipts']==1051199
 assert Decimal(rc['settled_native_DD_percent'])>55 # No winner / near gate, no conditional runs.
 saved=[ref(p) for p in sorted((J/recipe/'result').iterdir()) if p.is_file()]
 receipts.append(dict(recipe=recipe,receipt=ref(R/f'owner-{recipe}-receipt.json'),completion=ref(J/recipe/'completion.json'),start=ref(J/recipe/'start.json'),preparation=ref(J/recipe/'preparation.json'),expected_config=ref(J/recipe/'expected-config.json'),native_log=ref(J/recipe/'native.log'),native_files=saved,resources=rc['resources'],total=rc['total'],retention_percent=rc['profit_retention_percent'],settled_DD_percent=rc['settled_native_DD_percent'],config_sha256=rc['config_sha256'],data_sha256=rc['data_sha256'],execution_policy_sha256=rc['policy_sha256'],source_commit=SOURCE,actual_argv=attempt['argv'],actual_timed_argv=attempt['timed_argv']))
source_manifest=json.load((J/'source-bd04c9b-sha256.json').open())
assert all(sha(J/'source-bd04c9b'/p)==s for p,s in source_manifest.items())
assert all(not (J/'source-bd04c9b'/p).stat().st_mode&0o222 for p in source_manifest)
alias=list(csv.DictReader((R/'owner-Z-slot-alias-reconstruction.csv').open()));assert len(alias)==74 and all(x['exact_equal']=='True' for x in alias)
mechanics=list(csv.DictReader((R/'owner-activation-mechanical-checks.csv').open()));assert len(mechanics)==8 and all(x['actual_fill_qty_equal']=='True' for x in mechanics)
proofs={name:json.load((R/f'owner-{name}-arm-equivalence.json').open()) for name in ('Z','XZ','XZS')}
assert all(d['status']=='PASS_BENCHMARK_SPECIFIC_EQUIVALENCE' for d in proofs.values())
resources={k:str(sum((Decimal(str(rc['resources'][k])) for rc in receipts),Decimal(0))) for k in ('time_real_seconds','user_seconds','system_seconds')}
resources['maximum_resident_set_size_bytes']=max(rc['resources']['maximum_resident_set_size_bytes'] for rc in receipts)
resources['qualification']='Sum of eight /usr/bin/time -l native wrappers; peak RSS is maximum, not sum; offline analysis excluded.'
save('owner-physical-resource-summary.json',dict(source_commit=SOURCE,main_physical_attempts=8,conditional_physical_attempts=0,invalid_physical_native_attempts=0,prelaunch_incident='owner-prelaunch-incident.json (no native invocation, not an economic attempt)',resources=resources,runs=[dict(recipe=d['recipe'],resources=d['resources']) for d in receipts]))
b.update(stage='OWNER_COMPLETE_ALL_8_MAIN_FINALIZED_NO_CONDITIONAL_RUNS',execution_ledger_owner='root_finalization',native_launches_closed=True,owner_scope_complete=True,owner_freeze_utc=now,conditional_gate='NO_50_90_AND_NO_PREDECLARED_NEAR_PARETO',further_native_runs_authorized=False)
save('owner-run-budget.json',b)
save('owner-checkpoint.json',dict(status='OWNER_OUTPUTS_FROZEN_ALL_8_MAIN_COMPLETE_NO_GO',source_commit=SOURCE,source_mirror=str(J/'source-bd04c9b'),source_manifest='owner-file-manifest.json',budget='owner-run-budget.json',P0='owner-P0-parity.json',focused='owner-verification.json',rootcause='owner-rootcause.md',precheck_freeze='owner-precheck-freeze.json',full_runs_completed=8,full_runs_started=8,conditional_runs=0,active_engines=0,reserved=0,no_further_native_authorization=True,ledger_owner='root_finalization',no_pilot_or_services_changes=True,source_edits_after_results=False,freeze_utc=now))
ownerfiles=[]
for p in sorted(R.glob('owner-*')):
 if p.name in ('owner-file-manifest.json','owner-final-freeze.json'):continue
 files=[p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file())
 for f in files:
  q=ref(f)
  if f.suffix=='.csv':
   with f.open(newline='') as stream:q['rows']=sum(1 for _ in csv.reader(stream))-1
  ownerfiles.append(q)
manifest=dict(schema='OWNER_FINAL_OUTPUT_FREEZE_V1',frozen_utc=now,source_commit=SOURCE,source_mirror=str(J/'source-bd04c9b'),source_manifest=ref(J/'source-bd04c9b-sha256.json'),source_files_verified=89,source_files_read_only=True,source_bundle=ref(J/'source-bd04c9b.bundle'),main_completed=8,conditional_completed=0,active_engines=0,reserved=0,ledger_owner='root_finalization',further_native_authorized=False,owner_files=ownerfiles,native_runs=receipts,resources=resources,reference_contract=dict(actual_environment_and_input_pins='Per-recipe preparation.json env/input_pins and owner-run-preparation.json; historical preparation status is retained, final status is receipt+ledger.',source_argv='Per-recipe start.json and authoritative ledger preserve actual argv; native_files retain funding journal and both compressed traces.',risk_endpoint='Declared risk/calendar endpoint is preterminal; native TOTAL includes terminal closing and settlement. Do not silently compare endpoint equity with postsettlement TOTAL.',signed_funding='UNKNOWN: native audit has post-total, not signed cash delta attribution; no substitute PnL engine.',native_status='NOT_FAITHFUL_DIAGNOSTIC retained from original research artifact; mechanical validity is reported separately.',Z_qualification='armed_ns overwrites are benchmark-equivalent on all 74 armed cohorts; no general live/spread proof. Aliased terminal slots reconstructed exactly on 74/74, never treated as initial budgets.',statistical_accounting='Independent verifier owns detailed saved risk/monthly/asset-accounting exports; owner does not duplicate their scan.'))
save('owner-file-manifest.json',manifest)
save('owner-final-freeze.json',dict(status='FROZEN_OWNER_SCOPE_COMPLETE',source_commit=SOURCE,freeze_utc=now,manifest=ref(R/'owner-file-manifest.json'),main_completed=8,conditional_completed=0,active_engines=0,reserved=0,ledger_owner='root_finalization',native_launches_closed=True,no_source_changes_or_new_native_after_this_freeze=True,owner_file_count=len(ownerfiles),native_file_count=sum(len(d['native_files']) for d in receipts),all_8_mechanical_checks_PASS=True,complete_settled_receipts_each=1051199,Z_first_arm_equivalence_armed_cohorts=74,initial_slot_reconstruction_exact_cohorts=74,resources=resources))
print(json.dumps(json.load((R/'owner-final-freeze.json').open()),indent=2))
