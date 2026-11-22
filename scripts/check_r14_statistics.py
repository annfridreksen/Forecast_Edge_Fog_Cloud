"""Addressed statistics/controller acceptance. No grid, training, or PDF."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_r14_core import run_logged


def main():
    out = ROOT/'results/r14/current/statistics'
    out.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    files = ['efc/statistics.py','efc/pilot.py','tests/test_statistics.py','tests/test_pilot.py',
             'scripts/check_r14_statistics.py','colab/validation/01_R14_statistics.ipynb']
    report = dict(status='RUNNING', source_commit=sha, utc=datetime.now(timezone.utc).isoformat(),
                  scope='statistics and pilot small regression; NOT scientific map',
                  execution='Actions + nbconvert' if os.environ.get('GITHUB_ACTIONS')=='true' else 'local + nbconvert',
                  python=sys.version, platform=platform.platform(), colab_ui_tested=False,
                  full_grid_run=False, training_run=False, pdf_built=False, steps=[],
                  sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files})
    try:
        commands = [([sys.executable,'-m','unittest','discover','-s','tests','-p',name,'-v'],name+'.txt')
                    for name in ('test_statistics.py','test_pilot.py')]
        commands.append(([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',
                          'colab/validation/01_R14_statistics.ipynb','--output-dir',str(out),
                          '--ExecutePreprocessor.timeout=120'],'nbconvert.txt'))
        for cmd, log in commands:
            step=run_logged(cmd,out/log);report['steps'].append(step)
            if step['returncode']:raise RuntimeError('failed: '+log)
        book=json.loads((out/'01_R14_statistics.ipynb').read_text())
        cells=[c for c in book['cells'] if c['cell_type']=='code']
        if not cells or any(c['execution_count'] is None for c in cells):raise RuntimeError('unexecuted cell')
        if any(o['output_type']=='error' for c in cells for o in c['outputs']):raise RuntimeError('notebook error')
        for name in ('statistics-oracles.json','controller-oracles.json','kernel-adapter.json'):
            json.loads((out/name).read_text())
        report.update(status='PASS',executed_code_cells=len(cells))
    except Exception as exc:
        report.update(status='FAILED',error=repr(exc));raise
    finally:
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    print('PASS: statistics/controller regression only; full scientific map is not evaluated.')


if __name__=='__main__':main()
