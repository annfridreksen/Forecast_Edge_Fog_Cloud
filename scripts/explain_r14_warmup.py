"""Read-only loss-interval diagnostic; no simulation or scientific reclassification."""
from pathlib import Path
import argparse
import gzip
import json
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from efc.grid import digest, read_json


def explain(root, key):
    root = Path(root)
    manifest, mapping = read_json(root/'manifest.json'), read_json(root/'map.json')
    if mapping['manifest_sha256'] != digest(manifest):
        raise ValueError('manifest mismatch')
    row = next(r for r in mapping['rows'] if r['key'] == key)
    pilot = read_json(root/'cells'/key/'pilot.json')
    if row['pilot_sha256'] != digest(pilot) or row['config_id'] != pilot['config_id']:
        raise ValueError('pilot chain mismatch')
    decision = pilot['decisions'][-1]
    if decision['action'] != 'stop_warmup_limit':
        raise ValueError('expected terminal warmup diagnostic')
    selected = []
    sources = []
    for warmup in (decision['warmup'], decision['comparison_warmup']):
        observations = []
        for seed in range(100, 110):
            request = dict(config_id=pilot['config_id'], seed=seed, warmup=warmup,
                           observe=decision['observe'], guard=decision['guard'])
            path = root/'observations'/pilot['config_id']/(digest(request)+'.json.gz')
            data = json.loads(gzip.decompress(path.read_bytes()))
            obj = data['observation']
            if data['request'] != request or data['sha256'] != digest(obj):
                raise ValueError('primary checksum/request mismatch')
            for part in ('full', 'first', 'second'):
                c = obj[part]
                if (c['seed'] != seed or c['unfinished'] != 0 or c['arrivals'] <= 0
                        or c['arrivals'] != c['dropped']+len(c['latency_ticks'])):
                    raise ValueError('invalid diagnostic cohort')
            observations.append({p: {k: obj[p][k] for k in ('arrivals', 'dropped')}
                                 for p in ('full', 'first', 'second')})
            sources.append(dict(path=str(path.relative_to(root)), observation_sha256=data['sha256']))
        selected.append(observations)
    counts = np.random.default_rng(20261123).multinomial(10, np.full(10, .1), size=10000)
    def losses(rows, part):
        a = np.array([r[part]['arrivals'] for r in rows], dtype=np.int64)
        d = np.array([r[part]['dropped'] for r in rows], dtype=np.int64)
        return (counts @ d)/(counts @ a)
    checks = {}
    for name, delta in (
            ('warmup_check', losses(selected[1], 'full')-losses(selected[0], 'full')),
            ('halves_check', losses(selected[1], 'second')-losses(selected[1], 'first'))):
        measured = np.quantile(delta, [.025, .975], method='linear')
        stored = decision[name]['intervals']['drop_fraction']
        if not np.allclose(measured, [stored['lower'], stored['upper']], rtol=0, atol=1e-15):
            raise ValueError('loss interval does not reproduce')
        checks[name] = dict(stored=stored, recomputed_lower=float(measured[0]),
                            recomputed_upper=float(measured[1]),
                            within_tolerance=bool(-stored['epsilon'] <= measured[0]
                                                  and measured[1] <= stored['epsilon']),
                            contains_zero=bool(measured[0] <= 0 <= measured[1]),
                            p95_interval_read_not_recomputed=decision[name]['intervals']['p95_ms'])
    return dict(schema='R1.4-warmup-explanation-1', read_only=True,
                simulation_calls=0, scientific_status_unchanged=row['status'],
                key=key, config_id=row['config_id'], manifest_sha256=digest(manifest),
                pilot_sha256=digest(pilot), warmup=decision['warmup'],
                comparison_warmup=decision['comparison_warmup'], observe=decision['observe'],
                guard=decision['guard'], units='W/T/G: expected arrivals per reference Fog; loss: fraction',
                seed_ids=list(range(100, 110)), bootstrap_seed=20261123, repeats=10000,
                primary_requests_checked=len(sources), primary_sources_sha256=digest(sources), checks=checks,
                interpretation='Loss difference intervals reproduce but are wider than +/-0.00005; '
                'insufficient precision of equivalence, not proof of nonstationarity or inadmissibility.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--key', default='r0.10_F30_B000')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.resolve().is_relative_to(a.root.resolve()):
        p.error('output must be outside immutable checkpoint')
    result = explain(a.root, a.key)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'primary_sources'}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
