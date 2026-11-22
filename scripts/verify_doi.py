"""Check publisher-deposited DOI metadata; network failures remain explicit."""
from pathlib import Path
from datetime import datetime,timezone
import json,urllib.request,urllib.parse,time
ROOT=Path(__file__).resolve().parents[1]
ITEMS=[('10.1145/2342509.2342513','Fog computing and its role in the internet of things'),
('10.1109/JIOT.2016.2579198','Edge Computing: Vision and Challenges'),
('10.1109/71.993206','Performance-effective and low-complexity task scheduling for heterogeneous computing'),
('10.1002/spe.2766','How to place your apps in the fog'),
('10.4230/LIPIcs.APPROX/RANDOM.2020.60','Better and Simpler Learning-Augmented Online Caching'),
('10.1287/opre.9.3.383','A Proof for the Queuing Formula')]
rows=[]
for doi,title in ITEMS:
    url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'FEFC-scientific-metadata-check/1.0'})
        data=json.load(urllib.request.urlopen(request,timeout=30))['message']
        actual=data.get('title',[''])[0]
        ok=data['DOI'].lower()==doi.lower() and title.lower() in actual.lower()
        rows.append({'doi':doi,'expected_title':title,'actual_title':actual,'publisher':data.get('publisher'),'container':data.get('container-title'),'issued':data.get('issued'),'volume':data.get('volume'),'issue':data.get('issue'),'pages':data.get('page'),'authors':data.get('author'),'verified':ok,'source':url})
    except Exception as exc:rows.append({'doi':doi,'expected_title':title,'verified':False,'error':str(exc),'source':url})
(ROOT/'results/doi-check.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'note':'Publisher-deposited Crossref metadata, not a full independent review of each paper. Website checks are listed in docs/Источники.md.','records':rows},ensure_ascii=False,indent=2))
print('DOI metadata:',sum(x['verified'] for x in rows),'/',len(rows),'verified; failures retained, not fabricated.')
