import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import nbformat
from scripts.start_dashboard import make_start

class StartDashboardTests(unittest.TestCase):
    def build(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('scripts.start_dashboard.ROOT',Path(folder)):
                p=make_start();return nbformat.read(p,as_version=4)
    def test_required_cells_present_once(self):
        book=self.build();ids=[c.id for c in book.cells]
        self.assertEqual(len(ids),len(set(ids)))
        for key in ('start-environment','start-socket','start-p95','start-losses','start-components','start-predictions','start-claims'):
            self.assertIn(key,ids)
    def test_cells_compile(self):
        for cell in self.build().cells:
            if cell.cell_type=='code':compile(cell.source,cell.id,'exec')
    def test_no_heavy_series_called(self):
        import ast
        calls=[]
        for cell in self.build().cells:
            if cell.cell_type=='code':
                calls.extend(n.func.id for n in ast.walk(ast.parse(cell.source)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name))
        self.assertTrue({'stationary_series','sensitivity_series','forecast_study'}.isdisjoint(calls))
    def test_source_and_cell_map_explicit(self):
        code='\n'.join(c.source for c in self.build().cells if c.cell_type=='code')
        for text in ('stationary_replicates.csv','forecast_predictions.csv','claims-to-cells.csv','sha256','last_observed_completion_s'):
            self.assertIn(text,code)

if __name__=='__main__':unittest.main()
