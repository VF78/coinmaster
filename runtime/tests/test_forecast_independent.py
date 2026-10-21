import unittest,json,tempfile
from pathlib import Path
import numpy as np
from coinmaster.research.forecast_independent_data import MINUTE,HOUR,DAY,META,aggregate,pattern,sma20,targets,target_batch,mature,ms
class DataContractTests(unittest.TestCase):
 def test_identity_guard_rejects_stale_and_corrupt(self):
  from coinmaster.research.forecast_independent_data import verify_prepared,PROTOCOL_SHA,sha
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);f=p/'x.npy';f.write_bytes(b'abc');record={'protocol_sha256':'stale','artifacts':{'x.npy':{'sha256':sha(f),'bytes':3}}};(p/'manifest.json').write_text(json.dumps(record))
   with self.assertRaisesRegex(ValueError,'PREPARED_PROTOCOL'):verify_prepared(p)
   record['protocol_sha256']=PROTOCOL_SHA;(p/'manifest.json').write_text(json.dumps(record));f.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'PREPARED_ARTIFACT'):verify_prepared(p)

 def path(self):
  o=np.full(1440,100.);h=np.full(1440,101.);l=np.full(1440,99.);c=np.full(1440,100.);return o,h,l,c
 def test_stop_minute_bounds_and_symmetry(self):
  o,h,l,c=self.path();h[3]=120;l[3]=80
  y,d,s=targets(o,h,l,c,.1)
  self.assertEqual(s,[3,3]);self.assertEqual(d,2);self.assertAlmostEqual(y[0,0],np.log(1.01)/.1);self.assertAlmostEqual(y[1,0],np.log(1.2)/.1)
  inverse=[10000/o,10000/l,10000/h,10000/c];rev,_,_=targets(*inverse,.1);np.testing.assert_allclose(y[:,0],rev[:,1])
 def test_gap_stop_excludes_later_extreme(self):
  o,h,l,c=self.path();o[2]=80;l[2]=75;h[2]=200
  y,_,s=targets(o,h,l,c,.1);self.assertEqual(s[0],2);self.assertEqual(y[0,0],y[1,0]);self.assertLess(y[1,0],1)
 def test_zero_mfe_and_terminal_entry_basis(self):
  o=np.full(1440,100.);h=o.copy();l=o.copy();c=o.copy();y,d,_=targets(o,h,l,c,.1);np.testing.assert_array_equal(y,0);self.assertEqual(d,2)
  o[0]=110;h[0]=110;c[-1]=100;y,d,_=targets(o,h,l,c,.1);self.assertEqual(d,1)
 def test_vectorized_matches_scalar(self):
  rng=np.random.default_rng(7);o=np.exp(rng.normal(4.6,.01,3000));h=o*np.exp(rng.uniform(0,.03,3000));l=o*np.exp(-rng.uniform(0,.03,3000));c=o.copy();v=np.column_stack((o,h,l,c,np.ones(3000)))
  idx=np.array([0,1,121,1000]);sig=np.array([.01,.02,.03,.1]);y,d=target_batch(v,idx,sig)
  for i,k in enumerate(idx):
   expected,di,_=targets(o[k:k+1440],h[k:k+1440],l[k:k+1440],c[k:k+1440],sig[i]);np.testing.assert_allclose(y[i],expected,atol=1e-12);self.assertEqual(d[i],di)
 def test_actual_timestamps_and_no_upsampling(self):
  t=np.arange(120)*MINUTE;v=np.tile([100,101,99,100,1.],(120,1));a,b=aggregate(t,v,15*MINUTE);self.assertEqual(len(a),8);self.assertEqual(b[0,4],15)
  with self.assertRaises(ValueError):aggregate(a,b,MINUTE)
  t[20]+=1
  with self.assertRaises(ValueError):aggregate(t,v,15*MINUTE)
 def test_past_only_sma_and_latest_complete_bin(self):
  t=np.arange(200)*MINUTE;v=np.tile([100,101,99,100,1.],(200,1));v[:,3]=100+np.arange(200)/100;v[:,1]=103
  x=sma20(v);origin=100*MINUTE;result=pattern(t,x,origin,MINUTE,60);self.assertEqual(result[1],origin)
  v[100:]*=2;after=pattern(t,sma20(v),origin,MINUTE,60);np.testing.assert_array_equal(result[0],after[0]);self.assertIsNone(pattern(t,x,20*MINUTE,MINUTE,20))
 def test_entry_expiry_and_every_boundary_purge(self):
  end=ms('2026-04-01T00:00:00Z');m=np.zeros(3,dtype=META);m['origin']=[end-DAY-HOUR,end-DAY,end-HOUR];m['expiry']=m['origin']+MINUTE+DAY;m['observed']=True
  np.testing.assert_array_equal(mature(m,end-3*DAY,end),[True,False,False]);self.assertEqual(int(m['expiry'][0]),int(m['origin'][0])+MINUTE+DAY)
 def test_invalid_and_partial_horizon(self):
  o,h,l,c=self.path()
  with self.assertRaises(ValueError):targets(o[:-1],h,l,c,.1)
  with self.assertRaises(ValueError):targets(o,h,l,c,0)
if __name__=='__main__':unittest.main()
