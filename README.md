# Forecast_Edge_Fog_Cloud — FEFC R1.5

Рабочая ветка — `night/fefc-v3`, PR #2 без слияния. `v2/` — защищённый исторический эталон. Результаты имитации получены на искусственно сформированных данных, не на измерениях оборудования.

## Начать без программирования

1. [Открыть принятый PDF статьи ПСТА (v3)](https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/blob/c20aaa889337d23e2ab34033fe735ee5e0e905f9/deliverables/r15-visual-final/%D0%A1%D1%82%D0%B0%D1%82%D1%8C%D1%8F_FEFC_R15_v3_%D0%9F%D0%A1%D0%A2%D0%90.pdf) или [комплект W/P/F](https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/tree/c20aaa889337d23e2ab34033fe735ee5e0e905f9/deliverables/r15-visual-final). Срез статьи зафиксирован в `c20aaa889337d23e2ab34033fe735ee5e0e905f9`. Техническая и редакционная приёмка: [Issue #5, итог 25.11.2026](https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/issues/5#issuecomment-7154455723). Личные поля и решение об отправке остаются за авторами. Поздняя редакция v4 в этот комплект не включена.
2. Открыть [пошаговую инструкцию](docs/Как_пользоваться.md), затем [00 — Старт](https://colab.research.google.com/github/annfridreksen/Forecast_Edge_Fog_Cloud/blob/c20aaa889337d23e2ab34033fe735ee5e0e905f9/colab/00_%D0%A1%D1%82%D0%B0%D1%80%D1%82.ipynb). Сначала зафиксировать контрольный SHA выполняемого кода; не выбирать «Выполнить всё», если требуется только схема.
3. [01 — Среда и сохранённая карта](https://colab.research.google.com/github/annfridreksen/Forecast_Edge_Fog_Cloud/blob/c20aaa889337d23e2ab34033fe735ee5e0e905f9/colab/01_%D0%A1%D1%80%D0%B5%D0%B4%D0%B0_%D0%B8_%D0%BA%D0%BE%D0%BD%D1%84%D0%B8%D0%B3%D1%83%D1%80%D0%B0%D1%86%D0%B8%D1%8F.ipynb) читает сохранённую карту и итоговую серию; для сверки статьи подключить [замороженный архив](https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/actions/runs/45174257711/artifacts/14820151165).
4. [02 — Интерфейсы прогнозирования](https://colab.research.google.com/github/annfridreksen/Forecast_Edge_Fog_Cloud/blob/c20aaa889337d23e2ab34033fe735ee5e0e905f9/colab/02_%D0%9F%D1%80%D0%BE%D0%B3%D0%BD%D0%BE%D0%B7_%D0%B8_%D0%BD%D0%B5%D0%B9%D1%80%D0%BE%D1%81%D0%B5%D1%82%D1%8C.ipynb) описывает будущие интерфейсы; обучение и численные прогнозы не выполняются. [03 — Концепция переразмещения](https://colab.research.google.com/github/annfridreksen/Forecast_Edge_Fog_Cloud/blob/c20aaa889337d23e2ab34033fe735ee5e0e905f9/colab/03_%D0%90%D0%BB%D0%B3%D0%BE%D1%80%D0%B8%D1%82%D0%BC_%D0%BF%D0%B5%D1%80%D0%B5%D1%80%D0%B0%D0%B7%D0%BC%D0%B5%D1%89%D0%B5%D0%BD%D0%B8%D1%8F.ipynb) показывает концепцию целых подграфов, не запускает контроллер и эталон v2.

В 00 выполнение всей тетради запускает короткий демонстрационный опыт, ручной пример и пример отключения датчика. Это не итоговая статистическая серия. Для просмотра статьи и её чисел новые опыты не нужны.

## Границы и состояние

p95 — квантиль уровня 0,95 времени пребывания завершённых сообщений в системе; доля потерь учитывает все поступления. Наблюдённые нулевые потери не доказывают нулевого риска. Проверена одна итоговая конфигурация с оговорённым статистическим допущением; минимум всей сетки не доказан. Прогнозное переразмещение — концептуальная часть.

[Текущее состояние](docs/STATUS.md) · [Задание](docs/TASK.md). Личный веб-запуск Colab пока не подтверждён. Сохранённые технические проверки не равнозначны проверке виджетов в личном браузере.

## Исторический маршрут (не использовать для сверки R1.5)

Старые `colab/clean/`, `article/main.pdf`, команды обучения и полной генерации `scripts/build_artifacts.py` относятся к прежнему этапу. [Прежняя инструкция](https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/blob/c20aaa889337d23e2ab34033fe735ee5e0e905f9/README.md) сохранена в истории. Полная генерация перезаписывает генерируемые каталоги; не запускать её для авторского просмотра.
