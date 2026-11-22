"""Add reviewed steady-state series and a shared claim check to every notebook."""
from pathlib import Path
import nbformat as n
ROOT=Path(__file__).resolve().parents[1]

def pair(text,code):return [n.v4.new_markdown_cell(text),n.v4.new_code_cell(code)]
for path in sorted((ROOT/'colab/clean').glob('*.ipynb')):
    nb=n.read(path,as_version=4);prefix=path.name[:2]
    if prefix=='00':
        nb.cells+=pair('Покажем устройство среды и движение одного вычисленного события. Это те же функции схем, что в тетради01, а не картинка без связи с моделью.',"from efc.views import architecture,animate_task\nfrom efc import simulate\nfrom efc.placement.study import controls\nfrom IPython.display import HTML,display\nimport json,pandas as pd\narchitecture()\nstartup=simulate()\nPath('results/startup_metrics.json').write_text(json.dumps(startup['metrics'],indent=2))\ndisplay(HTML(animate_task(startup['tasks'][0])))\ncontrol,_,_=controls()")
        code="from efc.claims import publish\nrecords=[{'id':'startup_'+k,'value':startup['metrics'][k],'file':'results/startup_metrics.json','field':k} for k in ('mean_ms','p95_ms','mean_fog_wait_ms')]\nrecords += [{'id':'startup_control_'+mode,'value':expected,'file':'results/placement_controls.csv','where':{'scenario':'minimal','requested_method':mode},'field':'time_ms'} for mode,expected in [('P',8),('B',4)]]\ndisplay(publish('00_Старт.ipynb',records))\nprint('OK: число в статье = число из модели')"
    elif prefix=='01':
        if not any('stationary_series()' in c.source for c in nb.cells if c.cell_type=='code'):
            idx=next((i for i,c in enumerate(nb.cells) if c.cell_type=='markdown' and 'Ползунки' in c.source),len(nb.cells))
            nb.cells[idx:idx]=pair('Стационарная диагностика: все50Fog, rho0,1–0,95, 10 независимых seed. Перед измерением прогрев2000 ожидаемых поступлений на Fog, наблюдение4000 и хвост1000. Cloud40 только в этой серии обеспечивает устойчивую следующую стадию. Это не прежний переходный пик.',"from efc.stationary import stationary_series\nfrom efc.stationary_views import stationary_plots\nsteady,replicates=stationary_series()\ndisplay(steady[['series','scenario','rho_target','mean_ms','mean_ms_ci_low','mean_ms_ci_high','p95_ms','p95_ms_ci_low','p95_ms_ci_high','max_ms','max_ms_ci_low','max_ms_ci_high']])\nstationary_plots(steady)\nassert (steady.n_seeds>=10).all()\nassert replicates.mean_fog_wait_ms.min()>0")
        code="from efc.claims import publish\nbase=frame[frame.scenario=='baseline'].iloc[0]\nrecords=[{'id':'baseline_'+k,'value':float(base[k]),'file':'results/configuration.csv','where':{'scenario':'baseline'},'field':k} for k in ('mean_ms','p95_ms','mean_fog_wait_ms')]\nrecords += [{'id':'stationary95_'+k,'value':float(steady[(steady.series=='intensity')&(steady.scenario=='rho_0.95')].iloc[0][k]),'file':'results/stationary_summary.csv','where':{'series':'intensity','scenario':'rho_0.95'},'field':k} for k in ('mean_ms','p95_ms','mean_fog_wait_ms','n_seeds')]\ndisplay(publish('01_Среда_и_конфигурация.ipynb',records))\nprint('OK: число в статье = число из модели')"
    elif prefix=='02':
        code="from efc.claims import publish\nrecords=[{'id':name+'_'+k,'value':float(metrics[metrics.method==name].iloc[0][k]),'file':'results/forecast_metrics.csv','where':{'method':name},'field':k} for name in ('Queueing','NeuralNet') for k in ('mae_ms','coverage_before','coverage_p95')]\ndisplay(publish('02_Прогноз_и_нейросеть.ipynb',records))\nprint('OK: число в статье = число из модели')"
    else:
        code="from efc.claims import publish,verify\nrecords=[{'id':'bridge_'+mode+'_'+k,'value':float(linked[linked.requested_method==mode].iloc[0][k]),'file':'results/neural_placement.csv','where':{'requested_method':mode},'field':k} for mode in ('P','B') for k in ('planned_ms','actual_ms')]\ndisplay(publish('03_Алгоритм_переразмещения.ipynb',records))\nif all(Path('results/'+f).exists() for f in ('startup_metrics.json','stationary_summary.csv','forecast_metrics.csv')):\n    print(verify())\nprint('OK: число в статье = число из модели')"
    nb.cells+=pair('Проверка. Числа из выполненной ячейки сравниваются с первичным файлом результатов и заносятся в общий results/claims.json. Несовпадение вызывает ошибку, а не косметическое сообщение OK.',code)
    n.write(nb,path)
print('All four notebooks have diagrams/claim checks; steady-state series is included.')
