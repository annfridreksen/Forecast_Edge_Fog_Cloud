"""Causal forecasting interface for synthetic event delays.

fit(history) consumes completed observations only. predict(state) reads named
pre-service features, never the event's target or future calendars. The MLP is
a demonstration trained on this simulator, not a validated production network.
"""
from collections import defaultdict,deque
from typing import Protocol
import math
import warnings
import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning

FEATURES=('queue_before','busy_before','rho_feature','observed_rate_s','mobile','edge_known_ms')

def state_of(row):
    return {**{k:float(row[k]) for k in FEATURES if k!='edge_known_ms'},
            'edge_known_ms':row['edge_ms']+row['edge_fog_ms'],'fog':int(row['fog'])}

def vector(state):
    x=np.array([float(state[k]) for k in FEATURES],dtype=float)
    if not np.isfinite(x).all():raise ValueError('non-finite forecast features')
    return x

class Forecaster(Protocol):
    def fit(self,history):...
    def predict(self,state):...

class HistoryBase:
    def __init__(self):self.values=defaultdict(lambda:deque(maxlen=32));self.q=0.;self.fitted=False
    def fit(self,history):
        self.values.clear();self.q=0.
        for r in sorted(history,key=lambda x:x['end_s']):self.observe(r)
        if not sum(map(len,self.values.values())):raise ValueError('empty training history')
        self.fitted=True;return self
    def observe(self,row):self.values[int(row['fog'])].append(float(row['latency_ms']))
    def mean(self,state):raise NotImplementedError
    def predict(self,state):
        vector(state)
        if not self.fitted:raise ValueError('fit required')
        m=max(0.,float(self.mean(state)))
        return {'mean_ms':m,'p95_ms':max(m,m+self.q)}
    def history(self,state):
        return self.values[int(state['fog'])] or [v for vv in self.values.values() for v in vv]

class Naive(HistoryBase):
    def mean(self,state):return self.history(state)[-1]

class MovingAverage(HistoryBase):
    def mean(self,state):return float(np.mean(self.history(state)))

class EWMA(HistoryBase):
    def mean(self,state):
        values=self.history(state);m=values[0]
        for v in list(values)[1:]:m=.2*v+.8*m
        return m


def mm1k(rate,service_mean_s,capacity):
    """Stationary M/M/1/K mean for ADMITTED jobs, not exact for uniform service."""
    if rate<0 or service_mean_s<=0 or capacity<1 or int(capacity)!=capacity:raise ValueError('invalid queue parameters')
    if rate==0:return {'rho':0.,'blocking':0.,'L':0.,'lambda_eff':0.,'W_s':service_mean_s}
    rho=rate*service_mean_s
    logw=np.arange(capacity+1)*math.log(rho);logw-=max(logw)
    p=np.exp(logw);p/=p.sum();L=float(np.dot(np.arange(capacity+1),p))
    accepted=(1-float(p[0]))/service_mean_s
    return {'rho':rho,'blocking':float(p[-1]),'L':L,'lambda_eff':accepted,'W_s':L/accepted if accepted>0 else service_mean_s}

class Queueing(HistoryBase):
    """Conditional queue-state baseline, not an artificially blind comparator.

    Remaining service is approximated by half the configured mean; it is not
    an observed future completion and not the exact uniform residual lifetime.
    """
    def __init__(self,config=None):
        super().__init__()
        from ..model import Config
        self.config=Config() if config is None else config
        self.buffer=self.config.buffer
        self.service_mean_ms=sum(self.config.fog_service_ms)/2
        self.downstream_ms=(sum(self.config.fog_cloud_ms)+sum(self.config.cloud_service_ms))/2
    def mean(self,state):
        q=max(0.,state['queue_before']);b=float(bool(state['busy_before']))
        return state['edge_known_ms']+(q+.5*b+1)*self.service_mean_ms+self.downstream_ms

class QueueingMM1K(Queueing):
    """Unconditional stationary comparator, with the same Config-derived means."""
    def mean(self,state):
        q=mm1k(max(0.,state['observed_rate_s']),self.service_mean_ms/1000,self.buffer+1)
        return state['edge_known_ms']+q['W_s']*1000+self.downstream_ms


def conformal_margin(residuals,alpha=.05):
    """One-sided split-conformal order statistic; no test targets are inputs.

    Finite-sample coverage requires exchangeability, NOT assumed for queue time
    series here. Small calibration sets with rank n+1 return infinity explicitly.
    """
    scores=np.asarray(residuals,dtype=float)
    if scores.ndim!=1 or not len(scores) or not np.isfinite(scores).all() or not 0<alpha<1:
        raise ValueError('invalid calibration scores or alpha')
    k=math.ceil((len(scores)+1)*(1-alpha))
    return (math.inf if k>len(scores) else max(0.,float(np.sort(scores)[k-1]))),k

class NeuralNet(HistoryBase):
    def fit(self,history):
        super().fit(history)
        x=np.array([vector(state_of(r)) for r in history]);y=np.array([r['latency_ms'] for r in history])
        self.scaler=StandardScaler().fit(x);self.y_scale=max(1.,float(y.std()));self.y_mean=float(y.mean())
        self.net=MLPRegressor(hidden_layer_sizes=(16,8),random_state=42,max_iter=350,
                              early_stopping=False,alpha=.01,learning_rate_init=.005)
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always',ConvergenceWarning)
            self.net.fit(self.scaler.transform(x),(y-self.y_mean)/self.y_scale)
        self.training_warnings=[str(w.message) for w in seen]
        return self
    def mean(self,state):
        return float(self.net.predict(self.scaler.transform(vector(state).reshape(1,-1)))[0]*self.y_scale+self.y_mean)


def to_ranks(predictions):
    """Rank mean_ms only; ordinal labels never replace execution profiles."""
    if not predictions:raise ValueError('no devices')
    for name,p in predictions.items():
        if not isinstance(name,str) or not name or not math.isfinite(p['mean_ms']) or p['mean_ms']<0 or not math.isfinite(p['p95_ms']) or p['p95_ms']<p['mean_ms']:
            raise ValueError('invalid forecast')
    values=sorted(set(p['mean_ms'] for p in predictions.values()))
    return {name:values.index(p['mean_ms'])+1 for name,p in predictions.items()}


def export_network(model):
    return {'kind':'demonstration_MLP','features':list(FEATURES),'coefs':[x.tolist() for x in model.net.coefs_],
            'intercepts':[x.tolist() for x in model.net.intercepts_],
            'x_mean':model.scaler.mean_.tolist(),'x_scale':model.scaler.scale_.tolist(),
            'y_mean':model.y_mean,'y_scale':model.y_scale,'q':model.q,
            'note':'Synthetic simulator only; not a production or independently validated network.'}

class FrozenNetwork:
    def __init__(self,data):
        if data['features']!=list(FEATURES):raise ValueError('feature contract mismatch')
        self.data=data
    def predict(self,state):
        d=self.data;x=(vector(state)-np.asarray(d['x_mean']))/np.asarray(d['x_scale'])
        for i,(w,b) in enumerate(zip(d['coefs'],d['intercepts'])):
            x=x@np.asarray(w)+np.asarray(b)
            if i<len(d['coefs'])-1:x=np.maximum(0,x)
        m=max(0.,float(x[0]*d['y_scale']+d['y_mean']))
        return {'mean_ms':m,'p95_ms':max(m,m+d['q'])}
