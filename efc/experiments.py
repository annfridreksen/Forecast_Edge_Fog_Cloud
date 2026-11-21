"""Fixed, explicitly synthetic series; no calibration to conference results."""
from pathlib import Path
from dataclasses import replace
import json
import pandas as pd
from .model import Config,simulate


def configuration_series(output='results'):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    base=Config()
    series=[('baseline',base)]
    series += [(f'edge_{n}',replace(base,n_edge=n,arrival_rate_s=base.arrival_rate_s*n/1000)) for n in [1250,1500,1750,2000]]
    series += [(f'cloud_{n}',replace(base,n_cloud=n)) for n in [16,24]]
    series += [('fog_75',replace(base,n_fog=75))]
    series += [(f'buffer_{n}',replace(base,buffer=n)) for n in [20,50,100,200,400]]
    series += [('stationary',replace(base,mobile_fraction=0)),('mobile',replace(base,mobile_fraction=1))]
    series += [(f'ratio_{n}',replace(base,n_edge=50*n,arrival_rate_s=base.arrival_rate_s*n/20)) for n in [10,15,20,25,30,35,40]]
    # Separate stress test, not the 400/hour application regime.
    series += [(f'stress_buffer_{n}',replace(base,n_tasks=2000,arrival_rate_s=1200,buffer=n)) for n in [0,2,20,50,100,200,400]]
    rows=[];records=[]
    for label,c in series:
        r=simulate(c);m=r['metrics']
        row={'scenario':label,**{k:m[k] for k in ['arrivals','completed','dropped','drop_fraction','mean_ms','p95_ms','max_ms','mean_fog_wait_ms','arrival_window_s','drained_until_s','deadline_3s_violations']},
             **{k:getattr(c,k) for k in ['n_edge','n_fog','n_cloud','buffer','arrival_rate_s','seed']},**m['components_ms']}
        rows.append(row);records.append({'scenario':label,'config':r['config'],'metrics':m})
        if label=='baseline':
            pd.DataFrame(r['tasks']).to_csv(out/'baseline_tasks.csv',index=False)
            pd.DataFrame(r['queue_trace']).to_csv(out/'baseline_queue.csv',index=False)
        if label=='stress_buffer_20':pd.DataFrame(r['queue_trace']).to_csv(out/'stress_queue.csv',index=False)
    frame=pd.DataFrame(rows);frame.to_csv(out/'configuration.csv',index=False)
    (out/'configuration_details.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    assert (frame.completed+frame.dropped==frame.arrivals).all()
    return frame
