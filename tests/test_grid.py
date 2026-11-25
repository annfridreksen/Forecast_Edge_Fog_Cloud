"""Persistent attempts and global candidate freeze: small synthetic oracles."""
from dataclasses import replace
from pathlib import Path
import gzip
import json
import tempfile
import unittest
from unittest.mock import patch

from efc.model import Config
from efc.grid import (CachedSampler, GridRunner, BudgetStop, ResourceStop, exclusive,
                      digest, freeze_candidates, read_json, atomic_json)
from efc.pilot import Observation, select_windows, run_frozen
from efc.statistics import Cohort


class FixtureSampler:
    calls = []
    fail_seed = None
    bad_confirmation = False

    def __init__(self, config):
        self.config = config
        self.config_id = f'FIXTURE-F{config.n_fog}-B{config.buffer}'

    def __call__(self, seed, warm, observe, guard):
        type(self).calls.append((self.config_id, seed, warm, observe, guard))
        if seed == type(self).fail_seed:
            raise RuntimeError('injected stop')
        lost = 3 if self.config.buffer == 0 else 1
        tick = 300_000_000 if seed >= 200 and type(self).bad_confirmation else 100_000_000
        half = Cohort(seed, 1000, lost, 0, (tick,)*(1000-lost))
        full = Cohort(seed, 2000, 2*lost, 0, half.latency_ticks*2)
        return Observation(full, half, half, {'config_id':self.config_id})


class GridTests(unittest.TestCase):
    def setUp(self):
        FixtureSampler.calls=[];FixtureSampler.fail_seed=None;FixtureSampler.bad_confirmation=False
        self.config=Config(n_cloud=40,n_fog=30,buffer=2,arrival_rate_s=.1*50/.055)

    def test_disk_cache_reuses_exact_observation(self):
        with tempfile.TemporaryDirectory() as d:
            sample=FixtureSampler(self.config)
            c=CachedSampler(sample,d)
            first=c(100,2000,4000,1000)
            other=CachedSampler(FixtureSampler(self.config),d)
            self.assertEqual(first,other(100,2000,4000,1000))
            self.assertEqual((c.new_runs,other.new_runs,other.reused_runs),(1,0,1))
            self.assertEqual(len(FixtureSampler.calls),1)

    def test_corruption_not_silently_recomputed(self):
        with tempfile.TemporaryDirectory() as d:
            c=CachedSampler(FixtureSampler(self.config),d);c(100,2000,4000,1000)
            p=next(Path(d).rglob('*.json.gz'))
            data=json.loads(gzip.decompress(p.read_bytes()))
            data['observation']['full']['dropped']+=1
            p.write_bytes(gzip.compress(json.dumps(data).encode()))
            with self.assertRaises(ValueError):c(100,2000,4000,1000)
            self.assertEqual(len(FixtureSampler.calls),1)

    def test_resource_ceiling_does_not_shorten_windows(self):
        with tempfile.TemporaryDirectory() as d:
            c=CachedSampler(FixtureSampler(self.config),d,max_expected_events=350000)
            with self.assertRaises(ResourceStop):c(100,4000,4000,1000)
            self.assertEqual(FixtureSampler.calls,[])

    def test_cached_data_accessible_after_budget(self):
        with tempfile.TemporaryDirectory() as d:
            c=CachedSampler(FixtureSampler(self.config),d);x=c(100,2000,4000,1000)
            paused=CachedSampler(FixtureSampler(self.config),d,deadline=0)
            self.assertEqual(paused(100,2000,4000,1000),x)
            with self.assertRaises(BudgetStop):paused(101,2000,4000,1000)

    def test_frozen_resume_only_unfinished_samples(self):
        with tempfile.TemporaryDirectory() as d:
            sample=FixtureSampler(self.config);cache=CachedSampler(sample,d)
            selection=select_windows(cache)
            FixtureSampler.calls=[]
            FixtureSampler.fail_seed=5
            path=Path(d)/'main.json'
            with self.assertRaises(RuntimeError):run_frozen(cache,selection,'main',journal=path)
            FixtureSampler.fail_seed=None
            before=len(FixtureSampler.calls)
            answer=run_frozen(cache,selection,'main',journal=path,resume=True)
            self.assertEqual(answer['status'],'ACCEPTABLE')
            new=FixtureSampler.calls[before:]
            self.assertEqual([x[1] for x in new],list(range(5,10)))
            count=len(FixtureSampler.calls)
            self.assertEqual(run_frozen(cache,selection,'main',journal=path,resume=True),answer)
            self.assertEqual(len(FixtureSampler.calls),count)
            with self.assertRaises(FileExistsError):run_frozen(cache,selection,'main',journal=path)

    def test_frozen_resume_cannot_change_phase(self):
        with tempfile.TemporaryDirectory() as d:
            c=CachedSampler(FixtureSampler(self.config),d);s=select_windows(c);p=Path(d)/'x.json'
            run_frozen(c,s,'main',journal=p)
            with self.assertRaises(ValueError):run_frozen(c,s,'confirmation',journal=p,resume=True)

    def test_process_lock_rejects_second_writer(self):
        with tempfile.TemporaryDirectory() as d:
            with exclusive(d):
                with self.assertRaises(RuntimeError):
                    with exclusive(d):pass

    def test_small_map_reuses_completed_cells_after_restart(self):
        configs=[replace(self.config,buffer=0),self.config]
        with tempfile.TemporaryDirectory() as d:
            x=GridRunner(d,configurations=configs,factory=FixtureSampler).run()
            self.assertEqual(x['cells_with_10_main_seeds'],2)
            self.assertTrue(x['all_main_complete'])
            count=len(FixtureSampler.calls)
            y=GridRunner(d,configurations=configs,factory=FixtureSampler).run()
            self.assertEqual(len(FixtureSampler.calls),count)
            self.assertEqual(y['new_replications'],0)
            self.assertEqual(read_json(Path(d)/'map.json')['scope'],'small controller fixture')

    def test_all_candidates_frozen_before_confirmation(self):
        configs=[replace(self.config,buffer=0),self.config]
        with tempfile.TemporaryDirectory() as d:
            GridRunner(d,configurations=configs,factory=FixtureSampler).run()
            reg=read_json(Path(d)/'candidates.json')
            self.assertEqual(reg['candidates'][0]['key'],'r0.10_F30_B002')
            self.assertFalse(any(x[1]>=200 for x in FixtureSampler.calls))
            class WatchSampler(FixtureSampler):
                def __call__(self,*args):
                    if args[0]>=200:
                        assert Path(d,'candidates.json').exists()
                    return super().__call__(*args)
            GridRunner(d,configurations=configs,factory=WatchSampler).run(confirm=True)
            self.assertEqual(read_json(Path(d)/'cells/r0.10_F30_B002/confirmation.json')['summary']['seed_ids'],
                             list(range(200,210)))

    def test_failed_confirmation_does_not_pick_next_candidate(self):
        configs=[self.config,replace(self.config,n_fog=40)]
        with tempfile.TemporaryDirectory() as d:
            FixtureSampler.bad_confirmation=True
            GridRunner(d,configurations=configs,factory=FixtureSampler).run(confirm=True)
            reg=Path(d)/'candidates.json';before=reg.read_bytes()
            self.assertEqual(read_json(Path(d)/'cells/r0.10_F30_B002/confirmation.json')['status'],'UNACCEPTABLE')
            n=len(FixtureSampler.calls)
            GridRunner(d,configurations=configs,factory=FixtureSampler).run(confirm=True)
            self.assertEqual(reg.read_bytes(),before)
            self.assertEqual(len(FixtureSampler.calls),n)
            self.assertFalse((Path(d)/'cells/r0.10_F40_B002/confirmation.json').exists())

    def test_incompatible_configuration_blocks_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            GridRunner(d,configurations=[self.config],factory=FixtureSampler).run()
            with self.assertRaises(ValueError):
                GridRunner(d,configurations=[replace(self.config,buffer=5)],factory=FixtureSampler).run()

    def test_incomplete_map_not_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            r=GridRunner(d,configurations=[self.config],factory=FixtureSampler,wall_seconds=0)
            x=r.run()
            self.assertEqual(x['cells_with_10_main_seeds'],0)
            self.assertFalse(Path(d,'candidates.json').exists())
            self.assertEqual(read_json(Path(d)/'map.json')['rows'][0]['status'],'NOT_CALCULATED')

    def test_resume_pilot_reuses_completed_replications(self):
        with tempfile.TemporaryDirectory() as d:
            FixtureSampler.fail_seed=103
            GridRunner(d,configurations=[self.config],factory=FixtureSampler).run()
            FixtureSampler.fail_seed=None
            before=len(FixtureSampler.calls)
            GridRunner(d,configurations=[self.config],factory=FixtureSampler).run()
            new=FixtureSampler.calls[before:]
            self.assertNotIn((FixtureSampler(self.config).config_id,100,2000,4000,1000),new)
            self.assertTrue(list(Path(d).glob('cells/*/history/pilot-*.json')))

    def test_map_tampering_after_freeze_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=GridRunner(d,configurations=[self.config],factory=FixtureSampler);r.run()
            data=read_json(Path(d)/'map.json');data['rows'][0]['buffer']=5
            with self.assertRaises(ValueError):freeze_candidates(d,r.catalog,data)

    def test_no_confirmation_when_no_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            c=replace(self.config,buffer=0)
            GridRunner(d,configurations=[c],factory=FixtureSampler).run(confirm=True)
            self.assertIsNone(read_json(Path(d)/'candidates.json')['candidates'][0]['key'])
            self.assertFalse(any(x[1]>=200 for x in FixtureSampler.calls))
