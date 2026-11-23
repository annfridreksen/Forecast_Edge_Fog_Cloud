"""Build and package R1.5 from exact sources on a fresh runner.
No scientific simulation, bootstrap, author signature, or journal submission.
"""
from pathlib import Path, PurePosixPath
import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE='59914cea5dc733ec857ae3d4157d77398bae7cd5'
REPO='annfridreksen/Forecast_Edge_Fog_Cloud'
FROZEN_ID=14820151165
FROZEN_SHA='2cb91dbc964a641c36fb53e02ddea3590bf8fe939933f43b31399267508d40ef'
BASE_ID=14823489832
BASE_ZIP_SHA='d0b0059d719b8632aa800060e8a0c2739921a19f720827e7ac8dea26e73bbc40'
BASE_PDF_SHA='2c24e693106be38e9e56de8ff33610b7a45eab1e10905dfac3d0a0be2b41e920'
STYLE_URL='https://psta.psiras.ru/publ-conditions/psta.zip'
FONT_EXT={'.ttf','.otf','.woff','.woff2','.pfb','.pfa','.afm','.tfm','.vf','.enc'}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def put(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def download(url,destination,expected=None,github=False):
    headers={'User-Agent':'FEFC-R15-reproducible-build'}
    if github:
        token=os.environ.get('GITHUB_TOKEN')
        if not token:raise RuntimeError('GitHub token unavailable for restoring authorized artifact')
        request=urllib.request.Request(url,headers={**headers,'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        try: response=urllib.request.build_opener(NoRedirect).open(request,timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code not in (301,302,303,307,308):raise RuntimeError('Artifact restore HTTP '+str(exc.code)) from None
            url=exc.headers.get('Location')
            if not url:raise RuntimeError('Artifact redirect missing')
            # Never forward the GitHub token to the object-storage hostname.
            response=urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=120)
    else:response=urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=120)
    Path(destination).parent.mkdir(parents=True,exist_ok=True)
    with response,Path(destination).open('wb') as f:shutil.copyfileobj(response,f,1<<20)
    actual=sha(destination)
    if expected and actual!=expected:raise ValueError('Downloaded archive SHA256 mismatch')
    return actual


def unpack(archive,destination):
    root=Path(destination).resolve();root.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            p=PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename:
                raise ValueError('Unsafe archive path')
            if ((item.external_attr>>16)&0o170000)==0o120000:raise ValueError('Archive symlink rejected')
            target=(root/item.filename).resolve()
            if not target.is_relative_to(root):raise ValueError('Archive escapes destination')
            if item.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(item) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst,1<<20)
    return root


def command(args,cwd,log,timeout=900):
    env={**os.environ,'SOURCE_DATE_EPOCH':'1795478400','FORCE_SOURCE_DATE':'1'}
    result=subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    Path(log).parent.mkdir(parents=True,exist_ok=True);Path(log).write_bytes(result.stdout)
    if result.returncode:raise RuntimeError('Failed '+str(args[0])+'; exact log '+str(log))
    return result.stdout


def compile_tex(directory,name,logs):
    logs.mkdir(parents=True,exist_ok=True)
    for i in range(3):
        command(['pdflatex','-interaction=nonstopmode','-halt-on-error','-file-line-error','-recorder',name+'.tex'],directory,logs/f'pass-{i+1}.log')
    log=(directory/(name+'.log')).read_text(errors='replace')
    forbidden=['Undefined control sequence','LaTeX Error','There were undefined references','Citation `','Reference `','Emergency stop']
    errors=[s for s in forbidden if s in log]
    if errors:raise ValueError('Unresolved TeX error/reference: '+repr(errors))
    warnings=[line for line in log.splitlines() if 'Warning' in line or 'Overfull' in line or 'Underfull' in line]
    put(logs/'warnings.json',warnings)
    return directory/(name+'.pdf')


def package_zip(source,destination):
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(source.rglob('*')):
            if p.is_file():
                if p.suffix.lower() in FONT_EXT:raise ValueError('Font file cannot be distributed')
                z.write(p,p.relative_to(source).as_posix())


def normalize(text):
    text=unicodedata.normalize('NFKD',str(text))
    return re.sub(r'[^a-z0-9]+',' ',text.lower()).strip()


def bibliography_report(article,out):
    matrix=json.loads((article/'r15-sources.json').read_text())
    bib=(article/'r15-references.tex').read_text()
    blocks={m.group(1):m.group(2) for m in re.finditer(r'\\R?Bibitem\{([^}]+)\}(.*?)(?=\\R?Bibitem|\\end\{thebibliography\})',bib,re.S)}
    rows=[]
    for e in matrix['entries']:
        r=dict(e)
        if not e.get('doi'):
            r['fresh_metadata_check']='AUTHOR_REQUIRED' if e['key']=='nskf' else 'IDENTIFIER_IN_PRIMARY_RECORD'
            rows.append(r);continue
        try:
            url='https://api.crossref.org/works/'+urllib.parse.quote(e['doi'],safe='')
            req=urllib.request.Request(url,headers={'User-Agent':'FEFC-PSTA-bibliography-check/1.5'})
            with urllib.request.urlopen(req,timeout=25) as f:data=json.load(f)['message']
            title=re.search(r'\\paper ([^\n]+)',blocks[e['key']]).group(1)
            remote=' '.join(data.get('title',[]))
            score=difflib.SequenceMatcher(None,normalize(title),normalize(remote)).ratio()
            years={data[k]['date-parts'][0][0] for k in ('issued','published','published-print','published-online') if k in data and data[k].get('date-parts')}
            author_line=re.search(r'\\by ([^\n]+)',blocks[e['key']]).group(1)
            families=[a.get('family','') for a in data.get('author',[])]
            r.update(fresh_metadata_check='MATCH' if score>=.78 and e['year'] in years else 'REVIEW_METADATA',
                     title_from_registry=remote,title_similarity=score,registry_years=sorted(years),
                     registry_authors=families,manuscript_author_line=author_line,
                     registry_container=data.get('container-title'),registry_volume=data.get('volume'),
                     registry_issue=data.get('issue'),registry_pages=data.get('page') or data.get('article-number'))
        except Exception as exc:r.update(fresh_metadata_check='NETWORK_UNCONFIRMED',error=type(exc).__name__)
        rows.append(r)
    put(out/'bibliography-report.json',{'rows':rows,'scope':'Fresh registry lookup supports metadata only; claim passages are separately documented. No source is silently rewritten.'})
    return rows


def marked_pdf_comparison(before,after,target):
    """Honest PDF-level fallback if latexdiff cannot process a journal macro."""
    import fitz
    old,new=fitz.open(before),fitz.open(after)
    ow=[(i,w) for i,p in enumerate(old) for w in p.get_text('words')]
    nw=[(i,w) for i,p in enumerate(new) for w in p.get_text('words')]
    for tag,i,j,k,l in difflib.SequenceMatcher(None,[x[1][4] for x in ow],[x[1][4] for x in nw],autojunk=False).get_opcodes():
        if tag=='equal':continue
        for page,w in ow[i:j]:old[page].draw_rect(fitz.Rect(w[:4]),color=(.85,0,0),width=.7)
        for page,w in nw[k:l]:new[page].draw_rect(fitz.Rect(w[:4]),color=(0,.45,0),width=.7)
    result=fitz.open()
    for i in range(max(len(old),len(new))):
        p=result.new_page(width=842,height=595)
        p.insert_text((20,18),'BEFORE 59914cea (red changes) | AFTER R1.5 (green changes)',fontsize=10)
        if i<len(old):p.show_pdf_page(fitz.Rect(15,30,414,580),old,i)
        if i<len(new):p.show_pdf_page(fitz.Rect(428,30,827,580),new,i)
    result.save(target);result.close();old.close();new.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    delivery=out/'delivery';delivery.mkdir(exist_ok=True)
    work=out/'work';work.mkdir(exist_ok=True)
    source_sha=os.environ.get('GITHUB_SHA','unknown')
    receipt={'schema':'R1.5-package-build-1','source_sha':source_sha,'base_source_sha':BASE,
             'simulation_executed':False,'bootstrap_recomputed':False,'author_signed':False,
             'submission_ready':False,'visual_review':'PENDING_HUMAN_OR_ASSISTANT_PAGE_INSPECTION'}
    put(out/'receipt.json',receipt)
    # Measured raw ZIP, not merely the API-declared digest.
    frozen_zip=work/'frozen131.zip'
    download(f'https://api.github.com/repos/{REPO}/actions/artifacts/{FROZEN_ID}/zip',frozen_zip,FROZEN_SHA,github=True)
    frozen=unpack(frozen_zip,work/'frozen131')
    receipt['frozen_zip_sha256']=sha(frozen_zip)
    # Reuse executed B-stage output only if every manuscript source still matches.
    prior=ROOT/'results/r15/prior-text/validation'
    vr=json.loads((prior/'validation.json').read_text())
    if vr['article_sha256']!=sha(ROOT/'article/main.tex') or vr['biblio_sha256']!=sha(ROOT/'article/r15-references.tex'):
        raise ValueError('B-stage validation belongs to another manuscript')
    sys.path.insert(0,str(ROOT))
    from scripts.check_r14_paper import make_evidence
    from scripts.check_r14_trace import verify_outputs
    from scripts.check_r15_paper import validate
    e=json.loads((ROOT/'results/r14/article_evidence.json').read_text())
    if make_evidence(frozen)!=e:raise ValueError('fresh runner primary evidence mismatch')
    analytic=json.loads((ROOT/'results/r15/service_reference.json').read_text())
    matrix=json.loads((ROOT/'article/r15-sources.json').read_text())
    validate(e,analytic,(ROOT/'article/main.tex').read_text(),(ROOT/'article/r15-references.tex').read_text(),(ROOT/'article/r15-values.tex').read_text(),matrix)
    executed=json.loads((prior/'01_Среда_и_конфигурация.ipynb').read_text())
    original=json.loads((ROOT/'colab/01_Среда_и_конфигурация.ipynb').read_text())
    if [(c['id'],''.join(c['source'])) for c in executed['cells']] != [(c['id'],''.join(c['source'])) for c in original['cells']]:
        raise ValueError('prior notebook execution is stale')
    verify_outputs(executed,e)
    shutil.copytree(prior,delivery/'validation',dirs_exist_ok=True)
    receipt['prior_B_execution_reused']=True
    receipt['fresh_primary_verification']=True
    manuscript=work/'manuscript';manuscript.mkdir(exist_ok=True)
    for name in ('main.tex','r15-values.tex','r15-references.tex','r15-sources.json','psta.cls'):
        shutil.copy2(ROOT/'article'/name,manuscript/name)
    if (ROOT/'article/psta').exists():
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
    cls=(manuscript/'psta.cls').read_text(errors='replace')
    style['provides_class']=re.search(r'\\ProvidesClass[^\n]*',cls).group(0)
    put(delivery/'style-provenance.json',style)
    pdf=compile_tex(manuscript,'main',out/'tex-logs')
    shutil.copy2(pdf,delivery/'article.pdf')
    receipt['pdf_sha256']=sha(pdf);receipt['class']=style
    # Inventory only actual manuscript sources/styles, never fonts or hidden build state.
    package=work/'submission';package.mkdir(exist_ok=True)
    for p in manuscript.rglob('*'):
        if p.is_file() and p.suffix.lower() in ('.tex','.cls','.sty','.def','.cfg','.clo'):
            dest=package/p.relative_to(manuscript);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    for name in ('README.md','build.sh','NOTICE.md','cover_letter.md','author_checklist.md'):
        shutil.copy2(ROOT/'submission'/name,package/name)
        shutil.copy2(ROOT/'submission'/name,delivery/name)
    shutil.copy2(pdf,package/'article.pdf')
    shutil.copy2(ROOT/'article/r15-sources.json',package/'source-claim-matrix.json')
    shutil.copy2(delivery/'style-provenance.json',package/'style-provenance.json')
    shutil.copy2(ROOT/'results/r14/article_evidence.json',package/'empirical-evidence.json')
    shutil.copy2(ROOT/'results/r15/service_reference.json',package/'analytic-evidence.json')
    bibliography_report(ROOT/'article',delivery)
    shutil.copy2(delivery/'bibliography-report.json',package/'bibliography-report.json')
    package_zip(package,delivery/'submission.zip')
    # Isolated rebuild: only files unpacked from the delivered ZIP are available.
    with tempfile.TemporaryDirectory(prefix='fefc-r15-isolated-') as tmp:
        fresh=unpack(delivery/'submission.zip',Path(tmp)/'source')
        fresh_pdf=compile_tex(fresh,'main',out/'isolated-logs')
        import fitz
        with fitz.open(pdf) as aa,fitz.open(fresh_pdf) as bb:
            if len(aa)!=len(bb) or [p.get_text() for p in aa]!=[p.get_text() for p in bb]:
                raise ValueError('isolated ZIP build text differs')
        receipt['isolated_pdf_sha256']=sha(fresh_pdf)
        receipt['isolated_zip_rebuild']='PASS'
    # Full-page rendering and machine inventory; human visual acceptance is separate.
    import fitz
    pages=delivery/'pages';pages.mkdir(exist_ok=True)
    ledger=[]
    with fitz.open(pdf) as doc:
        for i,p in enumerate(doc):
            p.get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(pages/f'page-{i+1:02}.png')
            ledger.append(dict(page=i+1,text_characters=len(p.get_text()),raster_image_count=len(p.get_images(full=True)),
                               vector_paths=len(p.get_drawings()),visual_status='PENDING',pdf_sha256=sha(pdf)))
        receipt['pages']=len(doc)
        # A 7x crop is a genuine vector-render check, not raster upscaling.
        if len(doc)>2:
            p=doc[2];clip=fitz.Rect(0,0,min(240,p.rect.width),min(220,p.rect.height))
            p.get_pixmap(matrix=fitz.Matrix(7,7),clip=clip,alpha=False).save(pages/'vector-crop-7x.png')
    put(delivery/'page-review.json',ledger)
    # Text diff anchored to exact baseline source; preserve the actual baseline PDF too.
    baseline_zip=work/'baseline-artifact.zip'
    download(f'https://api.github.com/repos/{REPO}/actions/artifacts/{BASE_ID}/zip',baseline_zip,BASE_ZIP_SHA,github=True)
    baseline_root=unpack(baseline_zip,work/'baseline-artifact')
    old_pdfs=[p for p in baseline_root.rglob('*.pdf') if sha(p)==BASE_PDF_SHA]
    if not old_pdfs:raise ValueError('baseline PDF hash not found')
    shutil.copy2(old_pdfs[0],delivery/'before_R14.pdf')
    diffdir=work/'diff';shutil.copytree(manuscript,diffdir,dirs_exist_ok=True)
    for name in ('main.tex','r14-values.tex','r14-references.tex'):
        data=subprocess.check_output(['git','show',BASE+':article/'+name],cwd=ROOT)
        (diffdir/('before.tex' if name=='main.tex' else name)).write_bytes(data)
    diff_status={'baseline_sha':BASE,'baseline_pdf_sha256':BASE_PDF_SHA,'after_pdf_sha256':sha(pdf)}
    try:
        generated=command(['latexdiff','--encoding=utf8','--flatten','--math-markup=0','--disable-citation-markup','before.tex','main.tex'],diffdir,out/'latexdiff-output.log')
        (diffdir/'difference.tex').write_bytes(generated)
        changed=compile_tex(diffdir,'difference',out/'diff-logs')
        shutil.copy2(changed,delivery/'difference.pdf');diff_status['method']='latexdiff'
        diff_status['requested_utility_success']=True
    except Exception as exc:
        diff_status.update(method='PDF-word-difference fallback',requested_utility_success=False,
                           failure=type(exc).__name__+': '+str(exc)[:300])
        marked_pdf_comparison(old_pdfs[0],pdf,delivery/'difference.pdf')
    put(delivery/'difference-provenance.json',diff_status)
    # Publish exact frozen data in sub-100MB chunks, with explicit reassembly and SHA.
    data_manifest={'original_name':'frozen131.zip','sha256':FROZEN_SHA,'size':frozen_zip.stat().st_size,
                   'scientific_run_id':45174257711,'parts':[]}
    with frozen_zip.open('rb') as f:
        index=0
        while chunk:=f.read(80*1024*1024):
            name=f'frozen131.zip.part{index:02}';p=delivery/name;p.write_bytes(chunk)
            data_manifest['parts'].append({'name':name,'size':len(chunk),'sha256':sha(p)});index+=1
    put(delivery/'data-parts.json',data_manifest)
    # Reproducibility source subset: only allowed text/code, no original reports/photos/fonts.
    repro=work/'reproducibility';repro.mkdir(exist_ok=True)
    for folder in ('efc','scripts','colab','configs'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.mjs','.ipynb','.json'):
                d=repro/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
    for f in (ROOT/'requirements.txt',ROOT/'results/r14/article_evidence.json',ROOT/'results/r15/service_reference.json'):
        d=repro/f.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d)
    shutil.copy2(ROOT/'submission/reassemble.py',repro/'reassemble.py')
    shutil.copy2(delivery/'data-parts.json',repro/'data-parts.json')
    shutil.copy2(ROOT/'submission/README.md',repro/'README.md')
    package_zip(repro,delivery/'reproducibility.zip')
    shutil.copy2(ROOT/'submission/reassemble.py',delivery/'reassemble.py')
    receipt['submission_zip_sha256']=sha(delivery/'submission.zip')
    receipt['difference_pdf_sha256']=sha(delivery/'difference.pdf')
    receipt['diff']=diff_status
    receipt['data_complete_for_frozen_131']=True
    receipt['public_access']='PENDING_PUBLICATION_AND_ANONYMOUS_DOWNLOAD'
    put(delivery/'build-receipt.json',receipt);put(out/'receipt.json',receipt)
    hashes={p.relative_to(delivery).as_posix():sha(p) for p in sorted(delivery.rglob('*')) if p.is_file()}
    put(delivery/'SHA256.json',hashes)
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
