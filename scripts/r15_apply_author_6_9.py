"""Apply exact author decisions 6-9, with a recorded old/new diff and HEAD lease.
This is a deterministic script of the sole executor, not an autonomous writer.
It never changes simulation sources, v2, old evidence, or old checkpoints.
"""
from pathlib import Path
import argparse,difflib,hashlib,json,os,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.r15_zero_loss import analysis,macros
from scripts.check_r15_paper import validate,tests


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def replace(text,old,new):
    if text.count(old)!=1:raise ValueError('Expected exactly one replacement anchor: '+old[:100])
    return text.replace(old,new,1)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if git('hash-object','article/main.tex')!='c6724d749058f3e10afbf5feb1bcabb1f05831d9':
        raise RuntimeError('Unexpected article version; do not patch an already changed manuscript')
    expected=os.environ['GITHUB_SHA'];ref='refs/heads/night/fefc-v3'
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('Another executor changed HEAD')
    raw=(ROOT/'article/main.tex').read_text();text=raw
    obj=analysis(a.checkpoint)
    if obj['decision']['status']!='CONDITIONALLY_ACCEPTABLE':raise ValueError('Requested conditional conclusion is unsupported by actual saved prerequisites')
    if obj['decision']['n_min']<184450:raise ValueError('The author 50-fold scenario is not supported by the actual minimum')
    (ROOT/'results/r15/conditional_analysis.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'article/r15-conditional-values.tex').write_text(macros(obj))
    text=replace(text,r'\input{r15-values}',r'\input{r15-values}'+'\n'+r'\input{r15-conditional-values}')
    title_ru='Моделирование краевой и туманной среды для выбора конфигурации и переразмещения связных задач с учётом прогноза'
    title_en='Simulation of an Edge--Fog Environment for Configuration Selection and Forecast-Aware Reassignment of Connected Tasks'
    text=replace(text,r'\title[Конфигурирование Edge--Fog]{Проверяемое конфигурирование краевой и туманной среды по ограничениям хвоста задержки и потерь}',r'\title[Моделирование краевой и туманной среды]{'+title_ru+'}')
    text=replace(text,r'\title[Verifiable edge--fog configuration]{Verifiable Configuration of an Edge--Fog Environment under Tail-Latency and Message-Loss Constraints}',r'\title[Edge--fog simulation and reassignment]{'+title_en+'}')
    abstracts=re.findall(r'\\begin\{abstract\}\n(.*?)\n\\end\{abstract\}',text,re.S)
    if len(abstracts)!=2:raise ValueError('Bilingual abstracts not found')
    ru=r'''Рассматривается модель краевой и туманной среды для выбора конфигурации по задержкам и потерям и будущего переразмещения связных задач. Протокол использует одинаковые входные потоки, отдельные пилотные и итоговые реализации и проверку полной когорты. Для 30 туманных узлов и буфера 5 выполнены десять итоговых реализаций: завершено \dArrivals{} сообщений, p95 составляет \dQ{} мс, потерь не наблюдалось. При допущении независимых биномиальных исходов оценка верхней границы доли потерь равна \cLossPercent{}\%; использована наименьшая когорта из \cNmin{} поступлений. Конфигурация допустима при указанном допущении для совместных порогов 200 мс и 0,1\%, но её минимальность не установлена. Аналитический ориентир p95 обслуживания без ожидания составляет \dServiceQ{} мс. Описана архитектура метода переразмещения целых подграфов с порядковыми командами прогноза. Обучение оценивателей и прогнозное управление не выполнялись.'''
    en=r'''We present an edge--fog simulation model for configuration selection under latency and loss constraints and for future reassignment of connected tasks. The protocol uses common external workloads, separate pilot and main replications, and complete arrival cohorts. Ten main replications with 30 fog nodes and five waiting places produced 1,999,801 completed messages, a p95 latency of 170.9 ms, and no observed losses. Under an independent-binomial-outcome assumption, the estimated upper loss bound is \cLossPercentEN{}\%, using the smallest cohort of \cNmin{} arrivals. The configuration is acceptable under that assumption for the joint limits of 200 ms and 0.1\%; its minimality is not established. The analytical p95 reference for service without waiting is 151.0 ms. We describe an architecture for whole-subgraph reassignment using ordinal forecast commands. Estimator training and forecast-driven control have not been performed.'''
    text=replace(text,abstracts[0],ru);text=replace(text,abstracts[1],en)
    goal='Цель исследования --- разработать проверяемую модель краевой и туманной среды для выбора конфигурации по задержкам и потерям и определить архитектуру прогнозного переразмещения связных задач.'
    text=replace(text,r'\section{Введение}\label{sec:introduction}',r'\section{Введение}\label{sec:introduction}'+'\n'+goal+'\n')
    text=replace(text,'позволяющие отделить наблюдаемое выполнение требований от статистически подтверждённого выбора.','позволяющие отделить наблюдаемые показатели от вывода, условного по принятой статистической модели.')
    anchor='Достижение предела без выполнения критерия сохраняется как недостаточность данных. Оно не доказывает нестационарность процесса.'
    # Preserve pilot protocol, then add the author-approved separate loss analysis to the decision subsection.
    conditional=r'''Для нулевых потерь используется отдельная оценка Клоппера--Пирсона при допущении независимых биномиальных исходов~\cite{clopper}. Пусть $n_i$ --- поступления итоговой реализации $i$, а $n_{\min}=\min_i n_i$. При нуле потерь во всех десяти реализациях задаётся
\begin{equation}\label{eq:lossconditional}
 U_L=1-0{,}025^{1/n_{\min}}.
\end{equation}
Оценка~\eqref{eq:lossconditional} получается из уравнения $(1-p)^n=0{,}025$ для общего риска $p$ независимых исходов. Применение $n_{\min}$ не доказывает независимость сообщений очереди. Поэтому положительный вывод называется «допустима при указанном допущении», а не безусловной гарантией.

Ненулевые потери оцениваются прежним bootstrap целых реализаций. Для нулевых потерь проверка точности использует половину ширины $[0,U_L]$. Остальные проверки, включая прогрев, завершённость когорты и точность p95, сохраняются. Исторический вывод исходного bootstrap хранится отдельно от нового условного анализа.'''
    text=replace(text,'Оба условия~\eqref{eq:accept} проверяются до округления.',conditional+'\n\nОба условия~\eqref{eq:accept} проверяются до округления.')
    text=replace(text,'После классификации выбирается лексикографический минимум $(n_F,B)$ среди допустимых исследованных конфигураций.','После классификации выбирается лексикографический минимум $(n_F,B)$ среди допустимых исследованных конфигураций с одинаково указанными статистическими допущениями.')
    text=replace(text,'Три клетки получили статус недостаточности данных; остальные 267 не имеют итогового статуса.','В сохранённом исходном анализе три клетки получили статус недостаточности данных; остальные 267 не имеют итогового статуса.')
    text=replace(text,'Таблица~\ref{tab:main} относится только к последней конфигурации.','Таблица~\ref{tab:main} относится только к последней конфигурации и отдельно показывает её условную оценку по~\eqref{eq:lossconditional}.')
    text=replace(text,'Обоснованная граница $U_L$ & Не установлена\\\\','Условная оценка $U_L$, \\% & \\cLossPercent{}\\\\\nНаименьшая когорта $n_{\\min}$ & \\cNmin{}\\\\')
    text=replace(text,'Совместный вывод & Недостаточно данных\\\\','Совместный вывод & Условно допустима\\\\')
    start=text.index('Наблюдённых потерь нет во всех десяти реализациях.')
    stop=text.index('Для пилота с $B=0$',start)
    new_result=r'''Наблюдённых потерь нет во всех десяти реализациях. Исходный bootstrap дал вырожденный интервал $[0;0]$ и недостаточность данных. Эти сохранённые результаты не изменялись; условный анализ выполнен по тем же первичным когортам без повторного моделирования.

Числа поступлений для seed 0--9 соответственно равны: \cCounts{}. Наименьшее равно \cNmin{}, поэтому~\eqref{eq:lossconditional} даёт \cLossPercent{}\%. Использован минимум поступлений, не сумма, не среднее и не число завершённых сообщений.

Граница p95 равна \dQhi{} мс; обе оценки меньше порогов. Прогрев, полнота когорты и исходные допуски точности выполнены. Вывод: конфигурация допустима при указанном допущении независимости. Независимое подтверждение и минимальность из этого не следуют.

Для аналитической сверки примем отдельную очередь M/M/1/K, где $K=B+1=6$, $\mu=1/0{,}055$ с$^{-1}$. При интенсивности $\lambda_j$ и $\rho_j=\lambda_j/\mu$ стационарная доля отказов равна
\begin{equation}\label{eq:mm1k}
 \pi_{K,j}=\frac{\rho_j^K}{\sum_{k=0}^{K}\rho_j^k}.
\end{equation}
Десять Fog обслуживают по 34 датчика, двадцать --- по 33. При $\lambda_j=\lambda m_j/1000$ взвешенная по поступлениям оценка~\eqref{eq:mm1k} составляет \cQueuePercent{}\%. Она ниже 0,1\%, но не является точной оценкой потерь имитации.

M/M/1/K предполагает экспоненциальное обслуживание и пуассоновский поток непосредственно в Fog. В модели обслуживание равномерно, а вход проходит предшествующие ресурсы. Поэтому аналитическое сравнение служит ориентиром и не доказывает независимость сообщений или эквивалентность моделей.

'''
    text=text[:start]+new_result+text[stop:]
    a6=text.index(r'\section{Развитие среды: переразмещение с учётом прогноза}')
    b6=text.index(r'\section{Обсуждение и ограничения}',a6)
    text=text[:a6]+r'\section{Развитие среды: переразмещение с учётом прогноза}\label{sec:development}'+'\n'+(ROOT/'article/r15-author-section6.tex').read_text()+'\n'+text[b6:]
    a7=text.index('Главное различие состоит между наблюдаемой метрикой')
    b7=text.index('Доверительные интервалы остаются номинальными;',a7)
    limits=r'''Главное различие состоит между наблюдаемой метрикой и выводом при заданных допущениях. При p95 \dQ{} мс и нуле потерь условная оценка даёт допустимость. Она не удостоверяет независимость сообщений очереди, которая отдельно не оценивалась.

Чувствительность проверяется подстановкой предполагаемого эффективного объёма $n_{\mathrm{eff}}$ вместо $n_{\min}$ в~\eqref{eq:lossconditional}. Это сценарий, не измерение зависимости. Достаточное округлённое условие для $U_L\leq0{,}001$ равно
\begin{equation}\label{eq:zero}
 n_{\mathrm{eff}}\geq
 \left\lceil\frac{-\ln0{,}025}{0{,}001}\right\rceil=3689.
\end{equation}
При $n_{\mathrm{eff}}=3689$ оценка равна приблизительно $0{,}00099947$. Отношение фактического минимума к 3689 составляет \cReduction{}. Поэтому сценарное уменьшение объёма в 50 раз сохраняет порог потерь; оценка тогда равна \cFiftyBound{}\%.

Это не означает сохранения полного критерия допустимости при 50-кратном уменьшении. Отдельный допуск точности $U_L/2\leq0{,}00005$ требует большего эффективного объёма. Вывод о чувствительности порога не подменяет проверку точности или фактическую оценку зависимости. Нулевые индикаторы потерь сами по себе не позволяют оценить её силу.

'''
    text=text[:a7]+limits+text[b7:]
    ac=text.index(r'\section{Заключение}\label{sec:conclusion}')
    bc=text.index(r'\paragraph{Доступность материалов.}',ac)
    conclusion=r'''\section{Заключение}\label{sec:conclusion}
Цель исследования реализована в виде проверяемой модели среды и архитектуры будущего прогнозного переразмещения. Модель определяет общие входы, шесть стадий задержки и совместную проверку ограничений. Архитектура отделяет прогнозные команды от проверки полного плана связной задачи.

Для 30 Fog и буфера 5 выполнены десять итоговых реализаций с \dArrivals{} завершёнными сообщениями. Оценка p95 составляет \dQ{} мс, номинальный интервал --- [\dQlo{}; \dQhi{}] мс. Наблюдённых потерь нет. По наименьшей когорте \cNmin{} условная верхняя оценка потерь равна \cLossPercent{}\%.

Конфигурация допустима при указанном допущении независимости, но её минимальность не установлена. Аналитический ориентир p95 обслуживания без ожидания равен \dServiceQ{} мс. Полная сравнительная карта, независимое подтверждение, обучение оценивателей и экспериментальная проверка переразмещения остаются дальнейшей работой.

'''
    text=text[:ac]+conclusion+text[bc:]
    text=replace(text,'The configuration therefore remains classified as having insufficient evidence. No minimum configuration or independent confirmation is reported.',r'The original analysis remains unchanged. A separate analysis uses the smallest arrival cohort, \cNmin{}, to obtain an upper loss estimate of \cLossPercentEN{}\% under independent binomial outcomes. The configuration is acceptable under that explicit assumption and the other retained checks. No minimum configuration or independent confirmation is reported.')
    text=replace(text,'It is not evidence of universal optimality, simulator superiority, or forecast-driven acceleration.',r'The loss conclusion is conditional, not a dependence-robust guarantee. Substituting an assumed effective sample size of at least 3689 retains the loss threshold; it does not automatically retain the separate precision requirement. The result is not evidence of universal optimality, simulator superiority, or forecast-driven acceleration.')
    # Fix the availability statement when the actual public delivery is installed; no claim before it exists.
    (ROOT/'article/main.tex').write_text(text)
    bibpath=ROOT/'article/r15-references.tex';bib=bibpath.read_text()
    block=r'''\Bibitem{clopper}
\by Clopper C. J., Pearson E. S.
\paper The Use of Confidence or Fiducial Limits Illustrated in the Case of the Binomial
\jour Biometrika
\vol 26
\issue 4
\yr 1934
\pages 404--413
\doi 10.1093/biomet/26.4.404

'''
    bib=replace(bib,r'\end{thebibliography}',block+r'\end{thebibliography}');bibpath.write_text(bib)
    mp=ROOT/'article/r15-sources.json';matrix=json.loads(mp.read_text())
    matrix['entries'].append(dict(key='clopper',year=1934,doi='10.1093/biomet/26.4.404',
       url='https://academic.oup.com/biomet/article-abstract/26/4/404/291795',status='PRIMARY_TEXT_READ',
       location='original pages 404–407, binomial tails; PDF pages 1 and 3 visually inspected',
       claim='Binomial confidence construction under independent common-probability outcomes; no guarantee for dependent queue losses. Formula derived explicitly for zero observations.'))
    mp.write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+'\n')
    for name in ('cover_letter.md','README.md','author_checklist.md'):
        path=ROOT/'submission'/name;s=path.read_text()
        s=s.replace('Проверяемое конфигурирование краевой и туманной среды по ограничениям хвоста задержки и потерь',title_ru)
        s=s.replace('27 записей,26 идентифицируемых,10 последних лет','28 записей,27 идентифицируемых,10 последних лет')
        s=s.replace('совместный статус `INSUFFICIENT_DATA` не изменён.','исторический статус R1.4 `INSUFFICIENT_DATA` не изменён. Отдельный R1.5-анализ даёт условную допустимость при допущении независимости; реестр `conditional_analysis.json`.')
        s+='\n\nОбновление по решениям автора #7115069628/#7115236266: название и раздел6 изменены, нулевые потери переанализированы **условно при независимости**. Новой имитации/обучения не было; исходный R1.4 сохранён. Чувствительность порога и точность интервала различаются.\n'
        path.write_text(s)
    # Actual manuscript checks retain all previously accepted raw-value tests.
    evidence=json.loads((ROOT/'results/r14/article_evidence.json').read_text());analytic=json.loads((ROOT/'results/r15/service_reference.json').read_text())
    values=(ROOT/'article/r15-values.tex').read_text()
    validate(evidence,analytic,text,bib,values,matrix)
    testcount=tests(evidence,analytic,text,bib,values,matrix,a.out)
    if text.count(r'\subsection{Метод переразмещения целых подграфов}')!=1 or title_ru not in text or title_en not in text:
        raise ValueError('author title/section requirement absent')
    if 'при указанном допущении' not in text or text.count(r'\cLossPercent{}')<3:
        raise ValueError('conditional conclusion not consistently linked')
    diff=''.join(difflib.unified_diff(raw.splitlines(True),text.splitlines(True),fromfile='before_author_6_9',tofile='after_author_6_9'))
    (ROOT/'docs/R15_Решения_6-9.diff').write_text(diff)
    (ROOT/'docs/R15_Решения_6-9.md').write_text('# Решения автора6–9\n\nПрименены #7115069628/#7115236266; методическое уточнение рецензента#7115339108.\n\nНазвание заменено точно; введена одна фраза цели и согласованные выводы. Раздел6 содержит6.1–6.3 и концептуальную схему; обучение/ускорение не заявлены. Объём проверяется по новомуPDF, не по исходнику.\n\nУсловная оценка получена из десяти первичных main-когорт: n_i и n_min не выведены из суммы. Старые значения R1.4/критерий/архивы не менялись. Результат R1.5 — '+obj['decision']['interpretation']+' при допущении независимости. Порог3689 относится только к риску; при50-кратном уменьшении отдельный допуск точности не сохраняется.\n\nСравнениеM/M/1/K взвешено по33/34источникам наFog; отличие экспоненциального обслуживания и потока непосредственно вFog указано.\n\nМесто→было→стало сохранено точным unified diff в соседнемфайле. ФИО/фото/права/выходные данныеНСКФ остаются [ДЛЯ АВТОРА].\n')
    allowed=['article/main.tex','article/r15-conditional-values.tex','article/r15-references.tex','article/r15-sources.json',
             'results/r15/conditional_analysis.json','docs/R15_Решения_6-9.diff','docs/R15_Решения_6-9.md',
             'submission/cover_letter.md','submission/README.md','submission/author_checklist.md']
    git('config','user.name','FEFC author-decision executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--',*allowed)
    staged=subprocess.check_output(['git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
    if set(x for x in staged if x)!=set(allowed):raise ValueError('source write scope differs')
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD changed before source commit')
    git('commit','-m','Issue #4 п.10–12 / R1.5 автор6–9: название, архитектура и условная оценка нулевых потерь')
    source_sha=git('rev-parse','HEAD');git('push','origin','HEAD:'+ref)
    if git('ls-remote','origin',ref).split()[0]!=source_sha:raise RuntimeError('source push mismatch')
    if os.getenv('GITHUB_ENV'):
        with open(os.environ['GITHUB_ENV'],'a') as f:f.write('R15_SOURCE_SHA='+source_sha+'\n')
    print(json.dumps({'source_sha':source_sha,'new_manuscript_tests':testcount,'conditional':obj['decision'],'n_i':[r['arrivals'] for r in obj['rows']],
                      'sensitivity':obj['sensitivity'],'mm1k':obj['mm1k']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
