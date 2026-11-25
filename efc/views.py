"""Figures are exported only by notebook calls, not on module import."""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FuncAnimation
from IPython.display import HTML,display
from .model import COMPONENTS


def save(fig,name):
    out=Path('article/figures');out.mkdir(parents=True,exist_ok=True)
    fig.tight_layout();fig.savefig(out/(name+'.pdf'),bbox_inches='tight');fig.savefig(out/(name+'.png'),dpi=130,bbox_inches='tight')
    plt.show();plt.close(fig)


def architecture():
    fig,ax=plt.subplots(figsize=(9,3.5));ax.set_axis_off()
    nodes=['1000 датчиков\nEdge','50 независимых FIFO\nFog + буфер','8 серверов\nCloud']
    graph=nx.DiGraph();graph.add_edges_from(zip(nodes,nodes[1:]));pos={n:(i,0) for i,n in enumerate(nodes)}
    nx.draw_networkx(graph,pos,ax=ax,node_size=6000,node_shape='s',font_size=9,arrowsize=20)
    ax.text(1,-.16,'Зоны датчиков → отдельные очереди → внешний результат',ha='center')
    ax.set_ylim(-.3,.25);save(fig,'architecture')
    fig,ax=plt.subplots(figsize=(10,2.8));ax.axis('off')
    labels=['Edge','Edge→Fog','Fog FIFO','Fog','Fog→Cloud','Cloud']
    for i,label in enumerate(labels):
        ax.text(i,0,label,ha='center',bbox=dict(boxstyle='round',facecolor='white'))
        if i<5:ax.annotate('',xy=(i+.76,0),xytext=(i+.24,0),arrowprops=dict(arrowstyle='->'))
    ax.text(2.5,-.35,'Шесть компонент задержки: каждый интервал учтён один раз',ha='center');ax.set_xlim(-.5,5.5);ax.set_ylim(-.5,.4)
    save(fig,'six_path')
    fig,ax=plt.subplots(figsize=(9,2.5));ax.axis('off')
    for i,label in enumerate(['Параметры + seed\nпоток событий','Очередь событий\nресурсные календари','Задержки, потери\nтрассы и метрики']):
        ax.text(i,0,label,ha='center',bbox=dict(boxstyle='round',facecolor='white'))
        if i<2:ax.annotate('',xy=(i+.7,0),xytext=(i+.3,0),arrowprops=dict(arrowstyle='->'))
    ax.set_xlim(-.5,2.5);ax.set_ylim(-.5,.5);save(fig,'inputs_outputs')


def configuration_plots(frame,queue):
    baseline=frame[frame.scenario=='baseline'].iloc[0]
    fig,ax=plt.subplots(figsize=(8,4));ax.bar(COMPONENTS,[baseline[k] for k in COMPONENTS]);ax.set_ylabel('мс');ax.tick_params(axis='x',rotation=25);ax.set_title('Базовый прогон: 6 компонент, синтетические данные');save(fig,'components')
    ratios=frame[frame.scenario.str.startswith('ratio_')]
    fig,ax=plt.subplots(figsize=(7,4));ax.plot(ratios.n_edge/ratios.n_fog,ratios.mean_ms,'o-',label='средняя');ax.plot(ratios.n_edge/ratios.n_fog,ratios.p95_ms,'s-',label='p95');ax.set_xlabel('Датчиков на Fog');ax.set_ylabel('мс');ax.legend();save(fig,'ratio')
    stress=frame[frame.scenario.str.startswith('stress_')]
    fig,ax=plt.subplots(figsize=(7,4));ax.plot(stress.buffer,stress.drop_fraction,'o-');ax.set_xlabel('Мест ожидания в одном Fog');ax.set_ylabel('Доля потерь');ax.set_title('Отдельный стресс-тест: 1200 событий/с');save(fig,'buffer')
    f=int(queue.groupby('fog').waiting.max().idxmax());q=queue[queue.fog==f]
    fig,ax=plt.subplots(figsize=(7,4));ax.step(q.time_s,q.waiting,where='post');ax.set_xlabel('с');ax.set_ylabel('Ожидающих');ax.set_title(f'Стресс-тест, очередь Fog {f}, буфер 20');save(fig,'queue')


def animate_task(task):
    durations=np.array([task[k] for k in COMPONENTS]);bound=np.cumsum(np.r_[0,durations])
    fig,ax=plt.subplots(figsize=(8,2.5));ax.set_xlim(-.5,5.5);ax.set_ylim(-.6,.6);ax.set_yticks([])
    ax.set_xticks(range(6),['Edge','E→F','FIFO','Fog','F→C','Cloud'])
    dot,=ax.plot([],[],'o',markersize=14);label=ax.text(0,.35,'')
    def update(t):
        i=min(5,max(0,int(np.searchsorted(bound,t,side='right')-1)))
        dot.set_data([i],[0]);label.set_text(f'{t:.1f} мс: {COMPONENTS[i]}');return dot,label
    anim=FuncAnimation(fig,update,frames=np.linspace(0,float(bound[-1]),24),interval=120)
    html=anim.to_jshtml();plt.close(fig);display(HTML(html));return html
