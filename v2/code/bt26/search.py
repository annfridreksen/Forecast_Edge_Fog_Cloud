"""Ordinal selection with an auditable optimistic-prefix search.

The result is certified only in the finite class defined by the fixed schedule
builder. Clock measurements are elapsed (wall) time, not CPU time.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from collections import Counter
from time import perf_counter
import heapq
import math

from .model import InputError, prepare_forecast
from .scheduler import NoSchedule, build_plan, plan_to_dict
from .verify import verify_plan


@dataclass
class Result:
    status: str
    method: str  # effective mode; retained for compatibility
    forecast_status: str
    plan: object
    certified: bool
    stats: dict
    rejected: dict  # complete-plan failures, not partial-prefix pruning
    requested_method: str = ''

    def to_dict(self):
        return dict(
            status=self.status, requested_method=self.requested_method or self.method,
            effective_method=self.method, method=self.method,
            forecast_status=self.forecast_status, plan=plan_to_dict(self.plan),
            certified=self.certified, stats=self.stats, rejected=self.rejected,
            partial_rejections={'joint_memory': self.stats['memory_pruned']})


def command_vector(assignment, commands):
    return tuple(sorted((commands[d] for _, d in sorted(assignment.items())), reverse=True))


def moves(model, assignment):
    return 0 if model.previous is None else sum(
        assignment[b] != model.previous[b] for b in model.blocks)


def key(model, plan, commands=None):
    assignment = dict(plan.assignment)
    suffix = (plan.makespan, moves(model, assignment), plan.identifier)
    return (command_vector(assignment, commands),) + suffix if commands is not None else suffix


def optimistic_bound(model, commands, prefix, minimum_commands=None):
    """Lower ordinal bound for all completions of a prefix.

    Supplying minima precomputed once per search gives O(r log r) comparisons
    per call. Without them this convenience API also scans candidate sets.
    Joint memory of unassigned blocks is intentionally relaxed.
    """
    if len(prefix) > len(model.blocks):
        raise InputError('prefix longer than partition')
    if minimum_commands is None:
        minimum_commands = tuple(
            min(commands[d] for d in model.candidates[b]) for b in model.blocks)
    if len(minimum_commands) != len(model.blocks):
        raise InputError('minimum command vector has wrong length')
    values = [commands[d] for d in prefix] + list(minimum_commands[len(prefix):])
    return tuple(sorted(values, reverse=True))


def deterministic_result(data):
    """Remove volatile clock measurements from a serialized result.

    Counts, status, full plans, snapshots and diagnostic reasons are retained.
    This is an explicitly deterministic export, not a performance measurement.
    """
    if isinstance(data, dict):
        return {k: deterministic_result(v) for k, v in data.items()
                if not k.endswith('_seconds')}
    if isinstance(data, list):
        return [deterministic_result(v) for v in data]
    return data


def search(model, forecast=None, method='P', *, max_checks=None,
           max_expansions=None, max_seconds=None, early_stop=True, audit=None):
    """P: ordinal criterion/order; D: same criterion, lexicographic ID order;
    B: time criterion, lexicographic ID order. B and D have no bound-based stop.

    Limits are cooperative. `audit`, when supplied as an empty dict, collects
    checked assignments and the remaining frontier for verification, not timing.
    """
    if method not in ('P', 'B', 'D'):
        raise InputError('method must be P/B/D')
    for value in (max_checks, max_expansions):
        if value is not None and (type(value) is not int or value < 0):
            raise InputError('invalid search limit')
    if max_seconds is not None and (not math.isfinite(max_seconds) or max_seconds < 0):
        raise InputError('invalid time budget')
    if audit is not None and (not isinstance(audit, dict) or audit):
        raise InputError('audit must be an empty dict')
    started = perf_counter()
    commands, reason = (prepare_forecast(model, forecast)
                        if method != 'B' else (None, 'not_used'))
    effective = method if commands is not None else 'B'
    stats = dict(expanded=0, enqueued=0, memory_pruned=0, complete_checked=0,
                 feasible=0, peak_frontier=0, schedule_wall_seconds=0.0,
                 verify_wall_seconds=0.0)
    rejected = Counter()
    best = None
    certified = False
    stop = 'exhausted'
    frontier = []
    checked = [] if audit is not None else None

    def finish():
        stats['stop_reason'] = stop
        stats['elapsed_wall_seconds'] = perf_counter() - started
        stats['preparation_and_search_wall_seconds'] = max(
            0.0, stats['elapsed_wall_seconds'] - stats['schedule_wall_seconds']
            - stats['verify_wall_seconds'])
        if audit is not None:
            audit.update(checked_assignments=checked,
                         frontier=[{'bound': lb, 'prefix': prefix}
                                   for lb, prefix in sorted(frontier)],
                         stop_reason=stop,
                         effective_method=effective)
        status = (('FEASIBLE_CERTIFIED' if certified else 'FEASIBLE_LIMITED')
                  if best is not None else
                  ('NO_PLAN_IN_CLASS' if certified else 'SEARCH_LIMIT_NO_PLAN'))
        return Result(status, effective, reason, best, certified, stats,
                      dict(rejected), method)

    if any(not model.candidates[b] for b in model.blocks):
        certified, stop = True, 'empty_candidates'
        rejected['empty_candidates'] = 1
        return finish()

    minima = (tuple(min(commands[d] for d in model.candidates[b]) for b in model.blocks)
              if effective == 'P' else None)

    def bound(prefix):
        return optimistic_bound(model, commands, prefix, minima) if effective == 'P' else ()

    frontier = [(bound(()), ())]
    stats['enqueued'] = 1
    while frontier:
        stats['peak_frontier'] = max(stats['peak_frontier'], len(frontier))
        if (effective == 'P' and early_stop and best is not None
                and frontier[0][0] > key(model, best, commands)[0]):
            certified, stop = True, 'ordinal_bound'
            break
        if max_seconds is not None and perf_counter() - started >= max_seconds:
            stop = 'time_budget'
            break
        if max_expansions is not None and stats['expanded'] >= max_expansions:
            stop = 'expansion_budget'
            break
        lb, prefix = heapq.heappop(frontier)
        stats['expanded'] += 1
        if len(prefix) == len(model.blocks):
            if max_checks is not None and stats['complete_checked'] >= max_checks:
                heapq.heappush(frontier, (lb, prefix))  # preserve audit coverage
                stop = 'check_budget'
                break
            assignment = dict(zip(model.blocks, prefix))
            stats['complete_checked'] += 1
            if checked is not None:
                checked.append(prefix)
            tick = perf_counter()
            try:
                plan = build_plan(model, assignment)
            except NoSchedule as exc:
                stats['schedule_wall_seconds'] += perf_counter() - tick
                rejected[str(exc)] += 1
                continue
            stats['schedule_wall_seconds'] += perf_counter() - tick
            tick = perf_counter()
            violations = verify_plan(model, plan)
            stats['verify_wall_seconds'] += perf_counter() - tick
            if violations:
                rejected.update(violations)
                continue
            stats['feasible'] += 1
            if best is None or key(model, plan, commands) < key(model, best, commands):
                best = plan
            continue
        block = model.blocks[len(prefix)]
        used = Counter()
        for old, device in zip(model.blocks, prefix):
            used[device] += model.memory[old]
        for device in model.candidates[block]:
            # Nonnegative per-block memory makes this pruning monotone.
            if used[device] + model.memory[block] > model.devices[device].memory:
                stats['memory_pruned'] += 1
                continue
            child = prefix + (device,)
            heapq.heappush(frontier, (bound(child), child))
            stats['enqueued'] += 1
    else:
        certified = True
    return finish()


def reference(model, forecast=None, method='P'):
    """Cartesian enumeration with shared preprocessing, builder, key and checker.

    This is a differential oracle for search/pruning, NOT an independently
    implemented physical model, checker, or global scheduling optimizer.
    """
    commands, _ = prepare_forecast(model, forecast) if method != 'B' else (None, 'not_used')
    best, checked, feasible = None, 0, 0
    for values in product(*(model.candidates[b] for b in model.blocks)):
        checked += 1
        try:
            plan = build_plan(model, dict(zip(model.blocks, values)))
        except NoSchedule:
            continue
        if verify_plan(model, plan):
            continue
        feasible += 1
        if best is None or key(model, plan, commands) < key(model, best, commands):
            best = plan
    return best, checked, feasible


def reconsider(model, previous_assignment, forecast=None, old_forecast=None, *,
               allow_preference_change=False, **limits):
    """Pre-start/checkpoint reselection; no live migration or repartition.

    The opt-in policy also permits selection on first availability or loss of
    usable ordinal information. With old_forecast=None this is NOT called an
    established change of historical order. The default always keeps a feasible
    previous assignment. Invalid previous plans force a search regardless.
    """
    if model.previous is None or previous_assignment != model.previous:
        raise InputError('previous assignment contract mismatch')
    old_cmd, _ = prepare_forecast(model, old_forecast)
    new_cmd, _ = prepare_forecast(model, forecast)

    def relation(cmd):
        if cmd is None:
            return None
        ids = sorted(cmd)
        return tuple((a, b, (cmd[a] > cmd[b]) - (cmd[a] < cmd[b])) for a in ids for b in ids)

    try:
        old_plan = build_plan(model, previous_assignment)
        old_ok = not verify_plan(model, old_plan)
    except NoSchedule:
        old_plan, old_ok = None, False
    if old_ok and (not allow_preference_change or relation(old_cmd) == relation(new_cmd)):
        return {'action': 'KEEP', 'plan': plan_to_dict(old_plan),
                'reason': 'feasible_previous_assignment'}
    if not old_ok:
        reason = 'previous_plan_infeasible'
    elif old_cmd is None:
        reason = 'forecast_became_available'
    elif new_cmd is None:
        reason = 'forecast_became_unavailable'
    else:
        reason = 'ordinal_relation_changed'
    result = search(model, forecast, 'P', **limits)
    return {'action': 'RESELECT' if result.plan is not None else 'NO_PLAN',
            'reason': reason, 'search': result.to_dict()}
