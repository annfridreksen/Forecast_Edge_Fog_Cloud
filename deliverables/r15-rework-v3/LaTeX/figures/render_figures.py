"""Recovered figure geometry from the interrupted editorial v3 execution.
One editable layout generates SVG, TikZ and vector PDF; no simulation.
"""
from pathlib import Path
import html,json,subprocess,hashlib
FIGS=[]
def diagram(name,W,H):
 d=dict(name=name,width=W,height=H,nodes=[],edges=[],labels=[],frames=[]);FIGS.append(d);return d
def node(d,id,x,y,w,h,lines,kind='box',font=17,bold=False):d['nodes'].append(dict(id=id,x=x,y=y,w=w,h=h,lines=lines,kind=kind,font=font,bold=bold))
def label(d,x,y,text,font=16):d['labels'].append(dict(x=x,y=y,text=text,font=font))
def edge(d,start,end,points,dashed=False,text=None,xy=None):
 d['edges'].append(dict(start=start,end=end,points=points,dashed=dashed))
 if text:label(d,*xy,text)
def frame(d,x,y,w,h,dashed=False):d['frames'].append(dict(x=x,y=y,w=w,h=h,dashed=dashed))

f1=diagram('01_environment',600,640)
node(f1,'source',32,10,346,44,['1000 датчиков → сообщение'],bold=True)
node(f1,'edge',32,78,346,62,['1. Edge: ожидание + обработка','d_E; отдельный ресурс датчика'])
node(f1,'ingress',32,164,346,62,['2. Входной канал: ожидание + передача','d_EF; канал закреплённого Fog'],font=16)
node(f1,'admit',32,251,346,64,['Fog свободен или есть','место в буфере B?'],kind='decision',font=15)
node(f1,'wait',32,341,346,44,['3. Ожидание Fog: w_F'])
node(f1,'fog',32,409,346,44,['4. Обслуживание Fog: s_F'])
node(f1,'egress',32,477,346,62,['5. Выходной канал:','ожидание + передача, d_FC'])
node(f1,'cloud',32,563,346,62,['6. Cloud: ожидание + обработка','d_C; пул из 40 серверов → результат'])
node(f1,'loss',420,254,160,62,['Потеря','сообщения'],font=18,bold=True)
for a,b,ya,yb in [('source','edge',54,78),('edge','ingress',140,164),('ingress','admit',226,251),('admit','wait',315,341),('wait','fog',385,409),('fog','egress',453,477),('egress','cloud',539,563)]:edge(f1,a,b,[(205,ya),(205,yb)])
label(f1,233,331,'да',15);edge(f1,'admit','loss',[(378,283),(420,283)],text='нет',xy=(400,270))
node(f1,'note1',420,80,160,116,['Источник отключён:','новое сообщение','не создаётся.','Это не потеря','в очереди Fog.'],kind='note',font=16)
node(f1,'note2',420,360,160,100,['B — только места','ожидания.','Вместимость Fog:','K = B + 1.'],kind='note',font=16)
node(f1,'note3',420,500,160,112,['Прочие очереди','не ограничены.','Все ожидания','включены в D','ровно один раз.'],kind='note',font=16)

f2=diagram('02_verification',600,710)
node(f2,'input',25,10,550,52,['Конфигурация, внешний поток и параметры протокола'],font=18,bold=True)
node(f2,'pilot',30,88,355,65,['Пилот: seed 100–109','Выбор окон и проверка прогрева'],font=18)
node(f2,'windows',30,181,355,70,['Окна и точность','подтверждены?'],kind='decision',font=18)
node(f2,'insuff1',430,185,145,66,['Недостаточно','данных'],font=18,bold=True)
node(f2,'main',30,283,355,62,['Фиксированные окна','Итоговые seed 0–9'],font=18)
node(f2,'assessment',30,374,545,70,['Полнота когорты, точность и совместные пороги','Оценка p95 и потерь при явных допущениях'],font=18)
node(f2,'accept',20,496,176,68,['Допустима','при указанных','допущениях'],font=17,bold=True)
node(f2,'insuff2',212,496,176,68,['Недостаточно','данных'],font=17,bold=True)
node(f2,'reject',404,496,176,68,['Недопустима','при указанных','предпосылках'],font=17,bold=True)
frame(f2,15,596,570,104,True)
node(f2,'freeze',30,624,245,60,['Зафиксировать кандидата','из оценённой карты'],font=17)
node(f2,'confirm',320,624,245,60,['Независимое подтверждение','seed 200–209'],font=17)
label(f2,300,613,'ПОСЛЕДУЮЩИЙ ЭТАП — НЕ ВЫПОЛНЕН',15)
for a,b,p in [('input','pilot',[(207,62),(207,88)]),('pilot','windows',[(207,153),(207,181)]),('windows','main',[(207,251),(207,283)]),('main','assessment',[(207,345),(207,374)])]:edge(f2,a,b,p)
label(f2,236,270,'да');edge(f2,'windows','insuff1',[(385,216),(430,216)],text='нет',xy=(407,201))
for id,x in [('accept',108),('insuff2',300),('reject',492)]:edge(f2,'assessment',id,[(x,444),(x,496)])
for x,t in [(108,'пороги выполнены'),(300,'вывод не разрешён'),(492,'нижняя граница выше')]:label(f2,x,476,t,14)
edge(f2,'accept','freeze',[(108,564),(108,624)],True);edge(f2,'freeze','confirm',[(275,654),(320,654)],True)

f3=diagram('03_reassignment',800,1035)
frame(f3,22,10,738,98);frame(f3,15,145,748,878,True)
for x,y,t,fs in [(391,34,'РЕАЛИЗОВАННАЯ ИМИТАЦИОННАЯ СРЕДА',22),(391,63,'Датчики → Edge → Fog → Cloud',22),(391,89,'События, очереди и исходы сообщений',20),(390,170,'ПРОЕКТИРУЕМЫЕ ИНТЕРФЕЙСЫ И УПРАВЛЕНИЕ',21)]:label(f3,x,y,t,fs)
node(f3,'observations',42,190,360,74,['Будущий интерфейс наблюдений','Узел/зона, окно, единицы, время'],font=20)
node(f3,'task',455,190,280,102,['Входы задачи: граф;','фиксированное разбиение;','прежний план;','ограничения'],font=18)
node(f3,'predict',42,291,360,98,['Внешние оцениватели','Задержка и потери конфигурации','Риск переполнения Fog','Риск отказа источника'],font=18)
node(f3,'update',455,338,280,100,['М2.3. Проверить план','Сохранить допустимый','либо повторить выбор','Записать основание'],font=18)
node(f3,'adapter',42,417,360,65,['Адаптер порядковых команд','Правило и калибровка'],font=20)
node(f3,'m21',42,500,360,96,['М2.1: применимость','Актуальны и сопоставимы?'],kind='decision',font=17)
node(f3,'rankforecast',34,619,186,50,['С прогнозом','(R, T, N, id)'],font=20)
node(f3,'rankbase',255,619,186,50,['Без прогноза','(T, N, id)'],font=20)
node(f3,'m22',42,707,360,108,['М2.2. Полные назначения','целых подграфов','Проверка полного плана','Выбор по заданному порядку'],font=20)
node(f3,'no_plan',42,852,360,68,['Допустимый план не найден','Не доказательство невозможности'],font=19)
node(f3,'plan',455,789,280,66,['План + протокол','Новый либо сохранённый'],font=18,bold=True)
node(f3,'apply',455,905,280,70,['Будущее применение плана','в разрешённой точке'],font=20)
node(f3,'scope',460,606,270,46,['Команды — не секунды','и не вероятности'],kind='note',font=18)
edge(f3,'environment','observations',[(222,108),(222,190)],True)
for a,b,ya,yb in [('observations','predict',264,291),('predict','adapter',389,417),('adapter','m21',482,500)]:edge(f3,a,b,[(222,ya),(222,yb)])
edge(f3,'m21','rankforecast',[(222,596),(222,607),(127,607),(127,619)],text='да',xy=(120,598))
edge(f3,'m21','rankbase',[(222,596),(222,607),(348,607),(348,619)],text='нет',xy=(348,598))
edge(f3,'rankforecast','m22',[(127,669),(127,707)]);edge(f3,'rankbase','m22',[(348,669),(348,707)])
edge(f3,'m22','no_plan',[(222,815),(222,852)],text='не найден',xy=(284,839))
edge(f3,'m22','plan',[(402,762),(428,762),(428,822),(455,822)],text='найден',xy=(476,748))
edge(f3,'plan','apply',[(595,855),(595,905)])
edge(f3,'observations','update',[(402,227),(431,227),(431,371),(455,371)],True)
edge(f3,'task','update',[(595,292),(595,338)])
edge(f3,'update','m21',[(455,410),(431,410),(431,548),(402,548)],text='повторить выбор',xy=(543,478))
edge(f3,'update','plan',[(735,390),(742,390),(742,822),(735,822)],text='сохранить',xy=(682,577))
edge(f3,'task','m22',[(735,246),(751,246),(751,684),(418,684),(418,730),(402,730)],True)
label(f3,585,676,'граф, разбиение, ограничения',17)
edge(f3,'apply','environment',[(735,945),(787,945),(787,60),(760,60)],True)
label(f3,600,998,'Обратная связь — ещё не реализована',18)

CAPTIONS=[
 ['Реализованная среда: ресурсы, шесть составляющих задержки и потеря при заполнении Fog.','Implemented environment: resources, six latency components, and loss at a full fog queue.'],
 ['Протокол проверки: самостоятельный исход недостаточности данных и последующее подтверждение только зафиксированного кандидата.','Evaluation protocol: insufficient data is a separate outcome; subsequent confirmation is limited to a frozen candidate.'],
 ['Реализованная среда и проектируемое прогнозное управление. Выбор, сохранение и будущее применение полного плана разделены.','Implemented environment and proposed forecast-aware control. Selection, retention, and future application of a complete plan are separated.']]

def texescape(s):
 s=s.replace('\\',r'\textbackslash{}')
 for a,b in [('&',r'\&'),('%',r'\%'),('_',r'\_'),('#',r'\#')]:s=s.replace(a,b)
 return s.replace('→',r'$\rightarrow$').replace('×',r'$\times$')

def render(d,folder):
 W,H=d['width'],d['height'];widthmm=116;scale=widthmm*72/25.4/W
 parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{widthmm}mm" height="{H/W*widthmm:.3f}mm" viewBox="0 0 {W} {H}">','<title>'+html.escape(d['name'])+'</title>','<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#111"/></marker></defs>','<rect width="100%" height="100%" fill="white"/>']
 t=[r'\begin{tikzpicture}[x='+str(scale)+r'pt,y=-'+str(scale)+r'pt,>=Stealth]',r'\path[use as bounding box] (0,0) rectangle ('+f'{W},{H}'+');']
 for f in d['frames']:
  dash=' stroke-dasharray="10 7"' if f['dashed'] else ''
  parts.append(f'<rect x="{f["x"]}" y="{f["y"]}" width="{f["w"]}" height="{f["h"]}" fill="none" stroke="#111" stroke-width="2"{dash}/>')
  t.append(r'\draw[line width=0.8pt'+(',dashed' if f['dashed'] else '')+'] ('+f'{f["x"]},{f["y"]}'+') rectangle ('+f'{f["x"]+f["w"]},{f["y"]+f["h"]}'+');')
 for e in d['edges']:
  points=' '.join(f'{x},{y}' for x,y in e['points']);dash=' stroke-dasharray="7 5"' if e['dashed'] else ''
  parts.append(f'<polyline points="{points}" fill="none" stroke="#111" stroke-width="1.8" marker-end="url(#arrow)"{dash}/>')
  t.append(r'\draw[->,line width=0.6pt'+(',dashed' if e['dashed'] else '')+'] '+' -- '.join('('+f'{x},{y}'+')' for x,y in e['points'])+';')
 for n in d['nodes']:
  x,y,ww,hh=n['x'],n['y'],n['w'],n['h'];cx=x+ww/2;cy=y+hh/2
  if n['kind']=='decision':
   verts=[(cx,y),(x+ww,cy),(cx,y+hh),(x,cy)]
   parts.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in verts)+'" stroke="#111" stroke-width="1.8" fill="white"/>')
   t.append(r'\draw[fill=white,line width=0.6pt] '+' -- '.join('('+f'{a},{b}'+')' for a,b in verts)+r' -- cycle;')
  elif n['kind']=='box':
   parts.append(f'<rect x="{x}" y="{y}" width="{ww}" height="{hh}" rx="5" fill="white" stroke="#111" stroke-width="1.8"/>')
   t.append(r'\draw[fill=white,rounded corners=2pt,line width=0.6pt] ('+f'{x},{y}'+') rectangle ('+f'{x+ww},{y+hh}'+');')
  else:parts.append(f'<rect x="{x}" y="{y}" width="{ww}" height="{hh}" fill="white" stroke="none"/>')
  fs=n['font'];lh=fs*1.16;start=cy-(len(n['lines'])-1)*lh/2+fs*.33
  weight='bold' if n['bold'] else 'normal'
  parts.append(f'<text x="{cx}" y="{start}" text-anchor="middle" font-family="Times New Roman,Liberation Serif,serif" font-size="{fs}" font-weight="{weight}" fill="#111">')
  for i,line in enumerate(n['lines']):parts.append(f'<tspan x="{cx}" dy="{0 if i==0 else lh}">{html.escape(line)}</tspan>')
  parts.append('</text>');tl=r'\\'.join(texescape(s) for s in n['lines'])
  t.append(r'\node[align=center,inner sep=0pt,font=\fontsize{'+f'{fs*scale:.3f}'+r'}{'+f'{lh*scale:.3f}'+r'}\selectfont'+(r'\bfseries' if n['bold'] else '')+'] at ('+f'{cx},{cy}'+'){'+tl+'};')
 for l in d['labels']:
  parts.append(f'<text x="{l["x"]}" y="{l["y"]}" text-anchor="middle" font-family="Times New Roman,Liberation Serif,serif" font-size="{l["font"]}" fill="#111" stroke="white" stroke-width="3" paint-order="stroke">{html.escape(l["text"])}</text>')
  t.append(r'\node[fill=white,inner sep=1pt,font=\fontsize{'+f'{l["font"]*scale:.3f}'+r'}{'+f'{l["font"]*scale*1.15:.3f}'+r'}\selectfont] at ('+f'{l["x"]},{l["y"]-l["font"]*.30}'+'){'+texescape(l['text'])+'};')
 parts.append('</svg>');t.append(r'\end{tikzpicture}')
 (folder/(d['name']+'.svg')).write_text('\n'.join(parts),encoding='utf-8')
 (folder/(d['name']+'.tikz')).write_text('\n'.join(t),encoding='utf-8')
 wrapper=r'''\documentclass[border=1pt]{standalone}
\usepackage[T2A]{fontenc}\usepackage[utf8]{inputenc}
\usepackage[russian,english]{babel}\usepackage{tikz}\usetikzlibrary{arrows.meta}
\begin{document}\input{'''+d['name']+r'''.tikz}\end{document}
'''
 (folder/(d['name']+'.tex')).write_text(wrapper)

if __name__=='__main__':
 folder=Path(__file__).parent
 (folder/'diagrams.json').write_text(json.dumps(FIGS,ensure_ascii=False,indent=2)+'\n')
 for d in FIGS:render(d,folder)
