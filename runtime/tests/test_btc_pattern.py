import unittest
import numpy as np
from coinmaster.research.btc_pattern_data import *

class PatternDataTests(unittest.TestCase):
    def path(self):return np.tile([100.,100.,100.,100.,1.],(4320,1))
    def test_first_passage_and_intraminute_bounds(self):
        v=self.path();v[0,1]=102;v[1,2]=98;r=path_targets(v,.01)
        self.assertEqual(r['direction'],0);self.assertFalse(r['ambiguous']);self.assertGreater(r['mfe'][0,0],1)
        v=self.path();v[0,2]=98;v[1,1]=102;r=path_targets(v,.01)
        self.assertEqual(r['direction'],1);self.assertEqual(r['mfe'][0,0],0)
        v=self.path();v[0,1:3]=[102,98];r=path_targets(v,.01)
        self.assertEqual(r['direction'],-1);self.assertTrue(r['ambiguous']);self.assertEqual(r['mfe'][0,0],0);self.assertGreater(r['mfe'][0,1],1)
        v[0,0]=100 # entry remains separate from future gap
        v[1]=[98,103,97,100,1];v[0]=[100,100,100,100,1];r=path_targets(v,.01)
        self.assertEqual(r['direction'],1);self.assertEqual(r['mfe'][0,1],0)
        with self.assertRaises(ValueError):path_targets(v[:-1],.01)
    def test_utc_and_purge(self):
        self.assertEqual(ms('2025-01-01'),ms('2025-01-01T00:00:00Z'))
        m=np.zeros(24000,dtype=META);m['origin']=np.arange(ms('2024-06-01'),ms('2024-06-01')+len(m)*HOUR,HOUR);m['label_end']=m['origin']+MINUTE+72*HOUR;m['valid']=True;m['observed']=True
        for f in folds(m):
            for name,cut in [('subfit',f['inner_cutoff']),('early_stop',f['fit_cutoff']),('refit',f['fit_cutoff']),('outer',f['outer_end'])]:self.assertTrue((m['label_end'][f[name]]<=cut).all())
            self.assertFalse(np.intersect1d(f['subfit'],f['early_stop']).size)
    def test_causal_prefix_features(self):
        n=1700;t=np.arange(n)*HOUR;c=100*np.exp(np.arange(n)*.0001+np.sin(np.arange(n))*.001)
        v=np.column_stack((c,c*1.002,c*.998,c,np.arange(n)%27+10));t4,v4=aggregate(t,v,4*HOUR);panels={1:(t,v),4:(t4,v4)};origin=1300*HOUR
        before=features_at(panels,origin);v[1300:,:4]*=10;v4[t4>=origin,:4]*=7
        after=features_at(panels,origin)
        for a,b in zip(before[:4],after[:4]):np.testing.assert_array_equal(a,b)
        self.assertTrue((before[3]+np.array([4,1])[:,None]*HOUR<=origin).all())
    def test_filter_before_rank_and_separation(self):
        origins=np.arange(500)*HOUR;ends=origins+72*HOUR+MINUTE;z=np.tile([1.,0.],(500,1));q=np.array([1.,0.])
        got=neighbors(z,q,origins,ends,500*HOUR,400*HOUR)
        self.assertTrue((ends[got]<=400*HOUR).all());self.assertTrue((np.diff(origins[got])>=72*HOUR).all());self.assertGreater(len(got),0)
    def test_positive_and_block_shuffled_control(self):
        # Synthetic train-only outcomes: repeated shapes have matching classes;
        # shuffling 72h episode labels breaks the association without changing X.
        rng=np.random.default_rng(7);n=120;cl=np.arange(n)%3
        z=np.eye(3)[cl];orig=np.arange(n)*96*HOUR;ends=orig+72*HOUR+MINUTE
        correct=[];shuffled=[];permuted=cl[rng.permutation(n)]
        for k in range(3):
            idx=neighbors(z,np.eye(3)[k],orig,ends,20000*HOUR,20000*HOUR)
            correct.append(np.mean(cl[idx[:16]]==k));shuffled.append(np.mean(permuted[idx[:16]]==k))
        self.assertGreater(np.mean(correct),.99);self.assertLess(np.mean(shuffled),.6)
    def test_metric_no_support_and_gradients(self):
        import torch
        from coinmaster.research.btc_pattern_models import soft_metric,TCN
        z=torch.randn(8,64,requires_grad=True);y=torch.randn(8,12);o=torch.arange(8)*HOUR
        loss,s=soft_metric(z,y,o,o+72*HOUR,torch.ones(6),1.)
        self.assertEqual(float(loss.detach()),0);loss.backward();self.assertTrue(torch.isfinite(z.grad).all())
        z=torch.nn.functional.normalize(torch.randn(8,64,requires_grad=True),dim=1);o=torch.arange(8)*100*HOUR
        loss,s=soft_metric(z,y,o,o+72*HOUR,torch.ones(6),1.);self.assertTrue(torch.isfinite(loss));loss.backward();self.assertEqual(s['eligible_anchors'],1)
        model=TCN();self.assertLess(sum(p.numel() for p in model.parameters()),300000)
if __name__=='__main__':unittest.main()

class QualityVariantTests(unittest.TestCase):
    def metadata(self):
        n=20928;m=np.zeros(n,dtype=META);m['origin']=np.arange(ms('2024-06-01'),ms('2024-06-01')+n*HOUR,HOUR);m['label_end']=m['origin']+MINUTE+72*HOUR;m['input_start']=m['origin']-256*HOUR;m['valid']=True;m['observed']=True
        return m
    def test_recent_window_same_start_and_unchanged_outer(self):
        from coinmaster.research.pattern_quality_variants import variant_folds
        m=self.metadata();original=list(folds(m));recent=list(variant_folds(m,'RECENT180'))
        for f,b,expected in zip(recent,original,['2024-07-05','2025-01-02','2025-07-05']):
            self.assertEqual(f['window_start'],ms(expected));np.testing.assert_array_equal(f['outer'],b['outer']);np.testing.assert_array_equal(f['early_stop'],b['early_stop'])
            self.assertEqual(len(f['subfit']),3576);self.assertEqual(len(f['refit']),4248)
            for part,cut in [('subfit',f['inner_cutoff']),('early_stop',f['fit_cutoff']),('refit',f['fit_cutoff'])]:
                ids=f[part];self.assertTrue((m['origin'][ids]>=f['window_start']).all());self.assertTrue((m['label_end'][ids]<=cut).all())
            self.assertEqual(m['origin'][f['subfit'][0]],m['origin'][f['refit'][0]])
        for f,b in zip(variant_folds(m,'METRIC_OFF'),original):
            for part in ['subfit','early_stop','refit','outer']:np.testing.assert_array_equal(f[part],b[part])
    def test_recent_index_maturity_and_query_window(self):
        from coinmaster.research.pattern_quality_variants import variant_folds
        m=self.metadata();f=next(variant_folds(m,'RECENT180'));index=f['refit'];q=f['outer'][0];z=np.tile([1.,0.],(len(index),1));got=neighbors(z,np.array([1.,0.]),m['origin'][index],m['label_end'][index],f['fit_cutoff'],m['input_start'][q]);chosen=index[got]
        self.assertGreaterEqual(len(chosen),16);self.assertTrue((m['origin'][chosen]>=f['window_start']).all());self.assertTrue((m['label_end'][chosen]<=m['input_start'][q]).all());self.assertTrue((np.diff(m['origin'][chosen])>=72*HOUR).all())
    def test_metric_off_zero_gradient_preserves_support_statistics(self):
        import torch
        from coinmaster.research import btc_pattern_models as models
        from coinmaster.research.pattern_quality_variants import install_metric_off
        original=models.soft_metric
        try:
            torch.manual_seed(7);z=torch.randn(8,64,requires_grad=True);y=torch.randn(8,12);o=torch.arange(8)*100*HOUR
            expected,stat=original(z,y,o,o+72*HOUR,torch.ones(6),1.);self.assertGreater(float(expected.detach()),0)
            install_metric_off();actual,actualstat=models.soft_metric(z,y,o,o+72*HOUR,torch.ones(6),1.);actual.backward();self.assertEqual(float(actual.detach()),0);self.assertEqual(float(z.grad.abs().sum()),0);self.assertEqual(stat,actualstat)
        finally:models.soft_metric=original
