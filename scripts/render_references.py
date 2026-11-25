"""Render checked references and provenance; no simulation or model changes."""
from pathlib import Path
import json,re,html,subprocess,unicodedata
ROOT=Path(__file__).resolve().parents[1]

def tex(value):
    s=html.unescape(re.sub('<[^>]+>','',str(value or '')))
    s=s.replace('–','--').replace('—','---').replace('λ',r'\lambda{}').replace('μ',r'\mu{}')
    s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    s=s.replace('&',r'\&').replace('%',r'\%').replace('_',r'\_').replace('#',r'\#')
    return s.replace(r'\lambda{}',r'$\lambda$').replace(r'\mu{}',r'$\mu$')

def render():
    report=json.loads((ROOT/'results/doi-check.json').read_text())
    rows={r['key']:r for r in report['records']}
    source=ROOT/'article/main.tex'
    if not source.exists():raise RuntimeError('Generate final main.tex before bibliography')
    raw=source.read_text()
    start=raw.find('Исходным прикладным материалом служат')
    if start<0:raise RuntimeError('Prior-work paragraph not found')
    end=raw.index('\n\n',start)
    prior=r'Исходным прикладным материалом служат предоставленные тезисы НСКФ-2026~\cite{nskf} «Исследование конфигурации вычислительной среды Edge-Fog». Они задают сценарий мониторинга парковки и вопросы конфигурирования. Их численные выводы не переносятся в результаты новой программы. Полные выходные сведения сборника не подтверждены; ссылка в библиографии ведёт на программу доклада, не на опубликованный полный текст тезисов. Старый код не используется и не сверяется с новой реализацией.'
    raw=raw[:start]+prior+raw[end:]
    raw=raw.replace(r'\cite{lei,angelopoulos}',r'\cite{lei}')
    marker='% FEFC result provenance index'
    if marker not in raw:
        provenance=marker+'\n'+r'\paragraph{Источники численных результатов.} Таблицы раздела 4 сформированы из \path{results/stationary_summary.csv}, \path{results/sensitivity_summary.csv}, \path{results/component_shares.csv} и \path{results/level_shares.csv}; контроль малой нагрузки --- \path{results/configuration.csv}. Раздел 5 использует \path{results/forecast_metrics.csv} и \path{results/forecast_predictions.csv}; раздел 6 --- \path{results/placement_controls.csv} и \path{results/neural_placement.csv}. Точные поля, строки и ячейки для каждого зарегистрированного результата перечислены в \path{results/claims.json} и \path{docs/Утверждения.md}. Параметры и константы примеров являются входами модели, а не измерениями.'+'\n'
        raw=raw.replace(r'\input{availability}',provenance+r'\input{availability}')
    source.write_text(raw)
    text=raw.replace(r'\input{related}',(ROOT/'article/related.tex').read_text())
    keys=[]
    for group in re.findall(r'\\cite\{([^}]+)\}',text):
        for key in group.split(','):
            key=key.strip()
            if key not in keys:keys.append(key)
    bad=[k for k in keys if k!='nskf' and (k not in rows or not rows[k]['ok'])]
    if bad:raise RuntimeError('Unverified cited DOI: '+','.join(bad))
    if not 12<=len([k for k in keys if k!='nskf'])<=15:raise RuntimeError('Expected 12–15 relevant verified DOI sources')
    bibliography=[r'\begin{thebibliography}{99}']
    for key in keys:
        if key=='nskf':
            bibliography.extend([r'\RBibitem{nskf}',r'\by Игнатенко А. С., Орда-Жигулина М. В.',r'\paper Исследование конфигурации вычислительной среды Edge--Fog',r'\inbook Тезисы НСКФ-2026. Материал предоставлен авторами; выходные сведения уточняются. DOI не подтверждён',r'\yr 2026',r'\misc Программа доклада (не полный текст тезисов): \url{https://2015.nscf.ru/info/Schedule.pdf}, раздел 6',''])
            continue
        row=rows[key]
        authors=[tex(a.get('family',a.get('name',''))+' '+a.get('given','')) for a in row.get('authors',[])]
        if not authors:raise RuntimeError('No verified authors for '+key)
        bibliography.extend([r'\Bibitem{'+key+'}',r'\by '+', '.join(authors),r'\paper '+tex(row['actual_title'])])
        container=next((x for x in row.get('container',[]) if x),'')
        if container:bibliography.append(r'\jour '+tex(container))
        elif row.get('publisher'):bibliography.append(r'\publ '+tex(row['publisher']))
        for field,command in [('volume','vol'),('issue','issue'),('year','yr')]:
            if row.get(field):bibliography.append('\\'+command+' '+tex(row[field]))
        if row.get('pages') or row.get('article_number'):bibliography.append(r'\pages '+tex(row.get('pages') or row['article_number']))
        bibliography.extend([r'\doi '+row['doi'],''])
    bibliography.append(r'\end{thebibliography}')
    (ROOT/'article/references_verified.tex').write_text('\n'.join(bibliography)+'\n')
    try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.CalledProcessError):commit='LOCAL-UNCOMMITTED'
    previous=ROOT/'results/build-summary.json';reused=previous.exists()
    scientific=json.loads(previous.read_text())['source_commit'] if reused else commit
    origin=(r'Научные серии ранее выполнены из коммита \texttt{'+scientific+r'}; исходный набор результатов сохранён в \texttt{4c8b105}. Редакционная проверка не выдаётся за новое моделирование.' if reused else r'Научные серии выполнены из этого исходного коммита. Результаты публикуются отдельным последующим коммитом.')
    available=(r'\paragraph{Доступность кода и данных.} Код, тетради, первичные CSV и журналы доступны в репозитории \url{https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud}. Ветка --- \texttt{night/fefc-v3}. Коммит исходников данной редакции: '+(r'\texttt{'+commit+'}' if commit!='LOCAL-UNCOMMITTED' else '[локальная незакоммиченная сборка]')+r'. '+origin+r' Журналы текущей сборки и ссылки на Actions приведены в PR~2 и \path{results/revision-check.json}. Эталон \texttt{v2/} не изменён.'+'\n')
    (ROOT/'article/availability.tex').write_text(available)
    (ROOT/'results/citation-check.json').write_text(json.dumps({'cited_keys':keys,'doi_keys':[k for k in keys if k!='nskf'],'all_cited_doi_ok':not bad,'non_doi_exception':{'nskf':'supplied thesis, publication metadata pending; programme URL is not thesis full text; no invented DOI'},'source_commit':commit},ensure_ascii=False,indent=2))
    print('References:',len(keys),'including',len(keys)-int('nskf'in keys),'verified DOI; incomplete thesis explicitly marked.')
if __name__=='__main__':render()
