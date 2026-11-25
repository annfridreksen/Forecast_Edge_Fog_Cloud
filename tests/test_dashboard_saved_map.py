"""Neighbour corruption regressions: no grid execution or bootstrap rerun."""
import copy
from dataclasses import asdict, replace
import unittest
from unittest.mock import patch
import test_dashboard as fixtures
from efc import dashboard as d
from efc.grid import atomic_json, config_key, digest, read_json
from efc.primary import PrimarySampler


class WholeMapTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.DashboardTests(); self.fx.setUp()
        self.root, self.config = self.fx.root, self.fx.config
    def tearDown(self): self.fx.tearDown()
    def neighbour(self, mapping):
        config = replace(self.config, buffer=2)
        key, cid = config_key(config), PrimarySampler(config).config_id
        meta = dict(key=key, config_id=cid, arrival_rate_s=config.arrival_rate_s,
                    n_fog=config.n_fog, buffer=config.buffer, config=asdict(config))
        manifest = read_json(self.root/'manifest.json'); manifest['catalog'].append(meta)
        row = {k:v for k,v in meta.items() if k != 'config'}
        row.update(status='NOT_CALCULATED', main_seeds_completed=0)
        mapping['rows'].append(row); mapping['manifest_sha256'] = digest(manifest)
        atomic_json(self.root/'manifest.json', manifest)
        atomic_json(self.root/'map.json', mapping)
        return row
    def test_corrupted_unselected_acceptable_cell_rejected(self):
        mapping = self.fx.fixture(); row = self.neighbour(mapping)
        row['status'] = 'ACCEPTABLE'; atomic_json(self.root/'map.json', mapping)
        with self.assertRaisesRegex(ValueError, 'итогового журнала'): d.saved_cell(self.root,self.config)
    def test_neighbour_cannot_supply_unverified_curve(self):
        mapping = self.fx.fixture(); row = self.neighbour(mapping)
        row['summary'] = {'point': {'p95_ms': 1}}
        atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError): d.saved_cell(self.root,self.config)
    def test_neighbour_coordinates_must_match_manifest(self):
        mapping = self.fx.fixture(); row = self.neighbour(mapping); row['n_fog'] = 70
        atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError): d.saved_cell(self.root,self.config)
    def test_neighbour_model_identity_must_match(self):
        mapping = self.fx.fixture(); row = self.neighbour(mapping); row['config_id'] = 'foreign'
        atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError): d.saved_cell(self.root,self.config)
    def test_unproved_insufficient_status_rejected(self):
        mapping = self.fx.fixture(); row = self.neighbour(mapping); row['status'] = 'INSUFFICIENT_DATA'
        atomic_json(self.root/'map.json',mapping)
        with self.assertRaises((ValueError,FileNotFoundError)): d.saved_cell(self.root,self.config)
    def test_real_pilot_stop_remains_insufficient_not_unacceptable(self):
        mapping = self.fx.fixture(); row = self.neighbour(mapping)
        pilot = dict(config_id=row['config_id'],status='INSUFFICIENT_DATA',decisions=[{'action':'stop_warmup_limit'}])
        row.update(status='INSUFFICIENT_DATA',pilot_sha256=digest(pilot))
        atomic_json(self.root/'cells'/row['key']/'pilot.json',pilot)
        atomic_json(self.root/'map.json',mapping)
        r=d.saved_cell(self.root,self.config)
        self.assertEqual(r['rows'][1]['status'],'INSUFFICIENT_DATA')
        self.assertIsNone(r['rows'][1]['summary'])
        self.assertEqual(r['checked_rows'],2)
    def test_read_only_all_cells_without_recomputing_intervals(self):
        mapping,_ = self.fx.terminal_fixture(); self.neighbour(mapping)
        before={str(p):p.read_bytes() for p in self.root.rglob('*.json')}
        with patch('efc.statistics.cluster_summary',side_effect=AssertionError('no recompute')):
            r=d.saved_cell(self.root,self.config)
        self.assertEqual(r['status'],'ACCEPTABLE'); self.assertEqual(r['checked_rows'],2)
        self.assertTrue(all(x['display_chain_checked'] for x in r['rows']))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*.json')})
    def test_unknown_map_status_rejected(self):
        mapping=self.fx.fixture(); mapping['rows'][0]['status']='YES'
        atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError):d.saved_cell(self.root,self.config)
    def test_missing_final_summary_cannot_certify(self):
        mapping,main=self.fx.terminal_fixture();main['summary']=None
        row=mapping['rows'][0];row.update(main_sha256=digest(main),summary=None)
        atomic_json(self.root/'cells'/row['key']/'main.json',main)
        atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError):d.saved_cell(self.root,self.config)

if __name__=='__main__':unittest.main()
