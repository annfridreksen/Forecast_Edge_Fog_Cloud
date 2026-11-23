"""R1.4 paper: verify actual TeX values against an immutable scientific snapshot.

Never simulates, changes the scientific checkpoint, recomputes bootstrap,
or rewrites an incorrect number to make a verification pass.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from efc.grid import canonical, digest, read_json
from scripts.audit_r14_cache import verify

KEY = 'r0.10_F30_B005'
# macro: (point/interval key or audited count, decimal places, stable cell ID)
SPECS = {
 'rRequests': ('counts.requests', 0, 'r14-01-summary'),
 'rPilot': ('counts.pilot', 0, 'r14-01-summary'),
 'rMain': ('counts.main', 0, 'r14-01-summary'),
 'rConfirm': ('counts.confirmation', 0, 'r14-01-summary'),
 'rInsufficient': ('counts.insufficient', 0, 'r14-01-summary'),
 'rMissing': ('counts.missing', 0, 'r14-01-summary'),
 'rArrivals': ('point.arrivals', 0, 'r14-01-summary'),
 'rCompleted': ('point.completed', 0, 'r14-01-summary'),
 'rDropped': ('point.dropped', 0, 'r14-01-summary'),
 'rUnfinished': ('point.unfinished', 0, 'r14-01-summary'),
 'rMean': ('point.mean_ms', 6, 'r14-01-summary'),
 'rQ': ('point.p95_ms', 6, 'r14-01-summary'),
 'rQlo': ('q_interval.lower', 6, 'r14-01-summary'),
 'rQhi': ('q_interval.upper', 6, 'r14-01-summary'),
 'rH': ('point.H200', 9, 'r14-01-summary'),
 'rLoss': ('point.drop_fraction', 0, 'r14-01-summary'),
}


def sha(path):
    return hashlib.file_digest(Path(path).open('rb'), 'sha256').hexdigest()


def make_evidence(checkpoint):
    """Validate all primary hashes; independently recompute main points only."""
    root = Path(checkpoint)
    audit = verify(root)
    mapping, manifest = read_json(root/'map.json'), read_json(root/'manifest.json')
    if mapping['manifest_sha256'] != digest(manifest):
        raise ValueError('manifest identity mismatch')
    row = next(r for r in mapping['rows'] if r['key'] == KEY)
    main_path = root/'cells'/KEY/'main.json'
    main = read_json(main_path)
    pilot = read_json(root/'cells'/KEY/'pilot.json')
    if (digest(main) != row['main_sha256'] or main['summary'] != row['summary']
        or main['plan_sha256'] != pilot['plan_sha256']
        or digest(pilot['plan']) != pilot['plan_sha256'] or pilot['status'] != 'READY'):
        raise ValueError('broken map/main/pilot evidence chain')
    if main['summary']['seed_ids'] != list(range(10)):
        raise ValueError('main seeds must be exactly 0..9')
    arrays, records = [], []
    arrivals = dropped = unfinished = 0
    for run in main['runs']:
        request = {k: run[k] for k in ('seed','warmup','observe','guard')}
        request['config_id'] = main['config_id']
        path = root/'observations'/main['config_id']/(digest(request)+'.json.gz')
        raw = json.loads(gzip.decompress(path.read_bytes()))
        if raw['request'] != request or raw['sha256'] != digest(raw['observation']):
            raise ValueError('primary identity mismatch')
        full = raw['observation']['full']
        values = np.asarray(full['latency_ticks'], dtype=np.int64)
        if full['arrivals'] != len(values)+full['dropped']+full['unfinished']:
            raise ValueError('primary balance mismatch')
        arrays.append(values)
        arrivals += full['arrivals']; dropped += full['dropped']; unfinished += full['unfinished']
        records.append(dict(path=str(path.relative_to(root)), byte_sha256=sha(path), request=request))
    delays = np.concatenate(arrays)
    point = dict(arrivals=arrivals, completed=len(delays), dropped=dropped, unfinished=unfinished,
                 mean_ms=float(delays.mean()/1e6), p95_ms=float(np.quantile(delays,.95,method='linear')/1e6),
                 drop_fraction=dropped/arrivals, H200=int((delays<=200_000_000).sum())/arrivals)
    for name, value in point.items():
        if not np.isclose(value, main['summary']['point'][name], rtol=0, atol=1e-9):
            raise ValueError('main point differs from primary ticks: '+name)
    phases = Counter()
    for path in (root/'observations').glob('*/*.json.gz'):
        seed = json.loads(gzip.decompress(path.read_bytes()))['request']['seed']
        phases['pilot' if 100<=seed<=109 else 'main' if 0<=seed<=9 else 'confirmation' if 200<=seed<=209 else 'unknown']+=1
    if phases['unknown']:
        raise ValueError('unexpected seed family')
    return dict(schema='R1.4-paper-evidence-1', scientific_run_id=45174257711,
                artifact_id=14820151165, scientific_sha='b45bfee84d9b0727243faf6cd28eeda776813566',
                zip_sha256='2cb91dbc964a641c36fb53e02ddea3590bf8fe939933f43b31399267508d40ef',
                frozen_snapshot=True, manifest_sha256=digest(manifest),map_sha256=digest(mapping),
                main_path=str(main_path.relative_to(root)),main_byte_sha256=sha(main_path),
                main_canonical_sha256=digest(main),status=main['status'],reasons=main['summary']['reasons'],
                config_id=main['config_id'],plan_sha256=main['plan_sha256'],primary=records,
                point=point,q_interval=main['summary']['intervals']['p95_ms'],
                loss_interval=main['summary']['intervals']['drop_fraction'],
                counts=dict(requests=audit['unique_primary_observations'],pilot=phases['pilot'],main=phases['main'],
                            confirmation=phases['confirmation'],insufficient=audit['map_statuses'].get('INSUFFICIENT_DATA',0),
                            missing=audit['map_statuses'].get('NOT_CALCULATED',0)),
                intervals_recomputed=False,points_recomputed_from_ticks=True,scientific_acceptance=False)


def get(data, dotted):
    for part in dotted.split('.'):
        data = data[part]
    return data


def values_tex(evidence):
    lines = ['% Empirical values of a FROZEN snapshot; checked, not refreshed during build.']
    for macro,(field,places,_) in SPECS.items():
        text = f'{get(evidence,field):.{places}f}'.replace('.',',')
        lines.append('\\newcommand{\\'+macro+'}{'+text+'}')
    return '\n'.join(lines)+'\n'


def verify_text(evidence, value_text, paper, bibliography):
    if value_text != values_tex(evidence):
        raise ValueError('actual TeX numeric values differ from primary evidence')
    if paper.count('\\section{') != 7:
        raise ValueError('R1.4 requires seven sections')
    if any(token in paper+bibliography for token in ('\\misc ', 'TODO', '@@')):
        raise ValueError('unsupported legacy macro or unfinished placeholder')
    for name in SPECS:
        if '\\'+name+'{}' not in paper:
            raise ValueError('registered value not used in actual manuscript: '+name)
    labels = re.findall(r'\\label\{([^}]+)\}',paper)
    refs = re.findall(r'\\(?:eqref|ref)\{([^}]+)\}',paper)
    if len(labels)!=len(set(labels)) or not set(refs)<=set(labels):
        raise ValueError('broken labels/references')
    used = {k for g in re.findall(r'\\cite\{([^}]+)\}',paper) for k in g.split(',')}
    listed = re.findall(r'\\R?Bibitem\{([^}]+)\}',bibliography)
    if set(listed)!=used or len(listed)!=len(set(listed)) or not 12<=len(listed)<=15:
        raise ValueError('bibliography correspondence/count mismatch')
    if evidence['status']!='INSUFFICIENT_DATA' or evidence['scientific_acceptance']:
        raise ValueError('this frozen partial article must not claim acceptance')
    return dict(checked_values=len(SPECS),bibliography_entries=len(listed),sections=7,
                actual_manuscript_checked=True,bootstrap_recomputed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path)
    p.add_argument('--initialize',action='store_true',help='explicitly freeze initial evidence; never a verification fix')
    p.add_argument('--out',type=Path,default=ROOT/'results/r14/current/paper')
    a=p.parse_args()
    evidence_path=ROOT/'results/r14/article_evidence.json'
    if a.initialize:
        if a.checkpoint is None or evidence_path.exists():
            p.error('initialize needs checkpoint and absent evidence; no silent refresh')
        e=make_evidence(a.checkpoint)
        evidence_path.write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n')
        (ROOT/'article/r14-values.tex').write_text(values_tex(e))
    evidence=read_json(evidence_path)
    if a.checkpoint is not None and not a.initialize and make_evidence(a.checkpoint)!=evidence:
        raise ValueError('frozen evidence differs from supplied primary archive')
    receipt=verify_text(evidence,(ROOT/'article/r14-values.tex').read_text(),
                        (ROOT/'article/main.tex').read_text(),(ROOT/'article/r14-references.tex').read_text())
    receipt.update(primary_archive_checked=a.checkpoint is not None, simulation_executed=False,
                   evidence_sha256=sha(evidence_path), cell_outputs_checked=False,
                   cell_trace_note='Use scripts/check_r14_trace.py for executed notebook proof')
    a.out.mkdir(parents=True,exist_ok=True)
    index=[dict(macro=name,evidence_field=field,source_file=evidence['main_path'] if not field.startswith('counts.') else 'map.json / observations/',source_sha256=evidence['main_byte_sha256'] if not field.startswith('counts.') else evidence['map_sha256'],cell_id=cell,article_location='section 4 / table 2' if not field.startswith('counts.') else 'section 4.1',decimal_places=places) for name,(field,places,cell) in SPECS.items()]
    (a.out/'claim-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    (a.out/'number-check.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':main()
