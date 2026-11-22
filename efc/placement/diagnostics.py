"""Fixed-assignment counterfactual; not a new placement policy or experiment."""
from pathlib import Path
import copy,json
import pandas as pd
from .study import kernel

def background_accounting(frame,payload,output='results'):
    make,_,verify,_,_,_=kernel()
    from bt26.scheduler import build_plan
    problem=copy.deepcopy(payload['problem']);problem['busy']={}
    problem['infrastructure_version']='counterfactual-fixed-assignment-no-background'
    model=make(problem);rows=[]
    for record in frame.to_dict('records'):
        mode=record['requested_method'];assignment=dict(payload['plans'][mode]['plan']['assignment'])
        bare=build_plan(model,assignment);assert verify(model,bare)==()
        ms=float(bare.makespan*1000)
        rows.append({**record,'fixed_assignment_no_background_ms':ms,
                     'estimated_background_increment_ms':record['planned_ms']-ms,
                     'actual_background_increment_ms':record['actual_ms']-ms})
    result=pd.DataFrame(rows);payload['results']=rows
    payload['counterfactual']='same fixed assignment, identical block profiles and routes policy, no background; no reranking'
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    result.to_csv(out/'neural_placement.csv',index=False)
    (out/'neural_placement.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    return result,payload
