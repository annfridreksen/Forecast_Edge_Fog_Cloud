"""Trace oracles: synthetic output fixtures are not independent scientific data."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from efc.main_summary import CELL_ID,OUTPUT_PREFIX,summary_table,_inventory
from scripts.check_r14_paper import SPECS,get
from scripts.check_r14_trace import verify_outputs
from efc.grid import digest

class TraceTests(unittest.TestCase):
    def setUp(self):
        self.e=json.loads((ROOT/'results/r14/article_evidence.json').read_text())
        rows=[]
        for _,(field,_,_) in SPECS.items():
            rows.append(dict(field=field,value=get(self.e,field),source_file=self.e['main_path'],
                             source_byte_sha256=self.e['main_byte_sha256'],
                             source_canonical_sha256=self.e['map_sha256'] if field.startswith('counts.') else self.e['main_canonical_sha256'],
                             primary_inventory_sha256='fixture-not-a-measured-hash'))
        self.d=dict(schema='r14-notebook-summary-v1',state='CHECKED_CHAINS',selected_key='r0.10_F30_B005',
                    map_sha256=self.e['map_sha256'],manifest_sha256=self.e['manifest_sha256'],
                    status=self.e['status'],seed_ids=list(range(10)),rows=rows,
                    scientific_acceptance=False,simulation_executed=False,bootstrap_recomputed=False,
                    counts_state='EXACT_PRIMARY_FILE_INVENTORY',inventory={'primary_inventory_sha256':'fixture-not-a-measured-hash'})
    def book(self):
        return {'cells':[dict(id=CELL_ID,cell_type='code',execution_count=1,
                outputs=[dict(output_type='stream',text=OUTPUT_PREFIX+json.dumps(self.d)+'\n')])]}
    def test_all_sixteen_fields_have_actual_values(self):self.assertEqual(len(verify_outputs(self.book(),self.e)),16)
    def test_wrong_field_rejected(self):
        specs=copy.deepcopy(SPECS);specs['rH']=('point.not_H200',9,CELL_ID)
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e,specs)
    def test_existing_but_wrong_field_rejected_against_tex(self):
        specs=copy.deepcopy(SPECS);specs['rMean']=('point.H200',6,CELL_ID)
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e,specs)
    def test_wrong_registered_cell_id_rejected(self):
        specs=copy.deepcopy(SPECS);specs['rH']=('point.H200',9,'r14-01-curves')
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e,specs)
    def test_wrong_actual_cell_id_rejected(self):
        b=self.book();b['cells'][0]['id']='r14-01-curves'
        with self.assertRaises(ValueError):verify_outputs(b,self.e)
    def test_id_without_output_rejected(self):
        b=self.book();b['cells'][0]['outputs']=[]
        with self.assertRaises(ValueError):verify_outputs(b,self.e)
    def test_unexecuted_cell_rejected(self):
        b=self.book();b['cells'][0]['execution_count']=None
        with self.assertRaises(ValueError):verify_outputs(b,self.e)
    def test_duplicate_cell_rejected(self):
        b=self.book();b['cells']*=2
        with self.assertRaises(ValueError):verify_outputs(b,self.e)
    def test_duplicate_field_rejected(self):
        self.d['rows'].append(self.d['rows'][0])
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e)
    def test_wrong_value_rejected(self):
        next(r for r in self.d['rows'] if r['field']=='point.mean_ms')['value']+=1
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e)
    def test_wrong_main_byte_hash_rejected(self):
        next(r for r in self.d['rows'] if r['field']=='point.mean_ms')['source_byte_sha256']='0'*64
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e)
    def test_newer_snapshot_not_silently_used(self):
        self.d['map_sha256']='0'*64
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e)
    def test_unknown_counts_not_zero(self):
        self.d['counts_state']='UNAVAILABLE'
        with self.assertRaises(ValueError):verify_outputs(self.book(),self.e)
    def test_absent_archive_has_no_numbers(self):
        d=summary_table('/not-used',{'state':'NO_CHECKPOINT'},{'fog':30,'buffer':5})
        self.assertEqual(d['rows'],[])
    def test_cell_notebook_source_really_emits_table(self):
        b=json.loads((ROOT/'colab/01_Среда_и_конфигурация.ipynb').read_text())
        source=''.join(next(c['source'] for c in b['cells'] if c['id']==CELL_ID))
        emitted=[]
        class FakePandas:
            @staticmethod
            def DataFrame(rows): return rows
        ns=dict(checkpoint='unused',snapshot={},selection={},json=json,pd=FakePandas,
                display=emitted.append,print=lambda *x: emitted.append(' '.join(str(v) for v in x)))
        self.d['note']='synthetic control'
        with patch('efc.main_summary.summary_table',return_value=self.d):exec(compile(source,CELL_ID,'exec'),ns)
        self.assertIn(self.d['rows'],emitted)
        self.assertTrue(any(isinstance(x,str) and x.startswith(OUTPUT_PREFIX) for x in emitted))

class InventoryTests(unittest.TestCase):
    def test_replays_count_once_and_orphan_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);req=dict(config_id='cfg',seed=100,warmup=1,observe=2,guard=1)
            path=root/'observations'/'cfg'/(digest(req)+'.json.gz');path.parent.mkdir(parents=True);path.write_bytes(b'fixture')
            folder=root/'cells'/'k';folder.mkdir(parents=True)
            (folder/'pilot.json').write_text(json.dumps(dict(config_id='cfg',runs=[req,req])))
            snapshot=dict(rows=[dict(key='k',config_id='cfg',status='NOT_CALCULATED')])
            counts,_=_inventory(root,snapshot);self.assertEqual(counts['requests'],1);self.assertEqual(counts['pilot'],1)
            (path.parent/'orphan.json.gz').write_bytes(b'fixture')
            with self.assertRaises(ValueError):_inventory(root,snapshot)

if __name__=='__main__':unittest.main()
