"""Chronological training/calibration/test; outcomes become visible at completion."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from ..model import Config,simulate
from .models import Naive,MovingAverage,EWMA,Queueing,QueueingMM1K,NeuralNet,state_of,export_network,conformal_margin

FACTORIES={'Naive':Naive,'MovingAverage':MovingAverage,'EWMA':EWMA,'QueueingMM1K':QueueingMM1K,'Queueing':Queueing,'NeuralNet':NeuralNet}

def data_for_forecast():
    c=Config(n_edge=80,n_fog=4,n_cloud=8,buffer=50,n_tasks=6000,arrival_rate_s=60,
             fog_weights=(4,2,1,1),seed=42)
    r=simulate(c)
    observed=sorted([x for x in r['tasks'] if x['status']=='completed'],key=lambda x:(x['fog_arrival_s'],x['task_id']))
    all_arrivals=sorted(x['fog_arrival_s'] for x in r['tasks'])
    cut_train=float(np.quantile(all_arrivals,.6));cut_test=float(np.quantile(all_arrivals,.8))
    train=[x for x in observed if x['end_s']<cut_train]
    calibration=[x for x in observed if cut_train<=x['fog_arrival_s']<cut_test and x['end_s']<cut_test]
    test=[x for x in observed if x['fog_arrival_s']>=cut_test]
    assert max(x['end_s'] for x in train)<cut_train
    assert max(x['end_s'] for x in calibration)<cut_test
    return r,train,calibration,test,cut_train,cut_test


def forecast_study(output='results'):
    out=Path(output);out.mkdir(exist_ok=True,parents=True)
    sim,train,cal,test,cut1,cut2=data_for_forecast()
    all_completed=sorted([r for r in sim['tasks'] if r['status']=='completed'],key=lambda r:(r['end_s'],r['task_id']))
    rows=[];summary=[];models={}
    for name,factory in FACTORIES.items():
        model=(factory(Config(**sim['config'])) if name.startswith('Queueing') else factory()).fit(train)
        future=[r for r in all_completed if r['end_s']>=cut1];pointer=0
        cal_residual=[]
        for target in cal:
            while pointer<len(future) and future[pointer]['end_s']<target['fog_arrival_s']:
                model.observe(future[pointer]);pointer+=1
            pred=model.predict(state_of(target));cal_residual.append(target['latency_ms']-pred['mean_ms'])
        before_margin=max(0.,float(np.quantile(cal_residual,.95,method='higher')))
        model.q,conformal_k=conformal_margin(cal_residual)
        if not np.isfinite(model.q):raise ValueError('calibration set too small for finite 95% upper bound')
        for target in test:
            while pointer<len(future) and future[pointer]['end_s']<target['fog_arrival_s']:
                model.observe(future[pointer]);pointer+=1
            pred=model.predict(state_of(target))
            rows.append({'method':name,'task_id':target['task_id'],'fog':target['fog'],
                         'query_s':target['fog_arrival_s'],'truth_ms':target['latency_ms'],**pred,
                         'p95_before_ms':pred['mean_ms']+before_margin,
                         'last_observed_completion_s':future[pointer-1]['end_s'] if pointer else max(r['end_s'] for r in train)})
        part=[x for x in rows if x['method']==name]
        summary.append({'method':name,'train_n':len(train),'calibration_n':len(cal),'test_n':len(test),
                        'mae_ms':float(np.mean([abs(x['truth_ms']-x['mean_ms']) for x in part])),
                        'coverage_p95':float(np.mean([x['truth_ms']<=x['p95_ms'] for x in part])),
                        'coverage_before':float(np.mean([x['truth_ms']<=x['p95_before_ms'] for x in part])),
                        'residual_margin_before_ms':before_margin,'residual_margin_ms':model.q,
                        'conformal_order_k':conformal_k})
        models[name]=model
    frame=pd.DataFrame(rows);metrics=pd.DataFrame(summary)
    assert (frame.last_observed_completion_s<frame.query_s).all()
    frame.to_csv(out/'forecast_predictions.csv',index=False);metrics.to_csv(out/'forecast_metrics.csv',index=False)
    pd.DataFrame(sim['tasks']).to_csv(out/'forecast_tasks.csv',index=False)
    metadata={'config':sim['config'],'cut_train_s':cut1,'cut_test_s':cut2,'dropped':sim['metrics']['dropped'],
              'train_end_max_s':max(r['end_s'] for r in train),'calibration_end_max_s':max(r['end_s'] for r in cal),
              'notes':'MLP fit/scaling: train only. Before: empirical higher 95th residual percentile; after: rank ceil((n+1)*.95) of calibration residuals only. Frozen margin before test. Online baselines observe past completions. Queue time series are dependent and shifted: no finite-sample coverage guarantee is claimed; coverage is empirical and conditional on completion.',
              'queueing':'Queueing uses (q+0.5*b+1)*configured mean service plus configured downstream means; QueueingMM1K retained separately. Neither observes future calendars.',
              'conformal':'one-sided split-conformal residual rule, alpha=.05; finite-sample theorem requires exchangeability, not established here' ,
              'network_warnings':models['NeuralNet'].training_warnings}
    (out/'forecast_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    (out/'demo_network.json').write_text(json.dumps(export_network(models['NeuralNet']),indent=2))
    return metrics,frame,models,sim
