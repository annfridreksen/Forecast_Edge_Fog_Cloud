"""Read-only numeric table for notebook/article traceability, not a new estimator.

Reads the selected saved main and an inventory of primary files. No simulation,
bootstrap, forecast or classification change. Source and hash semantics are
explicit: a verified file chain is not independent statistical acceptance.
"""
from collections import Counter
import hashlib
import math
from pathlib import Path
from .grid import digest, read_json

CELL_ID = 'r14-01-summary'
OUTPUT_PREFIX = 'R14_SUMMARY_JSON:'
POINT_UNITS = {'arrivals': 'messages', 'completed': 'messages', 'dropped': 'messages',
               'unfinished': 'messages', 'mean_ms': 'ms', 'p95_ms': 'ms',
               'H200': 'fraction', 'drop_fraction': 'fraction'}


def byte_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _inventory(root, snapshot):
    """Count unique primary requests, never journal replays.

    Join current journals to actual file names and bytes. Unvisited imported
    primaries cannot be silently assigned a seed family; refuse counts instead.
    Does not decompress/recompute observations (the primary audit is separate).
    """
    catalog = {r['key']: r['config_id'] for r in snapshot['rows']}
    entries, journals = {}, {}
    for path in sorted((root/'cells').glob('*/*.json')):
        if path.name not in ('pilot.json', 'main.json', 'confirmation.json'):
            continue
        state = read_json(path)
        if catalog.get(path.parent.name) != state['config_id']:
            raise ValueError('foreign journal in inventory')
        journals[str(path.relative_to(root))] = byte_sha(path)
        for run in state.get('runs', []):
            request = {k: run[k] for k in ('seed', 'warmup', 'observe', 'guard')}
            request['config_id'] = state['config_id']
            rel = 'observations/'+state['config_id']+'/'+digest(request)+'.json.gz'
            if rel in entries:
                continue
            seed = request['seed']
            if type(seed) is not int or seed not in (*range(10), *range(100,110), *range(200,210)):
                raise ValueError('unknown seed family')
            entries[rel] = dict(path=rel, seed=seed, byte_sha256=byte_sha(root/rel))
    actual = {str(p.relative_to(root)) for p in (root/'observations').glob('*/*.json.gz')}
    if actual != set(entries):
        raise ValueError('primary inventory and unique journal requests differ')
    phases = Counter('pilot' if 100<=e['seed']<110 else 'main' if e['seed']<10 else 'confirmation'
                     for e in entries.values())
    counts = dict(requests=len(entries), pilot=phases['pilot'], main=phases['main'],
                  confirmation=phases['confirmation'],
                  insufficient=sum(r['status']=='INSUFFICIENT_DATA' for r in snapshot['rows']),
                  missing=sum(r['status']=='NOT_CALCULATED' for r in snapshot['rows']))
    return counts, dict(primary_inventory_sha256=digest(sorted(entries.values(), key=lambda e:e['path'])),
                        journal_files_sha256=journals, unique_requests=len(entries),
                        arrays_recomputed=False, orphan_policy='refuse counts; never impute seed')


def summary_table(root, snapshot, selection, key=None):
    """Show one saved main in the selected Fog/B pair, plus snapshot counters.

    With several loads, choose the lowest available load or an explicit key.
    This is display selection only. No available main => no invented values.
    """
    root = Path(root)
    result = dict(schema='r14-notebook-summary-v1', state=snapshot['state'], rows=[],
                  scientific_acceptance=False, simulation_executed=False, bootstrap_recomputed=False)
    if snapshot['state'] != 'CHECKED_CHAINS':
        result['note'] = 'Нет проверенного архива; значения отсутствуют, не равны нулю.'
        return result
    mapping = read_json(root/'map.json')
    manifest = read_json(root/'manifest.json')
    if (digest(mapping)!=snapshot['map_sha256'] or digest(manifest)!=snapshot['manifest_sha256']
            or mapping['manifest_sha256']!=digest(manifest)):
        raise ValueError('snapshot changed since chain verification')
    result.update(map_sha256=digest(mapping), manifest_sha256=digest(manifest))
    candidates = sorted((r for r in snapshot['rows'] if r.get('main_sha256') and r.get('summary')
                         and (r['n_fog'],r['buffer'])==(selection['fog'],selection['buffer'])),
                        key=lambda r:(r['arrival_rate_s'],r['key']))
    chosen = next((r for r in candidates if r['key']==key),None) if key is not None else next(iter(candidates),None)
    if key is not None and chosen is None:
        raise ValueError('explicit main key is absent from selected Fog/B')
    if chosen is not None:
        relative = 'cells/'+chosen['key']+'/main.json'
        path = root/relative
        main = read_json(path)
        if (digest(main)!=chosen['main_sha256'] or main.get('summary')!=chosen['summary']
                or main['config_id']!=chosen['config_id'] or main['summary']['seed_ids']!=list(range(10))):
            raise ValueError('selected main changed since chain verification')
        source = dict(source_file=relative, source_byte_sha256=byte_sha(path),
                      source_canonical_sha256=digest(main))
        for field,unit in POINT_UNITS.items():
            value = main['summary']['point'][field]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError('invalid saved main value')
            result['rows'].append(dict(field='point.'+field,value=value,unit=unit,**source))
        for name in ('p95_ms','drop_fraction'):
            interval = main['summary']['intervals'][name]
            prefix = 'q_interval' if name=='p95_ms' else 'loss_interval'
            for bound in ('lower','upper'):
                result['rows'].append(dict(field=prefix+'.'+bound,value=interval[bound],
                                          unit='ms' if name=='p95_ms' else 'fraction',**source))
        result.update(selected_key=chosen['key'],status=main['status'],
                      reasons=main['summary'].get('reasons',[]),seed_ids=main['summary']['seed_ids'],
                      note='Сохранённая main-серия; интервалы номинальные, bootstrap не повторялся. '
                           'Нулевые потери и [0,0] не подтверждают риск ≤ 0,1%.')
    else:
        result.update(selected_key=None,note='Для выбранных Fog/B нет итоговой серии; main-чисел нет.')
    try:
        counts, inventory = _inventory(root,snapshot)
        result.update(inventory=inventory,counts_state='EXACT_PRIMARY_FILE_INVENTORY')
        for field,value in counts.items():
            result['rows'].append(dict(field='counts.'+field,value=value,unit='cells' if field in ('missing','insufficient') else 'requests',
                                      source_file='map.json + cells/*/{pilot,main,confirmation}.json + observations/',
                                      source_canonical_sha256=result['map_sha256'],
                                      primary_inventory_sha256=inventory['primary_inventory_sha256']))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result.update(counts_state='UNAVAILABLE',counts_note=str(exc))
    return result
