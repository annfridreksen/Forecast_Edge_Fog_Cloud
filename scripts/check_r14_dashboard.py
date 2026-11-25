"""Execute the real author notebook and widget callbacks; no scientific grid."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_r14_core import run_logged

def main():
    out=ROOT/'results/r14/current/dashboard';out.mkdir(parents=True,exist_ok=True)
    os.environ['FEFC_SOURCE_SHA']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() if (ROOT/'.git').exists() else os.environ.get('FEFC_SOURCE_SHA','local archived sources')
    report=dict(status='RUNNING',execution='Actions/nbconvert' if os.getenv('GITHUB_ACTIONS')=='true' else 'local Python/nbconvert',colab_browser_checked=False,full_grid_run=False,steps=[])
    try:
        for name,cmd in [('tests',[sys.executable,'-m','unittest','discover','-s','tests','-p','test_dashboard*.py','-v']),
                         ('notebook',[sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute','colab/00_Старт.ipynb','--output-dir',str(out),'--ExecutePreprocessor.timeout=180']),
                         ('map-view',[sys.executable,'-m','jupyter','nbconvert','--to','notebook','--execute','colab/validation/04_R14_map_view.ipynb','--output-dir',str(out),'--ExecutePreprocessor.timeout=180'])]:
            r=run_logged(cmd,out/(name+'.log'));report['steps'].append(r)
            if r['returncode']:raise RuntimeError('failed '+name)
        b=json.loads((out/'00_Старт.ipynb').read_text());cells=[c for c in b['cells'] if c['cell_type']=='code']
        if len(cells)!=6 or any(c['execution_count'] is None for c in cells):raise RuntimeError('unexecuted cells')
        if any(o.get('output_type')=='error' for c in cells for o in c['outputs']):raise RuntimeError('notebook cell error')
        receipt=''.join(o.get('text','') if isinstance(o.get('text',''),str) else ''.join(o.get('text',[])) for o in cells[-1]['outputs'])
        data=json.loads(receipt)
        if data['full_grid_executed'] or data['forecast_executed'] or not data['shutdown_callback_checked']:raise RuntimeError('wrong execution scope')
        if data['example_calls']!=1 or data['single_replication_not_statistical']!='NOT_EVALUATED_SINGLE_REPLICATION':raise RuntimeError('wrong example semantics')
        import base64
        images=0
        for c in cells:
            for o in c['outputs']:
                encoded=o.get('data',{}).get('image/png')
                if encoded:
                    images+=1;(out/f'figure-{images}.png').write_bytes(base64.b64decode(encoded))
        if images<2:raise RuntimeError('missing architecture/manual diagrams')
        validation=json.loads((out/'04_R14_map_view.ipynb').read_text())
        vcells=[c for c in validation['cells'] if c['cell_type']=='code']
        if len(vcells)!=3 or any(c['execution_count'] is None for c in vcells):raise RuntimeError('unexecuted map-view cells')
        if any(o.get('output_type')=='error' for c in vcells for o in c['outputs']):raise RuntimeError('map-view cell error')
        texts=''.join(o.get('text','') if isinstance(o.get('text',''),str) else ''.join(o.get('text',[])) for o in vcells[-1]['outputs'])
        view_receipt=json.loads(texts)
        if not view_receipt['archive_error_isolated'] or not view_receipt['figure_states_distinct'] or view_receipt['fixture_is_scientific_result']:raise RuntimeError('map-view scope failed')
        map_images=0
        for c in vcells:
            for o in c['outputs']:
                encoded=o.get('data',{}).get('image/png')
                if encoded:
                    map_images+=1;(out/f'map-view-{map_images}.png').write_bytes(base64.b64decode(encoded))
        if map_images<1:raise RuntimeError('missing four-state map image')
        report.update(status='PASS',executed_code_cells=len(cells),validation_code_cells=len(vcells),
                      images=images,map_images=map_images,receipt=data,map_receipt=view_receipt)
    finally:
        report['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['efc/dashboard.py','efc/saved_map.py','efc/map_view.py','tests/test_dashboard.py','tests/test_dashboard_saved_map.py','tests/test_dashboard_resilience.py','tests/test_dashboard_map_colors.py','scripts/check_r14_dashboard.py','colab/00_Старт.ipynb','colab/validation/04_R14_map_view.ipynb']}
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PASS: author notebook and callbacks; not a stationary map or browser certification.')
if __name__=='__main__':main()
