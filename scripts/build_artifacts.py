"""Rebuild from an actual checkout; records real outputs and protected hashes."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess,sys,time,json,hashlib,os,shutil,platform,importlib.metadata,importlib.util,re
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
source=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
branch=subprocess.run(['git','branch','--show-current'],capture_output=True,text=True).stdout.strip()
if os.environ.get('GITHUB_ACTIONS')=='true' and branch!='night/fefc-v3':raise RuntimeError('wrong branch')
for rel in ['results','colab','article/figures']:
    p=ROOT/rel
    if p.exists():shutil.rmtree(p)
(ROOT/'article/main.pdf').unlink(missing_ok=True)
OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
steps=[]
def run(cmd,log,cwd=ROOT):
    t=time.perf_counter();p=subprocess.run(cmd,cwd=cwd,capture_output=True)
    text='$ '+' '.join(map(str,cmd))+'\n'+p.stdout.decode('utf-8',errors='backslashreplace')+p.stderr.decode('utf-8',errors='backslashreplace')
    (OUT/log).write_text(text)
    steps.append({'command':list(map(str,cmd)),'log':log,'returncode':p.returncode,'elapsed_wall_seconds':time.perf_counter()-t})
    if p.returncode:raise RuntimeError(f'{log}: exit {p.returncode}')
    return steps[-1]['elapsed_wall_seconds']

def hashes(folder):
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in str(p)}
protected=hashes(ROOT/'v2');journal=ROOT/'docs/Журнал_проверок_Perplexity.md'
journal_hash=hashlib.sha256(journal.read_bytes()).hexdigest() if journal.exists() else None
try:
    run([sys.executable,'-m','unittest','discover','-s','tests','-v'],'model-tests.txt')
    run(['sha256sum','-c','MANIFEST.sha256'],'v2-manifest-before.txt',ROOT/'v2')
    run([sys.executable,'-m','unittest','discover','-s','tests','-v'],'v2-tests.txt',ROOT/'v2/code')
    for name in ['make_notebooks.py','make_forecast_notebook.py','make_placement_notebook.py']:
        run([sys.executable,'scripts/'+name],name+'.txt')
    run([sys.executable,'scripts/complete_notebooks.py'],'notebooks-review.txt')
    timings={}
    for nb in sorted((ROOT/'colab/clean').glob('*.ipynb')):
        timings[nb.name]=run([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',str(nb),'--output-dir',str(ROOT/'colab'),'--ExecutePreprocessor.timeout=240'],nb.stem+'-execution.txt')
        executed=json.loads((ROOT/'colab'/nb.name).read_text())
        assert not any(o.get('output_type')=='error' for c in executed['cells'] for o in c.get('outputs',[]))
        assert any('OK' in str(o.get('text','')) for c in executed['cells'] for o in c.get('outputs',[])),nb.name
    assert len(timings)==4
    (OUT/'notebook-times.json').write_text(json.dumps(timings,ensure_ascii=False,indent=2))
    run([sys.executable,'scripts/check_figures.py'],'figure-check.txt')
    run([sys.executable,'scripts/verify_doi.py'],'doi-check.txt')
    run([sys.executable,'scripts/extend_article.py'],'article-extension.txt')
    shutil.copy2(OUT/'claims.json',OUT/'notebook-claims.json')
    run([sys.executable,'scripts/write_article.py'],'article-generation.txt')
    shutil.copy2(OUT/'claims.json',OUT/'article-claims.json')
    shutil.copy2(OUT/'notebook-claims.json',OUT/'claims.json')
    if (ROOT/'scripts/review_article.py').exists():run([sys.executable,'scripts/review_article.py'],'article-review.txt')
    from efc.claims import verify
    (OUT/'claims-check.json').write_text(json.dumps(verify(ROOT),indent=2))
    run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],'latex-pass1.txt',ROOT/'article')
    run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],'latex-pass2.txt',ROOT/'article')
    latex=(OUT/'latex-pass2.txt').read_text()
    assert 'There were undefined references' not in latex
    assert 'Overfull \\hbox' not in latex
    tex=(ROOT/'article/main.tex').read_text();assert tex.count('\\section{')==7 and '@@' not in tex
    from efc import simulate
    assert simulate()==simulate()
    run(['sha256sum','-c','MANIFEST.sha256'],'v2-manifest-after.txt',ROOT/'v2')
    assert hashes(ROOT/'v2')==protected
    if journal_hash:assert hashlib.sha256(journal.read_bytes()).hexdigest()==journal_hash
    summary={'utc':datetime.now(timezone.utc).isoformat(),'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'source_commit':source,'branch':branch,'python':sys.version,'platform':platform.platform(),'notebooks':timings,'all_available_stages_passed':True,'article_built':True,'cloud_colab_run':False,'protected_v2_unchanged':True,'reviewer_journal_unchanged':True,'dependencies':{x:(importlib.metadata.version(x) if importlib.util.find_spec(x.replace('scikit-learn','sklearn')) else 'not installed') for x in ['numpy','pandas','matplotlib','networkx','scikit-learn','nbformat','nbconvert','ipywidgets']},'steps':steps,'clock':'perf_counter elapsed wall time; not CPU time'}
    (OUT/'build-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    run([sys.executable,'-m','pip','freeze'],'requirements-executed.txt')
    (OUT/'source-hashes.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['efc','tests','scripts'] for p in (ROOT/folder).rglob('*.py')},ensure_ascii=False,indent=2))
    run([sys.executable,'scripts/write_report.py'],'report-generation.txt')
    final=['CLEAN CHECKOUT VERIFICATION','source_commit='+source,'branch='+branch,'utc='+summary['utc'],'']
    for step in steps:final.extend(['$ '+' '.join(step['command']),'exit='+str(step['returncode'])+'; elapsed_wall_seconds='+str(step['elapsed_wall_seconds']),'log=results/'+step['log']])
    final += ['','v2 SHA256 before/after: MATCH','reviewer journal: UNCHANGED','notebooks 00-03: executed, no error output, final OK','article PSTA: two pdflatex passes; no undefined references/overfull hbox','Google Colab UI: NOT directly tested','FINAL CHECK: PASS']
    (OUT/'final-check.txt').write_text('\n'.join(final)+'\n')
    with (ROOT/'docs/STATUS.md').open('a') as f:f.write('\n\n## Финальная проверка '+summary['utc']+'\nСделано/запущено: results/final-check.txt — PASS; исходный commit '+source+'. Все четыре тетради выполнены, PDF собран, v2 и журнал проверяющего сохранены. Это проверка чистого GitHub checkout, не личный запуск интерфейса Colab.\n')
    paths=[p for folder in ['efc','tests','scripts','colab','article','results','docs','v2'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.suffix not in ['.aux','.log','.out','.brf','.toc','.pyc']]
    paths += [ROOT/'requirements.txt',ROOT/'.github/workflows/fefc.yml']
    (ROOT/'MANIFEST.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(ROOT))+'\n' for p in sorted(paths)))
    print('FINAL CHECK: PASS; manifests, outputs and actual logs saved.')
except Exception as exc:
    (OUT/'final-check.txt').write_text('FINAL CHECK: FAILED\n'+repr(exc)+'\nCompleted steps:\n'+json.dumps(steps,ensure_ascii=False,indent=2))
    raise
