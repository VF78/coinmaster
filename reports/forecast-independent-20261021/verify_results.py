"""Independent persisted-forecast verification; never imports a model or scorer."""
import argparse, csv, hashlib, json
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
            compare(metrics(q,z,y,d),result[label]['all'],label+':ALL')
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
        exports[family] = pred; reports[family] = report
    for family,pred in exports.items():
        r = read(checks[family]/'result.json')
        if 'vs_raw_control' in r: compare(blocks(pred['calibrated_q'],exports['control']['calibrated_q'],y,meta['origin'][ids],begin),r['vs_raw_control'],'CONTROL_BLOCKS:'+family)
    for spec in a.csv:
        family,path = spec.split(':',1); require(family in families,'CSV_FAMILY')
        with Path(path).open() as f:
            reader = csv.DictReader(f); key = next((k for k in ('row','row_id','ids') if k in (reader.fieldnames or [])),None)
            require(key is not None,'CSV_ROW_ID_COLUMN_REQUIRED'); csv_ids = np.array([int(row[key]) for row in reader],dtype=np.int64)
        require(len(np.unique(csv_ids)) == len(csv_ids),'CSV_DUPLICATE_IDS')
        require(np.array_equal(np.sort(csv_ids),ids) or np.array_equal(np.sort(csv_ids),allids),'CSV_ID_SET')
        reports[family].setdefault('csv',[]).append({'path':path,'sha256':digest(path),'rows':len(csv_ids)})
    payload = {'status':'INDEPENDENT_PERSISTED_RESULT_VERIFICATION_PASS','verifier_sha256':digest(__file__),'protocol_sha256':protocol_sha,'registry_sha256':digest(a.registry),'families':reports,'scope':'Metrics, tie intervals and identity only; no model execution or independent reconstruction of 1m target paths.'}
    with a.output.open('x') as f: json.dump(payload,f,indent=2,allow_nan=False)
    print(json.dumps({'status':payload['status'],'output':str(a.output)}))
if __name__ == '__main__': main()
