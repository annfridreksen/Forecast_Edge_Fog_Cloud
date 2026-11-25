"""Configuration-independent exogenous messages (R1.4 TASK 3/5.3).

Uniform sensor IDs precede the assignment sensor % n_fog. Every message has
potential services, including messages later lost. Independent RNG streams
make prefixes stable when a fixed-time guard is extended. This changes the
legacy zone-first generator: its cached experiments are not R1.4 results.
"""
from dataclasses import dataclass, fields
import hashlib
import json
import random
from .timebase import seconds_to_ticks, milliseconds_to_ticks, split_ticks

GENERATOR_VERSION = 'r14-uniform-sensors-v1'
SOURCE_FIELDS = ('n_edge', 'arrival_rate_s', 'mobile_fraction', 'edge_fixed_ms',
                 'edge_mobile_ms', 'edge_processing_share', 'fog_service_ms',
                 'fog_cloud_ms', 'cloud_service_ms', 'seed')


def source_signature(config):
    if config.fog_weights is not None:
        raise ValueError('R1.4 uses uniform sensors; legacy fog_weights are not a paired workload')
    return json.dumps({k: getattr(config, k) for k in SOURCE_FIELDS},
                      sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True, slots=True)
class InputEvent:
    event_id: int
    release_tick: int
    sensor: int
    mobile: bool
    edge_service_tick: int
    ef_service_tick: int
    fog_service_tick: int
    fc_service_tick: int
    cloud_service_tick: int

    def record(self):
        return {name: getattr(self, name) for name in INPUT_FIELDS}


INPUT_FIELDS = tuple(f.name for f in fields(InputEvent))


@dataclass(frozen=True, slots=True)
class Workload:
    events: tuple[InputEvent, ...]
    source_signature: str
    horizon_tick: int | None = None

    def validate_for(self, config):
        if self.source_signature != source_signature(config):
            raise ValueError('source profile/seed mismatch; cannot reuse this workload')
        if not isinstance(self.events, tuple):
            raise ValueError('events must be an immutable tuple')
        if self.horizon_tick is not None and (type(self.horizon_tick) is not int or self.horizon_tick <= 0):
            raise ValueError('invalid source horizon')
        previous = -1
        types = {}
        for i, e in enumerate(self.events):
            if not isinstance(e, InputEvent) or type(e.mobile) is not bool:
                raise ValueError('invalid input event')
            for name in INPUT_FIELDS:
                if name != 'mobile' and (type(getattr(e, name)) is not int or getattr(e, name) < 0):
                    raise ValueError('event integers must be nonnegative')
            if e.event_id != i or e.release_tick < previous or e.sensor >= config.n_edge:
                raise ValueError('event IDs/order/sensor out of contract')
            if self.horizon_tick is not None and e.release_tick >= self.horizon_tick:
                raise ValueError('event outside half-open generation horizon')
            if e.sensor in types and types[e.sensor] != e.mobile:
                raise ValueError('sensor type changed within workload')
            types[e.sensor] = e.mobile
            previous = e.release_tick

    def metadata(self):
        header = {'generator': GENERATOR_VERSION, 'source': json.loads(self.source_signature),
                  'horizon_tick': self.horizon_tick, 'events': len(self.events)}
        h = hashlib.sha256(json.dumps(header, sort_keys=True, separators=(',', ':')).encode())
        for e in self.events:
            h.update(b'\n' + json.dumps(e.record(), sort_keys=True, separators=(',', ':')).encode())
        return {**header, 'sha256': h.hexdigest(), 'assignment': 'sensor modulo n_fog',
                'potential_services_include_dropped': True}


def generate_workload(config, arrivals_s=None, *, stop_s=None):
    """Either n_tasks, explicit n_tasks releases, or Poisson input on [0,stop).

    stop_s is fixed BEFORE observing the process; n_tasks is ignored only in
    this fixed-horizon mode. Primitives are rounded once to the approved clock.
    No Fog/Cloud count or buffer is read to generate messages or durations.
    """
    signature = source_signature(config)
    if arrivals_s is not None and stop_s is not None:
        raise ValueError('explicit arrivals and stop_s are mutually exclusive')
    horizon = seconds_to_ticks(stop_s) if stop_s is not None else None
    if horizon is not None and horizon <= 0:
        raise ValueError('positive generation horizon required')
    ra = random.Random(config.seed + 101)
    rs = random.Random(config.seed + 307)
    rt = random.Random(config.seed + 401)
    rd = random.Random(config.seed + 503)
    if arrivals_s is None:
        releases, now = [], 0.
        while horizon is not None or len(releases) < config.n_tasks:
            now += ra.expovariate(config.arrival_rate_s)
            tick = seconds_to_ticks(now)
            if horizon is not None and tick >= horizon:
                break
            releases.append(tick)
    else:
        releases = [seconds_to_ticks(t) for t in arrivals_s]
        if len(releases) != config.n_tasks or releases != sorted(releases):
            raise ValueError('arrivals must be ordered and match n_tasks')
    mobile = [rt.random() < config.mobile_fraction for _ in range(config.n_edge)]
    events = []
    for i, tick in enumerate(releases):
        sensor = rs.randrange(config.n_edge)
        combined = milliseconds_to_ticks(rd.uniform(
            *(config.edge_mobile_ms if mobile[sensor] else config.edge_fixed_ms)))
        ed, ef = split_ticks(combined, config.edge_processing_share)
        fs = milliseconds_to_ticks(rd.uniform(*config.fog_service_ms))
        fc = milliseconds_to_ticks(rd.uniform(*config.fog_cloud_ms))
        cs = milliseconds_to_ticks(rd.uniform(*config.cloud_service_ms))
        events.append(InputEvent(i, tick, sensor, mobile[sensor], ed, ef, fs, fc, cs))
    result = Workload(tuple(events), signature, horizon)
    result.validate_for(config)
    return result
