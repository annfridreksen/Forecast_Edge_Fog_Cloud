import unittest
from dataclasses import replace
from efc import Config,simulate
from efc.model import COMPONENTS

class ModelTests(unittest.TestCase):
 def test_default_all_zones(self):
  r=simulate();self.assertEqual(len(r['metrics']['observations_per_fog']),50);self.assertEqual(sum(r['metrics']['observations_per_fog']),200)
 def test_sum_six(self):
  for r in simulate()['tasks']:
   self.assertAlmostEqual(sum(r[x] for x in COMPONENTS),r['latency_ms'],places=7)
 def test_deterministic(self):self.assertEqual(simulate(),simulate())
 def test_conservation(self):
  m=simulate(Config(n_tasks=300,arrival_rate_s=1000,buffer=0))['metrics'];self.assertEqual(m['arrivals'],m['completed']+m['dropped']);self.assertGreater(m['dropped'],0)
 def test_fifo_capacity(self):
  c=Config(n_edge=1,n_fog=1,n_cloud=1,buffer=1,n_tasks=3,edge_fixed_ms=(0,0),mobile_fraction=0,fog_service_ms=(10,10),fog_cloud_ms=(0,0),cloud_service_ms=(0,0))
  r=simulate(c,[0,0,0]);self.assertEqual([x['status'] for x in r['tasks']],['completed','completed','dropped']);self.assertEqual([x['fog_start_s'] for x in r['tasks'][:2]],[0,.01])
 def test_tied_completion_before_arrival(self):
  c=Config(n_edge=1,n_fog=1,n_cloud=1,buffer=0,n_tasks=2,edge_fixed_ms=(0,0),mobile_fraction=0,fog_service_ms=(10,10),fog_cloud_ms=(0,0),cloud_service_ms=(0,0))
  self.assertEqual(simulate(c,[0,.01])['metrics']['dropped'],0)
 def test_each_fog_independent(self):
  r=simulate(Config(n_edge=50,n_fog=50,n_tasks=500,arrival_rate_s=500));self.assertEqual(len({x['fog'] for x in r['tasks']}),50)
 def test_empty(self):
  m=simulate(Config(n_tasks=0))['metrics'];self.assertIsNone(m['mean_ms']);self.assertEqual(m['dropped'],0)
 def test_bad_config(self):
  for kw in [{'n_fog':0},{'buffer':-1},{'arrival_rate_s':0},{'fog_service_ms':(-1,2)},{'fog_weights':(0,)}]:
   with self.assertRaises(ValueError):Config(**kw)
 def test_bad_arrivals(self):
  for a in [[0],[1,0],[0,float('nan')]]:
   with self.assertRaises(ValueError):simulate(Config(n_tasks=2),a)
 def test_utilization_bounds(self):
  for vv in simulate(Config(n_tasks=300,arrival_rate_s=500))['metrics']['utilization'].values():
   self.assertTrue(all(0<=v<=1+1e-9 for v in vv))
 def test_cloud_scaling_paired(self):
  a=simulate(Config());b=simulate(Config(n_cloud=24));self.assertEqual([r['fog_service_ms'] for r in a['tasks']],[r['fog_service_ms'] for r in b['tasks']]);self.assertAlmostEqual(a['metrics']['mean_ms'],b['metrics']['mean_ms'])
 def test_node_queues_do_not_overlap(self):
  r=simulate(Config(n_tasks=1000,arrival_rate_s=600))
  for f in range(50):
   intervals=sorted((x['fog_start_s'],x['fog_end_s']) for x in r['tasks'] if x['fog']==f and x['status']=='completed');self.assertTrue(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])))
 def test_raw_queue_capacity(self):
  r=simulate(Config(n_tasks=300,arrival_rate_s=1000,buffer=2));self.assertTrue(all(x['waiting']<=2 for x in r['queue_trace']))
 def test_sensor_types(self):
  for p in [0.,1.]:
   r=simulate(Config(mobile_fraction=p));self.assertTrue(all(x['mobile']==bool(p) for x in r['tasks']))
if __name__=='__main__':unittest.main()
