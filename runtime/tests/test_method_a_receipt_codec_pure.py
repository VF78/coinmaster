"""Two focused persisted-owner codec checks, with engine imports blocked."""
import json
import unittest
from copy import deepcopy
from test_method_a_recovery_code0 import Probe,FEATURE,D,OrderSide
from coinmaster.research.method_a_receipt_codec import receipt_owner_values
from coinmaster.research.method_a_risk_rows import wire


class ReceiptCodec(unittest.TestCase):
    def test_actual_persisted_code0_owner_serializes_without_mutation(self):
        p=Probe();p._pair_submit(p.sol.id,1,D('132.9'),'SOL_CAP',p.ns)
        owner=p._pair_orders[str(p.sent[0].client_order_id)]
        original=deepcopy(owner);feature=owner['code0_route']['feature'];side=owner['code0_route']['side']
        payload=wire(receipt_owner_values(owner))
        self.assertEqual(json.loads(json.dumps(payload)),payload)
        self.assertEqual(payload['code0_route']['side'],'BUY')
        self.assertEqual(payload['code0_route']['feature']['b'],str(FEATURE.b))
        self.assertEqual(owner,original);self.assertIs(owner['code0_route']['feature'],feature);self.assertIs(owner['code0_route']['side'],side)
        self.assertEqual(len(p.sent),1)
    def test_unsupported_metadata_remains_unknown_without_repr_or_owner_mutation(self):
        p=Probe();p._pair_submit(p.sol.id,1,D('132.9'),'SOL_CAP',p.ns)
        owner=p._pair_orders[str(p.sent[0].client_order_id)];original=deepcopy(owner)
        for key in ('feature','side'):
            invalid=dict(owner);invalid['code0_route']=dict(owner['code0_route']);invalid['code0_route'][key]=object()
            with self.assertRaisesRegex(TypeError,'UNKNOWN_CODE0_RECEIPT'):wire(receipt_owner_values(invalid))
        invalid=dict(owner);invalid['unrecognized_object']=object()
        with self.assertRaisesRegex(TypeError,'METHOD_A_UNKNOWN_REPORT_TYPE'):wire(receipt_owner_values(invalid))
        self.assertEqual(owner,original)

if __name__=='__main__':unittest.main()
