"""Read-only CM2 causal feature reconstruction and native inventory diagnostics."""
from dataclasses import asdict
from collections import Counter, deque
from decimal import Decimal as D
import argparse, bisect, gzip, hashlib, importlib.metadata, json, platform, sys
from pathlib import Path
from coinmaster.strategy.cm2_policy import Config, PairedHourBuilder, features, HOUR_NS
from coinmaster.research.cm2_runner import CM2RunConfig

START_MS, END_MS = 1725148800000, 1788220800000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def host_math():
    libs = {}
    maps = Path('/proc/self/maps')
    if maps.exists():
        for line in maps.read_text().splitlines():
            if '/libm.so' in line:
                path = line.split()[-1]; libs[path] = sha(path)
    return dict(python=platform.python_version(), executable=sys.executable,
                executable_sha256=sha(sys.executable), platform=platform.platform(),
                libc=platform.libc_ver(), libm_sha256=libs)


def feature_rows(seed, minutes, instruments):
    """Same source-rounded bars/barrier and existing feature function; no strategy."""
    hours = deque(seed, maxlen=170); cfg = Config(); barrier = PairedHourBuilder()
    yield asdict(features(tuple(hours), cfg, hours[-1].available_ns))
    for minute in minutes:
        closed = (minute.open_time_ms + 60000)*1_000_000
        for symbol, inst, row in zip(('BTC','SOL'), instruments, (minute.btc_execution, minute.sol_execution)):
            rounded = [float(inst.make_price(row[k])) for k in ('open','high','low','close')]
            hour = barrier.add(symbol, closed, closed, *rounded)
            if hour is not None:
                hours.append(hour)
                yield asdict(features(tuple(hours), cfg, hour.available_ns))


class FeatureTape:
    def __init__(self, rows):
        self.rows = rows; self.times = [int(r['available_ns']) for r in rows]
        if not rows or any(b <= a for a,b in zip(self.times,self.times[1:])):
            raise ValueError('FEATURE_TIME_ORDER')
    def asof(self, ns, strict=False):
        index = (bisect.bisect_left(self.times,ns) if strict else bisect.bisect_right(self.times,ns))-1
        if index < 0: return None
        row = self.rows[index]
        return row if ns-int(row['closed_ns']) <= HOUR_NS else None


def build_tape(args):
    from coinmaster.research.native_baseline import iter_minute_bundles
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    import coinmaster.strategy.cm2_policy as policy
    import coinmaster.research.cm2_runner as runner
    import coinmaster.research.native_baseline as baseline
    import coinmaster.research.current_hl_profile as profile_module
    import nautilus_trader.model.instruments.base as native_instrument
    distribution=importlib.metadata.distribution('nautilus_trader')
    if distribution.version!='1.231.0':raise ValueError('PINNED_NATIVE_1231_REQUIRED')
    engine_binary=next(Path(distribution.locate_file(f)) for f in distribution.files
        if str(f).startswith('nautilus_trader/backtest/engine.') and str(f).endswith('.so'))
    if not START_MS < args.end_ms <= END_MS or args.end_ms % 3600000:
        raise ValueError('WHOLE_HOUR_CANONICAL_PREFIX_REQUIRED')
    data, warm, profile = args.data_root, args.warmup_root, args.profile_root
    used = [data/'bybit-1m/manifest.json']
    used += [data/f'normalized/bybit-{s}-{k}.parquet' for s in ('BTCUSDT','SOLUSDT')
             for k in ('execution-1m','mark-1m','daily','funding')]
    used += [warm/f'data-warmup-{s}-1h.csv' for s in ('BTCUSDT','SOLUSDT')]
    used += [profile/n for n in ('native-btc-sol-raw.json','hyperliquid-meta-BTC-SOL-20261029.json','execution-profile-inputs.json')]
    code = {'cm2_policy':policy.__file__, 'cm2_runner':runner.__file__,
            'native_baseline':baseline.__file__, 'current_hl_profile':profile_module.__file__,
            'native_instrument':native_instrument.__file__, 'native_engine_binary':str(engine_binary), 'diagnostic':__file__}
    used += [Path(p) for p in code.values()]
    pins = json.loads(args.pins.read_text())
    actual = {str(p.resolve()):sha(p) for p in used}
    if any(pins.get(p) != digest for p,digest in actual.items()):
        raise ValueError('REQUIRED_DATA_PROFILE_CODE_PIN_MISSING_OR_MISMATCH')
    instruments = load_current_hl_diagnostic(profile).instruments
    seed = CM2RunConfig(Config(),warm).seed(START_MS*1_000_000)
    rows = list(feature_rows(seed,iter_minute_bundles(data,START_MS,args.end_ms,1440,
                    require_exact_source_rows=args.end_ms==END_MS),instruments))
    FeatureTape(rows)
    result = dict(schema='cm2-causal-feature-tape-v1', rows=rows, input_sha256=actual,
        code_sha256={name:sha(path) for name,path in code.items()}, pins_sha256=sha(args.pins), math_host=host_math(),
        start_ms=START_MS,end_ms=args.end_ms, config=asdict(Config()),
        basis='EXISTING_SEED169_NATIVE_MAKE_PRICE_PAIRED60_EXISTING_FEATURES',
        availability='bar.ts_event=bar.ts_init=M1open+60s; paired max receipt; <= risk clock OR < decision clock',
        equal_clock_strategy_visibility='UNKNOWN_WITHOUT_NATIVE_CALLBACK_FEATURE_RECEIPTS',
        invariant_scope='beta/guard/rho/residual/b/u/ATR invariant across trend_hours24..168; channel T72 ONLY',
        native_engine_constructions=0)
    write_json(args.output,result)


def inventory(row):
    totals = {'BTC':D(0),'SOL':D(0)}; marks = {}; ids = {'BTC':[],'SOL':[]}
    for p in row['positions']:
        symbol = str(p['instrument_id']).split('-')[0]
        if symbol not in totals or p['side'] not in ('LONG','SHORT'):
            raise ValueError('NATIVE_POSITION_SCHEMA_OR_FOREIGN_SYMBOL')
        if ids[symbol]:raise ValueError('MULTIPLE_NATIVE_POSITIONS_PER_SYMBOL_UNSUPPORTED')
        qty, mark = D(p['quantity']), D(p['native_price'])
        if qty < 0 or mark <= 0 or not qty.is_finite() or not mark.is_finite():
            raise ValueError('INVALID_NATIVE_POSITION')
        if symbol in marks and marks[symbol] != mark: raise ValueError('NATIVE_MARK_DISAGREEMENT')
        totals[symbol] += qty*(1 if p['side']=='LONG' else -1)
        marks[symbol] = mark; ids[symbol].append(p['position_id'])
    return totals, marks, ids


def model_metrics(qty,marks,feature,exit_fee):
    if not feature or not feature['valid'] or not feature['hedge_valid']:
        return {'status':'UNKNOWN_FEATURE_INVALID_OR_STALE'}
    btc, sol = qty['BTC']*marks['BTC'], qty['SOL']*marks['SOL']
    beta, guard, common, residual = [D(str(feature[k])) for k in ('beta','beta_guard','common_loss','residual_loss')]
    gross = abs(btc)*common
    joint = abs(btc+beta*sol)*common+abs(sol)*residual
    fee = abs(sol)*exit_fee*2
    opposite = btc*sol < 0
    return dict(status='MODEL_IMPLIED_ONLY', feature_available_ns=feature['available_ns'],
        notional_ratio=str(abs(sol/btc)),beta_factor_ratio=str(abs(beta*sol/btc)),
        guard_factor_ratio=str(abs(guard*sol/btc)),
        guard_nonflip=opposite and guard>0 and abs(guard*sol)<=abs(btc),
        btc_only_downside_model=str(gross),joint_downside_model=str(joint),
        roundtrip_hedge_fee_model=str(fee),net_downside_reduction_model=str(gross-joint-fee),
        model_hedge_hurdle=bool(opposite and gross-joint>fee))


def audit_rows(rows,tape,exit_fee,emit):
    counts=Counter(); problems=set(); fills=set(); episodes=[]; orphans=[]
    last_seq=0; last_ns=None; last_direction=None; episode=None; orphan=None; last_feature=None
    intervals=[]; interval=None; prior_class=None
    for row in rows:
        required={'sequence','event_ns','receipt_ns','kind','epoch','state_epoch','positions'}
        if not required.issubset(row):problems.add('NATIVE_TRACE_FIELDS_MISSING');continue
        seq=int(row['sequence']); ns=int(row['event_ns']); receipt=int(row['receipt_ns'])
        if seq != last_seq+1: problems.add('TRACE_SEQUENCE_NOT_CONTIGUOUS')
        last_seq=seq
        if row['kind']=='SETTLED_PRE_NEXT_SOURCE_WATERMARK': continue
        if receipt<ns or row.get('state_epoch')!=row.get('epoch'):
            problems.add('NATIVE_EVENT_OR_STATE_EPOCH_UNCERTAIN');continue
        if row.get('mark_available_ns') is not None and int(row['mark_available_ns'])>ns:
            problems.add('NATIVE_MARK_FROM_FUTURE');continue
        if last_ns is not None and ns<last_ns:
            problems.add('CURRENT_STATE_EVENT_CLOCK_REGRESSION');continue
        try: qty,marks,ids=inventory(row)
        except (ValueError,KeyError): problems.add('NATIVE_POSITION_FIELDS_UNKNOWN');continue
        counts['native_snapshot_rows']+=1
        direction=1 if qty['BTC']>0 else -1 if qty['BTC']<0 else 0
        if direction!=last_direction:
            if episode is not None: episode['end_sequence']=seq;episode['end_event_ns']=str(ns)
            episode=None
            if direction:
                episode=dict(observed_episode_id=f'BTC_OBSERVED_{len(episodes):05d}',start_sequence=seq,
                    start_event_ns=str(ns),direction=direction,left_censored=last_direction is None,
                    business_parent_GUID='UNKNOWN',native_position_ids=ids['BTC'])
                episodes.append(episode)
            last_direction=direction
        orphan_now=qty['SOL']!=0 and qty['BTC']==0
        orphan_changed=orphan_now != (orphan is not None)
        if orphan_now and orphan is None:
            orphan=dict(start_sequence=seq,start_event_ns=str(ns),left_censored=counts['native_snapshot_rows']==1)
            orphans.append(orphan)
        elif not orphan_now and orphan is not None:
            orphan.update(end_sequence=seq,end_event_ns=str(ns),native_event_clock_duration_ns=str(ns-int(orphan['start_event_ns'])))
            orphan=None
        both=qty['BTC']!=0 and qty['SOL']!=0
        if both:
            counts['coexposure_snapshot_rows']+=1
            counts['opposite_sign_rows' if qty['BTC']*qty['SOL']<0 else 'same_sign_rows']+=1
        risk=tape.asof(ns); decision=tape.asof(ns,strict=True)
        metric=model_metrics(qty,marks,risk,exit_fee) if both else {'status':'NO_COEXPOSURE'}
        strict=model_metrics(qty,marks,decision,exit_fee) if both else {'status':'NO_COEXPOSURE'}
        if both and metric.get('status')!='MODEL_IMPLIED_ONLY': counts['coexposure_feature_unknown_rows']+=1
        if both and metric.get('guard_nonflip') is False: counts['model_guard_flip_rows']+=1
        classification=(both, bool(both and qty['BTC']*qty['SOL']<0),metric.get('guard_nonflip'))
        if classification!=prior_class:
            if interval is not None:interval.update(end_sequence=seq,end_event_ns=str(ns))
            interval=dict(start_sequence=seq,start_event_ns=str(ns),coexposure=both,
                opposite_sign=classification[1],model_guard_nonflip=classification[2])
            intervals.append(interval);prior_class=classification
        if row['kind']=='POST_FILL_COMMITTED_NATIVE':
            if not row.get('native_id'):problems.add('FILL_ID_MISSING')
            elif row['native_id'] in fills:problems.add('DUPLICATE_POST_FILL_ID')
            else:fills.add(row['native_id'])
        feature_time=risk['available_ns'] if risk else None
        if row['kind']=='POST_FILL_COMMITTED_NATIVE' or feature_time!=last_feature or orphan_changed:
            emit(dict(sequence=seq,event_ns=ns,receipt_ns=receipt,kind=row['kind'],
                btc_qty=str(qty['BTC']),sol_qty=str(qty['SOL']),native_position_ids=ids,
                observed_btc_episode=episode['observed_episode_id'] if episode else None,
                orphan_native_snapshot=orphan_now,risk_asof_le=metric,decision_asof_lt=strict))
        last_feature=feature_time;last_ns=ns
    if interval is not None:interval['right_censored']=True
    if orphan is not None:orphan['right_censored']=True
    if episode is not None:episode['right_censored']=True
    if orphan is not None or any(x.get('left_censored') for x in orphans):problems.add('ORPHAN_INTERVAL_CENSORED')
    if not counts['native_snapshot_rows']:problems.add('NO_NATIVE_SNAPSHOTS')
    return dict(counts=dict(counts),native_post_fill_unique_ids=len(fills),native_inventory_episodes=episodes,
        orphan_native_event_intervals=orphans,observed_exposure_and_model_guard_intervals=intervals,
        trace_sequence_count=last_seq,unknown=sorted(problems))


def audit(args):
    for name in ('tape','trace','report'):
        if sha(getattr(args,name))!=getattr(args,name+'_sha256'):raise ValueError('AUDIT_INPUT_PIN_MISMATCH:'+name)
    frozen=json.loads(args.tape.read_text())
    if frozen.get('schema')!='cm2-causal-feature-tape-v1':raise ValueError('FEATURE_TAPE_SCHEMA')
    tape=FeatureTape(frozen['rows'])
    report=json.loads(args.report.read_text());observer=report.get('coherent_native_observer',{})
    output=args.output; output.mkdir(parents=True,exist_ok=False)
    with (output/'diagnostic-events.jsonl').open('x') as exported, gzip.open(args.trace,'rt') as stream:
        result=audit_rows((json.loads(line) for line in stream),tape,D('.000432'),
            lambda row:exported.write(json.dumps(row,separators=(',',':'))+'\n'))
    if observer.get('status')!='PASS':result['unknown'].append('UPSTREAM_NATIVE_OBSERVER_NOT_PASS')
    if observer.get('sequence_count')!=result['trace_sequence_count']:result['unknown'].append('TRACE_REPORT_SEQUENCE_MISMATCH')
    if observer.get('native_unique_fills')!=result['native_post_fill_unique_ids']:result['unknown'].append('TRACE_REPORT_FILL_COUNT_MISMATCH')
    if report.get('source_hashes',{}).get('strategy/cm2_policy.py')!=frozen['code_sha256']['cm2_policy']:
        result['unknown'].append('REPORT_TAPE_POLICY_SOURCE_MISMATCH')
    result.update(status='PARTIAL_DIAGNOSTICS_BUSINESS_STRUCTURE_UNKNOWN',
        trace_sha256=sha(args.trace),native_report_sha256=sha(args.report),feature_tape_sha256=sha(args.tape),
        diagnostic_source_sha256=sha(__file__),math_host=host_math(),
        invariant_metrics='beta/guard/rho/residual/b/u/ATR only; T72 channel never used for admission',
        business_parent_GUID='UNKNOWN_NOT_EXPORTED',meaningful_hedge_threshold='UNKNOWN_NOT_SPECIFIED',
        native_harvest_profit_fee_hurdle='UNKNOWN_VWAP_ALLOCATED_FEES_PARENT_FUNDING_NOT_EXPORTED',
        actual_hedge_benefit='UNPROVEN_NO_COUNTERFACTUAL_OR_PNL_RECONSTRUCTION',
        limitations=['Inventory episodes are observed contiguous signed BTC inventory, not business parent lineage.',
          'Counts are native snapshot/event counts, not duration-weighted returns or independent trades.',
          'Orphan endpoints use actual native event clock and sequence; no adapter +60s substitution.',
          'Feature equality at risk time is reconstructed availability, not proven decision callback visibility.',
          'Strict prior feature is conservative; it is not a claim that strategy used that older feature.',
          'Model bounds and hedge roundtrip fee hurdle are assumptions, never actual PnL or harvest permission.',
          'Missing/malformed snapshots, incomplete sequence or upstream UNKNOWN block strong qualification.'])
    write_json(output/'SUMMARY.json',result)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    build=sub.add_parser('build-tape')
    for name in ('data-root','warmup-root','profile-root','pins','output'):build.add_argument('--'+name,type=Path,required=True)
    build.add_argument('--end-ms',type=int,default=END_MS)
    check=sub.add_parser('audit')
    for name in ('tape','trace','report','output'):check.add_argument('--'+name,type=Path,required=True)
    for name in ('tape','trace','report'):check.add_argument('--'+name+'-sha256',required=True)
    args=p.parse_args();build_tape(args) if args.command=='build-tape' else audit(args)


if __name__=='__main__':main()
