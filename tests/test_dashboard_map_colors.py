"""Synthetic display fixtures only, not calculated scientific configurations."""
import copy
import unittest
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from efc.map_view import STYLES, configuration_map_figure


def fixture():
    return dict(verification='ALL_DISPLAY_CHAINS_CHECKED', rows=[
        dict(n_fog=30,buffer=b,arrival_rate_s=100.,status=s,display_chain_checked=True)
        for b,s in zip((0,2,5,10),STYLES)])


class MapColoursTests(unittest.TestCase):
    def tearDown(self): plt.close('all')
    def test_four_distinct_codes_colours_and_labels(self):
        f=configuration_map_figure(fixture(),100.);ax=f.axes[0]
        np.testing.assert_array_equal(ax.images[0].get_array(),[[0,1,2,3]])
        self.assertEqual(len(set(ax.images[0].cmap.colors)),4)
        self.assertEqual([t.get_text() for t in f.legends[0].texts],[v[2] for v in STYLES.values()])
        self.assertEqual([t.get_text() for t in ax.texts],[v[1] for v in STYLES.values()])
    def test_insufficient_is_not_unacceptable(self):
        self.assertNotEqual(STYLES['INSUFFICIENT_DATA'],STYLES['UNACCEPTABLE'])
        d=fixture();d['rows']=[d['rows'][-1]]
        f=configuration_map_figure(d,100.)
        self.assertEqual(float(f.axes[0].images[0].get_array()[0,0]),3)
        self.assertIn('Недостаточно',f.axes[0].texts[0].get_text())
    def test_unverified_neighbour_prevents_figure(self):
        d=fixture();d['rows'][-1]['display_chain_checked']=False
        with self.assertRaises(ValueError):configuration_map_figure(d,100.)
    def test_unknown_and_archive_error_status_not_coloured_as_scientific(self):
        for status in ('ARCHIVE_UNVERIFIED','invented'):
            d=fixture();d['rows'][0]['status']=status
            with self.assertRaises(ValueError):configuration_map_figure(d,100.)
    def test_duplicate_coordinates_rejected(self):
        d=fixture();d['rows'].append(dict(d['rows'][0]))
        with self.assertRaises(ValueError):configuration_map_figure(d,100.)
    def test_missing_catalog_cell_not_filled_with_zero(self):
        d=fixture();d['rows'][-1]['n_fog']=40
        f=configuration_map_figure(d,100.)
        self.assertTrue(np.ma.is_masked(f.axes[0].images[0].get_array()[1,0]))
        self.assertIn('Вне\nкаталога',[x.get_text() for x in f.axes[0].texts])
    def test_render_read_only_and_unknown_rate_rejected(self):
        d=fixture();before=copy.deepcopy(d);configuration_map_figure(d,100.)
        self.assertEqual(d,before)
        with self.assertRaises(ValueError):configuration_map_figure(d,200.)

if __name__=='__main__':unittest.main()
