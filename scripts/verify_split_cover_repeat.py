#!/usr/bin/env python3
"""Read-only economic identity proof for two completed native research jobs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3

JOBS=Path('/var/lib/coinmaster-native-gui/data/runs/jobs')
IDS={'episode_id','intent_id','client_order_id','venue_order_id','last_trade_id','trade_id',
     'position_id','init_id','order_list_id','linked_order_ids','parent_order_id','exec_spawn_id'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def canonical(value):
    if isinstance(value,dict):
        return {k:canonical(v) for k,v in value.items() if k not in IDS and k not in {'summary_path','trace_path'}}
    if isinstance(value,list):
        return [canonical(v) for v in value]
    return value


def result(job):
    if job.parent!=JOBS or not job.name.startswith('cm115-split-'):
        raise ValueError('UNEXPECTED_RESEARCH_JOB')
    found=[]
    for path in (job/'result').glob('*.json'):
        data=json.loads(path.read_text())
        if 'summary' in data and 'terminal_total' in data:
            found.append((path,data))
    if len(found)!=1:
        raise ValueError('EXACTLY_ONE_COMPLETED_NATIVE_RESULT_REQUIRED')
    return found[0]


def economic_csv(path):
    with Path(path).open(newline='') as stream:
        rows=[{k:v for k,v in row.items() if k not in IDS} for row in csv.DictReader(stream)]
    return sorted(rows,key=lambda row:json.dumps(row,sort_keys=True))


def funding(path):
    conn=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True,timeout=2)
    try:
        return conn.execute('SELECT instrument_id,ts_event,rate,settlement_mark,account_total_after FROM funding_events ORDER BY ts_event,instrument_id').fetchall()
    finally:
        conn.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('selected',type=Path)
    parser.add_argument('repeat',type=Path)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    jobs=[args.selected.resolve(),args.repeat.resolve()]
    results=[result(job) for job in jobs]
    a,b=[x[1] for x in results]
    checks={}
    def compare(name,left,right):
        checks[name]={'exact_equal':left==right,'selected_sha256':digest(left),'repeat_sha256':digest(right)}
        if isinstance(left,(list,dict)):
            checks[name].update(selected_count=len(left),repeat_count=len(right))
        if left!=right:
            checks[name]['mismatch']='ECONOMIC_IDENTITY_NOT_PROVEN; inspect immutable originals'
    for name in ('config','config_hash','data_hash','policy','policy_hash','native_fees','fills',
                 'native_order_rejections','terminal_total','terminal_active','terminal_reserve',
                 'terminal_open_positions','liquidation_count','liquidation_value','summary'):
        compare(name,a[name],b[name])
    for name in ('source-commit.txt','immutable-source-hashes.json','input-hashes.json'):
        compare(name,(jobs[0]/name).read_text(),(jobs[1]/name).read_text())
    for job in jobs:
        manifest=json.loads((job/'immutable-source-hashes.json').read_text())
        for path,expected in manifest.items():
            if hashlib.sha256((job/'source'/path).read_bytes()).hexdigest()!=expected:
                raise ValueError('FROZEN_SOURCE_CHANGED:'+str(job/'source'/path))
    if 'hedge_band_audit' in a or 'hedge_band_audit' in b:
        compare('hedge_band_native_lifecycle',canonical(a.get('hedge_band_audit')),canonical(b.get('hedge_band_audit')))
    compare('fill_audit_economic_ordered',canonical(a['fill_audit']),canonical(b['fill_audit']))
    for kind in ('fills','orders'):
        compare('native_'+kind+'_economic_signature',economic_csv(a['execution_artifacts'][kind]['path']),economic_csv(b['execution_artifacts'][kind]['path']))
    compare('parent_lots_and_planref_catchup_audit',canonical(a['split_cover_audit']['parents']),canonical(b['split_cover_audit']['parents']))
    compare('entry_sizing_plans',canonical(a['entry_sizing_audit']),canonical(b['entry_sizing_audit']))
    compare('all_marked_and_conditional_risk',canonical(a['minute_risk_observations']),canonical(b['minute_risk_observations']))
    compare('streaming_event_schedule',{k:v for k,v in a['streaming'].items() if k!='peak_rss_bytes'},{k:v for k,v in b['streaming'].items() if k!='peak_rss_bytes'})
    fa,fb=funding(a['funding_journal']),funding(b['funding_journal'])
    compare('native_funding_instrument_time_rate_mark_account_total_after',fa,fb)
    passed=all(item['exact_equal'] for item in checks.values())
    receipt={'status':'EXACT_ECONOMIC_REPEAT_PASS' if passed else 'REPEAT_MISMATCH',
        'selected_job':str(jobs[0]),'repeat_job':str(jobs[1]),
        'source_commit':(jobs[0]/'source-commit.txt').read_text().strip(),
        'checks':checks,'terminal_total':a['terminal_total'],'native_fees':a['native_fees'],'fills':a['fills'],
        'parents':len(a['split_cover_audit']['parents']),'markedDD_percent':a['minute_risk_observations']['curves']['all_native_close_samples']['top3_distinct_excursions'][0]['drawdown_peak_percent'],
        'minimum_marked_equity':a['minute_risk_observations']['curves']['all_native_close_samples']['minimum']['equity'],
        'funding_fields':['instrument_id','ts_event','rate','settlement_mark','account_total_after'],
        'excluded_identity_columns':sorted(IDS),'excluded_paths':['summary_path','trace_path'],
        'excluded_performance_field':'streaming.peak_rss_bytes',
        'raw_artifacts':[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path,_ in results],
        'raw_json_identity_expected':False,'native_signed_funding_amount':a['funding']['signed_amount'],
        'scope':'RESEARCH_ONLY; no promotion/activation or intrabar-safety proof'}
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'checks':len(checks),'funding_rows':len(fa),'receipt':str(args.receipt)}))
    if not passed:
        raise SystemExit(1)


if __name__=='__main__':
    main()
