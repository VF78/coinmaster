"""Task-local alignment/purge/ambiguity tests; no real model fitting."""
import unittest,pickle
import numpy as np
from coinmaster.research.forecast_cycle_data import feature_names,early_split,project_quantiles,JointFeatures
from coinmaster.research.forecast_independent_data import META,HOUR,DAY,ms,targets
class ContractTests(unittest.TestCase):
 def test_schema(self):self.assertEqual(len(feature_names()),750);self.assertEqual(len(set(feature_names())),750)
 def test_purge(self):
  m=np.zeros(24*80,dtype=META);end=ms("2025-03-01")
  m["origin"]=end-80*DAY+np.arange(len(m))*HOUR;m["expiry"]=m["origin"]+DAY+60000
  tr,va=early_split(m,np.arange(len(m)), "2025-03-01")
  self.assertTrue(np.all(m["expiry"][tr]<=end-28*DAY));self.assertTrue(np.all(m["origin"][va]>=end-28*DAY));self.assertTrue(np.all(m["expiry"][va]<=end));self.assertFalse(set(tr)&set(va))
 def test_future_feature_invariance(self):
  j=object.__new__(JointFeatures);j.panels={}
  end=600*HOUR
  for asset in ("BTCUSDT","SOLUSDT"):
   j.panels[asset]={}
   for tf in (15,60,240):
    n=600*60//tf+80;t=np.arange(n)*tf*60000
    c=100*np.exp(.0001*np.arange(n)+.003*np.sin(np.arange(n)/7))
    v=np.column_stack((c,c*1.01,c*.99,c,np.ones(n)*10))
    j.panels[asset][tf]=(t,v)
  before=j.one(end)
  self.assertIsNotNone(before)
  for panels in j.panels.values():
   for tf,(t,v) in panels.items():v[t+tf*60000>end,:4]*=7;v[t+tf*60000>end,4]*=13
  np.testing.assert_equal(before,j.one(end))
  # Frozen deterministic fixture head: future-bar invariance extends to predictions.
  weights=np.arange(750,dtype=np.float32)/750
  restored=pickle.loads(pickle.dumps(weights))
  np.testing.assert_equal(before@weights,j.one(end)@restored)
 def test_projection(self):
  np.testing.assert_equal(project_quantiles(np.array([[2.,-1.,1.]])),[[0.,1.,2.]])
 def test_ambiguity_and_gap(self):
  o=np.ones(1440)*100;h=o.copy();l=o.copy();c=o.copy();h[0]=130;l[0]=70
  y,_,_=targets(o,h,l,c,.1);self.assertEqual(y[0,0],0);self.assertGreater(y[1,0],0)
  o[0]=80
  y,_,_=targets(o,h,l,c,.1);self.assertTrue(np.all(y>=0))
if __name__=="__main__":unittest.main()
