"""One isolated RESOURCE measurement at approved W8000/T4000/G1000.

No scientific cache, grid, candidate search, or Actions are changed. This
is a resource probe, not acceptance of any R1.4 configuration.
"""
from argparse import ArgumentParser
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import platform
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from efc.grid import atomic_json
from efc.primary import PrimarySampler
from efc.stationary import scenarios

SEED, W, T, G = 100, 8000, 4000, 1000
LIMIT = 4 * 1024**3


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='new JSON outside existing scientific checkpoint')
    parser.add_argument('--check-only', action='store_true',
                        help='show exact request without computation')
    args = parser.parse_args()
    config = next(c for _, name, c in scenarios() if name == 'rho_0.10_fog_30_B_0')
    sample = PrimarySampler(config)
    record = dict(status='PLANNED',
                  scope='isolated engineering resource probe, NOT R1.4 cell acceptance',
                  execution='local Python (not Colab, not Actions)',
                  config_id=sample.config_id, configuration=asdict(config),
                  seed=SEED, warmup=W, observe=T, guard=G,
                  expected_events=50*(W+T+G),
                  address_space_limit_bytes=LIMIT,
                  python=platform.python_version())
    if args.check_only:
        print({k:v for k,v in record.items() if k != 'configuration'})
        return
    if args.output.exists():
        raise FileExistsError('no duplicate measurement; output already exists: '+str(args.output))
    if args.output.resolve().is_relative_to(ROOT.resolve()/'results'/'r14'/'night-map'):
        raise ValueError('resource probe must not modify scientific checkpoint')
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))
    record['started_utc'] = datetime.now(timezone.utc).isoformat()
    record['status'] = 'RUNNING'
    atomic_json(args.output, record)
    t0 = time.perf_counter()
    try:
        result = sample(SEED, W, T, G)
        record.update(status='PASS', observed_arrivals=result.full.arrivals,
                      observed_dropped=result.full.dropped,
                      observed_unfinished=result.full.unfinished,
                      completed_latency_count=len(result.full.latency_ticks),
                      workload_sha256=result.provenance['workload_sha256'])
    except BaseException as exc:
        record.update(status='FAILED', error=repr(exc))
        raise
    finally:
        record['wall_seconds'] = time.perf_counter()-t0
        record['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_json(args.output, record)
        print({k:v for k,v in record.items() if k != 'configuration'}, flush=True)


if __name__ == '__main__':
    main()
