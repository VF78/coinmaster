import unittest,tempfile,json
from pathlib import Path
import numpy as np
from coinmaster.research.forecast_independent_models import project,pinball,Calibrator,Scale,render,cnn_model,torch_loss,mass_distances,softmax
class ModelContractTests(unittest.TestCase):
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
