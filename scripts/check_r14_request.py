from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from scripts.run_r14_night import validate_request

class RequestTests(unittest.TestCase):
    def test_conservative_cap(self):
        self.assertEqual(validate_request(dict(mode='slice',wall_seconds=900,max_expected_events=1100000)),(900,1100000))
    def test_invalid_budget(self):
        for change in ({'wall_seconds':float('nan')},{'wall_seconds':True},{'wall_seconds':1501},{'max_expected_events':1100001},{'max_expected_events':False},{'mode':'train'}):
            r=dict(mode='slice',wall_seconds=900,max_expected_events=1100000);r.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate_request(r)

if __name__=='__main__':unittest.main()
