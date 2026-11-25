"""Check unchanged science, execute notebook00 and rebuild article; no series rerun."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time,re,platform
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ['PYTHONDONTWRITEBYTECODE']='1'
R=ROOT/'results';OUT=R/'revision';OUT.mkdir(exist_ok=True)

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],text=True,cwd=ROOT).strip()
def protected():
    return {str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'v2').rglob('*') if p.is_file() and '__pycache__' not in str(p)}|{'docs/Журнал_проверок_Perplexity.md':digest(ROOT/'docs/Журнал_проверок_Perplexity.md')}
def manifest():
    files=[p for folder in ('efc','tests','scripts','colab','article','results','docs','v2','.github/workflows') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.suffix not in ('.pyc','.aux','.out','.brf','.log','.toc')]
    files += [p for p in (ROOT/'README.md',ROOT/'requirements.txt') if p.exists()]
    (ROOT/'MANIFEST.sha256').write_text(''.join(digest(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in sorted(set(files))))

def main():
    assert git('branch','--show-current')=='night/fefc-v3'
    source=git('rev-parse','HEAD');before=protected()
    old=json.loads((R/'build-summary.json').read_text())
    assert old['all_available_stages_passed'] and old['workflow_run_id']=='45012597897'
    for name,value in json.loads((R/'source-hashes.json').read_text()).items():
        if name.startswith('efc/') and digest(ROOT/name)!=value:
            raise RuntimeError('Science source changed; cached-only validation forbidden: '+name)
    primary={str(p.relative_to(ROOT)):digest(p) for p in R.glob('*.csv')}
    for name in ('forecast_metadata.json','demo_network.json','stationary_metadata.json','source-hashes.json'):
        primary['results/'+name]=digest(R/name)
    for name,value in json.loads((R/'article-provenance.json').read_text())['source_files'].items():
        assert digest(R/name)==value,name
    report={'status':'RUNNING','utc':datetime.now(timezone.utc).isoformat(),'source_commit':source,'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'science_source_commit':old['source_commit'],'science_result_commit':'4c8b105408b5581054b84002cd649bae7ab3a27a','science_workflow_run_id':old['workflow_run_id'],'science_rerun':False,'execution':'Actions + nbconvert' if os.environ.get('GITHUB_ACTIONS')=='true' else 'local container + nbconvert','cloud_colab_run':False,'python':sys.version,'platform':platform.platform(),'steps':[]}
    def run(cmd,name,cwd=ROOT):
        start=time.perf_counter();p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True)
        (OUT/name).write_text('$ '+' '.join(cmd)+'\n'+p.stdout+p.stderr)
        report['steps'].append({'command':cmd,'log':'results/revision/'+name,'returncode':p.returncode,'elapsed_wall_s':time.perf_counter()-start})
        print(name,p.returncode,flush=True)
        if p.returncode:
            print((p.stdout+p.stderr)[-5000:],flush=True);raise RuntimeError(name)
    try:
        import numpy as np,pandas as pd
        from scipy.stats import t
        from efc.stationary import METRICS
        raw=pd.read_csv(R/'stationary_replicates.csv');summary=pd.read_csv(R/'stationary_summary.csv')
        intervals=0
        for _,s in summary.iterrows():
            part=raw[(raw.series==s.series)&(raw.scenario==s.scenario)]
            assert len(part)==part.seed.nunique()>=10
            for key in METRICS:
                values=part[key].to_numpy();mean=values.mean();half=t.ppf(.975,len(values)-1)*values.std(ddof=1)/np.sqrt(len(values))
                assert np.allclose([mean,mean-half,mean+half],[s[key],s[key+'_ci_low'],s[key+'_ci_high']],rtol=1e-10,atol=1e-8),(s.scenario,key)
                intervals+=1
        assert np.allclose(sorted(summary[summary.series=='intensity'].rho_target),[.1,.3,.5,.7,.85,.95])
        assert (raw.completed+raw.dropped==raw.arrivals).all()
        assert (raw.mean_fog_wait_ms>0).all()
        assert summary.groupby('series').mean_fog_wait_ms.nunique().min()>1
        assert (raw.warmup_expected_per_fog>=2000).all() and (raw.observation_expected_per_fog>=4000).all()
        report['stored_science_audit']={'replications':len(raw),'scenarios':len(summary),'seed_min':int(summary.n_seeds.min()),'intervals_recomputed':intervals,'balance_ok':True,'distinct_scenarios':True,'simulation_called':False}
        run([sys.executable,'-m','unittest','discover','-s','tests','-v'],'unit-tests.txt')
        run([sys.executable,'scripts/verify_doi.py'],'doi.txt')
        assert json.loads((R/'doi-check.json').read_text())['all_doi_ok']
        run([sys.executable,'scripts/render_references.py'],'references.txt')
        run([sys.executable,'scripts/start_dashboard.py'],'start-generation.txt')
        run([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute','colab/clean/00_Старт.ipynb','--output-dir','colab','--ExecutePreprocessor.timeout=600'],'start-nbconvert.txt')
        book=json.loads((ROOT/'colab/00_Старт.ipynb').read_text());codes=[c for c in book['cells'] if c['cell_type']=='code']
        assert codes and all(c['execution_count'] is not None for c in codes)
        assert not any(o.get('output_type')=='error' for c in codes for o in c.get('outputs',[]))
        report['start_executed_code_cells']=len(codes)
        report['unchanged_notebooks']={}
        for p in sorted((ROOT/'colab').glob('0[123]_*.ipynb')):
            b=json.loads(p.read_text());c=[c for c in b['cells'] if c['cell_type']=='code']
            assert c and all(x['execution_count'] is not None for x in c)
            assert not any(o.get('output_type')=='error' for x in c for o in x.get('outputs',[]))
            report['unchanged_notebooks'][p.name]={'sha256':digest(p),'executed_in_run':old['workflow_run_id'],'rerun_this_step':False}
        assert len(report['unchanged_notebooks'])==3
        from efc.claims import verify
        report['claims']=verify(ROOT)
        run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],'latex-1.txt',ROOT/'article')
        run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],'latex-2.txt',ROOT/'article')
        latex=(OUT/'latex-2.txt').read_text()
        assert 'There were undefined references' not in latex and 'Overfull \\hbox' not in latex
        tex=(ROOT/'article/main.tex').read_text();assert not re.search(r'TODO|FIXME|@@',tex)
        assert tex.count('\\section{')==7
        cited=json.loads((R/'citation-check.json').read_text())
        assert len(cited['doi_keys'])==14 and len(cited['cited_keys'])==15 and cited['all_cited_doi_ok']
        run(['pdfinfo',str(ROOT/'article/main.pdf')],'pdf-info.txt')
        run(['pdftotext','-layout',str(ROOT/'article/main.pdf'),str(OUT/'article.txt')],'pdf-text.txt')
        run(['pdftoppm','-scale-to','800','-png',str(ROOT/'article/main.pdf'),str(OUT/'page')],'pdf-render.txt')
        run(['sha256sum','-c','MANIFEST.sha256'],'v2-manifest.txt',ROOT/'v2')
        assert protected()==before,'protected files changed'
        assert all(digest(ROOT/p)==v for p,v in primary.items()),'unchanged scientific results were overwritten'
        report.update(status='PASS',protected_unchanged=True,primary_files_unchanged=True,primary_sha256=primary,article_pdf_sha256=digest(ROOT/'article/main.pdf'),article_tex_sha256=digest(ROOT/'article/main.tex'),doi_count=14,total_references=15)
        previous=json.loads((R/'article-provenance.json').read_text())
        (OUT/'previous-article-provenance.json').write_text(json.dumps(previous,ensure_ascii=False,indent=2))
        previous.update(main_tex_sha256=report['article_tex_sha256'],main_pdf_sha256=report['article_pdf_sha256'],related_tex_sha256=digest(ROOT/'article/related.tex'),verified_bibliography_sha256=digest(ROOT/'article/references_verified.tex'),source_commit=source,scientific_source_commit=old['source_commit'],editorial_only=True,start_dashboard_claims='results/start-dashboard/claims-to-cells.csv')
        (R/'article-provenance.json').write_text(json.dumps(previous,ensure_ascii=False,indent=2))
        with (ROOT/'docs/STATUS.md').open('a') as f:
            f.write('\n\n## Текущий адресный запуск — '+report['utc']+'\nActions '+str(report['workflow_run_id'])+', исходник '+source+'. Тесты и 00 через nbconvert выполнены, PDF собран, 14 DOI/15 записей, интервалы пересчитаны по сохранённым 180 реализациям. Серии, чувствительность и обучение не повторялись. 01–03 ранее выполнены в Actions 45012597897. Защищённые файлы и научные CSV не изменены. Веб-интерфейс Colab не запускался. Полный журнал: results/revision-check.json.\n')
        (R/'final-check.txt').write_text('INCREMENTAL CHECK: PASS\nsource_commit='+source+'\nworkflow_run_id='+str(report['workflow_run_id'])+'\nscience_source_commit='+old['source_commit']+'\nscience_workflow_run_id='+old['workflow_run_id']+'\nscience_rerun=False\n00: nbconvert executed\n01-03: previous executed outputs retained\nPDF: rebuilt, no undefined references or overfull hbox\nColab UI: NOT tested\nmain/v2/reviewer journal: not modified\nSee results/revision-check.json for executed stages.\n')
    except Exception as exc:
        report.update(status='FAILED',error=repr(exc));raise
    finally:
        (R/'revision-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        manifest()
    print(json.dumps({k:report[k] for k in ('status','source_commit','workflow_run_id','science_rerun','start_executed_code_cells','doi_count')},ensure_ascii=False))

if __name__=='__main__':main()
