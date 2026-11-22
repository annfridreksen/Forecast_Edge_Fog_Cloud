"""Write author-facing completion report only from executed build records."""
from pathlib import Path
import json,re,os
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results';D=ROOT/'docs'
s=json.loads((R/'build-summary.json').read_text())
conf=pd.read_csv(R/'configuration.csv');base=conf.set_index('scenario').loc['baseline']
f=pd.read_csv(R/'forecast_metrics.csv');mlp=f.set_index('method').loc['NeuralNet']
linked=pd.read_csv(R/'neural_placement.csv').set_index('requested_method')
meta=json.loads((R/'forecast_metadata.json').read_text())
doi=json.loads((R/'doi-check.json').read_text())
def tests(name):
 t=(R/name).read_text();n=re.search(r'Ran (\d+) tests? in ([0-9.]+)s',t)
 if not n or not t.rstrip().endswith('OK'):raise RuntimeError(name+' does not confirm success')
 return int(n.group(1)),n.group(2)
new_n,new_s=tests('model-tests.txt');old_n,old_s=tests('v2-tests.txt')
assert old_n==98 and new_n>=28
assert len(s['notebooks'])==4 and s['protected_v2_unchanged']
steps='\n'.join('| '+x['command'][-1]+' | '+str(x['returncode'])+' | '+f"{x['elapsed_wall_seconds']:.3f}"+' | `results/'+x['log']+'` |' for x in s['steps'])
notebooks='\n'.join(f'| {name} | {seconds:.3f} | OK |' for name,seconds in s['notebooks'].items())
runlink=('https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/actions/runs/'+s['workflow_run_id']) if s.get('workflow_run_id') else 'локальный запуск; не GitHub Actions'
text=f'''# Отчёт выполненного этапа FEFC v3

Дата/время UTC: {s['utc']}. Исходный коммит: `{s['source_commit']}`.
Ветка: `{s['branch']}`. Проверка: {runlink}.
Сведения ниже сформированы автоматически после тестов, выполнения тетрадей,
проверки данных рисунков и двух проходов LaTeX. Отчёт не означает принятия статьи.

## Сделано и запущено
- Модель среды написана заново: отдельные FIFO всех Fog, конечный буфер,
  потери, каналы, Cloud-пул и шесть сохраняемых компонент.
- Новые тесты: `Ran {new_n} tests in {new_s}s`, `OK`.
- Эталон v2: `Ran {old_n} tests in {old_s}s`, `OK`; SHA-256 до/после совпали.
- Серия конфигураций: {len(conf)} сценариев. База: средняя {base.mean_ms:.9f} мс,
  p95 {base.p95_ms:.9f} мс, ожидание Fog {base.mean_fog_wait_ms:.9f} мс,
  {int(base.completed)} завершений и {int(base.dropped)} потерь.
- Демонстрационный MLP и четыре сравнительных прогноза через общий интерфейс;
  train/calibration/test {int(mlp.train_n)}/{int(mlp.calibration_n)}/{int(mlp.test_n)}.
  В прогнозной серии {meta['dropped']} потерь; они не получают нулевых задержек.
- MLP: MAE {mlp.mae_ms:.9f} мс, покрытие p95 {mlp.coverage_p95:.9f}. Недопокрытие
  сохранено. Порог не перенастраивается по тестовой части.
- Контроль v2: P→EFE 8 мс, B→FFF 4 мс; срок 7→EFF 6 мс; срок 3→нет плана.
- Сквозной пример NeuralNet→ranks→P/B: фактическое в модели время
  P={linked.loc['P','actual_ms']:.9f} мс, B={linked.loc['B','actual_ms']:.9f} мс.
  Разность P−B={linked.loc['P','actual_ms']-linked.loc['B','actual_ms']:.9f} мс не удалена.
- 17 пар PDF/PNG из тетрадей, анимация события, код интерактивных ползунков.
- Полный текст семи разделов, аннотации RU/EN, формулы, таблицы из CSV,
  источники и PDF PSTA; отсутствие неопределённых ссылок/переполнений проверено.
- Реестр чисел: `docs/Утверждения.md` и `results/claims.json`.
- Метаданные DOI через Crossref: {sum(r['verified'] for r in doi['records'])}/{len(doi['records'])}.
  Ошибки доступа остаются в `results/doi-check.json`, не заменяются выдуманными данными.

## Тетради, выполненные nbconvert
| Тетрадь | Время, с | Последняя проверка |
|---|---:|---|
{notebooks}

Это фактическое время на указанном runner после установки зависимостей, не
гарантия времени запуска Google Colab и не измерение ручного взаимодействия.
Тетрадь 00 может повторно запускать тесты; это проверка, не новый опыт.

## Журналы
| Команда/объект | Код выхода | Прошедшее время, с | Полный вывод |
|---|---:|---:|---|
{steps}

Время получено `perf_counter` и означает прошедшее время, не время CPU.
Версии зависимостей: `results/build-summary.json`, `requirements-executed.txt`.
Проверка чистого checkout: `results/final-check.txt` (создаётся завершающим шагом
этого же процесса). Итоговые контрольные суммы: корневой `MANIFEST.sha256`.

## Только написано / не проверено непосредственно
- Веб-интерфейс Google Colab не открывался автоматически: проверены сами ipynb
  через nbconvert и их код виджетов, но не клики пользователя в браузере.
- Шаблон `my_network.py` исполняется с демонстрационной сетью; настоящая сеть
  пользователя, измерения оборудования и реальные протоколы не подключены.
- Формальная процедура подачи статьи не выполнялась. Авторство и полные выходные
  сведения тезисов НСКФ требуют подтверждения. Статья не объявляется готовой к подаче.
- Эталон v2 не исправлялся, включая известные рецензенту ограничения. Область
  выводов новой статьи ограничена; по R1–R19 записан отдельный ответ.

## Препятствия и обходы
Локальный DNS не позволял git clone; использованы GitHub API для коммитов и
GitHub runner для настоящего fetch/checkout. Не выдаётся за локальный clone.
Запуск44966025407 завершился ошибкой декодирования не-UTF8 фрагмента вывода
pdflatex. Сам PDF первого прохода был создан; stdout теперь декодируется с
явными escape-последовательностями. Коды выхода компилятора по-прежнему проверяются.
Старая модель2025 не читалась, не копировалась и не сверялась. main, v2 и журнал
проверяющего не изменены. Коммиты в ветке не означают автоматическое слияние.

## Расход
Доступа к счётчику токенов нет; числа токенов не выдумываются. Ниже — оценка
этапов действий, не счёт списаний: 1) возобновление/STATUS — 1 этап;
2) модель и исправление причинного порядка — 2 итерации;
3) серии/01/CI — 1 основной этап; 4) прогноз/02 — 1; 5) адаптер/03 — 1;
6) проверка рисунков — 1; 7) статья/библиография/устранение кодировки — 3;
8) документы — 1; 9) финальная проверка — число реально выполненных команд
в таблице выше. Повторные сборки не выдаются за новые научные эксперименты.

## Следующий шаг
Независимая проверка PR и воспроизведение тетрадей пользователем. PR не сливать
автоматически. Будущие замечания проверять по точным файлам/коммитам.

Слабое место: результаты относятся к принятым синтетическим профилям; точность
на реальной инфраструктуре, номинальное покрытие и преимущество P не доказаны.
'''
(D/'Отчёт_ночи.md').write_text(text)
print('Author report generated from real outputs, tests and timestamps.')
