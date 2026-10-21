"""Resume-only prefix-scaler/alignment fixture; no learned encoder/head fits."""
import unittest
import numpy as np
from coinmaster.research.forecast_cycle_data import ms
from coinmaster.research.forecast_independent_data import HOUR
from coinmaster.research.forecast_cycle_c_development import prefix_scale,rows_embedding
class ResumePrefixTests(unittest.TestCase):
 def test_prefix_scaler_future_invariance_and_two_asset_alignment(self):
  t=ms("2024-09-01")+np.arange(500)*HOUR
  x=np.random.default_rng(7).normal(size=(500,12)).astype(np.float32);end=int(t[300])
  a,fit=prefix_scale(t,x,end);changed=x.copy();changed[t>=end]*=1000;b,fit2=prefix_scale(t,changed,end)
  np.testing.assert_array_equal(a.mean_,b.mean_);np.testing.assert_array_equal(a.scale_,b.scale_)
  np.testing.assert_array_equal(a.transform(x[:300]),b.transform(changed[:300]));self.assertEqual(int(t[fit][-1]),end-HOUR)
  es,_=prefix_scale(t,x,int(t[200]));self.assertFalse(np.array_equal(a.mean_,es.mean_))
  meta=np.zeros(8,dtype=[("origin","i8")]);meta["origin"]=np.repeat(t[:4],2);z=np.arange(4*32,dtype=np.float32).reshape(4,32)
  np.testing.assert_array_equal(rows_embedding(meta,np.array([0,1,6,7]),t[:4],z),z[[0,0,3,3]])
  with self.assertRaisesRegex(ValueError,"EMBEDDING_ID_ALIGNMENT"):rows_embedding(meta,np.array([7]),t[:3],z[:3])
