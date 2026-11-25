"""Bounded engineering measurement of the current common kernel/storage.

This does not select scientific windows or classify a configuration. Cache is
separate from the scientific map and makes repeated probes reuse data explicitly.
"""
import argparse,json,os,platform,resource,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from efc.model import Config
from efc.primary import PrimarySampler
from efc.grid import CachedSampler,atomic_json,exclusive

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--warmup',type=int,default=16000);p.add_argument('--observe',type=int,default=32000)
    p.add_argument('--guard',type=int,default=16000);p.add_argument('--check-only',action='store_true')
    a=p.parse_args()
    if min(a.warmup,a.observe,a.guard)<1 or sum((a.warmup,a.observe,a.guard))>64000:p.error('invalid engineering window')
    c=Config(n_cloud=40,n_fog=70,buffer=400,arrival_rate_s=.95*50/.055)
    s=PrimarySampler(c)
    if a.check_only:
        print(json.dumps(dict(config_id=s.config_id,expected_events=50*(a.warmup+a.observe+a.guard),executed=False)));return
    limit=6*1024**3;resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    report=dict(status='RUNNING',scope='engineering probe, NOT scientific map',python=platform.python_version(),
                config_id=s.config_id,W=a.warmup,T=a.observe,G=a.guard,rlimit_as_bytes=limit,
                expected_events=50*(a.warmup+a.observe+a.guard),execution='Actions' if os.getenv('GITHUB_ACTIONS') else 'local Python')
    t=time.perf_counter()
    with exclusive(a.out):
        cache=CachedSampler(s,a.out)
        try:
            o=cache(100,a.warmup,a.observe,a.guard)
            report.update(status='PASS',arrivals=o.full.arrivals,dropped=o.full.dropped,unfinished=o.full.unfinished,
                          primary_summary=o.provenance['primary_summary'])
        except Exception as e:report.update(status='FAILED',error=repr(e));raise
        finally:
            report.update(elapsed_wall_seconds=time.perf_counter()-t,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          new_replications=cache.new_runs,reused_replications=cache.reused_runs)
            atomic_json(a.out/'probe.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
