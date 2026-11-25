"""Literal synthetic oracles; NOT measured configuration-map results."""
import unittest
import numpy as np
from efc.statistics import (Cohort, pooled_metrics, resample_counts, _weighted_metrics,
                            cluster_summary, classify, paired_equivalence, extract_cohort)


def ten(delay=100, arrivals=2000, lost=1, seeds=range(10)):
    return [Cohort(s, arrivals, lost, 0, (int(delay*1e6),)*(arrivals-lost)) for s in seeds]


class StatisticsTests(unittest.TestCase):
    def test_literal_pooled_not_mean_of_quantiles(self):
        a=Cohort(0,2,1,0,(100_000_000,)); b=Cohort(1,2,0,0,(200_000_000,300_000_000))
        r=pooled_metrics([a,b])
        self.assertEqual((r['p95_ms'],r['mean_ms'],r['drop_fraction'],r['H200']),(290,200,.25,.5))

    def test_ratio_of_counts_not_mean_of_ratios(self):
        r=pooled_metrics([Cohort(0,2,1,0,(1,)),Cohort(1,3,1,0,(2,3))])
        self.assertEqual(r['drop_fraction'],.4)

    def test_whole_cluster_literal_resamples(self):
        a=Cohort(0,2,1,0,(100_000_000,)); b=Cohort(1,2,0,0,(200_000_000,300_000_000))
        q,l=_weighted_metrics([a,b],np.array([[2,0],[1,1],[0,2]]))
        np.testing.assert_array_equal(q,[100,290,300]); np.testing.assert_array_equal(l,[.5,.25,0])

    def test_weighted_matches_independent_expansion(self):
        rng=np.random.default_rng(73)
        rows=[Cohort(s,s+4,1,0,tuple(map(int,rng.integers(0,1000000000,s+3)))) for s in range(10)]
        counts=resample_counts(10,120,7); q,l=_weighted_metrics(rows,counts)
        for i,c in enumerate(counts):
            expanded=[v for j,n in enumerate(c) for _ in range(n) for v in rows[j].latency_ticks]
            self.assertAlmostEqual(q[i],float(np.quantile(expanded,.95))/1e6,places=10)
            self.assertEqual(l[i],sum(c[j]*rows[j].dropped for j in range(10))/sum(c[j]*rows[j].arrivals for j in range(10)))

    def test_resample_reproducibility_and_totals(self):
        a=resample_counts(10,100); np.testing.assert_array_equal(a,resample_counts(10,100))
        np.testing.assert_array_equal(a.sum(axis=1),np.full(100,10))

    def test_zero_losses_do_not_certify(self):
        r=cluster_summary(ten(lost=0),repeats=10000)
        self.assertEqual(r['intervals']['drop_fraction']['upper'],0)
        self.assertIn('zero_loss_degenerate_bootstrap',r['reasons'])
        self.assertEqual(classify(r,warmup_ok=True),'INSUFFICIENT_DATA')

    def test_empty_seed_is_not_discarded(self):
        rows=ten(); rows[0]=Cohort(0,0,0,0,())
        r=cluster_summary(rows,repeats=10000)
        self.assertEqual(len(r['seed_ids']),10); self.assertEqual(r['intervals'],{})
        self.assertEqual(classify(r,warmup_ok=True),'INSUFFICIENT_DATA')

    def test_unfinished_suppresses_final_estimators(self):
        rows=ten(); rows[0]=Cohort(0,3,1,1,(120_000_000,))
        r=cluster_summary(rows,repeats=10000)
        self.assertIsNone(r['point']['p95_ms']); self.assertIsNone(r['point']['drop_fraction'])
        self.assertEqual(classify(r,warmup_ok=True),'INSUFFICIENT_DATA')

    def test_all_dropped_has_no_p95(self):
        r=cluster_summary([Cohort(s,3,3,0,()) for s in range(10)])
        self.assertIsNone(r['point']['p95_ms']); self.assertEqual(classify(r,warmup_ok=True),'INSUFFICIENT_DATA')

    def test_joint_exact_boundary(self):
        r=cluster_summary(ten(delay=200,arrivals=1000,lost=1),repeats=10000)
        self.assertEqual(classify(r,warmup_ok=True),'ACCEPTABLE')
        self.assertEqual(r['intervals']['p95_ms']['one_sided_level'],.975)
        self.assertFalse(r['familywise_map_guarantee'])

    def test_no_tolerance_added_to_p95_threshold(self):
        r=cluster_summary(ten(delay=200.000001),repeats=10000)
        self.assertEqual(classify(r,warmup_ok=True),'UNACCEPTABLE')

    def test_losses_alone_reject(self):
        self.assertEqual(classify(cluster_summary(ten(lost=3),repeats=10000),warmup_ok=True),'UNACCEPTABLE')

    def test_no_warmup_no_acceptance(self):
        self.assertEqual(classify(cluster_summary(ten(),repeats=10000),warmup_ok=False),'INSUFFICIENT_DATA')

    def test_fewer_than_ten_no_acceptance(self):
        self.assertEqual(classify(cluster_summary(ten()[:9],repeats=10000),warmup_ok=True),'INSUFFICIENT_DATA')

    def test_straddling_boundary_is_unknown(self):
        rows=[Cohort(s,2000,1,0,(int((198 if s<5 else 202)*1e6),)*1999) for s in range(10)]
        # Explicit independent intervals test decision branch, not bootstrap coverage.
        r=cluster_summary(rows,repeats=10000); r['precision_ok']=True
        r['intervals']['p95_ms'].update(lower=198,upper=202)
        self.assertEqual(classify(r,warmup_ok=True),'INSUFFICIENT_DATA')

    def test_pairing_by_seed_not_input_order(self):
        a=ten(); b=list(reversed(ten(delay=105)))
        r=paired_equivalence(a,b,repeats=10000)
        self.assertTrue(r['equivalent']); self.assertEqual(r['intervals']['p95_ms']['lower'],5)

    def test_wide_difference_not_equivalence(self):
        r=paired_equivalence(ten(),ten(delay=111),repeats=10000)
        self.assertFalse(r['equivalent'])

    def test_pair_requires_same_seeds(self):
        with self.assertRaises(ValueError):paired_equivalence(ten(),ten(seeds=range(10,20)))

    def test_malformed_cohort_and_duplicate_seeds(self):
        for args in ((0,2,0,0,(1,)),(True,1,0,0,(1,)),(0,1,0,0,(-1,))):
            with self.assertRaises(ValueError):Cohort(*args)
        with self.assertRaises(ValueError):pooled_metrics([ten()[0],ten()[0]])
        with self.assertRaises(ValueError):resample_counts(10,0)

    def test_extract_censoring_known_answer(self):
        tasks=[dict(event_id=0,release_tick=1_000_000,status='completed',end_tick=121_000_000,latency_tick=120_000_000),
               dict(event_id=1,release_tick=2_000_000,status='completed',end_tick=241_000_000,latency_tick=239_000_000),
               dict(event_id=2,release_tick=3_000_000,status='dropped',drop_tick=3_000_000)]
        a=extract_cohort(0,{'tasks':tasks},(0,4_000_000,300_000_000)); r=pooled_metrics([a])
        self.assertAlmostEqual(r['p95_ms'],233.05); self.assertEqual(r['drop_fraction'],1/3);self.assertEqual(r['H200'],1/3)
        b=extract_cohort(0,{'tasks':tasks},(0,4_000_000,200_000_000))
        self.assertEqual((len(b.latency_ticks),b.dropped,b.unfinished),(1,1,1))
        self.assertIsNone(pooled_metrics([b])['p95_ms'])

    def test_zero_inside_wide_interval_does_not_establish_equivalence(self):
        a=ten(); b=ten(); b[0]=Cohort(0,2000,1,0,(130_000_000,)*1999)
        r=paired_equivalence(a,b)
        self.assertEqual(r['intervals']['p95_ms']['lower'],0)
        self.assertGreater(r['intervals']['p95_ms']['upper'],10)
        self.assertFalse(r['equivalent'])

    def test_reduced_bootstrap_is_not_research_acceptance(self):
        r=cluster_summary(ten(),repeats=20)
        self.assertIn('nonprotocol_bootstrap_repeats',r['reasons'])
        self.assertEqual(classify(r,warmup_ok=True),'INSUFFICIENT_DATA')
