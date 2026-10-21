import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from coinmaster.research import btc_pattern_evaluate as ev
from coinmaster.research.btc_pattern_data import META,HOUR,method_input_start
from coinmaster.research.btc_pattern_train import aggregate_predict

class Form00(unittest.TestCase):
    def test_head_denominators_and_tail(self):
        np.testing.assert_allclose(aggregate_predict([(2,1,10,2),(2,2,0,4)]),[10/3+3,10/3,3])
        np.testing.assert_allclose(aggregate_predict([(64,64,0,0),(1,1,10,10)]),[20/65,10/65,10/65])
        np.testing.assert_allclose(aggregate_predict([(2,0,0,3)]),[3,0,3])
    def test_method_support_legacy_and_v2(self):
        legacy=np.zeros(2,dtype=[('origin','i8'),('input_start','i8')]);legacy['origin']=1000*HOUR;legacy['input_start']=744*HOUR
        np.testing.assert_array_equal(method_input_start(legacy,'TCN'),664*HOUR)
        np.testing.assert_array_equal(method_input_start(legacy,'numeric-knn'),664*HOUR)
        for method in ('CNN','Kronos','random-context'):np.testing.assert_array_equal(method_input_start(legacy,method),744*HOUR)
        m=np.zeros(2,dtype=META);m['origin']=legacy['origin'];m['input_start']=664*HOUR;m['raw_input_start']=744*HOUR;m['engineered_input_start']=664*HOUR
        for method in ('TCN','numeric-knn','CNN','Kronos','random-context'):np.testing.assert_array_equal(method_input_start(m,method),method_input_start(legacy,method))
        with self.assertRaises(ValueError):method_input_start(m,'unknown')
    def test_undefined_auc_and_empty_ci(self):
        self.assertIsNone(ev.safe_auc(np.ones(3),np.ones(3)*.5))
        self.assertIsNone(ev.safe_auc(np.array([]),np.array([])))
        self.assertIsNone(ev.paired_ci(np.array([np.nan]),np.array([1]))['mean'])
        self.assertEqual(ev.safe_auc(np.array([0,1]),np.array([.1,.9])),1)
    def fixture(self,root):
        prepared=root/'prepared';inputs=root/'forecasts';prepared.mkdir();inputs.mkdir();protocol=root/'protocol.json';protocol.write_text('{}')
        m=np.zeros(9,dtype=META);m['valid']=m['observed']=True;np.save(prepared/'metadata.npy',m)
        y=np.ones((9,2,2),np.float32);d=np.arange(9)%3;np.savez(prepared/'labels.npz',direction=d,mfe=y);(prepared/'manifest.json').write_text(json.dumps({'artifacts':{n:{'sha256':ev.sha(prepared/n)} for n in ('metadata.npy','labels.npz')}}));(inputs/'development-complete.json').write_text('{"status":"FORM00_ZERO_FIT_COMPLETE"}')
        methods=['prior','CatBoost','numeric-knn','random-context','TCN-direct'];folds=[]
        for f in range(3):
            name='F'+str(f+1);(inputs/name).mkdir();ids=np.arange(f*3,f*3+3);folds.append(dict(name=name,outer=ids))
            for method in methods:np.savez(inputs/name/(method+'.npz'),ids=ids,truth_D=d[ids],truth_Q=y[ids,:,0],truth_Q_upper=y[ids,:,1],probabilities=np.ones((3,3))/3,q_raw=np.ones((3,2,3)),q_projected=np.ones((3,2,3)),support=np.zeros(3))
        def bind():ev.write_evaluation_contract(inputs,prepared,protocol,methods,{'fixture':'SYNTHETIC_NOT_MARKET'})
        bind();return prepared,inputs,protocol,folds,bind
    def test_guards_reject_missing_fold_truth_ids_probability_projection_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            prepared,inputs,protocol,folds,bind=self.fixture(Path(tmp))
            with patch.object(ev,'folds',lambda meta:folds):
                ev.validate_artifacts(inputs,prepared,protocol)
                f=inputs/'F3/TCN-direct.npz';original=f.read_bytes();f.unlink();bind()
                with self.assertRaisesRegex(ValueError,'INCOMPLETE'):ev.validate_artifacts(inputs,prepared,protocol)
                f.write_bytes(original)
                changes=[('truth_D',lambda z:(z['truth_D']+1)%3,'TRUTH'),('ids',lambda z:z['ids'][::-1],'IDS'),('ids',lambda z:np.repeat(z['ids'][0],3),'IDS'),('probabilities',lambda z:np.zeros((3,3)),'PROBABILITY'),('probabilities',lambda z:np.full((3,3),np.nan),'PROBABILITY'),('q_projected',lambda z:z['q_projected']+1,'PROJECTION')]
                for key,fn,error in changes:
                    z=dict(np.load(f));z[key]=fn(z);np.savez(f,**z);bind()
                    with self.assertRaisesRegex(ValueError,error):ev.validate_artifacts(inputs,prepared,protocol)
                    f.write_bytes(original)
                bind();canonical=prepared/'labels.npz';saved=canonical.read_bytes();canonical.write_bytes(saved+b'changed')
                with self.assertRaisesRegex(ValueError,'PREPARED_ARTIFACT_HASH'):ev.validate_artifacts(inputs,prepared,protocol)
                canonical.write_bytes(saved)
                protocol.write_text('{"changed":true}')
                with self.assertRaisesRegex(ValueError,'HASH'):ev.validate_artifacts(inputs,prepared,protocol)
                (inputs/'evaluation-contract.json').unlink()
                with self.assertRaises(FileNotFoundError):ev.validate_artifacts(inputs,prepared,protocol)
if __name__=='__main__':unittest.main()
