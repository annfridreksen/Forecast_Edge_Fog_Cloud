from pathlib import Path
import tempfile,unittest
V2=Path(__file__).resolve().parents[1]/'v2/code'
@unittest.skipUnless(V2.exists(),'immutable v2 is absent in this checkout')
class PlacementTests(unittest.TestCase):
 def test_control_adapter(self):
  from efc.placement.study import controls
  with tempfile.TemporaryDirectory() as d:
   frame,_,_=controls(d);self.assertEqual(list(frame.time_ms.iloc[:3]),[8,4,6]);self.assertEqual(frame.status.iloc[3],'NO_PLAN_IN_CLASS')
if __name__=='__main__':unittest.main()
