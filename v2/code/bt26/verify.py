"""Checker independent of the scheduler; structural input validation is shared.

Numerical block aggregates and candidate sets are rederived from raw source
records, not trusted from the scheduler's cached Model fields. This is not a
claim of an independently validated physical model.
"""
from collections import defaultdict
from fractions import Fraction as F
import hashlib
import json


def source_aggregates(model):
    """Rederive quantities without make_model(), scheduler, or its aggregates."""
    src = model.source
    ops = {op['id']: op for op in src['operations']}
    devices = {d['id']: d for d in src['devices']}
    members = {b['id']: b['operations'] for b in src['blocks']}
    owner = {v: b for b, vv in members.items() for v in vv}
    memory = {b: sum(int(F(str(ops[v]['memory_bytes']))) for v in vv) for b, vv in members.items()}
    durations, candidates = {}, {}
    for b, vv in members.items():
        candidates[b] = []
        for d, dev in sorted(devices.items()):
            valid = (dev['layer'] in ('edge', 'fog') and dev.get('available', True)
                     and memory[b] <= int(F(str(dev['memory_bytes']))))
            for v in vv:
                op = ops[v]
                valid = valid and (d in op.get('allowed_devices', devices)
                    and set(op.get('requires', [])) <= set(dev.get('features', []))
                    and op.get('duration_s', {}).get(d) is not None)
            if valid:
                durations[b, d] = sum((F(str(ops[v]['duration_s'][d])) for v in vv), F(0))
                candidates[b].append(d)
        candidates[b] = tuple(candidates[b])
    messages = defaultdict(int)
    for edge in src.get('edges', []):
        a, b = owner[edge['src']], owner[edge['dst']]
        if a != b:
            messages[a, b] += int(F(str(edge['bits'])))
    fingerprint = hashlib.sha256(json.dumps(src, sort_keys=True, separators=(',', ':'),
                                            ensure_ascii=False).encode()).hexdigest()
    return memory, durations, candidates, dict(messages), fingerprint

def verify_plan(model,plan):
    errors=[]
    try:
        block_memory, durations, candidates, messages, source_fingerprint = source_aggregates(model)
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return ('source_aggregate_error',)
    if source_fingerprint != model.fingerprint:
        errors.append('source_snapshot_mismatch')
    for name, raw, cached in [('memory',block_memory,model.memory),
                             ('duration',durations,model.duration),
                             ('candidates',candidates,model.candidates),
                             ('messages',messages,model.messages)]:
        if raw != cached:errors.append('model_aggregate:'+name)
    if plan.fingerprint!=model.fingerprint:errors.append('snapshot_mismatch')
    assignments=dict(plan.assignment);runs={r.block:r for r in plan.runs}
    if len(assignments)!=len(plan.assignment) or set(assignments)!=set(model.blocks):return tuple(errors+['assignment_coverage'])
    if len(runs)!=len(plan.runs) or set(runs)!=set(model.blocks):return tuple(errors+['run_coverage'])
    memory=defaultdict(int);reservations=defaultdict(list)
    for r,xs in model.busy.items():
        for a,b in xs:reservations[r].append((a,b,'external'))
    for b in model.blocks:
        d=assignments[b];run=runs[b]
        if d not in candidates[b] or run.device!=d:errors.append('incompatible:'+b);continue
        if run.start<max(model.launch,model.release[b]) or run.end<run.start:errors.append('release:'+b)
        if run.end-run.start!=durations[b,d]:errors.append('duration:'+b)
        memory[d]+=block_memory[b]
        if run.end>run.start:reservations['cpu:'+d].append((run.start,run.end,'block:'+b))
    for d,total in memory.items():
        if total>model.devices[d].memory:errors.append('memory:'+d)
    byedge={(t.src,t.dst):t for t in plan.transfers}
    if len(byedge)!=len(plan.transfers) or set(byedge)!=set(messages):return tuple(errors+['message_coverage'])
    for (a,b),bits in messages.items():
        t=byedge[a,b]
        if t.bits!=bits:errors.append('message_size:'+a+'->'+b)
        src,dst=assignments[a],assignments[b];ready=runs[a].end;current=src;visited={src}
        if src==dst and t.hops:errors.append('nonempty_local_route')
        if src!=dst and not t.hops:errors.append('missing_route')
        for hop in t.hops:
            link=model.links.get(hop.link)
            if link is None or link.src!=current:errors.append('route_continuity');break
            if not link.available or link.bps<=0 or not model.devices[link.dst].available:errors.append('route_unavailable');break
            if link.dst in visited:errors.append('cyclic_route')
            visited.add(link.dst)
            if hop.start<ready or hop.start<0:errors.append('message_readiness')
            if hop.end-hop.start!=F(bits)/link.bps:errors.append('serialization_duration')
            if hop.arrival!=hop.end+link.latency:errors.append('propagation_delay')
            if hop.end>hop.start:
                for resource in link.resources:reservations[resource].append((hop.start,hop.end,'message:'+a+'->'+b))
            current,ready=link.dst,hop.arrival
        if current!=dst:errors.append('route_destination')
        if t.arrival!=ready:errors.append('arrival_mismatch')
        if runs[b].start<t.arrival:errors.append('precedence:'+a+'->'+b)
    for resource,intervals in reservations.items():
        ordered=sorted(intervals)
        for i in range(1,len(ordered)):
            if ordered[i][0]<ordered[i-1][1]:errors.append('resource_conflict:'+resource)
    if plan.makespan!=max(r.end for r in runs.values()):errors.append('makespan_mismatch')
    if plan.makespan>model.deadline:errors.append('deadline')
    return tuple(sorted(set(errors)))
