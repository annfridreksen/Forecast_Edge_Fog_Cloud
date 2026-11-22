"""Issue #4 item 12: self-contained start notebook, using unchanged primary data."""
from pathlib import Path
import nbformat as nb
ROOT=Path(__file__).resolve().parents[1]

def make_start():
    cells=[]
    def pair(key,explanation,code):
        cells.append(nb.v4.new_markdown_cell(explanation,id=key+'-text'))
        cells.append(nb.v4.new_code_cell(code.strip(),id=key))
    cells.append(nb.v4.new_markdown_cell('# FEFC: старт, схемы и проверка результатов\n\nВсе данные синтетические. Эта тетрадь **читает сохранённые серии**, проверяет их и строит графики без повторного обучения. Для нового моделирования используются тетради 01–03. Алгоритм части 3 остаётся в неизменённом `v2/`.',id='start-title'))
    pair('start-setup','## 1. Получить проект\nВ Colab при отсутствии проекта клонируется только рабочая ветка. Существующая копия не перезаписывается; другая ветка вызывает понятную ошибку.',r'''
from pathlib import Path
import os, sys, subprocess, json, hashlib
root=Path.cwd()
while root != root.parent and not (root/'efc').is_dir(): root=root.parent
if not (root/'efc').is_dir():
    root=Path('/content/Forecast_Edge_Fog_Cloud')
    if not root.exists():
        subprocess.run(['git','clone','--single-branch','--branch','night/fefc-v3','https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud.git',str(root)],check=True)
    if not (root/'efc').is_dir():raise RuntimeError('Каталог существует, но не содержит FEFC; исходники не перезаписаны.')
os.chdir(root); sys.path.insert(0,str(root)); sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
if (root/'.git').exists():
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    if branch!='night/fefc-v3':raise RuntimeError('Нужна ветка night/fefc-v3; текущая: '+branch)
if 'google.colab' in sys.modules:
    subprocess.run([sys.executable,'-m','pip','install','-q','-r','requirements.txt'],check=True)
print('Среда:',sys.version,'\nПапка:',root)
''')
    pair('start-tests','## 2. Запустить тесты\nЭто новые запуски тестов, не воспроизведение крупных научных серий. Эталон v2 не редактируется.',r'''
for directory in (root,root/'v2/code'):
    process=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=directory,text=True,capture_output=True)
    print(str(directory)+'\n'+process.stdout+process.stderr)
    if process.returncode:raise RuntimeError('Тесты завершились ошибкой: '+str(directory))
''')
    pair('start-sources','## 3. Прочитать первичные результаты\nКонтрольные суммы связывают таблицы с ранее выполненными сериями. Несовпадение — ошибка, а не разрешение использовать старые числа.',r'''
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display,Image
from scipy.stats import t
from efc.claims import verify
hashes=json.loads(Path('results/source-hashes.json').read_text())
for name,digest in hashes.items():
    if name.startswith('efc/'):
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
origin=json.loads(Path('results/article-provenance.json').read_text())
for name,digest in origin['source_files'].items():
    assert hashlib.sha256((Path('results')/name).read_bytes()).hexdigest()==digest,name
steady=pd.read_csv('results/stationary_summary.csv')
raw=pd.read_csv('results/stationary_replicates.csv')
parts=pd.read_csv('results/component_shares.csv')
forecast=pd.read_csv('results/forecast_predictions.csv')
metrics=pd.read_csv('results/forecast_metrics.csv')
assert (raw.completed+raw.dropped==raw.arrivals).all()
assert (steady.n_seeds>=10).all()
assert np.isclose(parts.share_pct.sum(),100)
assert (forecast.last_observed_completion_s<forecast.query_s).all()
print(verify(root));print('Исходный запуск:',json.loads(Path('results/build-summary.json').read_text())['workflow_run_id'])
Path('results/start-dashboard').mkdir(exist_ok=True)
def save_plot(fig,name):
    fig.tight_layout()
    fig.savefig('results/start-dashboard/'+name+'.png',dpi=150)
    fig.savefig('results/start-dashboard/'+name+'.pdf')
    plt.show();plt.close(fig)
''')
    pair('start-environment','## 4. Среда Edge–Fog–Cloud\nГруппы на схеме не означают объединённую очередь: все Fog моделируются отдельно. Схема взята из выполненной тетради 01.',"display(Image(filename='article/figures/architecture.png'))\ndisplay(Image(filename='article/figures/six_path.png'))")
    pair('start-socket','## 5. «Розетка» нейросети\nПодключаемый модуль получает доступную историю и состояние, возвращает `mean_ms` и верхний порог `p95_ms`. `to_ranks` строит порядковые команды. Они не заменяют проверку полного плана и не становятся временем подграфа. Веса обучаются на train, поправка — на calibration; факт test служит только оценке. Схема взята из выполненной тетради 02.',"display(Image(filename='article/figures/forecast_socket.png'))\nprint('Адаптер: efc/forecast/my_network.py; контракт: efc/forecast/models.py')")
    pair('start-p95','## 6. p95 в зависимости от предложенной нагрузки ρ\nДИ относится к среднему значению выборочного p95 по независимым seed, не к гарантии задержки каждого события.',r'''
load=steady[steady.series=='intensity'].sort_values('rho_target')
fig,ax=plt.subplots(figsize=(8,4))
ax.errorbar(load.rho_target,load.p95_ms,yerr=[load.p95_ms-load.p95_ms_ci_low,load.p95_ms_ci_high-load.p95_ms],fmt='o-',capsize=4)
ax.set(xlabel='Предложенная нагрузка Fog ρ',ylabel='Средний p95 реализации, мс',title='10 seed; 95% доверительный интервал')
ax.grid(alpha=.25);save_plot(fig,'p95_vs_rho')
''')
    pair('start-losses','## 7. Потери в зависимости от ρ\nПри буфере 400 в этой серии потери не зарегистрированы. Нулевое наблюдаемое значение не доказывает нулевую вероятность потери; не рисуем искусственный рост.',r'''
fig,ax=plt.subplots(figsize=(8,4))
ax.errorbar(load.rho_target,100*load.drop_fraction,yerr=[100*(load.drop_fraction-load.drop_fraction_ci_low),100*(load.drop_fraction_ci_high-load.drop_fraction)],fmt='o-',capsize=4)
ax.set(xlabel='Предложенная нагрузка Fog ρ',ylabel='Потери, %',title='Конечный буфер: 400 мест ожидания; 10 seed')
ax.set_ylim(bottom=0);ax.grid(alpha=.25);save_plot(fig,'losses_vs_rho')
display(steady[steady.series=='buffer'][['buffer','rho_target','drop_fraction','drop_fraction_ci_low','drop_fraction_ci_high']])
''')
    pair('start-components','## 8. Из чего складывается задержка\nЭто базовый малонагруженный контроль, не стационарная серия ρ=0,95. Каналы отнесены отправителю; шесть составляющих не перекрываются.',r'''
labels=['Edge','Edge → Fog','Ожидание Fog','Обработка Fog','Fog → Cloud','Cloud']
fig,ax=plt.subplots(figsize=(8,4))
ax.bar(labels,parts.mean_ms);ax.tick_params(axis='x',rotation=20)
ax.set(ylabel='Средняя составляющая, мс',title='Шесть составляющих базового контрольного прогона')
save_plot(fig,'latency_components');display(parts)
''')
    pair('start-predictions','## 9. Прогноз против факта модели\nПоказаны первые 100 проверочных событий MLP. Порог p95 не является гарантией; покрытие оценивается на всей проверочной выборке.',r'''
pred=forecast[forecast.method=='NeuralNet'].sort_values('query_s')
view=pred.iloc[:100]
fig,ax=plt.subplots(figsize=(9,4))
ax.plot(view.query_s,view.truth_ms,label='Факт модели')
ax.plot(view.query_s,view.mean_ms,label='Точечный прогноз MLP')
ax.plot(view.query_s,view.p95_ms,linestyle='--',label='Верхний порог')
ax.set(xlabel='Момент запроса, с',ylabel='Задержка, мс');ax.legend()
save_plot(fig,'forecast_vs_actual')
computed=[]
for name,group in forecast.groupby('method'):
    stored=metrics[metrics.method==name].iloc[0]
    mae=float(np.abs(group.truth_ms-group.mean_ms).mean())
    before=float((group.truth_ms<=group.p95_before_ms).mean())
    after=float((group.truth_ms<=group.p95_ms).mean())
    assert np.allclose([mae,before,after],[stored.mae_ms,stored.coverage_before,stored.coverage_p95])
    computed.append([name,mae,before,after])
display(pd.DataFrame(computed,columns=['Метод','MAE, мс','Покрытие до','Покрытие после']))
''')
    pair('start-claims','## 10. Утверждение статьи → вычисляющая ячейка\nЗдесь повторно считаются статистики по первичным строкам, а не проводится новая симуляция. Полный реестр всех чисел: `results/claims.json` и `docs/Утверждения.md`.',r'''
rows=[]
for scenario in load.scenario:
    series=raw[(raw.series=='intensity')&(raw.scenario==scenario)]
    stored=load[load.scenario==scenario].iloc[0]
    values=series.p95_ms.to_numpy();n=len(values)
    mean=float(values.mean());half=float(t.ppf(.975,n-1)*values.std(ddof=1)/np.sqrt(n))
    assert np.allclose([mean,mean-half,mean+half],[stored.p95_ms,stored.p95_ms_ci_low,stored.p95_ms_ci_high])
    rows.append({'Утверждение':'p95 и 95% ДИ: '+scenario,'Источник':'stationary_replicates.csv → stationary_summary.csv','Ячейка расчёта':'start-claims','Ячейка графика':'start-p95','Значение':mean,'Проверка':'OK'})
for name,mae,before,after in computed:
    for label,value in [('MAE',mae),('Покрытие до',before),('Покрытие после',after)]:
        rows.append({'Утверждение':name+': '+label,'Источник':'forecast_predictions.csv → forecast_metrics.csv','Ячейка расчёта':'start-predictions','Ячейка графика':'start-predictions','Значение':value,'Проверка':'OK'})
rows.append({'Утверждение':'Сумма долей = 100%','Источник':'component_shares.csv','Ячейка расчёта':'start-sources','Ячейка графика':'start-components','Значение':parts.share_pct.sum(),'Проверка':'OK'})
frame=pd.DataFrame(rows);display(frame)
frame.to_csv('results/start-dashboard/claims-to-cells.csv',index=False)
print('OK: число в статье = число из модели; проверены сохранённые данные, серии не перезапускались.')
''')
    book=nb.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'fefc':{'mode':'cached results with recomputed statistics','science_results_commit':'4c8b105408b5581054b84002cd649bae7ab3a27a'}})
    path=ROOT/'colab/clean/00_Старт.ipynb';path.parent.mkdir(parents=True,exist_ok=True)
    nb.validate(book);nb.write(book,path)
    return path

if __name__=='__main__':print(make_start())
