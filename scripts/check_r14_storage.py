"""Addressed storage/journal/migration tests and notebook, not a large series."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_r14_core import run_logged

def main():
    out=ROOT/'results/r14/current/storage';out.mkdir(parents=True,exist_ok=True)
    report=dict(status='RUNNING',execution='Actions/nbconvert' if os.getenv('GITHUB_ACTIONS')=='true' else 'local Python/nbconvert',
                colab_ui_tested=False,scientific_grid_run=False,steps=[])
    patterns=('test_journal_idempotence.py','test_archive_verification.py','test_storage_migration.py')
    try:
        for pattern in patterns:
            r=run_logged([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern,'-v'],out/(pattern+'.log'))
            report['steps'].append(r)
            if r['returncode']:raise RuntimeError('failed '+pattern)
        r=run_logged([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',
                      'colab/validation/03_R14_storage.ipynb','--output-dir',str(out),'--ExecutePreprocessor.timeout=120'],out/'nbconvert.log')
        report['steps'].append(r)
        if r['returncode']:raise RuntimeError('failed notebook')
        b=json.loads((out/'03_R14_storage.ipynb').read_text());cells=[c for c in b['cells'] if c['cell_type']=='code']
        if len(cells)!=3 or any(c['execution_count'] is None for c in cells):raise RuntimeError('unexecuted cells')
        if any(o.get('output_type')=='error' for c in cells for o in c['outputs']):raise RuntimeError('notebook error')
        report.update(status='PASS',executed_code_cells=len(cells))
    finally:
        report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for folder in ('efc','scripts','tests') for p in sorted((ROOT/folder).glob('*.py'))}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: storage/journal/explicit migration only, not a complete map.')
if __name__=='__main__':main()
