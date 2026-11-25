#!/bin/sh
set -eu
cd "$(dirname "$0")"
export SOURCE_DATE_EPOCH=1795478400 FORCE_SOURCE_DATE=1
printf '%s\n' '\relax' '\citation{*}' '\bibstyle{psta-source-preserve}' '\bibdata{references}' > references.aux
bibtex references > bibtex-build.log 2>&1
for pass in 1 2 3; do
 pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex > build-$pass.log 2>&1 || { tail -60 build-$pass.log; exit 1; }
done
if grep -E 'Undefined control sequence|LaTeX Error|There were undefined references|Citation .*undefined|Reference .*undefined|Float too large' main.log; then exit 1; fi
