"""Small read-only and disabled-port oracles, never scientific replications."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_dashboard as fixtures
from efc import companion as c
from efc.grid import atomic_json

ROOT = Path(__file__).resolve().parents[1]


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.DashboardTests(); self.fx.setUp()
        self.root = self.fx.root
    def tearDown(self): self.fx.tearDown()
    def test_absent_archive_no_fake_rows_or_files(self):
        self.assertEqual(c.overview(self.root)['state'], 'NO_CHECKPOINT')
        self.assertEqual(list(self.root.iterdir()), [])
    def test_corrupt_archive_gives_no_numbers(self):
        m = self.fx.fixture(); m['manifest_sha256'] = 'wrong'
        atomic_json(self.root/'map.json', m)
        s = c.overview(self.root)
        self.assertEqual(s['state'], 'ARCHIVE_UNVERIFIED'); self.assertEqual(s['rows'], [])
    def test_valid_archive_no_simulation_no_mutation(self):
        self.fx.fixture()
        before = {p: p.read_bytes() for p in self.root.rglob('*.json')}
        with patch('efc.model.simulate', side_effect=AssertionError('forbidden')):
            with patch('efc.grid.GridRunner.run', side_effect=AssertionError('forbidden')):
                s = c.overview(self.root)
        self.assertEqual(s['counts'], {'NOT_CALCULATED': 1})
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*.json')})
    def test_unproved_acceptable_cannot_make_curve(self):
        m = self.fx.fixture(); m['rows'][0]['status'] = 'ACCEPTABLE'; atomic_json(self.root/'map.json', m)
        self.assertEqual(c.curve_points(c.overview(self.root), 'p95_ms', 50, 5), [])
    def test_saved_main_points_have_file_and_hash(self):
        self.fx.terminal_fixture(); s = c.overview(self.root)
        p = c.curve_points(s, 'p95_ms', 50, 5)
        self.assertEqual(len(p), 1); self.assertTrue(p[0]['source'].endswith('/main.json'))
        self.assertEqual(len(p[0]['sha256']), 64)
    def test_no_interval_no_point(self):
        self.fx.terminal_fixture(); s = c.overview(self.root)
        s['rows'][0]['summary']['intervals']['p95_ms'] = None
        self.assertEqual(c.curve_points(s, 'p95_ms', 50, 5), [])
    def test_no_main_proof_no_point(self):
        self.fx.terminal_fixture(); s = c.overview(self.root); s['rows'][0].pop('main_sha256')
        self.assertEqual(c.curve_points(s, 'p95_ms', 50, 5), [])
    def test_nonfinite_or_impossible_loss_rejected(self):
        self.fx.terminal_fixture(); s = c.overview(self.root)
        for value in (float('nan'), True, -1, 2):
            changed = copy.deepcopy(s); changed['rows'][0]['summary']['point']['drop_fraction'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.curve_points(changed, 'drop_fraction', 50, 5)
    def test_unknown_metric_rejected(self):
        with self.assertRaises(ValueError): c.curve_points(c.overview(self.root), 'probability', 50, 5)
    def test_empty_curve_explicit_not_zero(self):
        import matplotlib.pyplot as plt
        fig = c.curve_figure(c.overview(self.root), 'p95_ms')
        self.assertEqual(len(fig.axes[0].lines), 0)
        self.assertIn('Нет итоговых', fig.axes[0].texts[0].get_text()); plt.close(fig)
    def test_ports_have_no_estimates(self):
        ports = c.port_contracts()
        self.assertEqual(len({p['id'] for p in ports}), 3)
        self.assertTrue(all(p['estimate'] is None and p['status'] == 'NOT_IMPLEMENTED' for p in ports))
        ports[0]['estimate'] = 10
        self.assertIsNone(c.port_contracts()[0]['estimate'])
    def test_all_port_calls_blocked(self):
        for p in c.port_contracts():
            with self.subTest(port=p['id']), self.assertRaises(NotImplementedError): c.invoke_port(p['id'], {})
        with self.assertRaises(ValueError): c.invoke_port('unknown', {})
    def test_symbolic_blocks_not_plan_validation(self):
        s = c.symbolic_placement(); self.assertTrue(c.check_symbolic(s))
        self.assertEqual(s['members']['A'], ('a1', 'a2')); self.assertFalse(s['plan_verified'])
    def test_independent_vertex_assignment_rejected(self):
        s = c.symbolic_placement(); s['after']['a1'] = 'E2'
        with self.assertRaises(ValueError): c.check_symbolic(s)
    def test_cloud_not_candidate(self):
        s = c.symbolic_placement(); s['candidates'] += ('Cloud',)
        with self.assertRaises(ValueError): c.check_symbolic(s)
    def test_false_execution_or_partition_claim_rejected(self):
        for name in ('partition_changed', 'plan_verified', 'controller_executed'):
            s = c.symbolic_placement(); s[name] = True
            with self.subTest(name=name), self.assertRaises(ValueError): c.check_symbolic(s)
    def test_exact_reference_read_not_executed(self):
        r = c.reference_fragments(ROOT)
        self.assertFalse(r['executed']); self.assertIn('reverse=True', r['fragments']['command_vector'])
        self.assertIn('plan.makespan, moves', r['fragments']['key'])
    def test_modified_reference_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td); (p/'v2/code/bt26').mkdir(parents=True)
            (p/'v2/MANIFEST.sha256').write_bytes((ROOT/'v2/MANIFEST.sha256').read_bytes())
            (p/'v2/code/bt26/search.py').write_text('changed')
            with self.assertRaises(ValueError): c.reference_fragments(p)
    def test_concept_diagrams_have_explicit_limits(self):
        import matplotlib.pyplot as plt
        for name, phrase in [('ports', 'НЕ РЕАЛИЗОВАН'), ('placement', 'НЕ КОНТРОЛЛЕР')]:
            fig = c.concept_figure(name)
            self.assertIn(phrase, '\n'.join(t.get_text() for t in fig.axes[0].texts)); plt.close(fig)
        with self.assertRaises(ValueError): c.concept_figure('actual_forecast')
    def test_notebook_code_no_old_execution_hooks(self):
        paths = sorted((ROOT/'colab').glob('0[123]_*.ipynb')); self.assertEqual(len(paths), 3)
        for path in paths:
            book = json.loads(path.read_text()); ids = [x['id'] for x in book['cells']]
            self.assertEqual(len(ids), len(set(ids)))
            for cell in book['cells']:
                if cell['cell_type'] != 'code': continue
                text = ''.join(cell['source'])
                self.assertEqual(cell['outputs'], [])
                for banned in ('efc.forecast', 'efc.placement', 'neural_placement', '.fit(', 'run_study', 'GridRunner(', 'simulate('):
                    self.assertNotIn(banned, text, path.name)
                ast.parse(text)

if __name__ == '__main__': unittest.main()
