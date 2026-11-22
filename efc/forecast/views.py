import matplotlib.pyplot as plt
from ..views import save

def plot_forecasts(metrics,predictions):
    fig,ax=plt.subplots(figsize=(9,2.8));ax.axis('off')
    labels=['История до t\nочередь, нагрузка','Forecaster\nfit / predict','mean_ms, p95_ms\nпроверка контракта','to_ranks\nкоманды для P']
    for i,label in enumerate(labels):
        ax.text(i,0,label,ha='center',bbox=dict(boxstyle='round',facecolor='white'))
        if i<3:ax.annotate('',xy=(i+.65,0),xytext=(i+.35,0),arrowprops=dict(arrowstyle='->'))
    ax.set_xlim(-.6,3.6);ax.set_ylim(-.4,.4);save(fig,'forecast_socket')
    fig,ax=plt.subplots(figsize=(7,4));ax.bar(metrics.method,metrics.mae_ms);ax.set_ylabel('MAE, мс');ax.tick_params(axis='x',rotation=20);save(fig,'forecast_mae')
    fig,ax=plt.subplots(figsize=(7,4));ax.bar(metrics.method,metrics.coverage_p95);ax.axhline(.95,linestyle='--');ax.set_ylabel('Доля y ≤ прогноз p95');ax.set_ylim(0,1);ax.tick_params(axis='x',rotation=20);save(fig,'forecast_coverage')
    fig,ax=plt.subplots(figsize=(8,4))
    import numpy as np
    x=np.arange(len(metrics));ax.bar(x-.18,metrics.coverage_before,width=.36,label='До: эмпирическая калибровка');ax.bar(x+.18,metrics.coverage_p95,width=.36,label='После: конечновыборочный ранг')
    ax.set_xticks(x,metrics.method,rotation=20);ax.axhline(.95,linestyle='--');ax.set_ylabel('Доля y ≤ верхний порог');ax.set_ylim(0,1);ax.legend();save(fig,'forecast_calibration')
    r=predictions[predictions.method=='NeuralNet'].iloc[:100]
    fig,ax=plt.subplots(figsize=(9,4));ax.plot(r.query_s,r.truth_ms,label='факт модели');ax.plot(r.query_s,r.mean_ms,label='точечный прогноз');ax.fill_between(r.query_s,0,r.p95_ms,alpha=.2,label='верхний порог p95, не гарантия');ax.set_xlabel('Время запроса, с');ax.set_ylabel('мс');ax.legend();save(fig,'forecast_trace')
