"""Task-local alignment/purge/ambiguity tests; no real model fitting."""
import unittest,pickle,os,time
import numpy as np
from coinmaster.research.forecast_cycle_data import feature_names,early_split,project_quantiles,JointFeatures,Dataset,ms,utc_boundary
from coinmaster.research.forecast_independent_data import META,HOUR,DAY,targets
class ContractTests(unittest.TestCase):
 def test_explicit_UTC_boundaries_across_host_timezones(self):
  previous=os.environ.get("TZ")
  try:
   expected=1740787200000
   for tz in ("UTC","Europe/Moscow"):
    os.environ["TZ"]=tz;time.tzset()
    self.assertEqual(ms("2025-03-01"),expected)
    self.assertEqual(ms("2025-03-01T00:00:00Z"),expected)
    self.assertEqual(utc_boundary("2025-03-01"),"2025-03-01T00:00:00Z")
    from unittest.mock import patch
    with patch("coinmaster.research.forecast_independent_data.Dataset.rows",return_value="sentinel") as legacy:
     self.assertEqual(Dataset.rows(object.__new__(Dataset),"2025-03-01","2025-06-01"),"sentinel")
     legacy.assert_called_once_with("2025-03-01T00:00:00Z","2025-06-01T00:00:00Z")
    self.test_purge()
  finally:
   if previous is None:os.environ.pop("TZ",None)
   else:os.environ["TZ"]=previous
   time.tzset()
 def test_inherited_seal_with_date_only_lock_under_both_TZ(self):
  from unittest.mock import patch
  previous=os.environ.get("TZ")
  def fixture_init(obj,*args,**kwargs):
   obj.lock={"train":["2024-09-01","2026-04-01"],"check":["2026-04-01","2026-10-21"]};obj.allow_check=False
   obj.meta=np.zeros(31*24,dtype=META);obj.meta["origin"]=ms("2026-03-01")+np.arange(31*24)*HOUR;obj.meta["expiry"]=obj.meta["origin"]+DAY+60000;obj.meta["observed"]=True
   obj.direction=np.zeros(31*24,np.int8);obj.targets=np.zeros((31*24,2,2))
  try:
   for tz in ("UTC","Europe/Moscow"):
    os.environ["TZ"]=tz;time.tzset()
    with patch("coinmaster.research.forecast_independent_data.Dataset.__init__",fixture_init):
     ds=Dataset("fixture","fixture")
    self.assertEqual(ds.lock["train"][1],"2026-04-01T00:00:00Z")
    self.assertEqual(len(ds.rows("2026-03-01","2026-04-01")),720)
    with self.assertRaisesRegex(ValueError,"CHECK_LABELS_SEALED"):ds.rows("2026-04-01","2026-04-02")
  finally:
   if previous is None:os.environ.pop("TZ",None)
   else:os.environ["TZ"]=previous
   time.tzset()
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
