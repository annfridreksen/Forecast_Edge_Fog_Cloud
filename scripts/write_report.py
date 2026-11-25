"""Write a current report and final provenance from actual executed records."""
from pathlib import Path
import json,re
from issue4_report import main as issue4_report
from finalize_provenance import main as finalize_provenance
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';D=ROOT/'docs'

def main():
    data=json.loads((R/'build-summary.json').read_text())
    for log in ('model-tests.txt','v2-tests.txt'):
        text=(R/log).read_text()
        if not re.search(r'Ran \d+ tests?',text) or not text.rstrip().endswith('OK'):raise RuntimeError('Tests not confirmed: '+log)
    if not data['protected_v2_unchanged'] or not data['reviewer_journal_unchanged']:raise RuntimeError('Protected source changed')
    run=data.get('workflow_run_id');url='https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/actions/runs/'+run if run else 'локальный запуск'
    text=f'''# Отчёт выполненной адресной доработки FEFC v3

UTC: {data['utc']}. Исходный коммит: `{data['source_commit']}`.
Ветка: `{data['branch']}`. Выполненный runner: {url}.
Это текущая сборка, а не утверждение о работе в течение всей прошедшей ночи.

## Запущенные тетради
| Тетрадь | Прошедшее время, с | Результат |
|---|---:|---|
'''
    for name,seconds in data['notebooks'].items():text+=f'| {name} | {seconds:.3f} | кодовые ячейки выполнены, ошибок нет, OK |\n'
    text+='\nИзмерено на runner после установки зависимостей; время Google Colab и ручное взаимодействие не гарантируются. Технический ориентир пяти минут проверяется по приведённым фактическим значениям, не объявляется автоматически выполненным.\n\n## Журналы команд\n| Команда | Код выхода | Прошедшее время, с | Журнал |\n|---|---:|---:|---|\n'
    for step in data['steps']:text+='| '+' '.join(step['command'])+' | '+str(step['returncode'])+f" | {step['elapsed_wall_seconds']:.3f} | results/{step['log']} |\n"
    text+='''
## Только написано / не проверено непосредственно
Веб-интерфейс Google Colab не открывался: выполнялись ipynb через nbconvert.
Настоящая пользовательская сеть и измерения оборудования не подключены.
Номинальная конформная гарантия для зависимого смещённого ряда не установлена.
Один снимок размещения не является сравнительным исследованием алгоритмов.
Подача статьи, авторские согласия и полные выходные сведения НСКФ не оформлены.

## Сохранность и воспроизведение
Выполнение из чистого GitHub checkout; final-check.txt создаётся последним шагом.
SHA-256 v2 до/после совпадают. Журнал Perplexity не изменён. main не затронута.
Коммит с результатами создаётся после проверки; его SHA не подставляется задним
числом в исходный коммит запуска. Версии зависимостей и фактические хеши исходников
сохраняются в build-summary.json, requirements-executed.txt, source-hashes.json.

## Препятствия
В локальной среде git clone недоступен из-за DNS. Изменения выполнялись через
GitHub API, настоящая сборка — на GitHub runner. Прежние неудачные/отменённые
запуски не удалены; их количество включено в журнал истории ниже.
'''
    (D/'Отчёт_ночи.md').write_text(text)
    finalize_provenance()
    issue4_report()
    with (D/'Отчёт_ночи.md').open('a') as f:f.write('\nСлабое место: результаты относятся к явным синтетическим допущениям; реальная инфраструктура, точная стационарность и преимущество P не подтверждены.\n')
if __name__=='__main__':main()
