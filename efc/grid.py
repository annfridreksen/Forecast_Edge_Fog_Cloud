"""R1.4 persistent execution, NOT a new model or statistical criterion.

All scientific calls delegate to KernelSampler/select_windows/run_frozen.
Completed observations are immutable, hashed JSON (never executable pickle).
A stopped process resumes the same frozen attempt, not a new candidate search.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import gzip
import hashlib
import json
import os
import time

from .pilot import KernelSampler, Observation, select_windows, run_frozen
from .statistics import Cohort
from .stationary import scenarios

TERMINAL = ('ACCEPTABLE', 'UNACCEPTABLE', 'INSUFFICIENT_DATA')
VERSION = 'R1.4-grid-1'


class BudgetStop(RuntimeError):
    """A resource pause is NOT a scientific decision about a configuration."""


class ResourceStop(BudgetStop):
    """Skip this unresolved cell without changing its scientific windows."""


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':')).encode('utf-8')


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('wb') as f:
        f.write(canonical(obj) + b'\n')
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


@contextmanager
def exclusive(root):
    """Advisory lock survives in the filesystem, not as a false stale PID."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.writer.lock').open('a+') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('another process owns this map; do not duplicate it') from exc
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class CachedSampler:
    def __init__(self, sample, root, *, deadline=None, max_expected_events=None):
        self.sample = sample
        self.config_id = sample.config_id
        self.root = Path(root) / 'observations' / self.config_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.deadline = deadline
        self.max_expected_events = max_expected_events
        self.new_runs = self.reused_runs = 0

    def __call__(self, seed, warmup, observe, guard):
        request = dict(config_id=self.config_id, seed=seed, warmup=warmup,
                       observe=observe, guard=guard)
        path = self.root / (digest(request) + '.json.gz')
        if path.exists():
            data = json.loads(gzip.decompress(path.read_bytes()))
            if data['request'] != request or data['sha256'] != digest(data['observation']):
                raise ValueError('checkpoint identity/checksum mismatch: ' + str(path))
            o = data['observation']
            result = Observation(*(Cohort(**o[k]) for k in ('full', 'first', 'second')),
                                 o['provenance'])
            self.reused_runs += 1
        else:
            if self.deadline is not None and time.monotonic() >= self.deadline:
                raise BudgetStop('wall budget reached between replications')
            expected = 50 * (warmup + observe + guard)
            if self.max_expected_events is not None and expected > self.max_expected_events:
                raise ResourceStop('per-replication resource limit; requested windows unchanged')
            result = self.sample(seed, warmup, observe, guard)
            if result.full.seed != seed or result.provenance.get('config_id') != self.config_id:
                raise ValueError('sampler returned another seed/configuration')
            o = asdict(result)
            data = dict(request=request, observation=o, sha256=digest(o))
            tmp = path.with_suffix(path.suffix + '.tmp')
            with tmp.open('wb') as f:
                f.write(gzip.compress(canonical(data), mtime=0))
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(path)
            self.new_runs += 1
        if result.full.seed != seed or result.provenance.get('config_id') != self.config_id:
            raise ValueError('checkpoint returned another seed/configuration')
        return result


def config_key(config):
    return f"r{config.arrival_rate_s*0.055/50:.2f}_F{config.n_fog:02d}_B{config.buffer:03d}"


def freeze_candidates(root, catalog, map_data):
    """Freeze ALL flows atomically before opening ANY confirmation seed."""
    root = Path(root)
    path = root / 'candidates.json'
    if path.exists():
        registry = read_json(path)
        if registry['map_sha256'] != digest(map_data):
            raise ValueError('candidate map changed after freezing')
        return registry
    expected = {r['key'] for r in catalog}
    rows = {r['key']: r for r in map_data['rows']}
    if len(rows) != len(map_data['rows']) or set(rows) != expected or any(r['status'] not in TERMINAL for r in rows.values()):
        raise ValueError('cannot freeze candidates before all catalog cells are resolved')
    if any((root/'cells').glob('*/confirmation.json')):
        raise ValueError('confirmation exists before global candidate freeze')
    chosen = []
    for flow in sorted({r['arrival_rate_s'] for r in catalog}):
        keys = {r['key'] for r in catalog if r['arrival_rate_s'] == flow}
        cells = sorted((rows[k] for k in keys), key=lambda r: (r['n_fog'], r['buffer']))
        candidate = next((r for r in cells if r['status'] == 'ACCEPTABLE'), None)
        smaller = [r for r in cells if candidate and
                   (r['n_fog'], r['buffer']) < (candidate['n_fog'], candidate['buffer'])]
        chosen.append(dict(arrival_rate_s=flow, key=candidate['key'] if candidate else None,
                           smaller_cells=smaller, selection='minimum of evaluated map only'))
    registry = dict(version=VERSION, map_sha256=digest(map_data),
                    candidates=chosen, confirmation_seeds=list(range(200, 210)),
                    no_reselection=True, frozen_utc=datetime.now(timezone.utc).isoformat())
    # The map writer lock is required by the caller.
    atomic_json(root/'frozen-map.json', map_data)
    with path.open('x', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, sort_keys=True, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    return registry


class GridRunner:
    def __init__(self, root, *, configurations=None, factory=KernelSampler,
                 wall_seconds=None, max_expected_events=1_000_000):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        configs = list(configurations) if configurations is not None else [c for _,_,c in scenarios()]
        self.configs = {config_key(c): c for c in configs}
        if len(self.configs) != len(configs):
            raise ValueError('duplicate cell key')
        self.factory = factory
        self.deadline = None if wall_seconds is None else time.monotonic()+wall_seconds
        self.max_expected_events = max_expected_events
        self.catalog = []
        for key, c in self.configs.items():
            sample = factory(c)
            self.catalog.append(dict(key=key, config_id=sample.config_id,
                                     arrival_rate_s=c.arrival_rate_s,
                                     n_fog=c.n_fog, buffer=c.buffer, config=asdict(c)))
        self.catalog.sort(key=lambda r:(r['arrival_rate_s'],r['n_fog'],r['buffer']))
        self.manifest = dict(version=VERSION, catalog=self.catalog,
                             scientific_grid=configurations is None,
                             pilot_seeds=list(range(100,110)), main_seeds=list(range(10)),
                             confirmation_seeds=list(range(200,210)))
        self.manifest = json.loads(canonical(self.manifest))
        self.new_runs = self.reused_runs = 0

    def _bind(self):
        path = self.root/'manifest.json'
        if path.exists():
            if read_json(path) != self.manifest:
                raise ValueError('incompatible model/protocol/catalog; never reuse this checkpoint')
        else:
            atomic_json(path, self.manifest)

    def _sample(self, key):
        return CachedSampler(self.factory(self.configs[key]), self.root,
                             deadline=self.deadline, max_expected_events=self.max_expected_events)

    def map_data(self):
        rows = []
        for c in self.catalog:
            p = self.root/'cells'/c['key']/'cell.json'
            row = {k:c[k] for k in ('key','config_id','arrival_rate_s','n_fog','buffer')}
            row.update(status='NOT_CALCULATED', main_seeds_completed=0)
            if p.exists():
                saved = read_json(p)
                if saved['config_id'] != c['config_id']:
                    raise ValueError('cell configuration changed')
                row.update(saved)
            rows.append(row)
        return dict(version=VERSION, manifest_sha256=digest(self.manifest), rows=rows,
                    total_cells=len(rows),
                    protocol_resolved_cells=sum(r['status'] in TERMINAL for r in rows),
                    cells_with_10_main_seeds=sum(r.get('main_seeds_completed')==10 for r in rows),
                    main_replications=sum(r.get('main_seeds_completed',0) for r in rows),
                    all_main_complete=all(r.get('main_seeds_completed')==10 for r in rows),
                    scope='scientific grid' if self.manifest['scientific_grid'] else 'small controller fixture')

    def _archive_partial(self, path):
        if path.exists():
            data = read_json(path)
            atomic_json(path.parent/'history'/(path.stem+'-'+digest(data)+'.json'), data)

    def _cell(self, key):
        folder = self.root/'cells'/key
        folder.mkdir(parents=True, exist_ok=True)
        cache = self._sample(key)
        status = dict(key=key, config_id=cache.config_id, status='RUNNING',
                      main_seeds_completed=0)
        try:
            pilot_path = folder/'pilot.json'
            pilot = read_json(pilot_path) if pilot_path.exists() else {}
            if pilot.get('config_id', cache.config_id) != cache.config_id:
                raise ValueError('pilot configuration mismatch')
            if pilot.get('status') not in ('READY','INSUFFICIENT_DATA'):
                self._archive_partial(pilot_path)
                # Deterministic control replay; completed samples come from disk.
                pilot = select_windows(cache, journal=pilot_path)
            status['pilot_status'] = pilot['status']
            if pilot['status'] != 'READY':
                status.update(status='INSUFFICIENT_DATA', reason='pilot_not_ready',
                              pilot_sha256=digest(pilot))
                return
            final_path = folder/'main.json'
            result = run_frozen(cache, pilot, 'main', journal=final_path,
                                resume=final_path.exists())
            completed = {r['seed'] for r in result['runs']
                         if r.get('unfinished') == 0}
            status.update(status=result['status'], main_sha256=digest(result),
                          main_seeds_completed=len(completed), plan_sha256=pilot['plan_sha256'],
                          summary=result.get('summary'), reason=result.get('reason'))
        except BudgetStop as exc:
            status.update(status='NOT_CALCULATED', execution_status='PAUSED', reason=str(exc))
            raise
        except Exception as exc:
            status.update(status='NOT_CALCULATED', execution_status='FAILED', reason=repr(exc))
            raise
        finally:
            self.new_runs += cache.new_runs
            self.reused_runs += cache.reused_runs
            atomic_json(folder/'cell.json', status)

    def run(self, *, confirm=False):
        with exclusive(self.root):
            self._bind()
            started = datetime.now(timezone.utc).isoformat()
            stopped = None
            errors = []
            registry_path = self.root/'candidates.json'
            if not registry_path.exists():
                for cell in self.map_data()['rows']:
                    if cell['status'] in TERMINAL:
                        continue
                    if self.deadline is not None and time.monotonic() >= self.deadline:
                        stopped = 'wall budget reached'; break
                    try:
                        self._cell(cell['key'])
                    except ResourceStop as exc:
                        errors.append(dict(key=cell['key'], resource_blocked=str(exc)))
                    except BudgetStop as exc:
                        stopped = str(exc); break
                    except Exception as exc:
                        errors.append(dict(key=cell['key'], error=repr(exc)))
                    finally:
                        atomic_json(self.root/'map.json', self.map_data())
            data = self.map_data()
            atomic_json(self.root/'map.json', data)
            if data['protocol_resolved_cells'] == data['total_cells']:
                registry = freeze_candidates(self.root, self.catalog, data)
                if confirm:
                    for choice in registry['candidates']:
                        key = choice['key']
                        if key is None: continue
                        cache = self._sample(key)
                        folder = self.root/'cells'/key
                        try:
                            selection = read_json(folder/'pilot.json')
                            path = folder/'confirmation.json'
                            run_frozen(cache, selection, 'confirmation', journal=path,
                                       resume=path.exists())
                        except BudgetStop as exc:
                            stopped = str(exc); break
                        except Exception as exc:
                            errors.append(dict(key=key, phase='confirmation', error=repr(exc)))
                        finally:
                            self.new_runs += cache.new_runs
                            self.reused_runs += cache.reused_runs
            progress = dict(started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                            status='PAUSED' if stopped else 'ERRORS' if errors else 'SLICE_FINISHED',
                            stop_reason=stopped, errors=errors,
                            new_replications=self.new_runs, reused_replications=self.reused_runs,
                            total_cells=data['total_cells'], protocol_resolved_cells=data['protocol_resolved_cells'],
                            cells_with_10_main_seeds=data['cells_with_10_main_seeds'],
                            all_main_complete=data['all_main_complete'],
                            next_command='python scripts/run_r14_grid.py --out '+str(self.root)+' --wall-seconds 1200')
            atomic_json(self.root/'progress.json', progress)
            return progress
