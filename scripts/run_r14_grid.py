"""Run/resume R1.4 without duplicate samples. No training, forecasts or PDF."""
import argparse
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from efc.grid import GridRunner

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', default='results/r14/grid')
    p.add_argument('--wall-seconds', type=float, default=1200)
    p.add_argument('--max-expected-events', type=int, default=1_000_000,
                   help='resource ceiling, not a scientific change; blocked cells stay unresolved')
    p.add_argument('--confirm', action='store_true',
                   help='only after ALL map cells are resolved and ALL candidates are frozen')
    args = p.parse_args()
    if not 0 < args.wall_seconds <= 18000 or args.max_expected_events < 350000:
        p.error('positive time budget <=18000 s; event ceiling >=350000')
    out = GridRunner(args.out, wall_seconds=args.wall_seconds,
                     max_expected_events=args.max_expected_events).run(confirm=args.confirm)
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    # A budget pause is saved, not interpreted as a complete scientific map.
    return 1 if out['errors'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
