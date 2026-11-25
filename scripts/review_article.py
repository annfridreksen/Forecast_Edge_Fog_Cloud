"""Integrate Issue #4 calculations into the generated article, without changing v2.
Runs AFTER write_article.py. Tables read notebook-produced files only.
"""
from pathlib import Path
import hashlib,json,re,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
R=ROOT/'results';A=ROOT/'article';D=ROOT/'docs'

def num(x,n=3):return f'{float(x):.{n}f}'.replace('.',',')
def ci(row,key):
    return r'\shortstack{'+num(row[key],2)+r'\\{\scriptsize['+num(row[key+'_ci_low'],2)+'; '+num(row[key+'_ci_high'],2)+']}}'
def table(label,caption,heads,rows,spec=None):
    spec=spec or '|'+ '|'.join(['l']+['r']*(len(heads)-1))+'|'
    lines=[r'\begin{table}\caption{'+caption+r'}\label{'+label+r'}\centering\small',r'\begin{tabular}{'+spec+r'}\hline',' & '.join(heads)+r'\\\hline']
    lines += [' & '.join(map(str,row))+r'\\' for row in rows]
    lines += [r'\hline\end{tabular}\end{table}']
    return '\n'.join(lines)
def figure(name,caption,label):
    if not (A/'figures'/f'{name}.pdf').exists():raise FileNotFoundError(name)
    return r'\begin{figure}\centering\includegraphics[width=.9\linewidth]{figures/'+name+r'.pdf}\caption{'+caption+r'}\label{'+label+r'}\end{figure}'
def section_replace(text,title,replacement):
    start=text.index(r'\section{'+title+'}')
    end=text.find(r'\section{',start+1)
    if end<0:raise ValueError('section has no following boundary: '+title)
    return text[:start]+r'\section{'+title+'}\n'+replacement+'\n\n'+text[end:]
def block_replace(text,start,end,replacement):
    a=text.index(start);b=text.index(end,a)
    return text[:a]+replacement+'\n\n'+text[b:]

def main():
    steady=pd.read_csv(R/'stationary_summary.csv');raw=pd.read_csv(R/'stationary_replicates.csv')
    smeta=json.loads((R/'stationary_metadata.json').read_text())
    sensitivity=pd.read_csv(R/'sensitivity_summary.csv')
    comp=pd.read_csv(R/'component_shares.csv');levels=pd.read_csv(R/'level_shares.csv')
    fm=pd.read_csv(R/'forecast_metrics.csv').set_index('method')
    linked=pd.read_csv(R/'neural_placement.csv').set_index('requested_method')
    base=pd.read_csv(R/'configuration.csv').set_index('scenario').loc['baseline']
    assert len(raw)==180 and (steady.n_seeds>=10).all() and raw.mean_fog_wait_ms.min()>0
    assert abs(comp.share_pct.sum()-100)<1e-8 and abs(levels.share_pct.sum()-100)<1e-8
    text=(A/'main.tex').read_text()
    text=text.replace('В них сообщаются средняя задержка',r'В этих тезисах~\cite{nskf} сообщаются средняя задержка',1)
    text=text.replace('Проведены серии изменения конфигурации и отдельные стрессовые испытания.','Выполнены контрольные низконагруженные прогоны, переходные испытания и серии постоянного потока после прогрева: нагрузка Fog 0,1--0,95, десять начальных значений генератора и 95\\%-е доверительные интервалы.')
    text=text.replace('На синтетической проверочной выборке нейросеть имеет меньшую среднюю абсолютную ошибку, но её верхний прогнозный порог не обеспечивает номинального покрытия 95\\%.','Условный прогноз по состоянию очереди в этой выборке точнее демонстрационной нейросети. Для верхнего порога показаны результаты до и после калибровки; нейросеть не достигает номинального покрытия 95\\%.')
    text=text.replace('Configuration sweeps and separate stress tests are performed.','Low-load controls, transient tests, and constant-input experiments after warm-up are performed, with Fog loads from 0.1 to 0.95, ten random seeds and 95\\% confidence intervals.')
    text=text.replace('On the synthetic test sample, the neural network has a lower mean absolute error, but its upper forecast threshold does not attain nominal 95\\% coverage.','A conditional queue-state predictor is more accurate than the demonstration neural network on this sample. Upper thresholds are assessed before and after calibration; the neural network does not attain nominal 95\\% coverage.')
    text=text.replace('Это конечный эксперимент с пустым начальным состоянием, не оценка стационарного режима реальной парковки.','Это описание исходного контрольного опыта. Дополнительная стационарная диагностика использует постоянную интенсивность, прогрев, фиксированное окно и защитный хвост; она также не калибрована по реальной парковке.')
    text=text.replace('Загрузка ресурса --- сумма его занятых интервалов, делённая на время от начала наблюдения до завершения дренирования.','В конечном контрольном прогоне загрузка ресурса --- сумма его занятых интервалов, делённая на время до завершения дренирования. В стационарной диагностике занятость обрезается границами измерительного окна и делится только на длину этого окна.')
    methods=r'''Исходные 29 сценариев тетради 01 сохранены как контрольные конечные прогоны. При суммарной интенсивности 400 событий/ч они практически не нагружают Fog и не позволяют определить оптимум буфера. Режим 1200 событий/с с 2000 поступлениями относится к переходному пику, не к стационарному состоянию. Эти показатели не объединяются с новой серией при вычислении интервалов.

Основная дополнительная серия задаёт постоянный пуассоновский поток и 50 отдельных Fog. Предложенная нагрузка $\rho_F=\lambda E[S_F]/50$ принимает значения 0,10; 0,30; 0,50; 0,70; 0,85; 0,95. При $E[S_F]=0,055$ с интенсивность задаётся непосредственно из этого равенства, без подгонки к тезисам. При сохранении восьми Cloud высоконагруженная серия могла бы стать неустойчивой по облаку. Поэтому только для этой диагностики принято 40 Cloud: при максимальной нагрузке их предложенная занятость около 0,432. Базовая конфигурация 1000/50/8 не изменена; результаты этих двух режимов не выдаются за однофакторное сравнение.

Для каждой конфигурации выполнены десять независимых реализаций, seed 0--9. Прогрев соответствует 2000 ожидаемым поступлениям на Fog, измерение --- 4000, защитный хвост --- 1000. Длительности окон определены до запуска через заданную интенсивность. Метрики задержки относятся к когорте внешних поступлений внутри окна, а занятость --- к пересечению интервалов обслуживания с окном. Потери считаются для той же когорты; проверяется её полное завершение до конца хвоста. Это исключает включение опустошения очереди в оценку временной занятости.

Серия отношения датчиков к Fog содержит значения 10, 15, 20, 25, 30, 35, 40 при постоянной частоте события на датчик; $\rho_F$ изменяется от 0,2375 до 0,95. Серия буферов 20, 50, 100, 200, 400 проводится при $\rho_F=0,95$. Каждая из 18 конфигураций имеет десять seed. Дополнительно проверены удвоенный прогрев при максимальной нагрузке и чувствительность доли обработки Edge 0,3/0,5/0,7 и среднего сервиса Fog--Cloud 20/35/50 мс при $\rho_F=0,70$.

Для каждой реализации сначала оцениваются средняя задержка, эмпирический p95 и максимум фиксированной по правилу наблюдения выборки. Затем для оценок $z_1,\ldots,z_n$ строится интервал
\begin{equation}\label{eq:ci}
 \overline z\ \pm\ t_{0.975,n-1}\frac{s_z}{\sqrt n},\qquad n=10.
\end{equation}
Таким образом, интервал для p95 относится к среднему оценок квантиля по реализациям, а интервал для максимума --- к среднему конечных максимумов, не к верхней границе распределения. Это приближённые интервалы Стьюдента; десять seed и конечный прогрев не доказывают точной стационарности или нормальности распределения экстремумов. При нулевых потерях вырожденный интервал не является гарантией отсутствия потерь.

Половины измерительного окна и удвоенный прогрев сравниваются отдельно. Сохраняются все отличия, а не только благоприятные. Аналитическая кривая M/M/1/K используется с интенсивностью и средним сервисом, но экспоненциальное обслуживание отличается от равномерного обслуживания имитатора. Совпадение кривых не навязывается.

Прогнозный опыт тетради 02 сохраняет собственную неравномерную нагрузку: 80 датчиков, четыре Fog, восемь Cloud, буфер 50, 6000 событий и 60 событий/с, веса зон 4:2:1:1. Обучение и калибровка отделены по времени от проверки. Тетрадь 03 содержит точный контроль и один интерфейсный пример размещения, не статистическое сравнение алгоритмов. Исходные CSV, состояния и номера ячеек перечислены в реестре утверждений. Рисунки экспортируются только тетрадями, а эталон v2 проверяется по SHA-256.'''
    text=section_replace(text,'Методика экспериментов',methods)
    series_tables=[]
    for series,label,caption in [('intensity','tab:steady_intensity','Постоянный поток после прогрева: средние оценок и 95\\%-е ДИ, мс'),('ratio','tab:steady_ratio','Датчики на Fog при постоянной частоте на датчик; средние и 95\\%-е ДИ, мс'),('buffer','tab:steady_buffer','Буферы при нагрузке Fog 0,95; средние и 95\\%-е ДИ, мс')]:
        part=steady[steady.series==series]
        first={'intensity':r'$\rho_F$','ratio':'Датчики/Fog','buffer':'Буфер'}[series];rows=[]
        for _,row in part.iterrows():
            value=num(row.rho_target,2) if series=='intensity' else str(int(row.n_edge/row.n_fog)) if series=='ratio' else str(int(row.buffer))
            rows.append([value,ci(row,'mean_ms'),ci(row,'p95_ms'),ci(row,'max_ms')])
        series_tables.append(table(label,caption,[first,'Средняя','p95','Максимум'],rows))
    names={'edge_ms':'Обработка Edge','edge_fog_ms':'Передача Edge--Fog','fog_wait_ms':'Ожидание Fog','fog_service_ms':'Обработка Fog','fog_cloud_ms':'Передача Fog--Cloud','cloud_ms':'Обработка Cloud'}
    shares_table=table('tab:sixshares','Шесть компонентов базового контроля; канальное ожидание включено в передачу',['Компонент','Среднее, мс','Доля, \\%'],[[names[r.component],num(r.mean_ms),num(r.share_pct,2)] for r in comp.itertuples()])
    level_table=table('tab:levelshares','Единое правило группировки уровней базового контроля',['Уровень','Состав','Доля, \\%'],[['Edge','Edge + Edge--Fog',num(levels.loc[levels.level=='Edge','share_pct'].iloc[0],2)],['Fog','Ожидание + сервис + Fog--Cloud',num(levels.loc[levels.level=='Fog','share_pct'].iloc[0],2)],['Cloud','Cloud',num(levels.loc[levels.level=='Cloud','share_pct'].iloc[0],2)]],r'|l|p{65mm}|r|')
    qlo=steady[(steady.series=='intensity')&(steady.scenario=='rho_0.10')].iloc[0];qhi=steady[(steady.series=='intensity')&(steady.scenario=='rho_0.95')].iloc[0]
    loss=steady[steady.series=='buffer'].copy()
    for k in ['drop_fraction','drop_fraction_ci_low','drop_fraction_ci_high']:loss[k]*=100
    losses=table('tab:steady_loss','Потери в стационарной диагностике: среднее и 95\\%-й ДИ',['Буфер','Потери, \\%'],[[int(r.buffer),ci(r,'drop_fraction')] for _,r in loss.iterrows()])
    sensitivity_rows=[]
    for _,r in sensitivity.iterrows():sensitivity_rows.append([('Edge '+num(r.edge_processing_share,1)) if r.series=='edge_share' else ('Fog--Cloud '+num(r.fog_cloud_mean_ms,0)),ci(r,'mean_ms'),ci(r,'p95_ms')])
    stable=r'''Базовый контроль при 400 событиях/ч сохранён: средняя задержка '''+num(base.mean_ms)+r''' мс, p95 '''+num(base.p95_ms)+r''' мс, максимум '''+num(base.max_ms)+r''' мс. В нём нет потерь и ожидания Fog. При $\rho_F\approx1,22\cdot10^{-4}$ отсутствие влияния буфера и числа Cloud является следствием малой нагрузки, а не результатом оптимизации. Одиночные 200 наблюдений не дают надёжного основания ранжировать близкие конфигурации.

'''+shares_table+'\n'+level_table+r'''
По правилу таблицы~\ref{tab:levelshares} канал относится к уровню отправителя. Обе суммы долей равны 100\% до округления; расхождение округлённых сумм допускается. Это правило не приписывается прежним тезисам, где его детализация недостаточна. Поэтому числа 16,6/69,1/14,4 прежней работы не считаются непосредственно сопоставимыми долями новой программы.

'''+figure('components','Шесть слагаемых низконагруженного контроля; тетрадь 01','fig:components')+r'''

В новой диагностике ожидание Fog ненулевое: при нагрузках 0,10 и 0,95 его средние равны соответственно '''+num(qlo.mean_fog_wait_ms)+r''' и '''+num(qhi.mean_fog_wait_ms)+r''' мс. Таблицы~\ref{tab:steady_intensity}--\ref{tab:steady_buffer} показывают результаты десяти реализаций и интервалы~\eqref{eq:ci}. Различие метрик не объявляется статистически доказанным попарным эффектом без отдельного теста; интервалы описывают вариабельность выбранных оценок.

'''+series_tables[0]+'\n'+figure('rho_wait','Ожидание Fog от предложенной нагрузки: модель и M/M/1/K с иными предпосылками сервиса; тетрадь 01','fig:rhowait')+'\n'+figure('rho_latency','Сквозная задержка после прогрева; 10 seed и 95\\%-е ДИ; тетрадь 01','fig:rholatency')+'\n'+series_tables[1]+'\n'+series_tables[2]+'\n'+losses+r'''
Увеличение буфера при высокой нагрузке меняет одновременно блокирование и задержку принятых событий. Усреднение только успешных задач без доли потерь вводило бы смещение отбора. Нулевые наблюдённые потери при большом буфере не доказывают их невозможности. Прежние рекомендации 20--25 датчиков или 50--100 мест не переносятся на эти серии как универсальный оптимум.

'''+figure('stationary_ratio','Отношение датчиков к Fog при постоянной частоте на датчик; тетрадь 01','fig:steadyratio')+'\n'+figure('stationary_buffer','Буфер и p95 при нагрузке 0,95; тетрадь 01','fig:steadybuffer')+'\n'+figure('stationary_losses','Потери при нагрузке 0,95, десять реализаций; тетрадь 01','fig:steadyloss')+'\n'+table('tab:sensitivity','Чувствительность допущений при нагрузке Fog 0,70; средние и 95\\%-е ДИ',['Допущение','Средняя, мс','p95, мс'],sensitivity_rows)+r'''
Доля обработки Edge 0,3/0,5/0,7 изменяет разложение суммарного профиля Edge между исполнителем и входным каналом. Интервалы Fog--Cloud 10--30, 20--50 и 30--70 мс имеют средние 20,35,50 мс. Оба фактора являются допущениями, не характеристиками измеренного оборудования; чувствительность приведена в таблице~\ref{tab:sensitivity}. Исходный диапазон 20--50 не подбирался к прежнему среднему. Изменение числа Cloud в низконагруженном контроле не является проверкой облачного узкого места при диагностической высокой интенсивности.

'''+figure('sensitivity_edge','Чувствительность распределения Edge-времени; тетрадь 01','fig:sensedge')+'\n'+figure('sensitivity_link','Чувствительность сервиса Fog--Cloud; тетрадь 01','fig:senselink')+'\n'
    wd=smeta['warmup_check']['mean_fog_wait_ms']
    stable+=r'''При удвоенном прогреве средняя парная разность ожидания Fog при нагрузке 0,95 равна '''+num(wd['long_minus_default'])+r''' мс, 95\%-й ДИ ['''+num(wd['ci_low'])+'; '+num(wd['ci_high'])+r''']. Это диагностическая проверка конечного прогрева, не доказательство точной стационарности. Разности половин окна сохранены для всех метрик в CSV. Прежняя стрессовая серия 1200 событий/с и 2000 поступлений остаётся в результатах как переходный пик, но не используется для стационарных выводов этого раздела.'''
    text=section_replace(text,'Исследование конфигурации',stable)
    text=text.replace('Для приближённого метода Queueing принята модель M/M/1/K','Для отдельного безусловного метода QueueingMM1K принята модель M/M/1/K')
    text=text.replace('поэтому Queueing --- приближённый сравнительный метод.','поэтому QueueingMM1K --- приближённый сравнительный метод.')
    conditional=r'''Для усиленного условного метода Queueing используется наблюдаемое состояние перед обслуживанием: число ожидающих $q$ и занятость $b\in\{0,1\}$. При $\mu^{-1}=E[S_F]$ оценка времени Fog имеет вид
\begin{equation}\label{eq:conditional}
 \widehat W(q,b)=\frac{q+0,5b+1}{\mu}.
\end{equation}
Остаток половины среднего сервиса является явным приближением, не известным будущим и не точным остаточным временем равномерного обслуживания. Добавляются известное Edge-время и средние следующих стадий, полученные из Config, а не константы 35 и 20 мс в коде. Методы Queueing и QueueingMM1K оцениваются на тех же наблюдениях, что остальные прогнозы.

'''
    text=text.replace('Демонстрационная нейросеть ---',conditional+'Демонстрационная нейросеть ---',1)
    calibration=r'''До коррекции используется эмпирический верхний 95-й процентиль калибровочных остатков (правило higher). После коррекции применяется односторонняя split-conformal порядковая статистика~\cite{lei,angelopoulos}. Пусть $e_j=y_j-\widehat y_j$ --- остатки только калибровочной части, $n_{\rm cal}$ --- её размер. Тогда
\begin{equation}\label{eq:upper}
 k=\lceil(n_{\rm cal}+1)(1-\alpha)\rceil,\quad
 \widehat u=\widehat y+\max(0,e_{(k)}),\quad\alpha=0,05.
\end{equation}
Если $k>n_{\rm cal}$, конечная граница без дополнительного допущения не выдаётся. Поправка фиксируется до проверки; тестовые ответы в неё не входят. Конечновыборочная гарантия требует обменности наблюдений. Для зависимого очередного ряда со сдвигом она здесь не установлена; показывается эмпирическое покрытие, а не обещание 95\%. Это сравнение двух калибровочных правил, а не калибровки с её полным отсутствием.

'''
    text=block_replace(text,'Для всех методов верхний порог строится одним способом.','Для $m$ проверочных событий рассчитываются',calibration)
    rows=[[name,num(row.mae_ms),num(row.coverage_before*100,2),num(row.coverage_p95*100,2)] for name,row in fm.iterrows()]
    text=re.sub(r'\\begin\{table\}\\caption\{[^}]*\}\\label\{tab:forecast\}.*?\\end\{table\}',lambda _:table('tab:forecast','Одинаковая отложенная выборка: MAE и покрытие до/после коррекции',['Метод','MAE, мс','До, \\%','После, \\%'],rows),text,flags=re.S)
    resulttext=(r'В таблице~\ref{tab:forecast} условный Queueing имеет MAE '+num(fm.loc['Queueing','mae_ms'])+' мс, безусловный QueueingMM1K --- '+num(fm.loc['QueueingMM1K','mae_ms'])+' мс, MLP --- '+num(fm.loc['NeuralNet','mae_ms'])+r''' мс. Улучшение очередного baseline обусловлено использованием текущего q/b и одинаковых параметров Config, а не доступом к будущему. Формулы M/M/1/K не опровергаются ошибкой безусловной оценки в неравномерном конечном режиме. MLP не объявляется лучшим из всех рассмотренных методов.

Покрытие MLP изменилось с '''+num(100*fm.loc['NeuralNet','coverage_before'])+r'\% до '+num(100*fm.loc['NeuralNet','coverage_p95'])+r'''\%. Номинальные 95\% не достигнуты; поправка не подгонялась к тестовым исходам. Улучшение рангового правила мало, что согласуется с близостью порядковых индексов на большой калибровочной выборке, но не является гарантией при сдвиге.''')
    text=block_replace(text,'В таблице~\\ref{tab:forecast} наименьшая MAE',r'\begin{figure}\centering\includegraphics[width=.88\linewidth]{figures/forecast_coverage.pdf}',resulttext)
    if not {'fixed_assignment_no_background_ms','estimated_background_increment_ms'}<=set(linked.columns):raise ValueError('placement diagnostic must run from notebook03')
    accounting=table('tab:background','Демонстрация одного снимка: план и вклад заданного фона, мс',['Режим','Без фона','С фоном','Разность'],[[mode,num(row.fixed_assignment_no_background_ms),num(row.planned_ms),num(row.estimated_background_increment_ms)] for mode,row in linked.iterrows()])
    pos=text.index('Проверены ',text.index(r'\section{Прогнозный алгоритм переразмещения}'))
    text=text[:pos]+accounting+r'''
Это контрфактическое сравнение тех же назначений при удалении внешних интервалов, не новое ранжирование. Большая длительность плана около 2,9 с определяется главным образом заданным фоном, а не суммой трёх блоков по 55 мс. Различие P/B возникает уже в плане: критерий ставит R раньше T по построению. Один снимок является демонстрацией стыка интерфейсов; он не даёт частоты выигрыша и не называется сравнительным исследованием методов.

'''+text[pos:]
    text=text.replace('Все параметры времени и новые события синтетические. Реальные протокольные эффекты, измеренные профили, независимая проверка обученной сети, стационарный анализ нагрузок, многократные статистические испытания и полноценная миграция остаются отдельными задачами.','Все параметры времени и новые события синтетические. Добавлены постоянные нагрузки после прогрева, десять seed, доверительные интервалы и диагностика прогрева, но точная стационарность реального объекта не доказана. Реальные протокольные эффекты, измеренные профили, независимая проверка обученной сети и полноценная миграция остаются отдельными задачами.')
    text=text.replace('Демонстрационный MLP на принятой синтетической выборке уменьшил MAE относительно выбранных простых методов, однако не обеспечил целевое покрытие p95.','Демонстрационный MLP на этой выборке уступил условной очередной оценке по MAE и не обеспечил целевое покрытие p95 даже после конечновыборочной калибровочной поправки.')
    text=text.replace('Стрессовые опыты показывают компромисс потерь и задержки, но не дают универсального оптимума.','Стационарная диагностика и отдельно обозначенные переходные пики показывают компромисс потерь и задержки, но не дают универсального оптимума.')
    text=re.sub(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}',lambda _:r'\input{availability}'+'\n'+r'\input{references_verified}',text,flags=re.S)
    text=re.sub(r'\\n(?![A-Za-z])',lambda _:'\n',text)
    assert text.count(r'\section{')==7 and '@@' not in text
    (A/'main.tex').write_text(text)
    from render_references import render
    render()
    from efc.claims import publish,verify
    specifications=[('stationary_summary.csv','01_Среда_и_конфигурация.ipynb',('series','scenario')),('sensitivity_summary.csv','01_Среда_и_конфигурация.ipynb',('series','scenario')),('component_shares.csv','01_Среда_и_конфигурация.ipynb',('component',)),('level_shares.csv','01_Среда_и_конфигурация.ipynb',('level',)),('forecast_metrics.csv','02_Прогноз_и_нейросеть.ipynb',('method',)),('neural_placement.csv','03_Алгоритм_переразмещения.ipynb',('requested_method',))]
    claims=[]
    for filename,notebook,keys in specifications:
        frame=pd.read_csv(R/filename);batch=[]
        for i,row in frame.iterrows():
            for column,value in row.items():
                if isinstance(value,(int,float)) and pd.notna(value):
                    rec={'id':f'article_{Path(filename).stem}_{i}_{column}','file':'results/'+filename,'where':{k:row[k] for k in keys},'field':column,'value':float(value),'article_section':'4' if notebook.startswith('01') else '5' if notebook.startswith('02') else '6','cell':'call to stationary_series/sensitivity_series/forecast_study/neural_placement/background_accounting','csv_row':int(i)+2}
                    batch.append(rec);claims.append({**rec,'notebook':notebook})
        publish(notebook,batch,ROOT)
    verify(ROOT)
    appendix=['\n\n## Issue #4: новые проверенные числа\n','Все новые данные синтетические. ДИ строятся между независимыми seed, не по коррелированным задачам одного запуска. Максимум — среднее конечных максимумов.\n','| Файл | Строка | Поле | Значение | Тетрадь/ячейка | Раздел |\n|---|---:|---|---:|---|---|\n']
    for c in claims:appendix.append(f"| {c['file']} | {c['csv_row']} | {c['field']} | {c['value']} | {c['notebook']}; {c['cell']} | {c['article_section']} |\n")
    appendix+=['\nПараметры 50Fog/40Cloud, rho0.1–.95, прогрев2000/окно4000/хвост1000, seed0–9: efc/stationary.py, results/stationary_metadata.json, тетрадь01. Это новая диагностика, не параметры НСКФ. ДоляEdge0.3/0.5/0.7 и Fog→Cloud(10,30)/(20,50)/(30,70): efc/sensitivity.py.\n','Окно калибровки, размеры выборок и ранг ceil((n+1)*.95): forecast_metadata.json/forecast_metrics.csv, тетрадь02. Предыдущие числа НСКФ не объявлены новыми.\n']
    with (D/'Утверждения.md').open('a') as f:f.write(''.join(appendix))
    report={'status':'PASS','source_files':{filename:hashlib.sha256((R/filename).read_bytes()).hexdigest() for filename,_,_ in specifications},'claims_added':len(claims),'article_sha256':hashlib.sha256((A/'main.tex').read_bytes()).hexdigest(),'all_new_tables_from_results':True,'stationary_replications':len(raw),'independent_seeds_per_scenario':int(steady.n_seeds.min()),'limitations':['Synthetic data only','Constant offered input and finite warmup are not proof of exact stationarity','t CI for mean of run estimates; maxima not a population bound','Conformal guarantee not established on dependent shifted time series','Single placement snapshot is not a comparative study']}
    (R/'issue4-article-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('Issue #4 article integration PASS; source records',len(claims))
if __name__=='__main__':main()
