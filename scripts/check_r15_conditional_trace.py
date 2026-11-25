"""Verify actual outputs of the new R1.5 conditional-analysis cell only.
The previously accepted R1.4 notebook, simulation and bootstrap are not rerun.
"""
from pathlib import Path
import argparse,copy,hashlib,json,math,os,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
BOOK='05_R15_Условная_оценка.ipynb'
TAG='R15_CONDITIONAL_REPORT='


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def field(obj,path):
    for token in path.split('.'):obj=obj[token]
    return obj


def verify(notebook,source,expected_sha):
    cells=[c for c in notebook['cells'] if c.get('id')=='r15-05-summary']
    if len(cells)!=1 or cells[0].get('execution_count') is None:raise ValueError('missing or unexecuted report cell')
    payload=[]
    for out in cells[0].get('outputs',[]):
        text=out.get('text','');text=''.join(text) if isinstance(text,list) else text
        payload += [json.loads(line[len(TAG):]) for line in text.splitlines() if line.startswith(TAG)]
    if len(payload)!=1:raise ValueError('expected one actual structured report')
    value=payload[0]
    if value.get('cell_id')!='r15-05-summary' or value.get('source_file')!='results/r15/conditional_analysis.json' or value.get('source_sha256')!=expected_sha:
        raise ValueError('reported cell/source identity mismatch')
    expected={'n_i':[r['arrivals'] for r in source['rows']], 'n_min':source['decision']['n_min'],
      'U_L':source['decision']['U_L'],'U_L_percent':100*source['decision']['U_L'],
      'U_Q_ms':source['decision']['U_Q_ms'],'conditional_status':source['decision']['status'],
      'assumption':source['decision']['assumption'],'sensitivity':source['sensitivity'],'mm1k':source['mm1k'],
      'raw_R14_status':source['previous_R14_status'],'simulation_executed':False}
    for name,want in expected.items():
        if name not in value or value[name]!=want:raise ValueError('actual output missing or different: '+name)
    if value['n_min']!=min(value['n_i']) or value['conditional_status']!='CONDITIONALLY_ACCEPTABLE':
        raise ValueError('minimum/conditional interpretation lost')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);out=a.out.resolve()
    source_path=ROOT/'results/r15/conditional_analysis.json';source=json.loads(source_path.read_text());h=sha(source_path)
    book=ROOT/'colab/validation'/BOOK
    r=subprocess.run([sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute',str(book),
        '--output-dir',str(out),'--ExecutePreprocessor.timeout=120'],cwd=ROOT,env={**os.environ,'MPLBACKEND':'Agg'},
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    (out/'nbconvert.log').write_bytes(r.stdout)
    if r.returncode:raise RuntimeError('conditional notebook failed; see retained log')
    nb=json.loads((out/BOOK).read_text());original=json.loads(book.read_text())
    if [(c['id'],''.join(c['source'])) for c in nb['cells']]!=[(c['id'],''.join(c['source'])) for c in original['cells']]:raise ValueError('executed source mismatch')
    value=verify(nb,source,h)
    class TraceTests(unittest.TestCase):
        def test_actual_output(self):verify(nb,source,h)
        def bad(self,change):
            obj=copy.deepcopy(nb);cell=next(c for c in obj['cells'] if c.get('id')=='r15-05-summary')
            bad=copy.deepcopy(value);change(bad);cell['outputs']=[dict(output_type='stream',name='stdout',text=TAG+json.dumps(bad))]
            with self.assertRaises(ValueError):verify(obj,source,h)
        def test_sum_not_min(self):self.bad(lambda d:d.update(n_min=sum(d['n_i'])))
        def test_missing_field(self):self.bad(lambda d:d.pop('U_L'))
        def test_wrong_source(self):self.bad(lambda d:d.update(source_sha256='0'*64))
        def test_wrong_id(self):self.bad(lambda d:d.update(cell_id='r14-01-curves'))
        def test_unconditional_claim(self):self.bad(lambda d:d.update(conditional_status='ACCEPTABLE'))
        def test_no_assumption(self):self.bad(lambda d:d.update(assumption=''))
        def test_sensitivity_precision_not_threshold(self):
            row=next(r for r in value['sensitivity'] if r['reduction_factor']==50)
            self.assertTrue(row['loss_threshold_pass']);self.assertFalse(row['old_precision_pass'])
    with (out/'trace-tests.log').open('w') as f:result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TraceTests))
    if not result.wasSuccessful():raise RuntimeError('conditional trace tests failed')
    index=[]
    for name in ('n_i','n_min','U_L','U_L_percent','U_Q_ms','conditional_status','assumption','sensitivity','mm1k'):
        index.append(dict(cell_id='r15-05-summary',actual_output_field=name,value=value[name],source_file=str(source_path.relative_to(ROOT)),source_sha256=h))
    (out/'conditional-claim-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    receipt=dict(tests=result.testsRun,code_cells=2,actual_fields=len(index),source_sha256=h,
                 execution='GitHub Actions / nbconvert',simulation_executed=False,bootstrap_recomputed=False,
                 personal_Colab_browser_checked=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
