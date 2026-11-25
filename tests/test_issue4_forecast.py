import unittest
from dataclasses import replace
import numpy as np
from efc.model import Config
from efc.forecast.models import Queueing,QueueingMM1K,conformal_margin

class ReviewForecastTests(unittest.TestCase):
    def test_conditional_formula(self):
        m=Queueing(Config());s={'queue_before':3,'busy_before':1,'edge_known_ms':10,'observed_rate_s':0}
        self.assertEqual(m.mean(s),10+4.5*55+35+20)
    def test_config_not_constants(self):
        c=replace(Config(),fog_service_ms=(20,40),fog_cloud_ms=(2,6),cloud_service_ms=(4,8))
        m=Queueing(c);self.assertEqual(m.mean({'queue_before':0,'busy_before':0,'edge_known_ms':7}),47)
    def test_current_queue_changes_prediction(self):
        m=Queueing();s={'queue_before':0,'busy_before':0,'edge_known_ms':0}
        self.assertEqual(m.mean(dict(s,queue_before=1))-m.mean(s),55)
    def test_mm1k_retained(self):
        m=QueueingMM1K(replace(Config(),fog_cloud_ms=(0,0),cloud_service_ms=(0,0)))
        self.assertEqual(m.mean({'observed_rate_s':0,'edge_known_ms':0}),55)
    def test_conformal_order_not_interpolation(self):
        q,k=conformal_margin(np.arange(20));self.assertEqual(k,20);self.assertEqual(q,19)
    def test_finite_sample_small_n(self):
        q,k=conformal_margin([1,2,3]);self.assertTrue(np.isinf(q));self.assertEqual(k,4)
    def test_calibration_is_not_test(self):
        a=np.arange(100);q,k=conformal_margin(a);self.assertEqual(k,96);self.assertEqual(q,95)
        self.assertEqual(conformal_margin(a),(q,k))
    def test_invalid_scores(self):
        with self.assertRaises(ValueError):conformal_margin([1,np.nan])
