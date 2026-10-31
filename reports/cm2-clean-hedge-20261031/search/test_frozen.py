"""Properties of the actual frozen design, without any native runtime."""
import hashlib
import json
from pathlib import Path
import unittest
import generate


class FreezeTests(unittest.TestCase):
    def test_frozen_design_contract(self):
        frozen = json.loads((generate.HERE / 'FROZEN64.json').read_text())
        space = json.loads((generate.HERE / 'SPACE.json').read_text())
        self.assertEqual(len(frozen['cases']), 64)
        self.assertEqual(len({x['policy_sha256'] for x in frozen['cases']}), 64)
        for i, case in enumerate(frozen['cases']):
            self.assertEqual(case['run_id'], f'CM2_BROAD_V1_{i:03d}')
            self.assertEqual(len(case['u']), 7)
            self.assertTrue(all(0 <= x < 1 for x in case['u']))
            self.assertEqual((case['policy']['mode'], case['policy']['version']), ('joint','cm2-v1'))
            for spec in space['parameters']:
                self.assertGreaterEqual(case['policy'][spec['name']], spec['lower'])
                self.assertLessEqual(case['policy'][spec['name']], spec['upper'])
            self.assertEqual(case['policy_sha256'], hashlib.sha256(json.dumps(case['policy'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
        self.assertEqual(sum(x['block']=='INITIAL32_PENDING_ROOT_GO' for x in frozen['cases']),32)
        self.assertEqual(sum(x['block']=='CONDITIONAL32_HOLD' for x in frozen['cases']),32)
    def test_deterministic_frozen_reproduction(self):
        before = (generate.HERE / 'FROZEN64.json').read_bytes()
        self.assertEqual(generate.encoded(generate.build()), before)
        self.assertEqual(generate.encoded(generate.build()), before)
        self.assertEqual((generate.HERE / 'FROZEN64.json').read_bytes(), before)
    def test_transform_boundaries_and_integer_channel(self):
        space = json.loads((generate.HERE / 'SPACE.json').read_text())
        lower = generate.transform([0]*7,space)
        upper = generate.transform([1]*7,space)
        for spec in space['parameters']:
            self.assertEqual(lower[spec['name']],spec['lower'])
            self.assertEqual(upper[spec['name']],spec['upper'])
        self.assertIsInstance(lower['trend_hours'], int)
        self.assertIsInstance(upper['trend_hours'], int)


if __name__=='__main__': unittest.main()
