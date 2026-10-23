"""Final saved-artifact QA only: no engine, trace scan or economic simulation."""
from pathlib import Path
from decimal import Decimal as D
import json, hashlib, re, datetime

r=Path(__file__).resolve().parent
read=lambda n:json.loads((r/n).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks={}
def ck(name, condition):
    checks[name]=bool(condition)
    assert condition, name

m=read('verifier-C1_CORRECTED-manifest.json')
for category in ['files','audit_outputs']:
    for name,pin in m[category].items():ck('independent_hash:'+name,sha(r/name)==pin)
p=read('protocol-freeze.json')
for name,pin in p['tooling_pins'].items():ck('original_freeze:'+name,sha(r/name)==pin)
ad=read('verifier-C1_CORRECTED-adjudication.json')
a=read('verifier-C1_CORRECTED-audit/verifier-C1_CORRECTED-audit.json')
c=read('comparison.json')['rows']
s=read('selection.json')
b=read('root-launch-budget.json')
ck('native_checks_44',len(a['checks'])==44 and all(a['checks'].values()) and not a['failed_checks'])
ck('mechanism_933',sum(ad['mechanisms']['checks_evaluated'].values())==933 and ad['mechanisms']['mechanism_acceptance'] and not ad['mechanisms']['failed_checks'])
ck('original_fail_preserved',ad['original_frozen_report_preserved'] and len(a['C1_witness']['failed_checks'])==13)
ck('one_trace_pass',m['trace_passes']==1 and m['supplement_trace_passes']==0 and m['native_engines']==0)
ck('coverage',a['risk']['receipts']==1051199 and a['risk']['missing_source_minutes']==a['risk']['invalid_timestamp_rows']==0)
ck('months24',len(a['risk']['monthly'])==24)
for row in c:
    label=row['variant']
    ck(label+'_ROI',D(row['ROI_percent'])==(D(row['TOTAL'])/10000-1)*100)
    ck(label+'_profitretention',D(row['S0_net_profit_retained_percent'])==(D(row['TOTAL'])-10000)/D('6067107.23887483')*100)
    ck(label+'_fee_sum',D(row['maker_fees'])+D(row['taker_fees'])==D(row['total_fees']))
    ck(label+'_fills',row['BTC_fills']+row['SOL_fills']==row['fills'])
ck('C1_money_identical',c[2]['TOTAL']==a['TOTAL']==ad['money_unchanged']['TOTAL'])
ck('DD_identical',c[2]['global_settled_minute_DD_percent']==a['risk']['global_settled_DD_percent']==ad['global_DD_unchanged'])
ck('selection_fail_both',not s['passes_profit_floor'] and not s['passes_DD'] and D(c[2]['TOTAL'])<D(s['TOTAL_floor']) and D(c[2]['global_settled_minute_DD_percent'])>50)
ck('budget_closed',b['started']==b['completed']==2 and b['active']==b['reserved']==0 and b['GO_for_further_attempts'] is False and b['unused_closed_slots']==2)
ck('childexit_not_invented',b['engines'][1]['native_child_exact_exit']=='UNKNOWN' and b['engines'][1]['wrapper_exit_code']==1)
ck('pilot_controls_unchanged',s['pilot_changes']==s['archived_S0_E4_reruns']==0 and not s['candidate_deployed'])
for link in re.findall(r'\]\(([^)]+)\)',(r/'REPORT.md').read_text()):
    if not link.startswith(('https://','http://')):ck('report_link:'+link,(r/link).exists())
out=dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks_passed=len(checks),checks=checks,economic_goal='NOT_MET',new_engines=0,full_trace_passes_added=0)
(r/'root-validation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(status='PASS',checks=len(checks),goal='NOT_MET',new_engines=0)))
