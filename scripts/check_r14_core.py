"""Scoped R1.4 core acceptance, NOT the scientific-grid/article acceptance.

No learning, cached research claims, full series, TeX build, or automatic push.
Raw subprocess bytes survive malformed UTF-8 and non-zero exits.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def run_logged(command, log, cwd=ROOT):
    """Save bytes before decoding; never turn a failed command into a pass."""
    start = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.with_suffix(log.suffix + '.raw').write_bytes(result.stdout)
    log.write_text('$ ' + ' '.join(command) + '\n' +
                   result.stdout.decode('utf-8', errors='backslashreplace'), encoding='utf-8')
    return {'command': command, 'log': str(log.relative_to(ROOT)),
            'returncode': result.returncode,
            'elapsed_wall_seconds': time.perf_counter() - start}


def main():
    out = ROOT / 'results/r14/current'
    out.mkdir(parents=True, exist_ok=True)
    env_sha = os.environ.get('FEFC_SOURCE_COMMIT')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                          stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = env_sha or 'LOCAL-UNCOMMITTED'
    report = dict(status='RUNNING', scope='R1.4 core and paired-window regressions only',
                  source_commit=commit, utc=datetime.now(timezone.utc).isoformat(),
                  execution='Actions + nbconvert' if os.environ.get('GITHUB_ACTIONS') == 'true'
                            else 'local Python container + nbconvert',
                  colab_ui_tested=False, full_series_run=False, training_run=False,
                  pdf_built=False, python=sys.version, platform=platform.platform(), steps=[])
    report['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for folder in ('efc', 'tests', 'scripts')
                              for p in sorted((ROOT/folder).rglob('*.py'))}
    report['source_sha256']['colab/validation/00_R14_core.ipynb'] = hashlib.sha256(
        (ROOT/'colab/validation/00_R14_core.ipynb').read_bytes()).hexdigest()
    try:
        commands = [([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                      '-p', 'test_r14_pipeline.py', '-v'], 'pipeline-tests.txt'),
                    ([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                      '-p', 'test_model*.py', '-v'], 'model-tests.txt'),
                    ([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                      '-p', 'test_stationary.py', '-v'], 'window-tests.txt'),
                    ([sys.executable, '-m', 'jupyter', 'nbconvert', '--to', 'notebook',
                      '--execute', 'colab/validation/00_R14_core.ipynb',
                      '--output-dir', str(out), '--ExecutePreprocessor.timeout=120'],
                     'nbconvert.txt')]
        for command, name in commands:
            step = run_logged(command, out/name)
            report['steps'].append(step)
            print(name, 'exit=' + str(step['returncode']), flush=True)
            if step['returncode']:
                raise RuntimeError('Failed: ' + name)
        book = json.loads((out/'00_R14_core.ipynb').read_text())
        cells = [c for c in book['cells'] if c['cell_type'] == 'code']
        if not cells or any(c['execution_count'] is None for c in cells):
            raise RuntimeError('Unexecuted code cells')
        if any(o.get('output_type') == 'error' for c in cells for o in c.get('outputs', [])):
            raise RuntimeError('Notebook error output')
        image_count = sum('image/png' in o.get('data', {}) for c in cells for o in c.get('outputs', []))
        if image_count < 1:
            raise RuntimeError('Manual timeline was not rendered in the notebook')
        paired = json.loads((out/'paired-configurations.json').read_text())
        same_path = json.loads((out/'window-path.json').read_text())
        if (len(paired) != 45 or len({x['input_sha256'] for x in paired}) != 1
            or not all(x['all_source_fields_equal'] for x in paired)
            or not same_path['all_kernel_records_equal']):
            raise RuntimeError('Paired inputs/shared-kernel regression failed')
        report.update(status='PASS', executed_code_cells=len(cells), rendered_png_outputs=image_count,
                      paired_regression_cases=len(paired), shared_kernel_records_equal=True)
    except Exception as exc:
        report.update(status='FAILED', error=repr(exc))
        raise
    finally:
        (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('PASS: scoped core only; configuration map/article not accepted.')


if __name__ == '__main__':
    main()
