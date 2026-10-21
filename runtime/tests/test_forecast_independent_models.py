import unittest,tempfile,json
from pathlib import Path
import numpy as np
from coinmaster.research.forecast_independent_models import project,pinball,Calibrator,Scale,render,cnn_model,torch_loss,mass_distances,softmax
class ModelContractTests(unittest.TestCase):
 def test_numeric_transform_and_scaler_precede_torch_import(self):
  from unittest.mock import patch
  import builtins
  from coinmaster.research.forecast_independent_models import Learned,Budget
  events=[];real_import=builtins.__import__
  class HeadBoundary(Exception):pass
  class FakeFeatures:
   def __init__(self,*args):pass
   def fit(self,ids):
    events.append('transform_fit');self.first_random=np.random.random();self_test.assertAlmostEqual(self.first_random,.07630828937395717);return self
   def materialize(self,ids):events.append('materialize');return self
   def get(self,ids):events.append('scale_values');return np.ones((len(ids),2),np.float32)
  def intercepted(name,*args,**kwargs):
   if name=='torch':
    self_test.assertEqual(events,['transform_fit','materialize','scale_values']);raise HeadBoundary()
   return real_import(name,*args,**kwargs)
  self_test=self
  with tempfile.TemporaryDirectory() as tmp,patch('coinmaster.research.forecast_independent_models.NumericFeatures',FakeFeatures),patch('builtins.__import__',side_effect=intercepted):
   model=Learned(None,'240x60','rdst',.001,7,Path(tmp))
   with self.assertRaises(HeadBoundary):model.fit(np.array([0,1]),np.array([2]),Budget(1),epochs=1,profile_only=True)
 def test_early_best_cannot_bypass_family_minimum(self):
  from coinmaster.research.forecast_independent_models import EpochChoice
  for minimum in (5,10):
   c=EpochChoice(minimum,3)
   for epoch in range(1,minimum+4):c.consider(epoch,(epoch,epoch))
   self.assertEqual(c.best_epoch,minimum);self.assertTrue(c.stop(minimum+3))
   profile=EpochChoice(minimum,3,profile_only=True);self.assertTrue(profile.consider(1,(0.,0.)));self.assertEqual(profile.best_epoch,1)

 def test_projection_pre_and_post_calibration(self):
  q=np.arange(24,dtype=float).reshape(2,2,2,3)-12;q[:,1]-=40;p=project(q)
  self.assertTrue((p>=0).all());self.assertTrue((np.diff(p,axis=-1)>=0).all());self.assertTrue((p[:,1]>=p[:,0]).all())
  c=Calibrator();c.offset=np.ones((2,2,3))*-50;c.offset[0]=20;c.temperature=2
  after,logits=c.apply(p,np.ones((2,3)));self.assertTrue((after[:,1]>=after[:,0]).all());self.assertTrue((np.diff(after,axis=-1)>=0).all());np.testing.assert_array_equal(logits,.5)
 def test_pinball_and_joint_loss_exact(self):
  import torch
  q=np.zeros((2,2,2,3));y=np.ones((2,2,2));np.testing.assert_allclose(pinball(q,y),np.broadcast_to([.2,.5,.8],q.shape))
  raw=torch.zeros((2,15));loss=torch_loss(raw,torch.ones((2,2,2)),torch.tensor([0,2]));self.assertAlmostEqual(float(loss),.75+.2*np.log(3),places=6)
 def test_training_only_scaler(self):
  x=np.array([[1.,3.],[3.,5.],[1e8,1e8]],np.float32);s=Scale().fit(lambda ids:x[ids],np.array([0,1]));np.testing.assert_array_equal(s.mean,[2,4]);np.testing.assert_array_equal(s.std,[1,1])
 def test_temperature_and_quantile_calibration(self):
  rng=np.random.default_rng(7);q=project(rng.uniform(0,3,(40,2,2,3)));y=rng.uniform(0,2,(40,2,2));d=np.arange(40)%3;logits=rng.normal(size=(40,3));c=Calibrator().fit(q,logits,y,d);self.assertGreaterEqual(c.temperature,.25);self.assertLessEqual(c.temperature,4)
  cq,cl=c.apply(q,logits);self.assertTrue((cq[:,1]>=cq[:,0]).all());np.testing.assert_allclose(softmax(cl).sum(1),1)
 def test_mass_optimized_exact_stumpy_parity(self):
  import stumpy
  rng=np.random.default_rng(7);queries=rng.normal(size=(2,24));library=rng.normal(size=(3,24));actual=mass_distances(queries,library)
  for i,q in enumerate(queries):
   for j,v in enumerate(library):self.assertAlmostEqual(actual[i,j],float(stumpy.mass(q,v)[0]),places=6)
  const=np.ones((1,24));self.assertEqual(float(mass_distances(const,const)[0,0]),0);self.assertAlmostEqual(float(mass_distances(const,library[:1])[0,0]),np.sqrt(24))
 def test_renderer_model_shape_and_determinism(self):
  import torch
  torch.set_num_threads(1);model=cnn_model();self.assertLessEqual(sum(p.numel() for p in model.parameters()),50000)
  for w,shape in [(20,(64,60)),(60,(96,180))]:
   x=np.tile([.3,.8,.1,.5,.4,.6],(w,1));im=render(x);self.assertEqual(im.shape,shape);np.testing.assert_array_equal(im,render(x));self.assertEqual(tuple(model(torch.from_numpy(im[None,None]),torch.zeros((1,4))).shape),(1,15))
 def test_opaque_rdst_parent_roundtrip_and_missing_cache_ids(self):
  from unittest.mock import patch
  import builtins,pickle
  from types import SimpleNamespace
  from coinmaster.research.forecast_independent_models import PhasedRDST,DiskFeatures
  from coinmaster.research.forecast_independent_run import _save_model,_load_model
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);ds=SimpleNamespace(meta=np.zeros(4));np.save(root/'transformed.npy',np.arange(6,dtype=np.float32).reshape(2,3));np.save(root/'cache-ids.npy',np.array([1,3]));reader=DiskFeatures(ds,root);np.testing.assert_array_equal(reader.get([3]),[[3,4,5]])
   with self.assertRaisesRegex(ValueError,'MISSING_IDS'):reader.get([0])
   reader.clear();obj={'kind':'rdst-phased','view':'60x20','l2':.001,'seed':7,'best_epoch':10,'head_features':772,'head_blob':b'opaque-head-not-unpicklable','transformer_blob':b'opaque-transform-not-unpicklable'};real_import=builtins.__import__
   def guard(name,*args,**kwargs):
    if name.split('.')[0] in ('torch','aeon','llvmlite'):raise AssertionError('heavy import in opaque parent')
    return real_import(name,*args,**kwargs)
   with patch('builtins.__import__',side_effect=guard):
    model=PhasedRDST.restore(ds,obj,root);_save_model(model,root/'model.pkl');restored=_load_model(ds,root/'model.pkl',root);self.assertEqual(restored.artifact(),obj)
 def test_injected_features_preserve_exact_existing_torch_head(self):
  from types import SimpleNamespace
  from coinmaster.research.forecast_independent_models import Learned,DiskFeatures,Budget
  rng=np.random.default_rng(11);x=rng.uniform(size=(6,20,6)).astype(np.float32);c=rng.uniform(size=(6,4)).astype(np.float32);y=np.full((6,2,2),.5);y[:,1]=1.;ds=SimpleNamespace(meta=np.zeros(6),targets=y,direction=np.arange(6)%3,features=lambda ids,view:(x[ids].copy(),c[ids].copy()));train=np.arange(4);val=np.arange(4,6)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);np.save(root/'transformed.npy',np.column_stack((x.reshape(6,-1),c)));np.save(root/'cache-ids.npy',np.arange(6));provider=DiskFeatures(ds,root);baseline=Learned(ds,'60x20','control',.001,7,root/'control').fit(train,val,Budget(1),epochs=1,profile_only=True);phased=Learned(ds,'60x20','rdst',.001,7,root).fit(train,val,Budget(1),epochs=1,profile_only=True,feature_provider=provider)
   for a,b in zip(baseline.predict(val),phased.predict(val)):np.testing.assert_array_equal(a,b)
   self.assertEqual(phased.best_epoch,1);provider.clear()
 def test_budget_counts_completed_child_cpu(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  from coinmaster.research.forecast_independent_models import Budget
  with patch('coinmaster.research.forecast_independent_models.time.process_time',return_value=10.) as clock,patch('coinmaster.research.forecast_independent_models.resource.getrusage',return_value=SimpleNamespace(ru_utime=2.,ru_stime=3.)):
   b=Budget(1);clock.return_value=20.;self.assertEqual(b.remaining(),50.)
 def test_all_five_seals_mandatory_before_any_check(self):
  from coinmaster.research.forecast_independent_run import validate_registry
  with self.assertRaisesRegex(ValueError,'ALL_FIVE'):validate_registry(None,Path('/unused'))
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'registry.json';p.write_text('{}')
   with self.assertRaisesRegex(ValueError,'ALL_FIVE'):validate_registry(p,Path('/unused'))
 def test_atomic_check_lock_prevents_duplicate_output_paths(self):
  from coinmaster.research.forecast_independent_run import acquire_check_lock
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'seal.json';p.write_text('{}');acquire_check_lock(p,Path(tmp)/'check1')
   with self.assertRaises(FileExistsError):acquire_check_lock(p,Path(tmp)/'check2')
if __name__=='__main__':unittest.main()
