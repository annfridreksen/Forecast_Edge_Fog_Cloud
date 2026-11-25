"""Apply approved author decisions 6-9 with exact text anchors and a HEAD lease.
All TeX-bearing Python strings are raw or explicitly escaped. No simulation.
"""
from pathlib import Path
import argparse,difflib,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.r15_zero_loss import analysis,macros
from scripts.check_r15_paper import validate,tests


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def replace(text,old,new):
    if text.count(old)!=1:raise ValueError('Expected exactly one replacement anchor: '+repr(old[:100]))
    return text.replace(old,new,1)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if git('hash-object','article/main.tex')!='c6724d749058f3e10afbf5feb1bcabb1f05831d9':raise RuntimeError('Unexpected article version; no duplicate author patch')
    expected=os.environ['GITHUB_SHA'];ref='refs/heads/night/fefc-v3'
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD lease lost')
    raw=(ROOT/'article/main.tex').read_text();text=raw;obj=analysis(a.checkpoint)
    if obj['decision']['status']!='CONDITIONALLY_ACCEPTABLE' or obj['decision']['n_min']<184450:
        raise ValueError('Actual cohorts do not support the proposed conditional/sensitivity statement')
    (ROOT/'results/r15/conditional_analysis.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'article/r15-conditional-values.tex').write_text(macros(obj))
    text=replace(text,r'\input{r15-values}',r'\input{r15-values}'+'\n'+r'\input{r15-conditional-values}')
    title_ru='Моделирование краевой и туманной среды для выбора конфигурации и переразмещения связных задач с учётом прогноза'
    title_en='Simulation of an Edge--Fog Environment for Configuration Selection and Forecast-Aware Reassignment of Connected Tasks'
    text=replace(text,r'\title[Конфигурирование Edge--Fog]{Проверяемое конфигурирование краевой и туманной среды по ограничениям хвоста задержки и потерь}',r'\title[Моделирование краевой и туманной среды]{'+title_ru+'}')
    text=replace(text,r'\title[Verifiable edge--fog configuration]{Verifiable Configuration of an Edge--Fog Environment under Tail-Latency and Message-Loss Constraints}',r'\title[Edge--fog simulation and reassignment]{'+title_en+'}')
    abstracts=re.findall(r'\\begin\{abstract\}\n(.*?)\n\\end\{abstract\}',text,re.S)
    if len(abstracts)!=2:raise ValueError('Bilingual abstracts missing')
    ru=r'''Рассматривается модель краевой и туманной среды для выбора конфигурации по задержкам и потерям и будущего переразмещения связных задач. Протокол использует одинаковые входные потоки, отдельные пилотные и итоговые реализации и проверку полной когорты. Для 30 туманных узлов и буфера 5 выполнены десять итоговых реализаций: завершено \dArrivals{} сообщений. Оценка 95-го перцентиля задержки (p95) составляет \dQ{} мс, потерь не наблюдалось. При допущении независимых биномиальных исходов оценка верхней границы доли потерь равна \cLossPercent{}\%; использована наименьшая когорта из \cNmin{} поступлений. Конфигурация допустима при указанном допущении для совместных порогов 200 мс и 0,1\%, но её минимальность не установлена. Аналитический ориентир p95 обслуживания без ожидания составляет \dServiceQ{} мс. Описана архитектура метода переразмещения целых подграфов с порядковыми командами прогноза. Обучение оценивателей и прогнозное управление не выполнялись.'''
    en=r'''We present an edge--fog simulation model for configuration selection under latency and loss constraints and for future reassignment of connected tasks. The protocol uses common external workloads, separate pilot and main replications, and complete arrival cohorts. Ten main replications with 30 fog nodes and five waiting places produced 1,999,801 completed messages. The estimated 95th-percentile latency (p95) is 170.9 ms, with no observed losses. Under an independent-binomial-outcome assumption, the estimated upper loss bound is \cLossPercentEN{}\%, using the smallest cohort of \cNmin{} arrivals. The configuration is acceptable under that assumption for the joint limits of 200 ms and 0.1\%; its minimality is not established. The analytical p95 reference for service without waiting is 151.0 ms. We describe an architecture for whole-subgraph reassignment using ordinal forecast commands. Estimator training and forecast-driven control have not been performed.'''
    text=replace(text,abstracts[0],ru);text=replace(text,abstracts[1],en)
    goal='Цель исследования --- разработать проверяемую модель краевой и туманной среды для выбора конфигурации по задержкам и потерям и определить архитектуру прогнозного переразмещения связных задач.'
    text=replace(text,r'\section{Введение}\label{sec:introduction}',r'\section{Введение}\label{sec:introduction}'+'\n'+goal+'\n')
    text=replace(text,'Увеличение буфера уменьшает вероятность отказа при переполнении,','Увеличение буфера может уменьшать вероятность отказа при переполнении,')
    text=replace(text,r'Датчик $i$ закреплён за узлом $i\bmod n_F$.',r'Число туманных узлов обозначим через $n_F$. Датчик $i$ закреплён за узлом $i\bmod n_F$.')
    text=replace(text,'начальное состояние генератора и окна наблюдения.','начальное состояние генератора (seed) и окна наблюдения.')
    text=replace(text,'позволяющие отделить наблюдаемое выполнение требований от статистически подтверждённого выбора.','позволяющие отделить наблюдаемые показатели от вывода, условного по принятой статистической модели.')
    conditional=r'''Для нулевых потерь используется отдельная оценка Клоппера--Пирсона при допущении независимых биномиальных исходов~\cite{clopper}. Пусть $n_i$ --- поступления итоговой реализации $i$, а $n_{\min}=\min_i n_i$. При нуле потерь во всех десяти реализациях задаётся
\begin{equation}\label{eq:lossconditional}
 U_L=1-0{,}025^{1/n_{\min}}.
\end{equation}
Оценка~\eqref{eq:lossconditional} получается из уравнения $(1-p)^n=0{,}025$ для общего риска $p$ независимых исходов. Применение $n_{\min}$ не доказывает независимость сообщений очереди. Поэтому положительный вывод называется «допустима при указанном допущении», а не безусловной гарантией.

Ненулевые потери оцениваются прежним bootstrap целых реализаций. Для нулевых потерь проверка точности использует половину ширины $[0,U_L]$. Остальные проверки, включая прогрев, завершённость когорты и точность p95, сохраняются. Исторический вывод исходного bootstrap хранится отдельно от нового условного анализа.'''
    anchor=r'Оба условия~\eqref{eq:accept} проверяются до округления.'
    text=replace(text,anchor,conditional+'\n\n'+anchor)
    text=replace(text,'После классификации выбирается лексикографический минимум $(n_F,B)$ среди допустимых исследованных конфигураций.','После классификации выбирается лексикографический минимум $(n_F,B)$ среди допустимых исследованных конфигураций с одинаково указанными статистическими допущениями.')
    text=replace(text,'Три клетки получили статус недостаточности данных; остальные 267 не имеют итогового статуса.','В сохранённом исходном анализе три клетки получили статус недостаточности данных; остальные 267 не имеют итогового статуса.')
    text=replace(text,r'Таблица~\ref{tab:main} относится только к последней конфигурации.',r'Таблица~\ref{tab:main} относится только к последней конфигурации и отдельно показывает её условную оценку по~\eqref{eq:lossconditional}.')
    text=replace(text,r'Обоснованная граница $U_L$ & Не установлена\\',r'Условная оценка $U_L$, \% & \cLossPercent{}\\'+'\n'+r'Наименьшая когорта $n_{\min}$ & \cNmin{}\\')
    text=replace(text,r'Совместный вывод & Недостаточно данных\\',r'Совместный вывод & Условно допустима\\')
    start=text.index('Наблюдённых потерь нет во всех десяти реализациях.');stop=text.index('Для пилота с $B=0$',start)
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
    a6=text.index(r'\section{Развитие среды: переразмещение с учётом прогноза}');b6=text.index(r'\section{Обсуждение и ограничения}',a6)
    text=text[:a6]+r'\section{Развитие среды: переразмещение с учётом прогноза}\label{sec:development}'+'\n'+(ROOT/'article/r15-author-section6.tex').read_text()+'\n'+text[b6:]
    a7=text.index('Главное различие состоит между наблюдаемой метрикой');b7=text.index('Доверительные интервалы остаются номинальными;',a7)
    limits=r'''Главное различие состоит между наблюдаемой метрикой и выводом при заданных допущениях. При p95 \dQ{} мс и нуле потерь условная оценка даёт допустимость. Она не удостоверяет независимость сообщений очереди, которая отдельно не оценивалась.

Чувствительность проверяется подстановкой предполагаемого эффективного объёма $n_{\mathrm{eff}}$ вместо $n_{\min}$ в~\eqref{eq:lossconditional}. Это сценарий, не измерение зависимости. Достаточное округлённое условие для $U_L\leq0{,}001$ равно
\begin{equation}\label{eq:zero}
 n_{\mathrm{eff}}\geq\left\lceil\frac{-\ln0{,}025}{0{,}001}\right\rceil=3689.
\end{equation}
При $n_{\mathrm{eff}}=3689$ оценка равна приблизительно $0{,}00099947$. Отношение фактического минимума к 3689 составляет \cReduction{}. Поэтому сценарное уменьшение объёма в 50 раз сохраняет порог потерь; оценка тогда равна \cFiftyBound{}\%.

Это не означает сохранения полного критерия допустимости при 50-кратном уменьшении. Отдельный допуск точности $U_L/2\leq0{,}00005$ требует большего эффективного объёма. Вывод о чувствительности порога не подменяет проверку точности или фактическую оценку зависимости. Нулевые индикаторы потерь сами по себе не позволяют оценить её силу.

'''
    text=text[:a7]+limits+text[b7:]
    ac=text.index(r'\section{Заключение}\label{sec:conclusion}');bc=text.index(r'\paragraph{Доступность материалов.}',ac)
    conclusion=r'''\section{Заключение}\label{sec:conclusion}
Цель исследования реализована в виде проверяемой модели среды и архитектуры будущего прогнозного переразмещения. Модель определяет общие входы, шесть стадий задержки и совместную проверку ограничений. Архитектура отделяет прогнозные команды от проверки полного плана связной задачи.

Для 30 Fog и буфера 5 выполнены десять итоговых реализаций с \dArrivals{} завершёнными сообщениями. Оценка p95 составляет \dQ{} мс, номинальный интервал --- [\dQlo{}; \dQhi{}] мс. Наблюдённых потерь нет. По наименьшей когорте \cNmin{} условная верхняя оценка потерь равна \cLossPercent{}\%.

Конфигурация допустима при указанном допущении независимости, но её минимальность не установлена. Аналитический ориентир p95 обслуживания без ожидания равен \dServiceQ{} мс. Полная сравнительная карта, независимое подтверждение, обучение оценивателей и экспериментальная проверка переразмещения остаются дальнейшей работой.

'''
    text=text[:ac]+conclusion+text[bc:]
    text=replace(text,'The configuration therefore remains classified as having insufficient evidence. No minimum configuration or independent confirmation is reported.',r'The original analysis remains unchanged. A separate analysis uses the smallest arrival cohort, \cNmin{}, to obtain an upper loss estimate of \cLossPercentEN{}\% under independent binomial outcomes. The configuration is acceptable under that explicit assumption and the other retained checks. No minimum configuration or independent confirmation is reported.')
    text=replace(text,'It is not evidence of universal optimality, simulator superiority, or forecast-driven acceleration.',r'The loss conclusion is conditional, not a dependence-robust guarantee. Substituting an assumed effective sample size of at least 3689 retains the loss threshold; it does not automatically retain the separate precision requirement. The result is not evidence of universal optimality, simulator superiority, or forecast-driven acceleration.')
    if '\r' in text or '\x08' in text:raise ValueError('Control character in generated TeX')
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
    bib=replace(bib,r'\end{thebibliography}',block+r'\end{thebibliography}')
    bib=bib.replace('\\jour Journal of Systems Architecture\n\\yr 2026','\\jour Journal of Systems Architecture\n\\vol 173\n\\yr 2026');bibpath.write_text(bib)
    mp=ROOT/'article/r15-sources.json';matrix=json.loads(mp.read_text())
    matrix['entries'].append(dict(key='clopper',year=1934,doi='10.1093/biomet/26.4.404',url='https://academic.oup.com/biomet/article-abstract/26/4/404/291538',status='PRIMARY_TEXT_READ',location='Original pages404–407; PDF pages1 and3 inspected; binomial construction',claim='Independent common-probability binomial outcomes; zero-loss formula explicitly derived. No guarantee for dependent queue losses.'))
    mp.write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+'\n')
    for name in ('cover_letter.md','README.md','author_checklist.md'):
        path=ROOT/'submission'/name;s=path.read_text().replace('Проверяемое конфигурирование краевой и туманной среды по ограничениям хвоста задержки и потерь',title_ru)
        s=s.replace('27 записей,26 идентифицируемых,10 последних лет','28 записей,27 идентифицируемых,10 последних лет')
        s=s.replace('совместный статус `INSUFFICIENT_DATA` не изменён.','исторический статус R1.4 `INSUFFICIENT_DATA` не изменён. Отдельный R1.5-анализ даёт условную допустимость при допущении независимости; реестр `conditional_analysis.json`.')
        s+='\n\nРешения автора #7115069628/#7115236266 применены: название и раздел6 изменены; нулевые потери переанализированы условно при независимости. Новой имитации/обучения нет; старый R1.4 сохранён. Чувствительность порога и точность интервала различаются.\n';path.write_text(s)
    evidence=json.loads((ROOT/'results/r14/article_evidence.json').read_text());analytic=json.loads((ROOT/'results/r15/service_reference.json').read_text());values=(ROOT/'article/r15-values.tex').read_text()
    validate(evidence,analytic,text,bib,values,matrix);testcount=tests(evidence,analytic,text,bib,values,matrix,a.out)
    if title_ru not in text or title_en not in text or text.count(r'\subsection{Метод переразмещения целых подграфов}')!=1:raise ValueError('author title/section missing')
    if text.count(r'\cLossPercent{}')<3 or 'при указанном допущении' not in text:raise ValueError('conditional conclusion inconsistent')
    (ROOT/'docs/R15_Решения_6-9.diff').write_text(''.join(difflib.unified_diff(raw.splitlines(True),text.splitlines(True),fromfile='before_author_6_9',tofile='after_author_6_9')))
    (ROOT/'docs/R15_Решения_6-9.md').write_text('# Решения автора6–9\n\nПрименены #7115069628/#7115236266 и методическое уточнение#7115339108. Название задано точно, цель согласована с выводом, раздел6 содержит6.1–6.3. Длина проверяется по PDF. Условная оценка из10 фактических когорт; n_min не из суммы. Старые R1.4/архивы не изменены. Чувствительность3689 относится только к порогу;50-кратное уменьшение не сохраняет отдельную точность.\n\nИсправлена ошибка Python-строки с TeX: обычная строка превратила \\ref в CR; все затронутые якоря теперь raw, контрольные символы блокируются. Никаких научных данных этим отказом не изменено; готовые15 тестов условного правила сохраняются в артефакте45282426757.\n\nМесто→было→стало в соседнем.diff. M/M/1/K отдельно, взвешен по33/34 датчикам; не граница имитации. ИсточникClopper URL291538 итомMECSim173 сверены по издателям. Авторские сведения/права/НСКФ открыты.\n')
    allowed=['article/main.tex','article/r15-conditional-values.tex','article/r15-references.tex','article/r15-sources.json','results/r15/conditional_analysis.json','docs/R15_Решения_6-9.diff','docs/R15_Решения_6-9.md','submission/cover_letter.md','submission/README.md','submission/author_checklist.md']
    git('config','user.name','FEFC author-decision executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');git('add','--',*allowed)
    staged=subprocess.check_output(['git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
    if set(x for x in staged if x)!=set(allowed):raise ValueError('write scope differs')
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD lease lost before source commit')
    git('commit','-m','Issue #4 п.10–12 / R1.5 автор6–9: название, архитектура и условная оценка нулевых потерь')
    source_sha=git('rev-parse','HEAD');git('push','origin','HEAD:'+ref)
    if git('ls-remote','origin',ref).split()[0]!=source_sha:raise RuntimeError('source push mismatch')
    if os.getenv('GITHUB_ENV'):
        with open(os.environ['GITHUB_ENV'],'a') as f:f.write('R15_SOURCE_SHA='+source_sha+'\n')
    print(json.dumps({'source_sha':source_sha,'new_manuscript_tests':testcount,'conditional':obj['decision'],'n_i':[r['arrivals'] for r in obj['rows']],'sensitivity':obj['sensitivity'],'mm1k':obj['mm1k']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
