"""Receipt-gated offline native comparison. No replay, cash correction or trace scan."""
import argparse, ast, csv, hashlib, json, resource
from collections import Counter, defaultdict, deque
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

OUT = Path(__file__).resolve().parent

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str, allow_nan=False) + '\n')

def rows(name, data):
    if data:
        with (OUT / name).open('w') as f:
            w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)

def sym(f):
    return 'BTC' if f.get('instrument', f.get('instrument_id', '')).startswith('BTC') else 'SOL'

def ns(text):
    return int(datetime.fromisoformat(text).timestamp()) * 1000000000

def fills(r):
    """Exact side join; weighted-average gross diagnostic, not native cash ledger."""
    native = list(csv.DictReader(open(r['execution_artifacts']['fills']['path'])))
    sides = defaultdict(deque); liq = defaultdict(lambda: dict(count=0, turnover=D(0), fees=D(0), unknown_commissions=0))
    for f in native:
        sides[ns(f['ts_last']), sym(f), D(f['filled_qty']), D(f['avg_px']).quantize(D('.000001'))].append(f['side'])
        x = liq[sym(f) + '_' + f.get('liquidity_side', 'UNKNOWN')]
        x['count'] += 1; x['turnover'] += D(f['filled_qty']) * D(f['avg_px'])
        try:
            for c in ast.literal_eval(f['commissions']):
                amount, currency = c.split(); assert currency == 'USDT'; x['fees'] += D(amount)
        except Exception:
            x['unknown_commissions'] += 1
    books = {s: dict(q=D(0), vwap=D(0), gross=D(0), fees=D(0), count=0) for s in ('BTC', 'SOL')}
    events = defaultdict(list)
    for f in r['fill_audit']:
        s = sym(f); t = int(f['fill_ns']); q = D(f['qty']); px = D(f['px'])
        key = t, s, q, px.quantize(D('.000001')); side = sides[key].popleft()
        signed = q if side == 'BUY' else -q; x = books[s]; old = x['q']
        x['fees'] += D(f['commission']); x['count'] += 1
        if old == 0 or old * signed > 0:
            x['vwap'] = (abs(old) * x['vwap'] + q * px) / (abs(old) + q)
        else:
            x['gross'] += min(abs(old), q) * (px - x['vwap']) * (1 if old > 0 else -1)
            if q > abs(old): x['vwap'] = px
        x['q'] += signed; events[t].append((s, signed))
    assert not any(sides.values()), 'Unmatched native fills'
    assert sum(x['fees'] for x in books.values()) == D(r['native_fees'])
    for x in books.values(): x['net_ex_funding'] = x['gross'] - x['fees']
    held = overlap = 0; qty = {'BTC': D(0), 'SOL': D(0)}; last = None
    for t, fs in sorted(events.items()):
        if last is not None and qty['BTC']:
            held += t - last
            if qty['SOL']: overlap += t - last
        for s, q in fs: qty[s] += q
        last = t
    return books, dict(liq), events, dict(btc_held_seconds=held / 1e9, with_sol_seconds=overlap / 1e9, fraction=overlap / held if held else None)

def economics(r):
    risk = r['minute_risk_observations']; curve = risk['curves']['all_native_close_samples']
    book, liquidity, events, overlap = fills(r)
    return dict(TOTAL=r['terminal_total'], ACTIVE=r['terminal_active'], RESERVE=r['terminal_reserve'], ROI_percent=(D(r['terminal_total']) / D(r['config'].get('initial_total_usdt', '10000')) - 1) * 100,
        marked_DD_percent=curve['top3_distinct_excursions'][0]['drawdown_peak_percent'], minimum=curve['minimum'], native_top3=curve['top3_distinct_excursions'], conditional_OHLC=risk['conditional_upper_to_later_lower_bound'],
        fees=r['native_fees'], fills=r['fills'], actual_asset_fill_diagnostic=book, native_liquidity=liquidity, native_liquidations=r['liquidation_count'], terminal_open_positions=r['terminal_open_positions'], native_rejections=r.get('native_order_rejections'), fullrows=r['streaming']['processed_rows_per_source'],
        signed_funding='UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA', funding_metadata=r.get('funding'), funding_journal=r.get('funding_journal'), cash_residual_not_funding=D(r['terminal_total']) - 10000 - sum(x['net_ex_funding'] for x in book.values()), actual_fill_held_overlap=overlap), events

def permissions(control, candidate):
    def index(r): return {int(x['q0_ns']) // 86400000000000: x for x in r['entry_sizing_audit']}
    a, b = index(control), index(candidate)
    def plans(r): return {x['episode_id']: x for x in r['split_cover_audit']['parents']}
    pa, pb = plans(control), plans(candidate); result = []
    for day in sorted(set(a) | set(b)):
        x, y = a.get(day), b.get(day); p = pa.get(x['episode_id']) if x else None; q = pb.get(y['episode_id']) if y else None
        row = dict(day=day, control_present=x is not None, candidate_present=y is not None)
        for field in ('q0_ns', 'q1_ns', 'q1_ask'):
            row[field + '_exact'] = str(x[field]) == str(y[field]) if x and y else None
        for field in ('side', 'first_vwap', 'start_ns'):
            row[field + '_exact'] = str(p.get(field)) == str(q.get(field)) if p and q else None
        row.update(control_Q=x.get('admitted_net_quantity') if x else None, candidate_Q=y.get('admitted_net_quantity') if y else None,
            candidate_planned=q.get('quantity') if q else None, candidate_filled=q.get('filled') if q else None, candidate_cancelled=q.get('cancelled') if q else None,
            own_plan_conserved=D(q['quantity']) == D(q['filled']) + D(q['cancelled']) if q else None,
            accepted_matches_plan=D(q['quantity']) == D(y['admitted_net_quantity']) if q and y else None,
            targets=json.dumps(y.get('reference_target_lots')) if y else None, omitted=json.dumps(y.get('omitted_zero_levels')) if y else None)
        result.append(row)
    summary = dict(control_count=len(a), candidate_count=len(b), missing=[x['day'] for x in result if not x['candidate_present']], extra=[x['day'] for x in result if not x['control_present']], changed_absolute_Q=sum(D(x['control_Q']) != D(x['candidate_Q']) for x in result if x['control_Q'] and x['candidate_Q']))
    for key in ('q0_ns_exact', 'q1_ns_exact', 'q1_ask_exact', 'side_exact', 'first_vwap_exact', 'start_ns_exact', 'own_plan_conserved', 'accepted_matches_plan'):
        summary[key] = sum(x[key] is True for x in result)
    summary['limit'] = 'Same causal normalized rules do not imply identical future absolute quantities under compounding. Missing/extra/late permissions are explicit.'
    return result, summary

def telemetry(r):
    audit = r.get('conditional_sol_audit', [])
    if not isinstance(audit, list): raise ValueError('Finalize collector audit schema before analysis')
    counts = Counter(x['event'] for x in audit); reasons = Counter((x['event'], str(x.get('reason'))) for x in audit)
    violations = []; physical = []; logical = []
    for x in audit:
        if all(x.get(k) not in (None, 'None') for k in ('original_desired', 'conditional_target', 'combined_target')):
            if D(x['combined_target']) != max(D(x['original_desired']), D(x['conditional_target'])): violations.append(x)
        if x['event'] in ('TRANSFER_TO_ORIGINAL', 'RELEASE_ORIGINAL'):
            logical.append(x)
            if x.get('native_fill') is not False: violations.append(x)
        if x['event'] == 'NATIVE_FILL':
            physical.append(x)
            if D(x['quantity']) != D(x['original_native_quantity']) + D(x['conditional_native_quantity']): violations.append(x)
    return dict(event_counts=dict(counts), event_reasons={str(k): v for k, v in reasons.items()}, activate_count=counts['ACTIVATE'], off_count=counts['OFF'], trim_count=counts['TRIM'], max_target_or_allocation_violations=violations,
        physical_native_quantity=sum((D(x['quantity']) for x in physical), D(0)), original_native_quantity=sum((D(x['original_native_quantity']) for x in physical), D(0)), conditional_native_quantity=sum((D(x['conditional_native_quantity']) for x in physical), D(0)),
        logical_ownership_event_count=len(logical), transfers_are_native_fills=False, Qc_cadence='Latched activation/actual BTC quantity changes; price-only drift intentionally allowed',
        limitations='Event snapshots are not complete minute coverage. Ownership transfers/releases change attribution, never venue fills/cash/PnL. No independent bucket PnL claimed.'), audit

def coverage(r, events, audit):
    """Optional one bounded canonical-mark pass; no native minute trace/uPnL scan."""
    import pyarrow.parquet as pq
    freezes = sorted((int(x['timestamp_ns']), float(x['beta'])) for x in audit if x['event'] == 'BETA_FREEZE' and x.get('beta') not in (None, 'None'))
    assert freezes, 'No frozen causal beta telemetry'
    readers = [pq.ParquetFile('/var/lib/coinmaster-native-gui/data/normalized/bybit-' + s + 'USDT-mark-1m.parquet').iter_batches(batch_size=10080, columns=['open_time_ms', 'close']) for s in ('BTC', 'SOL')]
    qty = {'BTC': D(0), 'SOL': D(0)}; c = Counter(); bins = Counter(); beta = None; i = 0; sums = 0.; lo = hi = None; matched = 0
    for bb, ss in zip(*readers):
        bt, st = bb.column(0).to_pylist(), ss.column(0).to_pylist(); assert bt == st
        for t, bp, sp in zip(bt, bb.column(1).to_pylist(), ss.column(1).to_pylist()):
            t = (int(t) + 60000) * 1000000
            for s, q in events.get(t, []): qty[s] += q; matched += 1
            while i < len(freezes) and freezes[i][0] <= t: beta = freezes[i][1]; i += 1
            if t >= int(r['minute_risk_observations']['end_exclusive_ns']): continue
            if not qty['BTC']:
                if qty['SOL']: c['orphan_seconds'] += 60
                continue
            c['BTC_held_seconds'] += 60
            if beta is None: c['unknown_beta_seconds'] += 60; continue
            ratio = float(abs(qty['SOL']) / abs(qty['BTC'])) * float(sp) / float(bp) * beta
            if qty['SOL'] * qty['BTC'] > 0: ratio = -ratio
            c['known_seconds'] += 60; bins[round(ratio, 4)] += 60; sums += ratio * 60; lo = ratio if lo is None else min(lo, ratio); hi = ratio if hi is None else max(hi, ratio)
            for key, yes in [('zero', ratio <= 1e-9), ('below45', ratio < .45), ('within45_55', .45 <= ratio <= .55), ('below50', ratio < .5), ('above100', ratio > 1)]:
                if yes: c[key + '_seconds'] += 60
    assert matched == len(r['fill_audit']); assert not any(qty.values())
    quant = {}; acc = 0
    for value, seconds in sorted(bins.items()):
        acc += seconds
        for q in (.01, .05, .25, .5, .75, .95, .99):
            if str(q) not in quant and acc >= q * c['known_seconds']: quant[str(q)] = value
    return dict(time_seconds=dict(c), mean=sums / c['known_seconds'] if c['known_seconds'] else None, minimum=lo, maximum=hi, quantiles_0001=quant, matched_actual_fill_rows=matched, formula='signed-opposite abs(SOLactual)*SOLmark*beta/(abs(BTCactual)*BTCmark)', limitations='Total actual NETTING inventory, not independent original/protection positions. One completed-minute quote counted60s; no intraminute path or hard coverage cap. Raw canonical mark close, no PnL reconstruction.')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--receipt', required=True); ap.add_argument('--coverage', action='store_true'); a = ap.parse_args()
    reuse = json.loads((OUT / 'control-reuse.json').read_text()); cr = reuse['control_artifacts'][0]
    receipt = json.loads(Path(a.receipt).read_text()); path = receipt['artifact']
    assert digest(path) == receipt['artifact_sha256'], 'Receipt result SHA mismatch'
    assert digest(cr['result']) == cr['result_sha256'], 'Control changed'
    r = json.loads(Path(path).read_text()); control = json.loads(Path(cr['result']).read_text())
    assert int(r['streaming']['processed_rows_per_source']) == 1051200, 'Only final complete run accepted'
    assert D(r['terminal_total']) == D(receipt['terminal_total'])
    assert r['terminal_open_positions'] == 0, 'Final flat receipt required'
    cm, _ = economics(control); nm, events = economics(r); pp, ps = permissions(control, r); tm, audit = telemetry(r)
    result = dict(status='ACTUAL_RECEIPT_VERIFIED', receipt=str(Path(a.receipt)), receipt_sha256=digest(a.receipt), candidate_result=path, candidate_result_sha256=digest(path), control_result=cr['result'], control_result_sha256=cr['result_sha256'], control=cm, candidate=nm, delta_TOTAL=D(nm['TOTAL']) - D(cm['TOTAL']), BTC_permissions=ps, conditional=tm,
        coverage=coverage(r, events, audit) if a.coverage else 'PENDING_OPTIONAL_LOW_MEMORY_CANONICAL_MARK_PASS', peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        limitations=['Authoritative native TOTAL/DD unchanged. Asset weighted-average fill diagnostics are not native settled asset cash. Funding UNKNOWN; residual not funding.', 'No liveDP50ROI/HL fidelity, no intraminuteDD guarantee. Transfers are logical ownership, not native fills. No protective bucket PnL ledger.'])
    rows('analysis-permissions.csv', pp); write('analysis-summary.json', result)
    print(json.dumps(dict(status=result['status'], TOTAL=nm['TOTAL'], DD=nm['marked_DD_percent'], permissions=ps, events=tm['event_counts']), default=str))

if __name__ == '__main__': main()
