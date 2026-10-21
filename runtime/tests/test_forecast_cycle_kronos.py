"""Kronos adapter sample-axis and as-of causality fixtures; no model fitting."""
import unittest
import numpy as np
from coinmaster.research.forecast_cycle_data import ASSETS,ms
from coinmaster.research.forecast_independent_data import HOUR
from coinmaster.research.forecast_cycle_kronos import sample_paths,asof,frame_input,sample_seed
class KronosContractTests(unittest.TestCase):
 def panel(self):
  t=ms("2024-07-01")+np.arange(600)*HOUR
  c=100*np.exp(.0002*np.arange(600)+.003*np.sin(np.arange(600)/5))
  v=np.column_stack([c,c*1.001,c*.999,c,np.ones(600)])
  return {a:{60:(t.copy(),v.copy())} for a in ASSETS}
 def test_sample_axis_and_future_invariance(self):
  import pandas as pd
  class Fixture:
   def __init__(self):self.calls=[]
   def predict(self,df,xt,yt,**kw):
    self.calls.append(kw);self.asserted=(df["volume"].eq(0).all() and df["amount"].eq(0).all())
    x=np.tile(df.iloc[-1].to_numpy(),(24,1));x[:,:4]*=np.exp(np.random.normal(0,.001,(24,4)))
    return pd.DataFrame(x,columns=df.columns)
  panel=self.panel();g=int(panel[ASSETS[0]][60][0][400]+HOUR);p=Fixture()
  r,paths=sample_paths(p,panel,ASSETS[0],g,np.random.seed)
  self.assertEqual(paths.shape,(16,24,6));self.assertTrue(p.asserted)
  self.assertEqual(len(p.calls),16);self.assertTrue(all(x["sample_count"]==1 for x in p.calls))
  self.assertGreater(r["distinct_terminal_values"],1);self.assertEqual(len(set(r["seeds"])),16)
  t,v=panel[ASSETS[0]][60];v[t+HOUR>g]*=1000 # Includes future OHLC and volume.
  r2,paths2=sample_paths(Fixture(),panel,ASSETS[0],g,np.random.seed)
  np.testing.assert_array_equal(paths,paths2);self.assertEqual(r,r2)
  ref={g:r,g+6*HOUR:dict(r,features=[999]*7)}
  row=asof(ref,g+5*HOUR);self.assertEqual(row["features"],r["features"]);self.assertEqual(row["reference_close"],r["reference_close"]);self.assertEqual(row["sigma"],r["sigma"]);self.assertEqual(row["age_hours"],5)
  self.assertIsNone(asof(ref,g-HOUR));self.assertEqual(asof(ref,g+6*HOUR)["features"],[999]*7)
  self.assertNotEqual(sample_seed(ASSETS[0],g,0),sample_seed(ASSETS[1],g,0))
