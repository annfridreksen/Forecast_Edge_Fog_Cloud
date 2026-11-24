"""Address post-review editorial defects; never simulate, bootstrap or sign for authors.
Prepare commits exact source changes under a lease. Inspect checks actual generated
bytes. Register persists post-publication evidence and releases this executor.
"""
from pathlib import Path
import argparse, difflib, hashlib, json, os, re, shutil, subprocess, sys, tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = '13623e2a442ecfdad83307e327cfe67b47bdcaf3'
BASE_PDF = '0672dff5958633b6119b436a88a41331c6e8c76c0b0a0dfe617525acee79e78a'
EDITORIAL = '1801dd37898e2d53eb2ab22a8dee532fd1083f5d'
REPO = 'annfridreksen/Forecast_Edge_Fog_Cloud'
REF = 'refs/heads/night/fefc-v3'
OUT = ROOT/'results/r15/build'
REVIEW = 'https://github.com/'+REPO+'/issues/5#issuecomment-7117633710'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def put(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Expected one unchanged anchor: '+repr(old[:100]))
    return s.replace(old, new, 1)

def commit(paths, message, expected):
    if git('ls-remote', 'origin', REF).split()[0] != expected:
        raise RuntimeError('HEAD lease lost; preserve results, do not overwrite')
    git('config','user.name','FEFC post-review executor')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--',*paths)
    staged = subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
    if not set(filter(None,staged)) <= set(paths):
        raise RuntimeError('Unexpected staged path')
    if git('ls-remote','origin',REF).split()[0] != expected:
        raise RuntimeError('HEAD moved before commit')
    git('commit','-m',message)
    new = git('rev-parse','HEAD')
    git('push','origin','HEAD:'+REF)
    if git('ls-remote','origin',REF).split()[0] != new:
        raise RuntimeError('Remote did not retain the published commit')
    return new

def bibliography(bib):
    """Real BibTeX input/style/output, preserving the accepted PSTA field stream."""
    blocks = re.split(r'(?=\\R?Bibitem\{)',bib)[1:]
    fields = ['psta%02d'%i for i in range(32)]
    db = ['% Generated from reviewed native PSTA records; no invented metadata.']
    keys = []
    for block in blocks:
        block = block.split(r'\end{thebibliography}',1)[0]
        lines = [x.strip() for x in block.splitlines() if x.strip()]
        key = re.match(r'\\R?Bibitem\{([^}]+)\}',lines[0]).group(1)
        if len(lines)>len(fields): raise ValueError('Too many native fields')
        keys.append(key)
        native = {}
        for line in lines[1:]:
            if line == r'\transl': break
            match = re.match(r'\\(\w+)\s+(.+)',line)
            if match: native[match[1]]=match[2]
        kind = 'unpublished' if key=='nskf' else ('book' if 'book' in native else ('article' if 'jour' in native else 'inproceedings'))
        meta = {'title':native.get('book',native.get('paper','')), 'year':native.get('yr','')}
        if native.get('by'):
            meta['author']=' and '.join('{'+n+'}' for n in native['by'].split(', '))
        for src,dst in [('jour','journal'),('inbook','booktitle'),('serial','series'),('vol','volume'),('issue','number'),('pages','pages'),('publ','publisher'),('doi','doi'),('URL','url'),('isbn','isbn'),('edition','edition')]:
            if src in native: meta[dst]=native[src]
        db.append('@'+kind+'{'+key+',')
        for name,value in meta.items(): db.append('  '+name+' = {'+value+'},')
        for name,value in zip(fields,lines): db.append('  '+name+' = {'+value+'},')
        db.append('}\n')
    if len(keys)!=28 or len(set(keys))!=28: raise ValueError('Reference count changed')
    metadata = 'author title year journal booktitle series volume number pages publisher doi url isbn edition'
    bst = ['ENTRY { '+metadata+' '+' '.join(fields)+' } {} {}', 'FUNCTION {record} {']
    bst += [f'  {f} empty$ {{ skip$ }} {{ {f} write$ newline$ }} if$' for f in fields]
    bst += ['  newline$', '}']
    for kind in ('book','article','inproceedings','unpublished','misc','default.type'):
        bst.append('FUNCTION {'+kind+'} { record }')
    bst += [r'FUNCTION {begin.bib} { "\begin{thebibliography}{99}" write$ newline$ }',r'FUNCTION {end.bib} { "\end{thebibliography}" write$ newline$ }','READ','EXECUTE {begin.bib}','ITERATE {call.type$}','EXECUTE {end.bib}']
    article = ROOT/'article'
    (article/'r15-references.bib').write_text('\n'.join(db)+'\n',encoding='utf-8')
    (article/'psta-source-preserve.bst').write_text('\n'.join(bst)+'\n',encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='r15-bibtex-') as tmp:
        t=Path(tmp)
        for name in ('r15-references.bib','psta-source-preserve.bst'): shutil.copy2(article/name,t/name)
        (t/'r15-references.aux').write_text('\\relax\n\\citation{*}\n\\bibstyle{psta-source-preserve}\n\\bibdata{r15-references}\n')
        r=subprocess.run(['bibtex','r15-references'],cwd=t,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        (OUT/'postreview-bibtex.log').write_bytes(r.stdout)
        if r.returncode: raise RuntimeError('BibTeX failed: '+r.stdout.decode(errors='replace'))
        produced=(t/'r15-references.bbl').read_text()
        expected=bib[bib.index(r'\begin{thebibliography}'):].strip()
        if ' '.join(produced.split())!=' '.join(expected.split()):
            raise ValueError('Generated BBL differs from reviewed native records')
        shutil.copy2(t/'r15-references.bbl',article/'r15-references.bbl')
    return dict(engine='BibTeX',entries=28,native_token_stream_equal=True,
                bib_sha256=sha(article/'r15-references.bib'),bbl_sha256=sha(article/'r15-references.bbl'),
                style_sha256=sha(article/'psta-source-preserve.bst'),
                style_origin='Original source-preserving exporter; official psta.cls is unchanged.')

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    expected=os.environ['GITHUB_SHA']
    if git('ls-remote','origin',REF).split()[0]!=expected: raise RuntimeError('Not current HEAD')
    if subprocess.check_output(['git','diff',BASE,'HEAD','--','article/main.tex','article/r15-references.tex'],cwd=ROOT):
        raise RuntimeError('Manuscript changed since the reviewed baseline')
    changed={}
    def edit(path, value):
        p=ROOT/path; old=p.read_text() if p.exists() else ''
        changed[path]=(old,value);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8')
    native=(ROOT/'article/r15-references.tex').read_text()
    native=once(native,r'\book Simulation Modeling and Analysis. 5th edition',r'\book Simulation Modeling and Analysis'+'\n'+r'\edition 5th edition')
    native=once(native,r'\inbook ISBN 978-0-07-340132-4',r'\isbn 978-0-07-340132-4')
    edit('article/r15-references.tex',native)
    bib_receipt=bibliography(native)
    scientific=git('rev-parse','b45bfee^{commit}')
    blobs=[]
    for path in ('efc/model.py','efc/workload.py','efc/grid.py','efc/pilot.py','efc/statistics.py'):
        original=git('rev-parse',scientific+':'+path); current=git('rev-parse',EDITORIAL+':'+path)
        if original!=current: raise ValueError('Scientific/editorial core differs: '+path)
        blobs.append(dict(path=path,scientific_blob=original,editorial_blob=current))
    origin=dict(scientific_source_sha=scientific,editorial_analysis_sha=EDITORIAL,core_blob_comparison=blobs,
                frozen_snapshot_requests=131,latest_scientific_cache_requests=162,
                snapshots_combined=False,simulation_executed=False,bootstrap_recomputed=False)
    put(ROOT/'docs/R15_SOURCE_ORIGIN.json',origin)
    text=(ROOT/'article/main.tex').read_text()
    text=once(text,r'\input{r15-references}',r'\input{r15-references.bbl}')
    origin_text='Первичные расчёты выполнены на версии '+r'\href{https://github.com/'+REPO+'/tree/'+scientific+'}{'+scientific[:8]+'}'+'.\nКод и отдельный условный анализ представлены в более поздней редакционной версии:'
    text=once(text,'Исходники расчётной версии зафиксированы в репозитории:',origin_text)
    edit('article/main.tex',text)
    builder=(ROOT/'scripts/r15_build_author.py').read_text()
    builder=once(builder,"'r15-sources.json','psta.cls'","'r15-sources.json','r15-references.bib','r15-references.bbl','psta-source-preserve.bst','psta.cls'")
    builder=once(builder,"if f.suffix.lower() in ('.tex','.cls','.sty','.def','.cfg','.clo')", "if f.suffix.lower() in ('.tex','.cls','.sty','.def','.cfg','.clo','.bib','.bbl','.bst')")
    edit('scripts/r15_build_author.py',builder)
    build=(ROOT/'submission/build.sh').read_text()
    regeneration="printf '%s\\n' '\\relax' '\\citation{*}' '\\bibstyle{psta-source-preserve}' '\\bibdata{r15-references}' > r15-references.aux\nbibtex r15-references > bibliography-build.log 2>&1 || { cat bibliography-build.log; exit 1; }\n"
    build=once(build,'for pass in 1 2 3; do',regeneration+'for pass in 1 2 3; do')
    edit('submission/build.sh',build)
    readme=(ROOT/'submission/README.md').read_text()
    edit('submission/README.md',readme+'\n\n## Адресная редакция после приёмки 24.11.2026\nБиблиография содержит настоящие r15-references.bib и r15-references.bbl. BBL получен запуском BibTeX с приложенным psta-source-preserve.bst; его поток команд совпадает с принятой нативной библиографией после исправления Law. Стиль сохраняет русские и английские поля и не заменяет официальный psta.cls. build.sh заново генерирует BBL из BIB. Native r15-references.tex оставлен для прослеживаемости. Новых расчётов не выполнено. Первичный научный SHA и поздняя редакционная версия различены в source-origin.json.\n')
    report='''# Адресная редакция R1.5 после независимой приёмки

Law: было — book с изданием и inbook с ISBN; проблема — inbook заменял книжный заголовок; стало — отдельные book, edition, isbn. Другие 27 записей не изменены.

Нативная библиография не переименована в BBL: BIB и собственный исходный BST преобразованы настоящим BibTeX. Равенство потока команд проверяется автоматически; BBL действительно подключён в main.tex. Официальный класс не меняется.

В разделе доступности научный исходник и поздняя редакционная версия обозначены отдельно; пять модулей сравниваются по Git blob. Наблюдения, seed, пороги, условность вывода и срез 07:00 не меняются.

C9 повторно не исправляется. Новый diff-PDF нужен только потому, что изменился итоговый PDF. Исторический просмотр #7117633710 хранится с прежним хешем; машинное совпадение страниц не выдаётся за собственный визуальный просмотр. Последующий #7123877180 не подтверждает нового просмотра. Авторские сведения, НСКФ, права и решение об A4 остаются открытыми. Вердикт НЕ ГОТОВО не отменён.
'''
    edit('submission/review-resolution.md',report)
    diffs=['# Место → было → причина → новая редакция\n',report]
    for path,(old,new) in changed.items():
        diffs.append('## '+path+'\n```diff\n'+''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='before/'+path,tofile='after/'+path))+'```\n')
    edit('docs/R15_POSTREVIEW_CHANGES.md','\n'.join(diffs))
    edit('docs/STATUS.md','# STATUS — R1.5, адресная редакция после приёмки\n\n24.11.2026. Старый владелец #7115035873 явно освободил запись. Текущий единственный писатель #7124374400, BT26-R15-EXEC-20261124-10. Только night/fefc-v3; PR#2 без слияния.\n\nПодготовлены исправление Law, реальные BIB/BBL и различение научной/редакционной версий. Новая сборка и публикация ещё не подтверждены. Последняя завершённая доставка '+BASE+', PDF '+BASE_PDF+'. Последний обработанный комментарий #7123877180; финальный вердикт #7122631239 — НЕ ГОТОВО.\n\nТекущий run '+os.environ.get('GITHUB_RUN_ID','unknown')+'. Пока он выполняется, не менять HEAD и не дублировать процесс. Следующая операция: штатная сборка, проверка отображения Law, восстановление BBL из BIB в изолированном ZIP, разница фактических страниц и публикация с lease.\n\nНаучный срез07:00 неизменён: статья131, отдельный кэш162; A4/независимое подтверждение не завершены. Авторские сведения/права/НСКФ остаются [ДЛЯ АВТОРА]. Согласия не подписаны, статья не отправлена. После публикации register сохранит точные SHA/хеши и явно освободит запись.\n')
    paths=list(changed)+['article/r15-references.bib','article/r15-references.bbl','article/psta-source-preserve.bst','docs/R15_SOURCE_ORIGIN.json']
    new=commit(paths,'Issue #5 R1.5: исправить Law, включить реальные BIB/BBL и уточнить происхождение кода',expected)
    with open(os.environ['GITHUB_ENV'],'a') as f:f.write('R15_SOURCE_SHA='+new+'\n')
    put(OUT/'bibliography-generation.json',bib_receipt)
    print('POSTREVIEW_SOURCE_SHA',new,flush=True)

def checklist(receipt, changed):
    return '''# Чек-лист R1.5 — адресная редакция после приёмки

Основание: задание автора и https://psta.psiras.ru/publ-conditions/publ-conditions.html . Квоты источников и BIB/BBL — дополнительные требования автора. Новая редакция не отменяет вердикт НЕ ГОТОВО.

|№|Статус|Файл / проверка|Что осталось|
|---|---|---|---|
|1|Выполнено технически|submission.zip; официальный класс; BIB, настоящий BibTeX-BBL и BST; чистая сборка ZIP|Авторская комплектность отдельно, см.3/8|
|2|Выполнено по прежней содержательной приёмке|RU/EN, аннотации, подписи, Extended summary; 8 разделов|Не выдавать это за одобрение журнала|
|3|[ДЛЯ АВТОРА]|Авторские блоки/фотографии отсутствуют без подтверждения|Состав авторов, организации, фото и права, 4–7 строк о каждом, финансирование|
|4|Law исправлен; остальное частично|law-render-check.json; bibliography-generation.json; 28 записей/27 идентификаторов/10 за2023–2026|[ДЛЯ АВТОРА] НСКФ: выходные сведения, авторство, идентификатор и основание использования профилей|
|5|См. publication.json|Неизменяемые ссылки; фактические анонимные загрузки и SHA|[ДЛЯ АВТОРА] права на публикацию; DOI комплекта не присваивался|
|6|Технические проверки выполнены|TikZ, номера, гиперссылки, двуязычные подписи; все страницы рисунков в7×|Визуальный осмотр всех схем7×; оставшиеся предупреждения не скрыты|
|7|Частично; не новый визуальный PASS|page-review.json: сравнение растров старого/нового PDF; прежний просмотр #7117633710|Просмотр изменённых страниц и всех полных рисунков7×; собственный просмотр не заявлен|
|8|Проект подготовлен|cover_letter.md, не подписан/не отправлен|[ДЛЯ АВТОРА] личные подтверждения, реквизиты, финансирование и подпись|
|9|Выполнено технически|difference.pdf; настоящий diff-pdf; точные before/after SHA в provenance|Независимая адресная приёмка нового комплекта|

**A4 не завершена.** Срез07:00 не расширен; нужны решение автора о подаче сокращённого исследования либо отдельное согласование недостающих сравнений. Минимум и независимое подтверждение не заявляются.

Изменённые по пикселям страницы: '''+', '.join(map(str,changed))+'. Полный список и хеш PDF — page-review.json.\n'

def inspect():
    import fitz
    from scripts.build_r15_submission import package_zip, unpack
    d=OUT/'delivery';receipt=json.loads((d/'build-receipt.json').read_text())
    old=OUT/'reviewed-baseline.pdf';new=d/'article.pdf'
    old.write_bytes(subprocess.check_output(['git','show',BASE+':deliverables/r15/article.pdf'],cwd=ROOT))
    if sha(old)!=BASE_PDF:raise ValueError('Wrong previously reviewed PDF')
    ledger=[];changed=[];figure_pages=[]
    main=(ROOT/'article/main.tex').read_text()
    captions=[]
    for figure in re.findall(r'\\begin\{figure\}.*?\\end\{figure\}',main,re.S):
        cap=re.search(r'\\engcap\{([^{}]*)\}',figure)
        if cap:captions.append(cap[1])
    normalize=lambda s:re.sub(r'\W+','',s.lower())
    with fitz.open(old) as before,fitz.open(new) as after:
        text=' '.join(p.get_text() for p in after)
        flat=' '.join(text.split())
        checks={'title':'Simulation Modeling and Analysis' in flat,'edition':'5th edition' in flat,'isbn':'9780073401324' in re.sub(r'[^0-9]','',flat)}
        if not all(checks.values()):raise ValueError('Law rendered fields missing: '+repr(checks))
        lawpages=[i+1 for i,p in enumerate(after) if 'Simulation Modeling and Analysis' in ' '.join(p.get_text().split())]
        put(d/'law-render-check.json',dict(status='PASS',pdf_sha256=sha(new),checks=checks,pages=lawpages,inspection='Actual extracted PDF text, not source-only and not visual'))
        for i,p in enumerate(after):
            pix=p.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
            equal=False
            if i<len(before):
                prev=before[i].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
                equal=(pix.width,pix.height,pix.samples)==(prev.width,prev.height,prev.samples)
            if not equal:changed.append(i+1)
            ledger.append(dict(page=i+1,pdf_sha256=sha(new),prior_pdf_sha256=BASE_PDF,pixel_equal_to_prior=equal,
                visual_status='PRIOR_REVIEW_RECORDED_PIXEL_IDENTICAL' if equal else 'PENDING_CHANGED_PAGE_VISUAL_REVIEW',
                prior_review=REVIEW,own_visual_review=False))
            normalized=normalize(p.get_text())
            for cap in captions:
                if normalize(cap)[:50] in normalized and i+1 not in figure_pages:
                    figure_pages.append(i+1)
                    p.get_pixmap(matrix=fitz.Matrix(7,7),alpha=False).save(d/'pages'/f'figure-page-{i+1:02}-7x.png')
        if not captions or len(captions)!=main.count(r'egin{figure}') or len(figure_pages)!=len(captions):raise ValueError('Not all source figure pages identified: '+repr((captions,figure_pages)))
    put(d/'page-review.json',ledger)
    put(d/'postreview-resolution.json',dict(baseline_delivery=BASE,pdf_sha256=sha(new),changed_pages=changed,
       figure_7x_pages=figure_pages,own_visual_review=False,prior_review_source=REVIEW,
       later_review_scope='7123877180 reports no new personal visual inspection; earlier record is preserved, not replaced.',
       resolved=['Law title/edition/ISBN rendering','real BibTeX BIB/BBL','one-shot C9 not rerun','scientific versus editorial source'],
       open=['author metadata and permissions','NSCF bibliographic details and profile provenance','A4 scope decision','changed-page and all-figure visual review','independent final acceptance'],
       wei_primary_source='https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.APPROX/RANDOM.2020.60',
       wei_checked='Author/title/year/volume/pages/DOI confirmed from publisher by executor web access on 2026-11-24 and reviewer 7122631239; not a new full bibliography audit.'))
    shutil.copy2(OUT/'bibliography-generation.json',d/'bibliography-generation.json')
    shutil.copy2(ROOT/'docs/R15_SOURCE_ORIGIN.json',d/'source-origin.json')
    shutil.copy2(ROOT/'submission/review-resolution.md',d/'review-resolution.md')
    (d/'author_checklist.md').write_text(checklist(receipt,changed),encoding='utf-8')
    report=json.loads((d/'bibliography-report.json').read_text())
    report['postreview_primary_verification']={'advice':{'status':'CONFIRMED','source':'https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.APPROX/RANDOM.2020.60','basis':'Executor web and reviewer 7122631239; old network failure retained historically'},'law':{'status':'CONFIRMED','source':'https://www.mheducation.com/highered/product/Simulation-Modeling-and-Analysis-Law.html','edition':5,'year':2015,'isbn':'9780073401324'}}
    put(d/'bibliography-report.json',report)
    package=OUT/'work/submission'
    for name in ('author_checklist.md','review-resolution.md','source-origin.json','bibliography-generation.json','law-render-check.json','page-review.json','postreview-resolution.json','bibliography-report.json'):
        shutil.copy2(d/name,package/name)
    package_zip(package,d/'submission.zip')
    # This distinct check regenerates BBL from BIB using the shipped build.sh.
    # The earlier builder checked direct pdflatex with shipped BBL; neither runs science.
    with tempfile.TemporaryDirectory(prefix='r15-final-zip-') as tmp:
        fresh=unpack(d/'submission.zip',Path(tmp)/'source')
        r=subprocess.run(['sh','build.sh'],cwd=fresh,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (OUT/'final-zip-bibtex-build.log').write_bytes(r.stdout)
        if r.returncode:raise RuntimeError('Final ZIP build.sh failed: '+r.stdout.decode(errors='replace')[-2000:])
        with fitz.open(fresh/'main.pdf') as a,fitz.open(new) as b:
            if len(a)!=len(b) or [p.get_text() for p in a]!=[p.get_text() for p in b]:raise ValueError('Final ZIP PDF content differs')
        isolated_sha=sha(fresh/'main.pdf')
        if sha(fresh/'r15-references.bbl')!=sha(ROOT/'article/r15-references.bbl'):
            raise ValueError('BIB regeneration changed BBL')
    receipt.update(submission_zip_sha256=sha(d/'submission.zip'),final_zip_build_sh='PASS',
       final_zip_bibtex_regeneration='PASS',final_zip_pdf_sha256=isolated_sha,
       final_zip_byte_identical=isolated_sha==sha(new),visual_review='PENDING_CHANGED_PAGES_AND_FULL_7X_FIGURES',
       changed_pages=changed,figure_7x_pages=figure_pages,law_render='PASS',bibtex_generation='PASS')
    put(d/'build-receipt.json',receipt);put(OUT/'receipt.json',receipt)
    print('POSTREVIEW_INSPECTION',json.dumps(receipt,ensure_ascii=False),flush=True)

def register():
    pub=json.loads((OUT/'publication.json').read_text())
    if pub['status']!='PUBLIC_DOWNLOAD_VERIFIED':raise ValueError('Publication was not verified')
    expected=pub['delivery_sha'];target=ROOT/'deliverables/r15'
    put(target/'publication.json',pub)
    receipt=json.loads((target/'build-receipt.json').read_text())
    receipt.update(public_access='PUBLIC_DOWNLOAD_VERIFIED',publication_receipt='publication.json',artifact_delivery_sha=expected)
    put(target/'build-receipt.json',receipt)
    put(target/'release-status.json',dict(ready_to_submit=False,article_sent=False,author_signed=False,
      writer_lease='RELEASED',writer_comment=7124374400,source_sha=pub['source_sha'],artifact_delivery_sha=expected,
      run_id=os.environ.get('GITHUB_RUN_ID'),last_review_comment=7123877180,final_review_verdict='NOT_READY_7122631239',
      fixed=['Law','BIB/BBL','repeatable build route','source provenance','persistent publication receipt'],
      open=['author metadata/rights/funding','NSCF identity/profile provenance','A4 scope decision','changed-page/full7x visual check','independent addressed acceptance']))
    put(target/'SHA256.json',{p.relative_to(target).as_posix():sha(p) for p in sorted(target.rglob('*')) if p.is_file() and p.name!='SHA256.json'})
    status='# STATUS — R1.5: адресный технический этап завершён\n\n24.11.2026. Владелец #7124374400 явно ОСВОБОДИЛ запись после успешной публикации. Старый #7115035873 также закрыт. Незавершённого push этого workflow нет. Только night/fefc-v3; PR#2 не слит.\n\nИсходники: '+pub['source_sha']+'. Коммит артефактов: '+expected+'. Run '+os.environ.get('GITHUB_RUN_ID','unknown')+'. Последующие метаданные не меняют PDF/ZIP.\nPDF SHA256 '+receipt['pdf_sha256']+'\nZIP SHA256 '+receipt['submission_zip_sha256']+'\n\nLaw title/edition/ISBN: PASS по тексту PDF. Настоящие BIB/BBL/BST: PASS, BBL подключён; изолированный ZIP→build.sh→BibTeX+pdflatex: PASS. diff-pdf выполнен для изменённого PDF. Девять анонимных загрузок с хешами сохранены в deliverables/r15/publication.json. Официальный класс не изменён. Старый отказ C9 закрыт.\n\nВизуальная проверка: прежняя #7117633710 относится к PDF '+BASE_PDF+'. Новое сравнение страниц — page-review.json; пиксельное равенство не называется собственным осмотром. Изменённые страницы '+str(receipt['changed_pages'])+' и все полные схемы7× требуют просмотра. Поздний #7123877180 сообщает отсутствие нового просмотра, не отменяет исторический отчёт.\n\nСрез07:00 не расширен: статья131, отдельный кэш162. Новых симуляций/bootstrap/обучения нет. Принятые решения6–9 и условный вывод сохранены. A4/независимое подтверждение не завершены. [ДЛЯ АВТОРА] решение о сокращённом исследовании, авторский состав/организации/финансирование/фото/права/согласия и сведения НСКФ. Вердикт #7122631239 НЕ ГОТОВО сохраняется до адресной независимой приёмки.\n\nСледующий шаг: читать publication/release-status/page-review, осмотреть только изменённые страницы и все схемы; получить подтверждённые авторские сведения; обновить описание PR ссылкой на эту регистрацию без слияния. Исправный PDF и научные тесты не повторять.\n\nЖурнал 24.11.2026 · BT26-R15-EXEC-20261124-10 · источник: реальные журналы текущего run, реестры и отзывы #7122631239/#7123877180 · технические исправления выполнены, отправка не разрешена, запись освобождена.\n'
    (ROOT/'docs/STATUS.md').write_text(status,encoding='utf-8')
    paths=['docs/STATUS.md']+['deliverables/r15/'+n for n in ('publication.json','build-receipt.json','release-status.json','SHA256.json')]
    final=commit(paths,'Issue #5 R1.5: сохранить фактическую доставку и освободить запись исполнителя',expected)
    put(OUT/'final-registration.json',dict(metadata_sha=final,**pub))
    print('FINAL_REGISTRATION_SHA',final,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('prepare','inspect','register'))
    {'prepare':prepare,'inspect':inspect,'register':register}[p.parse_args().stage]()
