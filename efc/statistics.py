"""R1.4 pooled metrics and percentile bootstrap of WHOLE independent seeds.

No individual-message resampling, binomial independence, or exact coverage claim.
Integer latency ticks remain authoritative. Empty/unfinished seeds are not dropped.
"""
from dataclasses import dataclass
import hashlib
import numpy as np

PILOT_SEEDS = tuple(range(100, 110))
MAIN_SEEDS = tuple(range(10))
CONFIRM_SEEDS = tuple(range(200, 210))
BOOTSTRAP_SEED = 20261123


@dataclass(frozen=True)
class Cohort:
    seed: int
    arrivals: int
    dropped: int
    unfinished: int
    latency_ticks: tuple[int, ...]

    def __post_init__(self):
        for value in (self.seed, self.arrivals, self.dropped, self.unfinished):
            if type(value) is not int or value < 0:
                raise ValueError('seed/count must be a nonnegative integer')
        object.__setattr__(self, 'latency_ticks', tuple(self.latency_ticks))
        if any(type(t) is not int or not 0 <= t < 2**62 for t in self.latency_ticks):
            raise ValueError('latencies must be nonnegative integer ticks below 2**62')
        if self.arrivals != len(self.latency_ticks) + self.dropped + self.unfinished:
            raise ValueError('cohort balance violated')


def extract_cohort(seed, result, window):
    """Read the kernel trace, not rounded p95 of an earlier summary."""
    lo, hi, stop = window
    if not 0 <= lo < hi <= stop:
        raise ValueError('invalid observation window')
    rows = [r for r in result['tasks'] if lo <= r['release_tick'] < hi]
    ids = [r['event_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate event_id in cohort')
    delays, drops = [], 0
    for r in rows:
        if r['status'] == 'completed' and r['end_tick'] <= stop:
            if r['latency_tick'] != r['end_tick'] - r['release_tick']:
                raise ValueError('latency identity violated')
            delays.append(r['latency_tick'])
        elif r['status'] == 'dropped' and r['drop_tick'] <= stop:
            drops += 1
        elif r['status'] not in ('completed', 'dropped', 'pending'):
            raise ValueError('unknown event status')
    return Cohort(seed, len(rows), drops, len(rows)-drops-len(delays), tuple(delays))


def _ordered(cohorts):
    rows = tuple(sorted(cohorts, key=lambda c: c.seed))
    if not rows or len({c.seed for c in rows}) != len(rows):
        raise ValueError('nonempty collection of distinct independent seeds required')
    return rows


def resample_counts(n, repeats=10000, seed=BOOTSTRAP_SEED):
    """Each row is multiplicities of n WHOLE seeds, including all their events."""
    if type(n) is not int or n < 1 or type(repeats) is not int or repeats < 1:
        raise ValueError('positive integer bootstrap dimensions required')
    return np.random.default_rng(seed).multinomial(n, np.full(n, 1/n), size=repeats)


def _weighted_metrics(rows, counts):
    """Exact repeated-sample linear quantile without expanding bootstrap copies.

    Binary search of integer order statistics over sorted per-seed arrays avoids
    concatenating millions of events 10000 times. Interpolation is NumPy linear.
    """
    counts = np.asarray(counts)
    if counts.ndim != 2 or counts.shape[1] != len(rows) or counts.dtype.kind not in 'iu':
        raise ValueError('invalid cluster multiplicities')
    if (counts < 0).any() or (counts.sum(axis=1) != len(rows)).any():
        raise ValueError('each resample must contain exactly n whole seeds')
    arrays = [np.sort(np.asarray(c.latency_ticks, dtype=np.int64)) for c in rows]
    arrivals = counts @ np.array([c.arrivals for c in rows], dtype=np.int64)
    drops = counts @ np.array([c.dropped for c in rows], dtype=np.int64)
    sizes = counts @ np.array([len(a) for a in arrays], dtype=np.int64)
    losses = np.full(len(counts), np.nan)
    np.divide(drops, arrivals, out=losses, where=arrivals > 0)
    q = np.full(len(counts), np.nan)
    valid = sizes > 0
    nonempty = [a for a in arrays if len(a)]
    if not nonempty:
        return q, losses
    low, high = min(int(a[0]) for a in nonempty), max(int(a[-1]) for a in nonempty)
    def order_stat(rank):
        left = np.full(len(counts), low, dtype=np.int64)
        right = np.full(len(counts), high, dtype=np.int64)
        while np.any(left < right):
            mid = left + (right-left)//2
            cumulative = sum(counts[:, j]*np.searchsorted(a, mid, side='right')
                             for j, a in enumerate(arrays))
            enough = cumulative > rank
            right = np.where(enough, mid, right)
            left = np.where(enough, left, mid+1)
        return left
    # 95/100 = 19/20: exact rank and interpolation fraction.
    rank, remainder = np.divmod(19*(sizes-1), 20)
    a = order_stat(np.maximum(rank, 0)).astype(float)
    b = order_stat(np.minimum(np.maximum(rank+1, 0), np.maximum(sizes-1, 0))).astype(float)
    q[valid] = (a[valid]+(b[valid]-a[valid])*remainder[valid]/20)/1_000_000
    return q, losses


def pooled_metrics(cohorts):
    rows = _ordered(cohorts)
    n, lost, pending = (sum(getattr(c, k) for c in rows)
                        for k in ('arrivals', 'dropped', 'unfinished'))
    result = dict(arrivals=n, dropped=lost, unfinished=pending,
                  completed=sum(len(c.latency_ticks) for c in rows), p95_ms=None,
                  drop_fraction=None, mean_ms=None, H200=None)
    if n == 0 or pending:
        return result
    q, loss = _weighted_metrics(rows, np.ones((1, len(rows)), dtype=np.int64))
    result.update(p95_ms=float(q[0]) if np.isfinite(q[0]) else None,
                  drop_fraction=float(loss[0]),
                  H200=sum(sum(t <= 200_000_000 for t in c.latency_ticks) for c in rows)/n)
    if result['completed']:
        result['mean_ms'] = sum(sum(c.latency_ticks) for c in rows)/result['completed']/1_000_000
    return result


def cluster_summary(cohorts, *, repeats=10000, bootstrap_seed=BOOTSTRAP_SEED):
    rows = _ordered(cohorts)
    point = pooled_metrics(rows)
    reasons = []
    if repeats != 10000: reasons.append('nonprotocol_bootstrap_repeats')
    if len(rows) < 10: reasons.append('fewer_than_10_seeds')
    if any(c.arrivals == 0 for c in rows): reasons.append('empty_seed_cohort')
    if any(c.unfinished for c in rows): reasons.append('unfinished_cohort')
    if not point['completed']: reasons.append('no_completed_events')
    report = dict(point=point, seed_ids=[c.seed for c in rows], reasons=reasons,
                  intervals={}, precision_ok=False, method='whole-seed percentile bootstrap',
                  repeats=repeats, bootstrap_seed=bootstrap_seed,
                  nominal_coverage_only=True, familywise_map_guarantee=False)
    # No silently excluding incomplete/empty replications.
    if any(c.arrivals == 0 or c.unfinished for c in rows) or not point['completed']:
        return report
    counts = resample_counts(len(rows), repeats, bootstrap_seed)
    q, losses = _weighted_metrics(rows, counts)
    report['resample_counts_sha256'] = hashlib.sha256(counts.astype('<i8').tobytes()).hexdigest()
    if not np.isfinite(q).all() or not np.isfinite(losses).all():
        reasons.append('undefined_bootstrap_sample')
        return report
    for name, values in (('p95_ms', q), ('drop_fraction', losses)):
        lo, hi = map(float, np.quantile(values, [.025, .975], method='linear'))
        report['intervals'][name] = dict(lower=lo, upper=hi, half_width=(hi-lo)/2,
                                        descriptive_level=.95, one_sided_level=.975)
    if point['dropped'] == 0:
        reasons.append('zero_loss_degenerate_bootstrap')
    report['precision_ok'] = (not reasons and
        report['intervals']['p95_ms']['half_width'] <= 10 and
        report['intervals']['drop_fraction']['half_width'] <= .00005)
    return report


def classify(summary, *, warmup_ok):
    """Conservative joint decision; tolerances NEVER relax the two limits."""
    if type(warmup_ok) is not bool:
        raise ValueError('explicit Boolean warmup diagnostic required')
    if not warmup_ok or not summary['precision_ok'] or summary['reasons']:
        return 'INSUFFICIENT_DATA'
    q, loss = (summary['intervals'][k] for k in ('p95_ms', 'drop_fraction'))
    if q['upper'] <= 200 and loss['upper'] <= .001:
        return 'ACCEPTABLE'
    if q['lower'] > 200 or loss['lower'] > .001:
        return 'UNACCEPTABLE'
    return 'INSUFFICIENT_DATA'


def paired_equivalence(first, second, *, repeats=10000, bootstrap_seed=BOOTSTRAP_SEED):
    """Paired whole-seed difference of pooled estimators: second minus first."""
    a, b = _ordered(first), _ordered(second)
    if [c.seed for c in a] != [c.seed for c in b]:
        raise ValueError('paired samples must have identical seed IDs')
    result = dict(equivalent=False, intervals={}, difference='second minus first')
    if len(a) < 10 or any(c.arrivals == 0 or c.unfinished for c in a+b):
        result['reason'] = 'missing_or_incomplete_replications'
        return result
    counts = resample_counts(len(a), repeats, bootstrap_seed)
    x, y = _weighted_metrics(a, counts), _weighted_metrics(b, counts)
    for i, (name, epsilon) in enumerate((('p95_ms', 10), ('drop_fraction', .00005))):
        delta = y[i]-x[i]
        if not np.isfinite(delta).all():
            result['reason'] = 'undefined_paired_sample'
            return result
        lo, hi = map(float, np.quantile(delta, [.025, .975], method='linear'))
        result['intervals'][name] = dict(lower=lo, upper=hi, epsilon=epsilon,
                                        inside=(-epsilon <= lo and hi <= epsilon))
    result['equivalent'] = all(v['inside'] for v in result['intervals'].values())
    result['zero_loss_diagnostic_only'] = not any(c.dropped for c in a+b)
    return result
