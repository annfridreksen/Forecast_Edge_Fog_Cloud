"""Generate a complete article and traceable number tables from executed notebooks."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re
import pandas as pd
from setup_psta import ensure
ROOT=Path(__file__).resolve().parents[1]

def number(x,n=3):return f'{float(x):.{n}f}'.replace('.',',')
def table(label,caption,headers,rows,width=None):
    spec=width or '|'+('|'.join('l' if i==0 else 'r' for i in range(len(headers))))+'|'
    body='\\hline\n'+' & '.join(headers)+r'\\\hline'+'\n'
    body+='\n'.join(' & '.join(map(str,row))+r'\\' for row in rows)+'\n\\hline\n'
    return r'\begin{table}\caption{'+caption+r'}\label{'+label+r'}\centering\small'+'\n'+r'\begin{tabular}{'+spec+'}\n'+body+r'\end{tabular}\end{table}'

def main():
    ensure();res=ROOT/'results';article=ROOT/'article';docs=ROOT/'docs';docs.mkdir(exist_ok=True)
    config=pd.read_csv(res/'configuration.csv');b=config.set_index('scenario').loc['baseline']
    forecast=pd.read_csv(res/'forecast_metrics.csv');m=forecast.set_index('method').loc['NeuralNet']
    meta=json.loads((res/'forecast_metadata.json').read_text());controls=pd.read_csv(res/'placement_controls.csv')
    linked=pd.read_csv(res/'neural_placement.csv');payload=json.loads((res/'neural_placement.json').read_text())
    details=json.loads((res/'configuration_details.json').read_text());shares=next(x for x in details if x['scenario']=='baseline')['metrics']['stage_shares_pct']
    names={'baseline':'Базовый','edge_1250':'Edge 1250','edge_1500':'Edge 1500','edge_1750':'Edge 1750','edge_2000':'Edge 2000','cloud_16':'Cloud 16','cloud_24':'Cloud 24','fog_75':'Fog 75','stationary':'Стационарные','mobile':'Мобильные'}
    cr=[]
    for _,r in config[config.scenario.isin(names)].iterrows():cr.append([names[r.scenario],number(r.mean_ms),number(r.p95_ms),number(r.mean_fog_wait_ms),int(r.dropped)])
    br=[]
    for _,r in config[config.scenario.str.startswith('stress_')].iterrows():br.append([int(r.buffer),number(r.mean_ms),number(r.p95_ms),number(r.mean_fog_wait_ms),int(r.dropped)])
    fr=[[r.method,number(r.mae_ms),number(100*r.coverage_p95,2)] for _,r in forecast.iterrows()]
    ctr=[]
    for _,r in controls.iterrows():ctr.append([str(r.scenario).replace('_',r'\_'),r.requested_method,str(r.assignment).replace('nan','---'),number(r.time_ms,0) if pd.notna(r.time_ms) else '---'])
    lr=[[r.requested_method,r.assignment,number(r.planned_ms),number(r.actual_ms)] for _,r in linked.iterrows()]
    replace={'BASEMEAN':number(b.mean_ms),'BASEP95':number(b.p95_ms),'BASEMAX':number(b.max_ms),
      'EDGE_SHARE':number(shares['edge'],2),'FOG_SHARE':number(shares['fog'],2),'CLOUD_SHARE':number(shares['cloud'],2),
      'TRAINN':str(int(m.train_n)),'CALN':str(int(m.calibration_n)),'TESTN':str(int(m.test_n)),
      'DROPPEDFORECAST':str(meta['dropped']),'MLPMAE':number(m.mae_ms),'MLPCOVER':number(100*m.coverage_p95,2),
      'RANKS':', '.join(k+' = '+str(v) for k,v in payload['ranks'].items()),
      'DIFF':number(linked.set_index('requested_method').loc['P','actual_ms']-linked.set_index('requested_method').loc['B','actual_ms']),
      'NEWTESTS':str(sum(len(re.findall(r'^\s*def test_',p.read_text(),re.M)) for p in (ROOT/'tests').glob('test_*.py'))),
      'CONFIGTABLE':table('tab:config','Новые расчёты выбранных конфигураций, мс',['Сценарий','Средняя','p95','Fog-ожидание','Потери'],cr),
      'BUFFERTABLE':table('tab:buffer','Отдельная стрессовая серия: 1200 событий/с, 2000 поступлений',['Буфер','Средняя, мс','p95, мс','Fog-ожидание, мс','Потери'],br),
      'FORECASTTABLE':table('tab:forecast','Прогноз на одинаковой отложенной выборке завершённых событий',['Метод','MAE, мс','Покрытие, \\%'],fr),
      'CONTROLTABLE':table('tab:controls','Точная проверка эталона; время в мс',['Вход','Режим','Назначение','Время'],ctr),
      'LINKEDTABLE':table('tab:linked','Один пример с нейросетевыми рангами; время в мс',['Режим','Назначение','План','Исполнение'],lr)}
    text=(article/'main.template.tex').read_text()
    for key,value in replace.items():text=text.replace('@@'+key+'@@',value)
    assert not re.search(r'@@\w+@@',text)
    (article/'main.tex').write_text(text)
    sources=[('configuration.csv','colab/01_Среда_и_конфигурация.ipynb','code cell 2 (configuration_series)','§2–4'),
             ('forecast_metrics.csv','colab/02_Прогноз_и_нейросеть.ipynb','code cell 2 (forecast_study)','§5'),
             ('placement_controls.csv','colab/03_Алгоритм_переразмещения.ipynb','code cell 2 (controls)','§6'),
             ('neural_placement.csv','colab/03_Алгоритм_переразмещения.ipynb','code cell 4 (neural_placement)','§6')]
    claims=[]
    for filename,nb,cell,section in sources:
        df=pd.read_csv(res/filename)
        for i,row in df.iterrows():
            for key,value in row.items():
                if pd.isna(value):continue
                claims.append({'file':'results/'+filename,'csv_row':i+2,'column':key,'value':str(value),'notebook':nb,'cell':cell,'section':section,'status':'new synthetic calculation'})
    for key,value in shares.items():claims.append({'file':'results/configuration_details.json','column':'baseline.metrics.stage_shares_pct.'+key,'value':str(value),'notebook':sources[0][1],'cell':sources[0][2],'section':'§4','status':'new synthetic calculation'})
    for key in ['dropped','cut_train_s','cut_test_s','train_end_max_s','calibration_end_max_s']:
        claims.append({'file':'results/forecast_metadata.json','column':key,'value':str(meta[key]),'notebook':sources[1][1],'cell':sources[1][2],'section':'§5','status':'new synthetic calculation'})
    formulas={'nominal_fog_rho':400/3600/50*.055,'bridge_P_minus_B_ms':float(linked.iloc[0].actual_ms-linked.iloc[1].actual_ms)}
    for key,value in formulas.items():claims.append({'file':'results/article-data.json','column':key,'value':str(value),'notebook':'01 or 03; arithmetic from listed inputs','cell':'derived arithmetic','section':'§4/§6','status':'calculation from model inputs'})
    (res/'article-data.json').write_text(json.dumps({'formatted_values':replace,'derived':formulas,'source_csvs':[x[0] for x in sources]},ensure_ascii=False,indent=2))
    (res/'claims.json').write_text(json.dumps(claims,ensure_ascii=False,indent=2))
    lines=['# Реестр утверждений и чисел\n','Все новые результаты синтетические. Предыдущие числа не являются результатами нового запуска.\n',
      '## Происхождение параметров и предыдущих результатов\n',
      '- TASK.md и предоставленные тезисы НСКФ: 1000/50/8, 5–15 и 8–20 мс, Fog30–80, Cloud10–30, буфер400, 400событий/ч, 200задач, seed42, требование3с; §1–3.\n',
      '- Предыдущая работа:134,70/170,90/186,00мс; очередь55,73мс; 2000/сутки; рекомендации20–25 и50–100. В новой программе не подставляются. Выходные сведения тезисов требуют проверки.\n',
      '- Допущения Config: доля mobile0.30, делениеEdge0.50, равномерные профили, Fog→Cloud20–50мс, зоныi%nFog, FIFO, Bмест ожидания,K=B+1. Источник efc/model.py; тетрадь01,таблица§2.\n',
      '- 29сценариев: len(configuration.csv); интенсивностьEdgeмасштабируется пропорционально. Стресс1200/с,2000задач,буферы0/2/20/50/100/200/400 — efc/experiments.py,тетрадь01.\n',
      '- Прогноз:80/4/8,6000,60/с,веса4:2:1:1,буфер50,отсечки.6/.8; efc/forecast/study.py и forecast_metadata.json; тетрадь02.\n',
      '- MLP16/8,350итераций,seed42; alpha.01,learning_rate.005; EWMA.2,history32; efc/forecast/models.py,тетрадь02.\n',
      '- Контроль8/4/6/3мс и память/профили: v2/code/examples/*.json; точное совпадение проверяет03. Новый мост55мс,27.5мс,8000бит,8Мбит/с,4Мбайт,10с,остаток.5сервиса,edge_known10мс: efc/placement/study.py; полные входы neural_placement.json.\n',
      '## Числа из результатов\n|Файл|Строка CSV|Поле|Значение|Тетрадь/ячейка|Раздел|\n|---|---|---|---|---|---|\n']
    for c in claims:lines.append('|'+ '|'.join([c['file'],str(c.get('csv_row','JSON')),c['column'],c['value'],c['notebook']+'; '+c['cell'],c['section']])+'|\n')
    lines.append('\n## Рисунки\n')
    for name in sorted((article/'figures').glob('*.pdf')):
        n=name.stem
        nb='02' if n.startswith('forecast_') else '03' if n.startswith(('placement','graph_','gantt_','neural_placement')) else '01'
        lines.append(f'- `{name.relative_to(ROOT)}` — тетрадь{nb}, ячейка вызова architecture/configuration_plots/plot_forecasts/placement_plots; функции efc/*/views.py.\n')
    (docs/'Утверждения.md').write_text(''.join(lines))
    metadata={'generated_utc':datetime.now(timezone.utc).isoformat(),'source_files':{f:hashlib.sha256((res/f).read_bytes()).hexdigest() for f,_,_,_ in sources},'main_tex_sha256':hashlib.sha256((article/'main.tex').read_bytes()).hexdigest(),'all_figures_from_notebooks':True,'numeric_claim_records':len(claims)}
    (res/'article-provenance.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    print('Article written; traced',len(claims),'scalar source records. No new numerical result invented.')
if __name__=='__main__':main()
