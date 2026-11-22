"""Controller state oracles on supplied synthetic observations, not grid runs."""
from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
from efc.statistics import Cohort, PILOT_SEEDS, MAIN_SEEDS, CONFIRM_SEEDS
from efc.pilot import Observation, select_windows, run_frozen


class FakeSampler:
    config_id='synthetic-controller-oracle'
    def __init__(self, mode='stable'):self.mode=mode;self.calls=[]
    def __call__(self, seed, warm, observe, guard):
        self.calls.append((seed,warm,observe,guard))
        if self.mode=='exception' and seed==102:raise RuntimeError('injected failure')
        lost=1 if self.mode!='zero' else 0
        pending=int(self.mode in ('tail','tail_limit') and (guard<2000 or self.mode=='tail_limit'))
        delay=100_000_000 if self.mode!='warmup' or warm>=8000 else warm*100_000
        a=Cohort(seed,1000,lost,pending,(delay,)*(1000-lost-pending))
        b=Cohort(seed,1000,lost,0,(delay,)*(1000-lost))
        if self.mode=='precision' and observe==4000:
            n=1 if seed<105 else 5
            a=Cohort(seed,1000,n,0,(delay,)*(1000-n))
            b=a
        return Observation(Cohort(seed,a.arrivals+b.arrivals,a.dropped+b.dropped,a.unfinished+b.unfinished,
                                   a.latency_ticks+b.latency_ticks),a,b,{'config_id':self.config_id})


class PilotTests(unittest.TestCase):
    def test_freezes_longer_warmup_and_disjoint_seeds(self):
        s=FakeSampler();r=select_windows(s,repeats=10000)
        self.assertEqual(r['status'],'READY');self.assertEqual(r['plan']['warmup'],4000)
        self.assertEqual({x[0] for x in s.calls},set(PILOT_SEEDS))
        self.assertFalse(set(PILOT_SEEDS)&set(MAIN_SEEDS));self.assertFalse(set(MAIN_SEEDS)&set(CONFIRM_SEEDS))

    def test_equivalence_requires_larger_warmup(self):
        s=FakeSampler('warmup');r=select_windows(s,repeats=10000)
        self.assertEqual(r['plan']['warmup'],16000)
        self.assertEqual(len(s.calls),len(set(s.calls))) # reuse identical cached pilot cases

    def test_precision_increases_observation_only(self):
        r=select_windows(FakeSampler('precision'),repeats=10000)
        self.assertEqual((r['status'],r['plan']['observe']),('READY',8000))
        self.assertIn('increase_observation',[d['action'] for d in r['decisions']])

    def test_guard_extends_and_records_reason(self):
        r=select_windows(FakeSampler('tail'),repeats=10000)
        self.assertEqual(r['plan']['guard'],2000)
        self.assertIn('extend_guard',[d['action'] for d in r['decisions']])

    def test_guard_limit_unknown(self):
        r=select_windows(FakeSampler('tail_limit'),repeats=10000)
        self.assertEqual(r['status'],'INSUFFICIENT_DATA');self.assertIsNone(r['plan'])
        self.assertEqual(r['decisions'][-1]['action'],'stop_guard_limit')

    def test_zero_losses_never_ready(self):
        r=select_windows(FakeSampler('zero'),repeats=10000)
        self.assertEqual(r['status'],'INSUFFICIENT_DATA');self.assertEqual(r['decisions'][-1]['action'],'stop_precision_limit')

    def test_partial_progress_survives_exception(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pilot.json'
            with self.assertRaises(RuntimeError):select_windows(FakeSampler('exception'),journal=p,repeats=10000)
            r=json.loads(p.read_text());self.assertEqual(r['status'],'FAILED');self.assertEqual(len(r['runs']),2)

    def test_frozen_main_and_confirmation_no_adaptation(self):
        s=FakeSampler();r=select_windows(s,repeats=10000);s.calls.clear()
        with tempfile.TemporaryDirectory() as d:
            a=run_frozen(s,r,'main',journal=Path(d)/'main.json')
            b=run_frozen(s,r,'confirmation',journal=Path(d)/'confirmation.json')
            self.assertEqual(a['summary']['seed_ids'],list(MAIN_SEEDS))
            self.assertEqual(b['summary']['seed_ids'],list(CONFIRM_SEEDS))
            self.assertEqual({x[1:3] for x in s.calls},{(4000,4000)})
            with self.assertRaises(FileExistsError):run_frozen(s,r,'confirmation',journal=Path(d)/'confirmation.json')

    def test_frozen_failure_does_not_search_or_extend_measurement(self):
        s=FakeSampler();r=select_windows(s,repeats=10000);s.mode='zero';s.calls.clear()
        with tempfile.TemporaryDirectory() as d:
            got=run_frozen(s,r,'main',journal=Path(d)/'main.json')
            self.assertEqual(got['status'],'INSUFFICIENT_DATA');self.assertEqual(len(s.calls),10)
            self.assertEqual({x[1:3] for x in s.calls},{(4000,4000)})

    def test_changed_plan_is_rejected(self):
        s=FakeSampler();r=select_windows(s,repeats=10000);r['plan']['observe']*=2
        with tempfile.TemporaryDirectory() as d,self.assertRaises(ValueError):run_frozen(s,r,'main',journal=Path(d)/'x')

    def test_wrong_config_is_rejected(self):
        s=FakeSampler();r=select_windows(s,repeats=10000);s.config_id='other'
        with tempfile.TemporaryDirectory() as d,self.assertRaises(ValueError):run_frozen(s,r,'main',journal=Path(d)/'x')

    def test_inconsistent_half_windows_rejected(self):
        a=Cohort(100,1,0,0,(1,))
        with self.assertRaises(ValueError):Observation(a,a,a,{})
