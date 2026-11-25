"""Display regressions, including a synthetic version of the zero-loss shape."""
import copy
import unittest
from unittest.mock import patch
import matplotlib.pyplot as plt
from efc import companion as c
from efc.curve_annotations import ZERO_NOTE
from test_companion_selection import snapshot


class CurveIntervalTests(unittest.TestCase):
    def tearDown(self): plt.close('all')
    def test_zero_point_and_raw_bounds_preserved(self):
        s = snapshot(); before = copy.deepcopy(s)
        p, = c.curve_points(s, 'drop_fraction', 30, 5)
        self.assertEqual((p['value'], p['lower'], p['upper']), (0, 0, 0))
        self.assertEqual(p['interval_note'], ZERO_NOTE)
        self.assertFalse(p['interval_drawn']); self.assertEqual(s, before)
    def test_zero_flag_derived_even_if_reason_missing(self):
        s = snapshot(); s['rows'][0]['summary']['reasons'] = []
        self.assertFalse(c.curve_points(s, 'drop_fraction', 30, 5)[0]['interval_drawn'])
    def test_degenerate_loss_is_not_interval_line(self):
        fig = c.curve_figure(snapshot(), 'drop_fraction', 30, 5)
        self.assertEqual([l.get_gid() for l in fig.axes[0].lines], ['saved-estimate'])
        self.assertEqual(list(fig.axes[0].lines[0].get_ydata()), [0])
    def test_warning_is_in_figure_and_refers_to_point(self):
        fig = c.curve_figure(snapshot(), 'drop_fraction', 30, 5)
        text = '\n'.join(t.get_text() for t in fig.texts)
        for word in ('ρ50=0.1', 'нулевые наблюдённые потери', 'вырожденный bootstrap', 'риск ≤0,1% не подтверждён'):
            self.assertIn(word, text)
        self.assertIn('†', '\n'.join(t.get_text() for t in fig.axes[0].texts))
    def test_p95_unchanged_by_loss_flag(self):
        p, = c.curve_points(snapshot(), 'p95_ms', 30, 5)
        self.assertTrue(p['interval_drawn'])
        fig = c.curve_figure(snapshot(), 'p95_ms', 30, 5)
        self.assertEqual([l.get_gid() for l in fig.axes[0].lines], ['saved-interval', 'saved-estimate'])
        self.assertEqual(fig.texts, [])
    def test_positive_nondegenerate_loss_has_nominal_interval(self):
        s = snapshot(); q = s['rows'][0]['summary']; q['reasons'] = []
        q['point']['drop_fraction'] = .0005
        q['intervals']['drop_fraction'] = dict(lower=.0002, upper=.0008)
        fig = c.curve_figure(s, 'drop_fraction', 30, 5)
        self.assertEqual(list(fig.axes[0].lines[0].get_ydata()), [.02, .08])
        self.assertIn('номинальный', fig.axes[0].lines[0].get_label())
    def test_generic_degenerate_not_promoted(self):
        s = snapshot(); q = s['rows'][0]['summary']; q['reasons'] = []
        q['point']['drop_fraction'] = .2
        q['intervals']['drop_fraction'] = dict(lower=.2, upper=.2)
        p, = c.curve_points(s, 'drop_fraction', 30, 5)
        self.assertEqual(p['interval_state'], 'DEGENERATE_SAVED_INTERVAL')
    def test_no_fabricated_upper_bound(self):
        with patch('efc.statistics.classify', side_effect=AssertionError('do not reclassify')):
            p, = c.curve_points(snapshot(), 'drop_fraction', 30, 5)
            self.assertEqual(p['upper'], 0)
    def test_missing_interval_is_still_missing(self):
        s = snapshot(); s['rows'][0]['summary']['intervals']['drop_fraction'] = None
        self.assertEqual(c.curve_points(s, 'drop_fraction', 30, 5), [])
    def test_empty_selected_curve_does_not_draw_zero(self):
        fig = c.curve_figure(snapshot(), 'drop_fraction', 50, 5)
        self.assertEqual(len(fig.axes[0].lines), 0)
        self.assertIn('точек: 0', fig.axes[0].get_title())
    def test_multiple_zero_points_are_identified(self):
        s = snapshot(); row = copy.deepcopy(s['rows'][0]); row['arrival_rate_s'] *= 2; s['rows'].append(row)
        fig = c.curve_figure(s, 'drop_fraction', 30, 5)
        self.assertIn('ρ50=0.1, 0.2', '\n'.join(t.get_text() for t in fig.texts))
        self.assertEqual(len(fig.axes[0].lines), 2)

if __name__ == '__main__': unittest.main()
