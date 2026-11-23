"""C-stage entry point after the verified end-of-bibliography failure.
Reuses packaging primitives, not the obsolete first C-stage main function.
The only bibliography change from B is a mandatory paragraph terminator.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import datetime as dt
import re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_r15_submission import (sha,put,download,unpack,compile_tex,command,
    package_zip,bibliography_report,marked_pdf_comparison,REPO,BASE,FROZEN_ID,
    FROZEN_SHA,BASE_ID,BASE_ZIP_SHA,BASE_PDF_SHA,STYLE_URL,FONT_EXT)
from scripts.check_r14_paper import make_evidence
from scripts.check_r14_trace import verify_outputs
from scripts.check_r15_paper import validate


def compile_checked(directory,name,logs):
    try:return compile_tex(directory,name,logs)
    except Exception:
        for p in sorted(logs.glob('*.log'))[-1:]:
            print('\nFAILED TEX TAIL '+str(p)+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-45:]),flush=True)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    delivery=out/'delivery';delivery.mkdir(exist_ok=True)
    work=out/'work';work.mkdir(exist_ok=True)
    receipt={'schema':'R1.5-package-build-2','source_sha':os.environ.get('GITHUB_SHA'),
      'base_source_sha':BASE,'simulation_executed':False,'bootstrap_recomputed':False,
      'author_signed':False,'submission_ready':False,'visual_review':'PENDING_PAGE_INSPECTION'}
    put(out/'receipt.json',receipt)
    frozen_zip=work/'frozen131.zip'
    download(f'https://api.github.com/repos/{REPO}/actions/artifacts/{FROZEN_ID}/zip',frozen_zip,FROZEN_SHA,github=True)
    frozen=unpack(frozen_zip,work/'frozen131');receipt['frozen_zip_sha256']=sha(frozen_zip)
    prior=ROOT/'results/r15/prior-text/validation';vr=json.loads((prior/'validation.json').read_text())
    text=(ROOT/'article/main.tex').read_text();bib=(ROOT/'article/r15-references.tex').read_text()
    old_bib=subprocess.check_output(['git','show','5b2a5987d1a148545eae678dba770d66df9a9cb7:article/r15-references.tex'],cwd=ROOT).decode()
    if vr['article_sha256']!=sha(ROOT/'article/main.tex'):
        raise ValueError('B-stage article text changed: new validation required')
    # Explicit compatibility proof, not a false claim that the corrected bibliography ran in B.
    if bib.replace('\n\n\\end{thebibliography}', '\n\\end{thebibliography}')!=old_bib:
        raise ValueError('Bibliography changed beyond the inspected paragraph terminator')
    if '\n\n\\end{thebibliography}' not in bib:
        raise ValueError('Last PSTA field lacks its paragraph terminator')
    e=json.loads((ROOT/'results/r14/article_evidence.json').read_text())
    if make_evidence(frozen)!=e:raise ValueError('fresh primary evidence mismatch')
    analytic=json.loads((ROOT/'results/r15/service_reference.json').read_text())
    matrix=json.loads((ROOT/'article/r15-sources.json').read_text())
    validate(e,analytic,text,bib,(ROOT/'article/r15-values.tex').read_text(),matrix)
    executed=json.loads((prior/'01_Среда_и_конфигурация.ipynb').read_text())
    original=json.loads((ROOT/'colab/01_Среда_и_конфигурация.ipynb').read_text())
    if [(c['id'],''.join(c['source'])) for c in executed['cells']]!=[(c['id'],''.join(c['source'])) for c in original['cells']]:
        raise ValueError('Accepted notebook execution is stale')
    verify_outputs(executed,e)
    shutil.copytree(prior,delivery/'validation',dirs_exist_ok=True)
    receipt.update(prior_B_execution_reused=True,fresh_primary_verification=True,
      bibliography_change='one paragraph terminator before end{thebibliography}; scientific content unchanged',
      new_bibliography_validation='static content and subsequent fresh TeX execution')
    manuscript=work/'manuscript';manuscript.mkdir(exist_ok=True)
    for name in ('main.tex','r15-values.tex','r15-references.tex','r15-sources.json','psta.cls'):
        shutil.copy2(ROOT/'article'/name,manuscript/name)
    shutil.copytree(ROOT/'article/psta',manuscript/'psta',dirs_exist_ok=True,
      ignore=lambda d,n:[x for x in n if Path(x).suffix.lower() in FONT_EXT])
    style={'url':STYLE_URL,'retrieved_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'official_downloaded':False}
    try:
        archive=work/'official-psta.zip';style['archive_sha256']=download(STYLE_URL,archive)
        extracted=unpack(archive,work/'official-style')
        classes=sorted(extracted.rglob('psta.cls'),key=lambda p:len(p.parts))
        if not classes:raise ValueError('official style has no psta.cls')
        parent=classes[0].parent
        for f in parent.rglob('*'):
            if f.is_file() and f.suffix.lower() in ('.cls','.sty','.def','.cfg','.clo'):
                target=manuscript/f.relative_to(parent);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
        style['official_downloaded']=True
    except Exception as exc:style['failure']=type(exc).__name__+': '+str(exc)[:200]
    style['used_class_sha256']=sha(manuscript/'psta.cls')
    style['provides_class']=re.search(r'\\ProvidesClass[^\n]*',(manuscript/'psta.cls').read_text(errors='replace')).group(0)
    put(delivery/'style-provenance.json',style)
    pdf=compile_checked(manuscript,'main',out/'tex-logs');shutil.copy2(pdf,delivery/'article.pdf')
    receipt.update(pdf_sha256=sha(pdf),style=style)
    package=work/'submission';package.mkdir(exist_ok=True)
    for p in manuscript.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(manuscript)
        allowed=p.suffix.lower() in ('.tex','.cls','.sty','.def','.cfg','.clo')
        # Official style's DOI/URL icons are compilation inputs, not author raster figures.
        allowed=allowed or (rel.parts[0]=='psta' and p.suffix.lower() in ('.png','.pdf','.jpg','.eps'))
        if allowed:
            dest=package/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    for name in ('README.md','build.sh','NOTICE.md','cover_letter.md','author_checklist.md'):
        shutil.copy2(ROOT/'submission'/name,package/name);shutil.copy2(ROOT/'submission'/name,delivery/name)
    for src,dst in [(pdf,'article.pdf'),(ROOT/'article/r15-sources.json','source-claim-matrix.json'),
                    (delivery/'style-provenance.json','style-provenance.json'),
                    (ROOT/'results/r14/article_evidence.json','empirical-evidence.json'),
                    (ROOT/'results/r15/service_reference.json','analytic-evidence.json')]:shutil.copy2(src,package/dst)
    bibliography_report(ROOT/'article',delivery);shutil.copy2(delivery/'bibliography-report.json',package/'bibliography-report.json')
    package_zip(package,delivery/'submission.zip')
    import fitz
    with tempfile.TemporaryDirectory(prefix='fefc-r15-isolated-') as tmp:
        fresh=unpack(delivery/'submission.zip',Path(tmp)/'source')
        fresh_pdf=compile_checked(fresh,'main',out/'isolated-logs')
        with fitz.open(pdf) as aa,fitz.open(fresh_pdf) as bb:
            if len(aa)!=len(bb) or [p.get_text() for p in aa]!=[p.get_text() for p in bb]:
                raise ValueError('isolated ZIP build text differs')
        receipt.update(isolated_pdf_sha256=sha(fresh_pdf),isolated_zip_rebuild='PASS')
    pages=delivery/'pages';pages.mkdir(exist_ok=True);ledger=[]
    with fitz.open(pdf) as doc:
        for i,p in enumerate(doc):
            p.get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(pages/f'page-{i+1:02}.png')
            drawings=p.get_drawings()
            ledger.append(dict(page=i+1,text_characters=len(p.get_text()),raster_image_count=len(p.get_images(full=True)),
                               vector_paths=len(drawings),visual_status='PENDING',pdf_sha256=sha(pdf)))
            if len(drawings)>12 and not (pages/'vector-crop-7x.png').exists():
                rect=drawings[0]['rect']
                clip=fitz.Rect(max(0,rect.x0-5),max(0,rect.y0-5),min(p.rect.width,rect.x0+180),min(p.rect.height,rect.y0+120))
                p.get_pixmap(matrix=fitz.Matrix(7,7),clip=clip,alpha=False).save(pages/'vector-crop-7x.png')
        receipt['pages']=len(doc)
    put(delivery/'page-review.json',ledger)
    baseline_zip=work/'baseline-artifact.zip'
    download(f'https://api.github.com/repos/{REPO}/actions/artifacts/{BASE_ID}/zip',baseline_zip,BASE_ZIP_SHA,github=True)
    base_root=unpack(baseline_zip,work/'baseline-artifact')
    old_pdfs=[p for p in base_root.rglob('*.pdf') if sha(p)==BASE_PDF_SHA]
    if not old_pdfs:raise ValueError('baseline PDF hash not found')
    shutil.copy2(old_pdfs[0],delivery/'before_R14.pdf')
    diffdir=work/'diff';shutil.copytree(manuscript,diffdir,dirs_exist_ok=True)
    for name in ('main.tex','r14-values.tex','r14-references.tex'):
        data=subprocess.check_output(['git','show',BASE+':article/'+name],cwd=ROOT)
        (diffdir/('before.tex' if name=='main.tex' else name)).write_bytes(data)
    diff_status=dict(baseline_sha=BASE,baseline_pdf_sha256=BASE_PDF_SHA,after_pdf_sha256=sha(pdf))
    try:
        generated=command(['latexdiff','--encoding=utf8','--flatten','--math-markup=0','--disable-citation-markup','before.tex','main.tex'],diffdir,out/'latexdiff-output.log')
        (diffdir/'difference.tex').write_bytes(generated)
        changed=compile_checked(diffdir,'difference',out/'diff-logs')
        shutil.copy2(changed,delivery/'difference.pdf');diff_status.update(method='latexdiff',requested_utility_success=True)
    except Exception as exc:
        diff_status.update(method='PDF-word-difference fallback',requested_utility_success=False,failure=type(exc).__name__+': '+str(exc)[:300])
        marked_pdf_comparison(old_pdfs[0],pdf,delivery/'difference.pdf')
    put(delivery/'difference-provenance.json',diff_status)
    data_manifest=dict(original_name='frozen131.zip',sha256=FROZEN_SHA,size=frozen_zip.stat().st_size,scientific_run_id=45174257711,parts=[])
    with frozen_zip.open('rb') as f:
        index=0
        while chunk:=f.read(80*1024*1024):
            name=f'frozen131.zip.part{index:02}';p=delivery/name;p.write_bytes(chunk)
            data_manifest['parts'].append(dict(name=name,size=len(chunk),sha256=sha(p)));index+=1
    put(delivery/'data-parts.json',data_manifest)
    repro=work/'reproducibility';repro.mkdir(exist_ok=True)
    for folder in ('efc','scripts','colab','configs'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.mjs','.ipynb','.json'):
                d=repro/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
    for f in (ROOT/'requirements.txt',ROOT/'results/r14/article_evidence.json',ROOT/'results/r15/service_reference.json'):
        d=repro/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d)
    for name in ('reassemble.py','README.md'):shutil.copy2(ROOT/'submission'/name,repro/name)
    shutil.copy2(delivery/'data-parts.json',repro/'data-parts.json');shutil.copy2(ROOT/'submission/reassemble.py',delivery/'reassemble.py')
    package_zip(repro,delivery/'reproducibility.zip')
    receipt.update(submission_zip_sha256=sha(delivery/'submission.zip'),difference_pdf_sha256=sha(delivery/'difference.pdf'),
                   diff=diff_status,data_complete_for_frozen_131=True,public_access='PENDING_PUBLICATION_AND_ANONYMOUS_DOWNLOAD')
    put(delivery/'build-receipt.json',receipt);put(out/'receipt.json',receipt)
    put(delivery/'SHA256.json',{p.relative_to(delivery).as_posix():sha(p) for p in sorted(delivery.rglob('*')) if p.is_file()})
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
