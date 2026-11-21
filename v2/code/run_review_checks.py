"""Post-review synthetic diagnostics; fixed deadlines, no parameter tuning.

All input changes relative to run_study are explicit below. Reports are saved
before a nonzero exit. These are finite regression checks, not a new theorem.
"""
from __future__ import annotations
from pathlib import Path
from itertools import product, permutations
from collections import Counter
from fractions import Fraction as F
import argparse
import copy
import csv
import json
import statistics

from bt26 import make_model, search, reference, prepare_forecast
from bt26.scheduler import build_plan, NoSchedule, plan_to_dict
from bt26.verify import verify_plan
from bt26.search import command_vector, optimistic_bound
from run_study import synthetic, dump, StudyVerificationError


def memory_ok(model, values):
    used = Counter()
    for b, d in zip(model.blocks, values):
        used[d] += model.memory[b]
    return all(n <= model.devices[d].memory for d, n in used.items())


def check_stop_coverage(model, forecast, result, audit):
    """Check the actual remaining frontier against all small completions."""
    commands, _ = prepare_forecast(model, forecast)
    checked = set(audit['checked_assignments'])
    failures = []
    for values in product(*(model.candidates[b] for b in model.blocks)):
        if not memory_ok(model, values) or values in checked:
            continue
        if result.certified and result.plan is None:
            failures.append('unvisited_after_no_plan')
            continue
        covers = [node for node in audit['frontier']
                  if values[:len(node['prefix'])] == node['prefix']]
        if not covers:
            failures.append('uncovered_completion')
        if commands is not None and result.method == 'P':
            vector = command_vector(dict(zip(model.blocks, values)), commands)
            if not any(node['bound'] <= vector for node in covers):
                failures.append('invalid_frontier_lower_bound')
            if result.certified and result.plan is not None:
                best = command_vector(dict(result.plan.assignment), commands)
                if vector <= best:
                    failures.append('unvisited_not_worse_vector_at_certified_stop')
    return sorted(set(failures))


def csvsave(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rename_devices(problem, forecast, new_labels):
    """One-to-one device-ID permutation; physical links keep their own IDs."""
    d, f = copy.deepcopy(problem), copy.deepcopy(forecast)
    old_labels = sorted(x['id'] for x in d['devices'])
    names = dict(zip(old_labels, new_labels))
    for dev in d['devices']:
        dev['id'] = names[dev['id']]
    for op in d['operations']:
        op['duration_s'] = {names[k]: v for k, v in op['duration_s'].items()}
        if 'allowed_devices' in op:
            op['allowed_devices'] = [names[x] for x in op['allowed_devices']]
    for link in d['links']:
        link['src'], link['dst'] = names[link['src']], names[link['dst']]
    d['busy'] = {('cpu:' + names[k[4:]] if k.startswith('cpu:') else k): v
                 for k, v in d.get('busy', {}).items()}
    if d.get('previous'):
        d['previous'] = {b: names[v] for b, v in d['previous'].items()}
    f['commands'] = {names[k]: v for k, v in f['commands'].items()}
    return d, f


def review_checks(out, seeds=80, permutation_seeds=60):
    out.mkdir(parents=True, exist_ok=True)
    failures, rows, traces, bound_rows = [], [], [], []
    # 30 and 35 ms were fixed before these runs, per the review proposal.
    # 60 ms is retained as a nonbinding reference, not silently replaced.
    for deadline in ('0.060', '0.030', '0.035'):
        for seed in range(seeds):
            d, f, _ = synthetic(seed)
            d['deadline_s'] = deadline
            model = make_model(d)
            audit = {}
            p = search(model, f, 'P', audit=audit)
            ref, total, feasible = reference(model, f, 'P')
            equal = p.plan == ref
            coverage = check_stop_coverage(model, f, p, audit)
            if not equal or coverage:
                failures.append({'seed': seed, 'deadline_s': deadline,
                                 'matches': equal, 'coverage_errors': coverage})
            # Count all deadline rejections in the fixed builder class, not
            # just those visited by P. Memory violations are counted separately.
            deadline_rejected, max_ms, prefiltered = 0, 0.0, 0
            for vals in product(*(model.candidates[b] for b in model.blocks)):
                if not memory_ok(model, vals):
                    prefiltered += 1
                    continue
                plan = build_plan(model, dict(zip(model.blocks, vals)))
                max_ms = max(max_ms, float(plan.makespan * 1000))
                deadline_rejected += 'deadline' in verify_plan(model, plan)
            rows.append({'seed': seed, 'deadline_s': deadline,
                         'requested_method': 'P', 'effective_method': p.method,
                         'forecast_status': p.forecast_status,
                         'matches_reference': equal, 'coverage_ok': not coverage,
                         'status': p.status, 'checks': p.stats['complete_checked'],
                         'reference_assignments': total, 'reference_feasible': feasible,
                         'memory_rejected_assignments': prefiltered,
                         'deadline_rejected_reference': deadline_rejected,
                         'deadline_rejected_P': p.rejected.get('deadline', 0),
                         'max_planned_ms_over_memory_feasible': max_ms,
                         'selected_ms': float(p.plan.makespan * 1000) if p.plan else None,
                         'plan_id': ','.join(p.plan.identifier) if p.plan else ''})
            # Full inputs, actual frontier and checks permit an external replay.
            traces.append({'seed': seed, 'deadline_s': deadline, 'problem': d,
                           'forecast': f, 'audit': audit, 'result': p.to_dict(),
                           'reference_plan': plan_to_dict(ref)})
    for seed in range(seeds):
        d, f, _ = synthetic(seed)
        model = make_model(d)
        commands, reason = prepare_forecast(model, f)
        count, errors = 0, 0
        if commands is not None:
            minima = tuple(min(commands[x] for x in model.candidates[b]) for b in model.blocks)
            for vals in product(*(model.candidates[b] for b in model.blocks)):
                vector = command_vector(dict(zip(model.blocks, vals)), commands)
                for length in range(len(vals) + 1):
                    bound = optimistic_bound(model, commands, vals[:length], minima)
                    count += 1
                    errors += not bound <= vector
        bound_rows.append({'seed': seed, 'forecast_status': reason,
                           'tested_prefix_completion_pairs': count, 'failures': errors})
        if errors:
            failures.append({'seed': seed, 'bound_errors': errors})
    permutation_rows = []
    for seed in range(permutation_seeds):
        d, f, _ = synthetic(seed)
        for index, labels in enumerate(permutations(('E', 'F1', 'F2'))):
            dd, ff = rename_devices(d, f, labels)
            model = make_model(dd)
            full = search(model, ff, 'P')
            for cap in (1, 4, 16):
                for mode in ('P', 'D'):
                    result = search(model, ff, mode, max_checks=cap, early_stop=False)
                    permutation_rows.append({'seed': seed, 'permutation': index,
                        'mapping_E_F1_F2': ','.join(labels), 'budget': cap,
                        'requested_method': mode, 'effective_method': result.method,
                        'forecast_status': result.forecast_status,
                        'matches_full_choice': result.plan == full.plan,
                        'checks': result.stats['complete_checked'],
                        'full_P_checks': full.stats['complete_checked'],
                        'plan_found': result.plan is not None})
    csvsave(out / 'active_deadline_checks.csv', rows)
    csvsave(out / 'bound_code_checks.csv', bound_rows)
    csvsave(out / 'device_id_sensitivity.csv', permutation_rows)
    # Fractions in audits are exported as exact strings.
    (out / 'stop_coverage_traces.json').write_text(
        json.dumps(traces, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    deadline_summary = {}
    for deadline in ('0.060', '0.030', '0.035'):
        part = [x for x in rows if x['deadline_s'] == deadline]
        deadline_summary[deadline] = {
            'runs': len(part), 'matches_reference': sum(x['matches_reference'] for x in part),
            'coverage_ok': sum(x['coverage_ok'] for x in part),
            'active_forecast_runs': sum(x['effective_method'] == 'P' for x in part),
            'no_plan_runs': sum(x['status'] == 'NO_PLAN_IN_CLASS' for x in part),
            'deadline_rejected_reference': sum(x['deadline_rejected_reference'] for x in part),
            'deadline_rejected_P': sum(x['deadline_rejected_P'] for x in part),
            'mean_checks': statistics.mean(x['checks'] for x in part)}
    sensitivity = {}
    for cap in (1, 4, 16):
        sensitivity[str(cap)] = {}
        for mode in ('P', 'D'):
            part = [x for x in permutation_rows if x['budget'] == cap and x['requested_method'] == mode]
            grouped = [sum(x['matches_full_choice'] for x in part if x['permutation'] == p) for p in range(6)]
            sensitivity[str(cap)][mode] = {'permutations': 6, 'runs_per_permutation': permutation_seeds,
                                         'matches_by_permutation': grouped,
                                         'mean_matches': statistics.mean(grouped)}
    summary = {'data_status': 'SYNTHETIC_POST_REVIEW_DIAGNOSTICS_NOT_NSKF_OR_NEURAL',
               'seed_range': [0, seeds - 1], 'deadlines_s': deadline_summary,
               'bound_pairs_checked': sum(x['tested_prefix_completion_pairs'] for x in bound_rows),
               'bound_failures': sum(x['failures'] for x in bound_rows),
               'device_id_sensitivity': sensitivity, 'verification_failures': failures}
    dump(out / 'review_summary.json', summary)
    print(json.dumps(summary, indent=2))
    if failures:
        raise StudyVerificationError('review checks failed; diagnostics have been saved')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('results/review_checks'))
    parser.add_argument('--seeds', type=int, default=80)
    parser.add_argument('--permutation-seeds', type=int, default=60)
    args = parser.parse_args()
    if args.seeds < 1 or args.permutation_seeds < 1:
        parser.error('seed counts must be positive')
    review_checks(args.out, args.seeds, args.permutation_seeds)
