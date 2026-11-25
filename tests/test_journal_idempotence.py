"""Journal replay is not an independent scientific replication."""
from pathlib import Path
import tempfile
import unittest
from efc.pilot import _record_run, _normalize_runs, select_windows, run_frozen
from efc.grid import CachedSampler, read_json
from test_grid import FixtureSampler
from efc.model import Config

class JournalTests(unittest.TestCase):
    def test_same_request_keeps_one_record(self):
        row=dict(seed=100,warmup=2000,observe=4000,guard=1000,arrivals=8,
                 dropped=1,unfinished=0,provenance={'config_id':'x'},reused=False)
        s={'runs':[]}
        _record_run(s,row);_record_run(s,{**row,'reused':True})
        self.assertEqual(s['runs'],[row]);self.assertEqual(s['journal_replays'],1)

    def test_conflicting_duplicate_rejected(self):
        row=dict(seed=100,warmup=1,observe=2,guard=3,arrivals=8,reused=False)
        s={'runs':[row]}
        with self.assertRaises(ValueError):_record_run(s,{**row,'arrivals':9})
        self.assertEqual(s['runs'],[row])

    def test_normalization_is_idempotent(self):
        row=dict(seed=100,warmup=1,observe=2,guard=3,arrivals=8,reused=False)
        s={'runs':[row,{**row,'reused':True}]}
        _normalize_runs(s);a=repr(s);_normalize_runs(s)
        self.assertEqual(repr(s),a)

    def test_different_windows_are_not_deduplicated(self):
        row=dict(seed=100,warmup=1,observe=2,guard=3,arrivals=8)
        s={'runs':[]};_record_run(s,row);_record_run(s,{**row,'warmup':2})
        self.assertEqual(len(s['runs']),2)

    def test_real_resume_writer_has_ten_rows_and_no_repeat_sampling(self):
        FixtureSampler.calls=[];FixtureSampler.fail_seed=None;FixtureSampler.bad_confirmation=False
        c=Config(n_cloud=40,buffer=2)
        with tempfile.TemporaryDirectory() as tmp:
            cache=CachedSampler(FixtureSampler(c),tmp)
            selection=select_windows(cache)
            FixtureSampler.calls=[];FixtureSampler.fail_seed=3
            path=Path(tmp)/'main.json'
            with self.assertRaises(RuntimeError):run_frozen(cache,selection,'main',journal=path)
            FixtureSampler.fail_seed=None
            end=run_frozen(cache,selection,'main',journal=path,resume=True)
            self.assertEqual(len(end['runs']),10)
            self.assertEqual(len({r['seed'] for r in end['runs']}),10)
            self.assertEqual(end['journal_replays'],3)
            calls=len(FixtureSampler.calls)
            self.assertEqual(end,run_frozen(cache,selection,'main',journal=path,resume=True))
            self.assertEqual(calls,len(FixtureSampler.calls))
