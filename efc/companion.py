"""Read-only companion views. No simulation, forecasting or plan application.

TASK R1.4 §§6–7; the historical v2 key is read, never imported or executed.
The caller distinguishes evidence-chain validation from statistical acceptance.
"""
from collections import Counter
from pathlib import Path
import ast
import hashlib
import math
from .model import Config
from .saved_map import saved_cell
from .grid import read_json, digest


def overview(root):
    """Validate every displayed row; absent/broken archives never supply numbers."""
    root = Path(root)
    try:
        if not (root / 'map.json').exists():
            return dict(state='NO_CHECKPOINT', rows=[], counts={}, note='Архив не загружен; это не нули.')
        manifest = read_json(root / 'manifest.json')
        result = saved_cell(root, Config(**manifest['catalog'][0]['config']))
        if result['verification'] != 'ALL_DISPLAY_CHAINS_CHECKED':
            raise ValueError('Нет проверенного снимка')
        result.update(state='CHECKED_CHAINS', counts=dict(Counter(r['status'] for r in result['rows'])),
                      manifest_sha256=digest(manifest), map_sha256=digest(read_json(root / 'map.json')))
        return result
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return dict(state='ARCHIVE_UNVERIFIED', rows=[], counts={}, note=str(exc))


def curve_points(snapshot, metric, fog, buffer):
    """Return only saved main estimates WITH intervals; never interpolate gaps."""
    if metric not in ('p95_ms', 'drop_fraction'):
        raise ValueError('Неизвестная метрика')
    if snapshot['state'] != 'CHECKED_CHAINS':
        return []
    points = []
    for row in snapshot['rows']:
        if (row['n_fog'], row['buffer']) != (fog, buffer):
            continue
        summary = row.get('summary')
        if not row.get('main_sha256') or summary is None:
            continue
        ci = summary.get('intervals', {}).get(metric)
        value = summary.get('point', {}).get(metric)
        if ci is None or value is None:
            continue
        values = (ci['lower'], value, ci['upper'])
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Некорректные значения оценки/интервала')
        if ci['lower'] > ci['upper'] or (metric == 'drop_fraction' and max(values) > 1):
            raise ValueError('Некорректные границы интервала')
        points.append(dict(rho50=row['arrival_rate_s'] * .055 / 50, value=value,
                           lower=ci['lower'], upper=ci['upper'], key=row['key'],
                           source='cells/' + row['key'] + '/main.json', sha256=row['main_sha256']))
    return sorted(points, key=lambda r: r['rho50'])


def curve_figure(snapshot, metric, fog=50, buffer=5):
    import matplotlib.pyplot as plt
    points = curve_points(snapshot, metric, fog, buffer)
    factor = 100 if metric == 'drop_fraction' else 1
    fig, ax = plt.subplots(figsize=(8, 3.2))
    for p in points:
        ax.plot([p['rho50']] * 2, [factor*p['lower'], factor*p['upper']], '-')
        ax.plot(p['rho50'], factor*p['value'], 'o')
    if not points:
        ax.text(.5, .5, 'Нет итоговых оценок с ДИ; нули не подставляются', transform=ax.transAxes, ha='center')
    ax.set(xlabel='Предложенная нагрузка ρ50', ylabel='Потери, %' if factor == 100 else 'p95, мс',
           title=f'Сохранённые итоговые оценки · Fog={fog}, B={buffer}', xlim=(.05, 1))
    fig.tight_layout()
    return fig


PORTS = (
    dict(id='configuration', inputs='λ, число Fog, B, версия профилей, область применимости',
         outputs='p95 (мс); потери (доля)', missing='Обучающие/отложенные данные и калибровка'),
    dict(id='overflow', inputs='Очередь, занятость, поток; определение события и горизонт',
         outputs='Риск переполнения (вероятность)', missing='Горизонт, разметка события и калибровка'),
    dict(id='sensor_failure', inputs='Телеметрия, heartbeat, размеченные отказы и горизонт',
         outputs='Риск отказа (вероятность)', missing='Подтверждённые данные об отказах и калибровка'),
)


def port_contracts():
    return [{**p, 'status': 'NOT_IMPLEMENTED', 'estimate': None} for p in PORTS]


def invoke_port(port, payload):
    """Explicitly disabled, including when historical weights exist on disk."""
    if port not in {p['id'] for p in PORTS}:
        raise ValueError('Неизвестный порт')
    raise NotImplementedError('R1.4: прогноз не выполняется; числового выхода нет')


def reference_fragments(root):
    """Verify protected v2 search bytes against its manifest, then read AST only."""
    root = Path(root)
    path = root / 'v2/code/bt26/search.py'
    entries = [line.split() for line in (root / 'v2/MANIFEST.sha256').read_text().splitlines() if line.strip()]
    expected = [h for h, name in entries if name == './code/bt26/search.py']
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(expected) != 1 or expected[0] != actual:
        raise ValueError('Не подтверждены байты эталона v2')
    text = path.read_text()
    functions = {n.name: ast.get_source_segment(text, n) for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    return dict(path='v2/code/bt26/search.py', sha256=actual,
                fragments={name: functions[name] for name in ('command_vector', 'key')}, executed=False)


def symbolic_placement():
    return dict(members={'A': ('a1', 'a2'), 'B': ('b',), 'C': ('c',)},
                before={'A': 'E1', 'B': 'F1', 'C': 'F1'},
                after={'A': 'E1', 'B': 'E2', 'C': 'F1'},
                candidates=('E1', 'E2', 'F1'), dependencies=(('A', 'B'), ('B', 'C')),
                partition_changed=False, plan_verified=False, controller_executed=False)


def check_symbolic(spec):
    """Check the drawing's structure only, NOT resource/network/time feasibility."""
    members = spec['members']
    vertices = [v for block in members.values() for v in block]
    if not members or any(not block for block in members.values()) or len(vertices) != len(set(vertices)):
        raise ValueError('Неверное фиксированное разбиение')
    if any(not isinstance(d, str) or not d.startswith(('E', 'F')) for d in spec['candidates']):
        raise ValueError('В условных кандидатах только Edge/Fog')
    for name in ('before', 'after'):
        if set(spec[name]) != set(members) or not set(spec[name].values()) <= set(spec['candidates']):
            raise ValueError('Назначаются только целые подграфы')
    if any(a not in members or b not in members for a, b in spec['dependencies']):
        raise ValueError('Неизвестная зависимость')
    if spec['partition_changed'] or spec['plan_verified'] or spec['controller_executed']:
        raise ValueError('Схема не является проверенным планом или исполнением')
    return True


def concept_figure(kind):
    """Text-labelled conceptual diagram; no numeric forecast or timing output."""
    import matplotlib.pyplot as plt
    if kind == 'ports':
        labels = ['Параметры / наблюдения\nс версиями и единицами',
                  'Будущий сменный оцениватель\nНЕ РЕАЛИЗОВАН',
                  'Будущие p95 / потери / риск\nСЕЙЧАС ЧИСЛОВОГО ВЫХОДА НЕТ']
        footer = 'Преобразование p95/риска в порядковые команды требует отдельного адаптера и проверки.'
    elif kind == 'placement':
        check_symbolic(symbolic_placement())
        labels = ['Снимок среды → будущий прогноз', 'Проверка применимости порядковых команд',
                  'Поиск назначений целых подграфов', 'Проверка полного плана: ресурсы, связи, срок',
                  'Сравнение допустимых: (R, T, N, id)', 'Выбранный план / допустимый план не найден']
        footer = 'СХЕМА, НЕ КОНТРОЛЛЕР. Нет команд → базовый режим; предел поиска ≠ доказанная невозможность.'
    else:
        raise ValueError('Неизвестная схема')
    fig, ax = plt.subplots(figsize=(11, 1.1*len(labels)+1.2)); ax.axis('off')
    for i, label in enumerate(labels):
        ax.text(.5, len(labels)-i, label, ha='center', va='center', fontsize=11,
                bbox=dict(boxstyle='round,pad=.5', fill=False))
        if i+1 < len(labels):
            ax.annotate('', xy=(.5, len(labels)-i-.73), xytext=(.5, len(labels)-i-.28), arrowprops=dict(arrowstyle='->'))
    ax.text(.5, .1, footer, ha='center', va='center', fontsize=9)
    ax.set(xlim=(0, 1), ylim=(-.3, len(labels)+.6)); fig.tight_layout()
    return fig
