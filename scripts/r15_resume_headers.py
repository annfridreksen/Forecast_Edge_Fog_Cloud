"""Finish artifact 14957479386: change running titles only; never rerun science/Word/figures."""
from pathlib import Path
import ast, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, tempfile, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_r15_submission import download, unpack
BASE='30ac4c3efe1e0a7fd90ea697a051f11aa9816b3a'
REPO='annfridreksen/Forecast_Edge_Fog_Cloud'
REF='refs/heads/night/fefc-v3'
ARTIFACT=14957479386
DIGEST='c7ef328f16a5215d57ba1b67a6b6f9117f4bf8308cdfcef37e1b6ff12497ae99'
OUT=ROOT/'results/r15-header-resume'
SHORT={'ru':'Моделирование краевой и туманной среды','en':'Edge--fog simulation and reassignment'}
FONT={'.ttf','.otf','.pfb','.pfa','.afm','.tfm','.vf','.woff','.woff2','.enc'}
TEMP={'.aux','.log','.out','.toc','.brf','.blg','.fls'}
CHECKS=[]

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def remote():return git('ls-remote','origin',REF).split()[0]
def check(condition,name):
    CHECKS.append({'check':name,'pass':bool(condition)})
    put(OUT/'resume-checks.json',CHECKS)
    if not condition:raise AssertionError(name)
def commit(paths,message,expected):
    if remote()!=expected:raise RuntimeError('HEAD lease lost before staging')
    git('config','user.name','FEFC header-fix executor')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--',*paths)
    staged=[s for s in subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0') if s]
    if not staged or any(not any(s==p or s.startswith(p+'/') for p in paths) for s in staged):raise RuntimeError('Unexpected staged files')
    if remote()!=expected:raise RuntimeError('HEAD lease lost before commit')
    git('commit','-m',message)
    if remote()!=expected:raise RuntimeError('HEAD lease lost before push; local commit retained')
    git('push','origin','HEAD:'+REF)
    new=git('rev-parse','HEAD')
    if remote()!=new:raise RuntimeError('Remote differs after push')
    return new

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    expected=os.environ['GITHUB_SHA']
    check(remote()==expected,'Remote HEAD matches this sole resumed job')
    check(not git('status','--porcelain','--untracked-files=no'),'Fresh runner has no uncommitted tracked edits')
    (OUT/'runner-processes.txt').write_text(subprocess.check_output(['ps','-eo','pid,ppid,etime,args'],text=True))
    git('diff','--exit-code',BASE,'HEAD','--','article/rework','scripts/r15_full_rework.py','submission/author_metadata.json','article/r15-references.bbl')
    archive=OUT/'original-artifact.zip'
    download(f'https://api.github.com/repos/{REPO}/actions/artifacts/{ARTIFACT}/zip',archive,DIGEST,github=True)
    unpack(archive,OUT/'original')
    candidates=list((OUT/'original').rglob('delivery/LaTeX/main.tex'))
    check(len(candidates)==1,'Exact archived delivery uniquely located')
    snapshot=candidates[0].parents[2]
    for name in ('article_body.md','metadata.json','change_register.md'):
        check(sha(snapshot/'delivery/LaTeX'/name)==sha(ROOT/'article/rework'/name),'Archive/source compatibility: '+name)
    check(sha(snapshot/'delivery/LaTeX/figures/render_figures.py')==sha(ROOT/'article/rework/figures/render_figures.py'),'Archived figure source matches saved geometry')
    put(OUT/'restoration.json',{'artifact_id':ARTIFACT,'archive_sha256':sha(archive),'original_root':str(snapshot),'base_sha':BASE,'local_private_workspace':'UNOBSERVABLE_CLIENTERROR_NOT_CLEANED','scientific_rerun':False})
    p=ROOT/'scripts/r15_full_rework.py';old=p.read_text();text=old
    anchor=' title=lambda s:pandoc_text(s).strip()\n'
    check(text.count(anchor)==1,'Unique running-title generator anchor')
    text=text.replace(anchor,anchor+' short_titles='+repr(SHORT)+'\n',1)
    old_token=repr('\\title{')
    new_token=repr('\\title[')+'+title(short_titles[lang])+'+repr(']{')
    check(text.count(old_token)==1,'Only the two-language title-generation expression changes')
    text=text.replace(old_token,new_token,1)
    ast.parse(text)
    check("require('Overfull' not in log,'PSTA has no overfull boxes')" in text,'Overfull publication guard preserved')
    check(text.count("M['title_'+lang]")==old.count("M['title_'+lang]"),'Full approved titles remain metadata-derived')
    p.write_text(text,encoding='utf-8')
    status=ROOT/'docs/STATUS.md'
    previous=status.read_text()
    top='# STATUS — R1.5 v3: сохранённая редакция; исправление колонтитулов\n\n24.11.2026 · BT26-R15-HEADERS-01 · владелец #7143527125. Только night/fefc-v3 / PR#2 без слияния. Предыдущий текст ниже — историческая запись, не текущий блокер.\n\nПолная редакция уже сохранена в article/rework/. Архив14957479386/run45474268993 восстановлен с проверенным SHA256 '+DIGEST+'. Word и схемы не создаются заново. В scripts/r15_full_rework.py добавлены только короткие RU/EN title; полные утверждённые названия и контроль Overfull сохранены.\n\nЛокальная частная среда отвечает ClientError; её несохранённые изменения/процессы не объявляются отсутствующими и не изменяются. Свежий runner проверен отдельно. Текущий run '+os.environ['GITHUB_RUN_ID']+' повторяет только затронутую LaTeX-сборку и незавершённые проверки/упаковку. Во время run единственный писатель — этот ход. Научные данные, тело статьи, готовые Word/Word-PDF и векторы должны совпасть побайтово. Моделирование, литература, bootstrap и обучение не повторяются.\n\nОЦЕНКА токенов: чтение точного приращения/подготовка ограниченного маршрута 6–10 тыс.; диагностика/регистрация 2–4 тыс. Это оценка, не биллинг.\n\nСледующий шаг: фактический результат текущего run, файлы и проверки. Новая визуальная/научная приёмка не присвоена.\n\n---\nИсторическая запись до восстановления редакции:\n\n'
    status.write_text(top+previous,encoding='utf-8')
    new=commit(['scripts/r15_full_rework.py','docs/STATUS.md'],'Issue #5 п.5: короткие RU/EN колонтитулы без изменения полного названия; актуализировать STATUS',expected)
    with open(os.environ['GITHUB_ENV'],'a') as f:f.write('REWORK_SOURCE_SHA='+new+'\n')
    print('HEADER_FIX_SHA',new,flush=True)

def zip_folder(folder,target):
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob('*')):
            if not p.is_file() or p==target or p.suffix.lower() in TEMP or 'review-images' in p.parts:continue
            if p.suffix.lower() in FONT:raise ValueError('Font distribution prohibited')
            z.write(p,p.relative_to(folder).as_posix())

def finish():
    import pymupdf as fitz
    from lxml import etree
    import scripts.r15_full_rework as m
    restored=json.loads((OUT/'restoration.json').read_text());snapshot=Path(restored['original_root'])
    work=OUT/'work';shutil.copytree(snapshot,work,dirs_exist_ok=True)
    m.OUT=work;m.D=work/'delivery';m.S=m.D/'LaTeX'
    prior=json.loads((snapshot/'checks-in-progress.json').read_text())
    check([x['check'] for x in prior if not x['pass']]==['PSTA has no overfull boxes'],'Only recorded prior failure is the running-header overflow')
    put(m.D/'prior-checks-45474268993.json',prior)
    protected=[p for p in m.D.glob('*') if p.suffix=='.docx' or (p.suffix=='.pdf' and not p.name.endswith('_ПСТА.pdf'))]
    protected+=list(p for p in (m.S/'figures').rglob('*') if p.is_file())
    before={p.relative_to(m.D).as_posix():sha(p) for p in protected}
    check(len(list(m.D.glob('*.docx')))>=2,'Saved real Word copies present before continuation')
    M=json.loads((m.S/'metadata.json').read_text());A=json.loads((ROOT/'submission/author_metadata.json').read_text());body=(m.S/'article_body.md').read_text()
    keys=re.findall(r'\\Bibitem\{([^}]+)\}',(m.S/'references.bbl').read_text())
    check(len(keys)==27,'Retained BBL has 27 entries; not regenerated for the main build')
    figs=json.loads((m.S/'figures/diagrams.json').read_text())
    tree=ast.parse((ROOT/'article/rework/figures/render_figures.py').read_text())
    captions=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CAPTIONS' for t in n.targets))
    old_main=(m.S/'main.tex').read_text();old_body=(m.S/'body.tex').read_bytes()
    expected=old_main
    for lang in ('ru','en'):
        expected=expected.replace('\\title{','\\title['+m.pandoc_text(SHORT[lang]).strip()+']{',1)
    # Exercise the corrected generator, not a hand-edited generated file.
    warnings=m.latex(M,A,body,keys,figs,captions)
    check((m.S/'main.tex').read_text()==expected,'Generated main.tex differs ONLY by two optional short titles')
    check((m.S/'body.tex').read_bytes()==old_body,'Generated scientific body is byte-identical')
    check(all(sha(m.D/p)==h for p,h in before.items()),'All saved Word, Word-PDF and figure files reused byte-for-byte')
    check('Overfull' not in (m.S/'main.log').read_text(errors='replace'),'Real final PSTA log has no Overfull')
    with fitz.open(m.D/'Статья_FEFC_R15_v3_ПСТА.pdf') as pdf:
        with fitz.open(snapshot/'delivery/Статья_FEFC_R15_v3_ПСТА.pdf') as old:
            check(len(pdf)==len(old),'Page count unchanged by short running titles')
        header_rows=[]
        for i,page in enumerate(pdf):
            words=[w for w in page.get_text('words') if w[1]<55]
            header_rows.append({'page':i+1,'text':' '.join(w[4] for w in words),'outside':any(w[0]<-1 or w[2]>page.rect.width+1 for w in words)})
        check(not any(r['outside'] for r in header_rows),'Every page running header stays within PDF page bounds')
        put(m.D/'running-headers.json',header_rows)
    # These checks were not reached by the failed earlier run.
    ledger=m.inspect_pdf()
    for name in ('change_register.md',):shutil.copy2(ROOT/'article/rework'/name,m.D/'Реестр_правок_FEFC_R15_v3.md')
    shutil.copy2(ROOT/'submission/author_metadata.json',m.D/'author_metadata.json')
    sourcezip=m.D/'Исходники_ПСТА_v3.zip';zip_folder(m.S,sourcezip)
    with tempfile.TemporaryDirectory(prefix='fefc-shortheaders-check-') as tmp:
        fresh=unpack(sourcezip,Path(tmp)/'source')
        m.run(['sh','build.sh'],fresh,'isolated-source-build.log',timeout=180)
        check('Overfull' not in (fresh/'main.log').read_text(errors='replace'),'Isolated source ZIP retains Overfull guard result')
        with fitz.open(fresh/'main.pdf') as a,fitz.open(m.S/'main.pdf') as b:
            check(len(a)==len(b) and [p.get_text() for p in a]==[p.get_text() for p in b],'Unpacked source build has identical pages/text')
        check(sha(fresh/'references.bbl')==sha(m.S/'references.bbl'),'Isolated build regenerates identical actual BBL')
        isolated={'command':'sh build.sh','execution':'GitHub Actions / isolated directory','passed':True,'byte_identical_pdf':sha(fresh/'main.pdf')==sha(m.S/'main.pdf'),'pdf_sha256':sha(fresh/'main.pdf')}
    put(m.D/'isolated-build.json',isolated)
    check(all(sha(m.D/p)==h for p,h in before.items()),'Completed packaging does not modify preserved Word or vector files')
    omissions=[]
    for p in m.D.glob('*.docx'):
        with zipfile.ZipFile(p) as z:
            doc=etree.fromstring(z.read('word/document.xml'))
            omissions.append({'file':p.name,'sha256':sha(p),'omml_objects':len(doc.xpath('//m:oMath',namespaces=m.NS))})
    check(all('R'+f'{i:02}' in (ROOT/'article/rework/change_register.md').read_text() for i in range(1,32)),'Saved register retained, not rewritten')
    combined=CHECKS+m.CHECKS
    receipt={'source_sha':os.environ['REWORK_SOURCE_SHA'],'archived_source_sha':BASE,'restored_artifact':ARTIFACT,'restored_archive_sha256':DIGEST,'build_run':os.environ['GITHUB_RUN_ID'],'execution':'GitHub Actions / retained artifact + corrected generator / pdflatex / isolated BibTeX build','scope':'Running titles only; remaining build checks','new_checks':combined,'new_checks_passed':sum(x['pass'] for x in combined),'prior_successful_checks_reused':sum(x['pass'] for x in prior),'prior_failure_retained_in':'prior-checks-45474268993.json','preserved_files':before,'word_inventory':omissions,'sections':8,'references':27,'figures':3,'scientific_snapshot_requests':131,'simulation_executed':False,'bootstrap_recomputed':False,'word_regenerated':False,'figures_regenerated':False,'literature_search_repeated':False,'whole_article_created':True,'ready_to_submit':False,'new_binary_visually_accepted':False,'article_sent':False,'warnings':warnings,'local_private_workspace_observable':False}
    put(m.D/'receipt.json',receipt)
    (m.D/'README.md').write_text('# FEFC R1.5 v3 — завершение сохранённой сборки\n\nПродолжение artifact14957479386/run45474268993. Исправлены только короткие RU/EN колонтитулы генератора; полное название, текст восьми разделов, числа, Word-копии и три схемы сохранены. Word/Word-PDF/векторы побайтово совпадают с исходным архивом. PDF ПСТА пересобран; проверка Overfull включена и пройдена.\n\nЧитаемая и красная DOCX-копии, их PDF, PDF ПСТА, письмо, 27 источников, девять формул, SVG/PDF/TikZ и исходный ZIP приложены. Красная копия выделяет переработанные разделы, а не посимвольный Track Changes. Авторские незаполненные поля остаются красными.\n\nИзолированная сборка и машинные проверки — receipt.json/isolated-build.json. Новый личный визуальный просмотр не присвоен; прежняя приёмка PDF не переносится автоматически. Модель/данные/литература не пересчитывались. Письмо не подписано, статья не отправлена.\n',encoding='utf-8')
    (m.D/'HEADER_FIX.md').write_text('# Адресная правка колонтитулов\n\nБыло: title{полное название} в обеих языковых частях. Проблема: выход длинного колонтитула за границу страницы, реальный Overfull. Стало: title[короткое название]{то же полное название}.\n\nRU: '+SHORT['ru']+'\nEN: '+SHORT['en']+'\n\nИсправлен генератор scripts/r15_full_rework.py. Тело main.tex вне двух необязательных аргументов, body.tex, сохранённые Word/схемы совпадают с архивом; контроль Overfull сохранён.\n',encoding='utf-8')
    put(m.D/'SHA256.json',{p.relative_to(m.D).as_posix():sha(p) for p in sorted(m.D.rglob('*')) if p.is_file() and p.name!='SHA256.json' and p.suffix.lower() not in TEMP})
    zip_folder(m.D,m.D/'FEFC_R15_v3_полный_комплект.zip')
    put(OUT/'resume-result.json',{'status':'BUILD_CHECKS_PASS_VISUAL_ACCEPTANCE_OPEN','source_sha':os.environ['REWORK_SOURCE_SHA'],'checks_passed':receipt['new_checks_passed'],'files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(m.D.iterdir()) if p.is_file() and p.suffix in ('.pdf','.docx','.zip')],'warnings':warnings})
    print('HEADER_RESUME_RESULT', (OUT/'resume-result.json').read_text(),flush=True)

def publish():
    source=os.environ['REWORK_SOURCE_SHA']
    result=json.loads((OUT/'resume-result.json').read_text())
    if result['status']!='BUILD_CHECKS_PASS_VISUAL_ACCEPTANCE_OPEN':raise RuntimeError('Unfinished delivery')
    d=OUT/'work/delivery';target=ROOT/'deliverables/r15-rework-v3'
    for p in sorted(d.rglob('*')):
        if not p.is_file() or p.suffix.lower() in TEMP:continue
        if p.suffix.lower() in FONT:raise RuntimeError('Font in delivery')
        dest=target/p.relative_to(d);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes()!=p.read_bytes():raise RuntimeError('Different pre-existing delivery; retain both and review')
        shutil.copy2(p,dest)
    if remote()!=source:raise RuntimeError('HEAD changed; retain artifact without publication')
    status=ROOT/'docs/STATUS.md'
    text='# STATUS — R1.5 v3: колонтитулы исправлены; текущая сборка завершена\n\n24.11.2026 · BT26-R15-HEADERS-01 · источник '+source+' · run '+os.environ['GITHUB_RUN_ID']+'.\n\nКомплект: deliverables/r15-rework-v3/. Архив14957479386 восстановлен по SHA256. Исправлены только необязательные короткие RU/EN title в генераторе. Полные названия, тело статьи, Word/Word-PDF и векторы сохранены; побайтовое равенство переиспользованных файлов — receipt.json. Проверка Overfull сохранена; пройдена основная и изолированная сборка. Точные новые проверки и предупреждения — receipt.json, файлы/хеши — SHA256.json.\n\nНовых опытов, bootstrap, обучения, поиска литературы, генерации Word или схем нет. Прежний согласованный комплект не заменён. Локальные несохранённые изменения не доступны из-за ClientError и не затронуты. Новая визуальная/содержательная приёмка остаётся открытой; технические проверки не названы согласием рецензента. Незаполненные авторские поля красные. Статья не отправлена, письмо не подписано.\n\nЕдинственный ход #7143527125 завершён после успешного push; запись ОСВОБОЖДЕНА. PR#2 без слияния; main/v2/журнал Perplexity/модель/числа не изменены. Следующий шаг — адресный просмотр нового PDF и решение по оставшимся авторским полям, без новой переработки или повторов расчёта.\n\nОЦЕНКА токенов: чтение/маршрут 6–10тыс., исправление/проверка/регистрация 4–8тыс.; не биллинг.\n\nЖурнал 24.11.2026 · BT26-R15-HEADERS-01 · основания:#7143003375, архив14957479386, текущие журналы Actions · решение: завершить сохранённую сборку после правки колонтитулов · статус: технические проверки пройдены, новая приёмка открыта.\n\n---\nИстория предыдущей точки сохранена ниже:\n\n'
    status.write_text(text+status.read_text(),encoding='utf-8')
    final=commit(['deliverables/r15-rework-v3','docs/STATUS.md'],'Issue #5 п.5: предъявить сохранённые Word и PDF с исправленными колонтитулами',source)
    import urllib.request,urllib.parse
    checks=[]
    for f in result['files']:
        url=f'https://raw.githubusercontent.com/{REPO}/{final}/deliverables/r15-rework-v3/'+urllib.parse.quote(f['name'])
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FEFC-header-delivery'}),timeout=120) as r:data=r.read()
        if hashlib.sha256(data).hexdigest()!=f['sha256']:raise RuntimeError('Published bytes mismatch: '+f['name'])
        checks.append({**f,'url':url,'anonymous_download':'PASS'})
    put(OUT/'publication.json',{'source_sha':source,'delivery_sha':final,'run_id':os.environ['GITHUB_RUN_ID'],'files':checks,'writer_released':True,'ready_to_submit':False})
    print('HEADER_DELIVERY_SHA',final,flush=True)
    print('PUBLICATION',json.dumps(checks,ensure_ascii=False),flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','finish','publish']);args=parser.parse_args()
    globals()[args.stage]()
