"""Provenance describes the final article, not the intermediate template output."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results';A=ROOT/'article'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=R/'article-provenance.json'
    old=json.loads(p.read_text())
    (R/'article-provenance-intermediate.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
    data=json.loads((R/'build-summary.json').read_text())
    check=json.loads((R/'issue4-article-check.json').read_text())
    cited=json.loads((R/'citation-check.json').read_text())
    assert check['article_sha256']==digest(A/'main.tex')
    records=json.loads((R/'claims.json').read_text())
    calls={'00':('simulate','controls','publish'),'01':('configuration_series','stationary_series','sensitivity_series','publish'),'02':('forecast_study','publish'),'03':('controls','neural_placement','background_accounting','publish')}
    cell_map={}
    for nb in sorted((ROOT/'colab').glob('*.ipynb')):
        content=json.loads(nb.read_text());entries=[]
        for index,cell in enumerate(content['cells'],1):
            if cell['cell_type']!='code':continue
            source=cell['source'];source=''.join(source) if isinstance(source,list) else source
            matched=[name for name in calls[nb.name[:2]] if name+'(' in source]
            if matched:entries.append({'notebook_cell_1based':index,'cell_id':cell.get('id'),'execution_count':cell.get('execution_count'),'calls':matched})
        assert entries,nb.name
        cell_map[nb.name]=entries
    for rec in records['claims'].values():
        rec['source_notebook_cells']=cell_map[rec['notebook']]
    (R/'claims.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    final={**old,'source_commit':data['source_commit'],'main_tex_sha256':digest(A/'main.tex'),'main_pdf_sha256':digest(A/'main.pdf'),'final_not_intermediate':True,'related_tex_sha256':digest(A/'related.tex'),'verified_bibliography_sha256':digest(A/'references_verified.tex'),'source_files':{**old['source_files'],**check['source_files']},'all_cited_doi_ok':cited['all_cited_doi_ok'],'numeric_claim_records':len(records['claims']),'exact_notebook_cells':cell_map,'limitation':'Hash and scalar checks do not establish scientific validity or manual visual inspection.'}
    p.write_text(json.dumps(final,ensure_ascii=False,indent=2))
    text='\n\n## Точные номера выполненных ячеек\nНумерация ниже включает Markdown-ячейки (индекс в notebook, начиная с 1). execution_count — фактический порядок выполнения кодовой ячейки.\n'
    for notebook,entries in cell_map.items():
        for entry in entries:text+=f"- {notebook}: ячейка {entry['notebook_cell_1based']}, id={entry['cell_id']}, execution_count={entry['execution_count']}, вызовы={','.join(entry['calls'])}.\n"
    with (ROOT/'docs/Утверждения.md').open('a') as out:out.write(text)
    print('Final provenance hashes and notebook cell mapping: PASS')
if __name__=='__main__':main()
