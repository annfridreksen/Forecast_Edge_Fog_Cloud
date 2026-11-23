"""Deterministic read-only checkpoint report from verified *primary* observations.

Replay journal rows are never additional scientific realizations. Does not
repair journals, open confirmation seeds, recalculate configurations or change
R1.4 statistics. No scientific acceptance follows from this report.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_r14_cache import verify
from efc.grid import canonical, read_json


def checkpoint_report(root: Path, *, artifact_id=None, zip_sha256=None) -> dict:
    root = Path(root)
    integrity = verify(root)
    catalog = read_json(root/'manifest.json')['catalog']
    by_id = {r['config_id']: r for r in catalog}
    by_key = {r['key']: r for r in read_json(root/'map.json')['rows']}
    primary = defaultdict(set)
    source_hashes = defaultdict(set)
    for path in sorted((root/'observations').glob('*/*.json.gz')):
        data = json.loads(gzip.decompress(path.read_bytes()))
        req, obj = data['request'], data['observation']
        ident = (req['seed'], req['warmup'], req['observe'], req['guard'])
        primary[req['config_id']].add(ident)
        source_hashes[req['config_id']].add(obj['provenance']['workload_sha256'])

    journal = defaultdict(list)
    for path in sorted((root/'cells').glob('*/*.json')):
        if path.name not in ('pilot.json','main.json','confirmation.json'):
            continue
        state = read_json(path)
        cid = state['config_id']
        for r in state.get('runs', []):
            journal[cid].append((r['seed'],r['warmup'],r['observe'],r['guard']))

    touched=[]
    orphaned=0
    for cid in sorted(primary, key=lambda c: by_id[c]['key']):
        meta = by_id[cid]
        rows = primary[cid]
        journal_set = set(journal[cid])
        extra = rows-journal_set
        orphaned += len(extra)
        by_phase = lambda lo,hi: sorted({seed for seed,_,_,_ in rows if lo<=seed<=hi})
        touched.append(dict(key=meta['key'], config_id=cid,
                            map_status=by_key[meta['key']]['status'],
                            unique_primary_requests=len(rows),
                            journal_rows=len(journal[cid]),
                            journal_unique_requests=len(journal_set),
                            replay_rows=len(journal[cid])-len(journal_set),
                            primary_not_yet_in_journal=len(extra),
                            distinct_pilot_seeds=by_phase(100,109),
                            distinct_main_seeds=by_phase(0,9),
                            distinct_confirmation_seeds=by_phase(200,209),
                            distinct_workload_sha256_count=len(source_hashes[cid])))

    if sum(x['unique_primary_requests'] for x in touched) != integrity['unique_primary_observations']:
        raise ValueError('primary summary conflicts with audited totals')
    if sum(x['replay_rows'] for x in touched) != integrity['journal_duplicate_rows']:
        raise ValueError('journal summary conflicts with audited totals')
    return dict(schema='r14-cache-normalized-report-v1',
                scope='verified primary data only; NO scientific cell acceptance',
                source_artifact_id=artifact_id, source_zip_sha256=zip_sha256,
                report_is_read_only=True, integrity=integrity,
                touched_cells=len(touched),
                cells_unresolved=integrity['map_cells']-sum(
                    n for status,n in integrity['map_statuses'].items()
                    if status in ('ACCEPTABLE','UNACCEPTABLE','INSUFFICIENT_DATA')),
                primary_without_journal_row=orphaned,
                touched=touched)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--artifact-id', type=int)
    p.add_argument('--zip-sha256')
    args=p.parse_args()
    if args.output is not None and args.output.resolve().is_relative_to(args.root.resolve()):
        p.error('output must remain outside immutable scientific checkpoint')
    report=checkpoint_report(args.root, artifact_id=args.artifact_id,
                             zip_sha256=args.zip_sha256)
    data=canonical(report)+b'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(data)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
