"""Build independently authorized R1.5 components, NOT a replacement article.
No simulation, bootstrap, model edits or claims that the unread Word was reviewed.
"""
from pathlib import Path
import argparse, copy, hashlib, json, os, re, shutil, subprocess, tempfile, zipfile
from lxml import etree

ROOT=Path(__file__).resolve().parents[1]
BASE='ccf54fb8774f33ba7a82b05afe88dd2169d68ef1'
SRC=ROOT/'article/rework_round3'
OUT=ROOT/'results/r15-components'
D=OUT/'delivery'
NAMES=['C01_environment','C02_verification','C03_future_reassignment']
CAPTIONS=[
 ('C01. Реализованная среда: путь сообщения, шесть составляющих задержки и место потери.', 'Implemented environment: the message path, six latency components and the loss location.'),
 ('C02. Совместная проверка задержки и потерь. Недостаточность данных — отдельный исход; независимое подтверждение в текущем опыте не выполнялось.', 'Joint latency and loss assessment. Insufficient evidence is a separate outcome; independent confirmation was not performed in the reported experiment.'),
 ('C03. Будущая интеграция переразмещения. Реализованная среда показана сплошной рамкой; прогноз, выбор, применение и обратная связь — проектируемые части.', 'Proposed reassignment integration. The implemented environment has a solid boundary; prediction, selection, application and feedback are planned components.')]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
CHECKS=[]

def ensure_style(doc,name):
 from docx.enum.style import WD_STYLE_TYPE
 key=name.replace(' ','').casefold()
 for st in doc.styles:
  if st.style_id.replace(' ','').casefold()==key:
   st.name=name
   return st
 return doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(args, cwd=ROOT, name=None, timeout=240):
 r=subprocess.run(list(map(str,args)),cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
 if name:(OUT/'logs').mkdir(parents=True,exist_ok=True);(OUT/'logs'/name).write_bytes(r.stdout)
 if r.returncode:raise RuntimeError(str(args[0])+' failed: '+r.stdout.decode(errors='replace')[-4000:])
 return r.stdout

def require(ok,name):
 CHECKS.append({'check':name,'pass':bool(ok)})
 if not ok:raise AssertionError(name)

def graph(path):
 obj=json.loads(run(['dot','-Tjson',path]))
 names={o['_gvid']:o['name'] for o in obj['objects'] if '_gvid' in o}
 edges={(names[e['tail']],names[e['head']]) for e in obj.get('edges',[])}
 return obj,edges

def reachable(edges,a,b):
 todo=[a];seen=set()
 while todo:
  u=todo.pop()
  if u==b:return True
  if u not in seen:seen.add(u);todo += [v for x,v in edges if x==u]
 return False

def figures():
 import fitz
 fig=D/'figures';fig.mkdir(parents=True,exist_ok=True)
 graphs=[]
 for name in NAMES:
  source=SRC/(name+'.dot');obj,edges=graph(source);graphs.append((obj,edges))
  if (fig/source.name).exists():require(sha(fig/source.name)==sha(source),name+': restored vector source is unchanged')
  shutil.copy2(source,fig/source.name)
  for fmt in ('svg','pdf','png'):
   if not (fig/(name+'.'+fmt)).exists():run(['dot','-T'+fmt,source,'-o',fig/(name+'.'+fmt)],name=name+'-'+fmt+'.log')
  svg=etree.parse(str(fig/(name+'.svg')))
  require(not svg.xpath('//*[local-name()="image"]'),name+': SVG contains no raster image')
  with fitz.open(fig/(name+'.pdf')) as doc:
   require(len(doc)==1 and len(doc[0].get_images())==0,name+': PDF is one-page vector')
   require(len(doc[0].get_drawings())>0 and len(doc[0].get_text())>100,name+': PDF has vector paths and text')
   if not (fig/(name+'-preview.png')).exists():doc[0].get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(fig/(name+'-preview.png'))
   if not (fig/(name+'-7x.png')).exists():doc[0].get_pixmap(matrix=fitz.Matrix(7,7),alpha=False).save(fig/(name+'-7x.png'))
  leaves=[o for o in obj['objects'] if 'pos' in o and o.get('shape')!='plaintext']
  overlaps=[]
  for i,a in enumerate(leaves):
   ax,ay=map(float,a['pos'].split(','));aw,ah=float(a['width'])*72,float(a['height'])*72
   for b in leaves[i+1:]:
    bx,by=map(float,b['pos'].split(','));bw,bh=float(b['width'])*72,float(b['height'])*72
    if abs(ax-bx)<(aw+bw)/2-.1 and abs(ay-by)<(ah+bh)/2-.1:overlaps.append([a['name'],b['name']])
  require(not overlaps,name+': leaf node bounding boxes do not overlap')
  put(fig/(name+'-layout.json'),obj)
 e=graphs[0][1]
 stages=['edge_stage','ingress','wait_fog','service_fog','egress','cloud']
 require(all(reachable(e,a,b) for a,b in zip(stages,stages[1:])),'C01: six stages in order')
 require(not any(a=='lost' for a,b in e if b!='note'),'C01: loss has no continuation stage')
 e=graphs[1][1]
 require(not reachable(e,'insufficient','confirmation'),'C02: insufficiency cannot reach confirmation')
 require(not reachable(e,'unacceptable','confirmation'),'C02: rejection cannot reach confirmation')
 require(reachable(e,'acceptable','freeze_candidate') and ('freeze_candidate','confirmation') in e,'C02: confirmation follows frozen acceptable candidate')
 require(reachable(e,'pilot_ok','insufficient') and reachable(e,'prerequisites','insufficient'),'C02: preliminary failure remains insufficient')
 e=graphs[2][1]
 require(all((n,'adapter') in e for n in ('config_est','overflow_est','failure_est')),'C03: all three external estimators feed adapter')
 require(('adapter','m21') in e and ('m21','baseline') in e and ('m21','ordinal') in e,'C03: applicability and both modes explicit')
 require(all((n,'m22') in e for n in ('task_graph','partition','previous','limits')),'C03: four task inputs explicit')
 require(('any_plan','no_plan') in e and not any(a=='no_plan' for a,b in e),'C03: not-found result is terminal')
 require(('m23','m21') in e and ('m23','plan') in e,'C03: M2.3 can keep or repeat')
 require(('plan','application') in e and ('application','environment') in e,'C03: application separate from selection')
 for name,bad in [('negative: insufficiency arrow',graphs[1][1]|{('insufficient','confirmation')}),('negative: rejected arrow',graphs[1][1]|{('unacceptable','confirmation')})]:
  source='insufficient' if 'insufficiency' in name else 'unacceptable'
  require(reachable(bad,source,'confirmation'),name+' detected')
 require(not all((n,'m22') in (graphs[2][1]-{('partition','m22')}) for n in ('task_graph','partition','previous','limits')),'negative: missing partition detected')
 require(any(a=='no_plan' for a,b in graphs[2][1]|{('no_plan','application')}),'negative: false application from not-found detected')


def style_docx(path, red_all=False):
 from docx import Document
 from docx.shared import Pt, Cm, RGBColor
 from docx.oxml import OxmlElement
 from docx.oxml.ns import qn
 doc=Document(path)
 for sec in doc.sections:
  sec.page_width=Cm(21);sec.page_height=Cm(29.7)
  sec.top_margin=sec.bottom_margin=Cm(1.8);sec.left_margin=sec.right_margin=Cm(2)
 for name in ('Normal','Body Text'):
  st=ensure_style(doc,name);st.font.name='Times New Roman';st.font.size=Pt(11.5)
  st.paragraph_format.space_after=Pt(5);st.paragraph_format.line_spacing=1.1
 for name in ('Heading 1','Heading 2','Heading 3'):
  st=ensure_style(doc,name);st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0);st.font.size=Pt(14 if name=='Heading 1' else 12)
  st.paragraph_format.keep_with_next=True
 for p in doc.paragraphs:
  if '[ДЛЯ АВТОРА' in p.text:
   for r in p.runs:r.font.color.rgb=RGBColor(192,0,0)
  p.paragraph_format.widow_control=True
 if red_all:
  for r in doc.element.xpath('//w:r|//m:r'):
   rp=r.find(qn('w:rPr'))
   if rp is None:rp=OxmlElement('w:rPr');r.insert(0,rp)
   col=rp.find(qn('w:color'))
   if col is None:col=OxmlElement('w:color');rp.append(col)
   col.set(qn('w:val'),'C00000')
 doc.save(path)


def add_figures(path):
 from docx import Document
 from docx.shared import Inches,Pt,Cm
 from docx.enum.section import WD_SECTION_START,WD_ORIENT
 from PIL import Image
 doc=Document(path)
 for name,(ru,en) in zip(NAMES,CAPTIONS):
  sec=doc.add_section(WD_SECTION_START.NEW_PAGE)
  sec.orientation=WD_ORIENT.LANDSCAPE if name.startswith('C03') else WD_ORIENT.PORTRAIT
  sec.page_width=Cm(29.7 if name.startswith('C03') else 21);sec.page_height=Cm(21 if name.startswith('C03') else 29.7)
  sec.top_margin=sec.bottom_margin=Cm(1.5);sec.left_margin=sec.right_margin=Cm(1.5)
  heading=doc.add_paragraph(ru.split('.')[0]+'. Схема');heading.style=ensure_style(doc,'Heading 1')
  image=D/'figures'/(name+'-preview.png')
  with Image.open(image) as im:w,h=im.size
  maxw=(sec.page_width-sec.left_margin-sec.right_margin)/914400
  maxh=(sec.page_height-sec.top_margin-sec.bottom_margin)/914400-1.1
  width=min(maxw,maxh*w/h)
  doc.add_picture(str(image),width=Inches(width))
  p=doc.add_paragraph(ru);p.paragraph_format.space_after=Pt(3)
  p=doc.add_paragraph(en);p.paragraph_format.space_after=Pt(0)
  for r in p.runs:r.italic=True;r.font.size=Pt(10)
 doc.save(path)


def embed_svg(path):
 """Keep PNG fallback for LibreOffice; include vector SVG for supporting Word."""
 ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
 relns='http://schemas.openxmlformats.org/package/2006/relationships'
 with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
 root=etree.fromstring(files['word/document.xml']);rels=etree.fromstring(files['word/_rels/document.xml.rels']);types=etree.fromstring(files['[Content_Types].xml'])
 blips=root.xpath('//a:blip',namespaces=ns)
 require(len(blips)==3,'Word: three figure previews')
 for idx,(blip,name) in enumerate(zip(blips,NAMES),1):
  rid='rIdVector'+str(idx)
  etree.SubElement(rels,'{'+relns+'}Relationship',Id=rid,Type=ns['r']+'/image',Target='media/'+name+'.svg')
  files['word/media/'+name+'.svg']=(D/'figures'/(name+'.svg')).read_bytes()
  extlst=etree.SubElement(blip,'{'+ns['a']+'}extLst');ext=etree.SubElement(extlst,'{'+ns['a']+'}ext',uri='{96DAC541-7B7A-43D3-8B79-37D633B846F1}')
  etree.SubElement(ext,'{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip',{'{'+ns['r']+'}embed':rid})
 if not any(x.get('Extension')=='svg' for x in types):etree.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Default',Extension='svg',ContentType='image/svg+xml')
 for name,tree in [('word/document.xml',root),('word/_rels/document.xml.rels',rels),('[Content_Types].xml',types)]:files[name]=etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in files.items():z.writestr(name,data)


def documents():
 import fitz
 text=(SRC/'section6.md').read_text()
 clean=D/'FEFC_R15_Раздел6_и_схемы.docx';marked=D/'FEFC_R15_Раздел6_красные_изменения.docx'
 run(['pandoc',SRC/'section6.md','--from=markdown','--to=docx','-M','lang=ru-RU','-o',clean],name='pandoc-docx.log')
 style_docx(clean);add_figures(clean)
 shutil.copy2(clean,marked);style_docx(marked,True)
 # restore section page sizes after styling the marked copy
 from docx import Document
 a,b=Document(clean),Document(marked)
 for x,y in zip(a.sections,b.sections):
  y.orientation=x.orientation;y.page_width=x.page_width;y.page_height=x.page_height
  y.top_margin=x.top_margin;y.bottom_margin=x.bottom_margin;y.left_margin=x.left_margin;y.right_margin=x.right_margin
 b.save(marked)
 for p in (clean,marked):embed_svg(p)
 with zipfile.ZipFile(clean) as z:
  xml=etree.fromstring(z.read('word/document.xml'));math=xml.xpath('//m:oMath',namespaces=NS)
  require(len(math)==len(re.findall(r'\$\$.*?\$\$|\$[^$\n]+\$',text,re.S)),'Word: all source formulas are native OMML, not images')
  require(len([n for n in z.namelist() if n.endswith('.svg')])==3,'Word: SVG originals embedded with PNG fallbacks')
  math_text=[''.join(m.itertext()) for m in math]
 with zipfile.ZipFile(marked) as z:
  xml=etree.fromstring(z.read('word/document.xml'))
  require([''.join(m.itertext()) for m in xml.xpath('//m:oMath',namespaces=NS)]==math_text,'Marked Word: math content unchanged')
  require(len(xml.xpath('//w:color[@w:val="C00000"]',namespaces=NS))>30,'Marked Word: new text in red')
 letter=D/'FEFC_R15_Сопроводительное_письмо.docx'
 run(['pandoc',ROOT/'submission/cover_letter.md','--to=docx','-M','lang=ru-RU','-o',letter],name='pandoc-letter.log');style_docx(letter)
 author=json.loads((ROOT/'submission/author_metadata.json').read_text())
 sheet='# Сведения об авторах\n\n'
 for i,person in enumerate(author['authors_in_order'],1):
  sheet+=f"## {i}. {person['ru']}\n\n{person['en']}\n\n{author['affiliation_ru']}.\n\n{author['biography_ru_for_each']}.\n\n{author['biography_en_for_each']}.\n\n[ДЛЯ АВТОРА: ORCID при наличии; фотография и право её использования.]\n\n"
 sheet+=f"Контактный автор: {author['corresponding_author']}, {author['correspondence_email']}.\n\n{author['funding_statement_ru']}.\n"
 (D/'author_fields.md').write_text(sheet)
 run(['pandoc',D/'author_fields.md','--to=docx','-o',D/'FEFC_R15_Авторские_сведения.docx'],name='pandoc-authors.log');style_docx(D/'FEFC_R15_Авторские_сведения.docx')
 pdfdir=D/'word_pdf';pdfdir.mkdir(exist_ok=True)
 run(['libreoffice','-env:UserInstallation=file:///tmp/fefc-r15-components-lo','--headless','--convert-to','pdf','--outdir',pdfdir,*D.glob('*.docx')],name='libreoffice.log',timeout=240)
 pages=D/'pages';pages.mkdir(exist_ok=True);ledger=[]
 for p in sorted(pdfdir.glob('*.pdf')):
  with fitz.open(p) as pdf:
   require(len(pdf)>0,p.name+': rendered PDF exists')
   alltext='\n'.join(pg.get_text() for pg in pdf)
   require('Error! Reference' not in alltext,p.name+': no broken reference field')
   for i,pg in enumerate(pdf):
    dst=pages/(p.stem+f'-{i+1:02}.png');pg.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).save(dst)
    ledger.append({'file':str(p.relative_to(D)),'page':i+1,'sha256':sha(p),'text_characters':len(pg.get_text()),'visual_review':'NOT_PERFORMED_BY_EXECUTOR'})
 require(len(list(pdfdir.glob('*.pdf')))==4,'Four Word documents rendered')
 put(D/'page-review.json',ledger)
 # A synchronized LaTeX component, not the unread complete article.
 texdir=D/'latex';texdir.mkdir(exist_ok=True)
 body=run(['pandoc',SRC/'section6.md','--from=markdown','--to=latex']).decode()
 body=body.replace('{6. Развитие','{Развитие').replace('{6.1. Задача','{Задача').replace('{6.2. От наблюдений','{От наблюдений').replace('{6.3. Обновление','{Обновление')
 (texdir/'section6_body.tex').write_text(body)
 shutil.copy2(ROOT/'article/psta.cls',texdir/'psta.cls');shutil.copytree(ROOT/'article/psta',texdir/'psta',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.ttf','*.otf','*.pfb','*.tfm','*.vf','*.afm','*.enc','*.woff*'))
 tex=r'''\documentclass{psta}
\usepackage{graphicx}
\usepackage{longtable}
\usepackage{booktabs}
\providecommand{\tightlist}{}
\Russian
\title{Развитие среды: переразмещение с учётом прогноза}
\begin{document}\maketitle
\setcounter{section}{5}
\input{section6_body}
\end{document}
'''
 (texdir/'section6_review.tex').write_text(tex)
 for i in range(3):run(['pdflatex','-interaction=nonstopmode','-halt-on-error','section6_review.tex'],cwd=texdir,name=f'psta-{i+1}.log')
 with fitz.open(texdir/'section6_review.pdf') as p:require(len(p)>0,'PSTA component PDF compiled')
 for f in texdir.glob('*'):
  if f.suffix in ('.aux','.log','.out','.toc'):f.unlink()
 put(D/'document-check.json',{'omml_objects':len(math_text),'word_documents':4,'pdfs_from_word':4,'whole_article_created':False,'input_word_read':False,'exact_32_comments_processed':False})


def records():
 scope='''# Независимые компоненты редакционной переработки R1.5

Это законченный подэтап, а НЕ новая полная редакция статьи. Полученный Word внутри ZIP в данном ходе недоступен; 32 примечания и реестр31правки не прочитаны и не объявлены обработанными. Прежний main.tex не подменяет эту основу и не изменяется.

Содержимое: новая редакция раздела6; отдельная красная копия; три схемы C01–C03 (редактируемые DOT/SVG и векторные PDF); PDF из тех же Word; LaTeX раздела6; обновлённые письмо и авторские сведения; предметный реестр.
Красная копия выделяет весь заново написанный раздел и подписи относительно репозиторного раздела6, НЕ является сравнением с непрочитанным авторским DOCX. Формулы — OMML. В Word встроены SVG с PNG-резервом для совместимости; отдельные SVG/PDF не содержат растра.

Основания: #7131272024 — полное задание на независимые схемы; #7132932227 — прямое разрешение продолжить независимые части и точная поддержка; #7130900462 — имена, порядок, ЮНЦ РАН и справки. Научные критерии сверены с article/main.tex и v2/code/bt26/search.py в ccf54fb8774f33ba7a82b05afe88dd2169d68ef1. Старый v2 используется только как эталон критерия, не как новый эксперимент.

Сокращённый объём уже согласован. Новые опыты, прогнозы, обучение, bootstrap не запускались. Полная новая статья требует точной Word-основы; повторно согласовывать известных авторов, контакт или поддержку не нужно.

Сборка и проверки выполняются GitHub Actions. Отрисовка PDF/PNG и проверка геометрии НЕ означают личного визуального просмотра. Технический статус и границы проверки — receipt.json. Не отправлять в редакцию как полную статью.
'''
 (D/'README.md').write_text(scope)
 shutil.copy2(SRC/'section6.md',D/'section6.md')
 shutil.copy2(ROOT/'submission/cover_letter.md',D/'cover_letter.md')
 shutil.copy2(ROOT/'submission/author_metadata.json',D/'author_metadata.json')
 register='''# Реестр выполненных независимых правок

|Место|Было|Проблема|Новая редакция / статус|
|---|---|---|---|
|§6.1|Общий рассказ об интеграции|Не различались конфигурирование, выбор и применение|Новая последовательность: входы → целые подграфы → проверка → критерий → отдельный результат; выполнено|
|§6.1, критерий|Формула (R,T,N,id)|Требовалось объяснить каждую величину и минимакс|Формула сохранена; пояснены порядок и базовый (T,N,id); выполнено|
|§6.2|Три оценивателя без явного интерфейса|Метрики среды могли читаться как команды узлов|Добавлены ID/время/окно, три разные цели, адаптер и калибровка; выполнено|
|§6.3|Выбор и применение в одной цепочке|Могло восприниматься как реализованный контроллер|Применение и обратная связь вынесены в будущий контур; выполнено|
|C01|Пять ресурсных блоков|Не были видны шесть составляющих задержки и условие потери|Шесть стадий; отдельный выход потери при занятом Fog и полном буфере; выполнено|
|C02|Кандидат или недостаточность → подтверждение|Недостаточность ошибочно вела к подтверждению|Три исхода; подтверждение только после фиксации кандидата, пунктиром; выполнено|
|C03|Линейная цепочка прогноз→поиск→выбор|Не показаны входы, базовый режим, М2.3 и применение|Полный проектируемый контур отдельно от реализованной среды; выполнено|
|Письмо|Известные ФИО/поддержка оставались вопросами|Повторное согласование уже принятых решений|Перенесены три ФИО, ЮНЦ РАН, контакт и точная формулировка ГЗ; выполнено|
|Авторские поля|Неизвестные ORCID, фото, согласия|Нет подтверждённых данных/прав|Сохранены красными; требует автора|
|Входная Word-копия|32 примечания, красные фрагменты|В данном ходе не читается ZIP; отдельная выгрузка не получена|Не обработано; источник не подменён|
|Полная статья и 31правка|Последняя авторская Word-основа|Нельзя молча заменить её репозиторной версией|Не завершено; этот пакет содержит только разрешённые независимые компоненты|
'''
 (D/'Реестр_правок.md').write_text(register)
 put(D/'receipt.json',{'source_sha':os.environ.get('COMPONENT_SOURCE_SHA',os.environ.get('GITHUB_SHA')),'base_sha':BASE,'execution':'GitHub Actions; Graphviz; pandoc; LibreOffice; pdflatex','checks':CHECKS,'checks_passed':sum(x['pass'] for x in CHECKS),'simulation_executed':False,'bootstrap_recomputed':False,'notebooks_executed':False,'input_word_read':False,'whole_article_created':False,'visual_review':'NOT_PERFORMED_BY_EXECUTOR','ready_to_submit':False,'protected_paths_unchanged':True})


def build():
 OUT.mkdir(parents=True,exist_ok=True);D.mkdir(exist_ok=True)
 run(['git','diff','--exit-code',BASE,'HEAD','--','article/main.tex','v2','efc','docs/Журнал_проверок_Perplexity.md','results/r14/article_evidence.json','results/r15/conditional_analysis.json'],name='protected-paths.log')
 figures();documents();records()
 forbidden={'.ttf','.otf','.pfb','.pfa','.afm','.tfm','.vf','.woff','.woff2','.enc'}
 require(not any(p.suffix.lower() in forbidden for p in D.rglob('*') if p.is_file()),'No font files distributed')
 put(D/'SHA256.json',{p.relative_to(D).as_posix():sha(p) for p in sorted(D.rglob('*')) if p.is_file() and p.name!='SHA256.json'})
 with zipfile.ZipFile(D/'FEFC_R15_Раздел6_и_три_схемы.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(D.rglob('*')):
   if p.is_file() and p.suffix!='.zip' and 'pages' not in p.parts and not p.name.endswith('-7x.png'):z.write(p,p.relative_to(D))
 print('COMPONENT_RECEIPT',json.dumps(json.loads((D/'receipt.json').read_text()),ensure_ascii=False),flush=True)


def publish():
 branch='refs/heads/night/fefc-v3';expected=os.environ.get('COMPONENT_SOURCE_SHA',os.environ['GITHUB_SHA'])
 git=lambda *a:run(['git',*a]).decode().strip()
 if git('ls-remote','origin',branch).split()[0]!=expected:raise RuntimeError('HEAD changed; preserve artifact, do not overwrite')
 target=ROOT/'deliverables/r15-components';shutil.copytree(D,target,dirs_exist_ok=True)
 status=ROOT/'docs/STATUS.md'
 old=status.read_text()
 note='# STATUS — R1.5: независимые компоненты подготовлены\n\n24.11.2026. Текущий ход #7141330007. Только night/fefc-v3; PR#2 без слияния.\n\nНовое: article/rework_round3/section6.md, три исходника DOT и deliverables/r15-components. Новая редакция §6, 3 векторные схемы, две Word-копии компонента, PDF, LaTeX, письмо с подтверждёнными именами/контактом/поддержкой. Это НЕ полная новая статья; входная Word-копия/32 комментария остаются непрочитанными из-за ClientError локальной среды. Не заменять её старым main.tex.\n\nСборка и контрактные проверки выполнены в Actions '+os.environ.get('GITHUB_RUN_ID','')+'; детали receipt.json. Личный визуальный просмотр НЕ заявлен. Модель, критерии, результаты, main.tex, v2 и журнал Perplexity не менялись; новых серий/bootstrap/обучения нет.\n\nКонтакт и поддержка, три ФИО/порядок, ЮНЦ РАН и сокращённый объём согласованы; не спрашивать заново. Открыты точная Word-основа, полная переработка с 31правкой/32комментариями, визуальная проверка новых компонентов, ORCID/фото/права/личные согласия и ссылка НСКФ.\n\nТочка продолжения: читать README и реестр в deliverables/r15-components; после появления точной Word/TXT-выгрузки интегрировать компоненты в неё, не строить статью заново. Ход освобождает запись после сохранения артефактов; незавершённого commit/push нет. Готовность к отправке не объявлена.\n\nОЦЕНКА токенов: 3–6тыс. чтение приращения/доступ; 8–15тыс. содержание/схемы; 10–18тыс. сборка/проверки. Это ориентир, не биллинг.\n\nЖурнал:24.11.2026 · BT26-R15-REWORK-COMPONENTS-01 · решение: выполнить разрешённые независимые части без подмены обязательной Word-основы · источники:#7130900462/#7131272024/#7132932227 и фактические журналы Actions · статус: компоненты подготовлены, полная статья открыта.\n\n---\nПредыдущая запись сохранена ниже.\n\n'
 status.write_text(note+old)
 git('config','user.name','FEFC component executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
 git('add','--','deliverables/r15-components','docs/STATUS.md')
 names=run(['git','diff','--cached','--name-only','-z']).decode().split('\0')
 require(all(not p or p=='docs/STATUS.md' or p.startswith('deliverables/r15-components/') for p in names),'Publication contains only component artifacts and STATUS')
 if git('ls-remote','origin',branch).split()[0]!=expected:raise RuntimeError('HEAD lease lost before publication')
 git('commit','-m','Issue #5 п.5: сохранить собранные независимые компоненты и точку продолжения')
 git('push','origin','HEAD:'+branch)
 final=git('rev-parse','HEAD');put(OUT/'publication.json',{'delivery_sha':final,'source_sha':expected,'whole_article_created':False,'writer_released':True})
 print('COMPONENT_DELIVERY_SHA',final,flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['build','publish']);a=p.parse_args();globals()[a.stage]()
