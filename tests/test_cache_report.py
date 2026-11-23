"""Idempotent resume proof: counted primary requests, not journal replays."""
from pathlib import Path
import tempfile
import unittest

from efc.grid import CachedSampler, atomic_json
from efc.pilot import Observation
from efc.statistics import Cohort
from scripts.report_r14_checkpoint import checkpoint_report


class RecordingSampler:
    calls=0
    config_id='unit-configuration'

    def __call__(self,seed,warm,observe,guard):
        type(self).calls+=1
        first=Cohort(seed,2,1,0,(100,))
        second=Cohort(seed,2,0,0,(100,100))
        full=Cohort(seed,4,1,0,(100,100,100))
        return Observation(full,first,second,
                           {'config_id':self.config_id,'workload_sha256':'shared-fixture-input'})


class CheckpointReportTests(unittest.TestCase):
    def test_replay_does_not_duplicate_scientific_sample_or_modify_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            cfg=RecordingSampler.config_id
            atomic_json(root/'manifest.json', {'catalog': [
                {'key':'r0.10_F30_B000','config_id':cfg,'arrival_rate_s':1.0}]})
            atomic_json(root/'map.json', {'rows':[
                {'key':'r0.10_F30_B000','status':'NOT_CALCULATED'}]})
            RecordingSampler.calls=0
            first=CachedSampler(RecordingSampler(),root)
            obs=first(100,2000,4000,1000)
            self.assertEqual(obs,CachedSampler(RecordingSampler(),root)(100,2000,4000,1000))
            self.assertEqual(RecordingSampler.calls,1)
            row={'seed':100,'warmup':2000,'observe':4000,'guard':1000}
            atomic_json(root/'cells/r0.10_F30_B000/pilot.json',
                        {'config_id':cfg,'runs':[row,row.copy()]})
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            a=checkpoint_report(root)
            b=checkpoint_report(root)
            after={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            self.assertEqual(a,b)
            self.assertEqual((a['integrity']['unique_primary_observations'],
                              a['integrity']['journal_rows'],
                              a['integrity']['journal_duplicate_rows']), (1,2,1))
            self.assertEqual(a['touched'][0]['distinct_pilot_seeds'],[100])
            self.assertEqual(a['touched'][0]['distinct_main_seeds'],[])
            self.assertEqual(a['cells_unresolved'],1)
            self.assertEqual(RecordingSampler.calls,1)

    def test_orphan_primary_visible_without_claiming_accepted_cell(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cfg=RecordingSampler.config_id
            atomic_json(root/'manifest.json', {'catalog': [
                {'key':'r0.10_F30_B000','config_id':cfg,'arrival_rate_s':1.0}]})
            atomic_json(root/'map.json', {'rows':[
                {'key':'r0.10_F30_B000','status':'NOT_CALCULATED'}]})
            CachedSampler(RecordingSampler(),root)(100,2000,4000,1000)
            a=checkpoint_report(root)
            self.assertEqual(a['primary_without_journal_row'],1)
            self.assertEqual(a['cells_unresolved'],1)
            self.assertEqual(a['integrity']['primary_completed_seed_repetitions'],0)

    def test_journal_claiming_missing_primary_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cfg=RecordingSampler.config_id
            atomic_json(root/'manifest.json', {'catalog': [
                {'key':'r0.10_F30_B000','config_id':cfg,'arrival_rate_s':1.0}]})
            atomic_json(root/'map.json', {'rows':[
                {'key':'r0.10_F30_B000','status':'NOT_CALCULATED'}]})
            atomic_json(root/'cells/r0.10_F30_B000/pilot.json',
                        {'config_id':cfg,'runs':[{'seed':100,'warmup':2000,'observe':4000,'guard':1000}]})
            with self.assertRaisesRegex(ValueError,'lack verified'):
                checkpoint_report(root)

if __name__=='__main__':
    unittest.main()
