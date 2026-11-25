"""Validate notebook-generated figures against primary numerical files."""
from pathlib import Path
from fractions import Fraction
import json,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
NAMES=('architecture','six_path','inputs_outputs','components','ratio','buffer','queue','forecast_socket','forecast_mae','forecast_coverage','forecast_trace','placement_chain','graph_P','graph_B','gantt_P','gantt_B','neural_placement','rho_latency','rho_wait','stationary_ratio','stationary_buffer','stationary_losses','sensitivity_edge','sensitivity_link','forecast_calibration')
def check():
    rows=[]
    for name in NAMES:
        for suffix in ('pdf','png'):
            p=ROOT/'article/figures'/f'{name}.{suffix}';b=p.read_bytes()
            assert b.startswith(b'%PDF-' if suffix=='pdf' else b'\x89PNG\r\n\x1a\n'),p
            assert len(b)>500,p
            rows.append({'file':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    control=json.loads((ROOT/'results/placement_controls.json').read_text())
    for mode,expected in [('P',8),('B',4)]:
        p=control['minimal_'+mode]['plan'];assert Fraction(p['makespan'])*1000==expected
        assert max(Fraction(r['end']) for r in p['runs'])==Fraction(p['makespan'])
    pred=pd.read_csv(ROOT/'results/forecast_predictions.csv')
    for r in pd.read_csv(ROOT/'results/forecast_metrics.csv').to_dict('records'):
        part=pred[pred.method==r['method']]
        assert abs((part.truth_ms-part.mean_ms).abs().mean()-r['mae_ms'])<1e-8
        assert abs((part.truth_ms<=part.p95_ms).mean()-r['coverage_p95'])<1e-12
        assert abs((part.truth_ms<=part.p95_before_ms).mean()-r['coverage_before'])<1e-12
    for name in ('component_shares','level_shares'):
        shares=pd.read_csv(ROOT/'results'/f'{name}.csv');assert abs(shares.share_pct.sum()-100)<1e-8
    out={'figures':rows,'figures_pdf_png':len(NAMES),'checks':'file signatures, expected names, control endpoints, recomputed forecast metrics and component-share sums','visual_review':'not automated; PDF contact-sheet inspection separate','status':'OK'}
    (ROOT/'results/figure-check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('OK:',len(NAMES),'PDF/PNG pairs and primary numerical checks.')
if __name__=='__main__':check()
