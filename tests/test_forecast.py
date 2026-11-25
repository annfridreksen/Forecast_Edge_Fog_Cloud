import unittest,math
import numpy as np
from efc import Config,simulate
from efc.forecast.models import *
from efc.forecast.my_network import MyNetwork
from efc.forecast.study import data_for_forecast

class ForecastTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rows=simulate(Config(n_edge=20,n_fog=2,n_tasks=150,arrival_rate_s=15))['tasks']
 def test_interface_baselines(self):
  for model in [Naive(),MovingAverage(),EWMA(),Queueing()]:
   model.fit(self.rows[:100]);p=model.predict(state_of(self.rows[100]));self.assertTrue(0<=p['mean_ms']<=p['p95_ms']);self.assertTrue(math.isfinite(p['p95_ms']))
 def test_network_adapter(self):
  m=MyNetwork().fit(self.rows[:100]);p=m.predict(state_of(self.rows[100]));self.assertTrue(0<=p['mean_ms']<=p['p95_ms'])
 def test_target_not_a_feature(self):
  m=MovingAverage().fit(self.rows[:100]);a=state_of(self.rows[100]);b=dict(a,latency_ms=1e99,end_s=1e99);self.assertEqual(m.predict(a),m.predict(b))
 def test_ranks(self):self.assertEqual(to_ranks({'E':{'mean_ms':4,'p95_ms':7},'F':{'mean_ms':2,'p95_ms':6},'G':{'mean_ms':2,'p95_ms':3}}),{'E':2,'F':1,'G':1})
 def test_invalid_prediction(self):
  for p in [{'mean_ms':float('nan'),'p95_ms':1},{'mean_ms':3,'p95_ms':2}]:
   with self.assertRaises(ValueError):to_ranks({'F':p})
 def test_queue_rho_one(self):
  q=mm1k(1,.9999999999999999,3);self.assertAlmostEqual(q['blocking'],.25);self.assertAlmostEqual(q['L'],1.5);self.assertAlmostEqual(q['W_s'],2)
 def test_queue_empty(self):self.assertEqual(mm1k(0,.055,51)['W_s'],.055)
 def test_little(self):
  for rate in [.01,10,18.181818,10000]:
   q=mm1k(rate,.055,51);self.assertAlmostEqual(q['lambda_eff']*q['W_s'],q['L']);self.assertTrue(0<=q['blocking']<=1)
 def test_temporal_split(self):
  _,train,cal,test,a,b=data_for_forecast();self.assertLess(max(r['end_s'] for r in train),a);self.assertLess(max(r['end_s'] for r in cal),b);self.assertGreaterEqual(min(r['fog_arrival_s'] for r in test),b)
if __name__=='__main__':unittest.main()

class ExportTests(unittest.TestCase):
 def test_frozen_export(self):
  rows=simulate(Config(n_edge=20,n_fog=2,n_tasks=150,arrival_rate_s=15))['tasks']
  m=NeuralNet().fit(rows[:100]);f=FrozenNetwork(export_network(m))
  for r in rows[100:110]:self.assertAlmostEqual(m.predict(state_of(r))['mean_ms'],f.predict(state_of(r))['mean_ms'],places=7)
