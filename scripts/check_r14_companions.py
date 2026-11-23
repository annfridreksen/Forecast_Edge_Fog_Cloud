"""Execute 01–03 only: saved-map reading and conceptual ports/placement.

No scientific series, forecasts, training or protected-v2 execution. Notebook
receipts distinguish verified source reading from execution and scientific claims.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_r14_core import run_logged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'results/r14/current/companions')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT):
        parser.error('Output must be under the repository (shared log contract)')
    out.mkdir(parents=True, exist_ok=True)
    if args.checkpoint:
        if out.is_relative_to(args.checkpoint.resolve()):
            raise ValueError('Check output must not modify the checkpoint')
        os.environ['FEFC_CHECKPOINT'] = str(args.checkpoint.resolve())
    if (ROOT/'.git').exists():
        os.environ['FEFC_SOURCE_SHA'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report = dict(status='RUNNING', execution='Actions/nbconvert' if os.getenv('GITHUB_ACTIONS') == 'true' else 'local Python/nbconvert',
                  python=sys.version, colab_browser_checked=False, simulation_executed=False,
                  forecast_executed=False, training_executed=False, steps=[], notebooks=[])
    paths = sorted((ROOT/'colab').glob('0[123]_*.ipynb'))
    if len(paths) != 3: raise ValueError('Exactly three companion notebooks required')
    try:
        step = run_logged([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_companion*.py', '-v'], out/'tests.log')
        report['steps'].append(step)
        if step['returncode']: raise RuntimeError('Companion tests failed')
        for path in paths:
            name = path.name[:2]
            step = run_logged([sys.executable, '-m', 'jupyter', 'nbconvert', '--to', 'notebook', '--execute', str(path),
                               '--output-dir', str(out), '--ExecutePreprocessor.timeout=120'], out/(name+'.log'))
            report['steps'].append(step)
            if step['returncode']: raise RuntimeError('Notebook failed: '+name)
            book = json.loads((out/path.name).read_text())
            cells = [c for c in book['cells'] if c['cell_type'] == 'code']
            if any(c['execution_count'] is None for c in cells): raise ValueError('Unexecuted cell')
            if any(o.get('output_type') == 'error' for c in cells for o in c['outputs']): raise ValueError('Notebook error output')
            text = ''.join(''.join(o.get('text', '')) for o in cells[-1]['outputs'])
            receipt = json.loads(text)
            for flag in ('simulation_executed', 'forecast_executed', 'training_executed', 'controller_executed', 'full_plan_verified', 'reference_executed', 'colab_browser_checked'):
                if receipt.get(flag, False) is not False: raise ValueError('Wrong scope: '+flag)
            images = 0
            for cell in cells:
                for output in cell['outputs']:
                    encoded = output.get('data', {}).get('image/png')
                    if encoded:
                        images += 1; (out/f'{name}-figure-{images}.png').write_bytes(base64.b64decode(encoded))
            if images < (2 if name == '01' else 1): raise ValueError('Missing diagram/explicit empty curve')
            report['notebooks'].append(dict(name=path.name, executed_code_cells=len(cells), images=images, receipt=receipt))
        report['status'] = 'PASS'
    except Exception as exc:
        report.update(status='FAILED', error=repr(exc)); raise
    finally:
        sources = paths + [ROOT/'efc/companion.py', ROOT/'efc/curve_selection.py', ROOT/'efc/curve_annotations.py', Path(__file__)] + sorted((ROOT/'tests').glob('test_companion*.py'))
        report['source_sha256'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('PASS: 01–03 read-only/conceptual execution; no full map or forecasting claim.')

if __name__ == '__main__': main()
