"""One bounded R1.4 night request; immutable checkpoints and no auto-commit."""
from pathlib import Path
from datetime import datetime, timezone
import json, os, platform, resource, shutil, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from efc.grid import GridRunner, CachedSampler, atomic_json, exclusive
from efc.primary import PrimarySampler

def validate_request(request):
    if request['mode'] not in ('probe','slice'):
        raise ValueError('unknown mode')
    budget=request['wall_seconds']; ceiling=request['max_expected_events']
    if (isinstance(budget,bool) or not isinstance(budget,(int,float))
        or not 0 < budget <= 1500 or type(ceiling) is not int
        or not 350000 <= ceiling <= 1100000):
        raise ValueError('invalid resource budget')
    return budget,ceiling


def main():
    request=json.loads((ROOT/'configs/r14-night-run.json').read_text())
    budget,ceiling=validate_request(request)
    out=ROOT/'results/r14/night-map';out.mkdir(parents=True,exist_ok=True)
    stamp=os.environ.get('GITHUB_RUN_ID','local')
    report=dict(status='RUNNING',request=request,
        utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        total_ram_bytes=os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES'),
        colab_ui_tested=False,full_map_claim=False)
    limit=min(6*1024**3, report['total_ram_bytes']//2)
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    report['address_space_limit_bytes']=limit
    t=time.perf_counter()
    try:
        runner=GridRunner(out,factory=PrimarySampler,wall_seconds=budget,max_expected_events=ceiling)
        if request['mode']=='probe':
            with exclusive(out):
                runner._bind()
                key=runner.catalog[0]['key']
                sample=runner._sample(key)
                obs=sample(100,2000,4000,1000)
                report.update(status='PROBE_COMPLETE',cell_key=key,seed=100,
                    warmup=2000,observe=4000,guard=1000,
                    cohort_arrivals=obs.full.arrivals,dropped=obs.full.dropped,
                    unfinished=obs.full.unfinished,new_replications=sample.new_runs,
                    reused_replications=sample.reused_runs,config_id=sample.config_id,
                    provenance=obs.provenance)
                atomic_json(out/'map.json',runner.map_data())
        else:
            result=runner.run(confirm=False)
            report.update(status=result['status'],progress=result)
    except Exception as exc:
        report.update(status='FAILED',error=repr(exc));raise
    finally:
        report.update(elapsed_wall_seconds=time.perf_counter()-t,
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            disk_free_bytes=shutil.disk_usage(out).free,
            checkpoint_files=sum(1 for _ in out.glob('observations/*/*.json.gz')))
        atomic_json(out/'runs'/(stamp+'.json'),report)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 1 if report['status']=='ERRORS' else 0
if __name__=='__main__':raise SystemExit(main())
