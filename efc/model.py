"""New discrete-event model, written from TASK.md, not the legacy simulator.

Times: integer nanoseconds internally; exported seconds/milliseconds. A Fog buffer holds
WAITING jobs; one additional job can be in service. FIFO drop-tail. All inputs
and results are synthetic. Network intervals model service, not protocol PHY.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import deque
import heapq
import math
from typing import Iterable
import numpy as np
from .timebase import TIME_CONTRACT
from .workload import generate_workload, Workload

COMPONENTS = ('edge_ms', 'edge_fog_ms', 'fog_wait_ms', 'fog_service_ms',
              'fog_cloud_ms', 'cloud_ms')

@dataclass(frozen=True)
class Config:
    n_edge: int = 1000
    n_fog: int = 50
    n_cloud: int = 8
    buffer: int = 400                 # waiting slots, K = buffer + 1
    n_tasks: int = 200
    arrival_rate_s: float = 400 / 3600 # total system rate, not per sensor
    mobile_fraction: float = 0.30
    edge_fixed_ms: tuple = (5., 15.)   # combined processing + transmission
    edge_mobile_ms: tuple = (8., 20.)
    edge_processing_share: float = 0.5
    fog_service_ms: tuple = (30., 80.)
    fog_cloud_ms: tuple = (20., 50.)   # explicit new assumption
    cloud_service_ms: tuple = (10., 30.)
    fog_weights: tuple | None = None
    seed: int = 42

    def __post_init__(self):
        for name in ('n_edge','n_fog','n_cloud','buffer','n_tasks'):
            value = getattr(self, name)
            if type(value) is not int or value < (1 if name.startswith('n_') and name != 'n_tasks' else 0):
                raise ValueError(f'{name}: invalid nonnegative/positive integer')
        if self.n_edge < self.n_fog:
            raise ValueError('each zone must have at least one sensor')
        if type(self.seed) is not int:
            raise ValueError('seed must be integer')
        if not math.isfinite(self.arrival_rate_s) or self.arrival_rate_s <= 0:
            raise ValueError('arrival_rate_s must be positive and finite')
        if not 0 <= self.mobile_fraction <= 1 or not 0 <= self.edge_processing_share <= 1:
            raise ValueError('invalid fraction')
        for name in ('edge_fixed_ms','edge_mobile_ms','fog_service_ms','fog_cloud_ms','cloud_service_ms'):
            bounds = getattr(self,name)
            if len(bounds) != 2 or any(not math.isfinite(x) or x < 0 for x in bounds) or bounds[1] < bounds[0]:
                raise ValueError(f'{name}: invalid range')
        if self.fog_weights is not None:
            if (len(self.fog_weights) != self.n_fog or
                any(not math.isfinite(x) or x < 0 for x in self.fog_weights) or sum(self.fog_weights) <= 0):
                raise ValueError('invalid zone weights')


def quantile95(values):
    """Empirical linear quantile, NumPy method='linear'; not a guarantee."""
    return None if not values else float(np.quantile(values, .95, method='linear'))


def simulate(config: Config = Config(), arrivals_s: Iterable[float] | None = None,
             *, workload: Workload | None = None):
    """Single integer-clock kernel for the demonstration and windowed series.

    Source messages and ALL potential durations precede assignment/execution.
    A supplied workload is authoritative but must match the source profile and
    n_tasks. Fog/Cloud counts and B may differ. No random draws occur in service.
    Exported *_s/*_ms fields are views; integer *_tick fields are authoritative.
    """
    c = config
    if workload is not None and arrivals_s is not None:
        raise ValueError('provide either workload or arrivals_s, not both')
    if workload is None:
        workload = generate_workload(c, arrivals_s=arrivals_s)
    workload.validate_for(c)
    if len(workload.events) != c.n_tasks:
        raise ValueError('workload length must match n_tasks')
    edge_free = [0]*c.n_edge
    ef_free = [0]*c.n_fog
    fc_free = [0]*c.n_fog
    cloud_free = [0]*c.n_cloud
    waiting = [deque() for _ in range(c.n_fog)]
    active = [None]*c.n_fog
    busy_until = [0]*c.n_fog
    last_arrival = [None]*c.n_fog
    interval_ewma = [None]*c.n_fog
    counts = [0]*c.n_fog
    busy = {'edge_fog_s': [0]*c.n_fog, 'fog_s': [0]*c.n_fog,
            'fog_cloud_s': [0]*c.n_fog, 'cloud_s': [0]*c.n_cloud}
    queue_trace, events, tasks = [], [], []
    for source in workload.events:
        i, release, sensor = source.event_id, source.release_tick, source.sensor
        f = sensor % c.n_fog
        edge_start = max(release, edge_free[sensor])
        edge_end = edge_start + source.edge_service_tick
        edge_free[sensor] = edge_end
        tasks.append(dict(source.record(), task_id=i, fog=f,
                          edge_start_tick=edge_start, edge_end_tick=edge_end,
                          edge_delay_tick=edge_end-release, edge_wait_tick=edge_start-release,
                          status='pending'))
        heapq.heappush(events, (edge_end, 1, i, 'edge_done'))

    def start_job(i, tick):
        r = tasks[i]
        f = r['fog']
        active[f] = i
        r['fog_start_tick'] = tick
        r['fog_wait_tick'] = tick-r['fog_arrival_tick']
        end = tick+r['fog_service_tick']
        busy_until[f] = end
        busy['fog_s'][f] += r['fog_service_tick']
        heapq.heappush(events, (end, 0, i, 'done'))

    while events:
        tick, _, i, kind = heapq.heappop(events)
        r = tasks[i]
        f = r['fog']
        if kind == 'edge_done':
            start = max(tick, ef_free[f])
            fa = start+r['ef_service_tick']
            ef_free[f] = fa
            busy['edge_fog_s'][f] += r['ef_service_tick']
            r.update(fog_arrival_tick=fa, edge_fog_tick=fa-tick, ef_link_wait_tick=start-tick)
            heapq.heappush(events, (fa, 2, i, 'arrival'))
            continue
        if kind == 'cloud_arrival':
            cloud = min(range(c.n_cloud), key=lambda j: (max(tick, cloud_free[j]), j))
            start = max(tick, cloud_free[cloud])
            end = start+r['cloud_service_tick']
            cloud_free[cloud] = end
            r.update(cloud=cloud, cloud_start_tick=start, end_tick=end,
                     cloud_tick=end-tick, cloud_wait_tick=start-tick,
                     latency_tick=end-r['release_tick'], status='completed')
            busy['cloud_s'][cloud] += r['cloud_service_tick']
            continue
        if kind == 'arrival':
            prior = last_arrival[f]
            if prior is not None and tick > prior:
                gap_s = (tick-prior)/1_000_000_000
                interval_ewma[f] = gap_s if interval_ewma[f] is None else .8*interval_ewma[f]+.2*gap_s
            last_arrival[f] = tick
            counts[f] += 1
            r['queue_before'] = len(waiting[f])
            r['busy_before'] = int(active[f] is not None)
            r['remaining_busy_tick'] = max(0, busy_until[f]-tick)
            r['observed_rate_s'] = 1/interval_ewma[f] if interval_ewma[f] else 0.
            r['rho_feature'] = r['observed_rate_s']*sum(c.fog_service_ms)/2000
            if active[f] is None:
                start_job(i, tick)
            elif len(waiting[f]) < c.buffer:
                waiting[f].append(i)
            else:
                r.update(status='dropped', drop_tick=tick)
        else:
            assert active[f] == i
            r['fog_end_tick'] = tick
            start = max(tick, fc_free[f])
            ce = start+r['fc_service_tick']
            fc_free[f] = ce
            r.update(fog_cloud_tick=ce-tick, fc_link_wait_tick=start-tick, cloud_arrival_tick=ce)
            busy['fog_cloud_s'][f] += r['fc_service_tick']
            heapq.heappush(events, (ce, 3, i, 'cloud_arrival'))
            active[f] = None
            busy_until[f] = tick
            if waiting[f]:
                start_job(waiting[f].popleft(), tick)
        queue_trace.append(dict(time_tick=tick, time_s=tick/1_000_000_000, fog=f,
                                waiting=len(waiting[f]), busy=int(active[f] is not None),
                                event=kind, task_id=i))
    timestamp_names = ('release', 'edge_start', 'edge_end', 'fog_arrival', 'fog_start',
                       'fog_end', 'cloud_arrival', 'cloud_start', 'end', 'drop')
    delay_names = {'edge_ms': 'edge_delay_tick', 'edge_fog_ms': 'edge_fog_tick',
                   'fog_wait_ms': 'fog_wait_tick', 'fog_service_ms': 'fog_service_tick',
                   'fog_cloud_ms': 'fog_cloud_tick', 'cloud_ms': 'cloud_tick',
                   'latency_ms': 'latency_tick', 'edge_wait_ms': 'edge_wait_tick',
                   'ef_service_ms': 'ef_service_tick', 'fc_service_ms': 'fc_service_tick',
                   'cloud_service_ms': 'cloud_service_tick', 'ef_link_wait_ms': 'ef_link_wait_tick',
                   'fc_link_wait_ms': 'fc_link_wait_tick', 'cloud_wait_ms': 'cloud_wait_tick',
                   'remaining_busy_ms': 'remaining_busy_tick'}
    for r in tasks:
        for name in timestamp_names:
            if name+'_tick' in r:
                r[name+'_s'] = r[name+'_tick']/1_000_000_000
        for field, source in delay_names.items():
            if source in r:
                r[field] = r[source]/1_000_000
    completed = [r for r in tasks if r['status'] == 'completed']
    lost = [r for r in tasks if r['status'] == 'dropped']
    end = max([0]+[r.get('end_tick', r.get('drop_tick', 0)) for r in tasks])
    horizon = end if end > 0 else 1
    values = [r['latency_ms'] for r in completed]
    means = {k: float(np.mean([r[k] for r in completed])) if completed else None for k in COMPONENTS}
    avg = float(np.mean(values)) if values else None
    metrics = dict(arrivals=len(tasks), completed=len(completed), dropped=len(lost),
                   drop_fraction=len(lost)/len(tasks) if tasks else 0.,
                   mean_ms=avg, p95_ms=quantile95(values), max_ms=max(values) if values else None,
                   mean_fog_wait_ms=means['fog_wait_ms'],
                   arrival_window_s=workload.events[-1].release_tick/1_000_000_000 if tasks else 0.,
                   drained_until_s=end/1_000_000_000,
                   deadline_3s_violations=sum(r['latency_tick'] > 3_000_000_000 for r in completed),
                   components_ms=means,
                   stage_shares_pct={'edge': 100*(means['edge_ms']+means['edge_fog_ms'])/avg,
                                     'fog': 100*(means['fog_wait_ms']+means['fog_service_ms']+means['fog_cloud_ms'])/avg,
                                     'cloud': 100*means['cloud_ms']/avg} if avg else None,
                   utilization={k: [v/horizon for v in vv] for k, vv in busy.items()},
                   observations_per_fog=counts, units='ms for delays; seconds for exported calendars')
    return {'config': asdict(c), 'timing': dict(TIME_CONTRACT), 'metrics': metrics,
            'workload': workload.metadata(), 'tasks': tasks, 'queue_trace': queue_trace}
