import unittest
import numpy as np
from followup import ratio_at,feature_edges,bins,survival_bounds
class FollowupTests(unittest.TestCase):
 def test_ratio_excludes_future_and_exact_warmup_boundary(self):
  n=11000;v=np.ones((n,5));v[:,3]=np.exp(np.cumsum(np.sin(np.arange(n)/60)*.0001));j=10500;before=ratio_at(v,j);v[j:,3]=999999;self.assertEqual(before,ratio_at(v,j));self.assertTrue(np.isnan(ratio_at(v,168*60)));self.assertTrue(np.isfinite(ratio_at(v,168*60+1)))
 def test_terciles_fit_only_and_cutoff(self):
  m=np.zeros(9,dtype=[('label_end','i8')]);m['label_end']=np.arange(9);x=np.arange(9,dtype=float);ids=np.arange(6);e=feature_edges(x,ids,m,5);x[6:]=1e9;np.testing.assert_array_equal(e,feature_edges(x,ids,m,5))
  with self.assertRaises(ValueError):feature_edges(x,np.arange(7),m,5)
  np.testing.assert_array_equal(bins(np.array([e[0]-1,e[0],e[1]]),e),[0,1,2])
 def test_nonparametric_quantile_survival_bounds_and_ties(self):
  q=np.array([[[.1,.5,1.5],[1.,1.,1.]]]);lo,hi=survival_bounds(q);np.testing.assert_allclose(lo,[[.2,0.]]);np.testing.assert_allclose(hi,[[.5,1.]])
if __name__=='__main__':unittest.main()
