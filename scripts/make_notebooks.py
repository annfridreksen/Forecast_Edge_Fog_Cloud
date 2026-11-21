"""Build clean notebooks; outputs are created by nbconvert, never invented."""
from pathlib import Path
import nbformat as n
ROOT=Path(__file__).resolve().parents[1]
BOOT='''from pathlib import Path
import os, sys
root = Path.cwd()
while root != root.parent and not (root/'efc').exists():
    root = root.parent
if not (root/'efc').exists():
    import subprocess
    target = Path('/content/Forecast_Edge_Fog_Cloud')
    subprocess.run(['git','clone','--branch','night/fefc-v3','https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud.git',str(target)],check=True)
    root=target
os.chdir(root)
sys.path.insert(0,str(root))
print('Рабочая папка:',root)
'''
def notebook(name,title,pairs):
    cells=[n.v4.new_markdown_cell('# '+title+'\n\nВсе данные синтетические. Работа выполняется в отдельной ветке; эталон v2 не изменяется.')]
    cells.extend([n.v4.new_markdown_cell('Найдём корень проекта. В Colab при отсутствии файлов клонируется только рабочая ветка; локально используются уже полученные исходники.'),n.v4.new_code_cell(BOOT)])
    for explain,code in pairs:cells.extend([n.v4.new_markdown_cell(explain),n.v4.new_code_cell(code)])
    nb=n.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    p=ROOT/'colab/clean'/name;p.parent.mkdir(parents=True,exist_ok=True);n.write(nb,p)

notebook('01_Среда_и_конфигурация.ipynb','Среда и конфигурация',[
('Что исследуем: как поток проходит Edge, отдельную FIFO одного из 50 Fog и Cloud. Интервалы из TASK.md — синтетические профили, а сетевые законы и деление Edge — явные допущения.',"from efc.experiments import configuration_series\nfrom efc.model import simulate,Config,COMPONENTS\nfrom efc.views import architecture,configuration_plots,animate_task\nimport pandas as pd\nframe=configuration_series()\ndisplay(frame)"),
('На схемах показаны уровни, шесть компонент и входы/выходы. Схема содержит группы устройств, но модель создаёт каждый Fog с собственной очередью.',"architecture()"),
('Сравним конфигурации на одинаковых правилах. Стресс-серия 1200 событий/с отделена от парковочной нагрузки 400 событий/ч; по ней нельзя заявлять параметры реальной парковки.',"queue=pd.read_csv('results/stress_queue.csv')\nconfiguration_plots(frame,queue)"),
('Анимация одного события использует его рассчитанные интервалы, а не произвольную длительность. Базовая очередь может быть пустой — это также результат.',"r=simulate()\nhtml=animate_task(r['tasks'][0])\nPath('results/event_animation.html').write_text(html)"),
('Ползунки изменяют параметры нового запуска. Если ipywidgets отсутствует в локальной среде, сначала установите зависимости; статические результаты выше уже воспроизводимы.',"try:\n    import ipywidgets as w\n    def explore(sensors=1000,fog=50,buffer=50,mobile=0.3):\n        m=simulate(Config(n_edge=sensors,n_fog=fog,buffer=buffer,mobile_fraction=mobile))['metrics']\n        print({k:m[k] for k in ('mean_ms','p95_ms','mean_fog_wait_ms','dropped')})\n    display(w.interactive(explore,sensors=w.IntSlider(value=1000,min=500,max=2000,step=250),fog=w.IntSlider(value=50,min=25,max=100,step=25),buffer=w.IntSlider(value=50,min=0,max=400,step=10),mobile=w.FloatSlider(value=.3,min=0,max=1,step=.1)))\nexcept ImportError:\n    print('ipywidgets не установлен: интерактивные ползунки не проверены в этой среде.')"),
('Проверка: баланс событий и сумма шести компонент. Таблица чисел предназначена для прямого переноса в статью с указанием источника.',"assert (frame.completed+frame.dropped==frame.arrivals).all()\nfor row in r['tasks']:\n    if row['status']=='completed':\n        assert abs(sum(row[k] for k in COMPONENTS)-row['latency_ms'])<1e-6\nb=frame.query(\"scenario=='baseline'\").iloc[0]\ndisplay(pd.DataFrame({'число в статье':[b.mean_ms,b.p95_ms,b.mean_fog_wait_ms],'число модели':[r['metrics']['mean_ms'],r['metrics']['p95_ms'],r['metrics']['mean_fog_wait_ms']]},index=['средняя,мс','p95,мс','Fog-ожидание,мс']))\nassert abs(b.mean_ms-r['metrics']['mean_ms'])<1e-9\nprint('OK')")])
notebook('00_Старт.ipynb','Старт и проверка',[
('Установим зависимости только в Colab. В подготовленной локальной среде установка не требуется; сетевой доступ для тестов не нужен.',"import subprocess\nif 'google.colab' in sys.modules:\n    subprocess.run([sys.executable,'-m','pip','install','-q','-r','requirements.txt'],check=True)\nprint(sys.version)"),
('Запустим тесты новой среды. Эталонные тесты v2 запускаются отдельно, без изменения их файлов.',"p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],text=True,capture_output=True)\nprint(p.stdout+p.stderr)\nassert p.returncode==0\nif (root/'v2/code').exists():\n    p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root/'v2/code',text=True,capture_output=True)\n    print(p.stdout+p.stderr)\n    assert p.returncode==0\nelse:\n    print('Эталон v2 отсутствует в этой локальной копии; его проверка не выполнена.')\nprint('OK: доступные тесты')")])
print('Created clean notebooks 00 and 01')
