"""Small source/adapter regressions, NOT the 270-configuration research series."""
from dataclasses import replace, FrozenInstanceError
import unittest
from unittest.mock import patch
from efc import model
from efc.model import Config, simulate, COMPONENTS
from efc.workload import generate_workload, Workload, source_signature, INPUT_FIELDS
from efc.stationary import stationary_run, observation_window, summarize_window, stationary_series, aggregate


class WorkloadTests(unittest.TestCase):
    def setUp(self):
        self.c = Config(n_cloud=40,n_tasks=120,arrival_rate_s=.95*50/.055,seed=7)

    def test_generator_independent_of_all_fog_buffer_pairs(self):
        w = generate_workload(self.c)
        for f in (30,40,50,60,70):
            for b in (0,2,5,10,20,50,100,200,400):
                with self.subTest(fog=f,buffer=b):
                    other=generate_workload(replace(self.c,n_fog=f,buffer=b))
                    self.assertEqual(w,other)
                    self.assertEqual(w.metadata(),other.metadata())

    def test_all_potential_fields_survive_drops(self):
        w=generate_workload(self.c); sources=[e.record() for e in w.events]
        outcomes=[]; loss_seen=False
        for f,b in ((30,0),(50,2),(70,400)):
            r=simulate(replace(self.c,n_fog=f,buffer=b),workload=w)
            self.assertEqual([{k:t[k] for k in INPUT_FIELDS} for t in r['tasks']],sources)
            self.assertTrue(all(t['fog']==t['sensor']%f for t in r['tasks']))
            for t in r['tasks']:
                if t['status']=='dropped':
                    loss_seen=True
                    self.assertIn('cloud_service_tick',t)
                    self.assertNotIn('latency_ms',t)
            outcomes.append([t['status'] for t in r['tasks']])
        self.assertTrue(loss_seen);self.assertNotEqual(outcomes[0],outcomes[-1])

    def test_cloud_count_is_not_a_source_parameter(self):
        self.assertEqual(generate_workload(self.c),generate_workload(replace(self.c,n_cloud=80)))

    def test_explicit_and_implicit_calls_match(self):
        self.assertEqual(simulate(self.c),simulate(self.c,workload=generate_workload(self.c)))

    def test_count_prefix_is_stable(self):
        a=generate_workload(self.c);b=generate_workload(replace(self.c,n_tasks=240))
        self.assertEqual(a.events,b.events[:120])

    def test_fixed_horizon_prefix_is_stable(self):
        a=generate_workload(self.c,stop_s='.2');b=generate_workload(self.c,stop_s='.4')
        self.assertGreater(len(b.events),len(a.events))
        self.assertEqual(a.events,b.events[:len(a.events)])
        self.assertTrue(all(e.release_tick<200_000_000 for e in a.events))

    def test_snapshot_is_immutable(self):
        w=generate_workload(self.c)
        with self.assertRaises(FrozenInstanceError):w.events[0].sensor=0
        with self.assertRaises(TypeError):w.events[0]=w.events[1]

    def test_source_changes_require_new_snapshot(self):
        w=generate_workload(self.c)
        for kw in ({'seed':8},{'n_edge':1100},{'arrival_rate_s':500},{'mobile_fraction':.1},
                   {'fog_service_ms':(20,40)}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                simulate(replace(self.c,**kw),workload=w)

    def test_no_ambiguous_input_mode(self):
        w=generate_workload(self.c)
        with self.assertRaises(ValueError):simulate(self.c,[0]*120,workload=w)
        with self.assertRaises(ValueError):generate_workload(self.c,[0]*120,stop_s=1)
        with self.assertRaises(ValueError):simulate(replace(self.c,n_tasks=119),workload=w)
        with self.assertRaises(ValueError):generate_workload(self.c,stop_s=0)

    def test_malformed_workload_is_not_silently_reassigned(self):
        w=generate_workload(self.c)
        for bad in (replace(w.events[0],event_id=2),replace(w.events[0],sensor=1000),
                    replace(w.events[0],release_tick=-1),replace(w.events[0],mobile=1),
                    replace(w.events[0],fog_service_tick=1.2)):
            with self.assertRaises(ValueError):simulate(self.c,workload=replace(w,events=(bad,)+w.events[1:]))
        with self.assertRaises(ValueError):simulate(self.c,workload=replace(w,events=list(w.events)))

    def test_legacy_zone_weights_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError,'uniform sensors'):
            generate_workload(replace(self.c,fog_weights=tuple([1]*50)))


class SharedKernelTests(unittest.TestCase):
    def manual(self):
        c=Config(n_edge=1,n_fog=1,n_cloud=1,buffer=2,n_tasks=5,arrival_rate_s=500,
                 mobile_fraction=0,edge_fixed_ms=(2,2),edge_processing_share=.5,
                 fog_service_ms=(10,10),fog_cloud_ms=(1,1),cloud_service_ms=(1,1))
        windows=observation_window(c,.01,.2,1)
        w=replace(generate_workload(c,['.001','.002','.003','.004','.011']),horizon_tick=windows[2])
        return c,w,windows

    def test_wrapper_calls_actual_kernel_and_matches_every_record(self):
        c,w,windows=self.manual(); direct=simulate(c,workload=w)
        with patch.object(model,'simulate',wraps=model.simulate) as called:
            row,through=stationary_run(c,.01,.2,1,workload=w,return_details=True)
        self.assertEqual(called.call_count,1)
        self.assertEqual(direct,through)
        self.assertEqual(row['p95_ms'],33.7)
        self.assertEqual(row['drop_fraction'],.2)
        self.assertEqual(row['H200'],.8)
        self.assertEqual((row['arrivals'],row['completed'],row['dropped'],row['unfinished']),(5,4,1,0))
        self.assertEqual([t.get('latency_ms') for t in through['tasks']],[14,23,32,None,34])
        self.assertAlmostEqual(row['fog_utilization'],.9)
        self.assertAlmostEqual(sum(row[k] for k in COMPONENTS),row['mean_ms'])

    def test_window_does_not_depend_on_selected_fog(self):
        c=Config(n_cloud=40,arrival_rate_s=500)
        windows=[observation_window(replace(c,n_fog=f),1,2,3) for f in (30,40,50,60,70)]
        self.assertTrue(all(w==windows[0] for w in windows))
        self.assertEqual(windows[0],(100_000_000,300_000_000,600_000_000))

    def test_window_runner_exposes_same_poisson_snapshot(self):
        c=Config(n_cloud=40,arrival_rate_s=300,n_tasks=1,seed=7)
        lo,hi,stop=observation_window(c,1,2,3)
        w=generate_workload(c,stop_s=stop/1_000_000_000)
        row,r=stationary_run(replace(c,n_fog=30,buffer=0),1,2,3,workload=w,return_details=True)
        direct=simulate(replace(c,n_fog=30,buffer=0,n_tasks=len(w.events)),workload=w)
        self.assertEqual(r,direct)
        self.assertEqual(row['workload_sha256'],w.metadata()['sha256'])
        self.assertEqual(row['statistical_acceptance'],'NOT_EVALUATED_SINGLE_REPLICATION')

    def test_insufficient_guard_cannot_certify_drained_cohort(self):
        c,w,_=self.manual(); short=observation_window(c,.01,.2,.001)
        w=replace(w,horizon_tick=short[2])
        row=stationary_run(c,.01,.2,.001,workload=w)
        self.assertGreater(row['unfinished'],0);self.assertFalse(row['cohort_complete'])
        self.assertIsNone(row['p95_ms']);self.assertIsNone(row['drop_fraction']);self.assertIsNone(row['H200'])
        self.assertEqual(row['arrivals'],row['completed']+row['dropped']+row['unfinished'])

    def test_different_horizon_not_silently_accepted(self):
        c,w,_=self.manual()
        with self.assertRaises(ValueError):stationary_run(c,.01,.2,2,workload=w)

    def test_half_open_external_cohort_not_downstream_arrivals(self):
        c,w,window=self.manual()
        r=simulate(c,workload=w)
        # Exactly .001 is included, exactly .011 is excluded here.
        row=summarize_window(c,r,(1_000_000,11_000_000,window[2]))
        self.assertEqual((row['arrivals'],row['completed'],row['dropped']),(4,3,1))

    def test_finite_fog_buffer_permits_offered_overload(self):
        c=Config(n_fog=30,n_cloud=40,arrival_rate_s=.95*50/.055,buffer=0)
        row=stationary_run(c,1,2,100)
        self.assertGreater(row['rho_target'],1);self.assertTrue(row['cohort_complete'])
        self.assertGreater(row['dropped'],0)

    def test_old_series_cannot_be_presented_as_r14_statistics(self):
        with self.assertRaises(NotImplementedError):stationary_series()
        with self.assertRaises(NotImplementedError):aggregate(None)
