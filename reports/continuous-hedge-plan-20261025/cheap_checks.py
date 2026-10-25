"""Descriptive admission only. Does not import an economic engine or simulate trades."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
from fractions import Fraction

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

OUT = Path(__file__).resolve().parent
MANAGER = OUT.parents[1]
WORKSPACE = MANAGER.parents[1]
INPUT = WORKSPACE / 'runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data'
CACHE = WORKSPACE / 'runtime/var/data/normalized'
START = pd.Timestamp('2024-09-01', tz='UTC')
END = pd.Timestamp('2026-09-01', tz='UTC')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


contract = load(OUT / 'CHEAP_CHECK_CONTRACT.json')
assert contract['physical_attempt_budget'] == 0
math_checks = 0
for rho in (Fraction(1, 5), Fraction(1, 2), Fraction(7, 10), Fraction(9, 10)):
    for vol_ratio in (Fraction(1), Fraction(2), Fraction(3)):
        cov = rho * vol_ratio
        hmv = cov / vol_ratio ** 2
        hinv = 1 / cov
        def variance(h):
            return 1 - 2 * h * cov + h ** 2 * vol_ratio ** 2
        assert hmv == rho ** 2 * hinv
        assert variance(hmv) == 1 - rho ** 2
        assert variance(hinv) == 1 / rho ** 2 - 1
        assert variance(hinv) >= variance(hmv)
        math_checks += 4
freeze = load(MANAGER / 'reports/market-redesign-20261024/full-freeze.json')
inputs = {}
series = {}
for asset in ('BTC', 'SOL'):
    key = f'normalized/bybit-{asset}USDT-daily.parquet'
    path = INPUT / key
    digest = sha(path)
    assert digest == freeze['inputs'][key]['sha256'], (key, 'frozen input hash mismatch')
    d = pq.read_table(path).to_pandas()
    ts = pd.to_datetime(d.open_time_ms, unit='ms', utc=True)
    assert ts.is_monotonic_increasing and ts.is_unique
    assert (ts.diff().dropna() == pd.Timedelta(days=1)).all(), 'daily gap'
    px = d.close.astype(float)
    assert np.isfinite(px).all() and (px > 0).all()
    # The close becomes available the next day. Shift one further day at decision.
    series[asset] = pd.Series(np.log(px).diff().to_numpy(), index=ts + pd.Timedelta(days=1))
    inputs[asset] = {'path': str(path), 'sha256': digest, 'rows': len(d),
                     'first_open_utc': str(ts.iloc[0]), 'last_open_utc': str(ts.iloc[-1]),
                     'missing_days': 0, 'duplicate_timestamps': 0}

r = pd.DataFrame(series)
days = pd.date_range(START, END, inclusive='left', freq='D')
assert len(days) == 730
rows, summaries = [], []
for w in contract['windows_days']:
    cov = r.BTC.rolling(w, min_periods=w).cov(r.SOL).shift(1)
    vb = r.BTC.rolling(w, min_periods=w).var().shift(1)
    va = r.SOL.rolling(w, min_periods=w).var().shift(1)
    f = pd.DataFrame({'cov': cov, 'vb': vb, 'va': va}).reindex(days)
    assert f.notna().all().all() and (f[['vb', 'va']] > 0).all().all()
    rho = f['cov'] / np.sqrt(f.vb * f.va)
    beta = f['cov'] / f.vb
    mv = f['cov'] / f.va
    inv = 1 / beta.where(beta > 0)
    vmv = (f.vb - 2 * mv * f['cov'] + mv ** 2 * f.va) / f.vb
    vinv = (f.vb - 2 * inv * f['cov'] + inv ** 2 * f.va) / f.vb
    assert np.allclose(mv, rho ** 2 * inv, equal_nan=True)
    assert np.allclose(vmv, 1 - rho ** 2)
    assert np.allclose(vinv, 1 / rho ** 2 - 1)
    for t in days:
        ready = t - pd.Timedelta(days=1)
        assert ready < t
        rows.append({'window_days': w, 'decision_utc': t.isoformat(),
                     'latest_close_ready_utc': ready.isoformat(), 'rho': rho[t],
                     'sigma_SOL_over_BTC': np.sqrt(f.va[t] / f.vb[t]),
                     'h_minvar_unclipped': mv[t], 'h_inverse_beta_unclipped': inv[t],
                     'Vminvar_over_Vbtc': vmv[t], 'Vinverse_over_Vbtc': vinv[t]})
    def quant(x):
        return {str(q): float(x.quantile(q)) for q in (0, .1, .5, .9, 1)}
    summaries.append({'window_days': w, 'decision_days': len(f), 'causal_complete_days': int(f.notna().all(axis=1).sum()),
                      'rho': quant(rho), 'sigma_SOL_over_BTC': quant(np.sqrt(f.va / f.vb)),
                      'h_minvar_unclipped': quant(mv), 'h_inverse_beta_unclipped': quant(inv),
                      'inverse_beta_variance_exceeds_unhedged_days': int((vinv > 1).sum()),
                      'minvar_theoretical_variance_reduction_median_fraction': float((1 - vmv).median()),
                      'not_economic_result': True})
pd.DataFrame(rows).to_csv(OUT / 'causal-coefficients.csv', index=False)

# Existing official normalized HL files explicitly contain nontrading proxy history.
hl = {}
for asset in ('BTC', 'SOL'):
    path = CACHE / f'hyperliquid-{asset}-daily.parquet'
    d = pq.read_table(path, columns=['open_time_ms', 'price_classification']).to_pandas()
    hl[asset] = {'path': str(path), 'sha256': sha(path),
                 'classification_counts': {str(k): int(v) for k,v in d.price_classification.value_counts().items()},
                 'proxy_is_not_native_execution_history': True}

# Targeted filename inventory only; do not infer global absence on Mac/VPS.
names = sorted(p.name for p in CACHE.iterdir() if p.is_file())
eth = [n for n in names if 'ETH' in n.upper()]
hour = [n for n in names if 'SOL' in n.upper() and any(x in n.lower() for x in ('1h', '4h', 'h1', 'h4', 'hour'))]

pres = load(MANAGER / 'reports/manager-handoff-20261024/evidence/S0-legacy-preservation.json')
sp = MANAGER / pres['durable_file']
payload = gzip.decompress(sp.read_bytes())
assert sha(sp) == pres['compressed_sha256']
assert hashlib.sha256(payload).hexdigest() == pres['uncompressed_sha256']
s0 = json.loads(payload)
assert str(s0['terminal_total']) == pres['TOTAL']
assert s0['config_hash'] == pres['config_sha256']
btc_path = MANAGER / 'reports/new-system-plan-20261024/inputs/old_S0_BTC_only_native_receipt.json'
btc = load(btc_path)
comparison_path = MANAGER / 'reports/broad-hedge-discovery-20261024/lot-corridor-comparison.json'
comparison = load(comparison_path)
assert comparison['variants']['OFF']['terminal_total'] == '19544.07357286'

baseline = {
    'scope': 'Fresh hash verification of archived receipts, NOT fresh baseline replay',
    'legacy_S0': {'source_anchor': '75ffc9c69e9d79c4da4cd0614634a3eeba48d716',
                  'TOTAL': pres['TOTAL'], 'report': str(sp), 'report_gzip_sha256': sha(sp),
                  'report_payload_sha256': hashlib.sha256(payload).hexdigest(),
                  'config_sha256': s0['config_hash'], 'data_sha256': s0['data_hash'],
                  'policy_sha256': s0['policy_hash'], 'verification': 'ARCHIVED_PAYLOAD_INTEGRITY_PASS'},
    'legacy_BTC_only': {'source_commit': btc['source_commit'], 'TOTAL': btc['terminal_total'],
                        'receipt_path': str(btc_path), 'receipt_sha256': sha(btc_path),
                        'native_report_sha256_as_archived': btc['artifact_sha256'],
                        'verification': 'ARCHIVED_RECEIPT_ONLY_NOT_FRESH_NATIVE_RAW_REPLAY'},
    'corrected_R3_prefix': {'source_commit': comparison['source_commit'],
                             'comparison_path': str(comparison_path), 'comparison_sha256': sha(comparison_path),
                             'TOTAL_OFF': comparison['variants']['OFF']['terminal_total'],
                             'verification': 'REUSE_COMPLETED_NATIVE_PARITY_FROM_CLOSED_PHYSICAL5_NOT_NEW_REPLAY'},
    'BTC_TP_constraint': 'Legacy zero TP controls are attribution only. Real3TP R3 is separately pinned; never call its TP unchanged legacy winner.',
    'fresh_baseline_engines_created': 0,
    'inputs_used_here': inputs,
    'engine_authority': 'Only native Nautilus1.231.0 for future economics; none instantiated here',
    'benchmark': contract['benchmark'], 'seed_USDT': '10000', 'reserve': '0',
    'fee_policy': 'Existing frozen Bybit BASE maker0.020%/taker0.055%; future HL separate qualification only',
}
(OUT / 'BASELINE_MANIFEST.json').write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + '\n')
result = {'task': contract['task'], 'contract_sha256': sha(OUT / 'CHEAP_CHECK_CONTRACT.json'),
          'script_sha256': sha(Path(__file__)), 'python': sys.version,
          'status': 'DESCRIPTIVE_ADMISSION_CHECKS_COMPLETE_NO_ECONOMIC_WINNER',
          'exact_rational_math_assertions_PASS': math_checks,
          'causal_coefficient_rows': len(rows), 'window_summaries': summaries,
          'hyperliquid_daily_classifications': hl,
          'targeted_normalized_inventory': {'directory': str(CACHE), 'ETH_files': eth,
                                             'SOL_H1_H4_files': hour, 'global_absence_claimed': False},
          'existing_failures': ['System python lacks pyarrow; corrected to existing runtime/.venv/bin/python without installation'],
          'not_proven': ['out-of-sample variance reduction', 'tail/DD50 guarantee', 'net edge after turnover/funding',
                         'restoration of 70/90 profit', 'ETH versus SOL', 'historical real L2 fills'],
          'native_instances': 0, 'economic_ROI_simulations': 0, 'downloads': 0,
          'product_changes': 0, 'physical_attempts': 0}
(OUT / 'cheap-checks-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
print(json.dumps({'status': result['status'], 'coefficient_rows': len(rows),
                  'inverse_variance_worse_days': {str(s['window_days']):s['inverse_beta_variance_exceeds_unhedged_days'] for s in summaries},
                  'native_instances': 0}, ensure_ascii=False))
