"""Prepare structural includes; bibliography is rendered from final main.tex later."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'article/main.template.tex';s=p.read_text()
if r'\input{related}' not in s:
    s=s.replace(r'\section{Модель вычислительной среды}',r'\input{related}'+'\n\n'+r'\section{Модель вычислительной среды}')
s=re.sub(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}',lambda _:r'\input{availability}'+'\n'+r'\input{references_verified}',s,flags=re.S)
if r'\cite{nskf}' not in s:s=s.replace('НСКФ-2026','НСКФ-2026~'+r'\cite{nskf}',1)
p.write_text(s)
print('Template includes prepared; final cited metadata will be checked after article integration.')
