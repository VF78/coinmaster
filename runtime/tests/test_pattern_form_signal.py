import unittest
from types import SimpleNamespace
import numpy as np
import torch
from coinmaster.research.pattern_form_models import Context,CNNSpatial,full_descriptor
from coinmaster.research.btc_pattern_models import CNN,Heads

class FormSignal(unittest.TestCase):
    def test_new_method_names_do_not_bypass_complex_controls(self):
        from coinmaster.research.btc_pattern_evaluate import required_references
        for name in ('Context','CNNSpatial','Flat'):
            self.assertEqual(required_references(name+'-direct'),['prior','CatBoost'])
            self.assertEqual(required_references(name+'-knn'),['prior','CatBoost','numeric-knn','random-context'])
    def test_context_is_exact_same_heads_and_ignores_window(self):
        torch.manual_seed(7);model=Context();torch.manual_seed(7);heads=Heads(0)
        for k,v in heads.state_dict().items():torch.testing.assert_close(model.heads.state_dict()[k],v,rtol=0,atol=0)
        c=torch.randn(4,12);a=model(torch.randn(4,2,64,6),c);b=model(torch.zeros(4,2,64,6),c);expected=heads(torch.empty(4,0),c)
        for x,y,z in zip(a,b,expected):torch.testing.assert_close(x,y,rtol=0,atol=0);torch.testing.assert_close(x,z,rtol=0,atol=0)
        self.assertEqual([tuple(v.shape) for v in a],[(4,64),(4,3),(4,2,3)])
    def test_saved_context_factory_inference_and_scalers(self):
        from coinmaster.research.btc_pattern_train import neural_predict
        torch.manual_seed(7);model=Context().eval();c=np.arange(36,dtype=np.float32).reshape(3,12)/36
        mean=np.ones(12,np.float32)*.1;std=np.ones(12,np.float32)*2
        state=dict(kind='Context',weights=model.state_dict(),context_mean=mean,context_std=std)
        actual=neural_predict(SimpleNamespace(c=c),state,np.arange(3),'cpu')
        with torch.inference_mode():z,d,q=model(torch.empty(3,0),torch.from_numpy((c-mean)/std))
        for a,b in zip(actual,(z.numpy(),torch.softmax(d,1).numpy(),q.numpy())):np.testing.assert_allclose(a,b,rtol=0,atol=0)
    def test_full_descriptor_preserves_all_positions_and_context(self):
        x=np.arange(2*2*64*6,dtype=np.float32).reshape(2,2,64,6);c=np.ones((2,12),np.float32);z=full_descriptor(SimpleNamespace(x=x,c=c))
        self.assertEqual(z.shape,(2,780));np.testing.assert_array_equal(z[:,:768],x.reshape(2,-1));np.testing.assert_array_equal(z[:,768:],c)
        a=np.zeros((1,2,64,6),np.float32);b=a.copy();a[0,0,0,0]=1;b[0,0,1,0]=1
        np.testing.assert_array_equal(a.reshape(1,2,16,4,6).mean(3),b.reshape(1,2,16,4,6).mean(3))
        self.assertFalse(np.array_equal(full_descriptor(SimpleNamespace(x=a,c=c[:1])),full_descriptor(SimpleNamespace(x=b,c=c[:1]))))
    def test_spatial_pool_keeps_position_and_same_original_conv_initialization(self):
        torch.manual_seed(7);old=CNN();torch.manual_seed(7);new=CNNSpatial()
        for k,v in old.encoder.state_dict().items():torch.testing.assert_close(v,new.encoder.state_dict()[k],rtol=0,atol=0)
        self.assertEqual(new.heads.projection.in_features,2060)
        a=torch.zeros(1,128,2,8);b=a.clone();a[:,:,0,0]=1;b[:,:,1,7]=1
        global_pool=torch.nn.AdaptiveAvgPool2d(1);spatial_pool=new.encoder[-1]
        torch.testing.assert_close(global_pool(a),global_pool(b),rtol=0,atol=0)
        self.assertGreater(float((spatial_pool(a)-spatial_pool(b)).abs().sum()),0)
        self.assertEqual(tuple(spatial_pool(a).flatten(1).shape),(1,2048))
if __name__=='__main__':unittest.main()
