"""R1.5 manuscript checks. Preserve R1.4 primary evidence and accepted cell trace.

This analysis version changes presentation, not the simulation or bootstrap.
No incorrect source number is overwritten to make validation pass.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_r14_paper import make_evidence, get, SPECS
from scripts.check_r14_trace import verify_outputs

DISPLAY = {
 'dRequests': ('counts.requests', 0), 'dPilot': ('counts.pilot', 0),
 'dMain': ('counts.main', 0), 'dArrivals': ('point.arrivals', 0),
 'dCompleted': ('point.completed', 0), 'dDropped': ('point.dropped', 0),
 'dUnfinished': ('point.unfinished', 0), 'dMean': ('point.mean_ms', 1),
 'dQ': ('point.p95_ms', 1), 'dQlo': ('q_interval.lower', 1),
 'dQhi': ('q_interval.upper', 1), 'dH': ('point.H200', 3),
}
ANALYTIC = {'dServiceQ': ('p95_ms.mixture', 1),
            'dServiceMean': ('mean_ms', 1), 'dServiceMax': ('max_service_ms', 0)}
SECTIONS = ['Введение', 'Обзор родственных работ', 'Модель вычислительной среды',
 'Метод выбора конфигурации', 'Результаты',
 'Развитие среды: переразмещение с учётом прогноза',
 'Обсуждение и ограничения', 'Заключение']


def read(path):
    return Path(path).read_text(encoding='utf-8')


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def expected_values(evidence, analytic):
    out = ['% R1.5 display rounding only; raw frozen evidence is unchanged.']
    for name, (field, places) in DISPLAY.items():
        out.append('\\newcommand{\\' + name + '}{' + f'{get(evidence, field):.{places}f}'.replace('.', ',') + '}')
    for name, (field, places) in ANALYTIC.items():
        out.append('\\newcommand{\\' + name + '}{' + f'{get(analytic, field):.{places}f}'.replace('.', ',') + '}')
    return '\n'.join(out) + '\n'


def validate(evidence, analytic, text, bib, values, matrix):
    if values != expected_values(evidence, analytic):
        raise ValueError('R1.5 display differs from frozen primary/analytic evidence')
    if re.findall(r'\\section\{([^}]+)\}', text) != SECTIONS:
        raise ValueError('eight scientific sections missing or reordered')
    if any(s in text + bib for s in ('\\misc ', 'TODO', '@@')):
        raise ValueError('unsupported command or unfinished drafting marker')
    for macro in {**DISPLAY, **ANALYTIC}:
        if '\\' + macro + '{}' not in text:
            raise ValueError('unused registered value: ' + macro)
    labels = re.findall(r'\\label\{([^}]+)\}', text)
    refs = re.findall(r'\\(?:eqref|ref)\{([^}]+)\}', text)
    if len(labels) != len(set(labels)) or not set(refs) <= set(labels):
        raise ValueError('duplicate or unresolved structural reference')
    cited = {k.strip() for g in re.findall(r'\\cite\{([^}]+)\}', text) for k in g.split(',')}
    listed = re.findall(r'\\R?Bibitem\{([^}]+)\}', bib)
    if len(listed) != len(set(listed)) or cited != set(listed) or not 25 <= len(listed) <= 40:
        raise ValueError('citation/reference correspondence or count')
    entries = matrix['entries']
    if {e['key'] for e in entries} != cited or len(entries) != len(cited):
        raise ValueError('source matrix does not cover references')
    verified = [e for e in entries if e['status'] != 'AUTHOR_PUBLICATION_DETAILS_REQUIRED']
    recent = [e for e in verified if 2023 <= e['year'] <= 2026]
    if len(verified) < 25 or 3 * len(recent) < len(listed):
        raise ValueError('verified-source count/recent quota not met')
    for e in verified:
        if not (e.get('doi') or e.get('url') or e.get('isbn')) or not e.get('claim') or not e.get('location'):
            raise ValueError('source identity/support absent: ' + e['key'])
    if text.count('\\engcap{') != text.count('\\caption{'):
        raise ValueError('a figure/table lacks its English caption')
    if len(re.findall(r'\\begin\{abstract\}', text)) != 2 or '\\section*{Extended summary}' not in text:
        raise ValueError('bilingual abstract or extended summary missing')
    if 'actions/runs/' in text or 'artifacts/' in text:
        raise ValueError('authenticated artifact link in scientific article')
    if evidence['status'] != 'INSUFFICIENT_DATA' or evidence['counts']['requests'] != 131:
        raise ValueError('this manuscript is bound to its declared 131-request snapshot')
    if evidence['scientific_acceptance'] or evidence['point']['dropped'] != 0:
        raise ValueError('frozen loss conclusion was altered')
    return dict(sections=8, references=len(listed), identified_references=len(verified),
                recent_identified_references=len(recent), empirical_display_fields=len(DISPLAY),
                analytic_display_fields=len(ANALYTIC), known_missing_reference='nskf',
                scientific_acceptance=False, submission_ready=False)


def tests(evidence, analytic, text, bib, values, matrix, out):
    class ManuscriptTests(unittest.TestCase):
        def check(self, **kw):
            data = dict(evidence=evidence, analytic=analytic, text=text, bib=bib, values=values, matrix=matrix)
            data.update(kw)
            return validate(**data)
        def test_actual_text(self): self.check()
        def test_false_rounded_value(self):
            with self.assertRaises(ValueError): self.check(values=values.replace('170,9', '169,9'))
        def test_missing_section(self):
            with self.assertRaises(ValueError): self.check(text=text.replace('\\section{Введение}', '\\section{История}'))
        def test_missing_reference(self):
            with self.assertRaises(ValueError): self.check(bib=bib.replace('\\Bibitem{law}', '\\Bibitem{absent}'))
        def test_fake_source_count(self):
            damaged=json.loads(json.dumps(matrix)); damaged['entries']=damaged['entries'][:-1]
            with self.assertRaises(ValueError): self.check(matrix=damaged)
        def test_false_acceptance(self):
            damaged=json.loads(json.dumps(evidence)); damaged['scientific_acceptance']=True
            with self.assertRaises(ValueError): self.check(evidence=damaged)
        def test_mixed_snapshot(self):
            damaged=json.loads(json.dumps(evidence)); damaged['counts']['requests']=162
            with self.assertRaises(ValueError): self.check(evidence=damaged)
        def test_missing_caption_translation(self):
            with self.assertRaises(ValueError): self.check(text=text.replace('\\engcap{Resources', '\\textit{Resources'))
        def test_auth_link_rejected(self):
            with self.assertRaises(ValueError): self.check(text=text+' actions/runs/123')
        def test_raw_rounding_not_modified(self):
            self.assertEqual(evidence['point']['p95_ms'], 170.863296)
            self.assertEqual(evidence['counts']['requests'], 131)
    with (out/'manuscript-tests.log').open('w', encoding='utf-8') as handle:
        result=unittest.TextTestRunner(stream=handle,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ManuscriptTests))
    if not result.wasSuccessful():
        raise ValueError('manuscript tests failed; log retained')
    return result.testsRun


def run(command, cwd, env, path, timeout=600):
    result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    Path(path).write_bytes(result.stdout)
    if result.returncode:
        raise RuntimeError('command failed: '+str(command[0])+'; see '+str(path))


def check(checkpoint, out):
    out.mkdir(parents=True, exist_ok=True)
    evidence=json.loads(read(ROOT/'results/r14/article_evidence.json'))
    analytic=json.loads(read(ROOT/'results/r15/service_reference.json'))
    if make_evidence(checkpoint) != evidence:
        raise ValueError('primary archive does not match frozen article evidence')
    text=read(ROOT/'article/main.tex'); bib=read(ROOT/'article/r15-references.tex')
    values=read(ROOT/'article/r15-values.tex'); matrix=json.loads(read(ROOT/'article/r15-sources.json'))
    receipt=validate(evidence,analytic,text,bib,values,matrix)
    receipt['tests_run']=tests(evidence,analytic,text,bib,values,matrix,out)
    run(['node','scripts/r15_service_reference.mjs'],ROOT,os.environ,out/'analytic-cli.log')
    # Read-only use of the accepted notebook and verifier, not the obsolete R1.4 text validator.
    book=ROOT/'colab/01_Среда_и_конфигурация.ipynb'
    env={**os.environ,'FEFC_CHECKPOINT':str(Path(checkpoint).resolve()),'MPLBACKEND':'Agg'}
    run([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',str(book),
         '--output-dir',str(out.resolve()),'--ExecutePreprocessor.timeout=180'],ROOT,env,out/'nbconvert.log')
    executed=out/book.name; obj=json.loads(read(executed)); original=json.loads(read(book))
    if [(c['id'],''.join(c['source'])) for c in obj['cells']] != [(c['id'],''.join(c['source'])) for c in original['cells']]:
        raise ValueError('executed notebook sources differ')
    codes=[c for c in obj['cells'] if c['cell_type']=='code']
    if any(c.get('execution_count') is None or any(o['output_type']=='error' for o in c.get('outputs',[])) for c in codes):
        raise ValueError('notebook execution incomplete')
    raw_claims=verify_outputs(obj,evidence)
    index=[]
    for macro,(field,places) in DISPLAY.items():
        raw=next(c for c in raw_claims if c['evidence_field']==field)
        index.append({**raw,'display_macro':macro,'display_decimal_places':places,
                      'article_location':'abstract / section 5 / conclusion',
                      'display_value':f'{get(evidence,field):.{places}f}'.replace('.',',')})
    for macro,(field,places) in ANALYTIC.items():
        index.append(dict(display_macro=macro,source_file='results/r15/service_reference.json',
                          source_sha256=sha(ROOT/'results/r15/service_reference.json'),evidence_field=field,
                          display_value=f'{get(analytic,field):.{places}f}'.replace('.',','),
                          calculation='scripts/r15_service_reference.mjs',article_location='section 3.3 / conclusion'))
    (out/'claim-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    receipt.update(primary_archive_verified=True, notebook_actual_fields=len(raw_claims),
                   notebook_code_cells=len(codes),simulation_executed=False,bootstrap_recomputed=False,
                   executed_source_sha=os.getenv('GITHUB_SHA'),execution='GitHub Actions / nbconvert / Node',
                   article_sha256=sha(ROOT/'article/main.tex'),biblio_sha256=sha(ROOT/'article/r15-references.tex'))
    (out/'validation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt))
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); check(args.checkpoint,args.out)
