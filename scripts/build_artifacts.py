"""Build available stages from a checkout; save real logs, never fabricate success."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess,sys,time,json,hashlib,os
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT);OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
def run(cmd,log,cwd=ROOT):
    t=time.perf_counter();p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True)
    (OUT/log).write_text('$ '+' '.join(map(str,cmd))+'\n'+p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(f'{log}: exit {p.returncode}')
    return time.perf_counter()-t
run([sys.executable,'-m','unittest','discover','-s','tests','-v'],'model-tests.txt')
if (ROOT/'v2').exists():
    run(['sha256sum','-c','MANIFEST.sha256'],'v2-manifest-before.txt',ROOT/'v2')
    run([sys.executable,'-m','unittest','discover','-s','tests','-v'],'v2-tests.txt',ROOT/'v2/code')
run([sys.executable,'scripts/make_notebooks.py'],'notebook-generation.txt')
if (ROOT/'scripts/make_forecast_notebook.py').exists():run([sys.executable,'scripts/make_forecast_notebook.py'],'forecast-notebook-generation.txt')
if (ROOT/'scripts/make_placement_notebook.py').exists():run([sys.executable,'scripts/make_placement_notebook.py'],'placement-notebook-generation.txt')
timings={}
for nb in sorted((ROOT/'colab/clean').glob('*.ipynb')):
    timings[nb.name]=run([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',str(nb),'--output-dir',str(ROOT/'colab'),'--ExecutePreprocessor.timeout=240'],nb.stem+'-execution.txt')
(OUT/'notebook-times.json').write_text(json.dumps(timings,ensure_ascii=False,indent=2))
if (ROOT/'scripts/write_article.py').exists():
    run([sys.executable,'scripts/write_article.py'],'article-generation.txt')
    run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],'latex-pass1.txt',ROOT/'article')
    run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],'latex-pass2.txt',ROOT/'article')
if (ROOT/'v2').exists():run(['sha256sum','-c','MANIFEST.sha256'],'v2-manifest-after.txt',ROOT/'v2')
source=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
summary={'utc':datetime.now(timezone.utc).isoformat(),'source_commit':source,'python':sys.version,'notebooks':timings,'all_available_stages_passed':True,'article_built':(ROOT/'article/main.pdf').exists(),'cloud_colab_run':False}
(OUT/'build-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
msg='\n\n## Выполненная проверка из checkout '+source+'\nUTC: '+summary['utc']+'\n'
msg+='Тесты новой модели и имеющиеся тетради запущены успешно; выводы results/*.txt.\n'
msg+='Тетради: '+', '.join(timings)+'. Время — notebook-times.json, не гарантия скорости Colab.\n'
msg+='Эталон v2 проверен до и после, не изменён. PDF собран: '+str(summary['article_built'])+'.\n'
msg+='Это запуск в GitHub runner/checkout, не личная проверка интерфейса Google Colab.\n'
(ROOT/'docs/STATUS.md').open('a').write(msg)
print(json.dumps(summary,ensure_ascii=False,indent=2))
