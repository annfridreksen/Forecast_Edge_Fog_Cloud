"""Explicit, restartable migration of PILOT-ONLY observations to new code IDs.

Does not recompute a seed, rewrite the source, carry over scientific decisions,
or bypass frozen-confirmation rules. Only the reviewed b3de9c52 storage change
is eligible. Data values are preserved; new provenance names the old digest.
"""
import argparse
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from efc.grid import GridRunner, canonical, digest, read_json, atomic_json, exclusive
from efc.pilot import Observation, _digest
from efc.primary import PrimarySampler
from efc.statistics import Cohort

OLD_FILES=('model.py','timebase.py','workload.py','stationary.py','statistics.py','pilot.py')


def compatible_certificate(path):
    c=read_json(path)
    if (c.get('schema')!='r14-storage-compatibility-v1' or c.get('status')!='PASS'
        or c.get('reference_commit')!='b3de9c52e029a967b03c3a93cc60230b82c83e3b'
        or not c.get('event_transition_AST_equal') or c.get('number_of_cases',0)<45):
        raise ValueError('reviewed storage evidence required')
    if set(c['new_sha256'])!=set(OLD_FILES)|{'records.py','primary.py'}:
        raise ValueError('incomplete code fingerprint')
    for name,h in c['new_sha256'].items():
        if hashlib.sha256((ROOT/'efc'/name).read_bytes()).hexdigest()!=h:
            raise ValueError('code changed since storage evidence: '+name)
    for name in ('timebase.py','workload.py','statistics.py'):
        if c['new_sha256'][name]!=c['old_sha256'][name]:
            raise ValueError('definitions changed; this migration is not applicable')
    return c


def old_id(config, certificate):
    d=dict(config)
    for key in ('seed','n_tasks'):d.pop(key)
    kid=_digest(dict(config=d,code_sha256={f:certificate['old_sha256'][f] for f in OLD_FILES}))
    return _digest(dict(kernel_config_id=kid,recording_adapter_sha256=certificate['old_sha256']['primary.py']))


def migrate(source, target, certificate_path):
    source,target=Path(source).resolve(),Path(target).resolve()
    if source==target or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('source and target must be separate trees')
    cert=compatible_certificate(certificate_path)
    manifest=read_json(source/'manifest.json')
    if (source/'candidates.json').exists() or any((source/'cells').glob('*/main.json')) or any((source/'cells').glob('*/confirmation.json')):
        raise ValueError('only pilot-only checkpoint migration is supported')
    for state in (source/'cells').glob('*/cell.json'):
        if read_json(state).get('main_seeds_completed',0):
            raise ValueError('cannot migrate evaluated candidates')
    runner=GridRunner(target,factory=PrimarySampler)
    new={r['key']:r for r in runner.catalog};old={r['key']:r for r in manifest['catalog']}
    if len(old)!=len(manifest['catalog']) or set(old)!=set(new):raise ValueError('catalog mismatch')
    by_id={}
    for key,row in old.items():
        if row['config']!=json.loads(canonical(new[key]['config'])) or row['config_id']!=old_id(row['config'],cert):
            raise ValueError('unrecognized source code/configuration')
        by_id[row['config_id']]=new[key]['config_id']
    source_id=digest(manifest);count=0;reused=0;imports=[]
    with exclusive(target):
        runner._bind()
        registry=target/'storage-migration.json'
        identity=dict(source_manifest_sha256=source_id,certificate_sha256=digest(cert))
        if registry.exists() and any(read_json(registry).get(k)!=v for k,v in identity.items()):
            raise ValueError('different migration already bound to target')
        atomic_json(registry,{**identity,'status':'RUNNING','scientific_replicates_executed':0})
        for path in sorted((source/'observations').glob('*/*.json.gz')):
            data=json.loads(gzip.decompress(path.read_bytes()))
            req,obj=data['request'],data['observation']
            if (path.name!=digest(req)+'.json.gz' or path.parent.name!=req['config_id']
                or data['sha256']!=digest(obj) or req['config_id'] not in by_id):
                raise ValueError('source observation checksum/identity mismatch')
            if req['seed'] not in range(100,110):raise ValueError('not a pilot seed')
            if req['warmup'] not in (2000,4000,8000,16000) or req['observe'] not in (4000,8000,16000,32000) or req['guard'] not in (1000,2000,4000,8000,16000):
                raise ValueError('nonprotocol observation window')
            obs=Observation(*(Cohort(**obj[k]) for k in ('full','first','second')),obj['provenance'])
            if obs.full.seed!=req['seed'] or obs.provenance['config_id']!=req['config_id']:
                raise ValueError('source provenance mismatch')
            new_id=by_id[req['config_id']]
            new_obj={**obj,'provenance':{**obj['provenance'],'config_id':new_id,
                'storage_migration':dict(old_config_id=req['config_id'],old_observation_sha256=data['sha256'],
                                         source_manifest_sha256=source_id)}}
            new_req={**req,'config_id':new_id}
            saved=dict(request=new_req,observation=new_obj,sha256=digest(new_obj))
            dest=target/'observations'/new_id/(digest(new_req)+'.json.gz')
            if dest.exists():
                if json.loads(gzip.decompress(dest.read_bytes()))!=saved:raise ValueError('target conflicts with migration')
                reused+=1
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                tmp=dest.with_suffix('.tmp');tmp.write_bytes(gzip.compress(canonical(saved),mtime=0));tmp.replace(dest)
            count+=1
            imports.append(dict(old_request_sha256=digest(req),old_observation_sha256=data['sha256'],
                                new_request_sha256=digest(new_req),new_observation_sha256=saved['sha256']))
        report={**identity,'status':'COMPLETE','source_changed':False,
                'imported_primary_requests':count,'scientific_replicates_executed':0,
                'decisions_imported':0,'imports':imports}
        atomic_json(registry,report)
        # Do not overwrite a map that has progressed since a previous import.
        if not (target/'map.json').exists():atomic_json(target/'map.json',runner.map_data())
    return {**report,'already_present_this_call':reused}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--target',type=Path,required=True)
    p.add_argument('--certificate',type=Path,default=ROOT/'results/r14/compact_storage_compatibility.json')
    a=p.parse_args();r=migrate(a.source,a.target,a.certificate)
    print(json.dumps({k:v for k,v in r.items() if k!='imports'},indent=2))

if __name__=='__main__':main()
