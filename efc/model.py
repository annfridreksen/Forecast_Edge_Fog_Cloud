"""New discrete-event model, written from TASK.md, not the legacy simulator.

Times: seconds internally; exported delays: milliseconds. A Fog buffer holds
WAITING jobs; one additional job can be in service. FIFO drop-tail. All inputs
and results are synthetic. Network intervals model service, not protocol PHY.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import deque
import heapq
import math
import random
from typing import Iterable
import numpy as np

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


def simulate(config: Config = Config(), arrivals_s: Iterable[float] | None = None):
    """Generate arrivals or use an explicit trace; drain all admitted jobs.

    Causal event order: completions before arrivals at equal times; then task ID.
    Separate random streams protect paired comparisons from branch consumption.
    Rates/observed state are exported at Fog arrival, before own service.
    """
    c = config
    rng_a = random.Random(c.seed + 101)
    rng_zone = random.Random(c.seed + 211)
    rng_sensor = random.Random(c.seed + 307)
    rng_type = random.Random(c.seed + 401)
    rng_duration = random.Random(c.seed + 503)
    if arrivals_s is None:
        now = 0.; arrivals = []
        for _ in range(c.n_tasks):
            now += rng_a.expovariate(c.arrival_rate_s); arrivals.append(now)
    else:
        arrivals = list(arrivals_s)
        if len(arrivals) != c.n_tasks or any(not math.isfinite(t) or t < 0 for t in arrivals) or arrivals != sorted(arrivals):
            raise ValueError('arrivals must be ordered, finite, nonnegative and match n_tasks')
    zones = [list(range(f,c.n_edge,c.n_fog)) for f in range(c.n_fog)]
    weights = list(c.fog_weights) if c.fog_weights is not None else [len(z) for z in zones]
    mobile = [rng_type.random() < c.mobile_fraction for _ in range(c.n_edge)]
    edge_free = [0.] * c.n_edge; ef_free = [0.] * c.n_fog; fc_free = [0.] * c.n_fog
    cloud_free = [0.] * c.n_cloud
    waiting = [deque() for _ in range(c.n_fog)]
    active = [None] * c.n_fog
    busy_until = [0.] * c.n_fog
    last_arrival = [None] * c.n_fog; interval_ewma = [None] * c.n_fog
    counts = [0] * c.n_fog
    busy = {'edge_fog_s':[0.]*c.n_fog,'fog_s':[0.]*c.n_fog,
            'fog_cloud_s':[0.]*c.n_fog,'cloud_s':[0.]*c.n_cloud}
    queue_trace=[]; events=[]; tasks=[]
    for i,release in enumerate(arrivals):
        f = rng_zone.choices(range(c.n_fog), weights=weights, k=1)[0]
        sensor = rng_sensor.choice(zones[f])
        combined = rng_duration.uniform(*(c.edge_mobile_ms if mobile[sensor] else c.edge_fixed_ms))/1000
        ed = combined*c.edge_processing_share; ef = combined-ed
        fs = rng_duration.uniform(*c.fog_service_ms)/1000
        fc = rng_duration.uniform(*c.fog_cloud_ms)/1000
        cs = rng_duration.uniform(*c.cloud_service_ms)/1000
        edge_start=max(release,edge_free[sensor]); edge_end=edge_start+ed; edge_free[sensor]=edge_end
        link_start=max(edge_end,ef_free[f]); fa=link_start+ef; ef_free[f]=fa
        busy['edge_fog_s'][f]+=ef
        task=dict(task_id=i,sensor=sensor,fog=f,mobile=mobile[sensor],release_s=release,
                  edge_start_s=edge_start,edge_end_s=edge_end,fog_arrival_s=fa,
                  edge_ms=1000*(edge_end-release),edge_fog_ms=1000*(fa-edge_end),
                  edge_wait_ms=1000*(edge_start-release),ef_link_wait_ms=1000*(link_start-edge_end),
                  fog_service_ms=1000*fs,fc_service_ms=1000*fc,cloud_service_ms=1000*cs,
                  status='pending')
        tasks.append(task);heapq.heappush(events,(fa,1,i,'arrival'))
    def start_job(i,t):
        r=tasks[i];f=r['fog'];active[f]=i
        r['fog_start_s']=t;r['fog_wait_ms']=1000*(t-r['fog_arrival_s'])
        end=t+r['fog_service_ms']/1000;busy_until[f]=end
        busy['fog_s'][f]+=r['fog_service_ms']/1000
        heapq.heappush(events,(end,0,i,'done'))
    while events:
        t,_,i,kind=heapq.heappop(events);r=tasks[i];f=r['fog']
        if kind=='arrival':
            prior=last_arrival[f]
            if prior is not None and t>prior:
                gap=t-prior
                interval_ewma[f]=gap if interval_ewma[f] is None else .8*interval_ewma[f]+.2*gap
            last_arrival[f]=t;counts[f]+=1
            r['queue_before']=len(waiting[f]);r['busy_before']=int(active[f] is not None)
            r['remaining_busy_ms']=1000*max(0,busy_until[f]-t)
            r['observed_rate_s']=1/interval_ewma[f] if interval_ewma[f] else 0.
            r['rho_feature']=r['observed_rate_s']*sum(c.fog_service_ms)/2000
            if active[f] is None:
                start_job(i,t)
            elif len(waiting[f])<c.buffer:
                waiting[f].append(i)
            else:
                r['status']='dropped';r['drop_s']=t
        else:
            assert active[f]==i
            r['fog_end_s']=t
            link_start=max(t,fc_free[f]);ce=link_start+r['fc_service_ms']/1000;fc_free[f]=ce
            r['fog_cloud_ms']=1000*(ce-t);r['fc_link_wait_ms']=1000*(link_start-t)
            cloud=min(range(c.n_cloud),key=lambda j:(max(ce,cloud_free[j]),j))
            cloud_start=max(ce,cloud_free[cloud]);end=cloud_start+r['cloud_service_ms']/1000
            cloud_free[cloud]=end;r['cloud']=cloud;r['cloud_start_s']=cloud_start;r['end_s']=end
            r['cloud_ms']=1000*(end-ce);r['cloud_wait_ms']=1000*(cloud_start-ce)
            r['latency_ms']=1000*(end-r['release_s']);r['status']='completed'
            busy['fog_cloud_s'][f]+=r['fc_service_ms']/1000;busy['cloud_s'][cloud]+=r['cloud_service_ms']/1000
            active[f]=None;busy_until[f]=t
            if waiting[f]:start_job(waiting[f].popleft(),t)
        queue_trace.append({'time_s':t,'fog':f,'waiting':len(waiting[f]),'busy':int(active[f] is not None),'event':kind,'task_id':i})
    completed=[r for r in tasks if r['status']=='completed'];lost=[r for r in tasks if r['status']=='dropped']
    end=max([0.]+[r.get('end_s',r.get('drop_s',0)) for r in tasks])
    horizon=end if end>0 else 1.
    values=[r['latency_ms'] for r in completed]
    means={k:float(np.mean([r[k] for r in completed])) if completed else None for k in COMPONENTS}
    avg=float(np.mean(values)) if values else None
    metrics=dict(arrivals=len(tasks),completed=len(completed),dropped=len(lost),
                 drop_fraction=len(lost)/len(tasks) if tasks else 0.,mean_ms=avg,p95_ms=quantile95(values),
                 max_ms=max(values) if values else None,mean_fog_wait_ms=means['fog_wait_ms'],
                 arrival_window_s=arrivals[-1] if arrivals else 0.,drained_until_s=end,
                 deadline_3s_violations=sum(r['latency_ms']>3000 for r in completed),components_ms=means,
                 stage_shares_pct={'edge':100*(means['edge_ms']+means['edge_fog_ms'])/avg,
                                  'fog':100*(means['fog_wait_ms']+means['fog_service_ms']+means['fog_cloud_ms'])/avg,
                                  'cloud':100*means['cloud_ms']/avg} if avg else None,
                 utilization={k:[v/horizon for v in vv] for k,vv in busy.items()},
                 observations_per_fog=counts,units='ms for delays; seconds for calendars')
    return {'config':asdict(c),'metrics':metrics,'tasks':tasks,'queue_trace':queue_trace}
