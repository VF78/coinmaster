"""F01 gzip footer regression: actual cleanup AST, stubs and standard gzip only."""
import ast,copy,csv,gzip,hashlib,json
from pathlib import Path
from types import SimpleNamespace as N
import pytest
from coinmaster.research import cm2_runner as runner,cm2_reference_fixture as fixture


def actual_cleanup():
    tree=ast.parse(Path(fixture.__file__).read_text())
    run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_fixture')
    cleanup=next(n for n in run.body if isinstance(n,ast.Try))
    # Resources and all data preparation are inside the protected region.
    protected={n.func.id for n in ast.walk(ast.Module(body=cleanup.body,type_ignores=[]))
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    assert {'NativeEventJournal','NativeMinuteRiskRecorder','CommittedNativeObserver'}<=protected
    # Execute ONLY the unchanged actual finalbody; no engine/strategy constructor.
    fn=ast.parse("def cleanup_case(risk,observer,engine,journal,fail_run):\n    try:\n        if fail_run: raise RuntimeError('synthetic run failure')\n    finally:\n        pass\n").body[0]
    fn.body[0].finalbody=copy.deepcopy(cleanup.finalbody)
    scope={};exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'ACTUAL_FIXTURE_FINALLY_ONLY','exec'),scope)
    return scope['cleanup_case']


def observer_close_method():
    path=Path(runner.__file__).with_name('paired_observer.py')
    cls=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='CommittedNativeObserver')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='close')
    scope={};exec(compile(ast.Module(body=[method],type_ignores=[]),'ACTUAL_OBSERVER_CLOSE_ONLY','exec'),scope)
    return scope['close']


@pytest.mark.parametrize('fail_run',[False,True])
def test_actual_finally_closes_observer_once_and_writes_real_footer(tmp_path,fail_run):
    path=tmp_path/'synthetic.jsonl.gz';writer=gzip.open(path,'wt');writer.write('{"synthetic":true}\n');writer.flush()
    calls={'observer':0,'risk':0,'engine':0,'journal':0}
    class File:
        def close(self):calls['observer']+=1;writer.close()
    class Observer:close=observer_close_method()
    observer=Observer();observer.file=File()
    def hit(key):calls[key]+=1
    args=(N(close_writers=lambda:hit('risk')),observer,N(dispose=lambda:hit('engine')),N(close=lambda:hit('journal')),fail_run)
    if fail_run:
        with pytest.raises(RuntimeError,match='synthetic run failure'):actual_cleanup()(*args)
    else:actual_cleanup()(*args)
    assert calls=={'observer':1,'risk':1,'engine':1,'journal':1}
    with gzip.open(path,'rt') as stream:assert json.loads(stream.read())=={'synthetic':True}


def test_closer_failure_still_releases_resources_with_standard_exception_chain(tmp_path):
    path=tmp_path/'synthetic.jsonl.gz';writer=gzip.open(path,'wt');writer.write('{}\n');calls=[]
    class File:
        def close(self):calls.append('observer');writer.close();raise OSError('synthetic close failure')
    class Observer:close=observer_close_method()
    observer=Observer();observer.file=File()
    with pytest.raises(OSError,match='synthetic close failure') as error:
        actual_cleanup()(N(close_writers=lambda:calls.append('risk')),observer,
            N(dispose=lambda:calls.append('engine')),N(close=lambda:calls.append('journal')),True)
    assert calls==['risk','observer','engine','journal']
    assert isinstance(error.value.__context__,RuntimeError)
    with gzip.open(path,'rt') as stream:assert stream.read()=='{}\n'


def synthetic_exports(output):
    output.mkdir(exist_ok=True);end=fixture.END_NS
    trace=output/'coherent-native-events.jsonl.gz'
    with gzip.open(trace,'wt') as stream:
        for row in ({'sequence':1,'kind':'PREQUOTE_DIRECT_NATIVE','event_ns':str(end-1)},
                {'sequence':2,'kind':'DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED','event_ns':str(end)}):
            stream.write(json.dumps(row)+'\n')
    risk_header=['bar_open_ms','close_available_ns','phase','cash','free_cash','native_initial_margin','native_maintenance_margin',
        'paired_close_equity','conditional_adverse_equity','conditional_favorable_equity','conditional_high_mark_mm_upper',
        'conditional_margin_breach','native_positions_and_mark_ohlc_json']
    settled_header=['source_quote_ns','receipt_ns','fill_epoch','cash','paired_close_equity','native_positions_and_mark_ohlc_json']
    for name,header in [('minute-native-risk.csv.gz',risk_header),('minute-native-settled-receipts.csv.gz',settled_header)]:
        with gzip.open(output/name,'wt',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(header);writer.writerow(['0']*(len(header)-1)+['[]'])
    result={'coherent_native_observer':{'sequence_count':2},
        'minute_risk_observations':{'rows':1,'settled_native_close_receipts':{'receipts':1}}}
    return result


def test_existing_exports_fully_read_and_input_bytes_unchanged(tmp_path):
    result=synthetic_exports(tmp_path);before={p.name:p.read_bytes() for p in tmp_path.glob('*.gz')}
    proof=runner.engineering_artifact_integrity(tmp_path,result,fixture.END_NS)
    assert {k:v['rows'] for k,v in proof.items()}=={'coherent-native-events.jsonl.gz':2,
        'minute-native-risk.csv.gz':1,'minute-native-settled-receipts.csv.gz':1}
    assert all(v['sha256']==hashlib.sha256(before[k]).hexdigest() for k,v in proof.items())
    assert before=={p.name:p.read_bytes() for p in tmp_path.glob('*.gz')}


@pytest.mark.parametrize('name',['coherent-native-events.jsonl.gz','minute-native-risk.csv.gz','minute-native-settled-receipts.csv.gz'])
def test_valid_rows_but_missing_footer_fail_before_completion(tmp_path,name):
    result=synthetic_exports(tmp_path);path=tmp_path/name;path.write_bytes(path.read_bytes()[:-8])
    before=path.read_bytes()
    with pytest.raises(EOFError):runner.engineering_artifact_integrity(tmp_path,result,fixture.END_NS)
    assert path.read_bytes()==before


@pytest.mark.parametrize('fault',['terminal','csv_header','row_count'])
def test_complete_gzip_with_invalid_export_schema_is_not_integrity_pass(tmp_path,fault):
    result=synthetic_exports(tmp_path)
    if fault=='terminal':
        path=tmp_path/'coherent-native-events.jsonl.gz'
        with gzip.open(path,'wt') as stream:
            stream.write(json.dumps({'sequence':1,'kind':'PREQUOTE_DIRECT_NATIVE','event_ns':str(fixture.END_NS)})+'\n')
        result['coherent_native_observer']['sequence_count']=1
    elif fault=='csv_header':
        with gzip.open(tmp_path/'minute-native-risk.csv.gz','wt') as stream:stream.write('wrong,header\n')
    else:result['minute_risk_observations']['rows']=2
    with pytest.raises(ValueError,match='CM2_ENGINEERING_ARTIFACT'):runner.engineering_artifact_integrity(tmp_path,result,fixture.END_NS)


def test_actual_engineering_postchild_rejects_truncated_trace_before_proof(tmp_path):
    result=synthetic_exports(tmp_path);trace=tmp_path/'coherent-native-events.jsonl.gz';trace.write_bytes(trace.read_bytes()[:-8])
    (tmp_path/'fixture-result.json').write_text(json.dumps(result));(tmp_path/'engine-construction-count.json').write_text('{"engine_constructions":1}')
    request={'fixture_id':fixture.FIXTURE_ID,'artifact_dir':str(tmp_path)}
    with pytest.raises(EOFError):runner.validate_engineering_output(request)
    assert not (tmp_path/'engineering-postchild-proof.json').exists()
