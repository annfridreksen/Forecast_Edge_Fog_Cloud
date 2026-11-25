"""Synthetic display-only fixtures; actual checkpoint is checked separately."""
import copy
import unittest
from unittest.mock import patch
from efc.curve_selection import choose_curve, curve_title


def snapshot():
    def row(fog, buffer, rate=90.9090909090909):
        return dict(n_fog=fog, buffer=buffer, arrival_rate_s=rate,
                    key=f'F{fog}_B{buffer}', main_sha256='fixture-not-evidence',
                    summary=dict(point=dict(p95_ms=170.0, drop_fraction=0.0),
                        intervals=dict(p95_ms=dict(lower=169.0, upper=171.0),
                                       drop_fraction=dict(lower=0.0, upper=0.0)),
                        reasons=['zero_loss_degenerate_bootstrap']))
    return dict(state='CHECKED_CHAINS', rows=[row(30, 5)])


class CurveSelectionTests(unittest.TestCase):
    def test_first_existing_main_selected(self):
        s = choose_curve(snapshot())
        self.assertEqual((s['fog'], s['buffer']), (30, 5))
        self.assertEqual(s['counts'], dict(p95_ms=1, drop_fraction=1))
    def test_explicit_missing_combination_stays_empty(self):
        s = choose_curve(snapshot(), 50, 5)
        self.assertEqual(s['mode'], 'EXPLICIT')
        self.assertEqual(s['counts'], dict(p95_ms=0, drop_fraction=0))
    def test_title_contains_selection_and_count(self):
        title = curve_title(choose_curve(snapshot()), 'p95_ms')
        for text in ('Fog=30', 'B=5', 'точек: 1'): self.assertIn(text, title)
    def test_no_checkpoint_is_not_zero(self):
        s = choose_curve(dict(state='NO_CHECKPOINT', rows=[]))
        self.assertEqual(s['mode'], 'EMPTY_FALLBACK')
        self.assertEqual(s['available'], [])
        self.assertEqual(s['counts']['p95_ms'], 0)
    def test_unverified_snapshot_cannot_offer_data(self):
        s = snapshot(); s['state'] = 'ARCHIVE_UNVERIFIED'
        self.assertEqual(choose_curve(s)['available'], [])
    def test_main_without_estimates_not_auto_selected(self):
        s = snapshot(); s['rows'][0]['summary']['intervals'] = {}
        self.assertEqual(choose_curve(s)['mode'], 'EMPTY_FALLBACK')
    def test_pilot_not_used_as_main(self):
        s = snapshot(); s['rows'][0].pop('main_sha256')
        self.assertEqual(choose_curve(s)['available'], [])
    def test_deterministic_default_not_mutating(self):
        s = snapshot(); other = copy.deepcopy(s['rows'][0]); other['n_fog'] = 70
        s['rows'].insert(0, other); before = copy.deepcopy(s)
        self.assertEqual(choose_curve(s)['fog'], 30)
        self.assertEqual(s, before)
    def test_partial_and_invalid_overrides_rejected(self):
        for f, b in ((30, None), (None, 5), (True, 5), (0, 5), (30, -1), (30, 2.5)):
            with self.subTest(f=f, b=b), self.assertRaises(ValueError): choose_curve(snapshot(), f, b)
    def test_no_simulation_no_bootstrap(self):
        with patch('efc.model.simulate', side_effect=AssertionError('simulation forbidden')):
            with patch('efc.grid.GridRunner.run', side_effect=AssertionError('grid forbidden')):
                self.assertEqual(choose_curve(snapshot())['fog'], 30)

if __name__ == '__main__': unittest.main()
