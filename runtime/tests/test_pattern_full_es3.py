import unittest
import numpy as np
from coinmaster.research.btc_pattern_data import META,HOUR,MINUTE,DAY,ms,folds
from coinmaster.research.pattern_full_es3 import anchor_ids,median_epochs,block_permutation
class FullES3Tests(unittest.TestCase):
 def test_anchor_zero_exact_original_and_all_full_prefix(self):
  n=20928;m=np.zeros(n,dtype=META);m['origin']=ms('2024-06-01')+np.arange(n)*HOUR;m['label_end']=m['origin']+MINUTE+72*HOUR;m['valid']=m['observed']=True
  for f in folds(m):
   zero=anchor_ids(m,f['fit_cutoff'],0)
   for role in ['subfit','early_stop']:np.testing.assert_array_equal(zero[role],f[role])
   for offset in [90,45,0]:
    a=anchor_ids(m,f['fit_cutoff'],offset);self.assertEqual(m['origin'][a['subfit'][0]],ms('2024-06-01'));self.assertTrue((m['label_end'][a['subfit']]<=a['inner_cutoff']).all());self.assertTrue((m['origin'][a['early_stop']]>=a['inner_cutoff']).all());self.assertTrue((m['label_end'][a['early_stop']]<=a['anchor']).all());self.assertGreater(len(a['subfit']),90*24)
   np.testing.assert_array_equal(f['refit'],np.flatnonzero((m['origin']<f['fit_cutoff'])&(m['label_end']<=f['fit_cutoff'])))
 def test_regime_full_history_boundary_cannot_wrap_future(self):
  import tempfile
  from pathlib import Path
  from types import SimpleNamespace
  from coinmaster.research.pattern_full_es3 import regime_arrays
  with tempfile.TemporaryDirectory() as folder:
   m=np.zeros(2,dtype=META);m['entry_index']=[43201,43202];minutes=np.ones((43202,5));minutes[:,3]=np.exp(np.arange(43202)*.00001);minutes[-1,3]=999999
   np.save(Path(folder)/'minutes.npy',minutes);ret,vol=regime_arrays(SimpleNamespace(path=Path(folder),meta=m))
   self.assertTrue(np.isnan(ret[0]));self.assertTrue(np.isnan(vol[0]));self.assertAlmostEqual(ret[1],.432);self.assertAlmostEqual(vol[1],0,places=10)
 def test_median_not_loss_average_and_reuse(self):
  self.assertEqual(median_epochs([3,9,6]),6);self.assertEqual(median_epochs([7,5,7]),7)
  with self.assertRaises(ValueError):median_epochs([2,4])
 def test_shuffle_preserves_whole_temporal_blocks(self):
  p=block_permutation(512,8,702);np.testing.assert_array_equal(np.sort(p),np.arange(512));self.assertFalse(np.array_equal(p,np.arange(512)));self.assertTrue((np.diff(p.reshape(-1,8),axis=1)==1).all());self.assertTrue((p.reshape(-1,8)[:,0]%8==0).all());np.testing.assert_array_equal(p,block_permutation(512,8,702))
if __name__=='__main__':unittest.main()
