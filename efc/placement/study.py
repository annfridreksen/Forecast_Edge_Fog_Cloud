"""Two short checks; no reinterpretation or editing of the v2 criterion."""
from pathlib import Path
from fractions import Fraction
import sys,json,copy,hashlib
import pandas as pd
from ..forecast.models import FrozenNetwork,to_ranks,state_of
from ..forecast.study import data_for_forecast
ROOT=Path(__file__).resolve().parents[2]

def kernel():
    path=ROOT/'v2/code'
    if not path.exists():raise RuntimeError('immutable v2/code is not available')
    sys.path.insert(0,str(path))
    from bt26 import make_model,search,verify_plan
    from bt26.search import deterministic_result
    from bt26.scheduler import plan_to_dict
    from bt26.replay import replay
    return make_model,search,verify_plan,deterministic_result,plan_to_dict,replay


def check_manifest():
    base=ROOT/'v2'
    for line in (base/'MANIFEST.sha256').read_text().splitlines():
        if not line.strip():continue
        expected,path=line.split(maxsplit=1);p=base/path.lstrip('*')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise AssertionError('v2 changed: '+path)


def controls(output='results'):
    make,search,verify,det,serialize,_=kernel();check_manifest()
    out=Path(output);out.mkdir(exist_ok=True,parents=True);folder=ROOT/'v2/code/examples'
    f=json.loads((folder/'forecast.json').read_text());rows=[];plans={};audits={}
    for name,mode,expected,ms in [('minimal','P',('E','F','E'),8),('minimal','B',('F','F','F'),4),('deadline_filter','P',('E','F','F'),6),('no_feasible','P',None,None)]:
        model=make(json.loads((folder/(name+'.json')).read_text()));audit={};r=search(model,f,mode,audit=audit)
        assert (r.plan.identifier if r.plan else None)==expected
        if ms is not None:assert r.plan.makespan==Fraction(ms,1000);assert verify(model,r.plan)==()
        label=name+'_'+mode;plans[label]=det(r.to_dict());audits[label]=audit
        rows.append({'scenario':name,'requested_method':mode,'effective_method':r.method,'forecast_status':r.forecast_status,'assignment':','.join(expected) if expected else '', 'time_ms':ms,'status':r.status,'checked':r.stats['complete_checked']})
    (out/'placement_controls.json').write_text(json.dumps(plans,ensure_ascii=False,indent=2))
    (out/'placement_audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2,default=str))
    pd.DataFrame(rows).to_csv(out/'placement_controls.csv',index=False);check_manifest()
    return pd.DataFrame(rows),plans,audits


def neural_placement(output='results'):
    make,search,verify,det,serialize,replay=kernel();check_manifest()
    out=Path(output);model=FrozenNetwork(json.loads((out/'demo_network.json').read_text()))
    sim,train,cal,test,cut1,t=data_for_forecast()
    names={0:'F0',1:'F1'};states={};estimated={};actual={}
    for f,name in names.items():
        past=[r for r in sim['tasks'] if r['fog']==f and r['fog_arrival_s']<t]
        latest=max(past,key=lambda r:r['fog_arrival_s'])
        pending=[r for r in past if r['status']=='completed' and r['fog_end_s']>t]
        waiting=sum(r['fog_start_s']>=t for r in pending)
        busy=int(any(r['fog_start_s']<t<r['fog_end_s'] for r in pending))
        s=state_of(latest);s.update(queue_before=waiting,busy_before=busy,mobile=0.,edge_known_ms=10.)
        states[name]=s
        estimated[name]=(waiting+busy*.5)*.055
        actual[name]=max([0.]+[r['fog_end_s']-t for r in pending])
    predictions={k:model.predict(v) for k,v in states.items()};ranks=to_ranks(predictions)
    d=json.loads((ROOT/'v2/code/examples/minimal.json').read_text())
    d.update(task_version='v3-adapter-small-chain',infrastructure_version='v3-common-estimated-backlog',task_class='same-monitoring-request-demo',load_scope='v3-two-fog-synthetic',deadline_s='10',decision_time_s=str(t))
    d['devices']=[{'id':n,'layer':'fog','memory_bytes':4000000,'available':True,'features':['runtime']} for n in names.values()]
    for op in d['operations']:
        value=.0275 if op['id'] in ('a1','a2') else .055
        op['duration_s']={n:str(value) for n in names.values()}
    d['links']=[{'id':a+'_'+b,'src':a,'dst':b,'bandwidth_bps':8000000,'latency_s':'0'} for a in names.values() for b in names.values() if a!=b]
    d['busy']={'cpu:'+n:[['0',str(v)]] for n,v in estimated.items() if v>0}
    d.pop('previous',None);d.pop('previous_partition_version',None)
    f={'kind':'external_neural','provenance':'demonstration MLP, synthetic training data; results/demo_network.json',
       'scale_id':'dense-mean-rank-v1','direction':'smaller_is_preferred','task_class':d['task_class'],
       'partition_version':d['partition_version'],'load_scope':d['load_scope'],
       'issued_at_s':str(t),'valid_until_s':str(t+1),'commands':ranks}
    forecast_input=make(d)
    truth=copy.deepcopy(d);truth['busy']={'cpu:'+n:[['0',str(v)]] for n,v in actual.items() if v>0};truth['infrastructure_version']='executor-realized-backlog';actual_model=make(truth)
    rows=[];plans={};traces={}
    for mode in ('P','B'):
        r=search(forecast_input,f,mode);assert r.plan is not None;assert verify(forecast_input,r.plan)==()
        ex=replay(actual_model,r.plan);assert ex['plan'] is not None;assert not ex['violations']
        rows.append({'requested_method':mode,'effective_method':r.method,'forecast_status':r.forecast_status,
                     'assignment':','.join(r.plan.identifier),'planned_ms':float(r.plan.makespan*1000),
                     'actual_ms':float(ex['plan'].makespan*1000),'checked':r.stats['complete_checked']})
        plans[mode]=det(r.to_dict());traces[mode]={'plan':serialize(ex['plan']),'events':ex['events'],'violations':ex['violations']}
    payload={'input_status':'SYNTHETIC_BRIDGE_DEMONSTRATION_NOT_REAL_MIGRATION','query_time_s':t,'states':states,
             'predictions':predictions,'ranks':ranks,'estimated_busy_s':estimated,'actual_busy_s':actual,
             'problem':d,'forecast':f,'executor_problem':truth,'results':rows,'plans':plans,'replay':traces,
             'scope':'Forecast model trained on Fog requests, therefore this bridge uses two Fog nodes, a subset of allowed E/F devices. No extrapolation to untrained Edge hardware. Graph and message sizes are explicit synthetic additions; predictions supply ranks only, never block durations. Existing background is frozen; no new arrivals during this short graph execution.'}
    (out/'neural_placement.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2));pd.DataFrame(rows).to_csv(out/'neural_placement.csv',index=False);check_manifest()
    return pd.DataFrame(rows),payload
