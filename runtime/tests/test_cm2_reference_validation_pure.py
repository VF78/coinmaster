"""Synthetic persisted-fact gate regressions; NOT a financial qualification/run."""
from copy import deepcopy
import csv,gzip,json,sqlite3
from pathlib import Path
import pytest
from coinmaster.research import cm2_committed_validation as v


@pytest.fixture
def facts(tmp_path):
    start=v.START;end=start+4*v.MIN
    db=tmp_path/'synthetic.sqlite'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE funding_cash(event_id TEXT,instrument_id TEXT,ts_event INTEGER,before_total TEXT,after_total TEXT,signed_delta TEXT)')
    scan={'terminal_native_cash':'10000','native_fill_cash_delta':'0','native_funding_cash_delta':'0',
        'fill_ids':[],'funding_ids':[],'kind_counts':{'PREQUOTE_DIRECT_NATIVE':8,'DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED':1}}
    obs={'status':'PASS','unknown':[],'end_exclusive_ns':end,'terminal_actual_cash':'10000',
        'native_cash_transitions':{'seed':'10000','terminal_cash':'10000','native_fill_cash_delta_total':'0',
            'native_funding_cash_delta_total':'0','exact_bridge':'0'}}
    report={'terminal_total':'10000','native_cash_reconciliation':{'signed_funding':'0',
        'native_position_lifecycle_export':{'unknown':[],'positions':[]},'native_realized_total':'0',
        'status':'EXACT','unallocated_bridge':'0'},'coherent_native_observer':obs,'fill_audit':[],
        'native_fees':'0','fee_attribution':{'native_total':'0','audited_total':'0','reconciled':True},
        'funding_cash_audit':[],'funding':{'signed_amount':'0'},'terminal_open_positions':0,
        'terminal_lifecycle':{'status':'FLAT'},'native_strategy_events':{'terminal_open_orders':0},
        'streaming':{'processed_rows_per_source':4},'config':{'accounting_currency':'USDC',
            'deposit_protection':'DISABLED_CLEAN_EXECUTION_DIAGNOSTIC_ONLY'}}
    return report,scan,db,end


def test_original_full_counts_and_money_predicates_unchanged(facts):
    report,scan,db,_=facts;report['coherent_native_observer']['end_exclusive_ns']=v.END
    report['streaming']['processed_rows_per_source']=1051200;scan['kind_counts']['PREQUOTE_DIRECT_NATIVE']=2102400
    checks=v.financial_checks(report,scan,db)
    assert all(value for key,value in checks.items() if key!='verified_financial_predicates')
    months=v.expected_month_rows(v.START,v.END)
    assert len(months)==24 and sum(months.values())==1051199


@pytest.mark.parametrize('kind,reason',[('cash','NATIVE_TERMINAL_TOTAL_MISMATCH'),
    ('end','ORIGINAL_OBSERVER_END_BOUNDARY_GATE_FAILED'),('funding','CONVERSION'),
    ('currency','ORIGINAL_FULL_ACCOUNTING_GATE_FAILED'),('minute','ORIGINAL_FULL_ACCOUNTING_GATE_FAILED'),
    ('unknown','NATIVE_OBSERVER_NOT_COMPLETE'),('orders','NATIVE_TERMINAL_RESIDUE')])
def test_invalid_actual_fact_cannot_be_qualified(facts,kind,reason):
    report,scan,db,end=facts
    if kind=='cash':report['terminal_total']='10000.00000001'
    if kind=='end':report['coherent_native_observer']['end_exclusive_ns']+=v.MIN
    if kind=='funding':report['funding']['signed_amount']='UNKNOWN'
    if kind=='currency':report['config']['accounting_currency']='BTC'
    if kind=='minute':report['streaming']['processed_rows_per_source']=3
    if kind=='unknown':report['coherent_native_observer']['unknown']=['unclassified cash']
    if kind=='orders':report['native_strategy_events']['terminal_open_orders']=1
    with pytest.raises((ValueError,ArithmeticError)) as error:v.financial_checks(report,scan,db,end=end,minutes=4)
    if kind!='funding':assert reason in str(error.value)


def test_foreign_commission_currency_not_numeric_zero(facts):
    report,scan,db,end=facts;report['fill_audit']=[{'trade_id':'synthetic-id','commission':'0','commission_currency':'BTC'}]
    scan['fill_ids']=['synthetic-id']
    with pytest.raises(ValueError,match='FEE_CURRENCY'):v.financial_checks(report,scan,db,end=end,minutes=4)


def test_prefix_actual_csv_missing_minute_rejected_and_never_full(tmp_path):
    path=tmp_path/'synthetic.csv.gz';start=v.START;end=start+4*v.MIN
    def write(indices):
        with gzip.open(path,'wt',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['source_quote_ns','receipt_ns'])
            writer.writerows((start+i*v.MIN,start+(i+1)*v.MIN) for i in indices)
    write([1,2,3]);coverage=v.interval_coverage(path,start,end)
    assert coverage['rows']==3 and coverage['scope']=='PREFIX' and coverage['full'] is False
    write([1,3])
    with pytest.raises(ValueError,match='SEQUENCE'):v.interval_coverage(path,start,end)


def test_frozen_source_mismatch_fails_actual_qualifier_entry(tmp_path):
    root=tmp_path/'source';research=root/'runtime/coinmaster/research';research.mkdir(parents=True)
    source=research/'minute_risk.py';source.write_text('# synthetic invalid source')
    for name in ('paired_observer.py','native_baseline.py'):
        (research/name).write_bytes(Path(v.__file__).with_name(name).read_bytes())
    policy={'version':'cm2-btc-reference-v1'}
    raw=tmp_path/'synthetic.json';raw.write_text(json.dumps({'cm2':{'policy':policy}}))
    request=tmp_path/'request.json';request.write_text(json.dumps({'source_family':'CM2BTCREF',
        'execution_source_root':str(root),'policy':policy,'freeze_files':[{'path':str(p),'sha256':v.sha(p)}
            for p in (source,research/'paired_observer.py',research/'native_baseline.py')]}))
    provenance={'request':{'path':str(request),'sha256':v.sha(request)}}
    with pytest.raises(ValueError,match='FROZEN_NATIVE_MEASURER_SOURCE_MISMATCH'):
        v.qualify(raw,tmp_path/'legacy',tmp_path/'trace',tmp_path/'derived',source,tmp_path/'coverage',1,
            expected_start_ns=v.START,expected_end_ns=v.START+4*v.MIN,provenance=provenance)


def test_report_request_identity_and_wrong_month_fail_unchanged_boundaries():
    from coinmaster.research.native_baseline import assert_report_boundaries
    interval={'start':'2024-09-01T00:00:00+00:00','end_exclusive':'2024-09-01T00:04:00+00:00','initial_active_seed':'10000'}
    report={'run_interval':interval,'config':{'run_interval':dict(interval)},'summary':{
        'monthly_returns':[{'month':'2024-09','total':'10000','return':'0'}],
        'interval_cash_terminal_total':'10000','drawdown_start':interval['start'],'drawdown_trough':interval['start']},
        'post_boundary_settlement':{'convention':'TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS','fill_count':0},
        'fill_timestamps_ns':[]}
    assert v.report_interval(report,v.START,v.START+4*v.MIN)==4
    assert_report_boundaries(report)
    bad=deepcopy(report);bad['summary']['monthly_returns'][0]['month']='2024-10'
    with pytest.raises(ValueError,match='MONTHLY_INTERVAL_COVERAGE'):assert_report_boundaries(bad)
    with pytest.raises(ValueError,match='REQUEST_REPORT_INTERVAL_IDENTITY'):v.report_interval(report,v.START,v.END)
