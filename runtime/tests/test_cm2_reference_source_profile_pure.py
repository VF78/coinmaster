"""Measurer profile identity metadata only; no financial qualification or engine."""
from pathlib import Path
import json
import pytest
from coinmaster.research import cm2_committed_validation as v


def pinned_request(tmp_path,mutate=None):
    root=Path(v.__file__).parents[3];source=Path(v.__file__).with_name('minute_risk.py')
    policy={'version':'cm2-btc-reference-v1'}
    request={'source_family':'CM2BTCREF','execution_source_root':str(root),'policy':policy,
        'freeze_files':[{'path':str(p),'sha256':v.sha(p)} for p in
            (source,source.with_name('paired_observer.py'),source.with_name('native_baseline.py'))]}
    if mutate:mutate(request)
    path=tmp_path/'synthetic-request.json';path.write_text(json.dumps(request))
    return source,{'cm2':{'policy':policy}},{'request':{'path':str(path),'sha256':v.sha(path)}}


def test_current_family_requires_exact_request_root_and_source_freeze(tmp_path):
    source,raw,pin=pinned_request(tmp_path)
    profile=v.measurer_profile(source,raw,pin)
    assert profile['source_family']=='CM2BTCREF' and profile['dd_sha256']==v.DD_SHA
    assert profile['observer_sha256']==v.OBSERVER_SHA


@pytest.mark.parametrize('fault',['root','family','relabel','request_hash','frozen_source'])
def test_matching_dd_bytes_do_not_override_wrong_family_identity(tmp_path,fault):
    def mutate(request):
        if fault=='root':request['execution_source_root']=str(tmp_path/'wrong-root')
        if fault=='family':request['source_family']='UNKNOWN'
        if fault=='relabel':request['source_family']='REFERENCE_BTC_ONLY'
        if fault=='frozen_source':request['freeze_files'][0]['sha256']='0'*64
    source,raw,pin=pinned_request(tmp_path,mutate)
    if fault=='request_hash':pin['request']['sha256']='0'*64
    with pytest.raises(ValueError):v.measurer_profile(source,raw,pin)
