"""Render only verified DOI metadata; keep the supplied thesis explicitly incomplete."""
from pathlib import Path
import json,re,html,subprocess,unicodedata
ROOT=Path(__file__).resolve().parents[1]

def tex(value):
    s=html.unescape(re.sub('<[^>]+>','',str(value or '')))
    s=s.replace('–','--').replace('—','---').replace('λ',r'\lambda{}').replace('μ',r'\mu{}')
    s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    s=s.replace('&',r'\&').replace('%',r'\%').replace('_',r'\_').replace('#',r'\#')
    s=s.replace(r'\lambda{}',r'$\lambda$').replace(r'\mu{}',r'$\mu$')
    return s

def render():
    report=json.loads((ROOT/'results/doi-check.json').read_text());rows={r['key']:r for r in report['records']}
    template=(ROOT/'article/main.template.tex').read_text()
    expanded=template.replace(r'\input{related}',(ROOT/'article/related.tex').read_text())
    keys=[]
    for group in re.findall(r'\\cite\{([^}]+)\}',expanded):
        for key in group.split(','):
            if key not in keys:keys.append(key)
    bad=[k for k in keys if k!='nskf' and (k not in rows or not rows[k]['ok'])]
    if bad:raise RuntimeError('Unverified cited DOI: '+','.join(bad))
    text=[r'\begin{thebibliography}{99}']
    for k in keys:
        if k=='nskf':
            text.extend([r'\Bibitem{nskf}',r'\by Игнатенко А. С., Орда-Жигулина М. В.',r'\paper Исследование конфигурации вычислительной среды Edge--Fog',r'\inbook Тезисы НСКФ-2026. Материал предоставлен авторами; выходные сведения уточняются. DOI не подтверждён',r'\yr 2026',''])
            continue
        r=rows[k];authors=[]
        for a in r.get('authors',[]):authors.append(tex(a.get('family',a.get('name',''))+' '+a.get('given','')))
        if not authors:raise RuntimeError('No verified authors for '+k)
        text.extend([r'\Bibitem{'+k+'}',r'\by '+', '.join(authors),r'\paper '+tex(r['actual_title'])])
        container=next((x for x in r.get('container',[]) if x),'')
        if container:text.append(r'\jour '+tex(container))
        elif r.get('publisher'):text.append(r'\publ '+tex(r['publisher']))
        if r.get('volume'):text.append(r'\vol '+tex(r['volume']))
        if r.get('issue'):text.append(r'\issue '+tex(r['issue']))
        if r.get('year'):text.append(r'\yr '+str(r['year']))
        if r.get('pages') or r.get('article_number'):text.append(r'\pages '+tex(r.get('pages') or r['article_number']))
        text.extend([r'\doi '+r['doi'],''])
    text.append(r'\end{thebibliography}')
    (ROOT/'article/references_verified.tex').write_text('\n'.join(text)+'\n')
    try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.CalledProcessError):commit='LOCAL-UNCOMMITTED'
    link='https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud'
    available=(r'\paragraph{Доступность кода и данных.} Исходники, тетради, первичные CSV и журналы размещены в репозитории \url{'+link+'}. Проверяемая ветка --- \texttt{night/fefc-v3}. Исходный коммит выполненной сборки: '+(r'\texttt{'+commit+'}' if commit!='LOCAL-UNCOMMITTED' else '[локальная незакоммиченная сборка]')+r'. Результаты публикуются отдельным последующим коммитом; его идентификатор и запуск указаны в PR~2 и \texttt{results/final-check.txt}. Эталон \texttt{v2/} сохранён без изменений.'+'\n')
    (ROOT/'article/availability.tex').write_text(available)
    (ROOT/'results/citation-check.json').write_text(json.dumps({'cited_keys':keys,'doi_keys':[k for k in keys if k!='nskf'],'all_cited_doi_ok':not bad,'non_doi_exception':{'nskf':'supplied thesis; publication metadata pending'},'source_commit':commit},ensure_ascii=False,indent=2))
    print('References:',len(keys),'including',len(keys)-int('nskf'in keys),'verified DOI; thesis explicitly incomplete.')
if __name__=='__main__':render()
