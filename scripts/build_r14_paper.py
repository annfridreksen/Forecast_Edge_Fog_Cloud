"""Scoped PSTA build: no historical simulator, predictor, or bootstrap execution."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'results/r14/current/paper')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    def run(cmd,name,cwd=ROOT):
        proc=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
        (out/(name+'.log')).write_bytes(proc.stdout)
        if proc.returncode:raise RuntimeError(name+' failed; exact log retained')
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for base in ('v2','efc') for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    cmd=[sys.executable,'scripts/check_r14_paper.py','--out',str(out)]
    if a.checkpoint:cmd+=['--checkpoint',str(a.checkpoint.resolve())]
    run(cmd,'evidence')
    run([sys.executable,'-m','unittest','discover','-s','article/tests','-v'],'tests')
    style=hashlib.sha256((ROOT/'article/psta.cls').read_bytes()).hexdigest()
    if style!='f0fdb7c786dd54fb5f066a58630a7b67235a01871457f5dcd26c48b6d476ea1b':
        raise RuntimeError('official retained class differs')
    for k in (1,2,3):
        run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],f'latex-{k}',ROOT/'article')
    log=(ROOT/'article/main.log').read_text(errors='replace')
    if any(s in log for s in ('Overfull \\hbox','There were undefined references','Citation `','! Undefined control sequence')):
        raise RuntimeError('unresolved layout/references; inspect retained log')
    shutil.copy2(ROOT/'article/main.pdf',out/'FEFC_R14_partial_article.pdf')
    run(['pdfinfo',str(out/'FEFC_R14_partial_article.pdf')],'pdfinfo')
    run(['pdftotext','-layout',str(out/'FEFC_R14_partial_article.pdf'),str(out/'article.txt')],'text')
    run(['pdftoppm','-scale-to','1100','-png',str(out/'FEFC_R14_partial_article.pdf'),str(out/'page')],'render')
    for path,h in before.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise RuntimeError('protected/scientific file changed')
    data=dict(status='COMPILED_AND_NUMBERS_CHECKED',utc=datetime.now(timezone.utc).isoformat(),
              build_sha=os.environ.get('GITHUB_SHA','LOCAL_UNCOMMITTED'),python=sys.version,
              platform=platform.platform(),scientific_simulation=False,bootstrap_recomputed=False,
              author_or_reviewer_approval=False,submission_ready=False,style_sha256=style,
              pdf_sha256=hashlib.sha256((out/'FEFC_R14_partial_article.pdf').read_bytes()).hexdigest(),
              source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'article/main.tex',ROOT/'article/r14-values.tex',ROOT/'article/r14-references.tex',ROOT/'results/r14/article_evidence.json',ROOT/'scripts/check_r14_paper.py',ROOT/'scripts/build_r14_paper.py']})
    (out/'build-receipt.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('PASS: scoped partial article; not full scientific acceptance; rendered pages need visual review.')

if __name__=='__main__':main()
