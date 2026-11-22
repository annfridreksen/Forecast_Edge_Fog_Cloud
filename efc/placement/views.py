import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from fractions import Fraction
from ..views import save

def placement_plots(plans,payload):
    fig,ax=plt.subplots(figsize=(10,3));ax.axis('off')
    labels=['Состояние\nмодели среды','MLP\nmean_ms,p95_ms','to_ranks\nпорядковые команды','v2: P → план\nотдельная проверка']
    for i,x in enumerate(labels):
        ax.text(i,0,x,ha='center',bbox=dict(boxstyle='round',facecolor='white'))
        if i<3:ax.annotate('',xy=(i+.68,0),xytext=(i+.32,0),arrowprops=dict(arrowstyle='->'))
    ax.set_xlim(-.55,3.6);ax.set_ylim(-.4,.4);save(fig,'placement_chain')
    for mode in ('P','B'):
        p=plans['minimal_'+mode]['plan'];mapping=dict(p['assignment'])
        fig,ax=plt.subplots(figsize=(7,3));g=nx.DiGraph([('a1','a2'),('a2','b'),('b','c')]);pos={n:(i,0) for i,n in enumerate(g)}
        owner={'a1':'A','a2':'A','b':'B','c':'C'};color={'E':'#DD9955','F':'#5599CC'}
        nx.draw_networkx(g,pos,ax=ax,node_color=[color[mapping[owner[n]]] for n in g],node_size=1200,arrowsize=20)
        ax.set_title(f'{mode}: '+', '.join(k+'→'+v for k,v in p['assignment']));ax.axis('off');save(fig,'graph_'+mode)
        fig,ax=plt.subplots(figsize=(8,3));ys={'E':1,'F':0}
        for run in p['runs']:
            start=float(Fraction(run['start'])*1000);end=float(Fraction(run['end'])*1000);y=ys[run['device']]
            ax.broken_barh([(start,end-start)],(y-.25,.5));ax.text((start+end)/2,y,run['block'],ha='center',va='center')
        for tr in p['transfers']:
            for hop in tr['hops']:
                a=float(Fraction(hop['start'])*1000);b=float(Fraction(hop['end'])*1000)
                ax.broken_barh([(a,b-a)],(-1.25,.5));ax.text((a+b)/2,-1,tr['src']+'→'+tr['dst'],ha='center',va='center',fontsize=8)
        ax.set_yticks([-1,0,1],['сеть','F','E']);ax.set_xlabel('мс');ax.set_title('Контроль v2, '+mode);ax.set_ylim(-1.6,1.6);save(fig,'gantt_'+mode)
    fig,ax=plt.subplots(figsize=(7,4));rows=payload['results'];ax.bar([x['requested_method'] for x in rows],[x['actual_ms'] for x in rows]);ax.set_ylabel('Время исполнения, мс');ax.set_title('Один сквозной синтетический пример, не доказательство преимущества');save(fig,'neural_placement')
