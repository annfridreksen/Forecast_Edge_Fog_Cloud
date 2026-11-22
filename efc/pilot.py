"""R1.4 finite pilot controller and frozen-window evaluation.

This module does not select candidates or run a grid. Confirmation selection
must be frozen by the map controller BEFORE any confirmation result is opened.
"""
from dataclasses import dataclass, asdict, replace
from pathlib import Path
import hashlib
import json
from .statistics import (Cohort, extract_cohort, cluster_summary, paired_equivalence,
                         classify, PILOT_SEEDS, MAIN_SEEDS, CONFIRM_SEEDS)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def _save(path, state):
    if path is not None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, allow_nan=False, indent=2)+'\n')
        tmp.replace(path)


@dataclass(frozen=True)
class Observation:
    full: Cohort
    first: Cohort
    second: Cohort
    provenance: dict

    def __post_init__(self):
        if len({c.seed for c in (self.full, self.first, self.second)}) != 1:
            raise ValueError('half-window seeds differ')
        for k in ('arrivals', 'dropped', 'unfinished'):
            if getattr(self.full, k) != getattr(self.first, k)+getattr(self.second, k):
                raise ValueError('half-window counts do not partition the cohort')
        if sorted(self.full.latency_ticks) != sorted(self.first.latency_ticks+self.second.latency_ticks):
            raise ValueError('half-window completed latencies do not partition the cohort')


class KernelSampler:
    """Only an adapter; all event handling stays in efc.model.simulate."""
    def __init__(self, config):
        self.config = config
        description = asdict(config)
        for key in ('seed', 'n_tasks'): description.pop(key)
        folder = Path(__file__).parent
        files = ('model.py','timebase.py','workload.py','stationary.py','statistics.py','pilot.py')
        hashes = {name: hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in files}
        self.config_id = _digest(dict(config=description, code_sha256=hashes))

    def __call__(self, seed, warmup, observe, guard):
        from .stationary import stationary_run
        row, result = stationary_run(replace(self.config, seed=seed), warmup, observe,
                                     guard, return_details=True)
        w = row['window_ticks']
        lo, hi, stop = w['start'], w['end'], w['guard_end']
        mid = (lo+hi)//2
        provenance = dict(config_id=self.config_id, window_ticks=w,
                          workload_sha256=row['workload_sha256'], kernel=row['kernel'])
        return Observation(extract_cohort(seed, result, (lo, hi, stop)),
                           extract_cohort(seed, result, (lo, mid, stop)),
                           extract_cohort(seed, result, (mid, hi, stop)), provenance)


def _collect(sample, seeds, warm, observe, guard, state, journal, cache=None):
    rows = []
    for seed in seeds:
        key = (seed, warm, observe, guard)
        reused = cache is not None and key in cache
        obs = cache[key] if reused else sample(*key)
        if cache is not None: cache[key] = obs
        if obs.full.seed != seed or obs.provenance.get('config_id') != sample.config_id:
            raise ValueError('sample provenance/seed mismatch')
        rows.append(obs)
        state['runs'].append(dict(seed=seed, warmup=warm, observe=observe, guard=guard,
                                  arrivals=obs.full.arrivals, dropped=obs.full.dropped,
                                  unfinished=obs.full.unfinished, reused=reused, provenance=obs.provenance))
        _save(journal, state)  # retain progress even if the next replication fails
    return rows


def select_windows(sample, *, journal=None, repeats=10000):
    """All model runs use ONLY 100..109. No inspection of final seeds here.

    Guard budget is engineering-only: 1000,2000,4000,8000,16000 expected
    arrivals/reference Fog; exhausting it gives insufficient data, not rejection.
    """
    if repeats != 10000: raise ValueError('R1.4 requires 10000 bootstrap repetitions')
    warmups, durations = (2000, 4000, 8000, 16000), (4000, 8000, 16000, 32000)
    state = dict(status='PILOT_RUNNING', config_id=sample.config_id, runs=[], decisions=[],
                 plan=None, pilot_seeds=list(PILOT_SEEDS), guard_limit=16000)
    i = j = 0
    cache = {}
    try:
        while True:
            warm, longer, observe, guard = warmups[i], warmups[i+1], durations[j], 1000
            while True:
                a = _collect(sample, PILOT_SEEDS, warm, observe, guard, state, journal, cache)
                b = _collect(sample, PILOT_SEEDS, longer, observe, guard, state, journal, cache)
                if not any(o.full.unfinished for o in a+b): break
                state['decisions'].append(dict(action='extend_guard' if guard < 16000 else 'stop_guard_limit',
                                                warmup=warm, observe=observe, guard=guard))
                if guard == 16000:
                    state['status'] = 'INSUFFICIENT_DATA'; return state
                cache.clear()
                guard *= 2
            full = [o.full for o in b]
            warm_check = paired_equivalence([o.full for o in a], full, repeats=repeats)
            halves = paired_equivalence([o.first for o in b], [o.second for o in b], repeats=repeats)
            precision = cluster_summary(full, repeats=repeats)
            decision = dict(warmup=warm, comparison_warmup=longer, observe=observe, guard=guard,
                            warmup_check=warm_check, halves_check=halves, precision=precision)
            state['decisions'].append(decision)
            if not (warm_check['equivalent'] and halves['equivalent']):
                decision['action'] = 'increase_warmup' if i+2 < len(warmups) else 'stop_warmup_limit'
                if i+2 == len(warmups):
                    state['status'] = 'INSUFFICIENT_DATA'; return state
                i += 1
            elif not precision['precision_ok']:
                decision['action'] = 'increase_observation' if j+1 < len(durations) else 'stop_precision_limit'
                if j+1 == len(durations):
                    state['status'] = 'INSUFFICIENT_DATA'; return state
                j += 1
            else:
                decision['action'] = 'freeze_longer_warmup'
                plan = dict(config_id=sample.config_id, warmup=longer, observe=observe, guard=guard,
                            pilot_seeds=list(PILOT_SEEDS), main_seeds=list(MAIN_SEEDS),
                            confirmation_seeds=list(CONFIRM_SEEDS), repeats=repeats,
                            protocol='R1.4', acceptance='pilot diagnostics, NOT exact stationarity')
                state.update(status='READY', plan=plan, plan_sha256=_digest(plan))
                return state
            cache = {k:v for k,v in cache.items() if k[1:] == (longer, observe, guard)}
            _save(journal, state)
    except Exception as exc:
        state.update(status='FAILED', error=repr(exc)); raise
    finally:
        _save(journal, state)


def run_frozen(sample, selection, phase, *, journal):
    """One frozen evaluation, no growing W/T or trying another candidate.

    A persistent journal is mandatory; an existing file blocks reuse even after
    a failed attempt. Guard extension changes only censoring, never W/T/seeds.
    """
    if selection['status'] != 'READY' or phase not in ('main', 'confirmation'):
        raise ValueError('ready pilot and known phase required')
    plan = selection['plan']
    if _digest(plan) != selection['plan_sha256'] or plan['config_id'] != sample.config_id:
        raise ValueError('frozen plan/configuration changed')
    if (plan['pilot_seeds'] != list(PILOT_SEEDS) or plan['main_seeds'] != list(MAIN_SEEDS)
            or plan['confirmation_seeds'] != list(CONFIRM_SEEDS)):
        raise ValueError('seed groups must remain disjoint and fixed')
    if journal is None: raise ValueError('persistent journal required')
    journal = Path(journal)
    journal.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation locks an attempt before seeing any final data.
    with journal.open('x') as f: f.write('{"status":"STARTED"}\n')
    seeds = MAIN_SEEDS if phase == 'main' else CONFIRM_SEEDS
    guard = plan['guard']
    state = dict(status='RUNNING', phase=phase, config_id=sample.config_id,
                 plan_sha256=selection['plan_sha256'], runs=[], decisions=[])
    try:
        while True:
            rows = _collect(sample, seeds, plan['warmup'], plan['observe'], guard, state, journal)
            if not any(o.full.unfinished for o in rows): break
            state['decisions'].append(dict(action='extend_guard' if guard < 16000 else 'stop_guard_limit', guard=guard))
            if guard >= 16000:
                state.update(status='INSUFFICIENT_DATA', reason='guard_limit'); return state
            guard = min(2*guard, 16000)
        summary = cluster_summary([o.full for o in rows], repeats=plan['repeats'])
        state.update(status=classify(summary, warmup_ok=True), summary=summary)
        return state
    except Exception as exc:
        state.update(status='FAILED', error=repr(exc)); raise
    finally:
        _save(journal, state)
