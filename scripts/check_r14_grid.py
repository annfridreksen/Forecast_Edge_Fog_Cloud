"""Small checkpoint/registry acceptance; never launches the scientific map."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_r14_core import run_logged

def main():
    out=ROOT/'results/r14/current/grid';out.mkdir(parents=True,exist_ok=True)
    try:
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        sha='LOCAL-UNCOMMITTED'
    files=['efc/grid.py','efc/pilot.py','tests/test_grid.py','scripts/run_r14_grid.py',
           'scripts/check_r14_grid.py','colab/validation/02_R14_resume.ipynb']
    report=dict(status='RUNNING',scope='small resume oracles, NOT scientific grid',
                source_commit=sha,utc=datetime.now(timezone.utc).isoformat(),
                execution='Actions + nbconvert' if os.environ.get('GITHUB_ACTIONS')=='true' else 'local Python + nbconvert',
                colab_ui_tested=False,full_grid_run=False,steps=[],
                sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files})
    try:
        commands=[([sys.executable,'-m','unittest','discover','-s','tests','-p','test_grid.py','-v'],'grid-tests.txt'),
                  ([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',
                    'colab/validation/02_R14_resume.ipynb','--output-dir',str(out),
                    '--ExecutePreprocessor.timeout=120'],'nbconvert.txt')]
        for command,name in commands:
            step=run_logged(command,out/name);report['steps'].append(step)
            if step['returncode']:raise RuntimeError('failed: '+name)
        b=json.loads((out/'02_R14_resume.ipynb').read_text())
        cells=[c for c in b['cells'] if c['cell_type']=='code']
        assert len(cells)==3 and all(c['execution_count'] is not None for c in cells)
        assert not any(o['output_type']=='error' for c in cells for o in c['outputs'])
        for name in ('resume-oracle.json','kernel-cache.json'):
            json.loads((out/name).read_text())
        report.update(status='PASS',executed_code_cells=len(cells))
    except Exception as exc:
        report.update(status='FAILED',error=repr(exc));raise
    finally:
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PASS: persistent resume and global freeze oracles only.')
if __name__=='__main__':main()
