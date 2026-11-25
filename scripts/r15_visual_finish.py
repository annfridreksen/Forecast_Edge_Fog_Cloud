"""Finish saved R1.5 documents: editable math, SVG labels, affected PDF, exact diff.
No model execution, resampling, literature lookup or author consent.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
import hashlib, importlib.util, json, os, re, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.r15_word_math_compat import repair_docx_math, mathematical_tokens, NS
BASE='fc50bb56800a2723aafd0d7e3d5d62b8976300bd';REF='refs/heads/night/fefc-v3'
INPUT=ROOT/'deliverables/r15-rework-v3';OUT=ROOT/'results/r15-visual';D=OUT/'delivery';S=D/'LaTeX'
FONT={'.ttf','.otf','.woff','.woff2','.pfb','.pfa','.afm','.tfm','.vf','.enc'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cmd(args,cwd=ROOT,name=None):
 r=subprocess.run(list(map(str,args)),cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
 if name:
  (OUT/'logs').mkdir(parents=True,exist_ok=True);(OUT/'logs'/name).write_bytes(r.stdout)
 if r.returncode:raise RuntimeError(str(args)+'\n'+r.stdout.decode(errors='replace')[-2200:])
 return r.stdout

def git(*a):return cmd(['git',*a]).decode().strip()
def commit(paths,message):
 expected=os.environ.get('VISUAL_HEAD',os.environ['GITHUB_SHA'])
 if git('ls-remote','origin',REF).split()[0]!=expected:raise RuntimeError('HEAD lease lost')
 git('config','user.name','FEFC editorial executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
 git('add','--',*paths)
 staged=cmd(['git','diff','--cached','--name-only','-z']).decode().split('\0')
 if any(p and not any(p==x or p.startswith(x+'/') for x in paths) for p in staged):raise RuntimeError('Unexpected staged file')
 if git('diff','--cached','--name-only'):
  git('commit','-m',message)
  if git('ls-remote','origin',REF).split()[0]!=expected:raise RuntimeError('HEAD changed before push')
  git('push','origin','HEAD:'+REF)
 value=git('rev-parse','HEAD');os.environ['VISUAL_HEAD']=value
 with open(os.environ['GITHUB_ENV'],'a') as f:f.write('VISUAL_HEAD='+value+'\n')
 return value

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 if git('ls-remote','origin',REF).split()[0]!=os.environ['GITHUB_SHA']:raise RuntimeError('HEAD moved')
 for n,h in json.loads((INPUT/'SHA256.json').read_text()).items():
  if sha(INPUT/n)!=h:raise ValueError('Saved input mismatch '+n)
 # Retain historical evidence; do not recalculate scientific results.
 shutil.copytree(INPUT,D,dirs_exist_ok=True)
 p=ROOT/'scripts/r15_full_rework.py';text=p.read_text()
 anchor=" red=D/'Статья_FEFC_R15_v3_красные_изменения.docx';shutil.copy2(p,red);style_word(red,True)"
 replacement=anchor+"\n from scripts.r15_word_math_compat import repair_docx_math\n for document in (p,red):repair_docx_math(document)"
 if replacement not in text:
  if text.count(anchor)!=1:raise ValueError('Word generator anchor changed')
  text=text.replace(anchor,replacement);p.write_text(text)
 mathsha=commit(['scripts/r15_full_rework.py'],'Issue #5 п.5: подключить сохранение OMML при экспорте обеих Word-копий')
 p=ROOT/'article/rework/figures/render_figures.py';text=p.read_text()
 old="node(f1,'note3',420,500,160,112,['Прочие очереди','не ограничены.','Все ожидания','включены в D','ровно один раз.'],kind='note',font=16)"
 new="node(f1,'note3',410,477,180,155,['К концу наблюдения:','незавершённое N_U','не является потерей.','Прочие очереди','не ограничены;','все ожидания входят','в D ровно один раз.'],kind='note',font=14.5)"
 if old in text:text=text.replace(old,new)
 elif new not in text:raise ValueError('C01 annotation anchor changed')
 lines=text.splitlines();matches=[(i,l) for i,l in enumerate(lines) if 'paint-order="stroke"' in l]
 if matches:
  if len(matches)!=1:raise ValueError('Unexpected SVG label renderer')
  i,line=matches[0]
  back=line.replace('fill="#111"','fill="white"').replace(' paint-order="stroke"',' aria-hidden="true"')
  front=line.replace(' stroke="white" stroke-width="3" paint-order="stroke"','')
  lines[i]=back+'\n'+front
 p.write_text('\n'.join(lines)+'\n')
 status=ROOT/'docs/STATUS.md';status.write_text('# STATUS — R1.5: исправление отображения, работа активна\n\n25.11.2026 · владелец #7145898717. Предыдущая проверка письма/ZIP принята, не повторяется без изменения. Исправляются только OMML/SVG и зависимые PDF. Run '+os.environ['GITHUB_RUN_ID']+'. Последнее замечание #7145835351 updated_at2026-11-24T22:07:31Z. Числа/тело статьи/научные данные не меняются. Следующий шаг: фактический экспорт, 9 формул и подписи, затронутый PSTA/ZIP, diff; затем личный просмотр страниц. Новая приёмка пока не присвоена.\n\n'+status.read_text())
 figsha=commit(['article/rework/figures/render_figures.py','docs/STATUS.md'],'Issue #5 п.3: вернуть SVG-подписи в Word и отделить незавершённое сообщение от потери')
 put(OUT/'source-commits.json',{'math_integration':mathsha,'svg_repair':figsha,'baseline':BASE})


def replace_media(path):
 ns={**NS,'a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','asvg':'http://schemas.microsoft.com/office/drawing/2016/SVG/main'}
 with ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
 root=E.fromstring(files['word/document.xml']);rels=E.fromstring(files['word/_rels/document.xml.rels']);lookup={e.get('Id'):e.get('Target') for e in rels}
 replaced=[]
 for blip in root.xpath('//a:blip[.//asvg:svgBlip]',namespaces=ns):
  vector=blip.find('.//{'+ns['asvg']+'}svgBlip');st='word/'+lookup[vector.get('{'+ns['r']+'}embed')]
  title=E.fromstring(files[st]).find('{http://www.w3.org/2000/svg}title').text
  files[st]=(S/'figures'/(title+'.svg')).read_bytes()
  pt='word/'+lookup[blip.get('{'+ns['r']+'}embed')];files[pt]=(S/'figures'/(title+'.png')).read_bytes();replaced.append(title)
 if len(replaced)!=3:raise ValueError('Three embedded vectors required')
 with ZipFile(path,'w',ZIP_DEFLATED) as z:
  for n,b in files.items():z.writestr(n,b)
 return replaced


def check_word_pdf(path):
 import fitz
 with fitz.open(path) as d:text='\n'.join(p.get_text() for p in d)
 flat=re.sub(r'\s+','',text)
 for glyph in ('λ','#','⌈','⌉','3689','K=B+1'):
  if glyph not in flat:raise ValueError('Missing rendered mathematics: '+glyph)
 if any(c in text for c in ('¿','�')):raise ValueError('Equation import error glyph')
 for n in range(1,10):
  if '('+str(n)+')' not in flat:raise ValueError('Missing rendered equation '+str(n))
 for label in ('РЕАЛИЗОВАННАЯ ИМИТАЦИОННАЯ СРЕДА','ПРОЕКТИРУЕМЫЕ ИНТЕРФЕЙСЫ И УПРАВЛЕНИЕ','ПОСЛЕДУЮЩИЙ ЭТАП — НЕ ВЫПОЛНЕН','Обратная связь — ещё не реализована','незавершённое N_U'):
  if re.sub(r'\s+','',label) not in flat:raise ValueError('Missing SVG label '+label)
 return {'file':Path(path).name,'nine_equation_numbers':True,'math_probe_glyphs':True,'branch_and_frame_labels':True,'pdf_sha256':sha(path)}


def finish():
 import fitz
 from scripts.r15_psta_readability import apply_saved, body_links_and_captions, verify_pdf
 import scripts.r15_full_rework as m
 component=cmd(['dpkg-query','-W','-f=${Status}','libreoffice-math']).decode()
 if component!='install ok installed':raise RuntimeError('LibreOffice Math is required')
 m.OUT=OUT;m.D=D;m.S=S;m.CHECKS=[]
 fg=S/'figures';shutil.copy2(ROOT/'article/rework/figures/render_figures.py',fg/'render_figures.py')
 cmd(['python',fg/'render_figures.py'],name='figure-source.log')
 cmd(['pdflatex','-interaction=nonstopmode','-halt-on-error','01_environment.tex'],fg,'C01-build.log')
 with fitz.open(fg/'01_environment.pdf') as d:d[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(fg/'01_environment.png')
 for name in ('02_verification','03_reassignment'):
  for ext in ('.pdf','.png','.tikz','.tex'):
   if sha(fg/(name+ext))!=sha(INPUT/'LaTeX/figures'/(name+ext)):raise ValueError('Unchanged vector changed: '+name+ext)
 edits=[]
 for path in D.glob('Статья*.docx'):
  edits.append(repair_docx_math(path));replace_media(path)
  if repair_docx_math(path)['compatibility_edits']!=0:raise ValueError('Math repair not idempotent')
  with ZipFile(path) as z,ZipFile(INPUT/path.name) as old:
   a=E.fromstring(z.read('word/document.xml'));b=E.fromstring(old.read('word/document.xml'))
   if a.xpath('//w:t/text()',namespaces=NS)!=b.xpath('//w:t/text()',namespaces=NS):raise ValueError('Article words changed')
   if [mathematical_tokens(e) for e in a.xpath('//m:oMath',namespaces=NS)]!=[mathematical_tokens(e) for e in b.xpath('//m:oMath',namespaces=NS)]:raise ValueError('Scientific mathematics changed')
   if len(a.xpath('//m:oMath',namespaces=NS))!=116 or len(a.xpath('//m:oMathPara',namespaces=NS))!=9:raise ValueError('OMML count changed')
 cmd(['libreoffice','-env:UserInstallation=file:///tmp/fefc-r15-visual','--headless','--convert-to','pdf','--outdir',D,*D.glob('Статья*.docx')],name='word-export.log')
 tests=[check_word_pdf(p) for p in D.glob('Статья*.pdf') if 'ПСТА' not in p.name]
 try:check_word_pdf(INPUT/'Статья_FEFC_R15_v3_для_чтения.pdf')
 except ValueError as exc:tests.append({'negative_original_bad_export':'REJECTED','reason':str(exc)})
 else:raise ValueError('Known missing-math baseline was not rejected')
 put(D/'word-render-checks.json',{'environment':component,'libreoffice':cmd(['libreoffice','--version']).decode().strip(),'edits':edits,'tests':tests,'simulation_executed':False,'bootstrap_recomputed':False,'text_rewritten':False})
 apply_saved(S)
 cmd(['sh','build.sh'],S,'psta-affected-build.log')
 log=(S/'main.log').read_text(errors='replace')
 if 'Overfull' in log or 'undefined references' in log:raise ValueError('TeX guard failed')
 shutil.copy2(S/'main.pdf',D/'Статья_FEFC_R15_v3_ПСТА.pdf')
 # Check actual shared validator; it includes explicit filenames and full letter.
 put(D/'psta-readability-checks.json',verify_pdf(S/'main.pdf'))
 put(D/'tex-warnings.json',[x for x in log.splitlines() if any(w in x for w in ('Warning','warning','Overfull','Underfull'))])
 shutil.copy2(S/'main.log',D/'checks/main.log')
 m.inspect_pdf();m.package()
 diff=Path(os.environ['DIFF_PDF_BIN']);baseline=ROOT/'deliverables/r15/article.pdf'
 if sha(baseline)!='5d0424d9c8f0b0af18f009e3b1549a764aaf5f1d490cfaaee0e07348911f596f':raise ValueError('Wrong exact comparison baseline')
 args=['xvfb-run','-a',str(diff),'--output-diff='+str(D/'Сравнение_с_R15_390b232a.pdf'),str(baseline),str(S/'main.pdf')]
 result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
 (OUT/'logs/diff-pdf.log').write_bytes(result.stdout)
 if result.returncode not in (0,1) or not (D/'Сравнение_с_R15_390b232a.pdf').exists():raise ValueError('diff-pdf failed')
 put(D/'comparison-provenance.json',{'method':'diff-pdf','exit':result.returncode,'baseline_delivery':'390b232a24b10d303b4f6646af8fc1414f7f182a','before_sha256':sha(baseline),'after_sha256':sha(S/'main.pdf'),'tool_commit':'092e6e31968cf28984c201a8c300f76f0020fbe4'})
 put(D/'visual-repair-receipt.json',{'source_sha':os.environ['VISUAL_HEAD'],'run_id':os.environ['GITHUB_RUN_ID'],'baseline':BASE,'checks':m.CHECKS,'word_math':'116 editable OMML including 9 display equations, same mathematical tokens','word_text_unchanged':True,'new_simulation':False,'new_bootstrap':False,'new_neural_training':False,'visual_review':'PENDING_PERSONAL_PAGE_REVIEW','ready_to_submit':False,'article_sent':False})
 for n in ('empirical-evidence.json','conditional-evidence.json','service-reference.json'):
  if sha(D/n)!=sha(INPUT/n):raise ValueError('Scientific evidence changed')
 if sha(S/'article_body.md')!=sha(INPUT/'LaTeX/article_body.md') or (S/'body.tex').read_text()!=body_links_and_captions((INPUT/'LaTeX/body.tex').read_text()):raise ValueError('Unexpected article body change')
 put(D/'SHA256.json',{p.relative_to(D).as_posix():sha(p) for p in sorted(D.rglob('*')) if p.is_file() and p.name not in ('SHA256.json','FEFC_R15_v3_полный_комплект.zip') and 'review-images' not in p.parts})
 with ZipFile(D/'FEFC_R15_v3_полный_комплект.zip','w',ZIP_DEFLATED) as z:
  for p in sorted(D.rglob('*')):
   if p.is_file() and p.name!='FEFC_R15_v3_полный_комплект.zip' and 'review-images' not in p.parts and p.suffix.lower() not in FONT:z.write(p,p.relative_to(D))
 print('VISUAL_REPAIR_COMPLETE',sha(D/'Статья_FEFC_R15_v3_ПСТА.pdf'),flush=True)


def publish():
 for p in D.rglob('*'):
  if p.is_file() and p.suffix.lower() in FONT:raise ValueError('Font distribution forbidden')
 shutil.copytree(D,INPUT,dirs_exist_ok=True)
 status=ROOT/'docs/STATUS.md';prior=status.read_text();status.write_text('# STATUS — R1.5: исправлен экспорт формул и SVG; нужен просмотр нового комплекта\n\n25.11.2026. Run '+os.environ['GITHUB_RUN_ID']+'; код '+os.environ['VISUAL_HEAD']+'. Файлы deliverables/r15-rework-v3/. Word OMML116/формул9 и слова сохранены; экспорт с LibreOffice Math. Подписи SVG исправлены без paint-order; C01 отличает незавершённое сообщение от потери. Word-render-checks, visual-repair-receipt, isolated-build и comparison-provenance содержат фактические проверки. PSTA пересобран из-за C01; исходный ZIP проверен в новой папке; новый diff-pdf к 390b232a. Наука не пересчитывалась.\n\nВладелец #7145898717 продолжает личный просмотр страниц/схем и содержательную сверку; не создавать второго писателя. Активный run после завершения отсутствует; новое визуальное согласие пока НЕ присвоено. Следующее действие: скачать артефакт этого run, сверить хеши и просмотреть все непринятые страницы обеих Word-PDF и ПСТА; записать результат. Последний обработанный comment7145835351 updated_at2026-11-24T22:07:31Z.\n\nОЦЕНКА токенов этапа: 10–18 тыс. диагностика/адресная правка, 5–10 тыс. проверка/регистрация; не биллинг.\n\n'+prior)
 result=commit(['deliverables/r15-rework-v3','docs/STATUS.md'],'Issue #5 п.5: предъявить Word с видимой математикой, векторы, PDF, ZIP и новое сравнение')
 put(OUT/'publication.json',{'delivery_sha':result,'article_sent':False,'writer':'7145898717; page review continues'})
 print('DELIVERY_SHA',result,flush=True)

if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ('prepare','finish','publish'):raise SystemExit('prepare|finish|publish')
 globals()[sys.argv[1]]()
