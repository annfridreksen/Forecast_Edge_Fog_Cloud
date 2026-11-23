#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
export SOURCE_DATE_EPOCH=1795478400
export FORCE_SOURCE_DATE=1
for pass in 1 2 3; do
  pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -recorder main.tex > "build-$pass.log" 2>&1 || { cat "build-$pass.log"; exit 1; }
done
if grep -E 'Undefined control sequence|There were undefined references|Citation .*undefined|Reference .*undefined|LaTeX Error' main.log; then
  echo 'Unresolved error/reference; manuscript is not accepted.' >&2
  exit 1
fi
printf '%s\n' 'PDF built. Author metadata and scientific acceptance must be checked separately.'
