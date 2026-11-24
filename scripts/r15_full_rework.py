"""Build the full restored editorial v3, not the independent-component draft.
Scientific data/model stay unchanged. Word formulas are native OMML. SVG/TikZ
share one recovered geometry. No newly claimed personal visual review.
"""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,math,os,re,shutil,subprocess,sys,tempfile,zipfile
from lxml import etree
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'article/rework';OUT=ROOT/'results/r15-rework-v3';D=OUT/'delivery';S=D/'LaTeX'
BASE='ccf54fb8774f33ba7a82b05afe88dd2169d68ef1'
FONT={'.ttf','.otf','.pfb','.pfa','.afm','.tfm','.vf','.woff','.woff2','.enc'}
CHECKS=[]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(args,cwd=ROOT,log=None,timeout=180,input=None):
 r=subprocess.run(list(map(str,args)),cwd=cwd,input=input,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
 if log:
  p=OUT/'logs'/log;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.stdout)
 if r.returncode:raise RuntimeError(str(args[0])+' failed: '+r.stdout.decode(errors='replace')[-2500:])
 return r.stdout

def require(ok,name):
 CHECKS.append({'check':name,'pass':bool(ok)})
 put(OUT/'checks-in-progress.json',CHECKS)
 if not ok:raise AssertionError(name)

def pandoc_text(text,target='latex'):
 return run(['pandoc','-f','markdown+tex_math_dollars','-t',target,'--wrap=none'],input=text.encode()).decode()

def prepare():
 D.mkdir(parents=True,exist_ok=True);S.mkdir(parents=True,exist_ok=True)
 for n in ('article_body.md','metadata.json','change_register.md'):shutil.copy2(SRC/n,S/n)
 M=json.loads((SRC/'metadata.json').read_text());A=json.loads((ROOT/'submission/author_metadata.json').read_text())
 body=(SRC/'article_body.md').read_text()
 run(['git','diff','--exit-code',BASE,'HEAD','--','efc','v2','colab','configs','article/main.tex','docs/Журнал_проверок_Perplexity.md','results/r14/article_evidence.json','results/r15/conditional_analysis.json','results/r15/service_reference.json'],log='scientific-protection.log')
 require(len(re.findall(r'^# [1-8]\. ',body,re.M))==8,'Eight source sections preserved')
 require(re.findall(r'\\qquad\(([0-9]+)\)',body)==list(map(str,range(1,10))),'Nine numbered source equations')
 require(all(body.count('@@FIG'+str(i)+'@@')==1 for i in range(1,4)),'Three source figure anchors')
 ev=json.loads((ROOT/'results/r14/article_evidence.json').read_text());cond=json.loads((ROOT/'results/r15/conditional_analysis.json').read_text())
 ni=[r['arrivals'] for r in cond['rows']]
 require(sum(ni)==1999801 and min(ni)==199114 and len(ni)==10,'Published cohort counts and minimum unchanged')
 require(ev['point']['p95_ms']==170.863296 and ev['counts']['requests']==131,'Frozen p95 and 131-request snapshot unchanged')
 require(ev['point']['dropped']==0 and ev['status']=='INSUFFICIENT_DATA','Original zero-loss bootstrap outcome unchanged')
 for text,names in [(body,['1 999 801','199 114','170,9','0,00185','151,0','0,986','127,2']), (M['abstract_en'],['1,999,801','199,114','170.9','0.00185','151.0'])]:
  require(all(x in text for x in names),'Displayed values occur consistently: '+names[2])
 require('не является p95' in body and 'не гарантирует ускорения' in body,'Plan time and future gains not confused with measured p95')
 require('не выполнялось' in M['abstract_ru'] and 'was not executed' in M['abstract_en'],'RU/EN both exclude executed forecast control')
 require(A['correspondence_email']=='jigulina@mail.ru' and A['corresponding_author']=='М. В. Орда-Жигулина','Approved contact not requested again')
 require('125011200147-2' in body,'Approved funding statement retained')
 for n in ('psta.cls',):shutil.copy2(ROOT/'article'/n,S/n)
 shutil.copytree(ROOT/'article/psta',S/'psta',dirs_exist_ok=True,ignore=lambda d,n:[x for x in n if Path(x).suffix.lower() in FONT])
 put(D/'source-recovery.json',{'source_sha':os.environ.get('REWORK_SOURCE_SHA',os.environ.get('GITHUB_SHA')),'input_basis':M['recovery'],'prior_read_comment':7133290317,'recovery_note':'Previous exact-source inspection and authored text are preserved in the execution record. Expired local DOCX/PDF bytes are not claimed recovered. This build creates new binaries from restored sources.','new_simulation':False,'new_bootstrap':False})
 for src,dst in [('results/r14/article_evidence.json','empirical-evidence.json'),('results/r15/conditional_analysis.json','conditional-evidence.json'),('results/r15/service_reference.json','service-reference.json')]:shutil.copy2(ROOT/src,D/dst)
 return M,A,body


def bibliography():
 native=(ROOT/'article/r15-references.tex').read_text()
 native,count=re.subn(r'\\RBibitem\{nskf\}.*?(?=\\Bibitem\{ifogsim\})','',native,flags=re.S)
 require(count==1,'Unconfirmed NSCF record removed as in the exact Word basis')
 native=native.replace('% R1.5 bibliography. Publication details for nskf remain unconfirmed.','% Reworked v3: 27 retained records; NSCF source question remains in text and letter.')
 (S/'references-native.tex').write_text(native)
 bib=(ROOT/'article/r15-references.bib').read_text()
 bib,n=re.subn(r'@\w+\{nskf,.*?(?=\n@\w+\{ifogsim,)','',bib,flags=re.S)
 require(n==1,'BIB removes the same unconfirmed record')
 (S/'references.bib').write_text(bib);shutil.copy2(ROOT/'article/psta-source-preserve.bst',S/'psta-source-preserve.bst')
 (S/'references.aux').write_text('\\relax\n\\citation{*}\n\\bibstyle{psta-source-preserve}\n\\bibdata{references}\n')
 run(['bibtex','references'],S,'bibtex.log')
 bbl=(S/'references.bbl').read_text();keys=re.findall(r'\\Bibitem\{([^}]+)\}',bbl)
 require(len(keys)==27 and 'nskf' not in keys,'27 real BBL records, NSCF not reintroduced')
 require('\\book Simulation Modeling and Analysis' in bbl and '\\isbn 978-0-07-340132-4' in bbl,'Law title and ISBN retained')
 paragraphs=[]
 for number,m in enumerate(re.finditer(r'\\Bibitem\{([^}]+)\}(.*?)(?=\\Bibitem|\\end\{thebibliography\})',native,re.S),1):
  fields=dict(re.findall(r'^\\(\w+) (.+)$',m[2],re.M));bits=[]
  for k,prefix in [('by',''),('paper',''),('book',''),('edition',''),('jour',''),('inbook',''),('serial',''),('vol','Vol. '),('issue','No. '),('publ',''),('yr',''),('pages','P. '),('isbn','ISBN '),('doi','DOI: '),('URL','URL: ')]:
   if k in fields:bits.append(prefix+fields[k]+'.')
  plain=run(['pandoc','-f','latex','-t','plain','--wrap=none'],input=' '.join(bits).encode()).decode().strip()
  paragraphs.append('\\['+str(number)+'] '+plain)
 return keys,'# Литература\n\n'+'\n\n'.join(paragraphs)


def figures():
 import fitz
 f=S/'figures';f.mkdir(exist_ok=True)
 shutil.copy2(SRC/'figures/render_figures.py',f/'render_figures.py')
 spec=importlib.util.spec_from_file_location('v3figures',f/'render_figures.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 put(f/'diagrams.json',mod.FIGS)
 for d in mod.FIGS:
  mod.render(d,f)
  if not (f/(d['name']+'.pdf')).exists():run(['pdflatex','-interaction=nonstopmode','-halt-on-error',d['name']+'.tex'],f,d['name']+'.log')
  with fitz.open(f/(d['name']+'.pdf')) as doc:
   require(len(doc)==1 and not doc[0].get_images(),d['name']+': actual PDF is vector')
   doc[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(f/(d['name']+'.png'))
   p=D/'review-images';p.mkdir(exist_ok=True)
   doc[0].get_pixmap(matrix=fitz.Matrix(7,7),alpha=False).save(p/(d['name']+'-7x.png'))
  require(not etree.parse(str(f/(d['name']+'.svg'))).xpath('//*[local-name()="image"]'),d['name']+': SVG contains no raster')
  require(all(0<=n['x'] and 0<=n['y'] and n['x']+n['w']<=d['width'] and n['y']+n['h']<=d['height'] for n in d['nodes']),d['name']+': node bounds within canvas')
  for p in f.glob(d['name']+'.*'):
   if p.suffix in ('.aux','.log'):p.unlink()
 edges=lambda d:{(e['start'],e['end']) for e in d['edges']}
 e=edges(mod.FIGS[1]);require(not any(x.startswith('insuff') for x,y in e),'C02: insufficiency has no outgoing edge')
 require(('freeze','confirm') in e and {x for x,y in e if y=='confirm'}=={'freeze'},'C02: only frozen candidate reaches confirmation')
 e=edges(mod.FIGS[2]);require(('m21','rankbase') in e and ('m21','rankforecast') in e,'C03: both ranking modes')
 require(not any(x=='no_plan' for x,y in e),'C03: not-found result does not apply a plan')
 require(('update','m21') in e and ('update','plan') in e and ('plan','apply') in e,'C03: retain/reselect and separate application')
 require(next(e for e in mod.FIGS[2]['edges'] if e['start']=='apply')['dashed'],'C03: feedback is proposed')
 require(not (not any(x.startswith('insuff') for x,y in edges(mod.FIGS[1])|{('insuff2','confirm')})),'Negative check: false insufficiency-confirmation edge rejected')
 return mod.FIGS,mod.CAPTIONS


def ensure_style(doc,name):
 from docx.enum.style import WD_STYLE_TYPE
 key=name.replace(' ','').casefold()
 for s in doc.styles:
  if s.style_id.replace(' ','').casefold()==key:return s
 return doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)


def style_word(path,red=False):
 from docx import Document
 from docx.shared import Cm,Pt,RGBColor
 from docx.enum.text import WD_ALIGN_PARAGRAPH
 from docx.oxml import OxmlElement
 from docx.oxml.ns import qn
 doc=Document(path);sec=doc.sections[0]
 sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=sec.bottom_margin=Cm(2);sec.left_margin=Cm(2.3);sec.right_margin=Cm(2)
 for st in doc.styles:
  if st.type==1:
   st.font.name='Times New Roman';st.font.size=Pt(11.5);st.font.color.rgb=RGBColor(0,0,0)
   st.paragraph_format.space_after=Pt(5);st.paragraph_format.line_spacing=1.08;st.paragraph_format.widow_control=True
 for name,size in [('Title',16),('Heading 1',14),('Heading 2',12.5),('Heading 3',12)]:
  st=ensure_style(doc,name);st.font.size=Pt(size);st.font.bold=True;st.paragraph_format.keep_with_next=True;st.paragraph_format.space_before=Pt(12);st.paragraph_format.space_after=Pt(6)
 for i,p in enumerate(doc.paragraphs):
  if i==0:p.style=ensure_style(doc,'Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  elif i<5:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  elif p.style.style_id.lower().startswith('heading'):pass
  else:p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
  if p.text.startswith(('Рисунок ','Таблица ')):
   p.paragraph_format.keep_with_next=True
   for r in p.runs:r.font.size=Pt(10.5)
  if p._p.xpath('.//w:drawing'):
   p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.paragraph_format.space_before=Pt(8)
  if '[ДЛЯ АВТОРА' in p.text or '[AUTHOR' in p.text:
   for r in p.runs:r.font.color.rgb=RGBColor(192,0,0)
 for tab in doc.tables:
  tab.autofit=False;nc=len(tab.columns)
  widths=([4.2,6.1,6.4] if nc==3 else ([2.8]+[1.9857]*7 if nc==8 else [9,7.7]))
  for no,row in enumerate(tab.rows):
   pr=row._tr.get_or_add_trPr();pr.append(OxmlElement('w:cantSplit'))
   if no==0:pr.append(OxmlElement('w:tblHeader'))
   for i,c in enumerate(row.cells):
    c.width=Cm(widths[i])
    for p in c.paragraphs:
     p.paragraph_format.line_spacing=1.02;p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(3)
     p.alignment=WD_ALIGN_PARAGRAPH.LEFT if i==0 or nc!=8 else WD_ALIGN_PARAGRAPH.RIGHT
     for r in p.runs:r.font.size=Pt(10);r.bold=(no==0)
  borders=OxmlElement('w:tblBorders')
  for side in ['top','bottom','insideH','left','right','insideV']:
   b=OxmlElement('w:'+side);b.set(qn('w:val'),'single' if side in ['top','bottom','insideH'] else 'nil');b.set(qn('w:sz'),'4');borders.append(b)
  tab._tbl.tblPr.append(borders)
 if red:
  active=False
  for el in doc.element.body:
   txt=''.join(el.xpath('.//w:t')) if False else ''.join(el.itertext())
   if el.tag==qn('w:p'):
    from docx.text.paragraph import Paragraph
    txt=Paragraph(el,doc._body).text
   if txt.startswith('1. Введение'):active=True
   if txt=='Литература':active=False
   if txt=='Extended summary':active=True
   if txt=='Сведения об авторах':active=False
   mark=active or txt.startswith(('Аннотация.','Abstract.'))
   if mark:
    for r in [v for v in el.iter() if v.tag in (qn('w:r'),qn('m:r'))]:
     rp=r.find(qn('w:rPr'))
     if rp is None:rp=OxmlElement('w:rPr');r.insert(0,rp)
     color=rp.find(qn('w:color'))
     if color is None:color=OxmlElement('w:color');rp.append(color)
     color.set(qn('w:val'),'C00000')
 footer=sec.footer.paragraphs[0];footer.clear();footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
 fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
 doc.core_properties.author='М. В. Орда-Жигулина; Д. В. Орда-Жигулина; А. С. Игнатенко'
 doc.core_properties.comments='Восстановленная редакция v3; научные данные не изменены. Красная копия выделяет переработанные разделы, не посимвольный Track Changes.'
 doc.save(path)


def embed_svg(path,figs):
 ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'};rn='http://schemas.openxmlformats.org/package/2006/relationships'
 with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
 root=etree.fromstring(files['word/document.xml']);rels=etree.fromstring(files['word/_rels/document.xml.rels']);types=etree.fromstring(files['[Content_Types].xml'])
 blips=root.xpath('//a:blip',namespaces=ns);require(len(blips)==3,'Word contains exactly three new figures')
 for i,(blip,d) in enumerate(zip(blips,figs),1):
  rid='rIdVector'+str(i);name=d['name']+'.svg';files['word/media/'+name]=(S/'figures'/name).read_bytes()
  etree.SubElement(rels,'{'+rn+'}Relationship',Id=rid,Type=ns['r']+'/image',Target='media/'+name)
  extlst=etree.SubElement(blip,'{'+ns['a']+'}extLst');ext=etree.SubElement(extlst,'{'+ns['a']+'}ext',uri='{96DAC541-7B7A-43D3-8B79-37D633B846F1}')
  etree.SubElement(ext,'{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip',{'{'+ns['r']+'}embed':rid})
 if not any(e.get('Extension')=='svg' for e in types):etree.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Default',Extension='svg',ContentType='image/svg+xml')
 for n,e in [('word/document.xml',root),('word/_rels/document.xml.rels',rels),('[Content_Types].xml',types)]:files[n]=etree.tostring(e,xml_declaration=True,encoding='UTF-8',standalone=True)
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in files.items():z.writestr(n,b)


def word(M,A,body,bibmd,figs,captions):
 md=body
 for i,(d,cap) in enumerate(zip(figs,captions),1):
  md=md.replace('@@FIG'+str(i)+'@@','![](figures/'+d['name']+'.png){width=14.5cm}\n\n**Рисунок '+str(i)+'. '+cap[0]+'**\n\n*'+cap[1]+'*')
 authors=A['authors_in_order']
 front='**'+M['title_ru']+'**\n\n**'+'; '.join(a['ru'] for a in authors)+'**\n\n'+A['affiliation_ru']+'.\n\n'+M['address_ru']+'.\n\n**Контактный автор:** М. В. Орда-Жигулина, jigulina@mail.ru.\n\nУДК '+M['udc']+'\n\n**Аннотация.** '+M['abstract_ru']+'\n\n**Ключевые слова:** '+M['keywords_ru']+'.\n\n'
 en='# '+M['title_en']+'\n\n**'+'; '.join(a['en'] for a in authors)+'**\n\n'+M['affiliation_en']+'.\n\n'+M['address_en']+'.\n\n**Corresponding author:** M. V. Orda-Zhigulina, jigulina@mail.ru.\n\n**Abstract.** '+M['abstract_en']+'\n\n**Keywords:** '+M['keywords_en']+'.\n\n# Extended summary\n\n'+M['extended_summary']
 bio='\n\n# Сведения об авторах\n\n'
 for a in authors:bio+='**'+a['ru']+'**\n\n'+A['biography_ru_for_each']+'.\n\n[ДЛЯ АВТОРА: ORCID при наличии; портрет и право публикации; дополнительные подтверждённые строки справки.]\n\n'
 bio+='[ДЛЯ АВТОРА: личное заявление о конфликте интересов, правах и согласии соавторов; не подписано исполнителем.]\n'
 reading=front+md+'\n\n'+bibmd+'\n\n'+en+bio
 (S/'reading.md').write_text(reading)
 p=D/'Статья_FEFC_R15_v3_для_чтения.docx'
 run(['pandoc','-f','markdown+tex_math_dollars','-t','docx','--standalone','reading.md','-o',p],S,'pandoc-reading.log');style_word(p);embed_svg(p,figs)
 red=D/'Статья_FEFC_R15_v3_красные_изменения.docx';shutil.copy2(p,red);style_word(red,True)
 with zipfile.ZipFile(p) as z:
  root=etree.fromstring(z.read('word/document.xml'));count=len(root.xpath('//m:oMath',namespaces=NS));display=len(root.xpath('//m:oMathPara',namespaces=NS))
  require(count>=60 and display==9,'Native Word math: all nine display equations and inline OMML')
  content=''.join(root.itertext());require('подтвердить М. В. Орда-Жигулину' not in content,'Obsolete contact question removed')
 with zipfile.ZipFile(red) as z:
  rr=etree.fromstring(z.read('word/document.xml'))
  texts=lambda el:el.xpath('//w:t/text()|//m:t/text()',namespaces=NS)
  require(texts(rr)==texts(root),'Red Word has the same content and equations as reading copy')
  require(len(rr.xpath('//w:color[@w:val="C00000"]',namespaces=NS))>100,'Reworked sections and unresolved fields highlighted red')
 letter=(ROOT/'submission/cover_letter.md').read_text().replace('К представлению планируются окончательные','К рукописи подготовлены новые')
 letter=letter.replace('Состав фактически готовой редакции определяется приложенным реестром; это письмо не удостоверяет завершённость ещё выполняемой переработки.','Состав приложений и границы проверки приведены в реестре редакции; письмо остаётся неподписанным проектом до личного согласования авторами.')
 (D/'Сопроводительное_письмо.md').write_text(letter)
 run(['pandoc',D/'Сопроводительное_письмо.md','-t','docx','-o',D/'Сопроводительное_письмо_ПСТА_v3.docx'],log='pandoc-letter.log');style_word(D/'Сопроводительное_письмо_ПСТА_v3.docx')
 run(['libreoffice','-env:UserInstallation=file:///tmp/fefc-v3-word','--headless','--convert-to','pdf','--outdir',D,*D.glob('*.docx')],log='libreoffice.log',timeout=240)
 require(all(x.with_suffix('.pdf').exists() for x in D.glob('*.docx')),'Every DOCX rendered to corresponding PDF')
 return {'omml_objects':count,'display_equations':display}


def latex(M,A,body,keys,figs,captions):
 def cite(m):
  nums=[]
  for s in m[1].split(','):
   s=s.strip();nums.extend(range(int(s.split('–')[0]),int(s.split('–')[-1])+1) if '–' in s else [int(s)])
  return '\\cite{'+','.join(keys[i-1] for i in nums)+'}'
 md=re.sub(r'\[([0-9]+(?:[–,][ 0-9]+)*)\]',cite,body)
 t=pandoc_text(md)
 t=re.sub(r'\\label\{ux[^}]+\}','',t)
 t=re.sub(r'(\\section\{)[1-8]\. ',lambda m:m[1],t)
 t=re.sub(r'(\\subsection\{)\d+\.\d+\. ',lambda m:m[1],t)
 t=re.sub(r'\\mathrm\{([А-Яа-яёЁ]+)\}',lambda m:r'\text{'+m[1]+'}',t)
 def equation(m):
  value=m[1];num=re.search(r'\\qquad\((\d+)\)',value);assert num
  value=re.sub(r'\\qquad\(\d+\)','',value).strip()
  if num[1]=='1':value=value.replace(r'\qquad'+'\nH(t)',r'\\ H(t)') if False else value
  return '\\begin{equation}\\label{eq:'+num[1]+'}\n'+value+'\n\\end{equation}'
 t=re.sub(r'\\\[(.*?)\\\]',equation,t,flags=re.S)
 t=t.replace('0{,}10;\\ 0{,}30;\\ 0{,}50;\\ 0{,}70;\\ 0{,}85;\\ 0{,}95','0{,}10;\\allowbreak 0{,}30;\\allowbreak 0{,}50;\\allowbreak 0{,}70;\\allowbreak 0{,}85;\\allowbreak 0{,}95')
 t=re.sub(r'\{\[\}ДЛЯ АВТОРА.*?\{\]\}',lambda m:'\\textcolor{red}{'+m[0]+'}',t,flags=re.S)
 for i,(d,cap) in enumerate(zip(figs,captions),1):
  f='\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\linewidth,height=130mm,keepaspectratio]{figures/'+d['name']+'.pdf}\n\\caption{'+cap[0]+'\\engcap{'+cap[1]+'}}\\label{fig:'+str(i)+'}\n\\end{figure}'
  t=t.replace('@@FIG'+str(i)+'@@',f)
 # Use actual fractions rather than Pandoc's equally sized narrow heading cells.
 def table(m):
  block=m[0];nn=block.count('\\real{')
  if nn==8:
   j=iter([.18]+[.117142857]*7);block=re.sub(r'\\real\{[0-9.]+\}',lambda _:r'\real{'+str(next(j))+'}',block)
  return '{\\small\\setlength{\\tabcolsep}{3pt}\n'+block+'\n}'
 t=re.sub(r'\\begin\{longtable\}.*?\\end\{longtable\}',table,t,flags=re.S)
 for name in ('Метод выбора конфигурации','Результаты','Обсуждение и ограничения'):t=t.replace('\\section{'+name+'}','\\FloatBarrier\n\\section{'+name+'}')
 (S/'body.tex').write_text(t)
 title=lambda s:pandoc_text(s).strip()
 short_titles={'ru': 'Моделирование краевой и туманной среды', 'en': 'Edge--fog simulation and reassignment'}
 base=r'''\documentclass{psta}
\usepackage{graphicx,booktabs,array,longtable,calc}
\usepackage{xcolor,placeins}
\DeclareUnicodeCharacter{2212}{\ensuremath{-}}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\newcommand{\engcap}[1]{\par\smallskip{\small\itshape #1}}
\emergencystretch=2em\tolerance=1800
\subjclass[UDC]{004.942}\JournalRubric{8}
\def\russianPublicationInfo{Авторская редакция.}
\def\englishPublicationInfo{Author manuscript.}
'''
 for lang in ('ru','en'):
  base+=('\\Russian\n' if lang=='ru' else '\\English\n')+'\\title['+title(short_titles[lang])+']{'+title(M['title_'+lang])+'}\n'
  for i,a in enumerate(A['authors_in_order']):
   name=a[lang];bits=name.split();name=bits[0]+', '+' '.join(bits[1:]) if lang=='ru' else bits[-1]+', '+' '.join(bits[:-1])
   org=A['affiliation_ru'] if lang=='ru' else M['affiliation_en']
   base+='\\author{'+name+'}\n\\address{'+org+'. '+M['address_'+lang]+'}\n'
   if i==0:base+='\\email{jigulina@mail.ru}\\correspondent\n'
   bio=A['biography_'+lang+'_for_each']
   blank='[ДЛЯ АВТОРА: ORCID при наличии; портрет и права; дополнительные подтверждённые строки справки.]' if lang=='ru' else '[AUTHOR: ORCID if available; portrait and permission; additional verified biographical details.]'
   base+='\\info{'+bio+'. \\textcolor{red}{'+blank+'}}\n'
  base+='\\begin{abstract}\n'+pandoc_text(M['abstract_'+lang])+'\n\\end{abstract}\n\\keywords{'+M['keywords_'+lang]+'}\n'
 base+=r'''\renewcommand{\PSTAconflictsofinterests}{\textcolor{red}{[ДЛЯ АВТОРА / AUTHOR: личное заявление о конфликте интересов; не подтверждено исполнителем.]}}
\begin{document}\Russian\maketitle
\input{body}
\raggedbottom\input{references.bbl}
\English\maketitle\section*{Extended summary}
'''+pandoc_text(M['extended_summary'])+'\n\\end{document}\n'
 (S/'main.tex').write_text(base)
 script=r'''#!/bin/sh
set -eu
cd "$(dirname "$0")"
export SOURCE_DATE_EPOCH=1795478400 FORCE_SOURCE_DATE=1
printf '%s\n' '\relax' '\citation{*}' '\bibstyle{psta-source-preserve}' '\bibdata{references}' > references.aux
bibtex references > bibtex-build.log 2>&1
for pass in 1 2 3; do
 pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex > build-$pass.log 2>&1 || { tail -60 build-$pass.log; exit 1; }
done
if grep -E 'Undefined control sequence|LaTeX Error|There were undefined references|Citation .*undefined|Reference .*undefined|Float too large' main.log; then exit 1; fi
'''
 (S/'build.sh').write_text(script)
 run(['sh','build.sh'],S,'psta-build.log',timeout=180)
 require((S/'main.pdf').exists(),'Full bilingual PSTA manuscript compiled')
 shutil.copy2(S/'main.pdf',D/'Статья_FEFC_R15_v3_ПСТА.pdf')
 log=(S/'main.log').read_text(errors='replace')
 warnings=[x for x in log.splitlines() if any(w in x for w in ('Warning','Overfull','Underfull'))]
 put(D/'tex-warnings.json',warnings)
 require('Overfull' not in log,'PSTA has no overfull boxes')
 return warnings


EXPECTED_PDFS={
 'Сопроводительное_письмо_ПСТА_v3.pdf':'letter',
 'Статья_FEFC_R15_v3_ПСТА.pdf':'article',
 'Статья_FEFC_R15_v3_для_чтения.pdf':'article',
 'Статья_FEFC_R15_v3_красные_изменения.pdf':'article',
}

def inspect_pdf():
 import fitz
 folder=D/'review-images';folder.mkdir(exist_ok=True);ledger=[]
 require(set(EXPECTED_PDFS)=={p.name for p in D.glob('*.pdf')},'Exact four expected document PDFs')
 for name,kind in EXPECTED_PDFS.items():
  path=D/name
  with fitz.open(path) as doc:
   require((1<=len(doc)<=45 if kind=='letter' else 2<=len(doc)<=45),path.name+': bounded complete page count')
   text='\n'.join(p.get_text() for p in doc)
   require('jigulina@mail.ru' in text,path.name+': confirmed contact rendered')
   if kind=='article':
    require('Simulation Modeling and Analysis' in text,path.name+': Law title rendered')
    require('Обсуждение и ограничения' in text and 'Extended summary' in text,path.name+': late sections and English summary rendered')
   else:
    compact=lambda t:re.sub(r'\s+','',t).replace('\u00ad','').replace('\u2011','-').replace('\u2010','-')
    markers=('Проект сопроводительного письма','НЕ ПОДПИСАНО','Моделирование краевой и туманной среды',
             'Марина Владимировна','Дина Владимировна','Игнатенко Александр Сергеевич','ЮНЦ РАН',
             '125011200147-2','НСКФ','Личные заявления авторов','Дата и подпись','ДЛЯ АВТОРА')
    require(len(compact(text))>=1400 and all(compact(m) in compact(text) for m in markers),
            path.name+': required complete letter content')
   outside=[]
   for i,p in enumerate(doc):
    pix=p.get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False);pix.save(folder/(path.stem+f'-{i+1:02}.png'))
    for b in p.get_text('blocks'):
     if b[6]==0 and (b[0]<-1 or b[1]<-1 or b[2]>p.rect.width+1 or b[3]>p.rect.height+1):outside.append(i+1)
    ledger.append({'file':path.name,'page':i+1,'pdf_sha256':sha(path),'text_characters':len(p.get_text()),'personal_visual_review':'NOT_CLAIMED_ON_NEW_BINARY','rendered':True})
   require(not outside,path.name+': text bounds do not leave the page')
 put(D/'page-review.json',ledger)
 return ledger

def package():
 shutil.copy2(SRC/'change_register.md',D/'Реестр_правок_FEFC_R15_v3.md')
 shutil.copy2(ROOT/'submission/author_metadata.json',D/'author_metadata.json')
 for p in S.rglob('*'):
  if p.is_file() and p.suffix.lower() in {'.aux','.log','.out','.toc','.brf','.blg'}:p.unlink()
 def zipped(folder,path):
  with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
   for p in sorted(folder.rglob('*')):
    if p.is_file() and p!=path and p.suffix.lower() not in FONT and 'review-images' not in p.parts:z.write(p,p.relative_to(folder))
 zipped(S,D/'Исходники_ПСТА_v3.zip')
 with tempfile.TemporaryDirectory(prefix='fefc-isolated-v3-') as tmp:
  fresh=Path(tmp)/'source'
  with zipfile.ZipFile(D/'Исходники_ПСТА_v3.zip') as z:z.extractall(fresh)
  run(['sh','build.sh'],fresh,'isolated-source-build.log',timeout=180)
  import fitz
  with fitz.open(fresh/'main.pdf') as a,fitz.open(S/'main.pdf') as b:
   require(len(a)==len(b) and [p.get_text() for p in a]==[p.get_text() for p in b],'Unpacked source ZIP rebuild has identical page texts')
  require(sha(fresh/'references.bbl')==sha(S/'references.bbl'),'Unpacked source ZIP regenerates the same actual BBL')
  require('Overfull' not in (fresh/'main.log').read_text(errors='replace'),'Unpacked source ZIP has no Overfull boxes')
  identical=sha(fresh/'main.pdf')==sha(S/'main.pdf')
 put(D/'isolated-build.json',{'passed':True,'byte_identical_pdf':identical,'command':'sh build.sh','execution':'GitHub Actions; isolated temporary directory'})
 require(not any(p.suffix.lower() in FONT for p in D.rglob('*') if p.is_file()),'No font files distributed')
 return zipped


def build():
 M,A,body=prepare();keys,bibmd=bibliography();figs,captions=figures();wc=word(M,A,body,bibmd,figs,captions);warnings=latex(M,A,body,keys,figs,captions);ledger=inspect_pdf();zipper=package()
 register=(SRC/'change_register.md').read_text();require(all('R'+f'{i:02}' in register for i in range(1,32)) and 'AU-04' in register,'All 32 prior source comment dispositions recovered')
 put(D/'receipt.json',{'source_sha':os.environ.get('REWORK_SOURCE_SHA',os.environ['GITHUB_SHA']),'base_sha':BASE,'execution':'GitHub Actions; Pandoc; python-docx; LibreOffice; BibTeX; pdflatex; PyMuPDF','checks':CHECKS,'checks_passed':sum(c['pass'] for c in CHECKS),**wc,'sections':8,'references':27,'figures':3,'scientific_snapshot_requests':131,'simulation_executed':False,'bootstrap_recomputed':False,'new_neural_training':False,'source_word_inspected_in_prior_interrupted_execution':True,'new_binary_visually_accepted':False,'whole_article_created':True,'ready_to_submit':False,'article_sent':False,'remaining_author_fields':['NSCF reference/provenance decision and number','ORCID if available; portraits and rights; additional verified biography lines','personal consents and signatures; conflict-of-interest statement'],'warnings':warnings})
 (D/'README.md').write_text('''# FEFC R1.5 — восстановленная полная редакция v3

Восемь разделов, две согласованные аннотации, английское резюме, 27 источников, девять формул и три новые векторные схемы. Читаемая Word-копия и отдельная красная копия содержат одинаковый текст. В красной копии целиком выделены переработанные разделы; это не посимвольный Track Changes. Незаполненные авторские поля красные в обеих копиях. Письмо — неподписанный проект.

PDF с окончанием «для_чтения» получен из соответствующего Word. PDF «ПСТА» — тот же научный текст, собранный pdflatex с двуязычным авторским блоком по классу журнала. LaTeX и исходный ZIP содержат настоящие BIB/BST/BBL и build.sh. SVG/TikZ/PDF в LaTeX/figures — векторные; Word содержит SVG и совместимый PNG-резерв.

Это продолжение прерванной редакции, основанной на точной Word-копии с 32 примечаниями. Тексты и геометрия восстановлены по протоколу предыдущего исполнения; утраченные локальные бинарные файлы не объявляются побайтово восстановленными. Новая сборка имеет собственные хеши. Предыдущий принятый комплект не заменён без регистрации.

Новых опытов, bootstrap и обучения нет; один итоговый сценарий и условность вывода сохранены. Готовность к отправке не объявляется до личных авторских подтверждений и проверки новой редакции. Растровая отрисовка/геометрические проверки не названы новым личным визуальным просмотром. Подробности — receipt.json и page-review.json.
''')
 put(D/'SHA256.json',{p.relative_to(D).as_posix():sha(p) for p in sorted(D.rglob('*')) if p.is_file() and p.name!='SHA256.json'})
 zipper(D,D/'FEFC_R15_v3_полный_комплект.zip')
 print('FULL_REWORK_RECEIPT',json.dumps(json.loads((D/'receipt.json').read_text()),ensure_ascii=False),flush=True)


def publish():
 expected=os.environ.get('REWORK_SOURCE_SHA',os.environ['GITHUB_SHA']);ref='refs/heads/night/fefc-v3'
 git=lambda *a:run(['git',*a]).decode().strip()
 if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD changed; do not overwrite')
 target=ROOT/'deliverables/r15-rework-v3';shutil.copytree(D,target,dirs_exist_ok=True)
 # Save exact generated LaTeX alongside the restored authoring source.
 prepared=ROOT/'article/rework/LaTeX';shutil.copytree(S,prepared,dirs_exist_ok=True)
 status=ROOT/'docs/STATUS.md';previous=status.read_text()
 top='# STATUS — R1.5: полная восстановленная редакция v3 собрана\n\n24.11.2026. Ход #7141330007 продолжает #7133290317. Только night/fefc-v3, PR#2 без слияния.\n\nПолная статья: deliverables/r15-rework-v3. Исходники: article/rework/article_body.md, metadata.json, figures/render_figures.py и LaTeX/. Исходный Word был прочитан в прерванном ходе; новый комплект восстановлен из его текстового протокола, не из старого main.tex. Старые локальные DOCX/PDF недоступны после истечения сессии; новые бинарные файлы имеют собственные хеши. Отдельные независимые компоненты article/rework_round3 не являются основной новой статьёй.\n\nИсточник сборки '+expected+'; Actions '+os.environ.get('GITHUB_RUN_ID','')+'. Восемь разделов, 27 источников, девять формул, три векторные схемы, читаемая и красная Word-копии, PDF Word/PSTA, письмо, реестр32примечаний. Проверки — receipt.json. Новая личная визуальная приёмка НЕ присвоена: страницы отрисованы и проверены машинно, изображения сохранены для адресного просмотра. Предыдущая приёмка не переносится автоматически.\n\nНаучное ядро/критерии/данные, main, v2 и журнал Perplexity не менялись. Срез статьи131 не смешан с162. Новых опытов/bootstrap/обучения нет. Контакт, состав, порядок, ЮНЦ РАН, сокращённый объём и поддержка подтверждены; не спрашивать повторно. Открытые личные поля красные.\n\nТочка продолжения: читать только новые receipt/реестр и выполнить адресный визуальный просмотр полученных PDF/схем; после замечаний менять только затронутые фрагменты. Статья не отправлена, письмо не подписано. Исправные серии не повторять.\n\nОЦЕНКА расхода этого длинного продолжения: 5–10тыс. доступ/восстановление; 15–25тыс. текст/схемы; 15–25тыс. сборка/отладка/проверки. Это диапазон, не биллинг.\n\nЖурнал 24.11.2026 · BT26-R15-REWORK-CONTINUE-01 · основание:#7131272024, точный исходный Word, сохранённый протокол прежней редакции и текущий Actions · решение: восстановить и предъявить полную редакцию, без нового исследования · статус: сборка выполнена, готовность к отправке не заявлена. Владелец освобождает запись после успешного push.\n\n---\nПредыдущая запись:\n\n'
 status.write_text(top+previous)
 git('config','user.name','FEFC editorial executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
 git('add','--','deliverables/r15-rework-v3','article/rework/LaTeX','docs/STATUS.md')
 staged=run(['git','diff','--cached','--name-only','-z']).decode().split('\0')
 if any(p and p!='docs/STATUS.md' and not p.startswith(('deliverables/r15-rework-v3/','article/rework/LaTeX/')) for p in staged):raise RuntimeError('Unexpected staged path')
 if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD changed before commit')
 git('commit','-m','Issue #5 п.5: опубликовать полную редакцию v3, Word/PDF/векторы и реестр')
 git('push','origin','HEAD:'+ref)
 final=git('rev-parse','HEAD');put(OUT/'publication.json',{'source_sha':expected,'delivery_sha':final,'writer_released':True,'whole_article_created':True,'article_sent':False});print('REWORK_DELIVERY_SHA',final,flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['build','publish']);a=p.parse_args();globals()[a.stage]()
