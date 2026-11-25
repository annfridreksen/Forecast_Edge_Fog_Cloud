"""Storage-only tests: all ticks, inputs, outcomes and metrics must agree."""
from dataclasses import replace
import json
import unittest
from efc.model import Config, simulate
from efc.records import TaskColumns, materialize_result
from efc.stationary import stationary_run, observation_window

class CompactTests(unittest.TestCase):
    def same(self,c,arrivals=None):
        a=simulate(c,arrivals);b=simulate(c,arrivals,compact=True)
        self.assertEqual(a,materialize_result(b))
        self.assertEqual(json.dumps(a,sort_keys=True),json.dumps(materialize_result(b),sort_keys=True))
        return a,b

    def test_empty(self):self.same(Config(n_tasks=0))

    def test_boundary_three_offsets(self):
        c=Config(n_edge=1,n_fog=1,n_cloud=1,buffer=0,n_tasks=2,mobile_fraction=0,
                 edge_fixed_ms=(3,3),edge_processing_share=1/3,fog_service_ms=(9,9),
                 fog_cloud_ms=(0,0),cloud_service_ms=(0,0))
        for t,drop in (('.008999999',1),('.009',0),('.009000001',0)):
            with self.subTest(t=t):
                a,_=self.same(c,['0',t]);self.assertEqual(a['metrics']['dropped'],drop)

    def test_five_manual(self):
        c=Config(n_edge=1,n_fog=1,n_cloud=1,buffer=2,n_tasks=5,mobile_fraction=0,
                 edge_fixed_ms=(2,2),edge_processing_share=.5,fog_service_ms=(10,10),
                 fog_cloud_ms=(1,1),cloud_service_ms=(1,1))
        a,_=self.same(c,[0,.001,.002,.003,.010])
        self.assertEqual([r.get('latency_ms') for r in a['tasks']],[14,23,32,None,34])

    def test_simultaneous_zero_services(self):
        self.same(Config(n_edge=1,n_fog=1,n_cloud=1,n_tasks=10,buffer=0,
                         mobile_fraction=0,edge_fixed_ms=(0,0),fog_service_ms=(0,0),
                         fog_cloud_ms=(0,0),cloud_service_ms=(0,0)),[0]*10)

    def test_45_paired_configurations_and_dropped_fields(self):
        for seed in (0,7,9):
            for f in (30,40,50,60,70):
                for B in (0,2,400):
                    with self.subTest(seed=seed,f=f,B=B):
                        a,b=self.same(Config(n_cloud=40,n_tasks=120,arrival_rate_s=.95*50/.055,
                                             n_fog=f,buffer=B,seed=seed))
                        for r in b['tasks']:
                            if r['status']=='dropped':
                                self.assertNotIn('latency_ms',r);self.assertIn('cloud_service_tick',r)

    def test_queue_switch_only_changes_trace(self):
        c=Config(n_tasks=300,arrival_rate_s=900,buffer=0)
        a,_=self.same(c)
        self.assertEqual(materialize_result(simulate(c,compact=True,record_queue=False)),{**a,'queue_trace':[]})

    def test_window_and_censoring(self):
        for guard in (.001,1):
            c=Config(n_cloud=40,arrival_rate_s=500)
            a,ar=stationary_run(c,.01,.2,guard,return_details=True)
            b,br=stationary_run(c,.01,.2,guard,return_details=True,compact=True)
            self.assertEqual(a,b);self.assertEqual(ar,materialize_result(br))

    def test_half_cohorts(self):
        from efc.statistics import extract_cohort
        c=Config(n_cloud=40,arrival_rate_s=500)
        a,x=stationary_run(c,1,5,2,return_details=True)
        b,y=stationary_run(c,1,5,2,return_details=True,compact=True,record_queue=False)
        lo,hi,stop=observation_window(c,1,5,2)
        for left,right in ((lo,hi),(lo,(lo+hi)//2),((lo+hi)//2,hi)):
            self.assertEqual(extract_cohort(42,x,(left,right,stop)),extract_cohort(42,y,(left,right,stop)))

    def test_missing_and_derived_fields(self):
        t=TaskColumns(2);t.append({'latency_tick':3,'mobile':True,'status':'pending'});t.append({'status':'dropped'})
        t.views={'latency_ms':('latency_tick',1_000_000)}
        self.assertEqual(t[0]['latency_ms'],.000003);self.assertNotIn('latency_ms',t[1])
        self.assertEqual(t[1].get('latency_ms'),None);self.assertIs(t[0]['mobile'],True)
        self.assertEqual(dict(t[1]),{'status':'dropped'})
        del t[0]['latency_tick'];self.assertNotIn('latency_ms',t[0])

    def test_capacity_and_types(self):
        t=TaskColumns(1);t.append({'status':'pending'})
        with self.assertRaises(ValueError):t.append({})
        for key,value in (('x_tick',-1),('x_tick',2**63),('x_tick',1.5),('mobile',1),('observed_rate_s',float('nan'))):
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):t[0][key]=value
        with self.assertRaises(IndexError):t[1]
        with self.assertRaises(ValueError):simulate(Config(n_tasks=0),compact=1)

    def test_identity_includes_storage_source(self):
        from unittest.mock import patch
        from efc.pilot import KernelSampler
        from pathlib import Path
        original=Path.read_bytes;a=KernelSampler(Config()).config_id
        def changed(p):return b'altered adapter' if p.name=='records.py' else original(p)
        with patch.object(Path,'read_bytes',changed):self.assertNotEqual(a,KernelSampler(Config()).config_id)
