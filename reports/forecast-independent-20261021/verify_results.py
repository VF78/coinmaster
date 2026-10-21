"""Independent persisted-forecast verification; never imports a model or scorer."""
import argparse, csv, gzip, hashlib, json
from datetime import datetime
from pathlib import Path
import numpy as np

TAU = np.array([.2, .5, .8]); DAY = 86400000
def digest(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def read(p): return json.loads(Path(p).read_text())
def epoch(s): return int(datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()*1000)
def require(ok, message):
    if not ok: raise ValueError(message)
def close(a, b, name): require(np.allclose(a, b, rtol=1e-8, atol=1e-10), name)
def losses(q, y):
    e = y[..., None]-q
    return np.where(e >= 0, TAU*e, (TAU-1)*e)
def metrics(q, z, y, d):
    p = np.exp(z-z.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
    v = losses(q, y)
    return dict(lower_pinball=float(v[:, 0].mean()), upper_pinball=float(v[:, 1].mean()),
        direction_logloss=float(-np.log(np.maximum(p[np.arange(len(d)), d], 1e-12)).mean()),
        direction_brier=float(((p-np.eye(3)[d])**2).sum(1).mean()),
        direction_accuracy=float((p.argmax(1) == d).mean()), n=len(d))
def compare(actual, expected, name):
    for k, value in actual.items(): close(value, expected[k], name+':'+k)
def blocks(q, baseline, y, origins, start):
    delta = (losses(q, y)[:, 0]-losses(baseline, y)[:, 0]).mean((1, 2))
    block = (origins-start)//(14*DAY); unique = np.unique(block)
    sums = np.array([delta[block == b].sum() for b in unique]); counts = np.array([(block == b).sum() for b in unique])
    rng = np.random.default_rng(7); estimates = []
    for _ in range(1000):
        pick = rng.integers(0, len(unique), len(unique)); estimates.append(sums[pick].sum()/counts[pick].sum())
    return dict(mean_lower_pinball_difference=float(delta.mean()), paired14day_CI95=np.quantile(estimates, [.025, .975]).tolist(), blocks=len(unique), bootstrap_replicates=1000, seed=7)
def verify_touches(folder, dataset, manifest, meta, ids, quantiles, result):
    """Full persisted aggregation; bounded deterministic independent genuine-path sample."""
    rows = read(folder/'actionable-forecasts.json'); rowids = [r['row'] for r in rows]
    require(len(set(rowids)) == len(rowids) and np.isin(rowids, ids).all(), 'ACTIONABLE_ROW_IDS')
    require(len(rows) == result['coverage']['actionable'], 'ACTIONABLE_COUNT')
    receipt = {'scope':'Full persisted hit aggregation; first20 actionable rows per asset independently path-checked', 'assets':{}}
    for asset,symbol in enumerate(('BTCUSDT','SOLUSDT')):
        group = sorted([r for r in rows if r['asset'] == symbol], key=lambda r:r['row'])
        require(len(group) == result['actionable_touch_summary'][symbol]['n'], 'TOUCH_ASSET_COUNT')
        for j in range(3):
            for bound in ('lower','upper'):
                freq = sum(r['touch'][j][bound+'_hit'] for r in group)/len(group) if group else None
                expected = result['actionable_touch_summary'][symbol]['targets'][j][bound+'_hit_frequency']
                if freq is None: require(expected is None, 'EMPTY_TOUCH_FREQUENCY')
                else: close(freq,expected,'FULL_TOUCH_AGGREGATE')
        path = np.load(dataset/f'minutes-{symbol}.npy',mmap_mode='r',allow_pickle=False)
        for r in group[:20]:
            row = r['row']; require(int(meta['asset'][row]) == asset, 'TOUCH_ASSET_ID')
            entry_ms = int(meta['origin'][row])+60000; offset = (entry_ms-manifest['minute_start_ms'])//60000
            require((entry_ms-manifest['minute_start_ms'])%60000 == 0 and offset >= 0, 'TOUCH_PATH_OFFSET')
            v = path[offset:offset+1440]; require(len(v) == 1440, 'TOUCH_WHOLE_HORIZON')
            side = r['side']; require(side in (-1,1), 'TOUCH_SIDE'); sidx = 0 if side == 1 else 1
            e = float(v[0,0]); sigma = float(meta['sigma'][row]); sl = e*np.exp(-side*sigma)
            tp = e*np.exp(side*sigma*quantiles[np.searchsorted(ids,row),0,sidx])
            require(r['entry_ms'] == entry_ms and r['expiry_ms'] == entry_ms+DAY and r['origin_ms'] == int(meta['origin'][row]), 'TOUCH_TIMESTAMPS')
            close([r['entry'],r['entry_SL']],[e,sl],'TOUCH_ENTRY_SL'); close(r['entry_TP'],tp,'TOUCH_TP_PRICES')
            stopmask = v[:,2] <= sl if side == 1 else v[:,1] >= sl
            stop = int(np.nonzero(stopmask)[0][0]) if stopmask.any() else 1440
            gap = stop < 1440 and (v[stop,0] <= sl if side == 1 else v[stop,0] >= sl)
            reached = v[:,1,None] >= tp if side == 1 else v[:,2,None] <= tp
            for j in range(3):
                prior = np.nonzero(reached[:stop,j])[0]; certain = int(prior[0])+1 if len(prior) else None
                maybe = certain
                if stop < 1440 and not gap and reached[stop,j] and maybe is None:
                    maybe = stop+1
                    if v[stop,0] >= tp[j] if side == 1 else v[stop,0] <= tp[j]: certain = stop+1
                expected = {'lower_hit':certain is not None,'upper_hit':maybe is not None,'lower_time_minutes':certain,'upper_time_minutes':maybe}
                require(r['touch'][j] == expected, f'INDEPENDENT_TP_PATH:{row}:{j}')
        receipt['assets'][symbol] = {'all_actionable_rows':len(group),'path_verified_ids':[r['row'] for r in group[:20]]}
        del path
    require(sum(v['all_actionable_rows'] for v in receipt['assets'].values()) == len(rows), 'TOUCH_UNKNOWN_ASSET')
    return receipt
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('dataset', 'protocol', 'registry', 'source-root', 'output'): ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--check', action='append', default=[], metavar='FAMILY:DIR')
    ap.add_argument('--csv', action='append', default=[], metavar='FAMILY:FILE')
    ap.add_argument('--execute-verification', action='store_true'); a = ap.parse_args()
    require(a.execute_verification, 'EXPLICIT_ROOT_GO_REQUIRED_BEFORE_OUTCOME_ACCESS')
    checks = {k:Path(v) for k,v in (s.split(':',1) for s in a.check)}
    families = {'control','stumpy','minirocket','rdst','cnn'}
    require(set(checks) == families, 'ALL_FIVE_PERSISTED_CHECK_EXPORTS_REQUIRED')
    protocol = read(a.protocol); manifest = read(a.dataset/'manifest.json'); registry = read(a.registry)
    require(set(registry) == families, 'REGISTRY_FAMILIES'); protocol_sha = digest(a.protocol)
    require(manifest['protocol_sha256'] == protocol_sha, 'DATA_PROTOCOL_HASH')
    for name, info in manifest['artifacts'].items():
        require(digest(a.dataset/name) == info['sha256'], 'DATA_ARTIFACT_HASH:'+name)
        require((a.dataset/name).stat().st_size == info['bytes'], 'DATA_ARTIFACT_SIZE:'+name)
    meta = np.load(a.dataset/'metadata.npy', mmap_mode='r', allow_pickle=False)
    begin,end = map(epoch, protocol['check']); horizon = 60000+DAY
    require(np.array_equal(meta['expiry'],meta['origin']+horizon), 'EXPIRY_METADATA')
    allids = np.flatnonzero((meta['origin'] >= begin)&(meta['origin'] < end))
    ids = allids[meta['observed'][allids]&(meta['expiry'][allids] <= end)]
    yall = np.full((len(meta),2,2), np.nan); dall = np.full(len(meta), -1, int)
    for part in ('train','check'):
        with np.load(a.dataset/f'labels-{part}.npz', allow_pickle=False) as f:
            yall[f['ids']] = f['target']; dall[f['ids']] = f['direction']
    y,d = yall[ids],dall[ids]; require(np.isfinite(y).all() and np.isin(d,[0,1,2]).all(), 'LABEL_DOMAIN')
    fit_end = epoch(protocol['final_fit_end']); train = np.flatnonzero((meta['origin'] >= epoch(protocol['train'][0]))&(meta['origin'] < fit_end)&meta['observed']&(meta['expiry'] <= fit_end))
    prior = np.quantile(yall[train],TAU,axis=0).transpose(1,2,0)
    bq = np.broadcast_to(prior,(len(ids),2,2,3)); bp = np.bincount(dall[train],minlength=3)/len(train)
    bz = np.broadcast_to(np.log(np.maximum(bp,1e-12)),(len(ids),3)); exports = {}; reports = {}
    for family in sorted(families):
        record = registry[family]; seal_path = Path(record['path'])
        if not seal_path.is_absolute(): seal_path = a.registry.parent/seal_path
        require(digest(seal_path) == record['sha256'], 'REGISTRY_SEAL_HASH:'+family)
        seal = read(seal_path); base = seal_path.parent; folder = checks[family]; result = read(folder/'result.json')
        require(seal['family'] == family and result['family'] == family, 'FAMILY_IDENTITY')
        require(seal['status'] == 'SEALED_READY_FOR_SEPARATE_CHECK' and result['status'] == 'ONE_FROZEN_CHECK_EVALUATION_COMPLETE', 'COMPLETION_STATUS')
        require(seal['protocol_sha256'] == protocol_sha == result['protocol_sha256'], 'PROTOCOL_HASH')
        require(seal['dataset_manifest_sha256'] == digest(a.dataset/'manifest.json') == result['dataset_manifest_sha256'], 'MANIFEST_HASH')
        require(result['seal_sha256'] == digest(seal_path), 'RESULT_SEAL_HASH')
        for name,h in seal['source_sha256'].items(): require(digest(a.source_root/'runtime/coinmaster/research'/name) == h, 'SOURCE_HASH:'+name)
        for model in seal['models']: require(digest(base/model['path']) == model['sha256'], 'MODEL_HASH')
        require(digest(base/'calibrator.pkl') == seal['calibrator_sha256'], 'CALIBRATOR_HASH')
        require(digest(base/'calibration-predictions.npz') == seal['calibration_predictions_sha256'], 'CALIBRATION_EXPORT_HASH')
        require(digest(folder/'predictions.npz') == result['predictions_sha256'], 'PREDICTION_HASH')
        with np.load(folder/'predictions.npz',allow_pickle=False) as f: pred = {k:f[k] for k in f.files}
        require(np.array_equal(pred['ids'],ids), 'OBSERVED_ROW_IDS:'+family)
        with np.load(folder/'predictions-all-origins.npz',allow_pickle=False) as f:
            require(np.array_equal(f['ids'],allids), 'ALL_ORIGIN_IDS'); require(np.array_equal(f['observed'],meta['observed'][allids]), 'CENSOR_FLAGS')
            positions = np.searchsorted(allids,ids)
            for key in ('q','logits','calibrated_q','calibrated_logits'): close(f[key][positions],pred[key], 'ALL_OBSERVED_PARITY:'+key)
        report = {'n':len(ids),'censored':len(allids)-len(ids),'groups':{}}
        months = meta['origin'][ids].astype('datetime64[ms]').astype('datetime64[M]').astype(str)
        for label,qkey,zkey in [('raw','q','logits'),('calibrated','calibrated_q','calibrated_logits')]:
            q,z = pred[qkey],pred[zkey]
            require(q.shape == (len(ids),2,2,3) and z.shape == (len(ids),3), 'OUTPUT_SHAPES')
            require(np.isfinite(q).all() and np.isfinite(z).all() and (q >= 0).all() and (np.diff(q,axis=-1) >= 0).all() and (q[:,1] >= q[:,0]).all(), 'OUTPUT_DOMAIN')
            report[label] = metrics(q,z,y,d); compare(report[label],result[label]['all'],label+':ALL')
            for asset in (0,1):
                for month in ['ALL',*sorted(set(months))]:
                    mask = meta['asset'][ids] == asset
                    if month != 'ALL': mask &= months == month
                    if not mask.any(): continue
                    key = f'{asset}:{month}'; yy,qq = y[mask,...,None],q[mask]; group = result[label]['groups'][key]
                    compare(metrics(qq,z[mask],y[mask],d[mask]),group,label+':'+key)
                    close(losses(qq,y[mask]).mean(0),group['pinball_bound_side_q'],'GROUP_PINBALL')
                    close((yy >= qq).mean(0),group['exceedance_bound_side_q'],'GROUP_EXCEEDANCE')
                    close(qq.mean(0),group['mean_sigma_target_distance'],'GROUP_DISTANCE')
                    report['groups'][label+':'+key] = {'n':int(mask.sum()),'cdf_lt':(yy < qq).mean(0).tolist(),'cdf_le':(yy <= qq).mean(0).tolist(),'ties':(yy == qq).mean(0).tolist()}
        compare(metrics(bq,bz,y,d),result['prefix_prior']['all'],'PREFIX_PRIOR')
        compare(blocks(pred['calibrated_q'],bq,y,meta['origin'][ids],begin),result['vs_prefix_prior'],'PRIOR_BLOCKS')
        require(result['coverage']['fully_observed'] == len(ids) and result['coverage']['censored_origins'] == len(allids)-len(ids), 'COVERAGE_COUNTS')
        report['TP_path_verification'] = verify_touches(folder,a.dataset,manifest,meta,ids,pred['calibrated_q'],result)
        exports[family] = pred; reports[family] = report
    for family,pred in exports.items():
        r = read(checks[family]/'result.json')
        if 'vs_raw_control' in r: compare(blocks(pred['calibrated_q'],exports['control']['calibrated_q'],y,meta['origin'][ids],begin),r['vs_raw_control'],'CONTROL_BLOCKS:'+family)
    for spec in a.csv:
        family,path = spec.split(':',1); require(family in families,'CSV_FAMILY')
        with gzip.open(path,'rt') if path.endswith('.gz') else Path(path).open() as f: rows = list(csv.DictReader(f))
        csv_ids = np.array([int(r['row']) for r in rows]); require(np.array_equal(csv_ids,allids),'CSV_ALL_EXACT_IDS')
        schema = read(Path(path).parent.parent/'schema.json'); require(list(rows[0]) == schema['columns'],'CSV_SCHEMA')
        with np.load(checks[family]/'predictions-all-origins.npz',allow_pickle=False) as f: full = {k:f[k] for k in f.files}
        evaluated = {r['row'] for r in read(checks[family]/'actionable-forecasts.json')}; emitted = set(evaluated)
        emitted |= {r['row'] for r in read(checks[family]/'censored-forecasts.json') if r['actionable_forecast']}
        for i,r in enumerate(rows):
            row = int(r['row']); observed = bool(meta['observed'][row]); m = meta[row]
            require(r['asset'] == ('BTCUSDT','SOLUSDT')[int(m['asset'])],'CSV_ASSET')
            require([int(r[k]) for k in ('origin_ms','entry_ms','expiry_ms')] == [int(m['origin']),int(m['origin'])+60000,int(m['expiry'])],'CSV_EXACT_TIMES')
            close([float(r[k]) for k in ('reference','entry','sigma24')],[m['reference'],m['entry'],m['sigma']],'CSV_METADATA')
            require(int(r['fully_observed']) == observed and int(r['censored']) == (not observed),'CSV_CENSOR_FLAGS')
            require(int(r['actionable_forecast']) == (row in emitted),'CSV_ACTIONABLE_FORECAST')
            require(int(r['evaluated_actionable']) == (row in evaluated),'CSV_EVALUATED_ACTIONABLE')
            require(r['direction_truth'] == (('UP','DOWN','NEUTRAL')[dall[row]] if observed else 'UNKNOWN'),'CSV_DIRECTION_TRUTH')
            for bound,bi in [('lower',0),('upper',1)]:
                for side,si in [('long',0),('short',1)]:
                    truth = r[f'truth_{bound}_{side}']
                    if observed: close(float(truth),yall[row,bi,si],'CSV_TARGET')
                    else: require(truth == '', 'CSV_CENSORED_TARGET_MUST_BE_BLANK')
                    for prefix,qkey in [('raw','q'),('calibrated','calibrated_q')]:
                        close([float(r[f'{prefix}_{bound}_{side}_q{q}']) for q in (20,50,80)],full[qkey][i,bi,si],'CSV_QUANTILES')
            for prefix,zkey in [('raw','logits'),('calibrated','calibrated_logits')]:
                z = full[zkey][i]; prob = np.exp(z-z.max()); prob /= prob.sum()
                close([float(r[f'{prefix}_logit_{c}']) for c in ('UP','DOWN','NEUTRAL')],z,'CSV_LOGITS')
                close([float(r[f'{prefix}_probability_{c}']) for c in ('UP','DOWN','NEUTRAL')],prob,'CSV_PROBABILITIES')
        reports[family].setdefault('csv',[]).append({'path':path,'sha256':digest(path),'rows':len(csv_ids),'numeric_prediction_target_metadata_parity':'PASS','actionable_forecast':len(emitted),'evaluated_actionable':len(evaluated)})
    payload = {'status':'INDEPENDENT_PERSISTED_RESULT_VERIFICATION_PASS','verifier_sha256':digest(__file__),'protocol_sha256':protocol_sha,'registry_sha256':digest(a.registry),'comparison_note':'vs_raw_control is calibrated method versus calibrated raw-feature control','families':reports,'scope':'Metrics, tie intervals, identity, full persisted TP aggregation and explicit genuine1m TP path sample; no model execution or reconstruction of MFE labels.'}
    with a.output.open('x') as f: json.dump(payload,f,indent=2,allow_nan=False)
    print(json.dumps({'status':payload['status'],'output':str(a.output)}))
if __name__ == '__main__': main()
