"""Primary-observation adapter: same event kernel and same cohort definitions.

Adds stage/occupancy/window summaries for provenance. No new queueing logic,
prediction or alternative statistical method. Cache schema has its own hash.
"""
from dataclasses import replace
from pathlib import Path
import hashlib
from .pilot import KernelSampler, Observation, _digest
from .statistics import extract_cohort

class PrimarySampler(KernelSampler):
    def __init__(self, config):
        super().__init__(config)
        self.config_id = _digest(dict(kernel_config_id=self.config_id,
            recording_adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))

    def __call__(self, seed, warmup, observe, guard):
        from .stationary import stationary_run
        row, result = stationary_run(replace(self.config,seed=seed),
            warmup,observe,guard,return_details=True,compact=True,record_queue=False)
        w=row['window_ticks'];lo,hi,stop=w['start'],w['end'],w['guard_end']
        mid=(lo+hi)//2
        provenance=dict(config_id=self.config_id,window_ticks=w,
            workload_sha256=row['workload_sha256'],kernel=row['kernel'],
            primary_summary=row,record_schema='R1.4-primary-1')
        return Observation(extract_cohort(seed,result,(lo,hi,stop)),
            extract_cohort(seed,result,(lo,mid,stop)),
            extract_cohort(seed,result,(mid,hi,stop)),provenance)
