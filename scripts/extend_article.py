"""Idempotent integration of reviewed literature and reproducibility metadata."""
from pathlib import Path
import re
from render_references import render
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'article/main.template.tex';s=p.read_text()
if r'\input{related}' not in s:
    s=s.replace(r'\section{Модель вычислительной среды}',r'\input{related}'+'\n\n'+r'\section{Модель вычислительной среды}')
s=re.sub(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}',lambda m:r'\input{availability}'+'\n'+r'\input{references_verified}',s,flags=re.S)
if r'\cite{nskf}' not in s:s=s.replace('НСКФ-2026','НСКФ-2026~'+r'\cite{nskf}',1)
p.write_text(s)
render()
