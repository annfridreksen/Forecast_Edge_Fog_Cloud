"""Render cited verified metadata from the FINAL article, not stale template."""
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
    text=source.read_text().replace(r'\input{related}',(ROOT/'article/related.tex').read_text())
    keys=[]
    for group in re.findall(r'\\cite\{([^}]+)\}',text):
        for key in group.split(','):
            key=key.strip()
            if key not in keys:keys.append(key)
    bad=[k for k in keys if k!='nskf' and (k not in rows or not rows[k]['ok'])]
    if bad:raise RuntimeError('Unverified cited DOI: '+','.join(bad))
    if not 15<=len([k for k in keys if k!='nskf'])<=25:raise RuntimeError('Expected 15–25 relevant verified DOI sources')
    bibliography=[r'\begin{thebibliography}{99}']
    for key in keys:
        if key=='nskf':
            bibliography.extend([r'\RBibitem{nskf}',r'\by Игнатенко А. С., Орда-Жигулина М. В.',r'\paper Исследование конфигурации вычислительной среды Edge--Fog',r'\inbook Тезисы НСКФ-2026. Материал предоставлен авторами; выходные сведения уточняются. DOI не подтверждён',r'\yr 2026',''])
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
    available=(r'\paragraph{Доступность кода и данных.} Код, тетради, первичные CSV и журналы доступны в репозитории \url{https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud}. Ветка --- \texttt{night/fefc-v3}. Исходный коммит выполненной сборки: '+(r'\texttt{'+commit+'}' if commit!='LOCAL-UNCOMMITTED' else '[локальная незакоммиченная сборка]')+r'. Результаты публикуются отдельным последующим коммитом; его идентификатор и запуск приведены в PR~2 и \texttt{results/final-check.txt}. Эталон \texttt{v2/} не изменён.'+'\n')
    (ROOT/'article/availability.tex').write_text(available)
    (ROOT/'results/citation-check.json').write_text(json.dumps({'cited_keys':keys,'doi_keys':[k for k in keys if k!='nskf'],'all_cited_doi_ok':not bad,'non_doi_exception':{'nskf':'supplied thesis, publication metadata pending; no invented DOI'},'source_commit':commit},ensure_ascii=False,indent=2))
    print('References:',len(keys),'including',len(keys)-int('nskf'in keys),'verified DOI; incomplete thesis explicitly marked.')
if __name__=='__main__':render()
