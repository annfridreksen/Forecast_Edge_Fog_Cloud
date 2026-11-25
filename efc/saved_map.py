"""Read-only validation of every displayed map row, never a statistical rerun.

Fail closed for the entire snapshot: no neighbour may lend an unchecked status
or summary to a heatmap/curve. Hash/identity checks do not repeat the primary
array audit or certify nominal confidence coverage.
"""
from dataclasses import replace
from pathlib import Path
from .grid import VERSION, config_key, digest, read_json
from .model import Config
from .primary import PrimarySampler
from .statistics import classify

MAP_STATUSES = ('NOT_CALCULATED', 'ACCEPTABLE', 'UNACCEPTABLE', 'INSUFFICIENT_DATA')


def _checked_row(root, meta, row):
    config = Config(**meta['config'])
    key = config_key(config)
    if key != meta['key'] or key != row['key']:
        raise ValueError('Ключ клетки не соответствует конфигурации')
    for field in ('arrival_rate_s', 'n_fog', 'buffer'):
        if row[field] != meta[field] or meta[field] != getattr(config, field):
            raise ValueError('Координаты карты не соответствуют конфигурации: '+key)
    current_id = PrimarySampler(config).config_id
    if meta['config_id'] != current_id or row['config_id'] != current_id:
        raise ValueError('Checkpoint относится к другой версии модели или параметрам: '+key)
    folder = root/'cells'/key
    summary = None
    if row.get('main_sha256'):
        main, pilot = read_json(folder/'main.json'), read_json(folder/'pilot.json')
        if (row['status'] == 'NOT_CALCULATED' or digest(main) != row['main_sha256']
                or main['config_id'] != current_id or main['phase'] != 'main'
                or main['status'] != row['status'] or pilot['status'] != 'READY'
                or pilot['config_id'] != current_id or pilot['plan']['config_id'] != current_id
                or digest(pilot['plan']) != pilot['plan_sha256']
                or main['plan_sha256'] != pilot['plan_sha256']
                or main.get('summary') != row.get('summary')):
            raise ValueError('Нарушена цепочка map → main → frozen pilot: '+key)
        plan = pilot['plan']
        if (plan['pilot_seeds'] != list(range(100, 110)) or plan['main_seeds'] != list(range(10))
                or plan['confirmation_seeds'] != list(range(200, 210))):
            raise ValueError('Изменены группы seed: '+key)
        summary = main.get('summary')
        if summary is not None:
            if summary['seed_ids'] != list(range(10)):
                raise ValueError('Сохранённая оценка не содержит итоговые seed 0–9: '+key)
            if classify(summary, warmup_ok=True) != row['status']:
                raise ValueError('Статус не соответствует совместному правилу Q/L: '+key)
        elif row['status'] != 'INSUFFICIENT_DATA':
            raise ValueError('Нет итоговой оценки для заявленного статуса: '+key)
    elif row['status'] in ('ACCEPTABLE', 'UNACCEPTABLE') or row.get('summary') is not None:
        raise ValueError('Нет первичного итогового журнала для заявленной оценки: '+key)
    elif row['status'] == 'INSUFFICIENT_DATA':
        pilot = read_json(folder/'pilot.json')
        if (digest(pilot) != row.get('pilot_sha256') or pilot['config_id'] != current_id
                or pilot['status'] != 'INSUFFICIENT_DATA'):
            raise ValueError('Нет подтверждённой остановки пилота: '+key)
    return {**row, 'summary': summary, 'display_chain_checked': True}


def saved_cell(root, config):
    root = Path(root)
    empty = dict(status='NOT_CALCULATED', summary=None, source=str(root), rows=[],
                 checked_rows=0, verification='NO_CHECKPOINT')
    if not (root/'map.json').exists():
        return {**empty, 'note': 'Статистический checkpoint не загружен. Это не нулевые результаты.'}
    manifest, mapping = read_json(root/'manifest.json'), read_json(root/'map.json')
    if (mapping['manifest_sha256'] != digest(manifest) or manifest['version'] != VERSION
            or mapping['version'] != VERSION):
        raise ValueError('Хеш или версия карты и manifest не согласованы')
    catalog = {r['key']: r for r in manifest['catalog']}
    rows = {r['key']: r for r in mapping['rows']}
    if (len(catalog) != len(manifest['catalog']) or len(rows) != len(mapping['rows'])
            or set(catalog) != set(rows) or any(r['status'] not in MAP_STATUSES for r in rows.values())):
        raise ValueError('Неверный каталог/статусы карты')
    # Validate ALL cells, even those outside the selected rate or buffer.
    checked = {key: _checked_row(root, meta, rows[key]) for key, meta in catalog.items()}
    key = config_key(config)
    if key not in catalog or catalog[key]['arrival_rate_s'] != config.arrival_rate_s:
        return {**empty, 'note': 'Эта интенсивность отсутствует в сохранённой сетке.'}
    if catalog[key]['config_id'] != PrimarySampler(config).config_id:
        raise ValueError('Выбранные параметры не соответствуют сохранённой конфигурации')
    row = checked[key]
    return dict(status=row['status'], summary=row['summary'], source=str(root/'cells'/key),
                rows=list(checked.values()), checked_rows=len(checked),
                verification='ALL_DISPLAY_CHAINS_CHECKED',
                note='Сохранённый результат, не новый расчёт. Проверены ссылки, версии, хеши '
                'и правило Q/L для всех отображаемых клеток. Bootstrap и первичные массивы '
                'не пересчитываются; проверка цепочки не заменяет научную приёмку.')
