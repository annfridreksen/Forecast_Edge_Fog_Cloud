"""Pilot-only import must be exact, restartable, and never simulate a seed."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import gzip
import json
import unittest
from unittest.mock import patch
from efc.grid import GridRunner, atomic_json, digest, canonical, read_json
from efc.primary import PrimarySampler
from efc.pilot import Observation
from efc.statistics import Cohort
from scripts.migrate_r14_storage import migrate,old_id,compatible_certificate,ROOT

CERT=ROOT/'results/r14/compact_storage_compatibility.json'

class MigrationTests(unittest.TestCase):
    def fixture(self,d):
        source=Path(d)/'source';target=Path(d)/'target'
        source.mkdir();r=GridRunner(Path(d)/'unused',factory=PrimarySampler)
        manifest=json.loads(canonical(r.manifest));cert=compatible_certificate(CERT)
        for cell in manifest['catalog']:cell['config_id']=old_id(cell['config'],cert)
        atomic_json(source/'manifest.json',manifest)
        cid=manifest['catalog'][0]['config_id'];half=Cohort(100,1,0,0,(100_000_000,))
        obs=Observation(Cohort(100,2,0,0,half.latency_ticks*2),half,half,{'config_id':cid,'workload_sha256':'fixture'})
        req=dict(config_id=cid,seed=100,warmup=2000,observe=4000,guard=1000)
        data=dict(request=req,observation=asdict(obs),sha256=digest(asdict(obs)))
        p=source/'observations'/cid/(digest(req)+'.json.gz');p.parent.mkdir(parents=True)
        p.write_bytes(gzip.compress(canonical(data),mtime=0))
        return source,target,p

    def test_import_and_repeat_preserve_primary_and_source(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p=self.fixture(d);original=p.read_bytes()
            with patch.object(PrimarySampler,'__call__',side_effect=AssertionError('no new simulation')):
                a=migrate(s,t,CERT);saved=(t/'storage-migration.json').read_bytes();b=migrate(s,t,CERT)
            self.assertEqual(a['imported_primary_requests'],1)
            self.assertEqual(b['already_present_this_call'],1)
            self.assertEqual(saved,(t/'storage-migration.json').read_bytes());self.assertEqual(p.read_bytes(),original)
            old=json.loads(gzip.decompress(original))['observation']
            new=json.loads(gzip.decompress(next((t/'observations').glob('*/*.gz')).read_bytes()))['observation']
            for key in ('full','first','second'):self.assertEqual(old[key],new[key])
            self.assertNotEqual(old['provenance']['config_id'],new['provenance']['config_id'])

    def test_source_digest_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p=self.fixture(d);v=json.loads(gzip.decompress(p.read_bytes()));v['sha256']='bad'
            p.write_bytes(gzip.compress(canonical(v)))
            with self.assertRaises(ValueError):migrate(s,t,CERT)

    def test_main_journal_blocks_migration(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,_=self.fixture(d);atomic_json(s/'cells'/'x'/'main.json',{})
            with self.assertRaises(ValueError):migrate(s,t,CERT)

    def test_same_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,_=self.fixture(d)
            with self.assertRaises(ValueError):migrate(s,s,CERT)

    def test_changed_scientific_code_rejected(self):
        from unittest.mock import patch
        original=Path.read_bytes
        def changed(p):return b'incompatible' if p.name=='model.py' else original(p)
        with patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):compatible_certificate(CERT)

    def test_target_conflict_not_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p=self.fixture(d);migrate(s,t,CERT)
            out=next((t/'observations').glob('*/*.gz'));out.write_bytes(gzip.compress(b'{}'))
            with self.assertRaises(ValueError):migrate(s,t,CERT)
            self.assertEqual(gzip.decompress(out.read_bytes()),b'{}')

    def test_confirmation_registry_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s,t,p=self.fixture(d);atomic_json(s/'candidates.json',{})
            with self.assertRaises(ValueError):migrate(s,t,CERT)
