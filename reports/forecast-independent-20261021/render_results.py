#!/usr/bin/env python3
"""Render completed exports only. Never import model/data code or evaluate forecasts.
Usage: render_results.py --root-go --output report.html METHOD_CHECK_DIR [...]
Optional example-path-ASSET.json: row, source_sha256, minutes (1440 rows
[time_ms,open,high,low,close]), ambiguous_minute_ms (explicit list).
These companion exports must be prepared separately after CHECK authorization.
"""
import argparse, base64, hashlib, html, json, math
from datetime import datetime, timezone
from pathlib import Path

def esc(value):
    return html.escape(str(value), quote=True)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stamp(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()

def read(path, evidence):
    value = json.loads(path.read_text())
    evidence[str(path.resolve())] = digest(path)
    return value

def chart(values, names, title, expected=None):
    width, height = 640, 230
    finite = [float(v) for row in values for v in row if v is not None]
    maximum = max(finite + ([expected] if expected is not None else []) + [.001]) * 1.15
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
             '<rect width="640" height="230" fill="white"/>']
    if expected is not None:
        y = 185 - 150 * expected / maximum
        parts.append(f'<path d="M50 {y}H625" stroke="#999" stroke-dasharray="5 4"/>')
    colors = ['#245db5', '#d28119', '#347b51']
    for i, row in enumerate(values):
        center = 65 + i * 550 / max(len(values), 1)
        for k, value in enumerate(row):
            if value is None:
                continue
            h = 150 * float(value) / maximum
            parts.append(f'<rect x="{center+k*14}" y="{185-h}" width="12" height="{h}" fill="{colors[k%3]}"/>')
        parts.append(f'<text x="{center}" y="207" font-size="10">{esc(names[i])}</text>')
    parts.append(f'<text x="10" y="18" font-size="13">{esc(title)}; scale 0–{maximum:.4g}</text></svg>')
    return ''.join(parts)

def future(path, example, evidence):
    if not path.exists():
        return '<p>Future path unavailable: companion minute OHLC export missing.</p>', str(path)
    obj = read(path, evidence)
    rows = obj.get('minutes', [])
    if obj.get('row') != example['row'] or len(rows) != 1440 or len(obj.get('source_sha256', '')) != 64:
        raise ValueError('INVALID_EXAMPLE_PATH_IDENTITY_OR_LENGTH')
    entry = example['entry_ms']
    for i, row in enumerate(rows):
        if len(row) != 5 or row[0] != entry + i * 60000 or not all(math.isfinite(v) and v > 0 for v in row[1:]):
            raise ValueError('INVALID_EXAMPLE_MINUTE')
        if not row[3] <= min(row[1], row[4]) <= max(row[1], row[4]) <= row[2]:
            raise ValueError('INVALID_EXAMPLE_OHLC')
    ambiguous = obj.get('ambiguous_minute_ms')
    if not isinstance(ambiguous, list) or any(t < entry or t >= example['expiry_ms'] for t in ambiguous):
        raise ValueError('AMBIGUITY_TIMESTAMPS_REQUIRED')
    levels = [example['entry'], example['reference'], example['entry_SL'], *example['entry_TP']]
    lo, hi = min([r[3] for r in rows] + levels), max([r[2] for r in rows] + levels)
    span = max(hi-lo, abs(hi)*1e-9)
    def y(p):
        return 255 - 220*(p-lo)/span
    def x(t):
        return 50 + 720*(t-entry)/86400000
    svg = ['<svg viewBox="0 0 990 300" role="img" aria-label="Actual 24h minute path and forecast levels">']
    for t in ambiguous:
        svg.append(f'<rect x="{x(t):.3f}" y="30" width="2" height="225" fill="#b3598d" opacity=".5"/>')
    for row in rows:
        svg.append(f'<path d="M{x(row[0]):.2f} {y(row[3]):.2f}V{y(row[2]):.2f}" stroke="#bac7d5" stroke-width=".6"/>')
    points = ' '.join(f'{x(r[0]+60000):.2f},{y(r[4]):.2f}' for r in rows)
    svg.append(f'<polyline points="{points}" fill="none" stroke="#294c73" stroke-width="1"/>')
    for label, price, color in zip(['entry','reference','SL','TP1','TP2','TP3'],levels,['#222','#777','#bd3b39','#3c8554','#3c8554','#3c8554']):
        svg.append(f'<path d="M50 {y(price):.2f}H770" stroke="{color}" stroke-dasharray="4 3"/><text x="780" y="{y(price):.2f}" font-size="12">{label} {price:.8g}</text>')
    svg.append('<text x="50" y="285" font-size="12">Entry → 24h expiry; wick range and close; pink = supplied ambiguous minute. Post-stop prices are context, not forecast hits.</text></svg>')
    return ''.join(svg), None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-go', action='store_true', help='Required explicit authorization to read completed CHECK exports')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('exports', nargs='+', type=Path)
    args = parser.parse_args()
    if not args.root_go:
        parser.error('--root-go required; no exports read')
    if args.output.exists() or args.output.with_suffix('.receipt.json').exists():
        raise ValueError('OUTPUT_EXISTS')
    evidence, missing, results = {}, [], []
    for directory in args.exports:
        r = read(directory/'result.json', evidence)
        if r.get('status') not in ('ONE_FROZEN_CHECK_EVALUATION_COMPLETE', 'INCOMPLETE_RESOURCE'):
            raise ValueError('ONLY_COMPLETED_CHECK_OR_EXPLICIT_RESOURCE_TERMINAL')
        results.append((directory, r))
    identities = {(r.get('protocol_sha256'), r.get('dataset_manifest_sha256')) for _, r in results}
    if len(identities) != 1 or any(v is None for pair in identities for v in pair):
        raise ValueError('MIXED_OR_MISSING_EXPORT_IDENTITIES')
    body = ['<!doctype html><meta charset="utf-8"><title>Independent forecast results</title><style>body{font:16px system-ui;max-width:1100px;margin:36px auto;padding:0 20px;color:#172331}table{border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #ddd}svg{max-width:100%;height:auto}img{image-rendering:pixelated;max-width:100%}section{margin:36px 0}pre{white-space:pre-wrap}</style><h1>Independent 24h pattern forecasts</h1><p>Persisted exports only. No fitting, inference, label loading or PnL calculation. CHECK is a previously studied historical period. Ambiguous intraminute ordering remains bounded.</p>',
            '<table><tr><th>Method</th><th>Lower pinball raw → calibrated</th><th>Direction logloss raw → calibrated</th><th>Actionable / observed</th></tr>']
    for _, r in results:
        if r['status'] == 'INCOMPLETE_RESOURCE':
            body.append(f'<tr><td>{esc(r["family"])}</td><td colspan="3">INCOMPLETE_RESOURCE; no predictive conclusion</td></tr>')
            continue
        a, b, c = r['raw']['all'], r['calibrated']['all'], r['coverage']
        body.append(f'<tr><td>{esc(r["family"])}</td><td>{a["lower_pinball"]:.6g} → {b["lower_pinball"]:.6g}</td><td>{a["direction_logloss"]:.6g} → {b["direction_logloss"]:.6g}</td><td>{c["actionable"]} / {c["fully_observed"]}</td></tr>')
    body.append('</table>')
    for directory, r in results:
        if r['status'] == 'INCOMPLETE_RESOURCE':
            continue
        body.append(f'<section><h2>{esc(r["family"])}</h2><pre>{esc(json.dumps({k:r[k] for k in ("coverage","vs_raw_control","vs_prefix_prior","actionable_touch_summary") if k in r},indent=2))}</pre>')
        for asset in ('BTCUSDT','SOLUSDT'):
            group = r['calibrated']['groups'].get(f'{0 if asset=="BTCUSDT" else 1}:ALL')
            if group:
                v = group['exceedance_bound_side_q']
                body.append(chart([v[b][s] for b in range(2) for s in range(2)], ['lower L','lower S','upper L','upper S'], f'{asset}: empirical MFE ≥ target, q .2/.5/.8'))
                body.append('<p>Exceedance uses ≥; zero/tied targets can prevent equality with 1−q. Endpoint calibration is not an exact latent-path guarantee.</p>')
            example = next((e for e in r['deterministic_examples'] if e['asset']==asset), None)
            if example is None:
                body.append(f'<p>{asset}: no actionable example; none substituted.</p>')
                continue
            body.append(f'<h3>{asset}, first actionable origin {esc(stamp(example["origin_ms"]))}</h3>')
            image = directory/f'example-{asset}.png'
            if image.exists():
                evidence[str(image.resolve())] = digest(image)
                body.append(f'<p>Past input chart; normalized price/volume axes.</p><img alt="Past chart input" src="data:image/png;base64,{base64.b64encode(image.read_bytes()).decode()}">')
            else:
                missing.append(str(image))
            body.append(f'<pre>{esc(json.dumps(example,indent=2))}</pre>')
            drawing, absent = future(directory/f'example-path-{asset}.json', example, evidence)
            body.append(drawing)
            if absent:
                missing.append(absent)
        body.append('</section>')
    body.append(f'<p>Missing visual exports: {esc(json.dumps(missing))}</p>')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(body))
    args.output.with_suffix('.receipt.json').write_text(json.dumps({'input_sha256':evidence,'output_sha256':digest(args.output),'missing_exports':missing,'recomputed_models_labels_or_PnL':False},indent=2))

if __name__ == '__main__':
    main()
