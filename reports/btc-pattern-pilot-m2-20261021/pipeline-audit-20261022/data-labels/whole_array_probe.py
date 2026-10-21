"""Closing whole-array invariants, zero fits and no CHECK outcome indexing."""
import json,time
from pathlib import Path
import numpy as np
from coinmaster.research.btc_pattern_data import MINUTE,HOUR,ms,folds
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];P=ROOT/'runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared';started=time.monotonic()
manifest=json.loads((P/'manifest.json').read_text());v=np.load(P/'minutes.npy',mmap_mode='r');m=np.load(P/'metadata.npy',mmap_mode='r')
o,h,l,c,volume=v.T
checks=dict(all_minutes_finite=bool(np.isfinite(v).all()),all_prices_positive=bool((v[:,:4]>0).all()),volume_nonnegative=bool((volume>=0).all()),high_ge_open_close=bool((h>=np.maximum(o,c)).all()),low_le_open_close=bool((l<=np.minimum(o,c)).all()),high_ge_low=bool((h>=l).all()),minute_count_matches_manifest=bool(len(v)*MINUTE==manifest['minute_end']-manifest['minute_start']),manifest_start_end_UTC_minute_aligned=bool(manifest['minute_start']%MINUTE==0 and manifest['minute_end']%MINUTE==0),origin_clock_regular_unique=bool((np.diff(m['origin'])==HOUR).all()),entry_indices_match_implicit_UTC_clock=bool(np.array_equal(m['entry_time'],manifest['minute_start']+m['entry_index']*MINUTE)))
dev=np.flatnonzero(m['valid']&m['observed']&(m['origin']>=ms('2024-06-01'))&(m['origin']<ms('2026-05-01'))&(m['label_end']<=ms('2026-05-01')))
# NPZ is decompressed by NumPy, but every outcome operation below indexes DEVELOPMENT only.
with np.load(P/'labels.npz') as z:
    y=z['mfe'][dev];sig=z['signature'][dev];policy=z['policy_mfe'][dev];d=z['direction'][dev];amb=z['ambiguous'][dev]
checks.update(DEVELOPMENT_MFE_finite=bool(np.isfinite(y).all()),DEVELOPMENT_signature_finite=bool(np.isfinite(sig).all()),DEVELOPMENT_policy_MFE_finite=bool(np.isfinite(policy).all()),DEVELOPMENT_MFE_nonnegative=bool((y>=0).all()),DEVELOPMENT_MFE_lower_le_upper=bool((y[:,:,0]<=y[:,:,1]).all()),DEVELOPMENT_policy_MFE_nonnegative=bool((policy>=0).all()),DEVELOPMENT_policy_MFE_lower_le_upper=bool((policy[:,:,:,:,0]<=policy[:,:,:,:,1]).all()),DEVELOPMENT_direction_valid=bool(np.isin(d,[-1,0,1,2]).all()),DEVELOPMENT_ambiguity_matches_D=bool(np.array_equal(amb,d==-1)))
outer=np.concatenate([f['outer'] for f in folds(m)]);assert np.all(m['origin'][outer]<ms('2026-05-01'))
positions=np.searchsorted(dev,outer);assert np.array_equal(dev[positions],outer)
od=d[positions];oy=y[positions,:,0];valid=od>=0;identity=[]
for side in (0,1):identity.append(int((((oy[:,side]>=1)!=(od==side))&valid).sum()))
checks['outer_direction_MFE_identity_both_sides']=identity==[0,0]
assert all(checks.values()),checks
receipt=dict(status='PASS_WHOLE_ARRAY_INVARIANTS',fits=0,new_targets=0,new_predictions=0,CHECK_scored=False,CHECK_outcomes_indexed=False,minutes_N=len(v),OHLC_price_values_checked=int(len(v)*4),DEVELOPMENT_mature_N=len(dev),DEVELOPMENT_outer_N=len(outer),outer_ambiguous_D_N=int((~valid).sum()),outer_identity_mismatches_long_short=identity,checks=checks,chronology_scope='minutes.npy has no timestamp column: length/alignment/implicit UTC axis verified; original explicit source timestamp gap/duplicate validation is reused from prepare validate()+source receipts, not independently rediscovered from OHLCV',wall_seconds=time.monotonic()-started)
(HERE/'whole-array-results.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
