"""Replicated steady-input tandem queues; synthetic, not conference measurements.

A feed-forward network is evaluated in causal arrival order at each stage.
This is equivalent to FIFO discrete-event service for this acyclic topology;
there is no feedback, preemption, or placement decision in these series.
All 50 Fog queues and every configured resource are represented separately.
"""
from dataclasses import asdict, replace
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import heapq
import json
import math
import os
import numpy as np
import pandas as pd
from scipy.stats import t as student_t
from .model import Config, COMPONENTS
from .forecast.models import mm1k

RHO_GRID=(.10,.30,.50,.70,.85,.95)
SEEDS=tuple(range(10))
WARMUP=2000
OBSERVE=4000
GUARD=1000

def clipped_busy(starts, ends, lo, hi):
    return np.maximum(0.,np.minimum(ends,hi)-np.maximum(starts,lo))

def fifo_fog(arrival, service, fog, n_fog, buffer):
    """Finite waiting buffer B; K=B+1 includes the in-service job."""
    order=np.argsort(arrival,kind='stable');start=np.full(len(arrival),np.nan)
    end=start.copy();q_before=np.zeros(len(arrival),dtype=np.int32)
    calendars=[deque() for _ in range(n_fog)]
    for i in order:
        q=calendars[int(fog[i])];a=arrival[i]
        while q and q[0]<=a:q.popleft()
        q_before[i]=max(0,len(q)-1)
        if len(q)>=buffer+1:continue
        s=max(a,q[-1]) if q else a
        start[i]=s;end[i]=s+service[i];q.append(end[i])
    return start,end,q_before

def stationary_run(config, warmup=WARMUP, observe=OBSERVE, guard=GUARD):
    """Fixed-time warm-up, measurement and guard; no drain-biased means.

    Durations are specified in expected arrivals PER FOG. Measurement selects
    the external-arrival cohort. All events are simulated through a guard and
    then drained; any cohort still unfinished by the guard boundary is flagged.
    Resource occupancy is integrated over the measurement interval only.
    """
    c=config
    if min(warmup,observe,guard)<=0:raise ValueError('positive window lengths required')
    if c.fog_weights is not None:raise ValueError('stationary series require uniform zone probabilities')
    per_fog=c.arrival_rate_s/c.n_fog
    service_mean=sum(c.fog_service_ms)/2000
    rho=per_fog*service_mean
    if not 0<rho<1:raise ValueError('offered Fog load must be between zero and one')
    fc_rho=per_fog*sum(c.fog_cloud_ms)/2000
    cloud_rho=c.arrival_rate_s*sum(c.cloud_service_ms)/2000/c.n_cloud
    if max(fc_rho,cloud_rho)>=1:raise ValueError('downstream stage would be unstable')
    lo=warmup/per_fog;hi=lo+observe/per_fog;stop=hi+guard/per_fog
    rng=np.random.default_rng(np.random.SeedSequence([c.seed,20261122]))
    # Uniform order statistics conditional on a Poisson count give exactly a
    # homogeneous Poisson process over the full fixed observation horizon.
    n=int(rng.poisson(c.arrival_rate_s*stop));release=np.sort(rng.uniform(0,stop,n))
    fog=rng.integers(0,c.n_fog,n,dtype=np.int32)
    sensors=np.arange(c.n_edge);mobile_type=rng.random(c.n_edge)<c.mobile_fraction
    zone_sizes=np.array([len(sensors[f::c.n_fog]) for f in range(c.n_fog)])
    sensor=fog+c.n_fog*(rng.random(n)*zone_sizes[fog]).astype(int)
    mobile=mobile_type[sensor]
    lower=np.where(mobile,c.edge_mobile_ms[0],c.edge_fixed_ms[0])/1000
    upper=np.where(mobile,c.edge_mobile_ms[1],c.edge_fixed_ms[1])/1000
    combined=lower+(upper-lower)*rng.random(n)
    ed=combined*c.edge_processing_share;ef=combined-ed
    fs=rng.uniform(*c.fog_service_ms,n)/1000
    fc=rng.uniform(*c.fog_cloud_ms,n)/1000
    cs=rng.uniform(*c.cloud_service_ms,n)/1000
    edge_start=np.empty(n);edge_end=np.empty(n);free=np.zeros(c.n_edge)
    for i in range(n):
        d=sensor[i];edge_start[i]=max(release[i],free[d]);edge_end[i]=edge_start[i]+ed[i];free[d]=edge_end[i]
    ef_start=np.empty(n);fa=np.empty(n);free=np.zeros(c.n_fog)
    for i in np.argsort(edge_end,kind='stable'):
        d=fog[i];ef_start[i]=max(edge_end[i],free[d]);fa[i]=ef_start[i]+ef[i];free[d]=fa[i]
    fstart,fend,q=fifo_fog(fa,fs,fog,c.n_fog,c.buffer)
    accepted=np.flatnonzero(np.isfinite(fend))
    fc_start=np.full(n,np.nan);ca=fc_start.copy();free=np.zeros(c.n_fog)
    for i in accepted[np.argsort(fend[accepted],kind='stable')]:
        d=fog[i];fc_start[i]=max(fend[i],free[d]);ca[i]=fc_start[i]+fc[i];free[d]=ca[i]
    cloud_start=np.full(n,np.nan);end=cloud_start.copy();servers=[(0.,d) for d in range(c.n_cloud)];heapq.heapify(servers)
    for i in accepted[np.argsort(ca[accepted],kind='stable')]:
        available,d=heapq.heappop(servers);cloud_start[i]=max(ca[i],available);end[i]=cloud_start[i]+cs[i];heapq.heappush(servers,(end[i],d))
    cohort=(release>=lo)&(release<hi);completed=cohort&np.isfinite(end);lost=cohort&~np.isfinite(end)
    if np.any(end[completed]>=stop):raise RuntimeError('guard insufficient for measurement cohort; extend and rerun')
    a=np.flatnonzero(completed);latency=(end[a]-release[a])*1000
    components=np.column_stack([edge_end[a]-release[a],fa[a]-edge_end[a],fstart[a]-fa[a],fs[a],ca[a]-fend[a],end[a]-ca[a]])*1000
    assert np.allclose(components.sum(axis=1),latency,atol=1e-7)
    window=hi-lo
    util_fog=clipped_busy(fstart[accepted],fend[accepted],lo,hi).sum()/(window*c.n_fog)
    util_cloud=clipped_busy(cloud_start[accepted],end[accepted],lo,hi).sum()/(window*c.n_cloud)
    row={'seed':c.seed,'rho_target':rho,'n_edge':c.n_edge,'n_fog':c.n_fog,'n_cloud':c.n_cloud,'buffer':c.buffer,
         'arrival_rate_s':c.arrival_rate_s,'warmup_s':lo,'observation_s':window,'guard_s':stop-hi,
         'warmup_expected_per_fog':warmup,'observation_expected_per_fog':observe,'guard_expected_per_fog':guard,
         'arrivals':int(cohort.sum()),'completed':int(completed.sum()),'dropped':int(lost.sum()),
         'mean_ms':float(latency.mean()),'p95_ms':float(np.quantile(latency,.95)),
         'max_ms':float(latency.max()),'mean_fog_wait_ms':float(components[:,2].mean()),
         'drop_fraction':float(lost.sum()/cohort.sum()),'fog_utilization':float(util_fog),'cloud_utilization':float(util_cloud),
         'fog_arrival_rate_s':float(((fa>=lo)&(fa<hi)).sum()/window/c.n_fog),
         'edge_processing_share':c.edge_processing_share,'fog_cloud_mean_ms':sum(c.fog_cloud_ms)/2}
    row.update(dict(zip(COMPONENTS,components.mean(axis=0).tolist())))
    mid=(lo+hi)/2
    for label,mask in [('first',release[a]<mid),('second',release[a]>=mid)]:
        row[label+'_mean_ms']=float(latency[mask].mean())
        row[label+'_p95_ms']=float(np.quantile(latency[mask],.95))
    return row

def scenarios():
    # Cloud=40 is a documented diagnostic capacity, not the 8-server baseline.
    # At rho=.95 the offered Cloud load is .432, so Fog is studied without
    # accidentally building an unstable Cloud queue.
    base=Config(n_cloud=40,seed=0)
    cases=[]
    for rho in RHO_GRID:
        cases.append(('intensity',f'rho_{rho:.2f}',replace(base,arrival_rate_s=rho*50/.055)))
    # Fixed per-sensor rate: rho=.95 at 40 sensors/Fog, .2375 at 10.
    for ratio in (10,15,20,25,30,35,40):
        cases.append(('ratio',f'ratio_{ratio}',replace(base,n_edge=50*ratio,arrival_rate_s=(.95/.055/40)*50*ratio)))
    for capacity in (20,50,100,200,400):
        cases.append(('buffer',f'buffer_{capacity}',replace(base,buffer=capacity,arrival_rate_s=.95*50/.055)))
    return cases

def ci95(values):
    v=np.asarray(values,dtype=float)
    if len(v)<2 or not np.isfinite(v).all():raise ValueError('CI needs independent finite replications')
    mean=float(v.mean());half=float(student_t.ppf(.975,len(v)-1)*v.std(ddof=1)/math.sqrt(len(v)))
    return mean,mean-half,mean+half

METRICS=('mean_ms','p95_ms','max_ms','mean_fog_wait_ms','drop_fraction','fog_utilization','cloud_utilization')

def aggregate(frame,group=('series','scenario')):
    rows=[]
    for keys,part in frame.groupby(list(group),sort=False):
        keys=(keys,) if not isinstance(keys,tuple) else keys
        row=dict(zip(group,keys));row['n_seeds']=part.seed.nunique()
        if row['n_seeds']!=len(part):raise ValueError('seed repeated within scenario')
        for k in ('rho_target','n_edge','n_fog','n_cloud','buffer','arrival_rate_s','warmup_s','observation_s','warmup_expected_per_fog','observation_expected_per_fog'):
            row[k]=part.iloc[0][k]
        for metric in METRICS:
            mean,lo,hi=ci95(part[metric]);row.update({metric:mean,metric+'_ci_low':lo,metric+'_ci_high':hi})
        # Maxima are averaged per fixed-length replication, never a population bound.
        for metric in ('mean_ms','p95_ms'):
            diff=part['second_'+metric]-part['first_'+metric]
            mean,lo,hi=ci95(diff);row.update({'half_difference_'+metric:mean,'half_difference_'+metric+'_ci_low':lo,'half_difference_'+metric+'_ci_high':hi})
        analytical=mm1k(row['arrival_rate_s']/row['n_fog'],.055,int(row['buffer'])+1)
        row['MM1K_wait_ms']=(analytical['W_s']-.055)*1000
        rows.append(row)
    return pd.DataFrame(rows)

def _job(args):
    series,label,c,warm,observe=args
    return {'series':series,'scenario':label,**stationary_run(c,warm,observe)}

def stationary_series(output='results',seeds=SEEDS,workers=2,warmup=WARMUP,observe=OBSERVE):
    if len(set(seeds))<10:raise ValueError('at least ten independent seeds required')
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    jobs=[(series,label,replace(c,seed=int(seed)),warmup,observe) for series,label,c in scenarios() for seed in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:rows=list(pool.map(_job,jobs,chunksize=1))
    raw=pd.DataFrame(rows);raw.to_csv(out/'stationary_replicates.csv',index=False)
    summary=aggregate(raw);summary.to_csv(out/'stationary_summary.csv',index=False)
    # Fixed longer-warm-up check, not chosen after seeing a favourable result.
    c=replace(Config(n_cloud=40),arrival_rate_s=.95*50/.055)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        extra=list(pool.map(_job,[('warmup','rho_0.95_double_warmup',replace(c,seed=int(seed)),2*warmup,observe) for seed in seeds]))
    pd.DataFrame(extra).to_csv(out/'warmup_replicates.csv',index=False)
    base=raw[(raw.series=='intensity')&(raw.scenario=='rho_0.95')].sort_values('seed')
    longer=pd.DataFrame(extra).sort_values('seed');diagnostic={}
    for metric in ('mean_ms','p95_ms','mean_fog_wait_ms'):
        vals=longer[metric].to_numpy()-base[metric].to_numpy();m,lo,hi=ci95(vals)
        diagnostic[metric]={'long_minus_default':m,'ci_low':lo,'ci_high':hi}
    metadata={'regime':'constant Poisson input, finite uniform-service FIFO after warmup',
      'seeds':list(seeds),'rho_grid':RHO_GRID,'n_fog':50,'n_cloud':40,
      'warmup_expected_arrivals_per_fog':warmup,'measurement_expected_arrivals_per_fog':observe,
      'guard_expected_arrivals_per_fog':GUARD,'replications':len(rows),
      'ci':'two-sided Student t across independent seed estimates; max is mean finite-window maximum',
      'warmup_check':diagnostic,'stationarity_claim':'time-homogeneous stable offered load; finite warmup diagnostics are not a proof of exact stationarity',
      'analytical':'M/M/1/K uses exponential service; simulator is uniform-service tandem, curves are not expected to coincide',
      'all_inputs':'synthetic; original 400/hour baseline unchanged; no parameter tuning to conference figures'}
    (out/'stationary_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    assert (raw.completed+raw.dropped==raw.arrivals).all()
    assert raw.mean_fog_wait_ms.min()>0
    assert summary.groupby('series').mean_fog_wait_ms.nunique().min()>1
    return summary,raw
