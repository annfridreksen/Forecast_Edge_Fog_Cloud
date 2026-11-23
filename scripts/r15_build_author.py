"""Fresh C build after author decisions 6-9; reuse unchanged raw evidence only."""
from pathlib import Path
import argparse,datetime as dt,json,os,re,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_r15_submission import (sha,put,download,unpack,compile_tex,package_zip,bibliography_report,
    marked_pdf_comparison,REPO,BASE,FROZEN_ID,FROZEN_SHA,BASE_ID,BASE_ZIP_SHA,BASE_PDF_SHA,STYLE_URL,FONT_EXT)
from scripts.check_r14_paper import make_evidence
from scripts.check_r14_trace import verify_outputs
from scripts.check_r15_paper import validate
from scripts.r15_zero_loss import analysis,macros


def compile_checked(root,name,logs):
    try:return compile_tex(root,name,logs)
    except Exception:
        for p in sorted(logs.glob('*.log'))[-1:]:print('\nTEX FAILURE\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-35:]),flush=True)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    out=p.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=True)
    work=out/'work';work.mkdir(exist_ok=True);delivery=out/'delivery';delivery.mkdir(exist_ok=True)
    receipt=dict(schema='R1.5-author69-build-1',source_sha=os.environ['R15_SOURCE_SHA'],
      simulation_executed=False,bootstrap_recomputed=False,ready_to_submit=False,author_signed=False,
      visual_review='PENDING_PAGE_INSPECTION')
    frozen_zip=work/'frozen131.zip'
    if not frozen_zip.exists():download(f'https://api.github.com/repos/{REPO}/actions/artifacts/{FROZEN_ID}/zip',frozen_zip,FROZEN_SHA,github=True)
    if sha(frozen_zip)!=FROZEN_SHA:raise ValueError('frozen ZIP mismatch')
    frozen=work/'frozen131'
    if not (frozen/'manifest.json').exists():unpack(frozen_zip,frozen)
    evidence=json.loads((ROOT/'results/r14/article_evidence.json').read_text())
    if make_evidence(frozen)!=evidence:raise ValueError('raw frozen evidence changed')
    cond=json.loads((ROOT/'results/r15/conditional_analysis.json').read_text())
    if cond!=analysis(frozen):raise ValueError('derived conditional evidence cannot be reproduced')
    if (ROOT/'article/r15-conditional-values.tex').read_text()!=macros(cond):raise ValueError('conditional display changed')
    prior=ROOT/'results/r15/prior-text/validation';accepted=json.loads((prior/'01_Среда_и_конфигурация.ipynb').read_text())
    original=json.loads((ROOT/'colab/01_Среда_и_конфигурация.ipynb').read_text())
    if [(c['id'],''.join(c['source'])) for c in accepted['cells']]!=[(c['id'],''.join(c['source'])) for c in original['cells']]:raise ValueError('accepted notebook changed')
    verify_outputs(accepted,evidence)
    text=(ROOT/'article/main.tex').read_text();bib=(ROOT/'article/r15-references.tex').read_text()
    analytic=json.loads((ROOT/'results/r15/service_reference.json').read_text());matrix=json.loads((ROOT/'article/r15-sources.json').read_text())
    receipt['static_validation']=validate(evidence,analytic,text,bib,(ROOT/'article/r15-values.tex').read_text(),matrix)
    receipt['conditional_status']=cond['decision']['status'];receipt['n_i']=[r['arrivals'] for r in cond['rows']]
    receipt['conditional_analysis_sha256']=sha(ROOT/'results/r15/conditional_analysis.json')
    shutil.copytree(prior,delivery/'validation/r14-frozen-output',dirs_exist_ok=True)
    for directory in ('author-tests','conditional-tests'):
        if (out/directory).exists():shutil.copytree(out/directory,delivery/'validation'/directory,dirs_exist_ok=True)
    manuscript=work/'manuscript';manuscript.mkdir(exist_ok=True)
    for name in ('main.tex','r15-values.tex','r15-conditional-values.tex','r15-references.tex','r15-sources.json','psta.cls'):
        shutil.copy2(ROOT/'article'/name,manuscript/name)
    shutil.copytree(ROOT/'article/psta',manuscript/'psta',dirs_exist_ok=True,
        ignore=lambda d,n:[x for x in n if Path(x).suffix.lower() in FONT_EXT])
    style=dict(url=STYLE_URL,retrieved_utc=dt.datetime.now(dt.timezone.utc).isoformat(),official_downloaded=False)
    try:
        archive=work/'official-psta.zip';style['archive_sha256']=download(STYLE_URL,archive)
        source=unpack(archive,work/'official-style');classes=sorted(source.rglob('psta.cls'),key=lambda p:len(p.parts))
        if not classes:raise ValueError('official archive missing class')
        for f in classes[0].parent.rglob('*'):
            if f.is_file() and f.suffix.lower() in ('.cls','.sty','.def','.cfg','.clo'):
                dest=manuscript/f.relative_to(classes[0].parent);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
        style['official_downloaded']=True
    except Exception as exc:style['failure']=type(exc).__name__+': '+str(exc)[:200]
    style['used_class_sha256']=sha(manuscript/'psta.cls')
    style['provides_class']=re.search(r'\\ProvidesClass[^\n]*',(manuscript/'psta.cls').read_text(errors='replace')).group(0)
    put(delivery/'style-provenance.json',style)
    pdf=compile_checked(manuscript,'main',out/'tex-logs');shutil.copy2(pdf,delivery/'article.pdf')
    receipt['pdf_sha256']=sha(pdf);receipt['style']=style
    package=work/'submission';package.mkdir(exist_ok=True)
    for f in manuscript.rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(manuscript)
        if f.suffix.lower() in ('.tex','.cls','.sty','.def','.cfg','.clo') or (rel.parts[0]=='psta' and f.suffix.lower() in ('.png','.pdf','.eps','.jpg')):
            dst=package/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
    for name in ('README.md','build.sh','NOTICE.md','cover_letter.md','author_checklist.md'):
        shutil.copy2(ROOT/'submission'/name,package/name);shutil.copy2(ROOT/'submission'/name,delivery/name)
    for name,src in [('article.pdf',pdf),('source-claim-matrix.json',ROOT/'article/r15-sources.json'),
                     ('empirical-evidence.json',ROOT/'results/r14/article_evidence.json'),('conditional_analysis.json',ROOT/'results/r15/conditional_analysis.json'),
                     ('analytic-evidence.json',ROOT/'results/r15/service_reference.json'),('style-provenance.json',delivery/'style-provenance.json')]:
        shutil.copy2(src,package/name)
        if name not in ('article.pdf','style-provenance.json'):shutil.copy2(src,delivery/name)
    previous=ROOT/'deliverables/r15/bibliography-report.json'
    bib_unchanged=not subprocess.check_output(['git','diff','1801dd37898e2d53eb2ab22a8dee532fd1083f5d','HEAD','--','article/r15-references.tex','article/r15-sources.json'],cwd=ROOT)
    if previous.exists() and bib_unchanged:
        shutil.copy2(previous,delivery/'bibliography-report.json')
        rows=json.loads(previous.read_text())['rows']
        receipt['bibliography_registry_reused_from']='45286829771; unchanged reference text and source matrix'
    else:
        rows=bibliography_report(ROOT/'article',delivery)
    shutil.copy2(delivery/'bibliography-report.json',package/'bibliography-report.json')
    print('BIBLIOGRAPHY_STATUS',json.dumps([{'key':r['key'],'status':r['fresh_metadata_check']} for r in rows]),flush=True)
    package_zip(package,delivery/'submission.zip')
    import fitz
    with tempfile.TemporaryDirectory(prefix='fefc-r15-isolated-') as tmp:
        fresh=unpack(delivery/'submission.zip',Path(tmp)/'source');freshpdf=compile_checked(fresh,'main',out/'isolated-logs')
        with fitz.open(pdf) as aa,fitz.open(freshpdf) as bb:
            if len(aa)!=len(bb) or [p.get_text() for p in aa]!=[p.get_text() for p in bb]:raise ValueError('isolated PDF differs')
        receipt.update(isolated_zip_rebuild='PASS',isolated_pdf_sha256=sha(freshpdf))
    pages=delivery/'pages';pages.mkdir(exist_ok=True);ledger=[]
    with fitz.open(pdf) as doc:
        receipt['pages']=len(doc);locations={}
        for i,p in enumerate(doc):
            pt=p.get_text();p.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(pages/f'page-{i+1:02}.png')
            drawings=p.get_drawings();ledger.append(dict(page=i+1,pdf_sha256=sha(pdf),text_characters=len(pt),vector_paths=len(drawings),visual_status='PENDING'))
            for key,phrase in [('section6','6. Развитие среды'),('section7','7. Обсуждение')]:
                found=p.search_for(phrase)
                if found and key not in locations:locations[key]=dict(page=i+1,y=found[0].y0,height=p.rect.height)
            if len(drawings)>12 and not (pages/'vector-crop-7x.png').exists():
                rr=drawings[0]['rect'];clip=fitz.Rect(max(0,rr.x0-4),max(0,rr.y0-4),min(p.rect.width,rr.x0+180),min(p.rect.height,rr.y0+120))
                p.get_pixmap(matrix=fitz.Matrix(7,7),clip=clip,alpha=False).save(pages/'vector-crop-7x.png')
        receipt['section_boundaries']=locations
    put(delivery/'page-review.json',ledger)
    basezip=work/'baseline-artifact.zip';download(f'https://api.github.com/repos/{REPO}/actions/artifacts/{BASE_ID}/zip',basezip,BASE_ZIP_SHA,github=True)
    baseroot=unpack(basezip,work/'baseline-artifact');basepdf=next(p for p in baseroot.rglob('*.pdf') if sha(p)==BASE_PDF_SHA)
    shutil.copy2(basepdf,delivery/'before_R14.pdf');diffroot=work/'diff';shutil.copytree(manuscript,diffroot,dirs_exist_ok=True)
    for name in ('main.tex','r14-values.tex','r14-references.tex'):
        data=subprocess.check_output(['git','show',BASE+':article/'+name],cwd=ROOT)
        (diffroot/('before.tex' if name=='main.tex' else name)).write_bytes(data)
    ds=dict(baseline_sha=BASE,baseline_pdf_sha256=BASE_PDF_SHA,after_pdf_sha256=sha(pdf))
    try:
        cmd=['latexdiff','--type=CFONT','--encoding=utf8','--flatten','--math-markup=0','--disable-citation-markup','before.tex','main.tex']
        r=subprocess.run(cmd,cwd=diffroot,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
        (out/'latexdiff-stderr.log').write_bytes(r.stderr)
        if r.returncode:raise RuntimeError('latexdiff returned '+str(r.returncode))
        if b'\\documentclass' not in r.stdout:raise ValueError('latexdiff TeX output missing class')
        (diffroot/'difference.tex').write_bytes(r.stdout)
        dp=compile_checked(diffroot,'difference',out/'diff-logs');shutil.copy2(dp,delivery/'difference.pdf')
        ds.update(method='latexdiff',requested_utility_success=True)
    except Exception as exc:
        ds.update(method='PDF-word-difference fallback',requested_utility_success=False,failure=type(exc).__name__+': '+str(exc)[:200])
        marked_pdf_comparison(basepdf,pdf,delivery/'difference.pdf')
    put(delivery/'difference-provenance.json',ds);receipt['diff']=ds
    dm=dict(original_name='frozen131.zip',sha256=FROZEN_SHA,size=frozen_zip.stat().st_size,scientific_run_id=45174257711,parts=[])
    with frozen_zip.open('rb') as f:
        index=0
        while chunk:=f.read(80*1024*1024):
            name=f'frozen131.zip.part{index:02}';dest=delivery/name;dest.write_bytes(chunk);dm['parts'].append(dict(name=name,size=len(chunk),sha256=sha(dest)));index+=1
    put(delivery/'data-parts.json',dm)
    repro=work/'reproducibility';repro.mkdir(exist_ok=True)
    for folder in ('efc','scripts','colab','configs'):
        for f in (ROOT/folder).rglob('*'):
            if f.is_file() and f.suffix in ('.py','.mjs','.ipynb','.json'):
                dst=repro/f.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
    for f in (ROOT/'requirements.txt',ROOT/'results/r14/article_evidence.json',ROOT/'results/r15/service_reference.json',ROOT/'results/r15/conditional_analysis.json'):
        dst=repro/f.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
    for name in ('README.md','reassemble.py'):shutil.copy2(ROOT/'submission'/name,repro/name)
    shutil.copy2(delivery/'data-parts.json',repro/'data-parts.json');shutil.copy2(ROOT/'submission/reassemble.py',delivery/'reassemble.py')
    package_zip(repro,delivery/'reproducibility.zip')
    receipt.update(submission_zip_sha256=sha(delivery/'submission.zip'),difference_pdf_sha256=sha(delivery/'difference.pdf'),
                   data_complete_for_frozen_131=True,public_access='PENDING_PUBLICATION_AND_ANONYMOUS_DOWNLOAD')
    put(delivery/'build-receipt.json',receipt);put(out/'receipt.json',receipt)
    put(delivery/'SHA256.json',{p.relative_to(delivery).as_posix():sha(p) for p in sorted(delivery.rglob('*')) if p.is_file()})
    print('BUILD_RECEIPT',json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
