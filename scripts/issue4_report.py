"""Source-grounded Issue #4 report. Never modifies the reviewer journal."""
from pathlib import Path
from datetime import datetime,timezone
import json,re,subprocess,urllib.request
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';D=ROOT/'docs'

def append_generated(path,heading,body):
    text=path.read_text() if path.exists() else ''
    marker='\n\n## '+heading+'\n'
    if marker in text:text=text.split(marker)[0]
    path.write_text(text.rstrip()+marker+body.strip()+'\n')

def history():
    log=subprocess.check_output(['git','log','--format=%H%x09%aI%x09%s','--reverse','HEAD'],cwd=ROOT,text=True)
    commits=[];stages={str(i):{'commits':[],'actions_runs':[]} for i in range(1,10)}
    for line in log.splitlines():
        sha,when,title=line.split('\t',2)
        if not title.startswith('FEFC:'):continue
        files=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',sha],cwd=ROOT,text=True).splitlines();tags=set()
        if 'начало работы' in title:tags.add('1')
        if any(x.startswith(('efc/model','tests/test_model')) for x in files):tags.add('2')
        if any(x.startswith(('efc/stationary','efc/sensitivity','scripts/make_notebooks','scripts/complete_notebooks')) for x in files):tags.add('3')
        if any(x.startswith(('efc/forecast','scripts/make_forecast')) for x in files):tags.add('4')
        if any(x.startswith(('efc/placement','scripts/make_placement','scripts/add_placement')) for x in files):tags.add('5')
        if any('views.py' in x or x.startswith(('scripts/check_figures','article/figures')) for x in files):tags.add('6')
        if any(x.startswith(('article/','scripts/write_article','scripts/review_article','scripts/render_references','scripts/verify_doi')) for x in files):tags.add('7')
        if any(x.startswith(('docs/','scripts/write_report','scripts/issue4_report')) for x in files):tags.add('8')
        if any(x.startswith(('.github/workflows','scripts/build_artifacts','results/final-check','results/build-summary')) for x in files):tags.add('9')
        commits.append({'sha':sha,'time':when,'title':title,'stages':sorted(tags),'files':files})
        for tag in tags:stages[tag]['commits'].append(sha)
    runs=[];error=None
    try:
        for page in (1,2):
            url=f'https://api.github.com/repos/annfridreksen/Forecast_Edge_Fog_Cloud/actions/runs?branch=night%2Ffefc-v3&per_page=100&page={page}'
            req=urllib.request.Request(url,headers={'User-Agent':'FEFC-audit'})
            with urllib.request.urlopen(req,timeout=20) as response:items=json.load(response)['workflow_runs']
            runs.extend({k:x.get(k) for k in ('id','head_sha','status','conclusion','created_at','run_started_at','updated_at','html_url')} for x in items)
            if len(items)<100:break
        else:error='history exceeds two pages; counts are partial'
    except Exception as exc:error=str(exc)
    bysha={c['sha']:c for c in commits}
    for run in runs:
        for tag in set(bysha.get(run['head_sha'],{}).get('stages',[]))|{'9'}:stages[tag]['actions_runs'].append(run['id'])
    return {'commits':commits,'runs':runs,'stages':stages,'api_error':error,'note':'Stage tags overlap: counts are not additive. Includes failures/cancellations; current run may be in progress. Commit timestamps and run durations are not active human working time.'}

def main():
    build=json.loads((R/'build-summary.json').read_text());s=pd.read_csv(R/'stationary_summary.csv')
    forecast=pd.read_csv(R/'forecast_metrics.csv').set_index('method');conf=pd.read_csv(R/'configuration.csv')
    cited=json.loads((R/'citation-check.json').read_text());doi=json.loads((R/'doi-check.json').read_text())
    assert cited['all_cited_doi_ok'] and doi['all_doi_ok']
    assert json.loads((R/'issue4-article-check.json').read_text())['status']=='PASS'
    h=history();(R/'work-history.json').write_text(json.dumps(h,ensure_ascii=False,indent=2))
    source=build['source_commit'];run=build.get('workflow_run_id')
    testlog=(R/'model-tests.txt').read_text();n=int(re.search(r'Ran (\d+) tests?',testlog).group(1));assert testlog.rstrip().endswith('OK')
    assert 'Ran 98 tests' in (R/'v2-tests.txt').read_text()
    pairs=len(list((ROOT/'article/figures').glob('*.pdf')))
    body=f'''Исправления проверены из исходного коммита `{source}`; Actions `{run}`.
Новых тестов: {n}; эталонных: 98. Все прошли. Четыре тетради выполнены nbconvert;
фактические времена — notebook-times.json, не обещание времени интерфейса Colab.
Низконагруженная часть исходных {len(conf)} сценариев не исследовала очереди;
переходные пики сохранены отдельно. Новая серия: 18×10=180 реализаций, плюс
10 реализаций удвоенного прогрева и 60 реализаций чувствительности допущений.
ДИ в статье относятся к средним оценкам между seed; конечный максимум
не является верхней границей распределения. Точная стационарность не доказана.
Queueing: MAE {forecast.loc['Queueing','mae_ms']:.6f} мс;
QueueingMM1K: {forecast.loc['QueueingMM1K','mae_ms']:.6f} мс;
MLP: {forecast.loc['NeuralNet','mae_ms']:.6f} мс.
Покрытие MLP до/после: {100*forecast.loc['NeuralNet','coverage_before']:.6f}% /
{100*forecast.loc['NeuralNet','coverage_p95']:.6f}%. Калибровка не использует тестовые
ответы и не обещает 95% на зависимом ряде.
PDF пересобран; тетрадями созданы {pairs} пар PDF/PNG.
Библиография: {len(cited['doi_keys'])} проверенных DOI плюс тезисы с явно неполными
выходными сведениями. DataCite DOI не объявляется неверным по одному 404 Crossref.
Каждая DOI-ссылка итогового текста подтверждена. Репозиторий и исходный коммит
указаны в статье; результаты публикуются отдельным последующим коммитом.
'''
    body+='\n### Расход и фактические события\nТокены неизвестны. Ниже счётчики истории, не оценка токенов.\n| Этап TASK | Коммитов | Запусков Actions |\n|---|---:|---:|\n'
    for stage,item in h['stages'].items():body+=f"| {stage} | {len(item['commits'])} | {len(set(item['actions_runs'])) if h['api_error'] is None else 'не подтверждено полностью'} |\n"
    body+=f'\nУникальных FEFC-коммитов в доступной истории: {len(h["commits"])}; запусков Actions: {len(h["runs"])}. Этапы пересекаются: столбцы не суммировать.\n'
    durations=[]
    for x in h['runs']:
        if x['status']=='completed' and x['run_started_at'] and x['updated_at']:
            durations.append((datetime.fromisoformat(x['updated_at'].replace('Z','+00:00'))-datetime.fromisoformat(x['run_started_at'].replace('Z','+00:00'))).total_seconds())
    if durations:body+=f'Длительность завершённых запусков по меткам run_started_at→updated_at: суммарно {sum(durations):.1f} с, диапазон {min(durations):.1f}–{max(durations):.1f} с. Это не активное время автора и не чистое время вычислений.\n'
    if h['api_error']:body+='История Actions прочитана не полностью: '+h['api_error']+'. Неполный счётчик не объявлен полным.\n'
    body+='\n### Issue #3: временные ограничения\nПрежний PASS означал техническую сборку, не закрытие научных замечаний. Отдельный коммит в 07:50 МСК 22.11.2026 не подтверждён и задним числом не создаётся. Непрерывной фоновой работы не было. Настоящий этап выполняется по новому сообщению автора и имеет фактические UTC-метки; результаты не датируются прошедшим сроком.\n'
    append_generated(D/'Отчёт_ночи.md','Адресная доработка Issue #4 и ответ на Issue #3',body)
    (D/'Краткий_план_статьи.md').write_text(f'''# Краткий план и реальный статус после Issue #4

1. Введение и обзор: архитектура, 18 проверенных DOI и отдельно тезисы как предыдущая работа.
2. Модель: 50 отдельных Fog, шесть слагаемых; параметры Config и допущения перечислены в таблице.
3. Методика: низкая нагрузка отделена от переходного пика и постоянного потока после прогрева; десять seed, ДИ, проверка удвоенного прогрева.
4. Конфигурация: низконагруженная часть прежних 29 сценариев практически вырождена по ожиданию и не доказывает оптимум. Новые 180 реализаций и 60 реализаций чувствительности дают ненулевое ожидание, потери и интервалы с указанными границами применимости.
5. Прогноз: шесть методов, включая условный Queueing и отдельный QueueingMM1K; показатели до/после калибровки. MLP демонстрационный, недопокрытие сохранено.
6. Алгоритм: неизменное v2, 98 тестов и точные 8/4/6 мс; один снимок MLP→ранги→P/B с отдельно указанным фоном. Это демонстрация интерфейсов, не сравнительное исследование алгоритмов.
7. Ограничения: синтетические данные; нет обещания 95% покрытия или универсального превосходства. Авторы, измерения оборудования и полные выходные сведения тезисов требуют подтверждения.

Источник выполненной сборки: {source}. Тетради выполнены на runner, не кликами в Google Colab.
''')
    items={
    1:('9f939992e1fb48d931dd2a099ff59d784ae8dde6','Постоянный поток, rho .1–.95, 50 очередей, прогрев и хвост; таблицы и рисунки в §4','stationary_replicates.csv; stationary_summary.csv'),
    2:('9f939992e1fb48d931dd2a099ff59d784ae8dde6','10 seed; 95% t-ДИ для среднего, p95 и конечного максимума; смысл интервалов ограничен','stationary_summary.csv; §3–4'),
    3:('9f939992e1fb48d931dd2a099ff59d784ae8dde6','Прежние 1200/с и 2000 поступлений названы переходным пиком, не смешаны с новой серией','§3–4'),
    4:('94eaec6b65973867889338c8e82c2ce27bfe3b40','Шесть долей и три уровня; каналы относятся отправителю; суммы 100%','component_shares.csv; level_shares.csv'),
    5:('94eaec6b65973867889338c8e82c2ce27bfe3b40','Доля Edge .3/.5/.7; десять seed и одинаковые окна, ДИ','sensitivity_summary.csv'),
    6:('94eaec6b65973867889338c8e82c2ce27bfe3b40','Fog→Cloud 10–30/20–50/30–70; явное допущение и чувствительность','sensitivity_summary.csv'),
    7:('e5fcbe515fc9333174665a517b55755d9c2156de','Queueing учитывает q/b и Config; безусловный метод сохранён отдельно','forecast_metrics.csv; §5'),
    8:('e5fcbe515fc9333174665a517b55755d9c2156de','ceil((n+1)*.95) только по калибровке; покрытие до/после без гарантии 95%','forecast_metadata.json; forecast_metrics.csv'),
    9:('1294a989b5212043695d6fbe00bffc25e32b1dec','Один снимок: план без фона/с фоном, разность и приоритет R раньше T','neural_placement.csv; §6'),
    10:('fafd98a489020c2d86bcac3f15cda15bad509c2e','18 DOI и тезисы с неполными сведениями; подраздел обзора; репозиторий/коммит','citation-check.json; references_verified.tex; availability.tex'),
    11:('fafd98a489020c2d86bcac3f15cda15bad509c2e','quote(safe="") сохранён; 404 вызван другим регистратором; Crossref/DataCite','doi-check.json'),
    12:('f74734d014ed57b9a90de13393b67e75f940aaf1','В 00 схема, анимация и числовая таблица; общий claims во всех четырёх','colab/00_Старт.ipynb; claims.json'),
    13:(source,'Технический PASS не закрывает научную рецензию; нет обещания фоновой работы и заднего датирования','Этот отчёт; Issue #3'),
    14:(source,'Краткий план прямо описывает вырожденность низкой нагрузки и новые диагностические серии','Краткий_план_статьи.md'),
    15:(source,'Фактические коммиты, Actions и длительности; ошибки чтения не заменяются нулём; токены неизвестны','work-history.json; этот отчёт')}
    answer='| Пункт | Реализация/коммит | Выполненное изменение | Файл/место |\n|---|---|---|---|\n'
    for i,(commit,decision,file) in items.items():answer+=f'| {i} | `{commit}` | {decision} | {file} |\n'
    answer+='\nВсе строки относятся к выполненному источнику '+source+'. Код некоторых исправлений появился раньше, но согласованные артефакты пересобраны сейчас. Замечания не закрываются автоматически.\n'
    append_generated(D/'Ответ_на_замечания.md','Issue #4: пункты 1–15',answer)
    append_generated(D/'Взаимодействие_с_проверяющим.md','Issue #3 и Issue #4: продолжение',f'UTC: {datetime.now(timezone.utc).isoformat()}; источник: {source}; Actions: {run}. Поэлементный ответ — Ответ_на_замечания.md. main, v2/ и Журнал_проверок_Perplexity.md не изменены. Общий PASS технический; статья не объявлена готовой к подаче.')
    append_generated(D/'Как_пользоваться.md','Подключить свою нейросеть за три шага','''1. Откройте efc/forecast/my_network.py и замените функцию прогноза своей моделью. Сохраните именованные входы и выходы mean_ms,p95_ms.
2. В тетради 02 выполните адаптер и проверки: конечные неотрицательные значения, p95>=mean; истинный будущий ответ не передаётся в признаки.
3. Сравните MAE и покрытие на отложенной по времени выборке; затем передайте прогноз в to_ranks и тетрадь 03. Веса и масштабирование обучаются только на train, поправка — только на calibration. Удачный запуск адаптера не подтверждает точность на реальном оборудовании.''')
    (R/'issue4-report.json').write_text(json.dumps({'source_commit':source,'workflow_run_id':run,'tests':n,'v2_tests':98,'figures':pairs,'stationary_replicates':180,'doi_verified':len(cited['doi_keys']),'items':{str(i):{'implementation_commit':c,'decision':d,'evidence':f} for i,(c,d,f) in items.items()},'history_api_error':h['api_error'],'publication_ready':False},ensure_ascii=False,indent=2))
    print('Issue #4/3 report and all 15 response rows written from executed files.')
if __name__=='__main__':main()
