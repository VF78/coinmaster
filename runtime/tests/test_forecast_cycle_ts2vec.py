"""TS2Vec prefix/roundtrip fixture; random weights only, no training."""
import unittest,tempfile
from pathlib import Path
import numpy as np
from coinmaster.research.forecast_cycle_data import ASSETS,ms
from coinmaster.research.forecast_independent_data import HOUR
from coinmaster.research.forecast_cycle_ts2vec import channels,new_model,encode
class TS2VecCausalityTests(unittest.TestCase):
 def test_channels_prefix_encoder_and_saved_roundtrip(self):
  import torch
  torch.set_num_threads(1)
  t=ms("2024-06-01")+np.arange(500)*HOUR
  c=100*np.exp(.0001*np.arange(500)+.002*np.sin(np.arange(500)/7))
  panel={a:{60:(t.copy(),np.column_stack([c,c*1.001,c*.999,c,np.arange(500)+1.]))} for a in ASSETS}
  ends,x=channels(panel);g=int(ends[450])
  for a in ASSETS:
   tt,v=panel[a][60];v[tt+HOUR>g,:]*=1000
  ends2,x2=channels(panel);np.testing.assert_array_equal(x[ends<=g],x2[ends<=g])
  # No learned scaler or encoder sees future data; random-weight fixture isolates causal API.
  model=new_model(Path("reports/ai-cycle-20261021-01"));xx=np.random.default_rng(7).normal(size=(288,12)).astype(np.float32)
  before=encode(model,xx[:256]);future=xx.copy();future[256:]*=1000;after=encode(model,future)[:256]
  np.testing.assert_allclose(before,after,rtol=0,atol=1e-6)
  self.assertEqual(before.shape,(256,32))
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/"encoder.pt";model.save(p);restored=new_model(Path("reports/ai-cycle-20261021-01"));restored.load(p)
   np.testing.assert_array_equal(before,encode(restored,xx[:256]))
