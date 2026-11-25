"""Read-only R1.4 checkpoint audit. Replay log rows are NOT independent runs.

Checks JSON checksums, cohort balance, fixed input pairing, and unique
(config_id, seed, W, T, G) observations without modifying the checkpoint.
This audit does not certify statistical stationarity or a complete map.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from efc.grid import digest


def verify(root: Path) -> dict:
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    mapping = {r['config_id']: r for r in manifest['catalog']}
    if len(mapping) != len(manifest['catalog']):
        raise ValueError('duplicate config_id in manifest')
    map_rows = json.loads((root/'map.json').read_text(encoding='utf-8'))['rows']
    if {r['key'] for r in manifest['catalog']} != {r['key'] for r in map_rows}:
        raise ValueError('map/catalog keys differ')

    verified = set()
    workloads = {}
    paired_matches = 0
    counts = Counter()
    for path in sorted((root/'observations').glob('*/*.json.gz')):
        data = json.loads(gzip.decompress(path.read_bytes()))
        req, obj = data['request'], data['observation']
        ident = (req['config_id'], req['seed'], req['warmup'], req['observe'], req['guard'])
        if req['config_id'] not in mapping or path.parent.name != req['config_id']:
            raise ValueError(f'foreign checkpoint: {path}')
        if path.stem != digest(req) + '.json':
            raise ValueError(f'checkpoint filename mismatch: {path}')
        if data['sha256'] != digest(obj) or obj['provenance']['config_id'] != req['config_id']:
            raise ValueError(f'checkpoint checksum/provenance mismatch: {path}')
        if ident in verified:
            raise ValueError(f'duplicate primary observation: {ident}')
        verified.add(ident)
        full, first, second = (obj[k] for k in ('full', 'first', 'second'))
        for cohort in (full, first, second):
            if cohort['seed'] != req['seed'] or any(type(cohort[k]) is not int or cohort[k] < 0 for k in ('arrivals', 'dropped', 'unfinished')):
                raise ValueError(f'invalid cohort counts/seed: {path}')
            if cohort['arrivals'] != cohort['dropped'] + cohort['unfinished'] + len(cohort['latency_ticks']):
                raise ValueError(f'cohort balance mismatch: {path}')
        for k in ('arrivals', 'dropped', 'unfinished'):
            if full[k] != first[k] + second[k]:
                raise ValueError(f'cohort halves mismatch: {path}')
        if sorted(full['latency_ticks']) != sorted(first['latency_ticks'] + second['latency_ticks']):
            raise ValueError(f'cohort latency partition mismatch: {path}')
        rate = mapping[req['config_id']]['arrival_rate_s']
        source_key = (rate, req['seed'], req['warmup'], req['observe'], req['guard'])
        signature = obj['provenance']['workload_sha256']
        if source_key in workloads:
            if workloads[source_key] != signature:
                raise ValueError(f'paired input mismatch: {source_key}')
            paired_matches += 1
        else:
            workloads[source_key] = signature
        counts['arrivals'] += full['arrivals']
        counts['dropped'] += full['dropped']
        counts['unfinished'] += full['unfinished']

    journal_rows = 0
    duplicates = 0
    journal_unique = set()
    missing_primary = set()
    for path in sorted((root/'cells').glob('*/*.json')):
        if path.name not in ('pilot.json', 'main.json', 'confirmation.json'):
            continue
        state = json.loads(path.read_text(encoding='utf-8'))
        config_id = state['config_id']
        for row in state.get('runs', []):
            ident = (config_id, row['seed'], row['warmup'], row['observe'], row['guard'])
            journal_rows += 1
            if ident in journal_unique:
                duplicates += 1
            journal_unique.add(ident)
            if ident not in verified:
                missing_primary.add(ident)
    if missing_primary:
        raise ValueError(f'journal rows lack verified primary checkpoints: {len(missing_primary)}')
    statuses = Counter(r['status'] for r in map_rows)
    return {
        'scope': 'read-only integrity audit; NOT statistical acceptance',
        'manifest_cells': len(manifest['catalog']),
        'map_cells': len(map_rows),
        'map_statuses': dict(statuses),
        'unique_primary_observations': len(verified),
        'primary_completed_seed_repetitions': sum(ident[1] in range(10) for ident in verified),
        'journal_rows': journal_rows,
        'journal_unique_requests': len(journal_unique),
        'journal_duplicate_rows': duplicates,
        'journal_missing_primary': 0,
        'paired_source_rechecks': paired_matches,
        'full_arrivals_sum_for_integrity_only': counts['arrivals'],
        'full_dropped_sum_for_integrity_only': counts['dropped'],
        'full_unfinished_sum_for_integrity_only': counts['unfinished'],
        'interpretation': 'duplicates are not independent runs; do not pool cross-configuration arrivals as a cohort'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', type=Path, help='optional report outside checkpoint root')
    args = parser.parse_args()
    if args.output is not None and args.output.resolve().is_relative_to(args.root.resolve()):
        parser.error('report must be outside the immutable checkpoint directory')
    report = verify(args.root)
    content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    print(content, end='')


if __name__ == '__main__':
    main()
