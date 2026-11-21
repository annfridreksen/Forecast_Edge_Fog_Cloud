"""Targeted regression tests requested by the second review."""
import copy
import contextlib
import csv
from dataclasses import replace
from fractions import Fraction as F
import hashlib
import importlib.util
import inspect
import io
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from bt26 import make_model, search, reference, prepare_forecast, verify_plan, reconsider
from bt26.scheduler import build_plan, NoSchedule, Hop
from bt26.search import command_vector, optimistic_bound
from run_study import synthetic, study, StudyVerificationError
from run_review_checks import check_stop_coverage

ROOT = Path(__file__).resolve().parents[1]


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT/'examples/minimal.json').read_text())
        self.forecast = json.loads((ROOT/'examples/forecast.json').read_text())
        self.model = make_model(self.data)
        self.plan = search(self.model, self.forecast).plan

    def test_requested_effective_seed20(self):
        counts = []
        for seed in range(60):
            d, f, _ = synthetic(seed)
            r = search(make_model(d), f)
            counts.append(r.method)
            self.assertEqual(r.to_dict()['requested_method'], 'P')
            if seed == 20:
                self.assertEqual((r.method, r.forecast_status), ('B', 'constant'))
                self.assertEqual(r.stats['complete_checked'], 78)
        self.assertEqual(counts.count('P'), 59)

    def test_manual_eight_rows(self):
        # Hand calculation; no reference(), key() or optimistic-bound oracle.
        expected = {'EEE': ((1,1,1), None), 'EEF': ((2,1,1), None),
                    'EFE': ((2,1,1), 8), 'EFF': ((2,2,1), 6),
                    'FEE': ((2,1,1), 9), 'FEF': ((2,2,1), 9),
                    'FFE': ((2,2,1), 6), 'FFF': ((2,2,2), 4)}
        commands = {'E': F(1), 'F': F(2)}
        for name, (vector, duration) in expected.items():
            with self.subTest(assignment=name):
                a = dict(zip(self.model.blocks, name))
                self.assertEqual(command_vector(a, commands), vector)
                if duration is None:
                    with self.assertRaises(NoSchedule):
                        build_plan(self.model, a)
                else:
                    p = build_plan(self.model, a)
                    self.assertEqual(p.makespan, F(duration, 1000))
                    self.assertEqual(verify_plan(self.model, p), ())

    def test_strict_bound_mutation_is_detected(self):
        # EFE is visited first with 8 ms; the equal-R FEE has 6 ms here.
        self.data['operations'][2]['duration_s']['E'] = '0.002'
        m = make_model(self.data)
        correct = search(m, self.forecast)
        self.assertEqual(correct.plan.identifier, ('F','E','E'))
        self.assertEqual(correct.plan.makespan, F(6,1000))
        source = (ROOT/'bt26/search.py').read_text()
        needle = 'frontier[0][0] > key(model, best, commands)[0]'
        self.assertEqual(source.count(needle), 1)
        mutant = types.ModuleType('bt26._test_mutant')
        mutant.__package__ = 'bt26'
        sys.modules[mutant.__name__] = mutant
        try:
            exec(compile(source.replace(needle, needle.replace(' > ', ' >= ')),
                         '<mutated-search>', 'exec'), mutant.__dict__)
            wrong = mutant.search(m, self.forecast)
            self.assertNotEqual(wrong.plan, correct.plan)
            self.assertEqual(wrong.plan.identifier, ('E','F','E'))
        finally:
            sys.modules.pop(mutant.__name__, None)

    def test_stop_frontier_and_active_deadlines(self):
        rejected = 0
        for deadline in ('0.060', '0.030', '0.035'):
            for seed in range(80):
                d, f, _ = synthetic(seed)
                d['deadline_s'] = deadline
                m = make_model(d)
                audit = {}
                result = search(m, f, audit=audit)
                self.assertEqual(check_stop_coverage(m, f, result, audit), [])
                oracle, _, _ = reference(m, f)
                self.assertEqual(result.plan, oracle)
                rejected += result.rejected.get('deadline', 0)
        self.assertGreater(rejected, 0)

    def test_wall_clock_fields(self):
        result = search(self.model, self.forecast)
        for field in ('elapsed_wall_seconds', 'schedule_wall_seconds',
                      'verify_wall_seconds', 'preparation_and_search_wall_seconds'):
            self.assertGreaterEqual(result.stats[field], 0)
        self.assertNotIn('cpu_seconds', result.stats)

    def test_bound_precomputed_equals_public_convenience(self):
        c, _ = prepare_forecast(self.model, self.forecast)
        minimum = tuple(min(c[d] for d in self.model.candidates[b]) for b in self.model.blocks)
        for values in product('EF', repeat=3):
            for length in range(4):
                self.assertEqual(optimistic_bound(self.model,c,values[:length]),
                                 optimistic_bound(self.model,c,values[:length],minimum))

    def test_source_duration_corruption(self):
        durations = dict(self.model.duration)
        durations['A','E'] = F(9,1000)
        corrupted = replace(self.model, duration=durations)
        self.assertIn('model_aggregate:duration', verify_plan(corrupted, self.plan))

    def test_source_memory_corruption(self):
        corrupted = replace(self.model, memory={**self.model.memory, 'A': 1})
        self.assertIn('model_aggregate:memory', verify_plan(corrupted, self.plan))

    def test_source_messages_corruption(self):
        corrupted = replace(self.model, messages={**self.model.messages, ('A','B'): 0})
        self.assertIn('model_aggregate:messages', verify_plan(corrupted, self.plan))

    def test_source_candidates_corruption(self):
        corrupted = replace(self.model, candidates={**self.model.candidates, 'A': ('F',)})
        self.assertIn('model_aggregate:candidates', verify_plan(corrupted, self.plan))

    def test_raw_rational_integer_memory_supported(self):
        self.data['operations'][0]['memory_bytes'] = '1000000/1'
        m = make_model(self.data)
        p = build_plan(m, {'A':'E','B':'F','C':'E'})
        self.assertEqual(verify_plan(m,p), ())

    def _first_hop(self, **kwargs):
        t = self.plan.transfers[0]
        changed = replace(t, hops=(replace(t.hops[0], **kwargs),)+t.hops[1:])
        return replace(self.plan, transfers=(changed,)+self.plan.transfers[1:])

    def test_serialization_duration_code(self):
        p = self._first_hop(end=self.plan.transfers[0].hops[0].end+F(1,1000))
        self.assertIn('serialization_duration', verify_plan(self.model,p))

    def test_propagation_delay_code(self):
        p = self._first_hop(arrival=self.plan.transfers[0].hops[0].arrival+F(1,1000))
        self.assertIn('propagation_delay', verify_plan(self.model,p))

    def test_release_code(self):
        run = self.plan.runs[0]
        p = replace(self.plan, runs=(replace(run,start=-F(1,1000),end=run.end-F(1,1000)),)+self.plan.runs[1:])
        self.assertIn('release:A', verify_plan(self.model,p))

    def test_cyclic_route_code(self):
        t = self.plan.transfers[0]
        h0 = t.hops[0]
        h1 = Hop('FE', h0.arrival, h0.arrival+F(1,1000),h0.arrival+F(1,1000))
        h2 = Hop('EF', h1.arrival,h1.arrival+F(1,1000),h1.arrival+F(1,1000))
        changed = replace(t,hops=(h0,h1,h2),arrival=h2.arrival)
        p = replace(self.plan,transfers=(changed,)+self.plan.transfers[1:])
        self.assertIn('cyclic_route', verify_plan(self.model,p))

    def test_message_size_code(self):
        t = replace(self.plan.transfers[0], bits=1)
        p = replace(self.plan,transfers=(t,)+self.plan.transfers[1:])
        self.assertIn('message_size:A->B',verify_plan(self.model,p))

    def test_nonempty_local_route_code(self):
        p = build_plan(self.model,dict.fromkeys(self.model.blocks,'F'))
        t = replace(p.transfers[0],hops=(Hop('FE',F(1,1000),F(2,1000),F(2,1000)),),arrival=F(2,1000))
        self.assertIn('nonempty_local_route',verify_plan(self.model,replace(p,transfers=(t,)+p.transfers[1:])))

    def test_makespan_mismatch_code(self):
        self.assertIn('makespan_mismatch',verify_plan(self.model,replace(self.plan,makespan=F(0))))

    def test_single_relevant_device_and_memory_reason(self):
        d=json.loads((ROOT/'examples/failed_node.json').read_text())
        r=search(make_model(d),self.forecast)
        self.assertEqual(r.forecast_status,'single_relevant_device')
        self.assertEqual(r.status,'NO_PLAN_IN_CLASS')
        self.assertGreater(r.to_dict()['partial_rejections']['joint_memory'],0)
        self.assertEqual(r.rejected,{})  # no complete assignment was checked

    def test_optional_first_forecast_is_named(self):
        r=reconsider(self.model,self.model.previous,self.forecast,allow_preference_change=True)
        self.assertEqual(r['reason'],'forecast_became_available')
        self.assertEqual(r['action'],'RESELECT')

    def test_mismatch_written_before_failure(self):
        real_reference = reference
        def faulty_reference(*args,**kwargs):
            p,n,k=real_reference(*args,**kwargs)
            return None,n,k  # deliberate differential-test failure
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            with patch('run_study.reference',side_effect=faulty_reference),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(StudyVerificationError):
                    study(1,out)
            rows=list(csv.DictReader((out/'reference_comparison.csv').open()))
            self.assertTrue(rows)
            self.assertTrue(all(x['matches_reference']=='False' for x in rows))
            self.assertFalse(json.loads((out/'summary.json').read_text())['all_comparisons_match'])

    def test_declared_scale_mismatch_falls_back(self):
        self.data['expected_forecast_scale_id']=self.forecast['scale_id']
        m=make_model(self.data)
        f=copy.deepcopy(self.forecast);f['scale_id']='different'
        r=search(m,f)
        self.assertEqual((r.method,r.forecast_status),('B','scale_mismatch'))
        self.assertEqual(r.plan,search(m,None,'B').plan)

    def test_no_declared_scale_is_presence_only(self):
        f=copy.deepcopy(self.forecast);f['scale_id']='new-explicit-nonempty-label'
        self.assertEqual(search(self.model,f).method,'P')

    def test_cli_deterministic_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs=[Path(tmp)/'a.json',Path(tmp)/'b.json']
            for output in outputs:
                subprocess.run([sys.executable,'-m','bt26','examples/minimal.json','--forecast',
                    'examples/forecast.json','--output',str(output),'--deterministic-output'],
                    cwd=ROOT,check=True,capture_output=True)
            self.assertEqual(outputs[0].read_bytes(),outputs[1].read_bytes())
            self.assertNotIn('elapsed_wall_seconds',json.loads(outputs[0].read_text())['stats'])

    def test_budget_audit_preserves_popped_completion(self):
        audit={}
        r=search(self.model,self.forecast,max_checks=0,audit=audit)
        self.assertEqual(check_stop_coverage(self.model,self.forecast,r,audit),[])


if __name__=='__main__':
    unittest.main()
