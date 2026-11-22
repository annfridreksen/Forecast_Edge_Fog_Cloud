import unittest
from dataclasses import replace
import numpy as np
from efc.model import Config,simulate,COMPONENTS
from efc.sensitivity import sensitivity_designs
class SensitivityTests(unittest.TestCase):
    def test_design_prespecified_and_stable(self):
        x=sensitivity_designs();self.assertEqual(len(x),6)
        for _,_,c in x:
            self.assertEqual((c.n_fog,c.n_cloud),(50,40))
            self.assertAlmostEqual(c.arrival_rate_s/c.n_fog*.055,.7)
            self.assertLess(c.arrival_rate_s/c.n_fog*sum(c.fog_cloud_ms)/2000,1)
    def test_share_keeps_combined_profile(self):
        values=[]
        for share in (.3,.5,.7):
            r=simulate(replace(Config(),edge_processing_share=share));values.append(r['metrics']['mean_ms'])
        self.assertTrue(np.allclose(values,values[0],atol=1e-6))
    def test_six_and_three_shares_close(self):
        r=simulate()['metrics'];self.assertAlmostEqual(sum(r['components_ms'].values()),r['mean_ms'],7)
        self.assertAlmostEqual(sum(r['stage_shares_pct'].values()),100,7)
    def test_network_profile_from_config(self):
        r=simulate(replace(Config(),fog_cloud_ms=(30,70)))
        self.assertTrue(all(30<=x['fc_service_ms']<=70 for x in r['tasks']))
