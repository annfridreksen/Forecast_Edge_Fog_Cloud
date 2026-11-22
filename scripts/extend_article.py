"""Idempotent, explicit response to review R19; no numeric results are changed."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'article/main.template.tex';s=p.read_text()
if r'\input{related}' not in s:
    s=s.replace(r'\section{Модель вычислительной среды}',r'\input{related}'+'\n\n'+r'\section{Модель вычислительной среды}')
if r'\input{related_references}' not in s:
    s=s.replace(r'\Bibitem{little}',r'\input{related_references}'+'\n'+r'\Bibitem{little}')
p.write_text(s)
