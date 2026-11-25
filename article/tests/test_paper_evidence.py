"""Small manuscript-transfer controls; not statistical replications."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.check_r14_paper import verify_text, values_tex

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.e=json.loads((ROOT/'results/r14/article_evidence.json').read_text())
        self.v=(ROOT/'article/r14-values.tex').read_text()
        self.t=(ROOT/'article/main.tex').read_text()
        self.b=(ROOT/'article/r14-references.tex').read_text()
    def check(self):return verify_text(self.e,self.v,self.t,self.b)
    def test_actual_manuscript(self):self.assertEqual(self.check()['checked_values'],16)
    def test_wrong_p95_fails(self):
        self.v=self.v.replace('170,863296','180,863296')
        with self.assertRaisesRegex(ValueError,'numeric values'):self.check()
    def test_wrong_loss_fails(self):
        self.v=self.v.replace('\\rLoss}{0}','\\rLoss}{1}')
        with self.assertRaisesRegex(ValueError,'numeric values'):self.check()
    def test_missing_value_fails(self):
        self.v=self.v.replace('\\newcommand{\\rH}{0,986225129}\n','')
        with self.assertRaises(ValueError):self.check()
    def test_registered_but_unused_value_fails(self):
        self.t=self.t.replace('\\rQ{}','170,863296')
        with self.assertRaisesRegex(ValueError,'not used'):self.check()
    def test_broken_reference_fails(self):
        self.t+='\\ref{not-a-label}'
        with self.assertRaisesRegex(ValueError,'references'):self.check()
    def test_duplicate_reference_fails(self):
        self.b+='\\Bibitem{shi}'
        with self.assertRaisesRegex(ValueError,'bibliography'):self.check()
    def test_unsupported_misc_rejected(self):
        self.b+='\\misc old-generation-error'
        with self.assertRaisesRegex(ValueError,'unsupported'):self.check()
    def test_no_acceptance_from_zero(self):
        self.assertEqual(self.e['point']['drop_fraction'],0)
        self.assertEqual(self.e['loss_interval']['upper'],0)
        self.assertIn('zero_loss_degenerate_bootstrap',self.e['reasons'])
        self.e['status']='ACCEPTABLE'
        with self.assertRaisesRegex(ValueError,'acceptance'):self.check()
    def test_confidence_interval_not_claimed_recomputed(self):
        self.assertFalse(self.e['intervals_recomputed'])
        self.assertTrue(self.e['points_recomputed_from_ticks'])
        self.assertEqual(self.e['counts']['requests'],131)
    def test_values_exactly_regenerated_without_writing(self):
        self.assertEqual(values_tex(self.e),self.v)
    def test_frozen_archive_identified(self):
        self.assertEqual(self.e['artifact_id'],14820151165)
        self.assertEqual(len(self.e['primary']),10)
        self.assertEqual([r['request']['seed'] for r in self.e['primary']],list(range(10)))

if __name__=='__main__':unittest.main()
