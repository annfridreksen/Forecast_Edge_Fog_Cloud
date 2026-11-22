"""Single numerical claim registry shared by all four executed notebooks."""
from pathlib import Path
import json,math
import pandas as pd

def source_value(record,root=Path('.')):
    p=root/record['file']
    if p.suffix=='.csv':
        frame=pd.read_csv(p)
        for k,v in record.get('where',{}).items():frame=frame[frame[k]==v]
        if len(frame)!=1:raise AssertionError('claim selector is not unique: '+record['id'])
        return float(frame.iloc[0][record['field']])
    obj=json.loads(p.read_text())
    for k in record['field'].split('.'):obj=obj[k]
    return float(obj)

def publish(notebook,records,root=Path('.')):
    path=root/'results/claims.json';path.parent.mkdir(parents=True,exist_ok=True)
    data=json.loads(path.read_text()) if path.exists() else {'schema':'FEFC-claims-v1','claims':{}}
    if not isinstance(data,dict) or 'claims' not in data:raise ValueError('claims registry overwritten')
    table=[]
    for r in records:
        model=float(r['value']);file=source_value(r,root)
        if not math.isfinite(model) or not math.isclose(model,file,rel_tol=1e-10,abs_tol=1e-8):raise AssertionError(r['id'])
        data['claims'][r['id']]={**r,'notebook':notebook,'status':'verified against primary result','value':model}
        table.append({'показатель':r['id'],'число в статье':file,'число из модели':model,'проверка':'OK'})
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    return pd.DataFrame(table)

def verify(root=Path('.')):
    data=json.loads((root/'results/claims.json').read_text());seen=set()
    for r in data['claims'].values():
        assert math.isclose(r['value'],source_value(r,root),rel_tol=1e-10,abs_tol=1e-8),r['id']
        seen.add(r['notebook'][:2])
    assert seen=={'00','01','02','03'},seen
    return {'status':'OK','claims':len(data['claims']),'notebooks':sorted(seen)}
