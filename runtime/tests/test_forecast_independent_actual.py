import unittest,os,csv,json
from pathlib import Path
import numpy as np
from coinmaster.research.forecast_independent_data import Dataset,MINUTE,HOUR,DAY,ms,sha,targets
@unittest.skipUnless(os.environ.get('FORECAST_DATASET'),'isolated prepared dataset required')
class ActualPreparedContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.ds=Dataset(os.environ['FORECAST_DATASET'],os.environ['FORECAST_PROTOCOL'])
 def test_actual_counts_expiries_and_censor(self):
  d=self.ds;m=d.meta;self.assertEqual(len(m),37440)
  for start,end,pooled,last in [('2024-09-01T00:00:00Z','2026-04-01T00:00:00Z',27648,'2026-03-30T23:00:00Z'),('2024-09-01T00:00:00Z','2026-03-01T00:00:00Z',26160,'2026-02-27T23:00:00Z'),('2026-03-01T00:00:00Z','2026-04-01T00:00:00Z',1440,'2026-03-30T23:00:00Z')]:
   ids=d.rows(start,end);self.assertEqual(len(ids),pooled);self.assertEqual(int(m['origin'][ids[-1]]),ms(last));self.assertTrue((m['expiry'][ids]<=ms(end)).all())
  mask=(m['origin']>=ms(d.lock['check'][0]))&m['observed']&(m['expiry']<=ms(d.lock['check'][1]));ids=np.flatnonzero(mask);self.assertEqual(len(ids),9696);self.assertEqual(int(m['origin'][ids[-1]]),ms('2026-10-19T23:00:00Z'));self.assertEqual(int((~m['observed']).sum()),48)
  self.assertTrue(np.array_equal(m['expiry'],m['origin']+MINUTE+DAY))
  with self.assertRaisesRegex(ValueError,'CHECK_LABELS_SEALED'):d.rows(*d.lock['check'])
 def test_actual_source_entry_terminal_and_label_parity(self):
  d=self.ds;train=d.rows(*d.lock['train'])
  for asset,symbol in enumerate(('BTCUSDT','SOLUSDT')):
   minute=np.load(d.path/f'minutes-{symbol}.npy',mmap_mode='r');ids=train[d.meta['asset'][train]==asset]
   for row in [ids[0],ids[len(ids)//2],ids[-1]]:
    index=(int(d.meta['origin'][row])-d.manifest['minute_start_ms'])//MINUTE+1
    self.assertEqual(float(d.meta['entry'][row]),float(minute[index,0]));self.assertEqual(float(d.meta['reference'][row]),float(minute[index-2,3]));v=minute[index:index+1440];y,di,_=targets(v[:,0],v[:,1],v[:,2],v[:,3],d.meta['sigma'][row]);np.testing.assert_allclose(y,d.targets[row],atol=1e-12);self.assertEqual(di,d.direction[row])
 def test_actual_feature_bar_ids_and_sigma(self):
  d=self.ds;ends=np.load(d.path/'feature-bar-ends.npy',mmap_mode='r');self.assertTrue((ends<=d.meta['origin'][:,None]).all());self.assertTrue(np.array_equal(ends[:,:2],np.broadcast_to(d.meta['origin'][:,None],ends[:,:2].shape)))
  for a,symbol in enumerate(('BTCUSDT','SOLUSDT')):
   p=Path(os.environ['FORECAST_SOURCE_ROOT'])/f'reports/btc-split-sol-cover-20261018/data-warmup-{symbol}-1h.csv'
   with p.open() as f:rows=list(csv.DictReader(f))
   close=np.array([float(r['close']) for r in rows[-169:]]);expected=np.std(np.diff(np.log(close)),ddof=1)*np.sqrt(24);self.assertAlmostEqual(expected,d.meta['sigma'][a],places=13)
 def test_source_manifest_pins(self):
  source=Path(os.environ['FORECAST_SOURCE_ROOT'])
  for old,digest in self.ds.manifest['sources'].items():
   relative=old.split('/source/',1)[1];self.assertEqual(sha(source/relative),digest)
if __name__=='__main__':unittest.main()
