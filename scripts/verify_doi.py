"""Verify DOI registration metadata with Crossref AND DataCite.

URL quoting already existed before Issue #4. A DataCite DOI is not made invalid
by a Crossref 404. No network failure is converted to a successful verification.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,urllib.request,urllib.parse,re,time,html
ROOT=Path(__file__).resolve().parents[1]

def norm(s):return ''.join(c for c in html.unescape(re.sub('<[^>]*>','',s)).lower() if c.isalnum())
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'FEFC-scientific-metadata-check/2.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)

def crossref(doi):
    url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
    d=get(url)['message'];date=d.get('published-print',d.get('issued',{})).get('date-parts',[[None]])[0]
    return {'registered_doi':d['DOI'],'actual_title':d.get('title',[''])[0],
        'authors':d.get('author',[]),'publisher':d.get('publisher'),'container':d.get('container-title',[]),
        'year':date[0],'volume':d.get('volume'),'issue':d.get('issue'),'pages':d.get('page'),
        'article_number':d.get('article-number'),'source':url,'registry':'Crossref'}

def datacite(doi):
    url='https://api.datacite.org/dois/'+urllib.parse.quote(doi,safe='')
    d=get(url)['data']['attributes'];container=d.get('container') or {};authors=[]
    for a in d.get('creators',[]):
        authors.append({'family':a.get('familyName') or a.get('name'),'given':a.get('givenName','')})
    pages=container.get('firstPage')
    if pages and container.get('lastPage'):pages+='--'+container['lastPage']
    return {'registered_doi':d['doi'],'actual_title':d['titles'][0]['title'],
        'authors':authors,'publisher':d.get('publisher'),'container':[container.get('title','')],
        'year':d.get('publicationYear'),'volume':container.get('volume'),'issue':container.get('issue'),
        'pages':pages,'article_number':None,'source':url,'registry':'DataCite','landing_page':d.get('url')}

def verify(item):
    row={**item,'expected_title':item['title'],'ok':False,'verified':False,'attempts':[]}
    functions=(datacite,crossref) if item['doi'].lower().startswith('10.4230/') else (crossref,datacite)
    for fn in functions:
        for attempt in range(2):
            try:
                metadata=fn(item['doi']);ok=metadata['registered_doi'].lower()==item['doi'].lower() and norm(item['title']) in norm(metadata['actual_title'])
                row.update(metadata);row.update(ok=ok,verified=ok)
                if not ok:row['attempts'].append({'registry':fn.__name__,'error':'DOI/title mismatch'})
                if ok:return row
                break
            except Exception as exc:
                row['attempts'].append({'registry':fn.__name__,'error':str(exc)})
                if attempt==0:time.sleep(.5)
    return row

def main():
    items=json.loads((ROOT/'article/references.json').read_text());rows=[verify(x) for x in items]
    result={'utc':datetime.now(timezone.utc).isoformat(),
      'note':'Registration metadata and title matching, not full peer review. DataCite and Crossref are different registries. Errors remain explicit.',
      'records':rows,'all_doi_ok':all(x['ok'] for x in rows),
      'non_doi_source':{'key':'nskf','source':'provided НСКФ-2026 thesis; Russian title/author block and docs/TASK.md',
        'title':'Исследование конфигурации вычислительной среды Edge-Fog',
        'authors':'А. С. Игнатенко; М. В. Орда-Жигулина','year':2026,'doi':None,
        'publication_metadata_confirmed':False,'status':'выходные сведения уточняются'}}
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'results/doi-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('DOI metadata:',sum(x['ok'] for x in rows),'/',len(rows),'verified; no invented success.')
    return result
if __name__=='__main__':main()
