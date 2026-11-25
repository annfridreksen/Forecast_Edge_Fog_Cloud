"""Predeclared one-factor sensitivities; no tuning to conference figures."""
from dataclasses import replace
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json,os
import numpy as np
import pandas as pd
from .model import Config,COMPONENTS
from .stationary import _job,aggregate,WARMUP,OBSERVE,SEEDS

def run_jobs(jobs,workers):
    if int(os.environ.get('FEFC_WORKERS',workers))==1:return [_job(x) for x in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:return list(pool.map(_job,jobs,chunksize=1))

def sensitivity_designs():
    base=replace(Config(n_cloud=40),arrival_rate_s=.70*50/.055)
    designs=[('edge_share',f'edge_share_{x}',replace(base,edge_processing_share=x)) for x in (.3,.5,.7)]
    designs += [('fog_cloud',f'fog_cloud_{sum(x)/2}',replace(base,fog_cloud_ms=x)) for x in ((10.,30.),(20.,50.),(30.,70.))]
    return designs

def sensitivity_series(output='results',workers=2):
    jobs=[(series,label,replace(c,seed=seed),WARMUP,OBSERVE) for series,label,c in sensitivity_designs() for seed in SEEDS]
    return summarize_sensitivity(run_jobs(jobs,workers),output)

def summarize_sensitivity(rows,output='results'):
    out=Path(output);out.mkdir(exist_ok=True,parents=True)
    raw=pd.DataFrame(rows);summary=aggregate(raw)
    for k in ('edge_processing_share','fog_cloud_mean_ms',*COMPONENTS):
        values=raw.groupby(['series','scenario'],sort=False)[k].mean()
        summary[k]=[values.loc[(r.series,r.scenario)] for r in summary.itertuples()]
    raw.to_csv(out/'sensitivity_replicates.csv',index=False);summary.to_csv(out/'sensitivity_summary.csv',index=False)
    details=json.loads((out/'configuration_details.json').read_text())
    metrics=next(r['metrics'] for r in details if r['scenario']=='baseline')
    means=metrics['components_ms'];total=metrics['mean_ms']
    component=pd.DataFrame([{'component':k,'mean_ms':means[k],'share_pct':100*means[k]/total} for k in COMPONENTS])
    levels=pd.DataFrame([{'level':'Edge','components':'edge_ms + edge_fog_ms','mean_ms':means['edge_ms']+means['edge_fog_ms']},
        {'level':'Fog','components':'fog_wait_ms + fog_service_ms + fog_cloud_ms','mean_ms':means['fog_wait_ms']+means['fog_service_ms']+means['fog_cloud_ms']},
        {'level':'Cloud','components':'cloud_ms','mean_ms':means['cloud_ms']}])
    levels['share_pct']=100*levels.mean_ms/total
    assert np.isclose(component.share_pct.sum(),100) and np.isclose(levels.share_pct.sum(),100)
    component.to_csv(out/'component_shares.csv',index=False);levels.to_csv(out/'level_shares.csv',index=False)
    return summary,raw

def sensitivity_plots(data,output='article/figures'):
    import matplotlib.pyplot as plt
    out=Path(output)
    for series,x,name,label in [('edge_share','edge_processing_share','sensitivity_edge','Доля обработки Edge'),('fog_cloud','fog_cloud_mean_ms','sensitivity_link','Среднее обслуживание Fog→Cloud, мс')]:
        part=data[data.series==series].sort_values(x);fig,ax=plt.subplots(figsize=(7,4))
        ax.errorbar(part[x],part.mean_ms,yerr=[part.mean_ms-part.mean_ms_ci_low,part.mean_ms_ci_high-part.mean_ms],fmt='o-',capsize=4,label='Сквозная задержка')
        if series=='edge_share':
            ax.plot(part[x],part.edge_ms,'s--',label='Edge: обработка + ожидание')
            ax.plot(part[x],part.edge_fog_ms,'^--',label='Edge→Fog: канал + ожидание')
        ax.set(xlabel=label,ylabel='Время, мс',title='Синтетическая чувствительность: ρ Fog=0,70; 10 seed');ax.grid(alpha=.25);ax.legend()
        fig.tight_layout();fig.savefig(out/(name+'.pdf'));fig.savefig(out/(name+'.png'),dpi=160);plt.show();plt.close(fig)

if __name__=='__main__':
    import time
    start=time.perf_counter();s,r=sensitivity_series();print(s.to_string(index=False));print('elapsed',time.perf_counter()-start)
