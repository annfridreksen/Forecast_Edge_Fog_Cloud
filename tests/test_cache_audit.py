"""Small fixtures: distinguish replay journal rows from distinct scientific samples."""
from pathlib import Path
import gzip
import json
import tempfile
import unittest
from efc.grid import atomic_json, canonical, digest
from scripts.audit_r14_cache import verify


def fixture(root, *, duplicate=False, corrupt=False, mismatched_source=False):
    root = Path(root)
    ids = ['cfg-A', 'cfg-B']
    atomic_json(root/'manifest.json', {
        'catalog': [{'key': f'k{i}', 'config_id': c, 'arrival_rate_s': 1.0} for i,c in enumerate(ids)]})
    atomic_json(root/'map.json', {'rows': [{'key': f'k{i}', 'status': 'NOT_CALCULATED'} for i in range(2)]})
    for i, cfg in enumerate(ids):
        req = {'config_id': cfg, 'seed': 100, 'warmup': 2000, 'observe': 4000, 'guard': 1000}
        half = {'seed': 100, 'arrivals': 2, 'dropped': 1, 'unfinished': 0, 'latency_ticks': [100]}
        full = {'seed': 100, 'arrivals': 4, 'dropped': 2, 'unfinished': 0, 'latency_ticks': [100, 100]}
        obj = {'full': full, 'first': half, 'second': half,
               'provenance': {'config_id': cfg, 'workload_sha256': 'DIFFERENT' if mismatched_source and i else 'SHARED'}}
        data = {'request': req, 'observation': obj, 'sha256': digest(obj)}
        if corrupt and i == 0:
            data['sha256'] = 'BAD'
        path = root/'observations'/cfg/(digest(req)+'.json.gz')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(canonical(data)))
        rows = [{'seed': 100, 'warmup': 2000, 'observe': 4000, 'guard': 1000}]
        if duplicate:
            rows.append(rows[0].copy())
        atomic_json(root/'cells'/f'k{i}'/'pilot.json', {'config_id': cfg, 'runs': rows})


class ReadOnlyAuditTests(unittest.TestCase):
    def test_replay_rows_not_independent_repetitions(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, duplicate=True)
            before = sorted((str(p.relative_to(d)), p.read_bytes()) for p in Path(d).rglob('*') if p.is_file())
            result = verify(d)
            after = sorted((str(p.relative_to(d)), p.read_bytes()) for p in Path(d).rglob('*') if p.is_file())
            self.assertEqual(before, after)
            self.assertEqual((result['unique_primary_observations'],
                              result['journal_rows'], result['journal_duplicate_rows']), (2, 4, 2))
            self.assertEqual(result['paired_source_rechecks'], 1)
            self.assertEqual(result['map_statuses'], {'NOT_CALCULATED': 2})
            self.assertEqual(result['primary_completed_seed_repetitions'], 0)

    def test_corrupt_primary_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, corrupt=True)
            with self.assertRaisesRegex(ValueError, 'checksum'):
                verify(d)

    def test_mismatched_common_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, mismatched_source=True)
            with self.assertRaisesRegex(ValueError, 'paired input mismatch'):
                verify(d)

    def test_journal_cannot_claim_absent_primary(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d)
            p = Path(d)/'cells/k0/pilot.json'
            data = json.loads(p.read_text())
            data['runs'].append({'seed':101, 'warmup':2000, 'observe':4000, 'guard':1000})
            atomic_json(p, data)
            with self.assertRaisesRegex(ValueError, 'lack verified'):
                verify(d)


if __name__ == '__main__':
    unittest.main()
