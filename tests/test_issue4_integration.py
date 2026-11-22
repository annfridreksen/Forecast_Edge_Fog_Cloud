"""Regression checks for integration; no network traffic in unit tests."""
import json,math,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scipy.stats import t
from efc.stationary import ci95
from scripts.review_article import ci,table,section_replace,block_replace
from scripts.verify_doi import verify,crossref

class Issue4Integration(unittest.TestCase):
    def test_ci_across_replications(self):
        values=np.arange(10,dtype=float)
        mean,lo,hi=ci95(values)
        half=t.ppf(.975,9)*values.std(ddof=1)/math.sqrt(10)
        self.assertAlmostEqual(mean,4.5)
        self.assertAlmostEqual(lo,4.5-half)
        self.assertAlmostEqual(hi,4.5+half)
    def test_ci_requires_replicates(self):
        with self.assertRaises(ValueError):ci95([2])
        with self.assertRaises(ValueError):ci95([1,float('nan')])
    def test_interval_table_uses_stored_endpoints(self):
        text=ci({'mean_ms':12,'mean_ms_ci_low':10,'mean_ms_ci_high':14},'mean_ms')
        for value in ('12,00','10,00','14,00'):self.assertIn(value,text)
        self.assertIn('shortstack',text)
    def test_table_not_invented_from_caption(self):
        text=table('tab:test','Example',['A','B'],[['x','2,5']])
        self.assertIn(r'\label{tab:test}',text)
        self.assertIn('x & 2,5',text)
    def test_section_replacement_keeps_structure(self):
        source=''.join(r'\section{'+str(i)+'}\nOLD\n' for i in range(7))
        result=section_replace(source,'3','NEW')
        self.assertEqual(result.count(r'\section{'),7)
        self.assertIn('NEW',result)
        self.assertEqual(result.count('OLD'),6)
    def test_block_replacement_preserves_boundary(self):
        self.assertEqual(block_replace('a START old END z','START','END','new'),'a new\n\nEND z')
    def test_missing_section_fails(self):
        with self.assertRaises(ValueError):section_replace('no sections','3','new')
    def test_crossref_slash_encoded(self):
        response={'message':{'DOI':'10.1/a/b','title':['T'],'issued':{'date-parts':[[2020]]}}}
        with patch('scripts.verify_doi.get',return_value=response) as get:
            crossref('10.1/a/b')
            self.assertTrue(get.call_args.args[0].endswith('10.1%2Fa%2Fb'))
    def test_datacite_is_valid_for_dagstuhl(self):
        item={'key':'advice','doi':'10.4230/LIPIcs.APPROX/RANDOM.2020.60','title':'Better and Simpler Learning-Augmented Online Caching'}
        data={'registered_doi':item['doi'],'actual_title':item['title'],'registry':'DataCite'}
        with patch('scripts.verify_doi.datacite',new=lambda _:data),patch('scripts.verify_doi.crossref',side_effect=AssertionError('must not need Crossref')):
            self.assertTrue(verify(item)['ok'])
    def test_title_mismatch_not_success(self):
        item={'doi':'10.1/test','title':'Expected title'}
        data={'registered_doi':item['doi'],'actual_title':'Unrelated title'}
        with patch('scripts.verify_doi.crossref',new=lambda _:data),patch('scripts.verify_doi.datacite',new=lambda _:data):
            self.assertFalse(verify(item)['ok'])
    def test_catalog_matches_author_scope_without_duplicates(self):
        records=json.loads((Path(__file__).resolve().parents[1]/'article/references.json').read_text())
        self.assertGreaterEqual(len(records),12)
        self.assertLessEqual(len(records),15)
        self.assertEqual(len({r['key'] for r in records}),len(records))
        self.assertEqual(len({r['doi'].lower() for r in records}),len(records))
        required={'heft':'10.1109/71.993206','fogsurvey':'10.1002/spe.2766','lykouris':'10.1145/3447579','advice':'10.4230/LIPIcs.APPROX/RANDOM.2020.60'}
        by_key={r['key']:r['doi'] for r in records}
        for key,doi in required.items():self.assertEqual(by_key.get(key),doi)

if __name__=='__main__':unittest.main()
