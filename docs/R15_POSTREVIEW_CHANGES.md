# Место → было → причина → новая редакция

# Адресная редакция R1.5 после независимой приёмки

Law: было — book с изданием и inbook с ISBN; проблема — inbook заменял книжный заголовок; стало — отдельные book, edition, isbn. Другие 27 записей не изменены.

Нативная библиография не переименована в BBL: BIB и собственный исходный BST преобразованы настоящим BibTeX. Равенство потока команд проверяется автоматически; BBL действительно подключён в main.tex. Официальный класс не меняется.

В разделе доступности научный исходник и поздняя редакционная версия обозначены отдельно; пять модулей сравниваются по Git blob. Наблюдения, seed, пороги, условность вывода и срез 07:00 не меняются.

C9 повторно не исправляется. Новый diff-PDF нужен только потому, что изменился итоговый PDF. Исторический просмотр #7117633710 хранится с прежним хешем; машинное совпадение страниц не выдаётся за собственный визуальный просмотр. Последующий #7123877180 не подтверждает нового просмотра. Авторские сведения, НСКФ, права и решение об A4 остаются открытыми. Вердикт НЕ ГОТОВО не отменён.

## article/r15-references.tex
```diff
--- before/article/r15-references.tex
+++ after/article/r15-references.tex
@@ -153,10 +153,11 @@
 
 \Bibitem{law}
 \by Law A. M.
-\book Simulation Modeling and Analysis. 5th edition
+\book Simulation Modeling and Analysis
+\edition 5th edition
 \publ McGraw-Hill Education
 \yr 2015
-\inbook ISBN 978-0-07-340132-4
+\isbn 978-0-07-340132-4
 \URL https://www.mheducation.ca/product/simulation-modeling-and-analysis-9780073401324-can
 
 \Bibitem{sargent}
```

## article/main.tex
```diff
--- before/article/main.tex
+++ after/article/main.tex
@@ -330,14 +330,15 @@
 Конфигурация допустима при указанном допущении независимости, но её минимальность не установлена. Аналитический ориентир p95 обслуживания без ожидания равен \dServiceQ{} мс. Полная сравнительная карта, независимое подтверждение, обучение оценивателей и экспериментальная проверка переразмещения остаются дальнейшей работой.
 
 \paragraph{Доступность материалов.}
-Исходники расчётной версии зафиксированы в репозитории:
+Первичные расчёты выполнены на версии \href{https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/tree/b45bfee84d9b0727243faf6cd28eeda776813566}{b45bfee8}.
+Код и отдельный условный анализ представлены в более поздней редакционной версии:
 \url{https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/tree/1801dd37898e2d53eb2ab22a8dee532fd1083f5d}.
 Первичные данные, контрольные суммы и воспроизводящие материалы доступны без авторизации:
 \url{https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/tree/4a8bc330e49adfaea7259586ca632b3b3250fc5f/deliverables/r15}.
 Набор содержит именно зафиксированный срез из131 запроса и отдельную условную оценку. Обновление оформления не изменяет эти наблюдения. Полные выходные сведения авторских тезисов НСКФ требуют уточнения.
 
 \raggedbottom
-\input{r15-references}
+\input{r15-references.bbl}
 \English\maketitle
 \section*{Extended summary}
 \textbf{Problem.} The study addresses infrastructure configuration and outlines a conceptual architecture for forecast-aware reassignment of connected tasks. The reported experiments concern configuration only. A fixed external stream is processed by an Edge--Fog--Cloud environment. The decision variables are fog-node count and waiting-buffer capacity. Both the conditional p95 of completed-message latency and the loss fraction among all arrivals must satisfy their thresholds.
```

## scripts/r15_build_author.py
```diff
--- before/scripts/r15_build_author.py
+++ after/scripts/r15_build_author.py
@@ -47,7 +47,7 @@
     for directory in ('author-tests','conditional-tests'):
         if (out/directory).exists():shutil.copytree(out/directory,delivery/'validation'/directory,dirs_exist_ok=True)
     manuscript=work/'manuscript';manuscript.mkdir(exist_ok=True)
-    for name in ('main.tex','r15-values.tex','r15-conditional-values.tex','r15-references.tex','r15-sources.json','psta.cls'):
+    for name in ('main.tex','r15-values.tex','r15-conditional-values.tex','r15-references.tex','r15-sources.json','r15-references.bib','r15-references.bbl','psta-source-preserve.bst','psta.cls'):
         shutil.copy2(ROOT/'article'/name,manuscript/name)
     shutil.copytree(ROOT/'article/psta',manuscript/'psta',dirs_exist_ok=True,
         ignore=lambda d,n:[x for x in n if Path(x).suffix.lower() in FONT_EXT])
@@ -70,7 +70,7 @@
     for f in manuscript.rglob('*'):
         if not f.is_file():continue
         rel=f.relative_to(manuscript)
-        if f.suffix.lower() in ('.tex','.cls','.sty','.def','.cfg','.clo') or (rel.parts[0]=='psta' and f.suffix.lower() in ('.png','.pdf','.eps','.jpg')):
+        if f.suffix.lower() in ('.tex','.cls','.sty','.def','.cfg','.clo','.bib','.bbl','.bst') or (rel.parts[0]=='psta' and f.suffix.lower() in ('.png','.pdf','.eps','.jpg')):
             dst=package/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
     for name in ('README.md','build.sh','NOTICE.md','cover_letter.md','author_checklist.md'):
         shutil.copy2(ROOT/'submission'/name,package/name);shutil.copy2(ROOT/'submission'/name,delivery/name)
```

## submission/build.sh
```diff
--- before/submission/build.sh
+++ after/submission/build.sh
@@ -3,6 +3,8 @@
 cd "$(dirname "$0")"
 export SOURCE_DATE_EPOCH=1795478400
 export FORCE_SOURCE_DATE=1
+printf '%s\n' '\relax' '\citation{*}' '\bibstyle{psta-source-preserve}' '\bibdata{r15-references}' > r15-references.aux
+bibtex r15-references > bibliography-build.log 2>&1 || { cat bibliography-build.log; exit 1; }
 for pass in 1 2 3; do
   pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -recorder main.tex > "build-$pass.log" 2>&1 || { cat "build-$pass.log"; exit 1; }
 done
```

## submission/README.md
```diff
--- before/submission/README.md
+++ after/submission/README.md
@@ -40,3 +40,7 @@
 
 
 Решения автора #7115069628/#7115236266 применены: название и раздел6 изменены; нулевые потери переанализированы условно при независимости. Новой имитации/обучения нет; старый R1.4 сохранён. Чувствительность порога и точность интервала различаются.
+
+
+## Адресная редакция после приёмки 24.11.2026
+Библиография содержит настоящие r15-references.bib и r15-references.bbl. BBL получен запуском BibTeX с приложенным psta-source-preserve.bst; его поток команд совпадает с принятой нативной библиографией после исправления Law. Стиль сохраняет русские и английские поля и не заменяет официальный psta.cls. build.sh заново генерирует BBL из BIB. Native r15-references.tex оставлен для прослеживаемости. Новых расчётов не выполнено. Первичный научный SHA и поздняя редакционная версия различены в source-origin.json.
```

## submission/review-resolution.md
```diff
--- before/submission/review-resolution.md
+++ after/submission/review-resolution.md
@@ -0,0 +1,9 @@
+# Адресная редакция R1.5 после независимой приёмки
+
+Law: было — book с изданием и inbook с ISBN; проблема — inbook заменял книжный заголовок; стало — отдельные book, edition, isbn. Другие 27 записей не изменены.
+
+Нативная библиография не переименована в BBL: BIB и собственный исходный BST преобразованы настоящим BibTeX. Равенство потока команд проверяется автоматически; BBL действительно подключён в main.tex. Официальный класс не меняется.
+
+В разделе доступности научный исходник и поздняя редакционная версия обозначены отдельно; пять модулей сравниваются по Git blob. Наблюдения, seed, пороги, условность вывода и срез 07:00 не меняются.
+
+C9 повторно не исправляется. Новый diff-PDF нужен только потому, что изменился итоговый PDF. Исторический просмотр #7117633710 хранится с прежним хешем; машинное совпадение страниц не выдаётся за собственный визуальный просмотр. Последующий #7123877180 не подтверждает нового просмотра. Авторские сведения, НСКФ, права и решение об A4 остаются открытыми. Вердикт НЕ ГОТОВО не отменён.
```
