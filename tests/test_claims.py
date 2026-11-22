import unittest,tempfile,json
from pathlib import Path
from efc.claims import publish,verify
class ClaimTests(unittest.TestCase):
    def test_all_four_share_sources(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/'results').mkdir();(r/'results/x.json').write_text('{"value":2}')
            for name in ('00','01','02','03'):publish(name,[{'id':name,'value':2,'file':'results/x.json','field':'value'}],r)
            self.assertEqual(verify(r)['claims'],4)
    def test_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/'results').mkdir();(r/'results/x.json').write_text('{"value":2}')
            with self.assertRaises(AssertionError):publish('00',[{'id':'wrong','value':3,'file':'results/x.json','field':'value'}],r)
    def test_changed_source_is_detected(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/'results').mkdir();(r/'results/x.json').write_text('{"value":2}')
            for name in ('00','01','02','03'):publish(name,[{'id':name,'value':2,'file':'results/x.json','field':'value'}],r)
            (r/'results/x.json').write_text('{"value":3}')
            with self.assertRaises(AssertionError):verify(r)
