"""Recording preserves the accepted cohort and no completed seed is repeated."""
import tempfile
import unittest
from efc.model import Config, COMPONENTS
from efc.pilot import KernelSampler
from efc.primary import PrimarySampler
from efc.grid import CachedSampler

class PrimarySummaryTests(unittest.TestCase):
    def test_exact_cohort_and_components_survive_cache(self):
        c=Config(n_cloud=40,n_fog=30,buffer=2,arrival_rate_s=.1*50/.055,seed=100)
        with tempfile.TemporaryDirectory() as d:
            sample=CachedSampler(PrimarySampler(c),d)
            observation=sample(100,2,4,1)
            old=KernelSampler(c)(100,2,4,1)
            self.assertEqual((observation.full,observation.first,observation.second),
                             (old.full,old.first,old.second))
            row=observation.provenance['primary_summary']
            self.assertEqual(row['arrivals'],observation.full.arrivals)
            self.assertEqual(row['dropped'],observation.full.dropped)
            self.assertEqual(row['unfinished'],observation.full.unfinished)
            self.assertAlmostEqual(sum(row[k] for k in COMPONENTS),row['mean_ms'],places=9)
            self.assertEqual(row['kernel'],'efc.model.simulate')
            restored=CachedSampler(PrimarySampler(c),d)
            self.assertEqual(observation,restored(100,2,4,1))
            self.assertEqual(restored.new_runs,0)
