"""Figures are produced only by notebook calls; CI from independent seeds."""
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

def stationary_plots(summary,output='article/figures'):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    def save(fig,name):
        fig.tight_layout();fig.savefig(out/(name+'.pdf'));fig.savefig(out/(name+'.png'),dpi=160);plt.show();plt.close(fig)
    intensity=summary[summary.series=='intensity'].sort_values('rho_target')
    for metric,name,ylabel in [('mean_ms','rho_latency','Средняя задержка, мс'),('mean_fog_wait_ms','rho_wait','Среднее ожидание Fog, мс')]:
        fig,ax=plt.subplots(figsize=(7,4))
        ax.errorbar(intensity.rho_target,intensity[metric],yerr=[intensity[metric]-intensity[metric+'_ci_low'],intensity[metric+'_ci_high']-intensity[metric]],fmt='o-',capsize=4,label='Модель: 10 seed, 95% ДИ')
        if metric=='mean_fog_wait_ms':ax.plot(intensity.rho_target,intensity.MM1K_wait_ms,'--',label='M/M/1/K: иные предпосылки сервиса')
        ax.set(xlabel='Предложенная нагрузка Fog ρ',ylabel=ylabel,title='Постоянный поток после прогрева');ax.grid(alpha=.25);ax.legend();save(fig,name)
    for series,name,xlabel in [('ratio','stationary_ratio','Датчиков на Fog'),('buffer','stationary_buffer','Мест ожидания в буфере')]:
        data=summary[summary.series==series].copy()
        data['x']=data.n_edge/data.n_fog if series=='ratio' else data.buffer
        data=data.sort_values('x');fig,ax=plt.subplots(figsize=(7,4))
        ax.errorbar(data.x,data.p95_ms,yerr=[data.p95_ms-data.p95_ms_ci_low,data.p95_ms_ci_high-data.p95_ms],fmt='o-',capsize=4)
        ax.set(xlabel=xlabel,ylabel='Средний p95 прогона, мс',title='10 независимых seed; 95% ДИ');ax.grid(alpha=.25);save(fig,name)
    data=summary[summary.series=='buffer'].sort_values('buffer');fig,ax=plt.subplots(figsize=(7,4))
    ax.errorbar(data.buffer,100*data.drop_fraction,yerr=[100*(data.drop_fraction-data.drop_fraction_ci_low),100*(data.drop_fraction_ci_high-data.drop_fraction)],fmt='o-',capsize=4)
    ax.set(xlabel='Мест ожидания в буфере',ylabel='Потери, %',title='ρ Fog = 0,95; постоянный поток после прогрева');ax.grid(alpha=.25);save(fig,'stationary_losses')
