import unittest
from types import SimpleNamespace
import numpy as np
import torch
from coinmaster.research.btc_pattern_data import META
from coinmaster.research import btc_pattern_models as models
from coinmaster.research.pattern_q_prior_init import fit_prior,initialized_factory
class PriorInitTests(unittest.TestCase):
 def test_prior_raw_Q_all_inputs_and_rng_other_heads_unchanged(self):
  torch.set_num_threads(4);torch.manual_seed(7);baseline=models.CNN();after_original=torch.rand(8);prior=np.array([[.2,.7,1.2],[.4,.8,1.2]],dtype='float32')
  torch.manual_seed(7)
  with initialized_factory(prior):candidate=models.CNN()
  after_candidate=torch.rand(8);torch.testing.assert_close(after_original,after_candidate,rtol=0,atol=0)
  for name,value in baseline.state_dict().items():
   if not name.startswith('heads.quantiles.'):torch.testing.assert_close(value,candidate.state_dict()[name],rtol=0,atol=0)
  self.assertEqual(float(candidate.heads.quantiles.weight.abs().sum()),0)
  with torch.no_grad():z,d,q=candidate(torch.randn(3,3,224,224),torch.randn(3,12))
  torch.testing.assert_close(q,torch.from_numpy(prior)[None].expand(3,-1,-1),rtol=0,atol=0)
 def test_prior_fit_ids_cutoff_and_fresh_refit(self):
  meta=np.zeros(10,dtype=META);meta['label_end']=np.arange(10)+10;y=np.arange(20,dtype='float32').reshape(10,2);data=SimpleNamespace(meta=meta,y=y);ids=np.arange(4)
  prior=fit_prior(data,ids,13,ids);np.testing.assert_array_equal(prior,np.quantile(y[:4],[.2,.5,.8],axis=0).T.astype('float32'))
  data.y[4:]=1e8;np.testing.assert_array_equal(prior,fit_prior(data,ids,13,ids));self.assertFalse(np.array_equal(prior,fit_prior(data,np.arange(8),17,np.arange(8))))
  with self.assertRaises(ValueError):fit_prior(data,np.arange(5),13,np.arange(5))
  with self.assertRaises(ValueError):fit_prior(data,np.arange(3),13,ids)
 def test_restore_factory_even_on_error(self):
  original=models.CNN
  with self.assertRaises(RuntimeError):
   with initialized_factory(np.ones((2,3),'float32')):
    self.assertIsNot(models.CNN,original);raise RuntimeError('intentional')
  self.assertIs(models.CNN,original)
if __name__=='__main__':unittest.main()
