"""Supplemental immutable exports and causal native-fill checks; no trace reads."""
from pathlib import Path
from decimal import Decimal as D
import json,csv,hashlib,sys
P=Path(__file__).resolve().parent
for recipe in sys.argv[1:]:
 r=json.loads((P/f'owner-{recipe}-receipt.json').read_text());d=json.loads(Path(r['artifact']).read_text());raw=json.loads(Path(r['raw_artifact']).read_text());a=json.loads((P/f'verifier-{recipe}-audit.json').read_text())
 checks={};exports={}
 for name,meta in r['exports'].items():
  path=Path(meta['path']);rows=list(csv.DictReader(path.open()));exports[name]=rows
  checks[name+'_frozen_hash']=hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256']
  checks[name+'_row_count']=len(rows)==meta['rows']
 events=d['next_band_audit'];fills=d['fill_audit'];risks=[f for f in fills if 'RISK' in f['reason']];rf=[e for e in events if e['event']=='RISK_FILL']
 checks['zero_BTC_Z_trigger']=not any(e['event']=='Z_TRIGGER' or e.get('kind')=='Z' for e in events)
 checks['zero_BTC_risk_order_intents']=not any(e['instrument'].startswith('BTC') and 'RISK' in e['reason'] for e in raw['native_order_events'].values())
 checks['all_actual_risk_fills_SOL_no_BTC_TP_action']=all(f['instrument'].startswith('SOL') and f['action']=='SOL_EXIT' and f['reason']=='SOL_DOMINANT_ADVERSE_RISK' for f in risks)
 checks['zero_risk_right_retirements']=all(not e.get('retired_lots') for e in rf)
 checks['risk_event_native_fill_total_exact']=sum((D(str(e['quantity'])) for e in rf),D(0))==sum((D(f['qty']) for f in risks),D(0))
 checks['risk_fill_receipts_match_native_audit']=all(sum((D(f['qty']) for f in risks if int(f['fill_ns'])==int(e['timestamp_ns'])),D(0))==D(str(e['quantity'])) for e in rf)
 nb=d['config']['next_band_research'];checks['expected_residual_flag']=bool(nb.get('sol_residual',False))==(recipe!='P0');checks['expected_minute_flag']=bool(nb.get('sol_minute',False))==(recipe in ('R2','R2C'))
 out=dict(recipe=recipe,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,failed_checks=[k for k,v in checks.items() if not v],S_triggers=[e for e in events if e['event']=='S_TRIGGER'],actual_risk_fills=risks,risk_fill_events=rf,BTC_fallback_entries=sum(e.get('branch')=='MARKETABLE_FULL_ENTRY_FALLBACK' for e in d['entry_sizing_audit']),ordinary_BTC_TP_native_fills=sum(f['reason'].startswith('BTC_TP') for f in fills),ordinary_native_SOL_exit_reasons=sorted({f['reason'] for f in fills if f['instrument'].startswith('SOL') and f not in risks}),qualification='Output checks confirm actual risk action separation and zero right retirements. Preservation of rights code paths and fallback semantics additionally depends on independent frozen-source review; later economic calendars may legitimately differ.',no_trace_read=True,no_engine=True)
 (P/f'verifier-{recipe}-mechanisms.json').write_text(json.dumps(out,indent=2)+'\n')
 a['mechanism_checks']=checks;a['mechanism_status']=out['status'];a['resource_observation']=r['resources'];a['resource_qualification']='Native saved economics independently verified. /usr/bin/time -l wrapper exit 1 due sysctl kern.clockrate denial if present; RSS UNKNOWN/null, not zero. No economic rerun.'
 if not all(checks.values()):a['status']='FAIL';a['pass_50_90']=False
 (P/f'verifier-{recipe}-audit.json').write_text(json.dumps(a,indent=2)+'\n')
 print(json.dumps(dict(recipe=recipe,status=out['status'],failed=out['failed_checks'],actual_risk_fill_rows=len(risks),BTC_fallback_entries=out['BTC_fallback_entries'])))
