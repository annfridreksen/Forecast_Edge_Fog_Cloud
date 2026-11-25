import unittest
from dataclasses import replace
import numpy as np
from efc.model import Config,COMPONENTS
from efc.stationary import fifo_fog,stationary_run,ci95,scenarios

class StationaryTests(unittest.TestCase):
    def test_known_fifo_and_drop(self):
        a=np.array([0.,.1,.2,1.]);s=np.ones(4);f=np.zeros(4,dtype=int)
        start,end,q=fifo_fog(a,s,f,1,1)
        np.testing.assert_allclose(start[[0,1,3]],[0,1,2])
        self.assertTrue(np.isnan(start[2]));self.assertEqual(q[2],1)
    def test_completions_before_equal_arrival(self):
        start,end,_=fifo_fog(np.array([0.,1.]),np.ones(2),np.zeros(2,dtype=int),1,0)
        np.testing.assert_allclose(start,[0,1])
    def test_distinct_queues(self):
        start,end,_=fifo_fog(np.zeros(4),np.ones(4),np.array([0,1,0,1]),2,1)
        np.testing.assert_allclose(start,[0,0,1,1])
    def test_buffer_monotonicity_on_shared_stream(self):
        rng=np.random.default_rng(10);a=np.cumsum(rng.exponential(.04,2000));s=rng.uniform(.03,.08,2000);f=np.zeros(2000,dtype=int)
        counts=[np.isfinite(fifo_fog(a,s,f,1,b)[1]).sum() for b in (0,2,20,100)]
        self.assertEqual(counts,sorted(counts))
    def test_window_balance_and_components(self):
        c=replace(Config(n_cloud=40),arrival_rate_s=.85*50/.055)
        r=stationary_run(c,warmup=40,observe=80,guard=100)
        self.assertEqual(r['completed']+r['dropped'],r['arrivals'])
        self.assertAlmostEqual(sum(r[x] for x in COMPONENTS),r['mean_ms'],7)
        self.assertGreater(r['mean_fog_wait_ms'],0)
        self.assertTrue(0<r['fog_utilization']<1)
        self.assertTrue(0<r['cloud_utilization']<1)
    def test_repeatability(self):
        c=replace(Config(n_cloud=40),arrival_rate_s=.5*50/.055)
        self.assertEqual(stationary_run(c,20,40,100),stationary_run(c,20,40,100))
    def test_cloud_instability_rejected(self):
        with self.assertRaises(ValueError):stationary_run(replace(Config(),arrival_rate_s=.95*50/.055),10,10,10)
    def test_student_interval_uses_replicates(self):
        mean,lo,hi=ci95(np.arange(10));self.assertEqual(mean,4.5)
        self.assertAlmostEqual(hi-mean,2.16585059,6)
        self.assertAlmostEqual(mean-lo,hi-mean)
    def test_scenario_design(self):
        ss=scenarios();self.assertEqual(len(ss),270)
        self.assertTrue(all(c.n_fog in (30,40,50,60,70) and c.n_cloud==40 for _,_,c in ss))
        self.assertTrue(all(0<c.arrival_rate_s/50*.055<1 for _,_,c in ss))
    def test_empty_ci_invalid(self):
        with self.assertRaises(ValueError):ci95([1])
