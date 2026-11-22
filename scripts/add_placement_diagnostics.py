"""Add explicit background accounting to the executed placement notebook."""
from pathlib import Path
import nbformat as n
p=Path(__file__).resolve().parents[1]/'colab/clean/03_Алгоритм_переразмещения.ipynb'
nb=n.read(p,as_version=4)
for cell in nb.cells:
    if cell.cell_type=='code' and 'linked,payload=neural_placement()' in cell.source and 'background_accounting' not in cell.source:
        cell.source=cell.source.replace('linked,payload=neural_placement()','linked,payload=neural_placement()\nfrom efc.placement.diagnostics import background_accounting\nlinked,payload=background_accounting(linked,payload)')
n.write(nb,p)
print('Placement counterfactual added without changing v2 or reranking.')
