"""Fixed-window adapter to model.simulate; there is NO second queue scheduler.

R1.4 windows use the REFERENCE 50 Fog, not the selected configuration. This
module computes one replication, not a confidence interval or accepted map.
The old 18-scenario runner is disabled; its stored CSVs remain historical.
"""
from dataclasses import replace
from pathlib import Path
import math
import numpy as np
from scipy.stats import t as student_t
from . import model
from .model import Config, COMPONENTS
from .timebase import seconds_to_ticks, TICKS_PER_SECOND
from .workload import InputEvent, Workload, source_signature, generate_workload

RHO_GRID = (.10, .30, .50, .70, .85, .95)
SEEDS = tuple(range(10))
WARMUP, OBSERVE, GUARD = 2000, 4000, 1000
REFERENCE_FOG = 50
METRICS = ('mean_ms','p95_ms','max_ms','mean_fog_wait_ms','drop_fraction',
           'fog_utilization','cloud_utilization')


def clipped_busy(starts, ends, lo, hi):
    return np.maximum(0., np.minimum(ends, hi)-np.maximum(starts, lo))


def observation_window(config, warmup=WARMUP, observe=OBSERVE, guard=GUARD):
    """Counts per reference Fog are converted once to fixed absolute ticks."""
    if any(isinstance(x, bool) or not math.isfinite(x) or x <= 0
           for x in (warmup, observe, guard)):
        raise ValueError('positive finite window lengths required')
    unit = REFERENCE_FOG/config.arrival_rate_s
    lo, hi, stop = (seconds_to_ticks(x*unit)
                    for x in (warmup, warmup+observe, warmup+observe+guard))
    if not 0 < lo < hi < stop:
        raise ValueError('windows must have positive integer-clock lengths')
    return lo, hi, stop


def _non_fog_load_bounds(c):
    """Sufficient nominal load bounds, not measured busy fractions.

    Downstream traffic is bounded by the Fog service capacity as well as the
    offered stream; rho_F>1 with a finite waiting buffer is NOT rejected.
    These bounds assume the declared uniform source and independent services.
    """
    sizes = [len(range(f, c.n_edge, c.n_fog)) for f in range(c.n_fog)]
    rates = [c.arrival_rate_s*n/c.n_edge for n in sizes]
    profiles = ([c.edge_fixed_ms] if c.mobile_fraction == 0 else
                [c.edge_mobile_ms] if c.mobile_fraction == 1 else [c.edge_fixed_ms,c.edge_mobile_ms])
    combined = max(sum(x) for x in profiles)/2000
    fs, fc, cs = (sum(x)/2000 for x in
                  (c.fog_service_ms, c.fog_cloud_ms, c.cloud_service_ms))
    accepted_bound = [min(r, 1/fs) if fs else r for r in rates]
    return {'edge': c.arrival_rate_s/c.n_edge*combined*c.edge_processing_share,
            'edge_fog': max(rates)*combined*(1-c.edge_processing_share),
            'fog_cloud': max(accepted_bound)*fc,
            'cloud': sum(accepted_bound)*cs/c.n_cloud}


def _mean(values):
    return float(np.mean(values)) if values else None


def summarize_window(config, result, window):
    """Only observation/aggregation; all start/end times come from the kernel.

    Events drained after the guard are NOT used to certify this cohort: future
    input after the guard has not been generated. Extend the source horizon.
    """
    lo, hi, stop = window
    tasks = result['tasks']
    cohort = [r for r in tasks if lo <= r['release_tick'] < hi]
    completed = [r for r in cohort if r['status']=='completed' and r['end_tick'] <= stop]
    lost = [r for r in cohort if r['status']=='dropped' and r['drop_tick'] <= stop]
    pending = len(cohort)-len(completed)-len(lost)
    final = bool(cohort) and pending == 0
    values = [r['latency_ms'] for r in completed] if final else []
    means = {k: _mean([r[k] for r in completed]) if final else None for k in COMPONENTS}
    def occupancy(start, end, resources):
        ticks = sum(max(0, min(r[end], hi)-max(r[start], lo)) for r in tasks if start in r and end in r)
        return ticks/((hi-lo)*resources)
    row = {'seed':config.seed, 'rho_target':config.arrival_rate_s/config.n_fog*sum(config.fog_service_ms)/2000,
           'rho50':config.arrival_rate_s/REFERENCE_FOG*sum(config.fog_service_ms)/2000,
           'n_edge':config.n_edge, 'n_fog':config.n_fog, 'n_cloud':config.n_cloud, 'buffer':config.buffer,
           'arrival_rate_s':config.arrival_rate_s, 'reference_fog':REFERENCE_FOG,
           'warmup_s':lo/TICKS_PER_SECOND, 'observation_s':(hi-lo)/TICKS_PER_SECOND,
           'guard_s':(stop-hi)/TICKS_PER_SECOND,
           'window_ticks':{'start':lo,'end':hi,'guard_end':stop},
           'arrivals':len(cohort), 'completed':len(completed), 'dropped':len(lost), 'unfinished':pending,
           'cohort_complete':final, 'status':'COHORT_COMPLETE' if final else 'INSUFFICIENT_GUARD_OR_EMPTY',
           'drop_fraction':len(lost)/len(cohort) if final else None,
           'mean_ms':_mean(values), 'p95_ms':model.quantile95(values), 'max_ms':max(values) if values else None,
           'mean_fog_wait_ms':means['fog_wait_ms'],
           'H200':sum(r['latency_tick'] <= 200_000_000 for r in completed)/len(cohort) if final else None,
           'fog_utilization':occupancy('fog_start_tick','fog_end_tick',config.n_fog),
           'cloud_utilization':occupancy('cloud_start_tick','end_tick',config.n_cloud),
           'fog_arrival_rate_s':sum(lo <= r['fog_arrival_tick'] < hi for r in tasks)/((hi-lo)/TICKS_PER_SECOND)/config.n_fog,
           'edge_processing_share':config.edge_processing_share, 'fog_cloud_mean_ms':sum(config.fog_cloud_ms)/2,
           'workload_sha256':result['workload']['sha256'], 'kernel':'efc.model.simulate',
           'statistical_acceptance':'NOT_EVALUATED_SINGLE_REPLICATION'}
    row.update(means)
    mid = (lo+hi)//2
    for label, predicate in (('first', lambda r:r['release_tick']<mid),
                             ('second', lambda r:r['release_tick']>=mid)):
        part = [r for r in cohort if predicate(r)]
        done = [r['latency_ms'] for r in completed if predicate(r)] if final else []
        row[label+'_mean_ms'] = _mean(done)
        row[label+'_p95_ms'] = model.quantile95(done)
        row[label+'_drop_fraction'] = sum(predicate(r) for r in lost)/len(part) if final and part else None
    return row


def stationary_run(config, warmup=WARMUP, observe=OBSERVE, guard=GUARD,
                   *, workload=None, return_details=False, compact=False, record_queue=True):
    """One fixed-window replication, using exactly the demonstration kernel.

    Supplied sources require the same declared generation horizon. Length is
    inferred for the kernel; n_tasks is not a fixed-time observation criterion.
    No claim of stationary accuracy/CI follows from this one adapter call.
    """
    window = observation_window(config, warmup, observe, guard)
    bounds = _non_fog_load_bounds(config)
    if any(v >= 1 for v in bounds.values()):
        raise ValueError('no sufficient stability margin for unbounded queues: '+str(bounds))
    if workload is None:
        # Decimal text avoids re-rounding an already quantized horizon via float.
        seconds = f'{window[2]//TICKS_PER_SECOND}.{window[2]%TICKS_PER_SECOND:09d}'
        workload = generate_workload(config, stop_s=seconds)
    if workload.horizon_tick != window[2]:
        raise ValueError('workload horizon must equal declared guard end')
    actual = replace(config, n_tasks=len(workload.events))
    result = model.simulate(actual, workload=workload, compact=compact, record_queue=record_queue)
    row = summarize_window(config, result, window)
    row.update(warmup_expected_per_reference_fog=warmup, observation_expected_per_reference_fog=observe,
               guard_expected_per_reference_fog=guard, non_fog_load_bounds=bounds)
    return (row, result) if return_details else row


def fifo_fog(arrival, service, fog, n_fog, buffer):
    """Legacy test adapter only: zero other services, SAME kernel, no scheduler.

    Output positions follow the original input order. New experiments must
    supply complete workloads and use stationary_run/simulate instead.
    """
    if len(arrival) != len(service) or len(arrival) != len(fog):
        raise ValueError('input lengths differ')
    order = sorted(range(len(arrival)), key=lambda i:(seconds_to_ticks(arrival[i]),i))
    c = Config(n_edge=n_fog, n_fog=n_fog, n_cloud=1, buffer=buffer, n_tasks=len(order),
               mobile_fraction=0, edge_fixed_ms=(0,0), fog_service_ms=(0,0),
               fog_cloud_ms=(0,0), cloud_service_ms=(0,0))
    if any(isinstance(f, (bool,np.bool_)) or int(f) != f or not 0 <= f < n_fog for f in fog):
        raise ValueError('invalid Fog index')
    events = tuple(InputEvent(j,seconds_to_ticks(arrival[i]),int(fog[i]),False,
                             0,0,seconds_to_ticks(service[i]),0,0) for j,i in enumerate(order))
    result = model.simulate(c, workload=Workload(events,source_signature(c)))
    start = np.full(len(order),np.nan); end = start.copy(); q = np.zeros(len(order),dtype=np.int32)
    for i,r in zip(order,result['tasks']):
        q[i] = r['queue_before']
        if r['status']=='completed':
            start[i]=r['fog_start_s']; end[i]=r['fog_end_s']
    return start,end,q


def scenarios():
    """Approved R1.4 grid; enumerating it does not run experiments."""
    base=Config(n_cloud=40,seed=0)
    return [('configuration',f'rho_{rho:.2f}_fog_{f}_B_{b}',
             replace(base,n_fog=f,buffer=b,arrival_rate_s=rho*50/.055))
            for rho in RHO_GRID for f in (30,40,50,60,70)
            for b in (0,2,5,10,20,50,100,200,400)]


def ci95(values):
    """Legacy replicate-mean diagnostic, NOT the R1.4 pooled-p95 decision CI."""
    v=np.asarray(values,dtype=float)
    if len(v)<2 or not np.isfinite(v).all():
        raise ValueError('CI needs independent finite replications')
    mean=float(v.mean()); half=float(student_t.ppf(.975,len(v)-1)*v.std(ddof=1)/math.sqrt(len(v)))
    return mean,mean-half,mean+half


def _job(args):
    series,label,c,warm,observe=args
    return {'series':series,'scenario':label,**stationary_run(c,warm,observe)}


def aggregate(*args, **kwargs):
    raise NotImplementedError('R1.4 pooled cluster-bootstrap acceptance is not implemented; legacy t summary is disabled')


def stationary_series(*args, **kwargs):
    raise NotImplementedError('R1.4 pilot/grid/confirmation controller not implemented; no legacy series may certify it')
