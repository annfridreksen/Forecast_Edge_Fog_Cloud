ENTRY { author title year journal booktitle series volume number pages publisher doi url isbn edition psta00 psta01 psta02 psta03 psta04 psta05 psta06 psta07 psta08 psta09 psta10 psta11 psta12 psta13 psta14 psta15 psta16 psta17 psta18 psta19 psta20 psta21 psta22 psta23 psta24 psta25 psta26 psta27 psta28 psta29 psta30 psta31 } {} {}
FUNCTION {record} {
  psta00 empty$ { skip$ } { psta00 write$ newline$ } if$
  psta01 empty$ { skip$ } { psta01 write$ newline$ } if$
  psta02 empty$ { skip$ } { psta02 write$ newline$ } if$
  psta03 empty$ { skip$ } { psta03 write$ newline$ } if$
  psta04 empty$ { skip$ } { psta04 write$ newline$ } if$
  psta05 empty$ { skip$ } { psta05 write$ newline$ } if$
  psta06 empty$ { skip$ } { psta06 write$ newline$ } if$
  psta07 empty$ { skip$ } { psta07 write$ newline$ } if$
  psta08 empty$ { skip$ } { psta08 write$ newline$ } if$
  psta09 empty$ { skip$ } { psta09 write$ newline$ } if$
  psta10 empty$ { skip$ } { psta10 write$ newline$ } if$
  psta11 empty$ { skip$ } { psta11 write$ newline$ } if$
  psta12 empty$ { skip$ } { psta12 write$ newline$ } if$
  psta13 empty$ { skip$ } { psta13 write$ newline$ } if$
  psta14 empty$ { skip$ } { psta14 write$ newline$ } if$
  psta15 empty$ { skip$ } { psta15 write$ newline$ } if$
  psta16 empty$ { skip$ } { psta16 write$ newline$ } if$
  psta17 empty$ { skip$ } { psta17 write$ newline$ } if$
  psta18 empty$ { skip$ } { psta18 write$ newline$ } if$
  psta19 empty$ { skip$ } { psta19 write$ newline$ } if$
  psta20 empty$ { skip$ } { psta20 write$ newline$ } if$
  psta21 empty$ { skip$ } { psta21 write$ newline$ } if$
  psta22 empty$ { skip$ } { psta22 write$ newline$ } if$
  psta23 empty$ { skip$ } { psta23 write$ newline$ } if$
  psta24 empty$ { skip$ } { psta24 write$ newline$ } if$
  psta25 empty$ { skip$ } { psta25 write$ newline$ } if$
  psta26 empty$ { skip$ } { psta26 write$ newline$ } if$
  psta27 empty$ { skip$ } { psta27 write$ newline$ } if$
  psta28 empty$ { skip$ } { psta28 write$ newline$ } if$
  psta29 empty$ { skip$ } { psta29 write$ newline$ } if$
  psta30 empty$ { skip$ } { psta30 write$ newline$ } if$
  psta31 empty$ { skip$ } { psta31 write$ newline$ } if$
  newline$
}
FUNCTION {book} { record }
FUNCTION {article} { record }
FUNCTION {inproceedings} { record }
FUNCTION {unpublished} { record }
FUNCTION {misc} { record }
FUNCTION {default.type} { record }
FUNCTION {begin.bib} { "\begin{thebibliography}{99}" write$ newline$ }
FUNCTION {end.bib} { "\end{thebibliography}" write$ newline$ }
READ
EXECUTE {begin.bib}
ITERATE {call.type$}
EXECUTE {end.bib}
