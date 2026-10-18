"""One receipt-gated native artifact analyzer for cap50, dd-cov and split-atr.
No engine, counterfactual cash/PnL ledger, optimizer or automatic trace reader.
"""
import argparse, ast, csv, hashlib, json, resource
from collections import Counter, defaultdict
from decimal import Decimal as D
from pathlib import Path
OUT = Path(__file__).resolve().parent
VARIANTS = ('cap50', 'dd-cov', 'split-atr')

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()

def canonical_sha(value):
    h = hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True, separators=(',', ':')).iterencode(value): h.update(chunk.encode())
    return h.hexdigest()

def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str, allow_nan=False) + '\n')

def csvsave(path, rows):
    if rows:
        with Path(path).open('w') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def asset(row):
    return 'BTC' if row.get('instrument', row.get('instrument_id', '')).startswith('BTC') else 'SOL'

def native_execution(result):
    """Only actual fills/fees/turnover; never reconstruct PnL or account cash."""
    groups = defaultdict(lambda: dict(fill_events=0, quantity=D(0), turnover=D(0), fees=D(0)))
    for f in result['fill_audit']:
        assert f['commission_currency'] == 'USDT'
        key = asset(f) + '_' + f.get('native_liquidity_side', 'UNKNOWN')
        x = groups[key]; x['fill_events'] += 1; x['quantity'] += D(f['qty']); x['turnover'] += D(f['notional']); x['fees'] += D(f['commission'])
    assert sum(x['fees'] for x in groups.values()) == D(result['native_fees'])
    native_fills = result['execution_artifacts']['fills']; native_orders = result['execution_artifacts']['orders']
    for meta in (native_fills, native_orders):
        if meta.get('sha256'): assert sha(meta['path']) == meta['sha256']
    report_fees = D(0); report_turnover = D(0); unknown = 0; count = 0; reported_liquidity = Counter()
    for f in csv.DictReader(open(native_fills['path'])):
        count += 1; report_turnover += D(f['filled_qty']) * D(f['avg_px']); reported_liquidity[f.get('liquidity_side', 'UNKNOWN')] += 1
        try:
            for c in ast.literal_eval(f['commissions']):
                amount, currency = c.split(); assert currency == 'USDT'; report_fees += D(amount)
        except Exception: unknown += 1
    if not unknown: assert report_fees == D(result['native_fees'])
    statuses = Counter(); open_orders = 0
    for f in csv.DictReader(open(native_orders['path'])):
        statuses[f['status']] += 1
        if f['status'] not in ('FILLED', 'CANCELED', 'DENIED', 'REJECTED', 'EXPIRED'): open_orders += 1
    return dict(actual_event_asset_liquidity=dict(groups), native_fill_report_rows=count, native_fill_report_liquidity_order_counts=dict(reported_liquidity), native_fill_report_turnover=report_turnover, native_report_actual_commissions=report_fees, unknown_commission_rows=unknown, native_order_status_counts=dict(statuses), native_open_order_rows=open_orders, turnover_representation_delta=sum(x['turnover'] for x in groups.values()) - report_turnover, method='Actual callback fill liquidity/quantity/notional/commission, crosschecked against native reports. Filled-order rows and execution event counts can differ with partialGTC. CSV avg_px rendering can leave subcent turnover representation delta. No maker inference from LIMIT/IOC. No assetPnL/cash ledger.')

def metrics(result):
    obs = result['minute_risk_observations']
    assert obs['basis'] == 'NATIVE_ACCOUNT_CASH_PLUS_NATIVE_POSITION_UNREALIZED_PNL'
    curve = obs['curves']['all_native_close_samples']; bound = obs['conditional_upper_to_later_lower_bound']
    assert int(curve['samples']) == 3153599, 'Observer count differs from full frozen control; request compact provenance, never accept a truncated curve'
    assert int(bound['samples']) == 1051200 and not bound['actual_intrabar_path_proven']
    assert int(result['streaming']['processed_rows_per_source']) == 1051200
    assert int(obs['end_exclusive_ns']) == 1788220800000000000
    initial = D(result['config'].get('initial_total_usdt', '10000')); assert initial == 10000
    ex = native_execution(result)
    return dict(TOTAL=result['terminal_total'], ACTIVE=result['terminal_active'], RESERVE=result['terminal_reserve'], ROI_percent=(D(result['terminal_total']) / initial - 1) * 100, global_marked_DD_percent=curve['top3_distinct_excursions'][0]['drawdown_peak_percent'], minimum=curve['minimum'], native_top3=curve['top3_distinct_excursions'], native_observer_samples=curve['samples'], conditional_OHLC_upper_strictly_later_lower=bound, native_fees=result['native_fees'], fills=result['fills'], BTC_parents=len(result['split_cover_audit']['parents']), liquidations=result['liquidation_count'], terminal_open_positions=result['terminal_open_positions'], native_rejections=result.get('native_order_rejections'), full_rows_per_source=result['streaming']['processed_rows_per_source'], funding_metadata=result['funding'], signed_funding='UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA', execution=ex, observer_trace_read_passes=0)

def permissions(control, candidate):
    def index(r): return {int(x['q0_ns']) // 86400000000000: x for x in r['entry_sizing_audit']}
    def plans(r): return {x['episode_id']: x for x in r['split_cover_audit']['parents']}
    a, b, pa, pb = index(control), index(candidate), plans(control), plans(candidate); rows = []
    for day in sorted(set(a) | set(b)):
        x, y = a.get(day), b.get(day); p = pa.get(x['episode_id']) if x else None; q = pb.get(y['episode_id']) if y else None
        z = dict(day=day, control_present=x is not None, candidate_present=y is not None)
        for key in ('q0_ns', 'q1_ns', 'q1_ask'): z[key + '_exact'] = str(x[key]) == str(y[key]) if x and y else None
        for key in ('side', 'first_vwap', 'start_ns'): z[key + '_exact'] = str(p.get(key)) == str(q.get(key)) if p and q else None
        z.update(control_Q=x.get('admitted_net_quantity') if x else None, candidate_Q=y.get('admitted_net_quantity') if y else None, own_plan_conserved=D(q['quantity']) == D(q['filled']) + D(q['cancelled']) if q else None, accepted_matches_plan=D(q['quantity']) == D(y['admitted_net_quantity']) if q and y else None, candidate_planned=q.get('quantity') if q else None, candidate_filled=q.get('filled') if q else None, candidate_cancelled=q.get('cancelled') if q else None, step=q.get('step') if q else None, control_q0_ns=x.get('q0_ns') if x else None, candidate_q0_ns=y.get('q0_ns') if y else None, control_q1_ns=x.get('q1_ns') if x else None, candidate_q1_ns=y.get('q1_ns') if y else None, firstfill_delay_seconds=(int(q['start_ns']) - int(p['start_ns'])) / 1e9 if p and q else None)
        rows.append(z)
    summary = dict(control_count=len(a), candidate_count=len(b), missing_days=[x['day'] for x in rows if not x['candidate_present']], extra_days=[x['day'] for x in rows if not x['control_present']], changed_absolute_Q=sum(D(x['control_Q']) != D(x['candidate_Q']) for x in rows if x['control_Q'] and x['candidate_Q']))
    for key in ('q0_ns_exact', 'q1_ns_exact', 'q1_ask_exact', 'side_exact', 'first_vwap_exact', 'start_ns_exact', 'own_plan_conserved', 'accepted_matches_plan'): summary[key] = sum(x[key] is True for x in rows)
    summary['execution_delay_rows'] = [x for x in rows if x['firstfill_delay_seconds'] not in (None, 0)]
    summary['limit'] = 'Calendar/side/actualquotes/P0 distinct from absoluteQ, which can change through equity. No injected permission list or counterfactual fixedQ.'
    return rows, summary

def table_row(variant, status, m, permissions_summary=None):
    groups = m['execution']['actual_event_asset_liquidity']
    def total(suffix, key): return sum((D(v[key]) for k, v in groups.items() if k.endswith(suffix)), D(0))
    return dict(variant=variant, status=status, TOTAL=m['TOTAL'], ROI_percent=m['ROI_percent'], global_native_marked_DD_percent=m['global_marked_DD_percent'], numeric_DD_le50=D(m['global_marked_DD_percent']) <= 50, eligible_for_selection='PENDING_INTEGRITY_REVIEW' if status == 'PENDING_INTEGRITY_REVIEW' else status.startswith('ACCEPTED') and D(m['global_marked_DD_percent']) <= 50, minimum_native_equity=m['minimum']['equity'], conditional_OHLC_DD_percent=m['conditional_OHLC_upper_strictly_later_lower']['maximum']['drawdown_peak_percent'], exact_intraminute_path=False, fees=m['native_fees'], maker_turnover=total('_MAKER', 'turnover'), taker_turnover=total('_TAKER', 'turnover'), maker_fees=total('_MAKER', 'fees'), taker_fees=total('_TAKER', 'fees'), fills=m['fills'], BTC_fill_events=sum(v['fill_events'] for k, v in groups.items() if k.startswith('BTC')), SOL_fill_events=sum(v['fill_events'] for k, v in groups.items() if k.startswith('SOL')), native_order_status_counts=json.dumps(m['execution']['native_order_status_counts']), liquidations=m['liquidations'], native_open_positions=m['terminal_open_positions'], native_open_orders=m['execution']['native_open_order_rows'], funding_count=m['funding_metadata']['count'], signed_funding=m['signed_funding'], BTC_parents=m['BTC_parents'], missing_days=json.dumps(permissions_summary['missing_days']) if permissions_summary else '[]', extra_days=json.dumps(permissions_summary['extra_days']) if permissions_summary else '[]', changed_absolute_Q=permissions_summary['changed_absolute_Q'] if permissions_summary else 0, observer_trace_read_passes=0)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--variant', required=True, choices=VARIANTS); ap.add_argument('--receipt', required=True); ap.add_argument('--expected-source', required=True); a = ap.parse_args()
    prefix = 'analysis-' + a.variant; summary_path = OUT / (prefix + '-summary.json'); perm_path = OUT / (prefix + '-permissions.csv'); assert not summary_path.exists() and not perm_path.exists(), 'Immutable prior outputs exist'
    if Path('/proc/meminfo').exists():
        available = int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))) * 1024
        assert available >= 700 * 1024 * 1024, 'Defer lean analysis until MemAvailable>=700MiB; never interrupt engine'
    rp = Path(a.receipt); assert rp.name == 'risk-first-' + a.variant + '-receipt.json'; receipt = json.loads(rp.read_text()); assert receipt['source_commit'] == a.expected_source
    path = Path(receipt['artifact']); assert path.stat().st_size <= 32 * 1024 * 1024, 'Need bounded collector extraction for largeJSON, no uncontrolledload'
    assert sha(path) == receipt['artifact_sha256']; r = json.loads(path.read_text()); provenance = json.loads((OUT / 'analysis-control-provenance.json').read_text()); cp = Path(provenance['control']['result']); assert sha(cp) == provenance['control']['result_sha256']; control = json.loads(cp.read_text())
    assert all(r[k] == receipt[k] for k in ('config_hash', 'data_hash', 'policy_hash')); assert r['terminal_total'] == receipt['terminal_total']; assert r['terminal_open_positions'] == 0; assert r['data_hash'] == control['data_hash'] and r['policy_hash'] == control['policy_hash']
    audit = r['risk_first_sol_audit']; assert isinstance(audit, list); assert len(audit) == receipt['risk_first_sol_audit']['event_count']; assert canonical_sha(audit) == receipt['risk_first_sol_audit']['sha256']
    funding_files = receipt['funding_journal_files']; assert funding_files and all(sha(k) == v for k, v in funding_files.items())
    cm, nm = metrics(control), metrics(r); perms, ps = permissions(control, r); status = 'PENDING_INTEGRITY_REVIEW'
    result = dict(status=status, variant=a.variant, receipt=str(rp), receipt_sha256=sha(rp), result=str(path), result_sha256=sha(path), expected_source=a.expected_source, config_hash=r['config_hash'], data_hash=r['data_hash'], policy_hash=r['policy_hash'], metrics=nm, BTC_permissions=ps, delta_TOTAL=D(nm['TOTAL']) - D(cm['TOTAL']), audit=dict(event_count=len(audit), canonical_sha256=canonical_sha(audit), event_counts=dict(Counter(x['event'] for x in audit)), event_reason_counts={str(k): v for k, v in Counter((x['event'], x.get('reason')) for x in audit).items()}), funding_journal_files_verified=funding_files, observer_trace_read_passes=0, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, integrity_gate='Await engine actual native authority/order/cadence/variant parameter proof; nativeTOTAL alone notacceptance', limitations=['No additional PnL/cash ledger or assetuPnL reconstruction. NativeTOTAL/DD authoritative; signedfunding UNKNOWN, notzero.', 'Fullintervalglobal nativeDD<=50 required; no epochreset/partialrangepick/relaxedthreshold. Noeligible -> нетпобедителяпоусловию.', 'ConditionalOHLC separate/notexactintraminute. Native minuteclose/size1000/L2/execution/liquidation model limits retained. No live/HL/DP50ROI projection.'])
    csvsave(perm_path, perms); save(summary_path, result)
    table = [table_row('control', 'REUSED_VERIFIED_CONTROL', cm)]
    for variant in VARIANTS:
        f = OUT / ('analysis-' + variant + '-summary.json')
        if f.exists():
            x = json.loads(f.read_text()); table.append(table_row(variant, x['status'], x['metrics'], x['BTC_permissions']))
    csvsave(OUT / 'analysis-comparison.csv', table)
    params = OUT / ('risk-first-' + a.variant + '-resolved-parameters.json'); members = [summary_path, perm_path, rp]
    if params.exists(): members.append(params)
    save(OUT / (prefix + '-manifest.json'), dict(status=status, helper_historical_sha256=sha(__file__), files={str(f): sha(f) for f in members}, note='SharedcomparisonCSV/mutablehelper notvariantfrozenmembers; regeneratefinalmanifest AFTER rootintegritystatusfinal. No receipt/raw rewrite.'))
    print(json.dumps(dict(status=status, variant=a.variant, TOTAL=nm['TOTAL'], DD=nm['global_marked_DD_percent'], BTC_permissions=ps, trace_passes=0), default=str))

if __name__ == '__main__': main()
