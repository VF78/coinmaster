"""Constructor-free exact Features parity and timing against executed b2 source."""
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
import sys
import time
import types
from coinmaster.strategy.cm2_policy import Config,Hour,features,HOUR_NS

BASE="b2fd9c818631f072dd5c9ca36378b355b19945f3"

def main():
    root=Path(__file__).parents[2]
    old_source=subprocess.check_output(["git","show",BASE+":runtime/coinmaster/strategy/cm2_policy.py"],cwd=root,text=True)
    previous=types.ModuleType("cm2_executed_b2_feature_reference")
    sys.modules[previous.__name__]=previous
    exec(compile(old_source,"<executed-b2-cm2-policy>","exec"),previous.__dict__)
    warm=root/"reports/btc-split-sol-cover-20261018"
    paired={}
    hashes={}
    for symbol in ("BTCUSDT","SOLUSDT"):
        path=warm/f"data-warmup-{symbol}-1h.csv"
        hashes[symbol]=hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open() as handle:
            paired[symbol]={int(r["open_time_ms"])*1_000_000+HOUR_NS:r for r in csv.DictReader(handle)}
    hours=tuple(Hour(t,t,*(float(paired["BTCUSDT"][t][k]) for k in ("open","high","low","close")),
                     float(paired["SOLUSDT"][t]["close"]))
                for t in sorted(set(paired["BTCUSDT"]) & set(paired["SOLUSDT"])))
    cases=[]
    for trend in (24,72,168):
        for count in (0,1,168,169,170,171,200,500,1000,2208):
            prefix=hours[:count]
            now=prefix[-1].available_ns if prefix else 0
            cfg=Config(trend_hours=trend)
            before=asdict(previous.features(prefix,cfg,now))
            after=asdict(features(prefix,cfg,now))
            if before!=after:
                raise AssertionError({"trend":trend,"prefix_hours":count,"before":before,"after":after})
            cases.append({"trend_hours":trend,"prefix_hours":count,"available_ns":now,
                          "all_fields_exact":True,"valid":after["valid"]})
    # Same host/process/input, interleaved3x30. No native objects/engines.
    window=hours[-169:];cfg=Config();now=window[-1].available_ns
    old_samples=[];new_samples=[]
    for _ in range(3):
        start=time.perf_counter()
        for _ in range(30): previous.features(window,cfg,now)
        old_samples.append((time.perf_counter()-start)/30)
        start=time.perf_counter()
        for _ in range(30): features(window,cfg,now)
        new_samples.append((time.perf_counter()-start)/30)
    result={"status":"EXACT_FEATURES_PARITY_PASS","reference_source":BASE,
        "new_policy_file_sha256":hashlib.sha256((root/"runtime/coinmaster/strategy/cm2_policy.py").read_bytes()).hexdigest(),
        "native_engine_constructions":0,"parity_cases":len(cases),"cases":cases,
        "warmup_sha256":hashes,"host_system":platform.system(),"host_machine":platform.machine(),
        "timing_method":"INTERLEAVED3x30_COMPLETED169_HOUR_WINDOW_SAME_PROCESS",
        "old_median_ms":median(old_samples)*1000,"new_median_ms":median(new_samples)*1000,
        "old_samples_ms":[x*1000 for x in old_samples],"new_samples_ms":[x*1000 for x in new_samples],
        "speedup":median(old_samples)/median(new_samples),
        "per_full_17520_hour_estimated_feature_seconds_before":median(old_samples)*17520,
        "per_full_17520_hour_estimated_feature_seconds_after":median(new_samples)*17520,
        "operation_change":"mean(btc),mean(sol) computed once; inner float subtract/multiply unchanged",
        "not_changed":["variance","quantile","feature_horizons","parameters","policy_version","native_fill_money","sampling"]}
    output=root/"reports/cm2-clean-hedge-20261031/FEATURE_CSE_PARITY_TIMING.json"
    output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("status","parity_cases","native_engine_constructions","old_median_ms","new_median_ms","speedup")}))

if __name__=="__main__": main()
