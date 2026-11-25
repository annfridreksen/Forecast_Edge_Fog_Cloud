"""Verify article fields against actual outputs of the read-only notebook 01.

Uses the FROZEN article snapshot, never the newest scientific checkpoint.
No simulation/bootstrap/PDF build. An ID without a matching output is not proof.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from efc.main_summary import CELL_ID, OUTPUT_PREFIX
from efc.grid import read_json
from scripts.check_r14_paper import SPECS, KEY, get, make_evidence, verify_text


def verify_outputs(book, evidence, specs=None):
    specs = SPECS if specs is None else specs
    actual_tex = dict(re.findall(r'\\newcommand\{\\(\w+)\}\{([^}]+)\}', (ROOT/'article/r14-values.tex').read_text()))
    cells = [c for c in book['cells'] if c.get('id')==CELL_ID]
    if len(cells)!=1 or cells[0].get('cell_type')!='code' or cells[0].get('execution_count') is None:
        raise ValueError('missing/duplicate/unexecuted summary cell ID')
    cell=cells[0]
    if any(o.get('output_type')=='error' for o in cell.get('outputs',[])):
        raise ValueError('summary cell contains an execution error')
    text=''.join(''.join(o.get('text','')) for o in cell.get('outputs',[]) if o.get('output_type')=='stream')
    lines=[line[len(OUTPUT_PREFIX):] for line in text.splitlines() if line.startswith(OUTPUT_PREFIX)]
    if len(lines)!=1: raise ValueError('missing or ambiguous actual numeric output')
    data=json.loads(lines[0])
    if (data.get('schema')!='r14-notebook-summary-v1' or data.get('state')!='CHECKED_CHAINS'
        or data.get('selected_key')!=KEY or data.get('map_sha256')!=evidence['map_sha256']
        or data.get('manifest_sha256')!=evidence['manifest_sha256']
        or data.get('status')!=evidence['status'] or data.get('seed_ids')!=list(range(10))
        or data.get('simulation_executed') is not False or data.get('bootstrap_recomputed') is not False
        or data.get('scientific_acceptance') is not False):
        raise ValueError('executed summary does not match frozen scope/source')
    rows={r['field']:r for r in data['rows']}
    if len(rows)!=len(data['rows']): raise ValueError('duplicate output field')
    claims=[]
    for macro,(field,places,cell_id) in specs.items():
        if cell_id!=CELL_ID or field not in rows:
            raise ValueError('declared field/cell ID is absent from actual output: '+macro)
        row=rows[field];value=row['value'];expected=get(evidence,field)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isclose(value,expected,rel_tol=0,abs_tol=1e-9):
            raise ValueError('actual cell value differs from evidence: '+field)
        if f'{value:.{places}f}'.replace('.',',') != actual_tex.get(macro):
            raise ValueError('output field does not reproduce actual TeX macro: '+macro)
        if field.startswith('counts.'):
            if (data.get('counts_state')!='EXACT_PRIMARY_FILE_INVENTORY'
                or row.get('source_canonical_sha256')!=evidence['map_sha256']
                or row.get('primary_inventory_sha256')!=data['inventory']['primary_inventory_sha256']):
                raise ValueError('wrong count inventory/map source')
        elif (row.get('source_file')!=evidence['main_path']
              or row.get('source_byte_sha256')!=evidence['main_byte_sha256']
              or row.get('source_canonical_sha256')!=evidence['main_canonical_sha256']):
            raise ValueError('wrong main source path/hash')
        claims.append(dict(macro=macro,evidence_field=field,cell_id=cell_id,actual_output_field=field,
                           value=value,source_file=row['source_file'],
                           source_sha256=row.get('source_byte_sha256',row['source_canonical_sha256']),
                           actual_cell_output_checked=True,decimal_places=places))
    return claims


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--executed-notebook',type=Path,help='verify an existing execution; do not re-execute unchanged cells')
    p.add_argument('--out',type=Path,default=ROOT/'results/r14/current/trace')
    a=p.parse_args();out=a.out.resolve();checkpoint=a.checkpoint.resolve()
    if out.is_relative_to(checkpoint): p.error('output must not modify immutable checkpoint')
    out.mkdir(parents=True,exist_ok=True)
    evidence=read_json(ROOT/'results/r14/article_evidence.json')
    if make_evidence(checkpoint)!=evidence: raise ValueError('not the frozen article snapshot')
    verify_text(evidence,(ROOT/'article/r14-values.tex').read_text(),(ROOT/'article/main.tex').read_text(),
                (ROOT/'article/r14-references.tex').read_text())
    path=ROOT/'colab/01_Среда_и_конфигурация.ipynb'
    env={**os.environ,'FEFC_CHECKPOINT':str(checkpoint),'MPLBACKEND':'Agg'}
    command=[sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',str(path),
             '--output-dir',str(out),'--ExecutePreprocessor.timeout=180']
    executed = a.executed_notebook or out/path.name
    if a.executed_notebook is None:
        proc=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=360)
        (out/'nbconvert.log').write_bytes(proc.stdout)
        if proc.returncode: raise RuntimeError('notebook failed; exact log retained')
    book=read_json(executed)
    original=read_json(path)
    if [(c['id'],''.join(c['source'])) for c in book['cells']]!=[(c['id'],''.join(c['source'])) for c in original['cells']]:
        raise ValueError('executed cell sources differ from repository notebook')
    code=[c for c in book['cells'] if c['cell_type']=='code']
    if any(c.get('execution_count') is None or any(o.get('output_type')=='error' for o in c.get('outputs',[])) for c in code):
        raise ValueError('notebook has unexecuted/error cells')
    claims=verify_outputs(book,evidence)
    (out/'claim-index.json').write_text(json.dumps(claims,ensure_ascii=False,indent=2)+'\n')
    receipt=dict(status='PASS',verified_actual_outputs=len(claims),executed_code_cells=len(code),
                 frozen_scientific_run_id=evidence['scientific_run_id'],cell_id=CELL_ID,
                 existing_execution_reused=a.executed_notebook is not None,
                 execution='Actions/nbconvert' if os.getenv('GITHUB_ACTIONS')=='true' else 'local Python/nbconvert',
                 python=sys.version,simulation_executed=False,bootstrap_recomputed=False,pdf_rebuilt=False,
                 colab_browser_checked=False,notebook_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                 executed_notebook_sha256=hashlib.sha256(executed.read_bytes()).hexdigest())
    (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__': main()
