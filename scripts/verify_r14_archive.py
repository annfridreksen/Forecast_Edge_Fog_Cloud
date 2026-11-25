"""Verify ZIP bytes and every extracted member before quoting its provenance.

Does not modify the checkpoint, normalize its journals or recalculate a seed.
The GitHub artifact ID is declared metadata; only bytes/hashes are measured.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


def verify_archive(archive, root, *, expected_sha256, artifact_id=None):
    archive,root=Path(archive),Path(root).resolve()
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64:
        raise ValueError('expected SHA-256 is required')
    actual=file_hash(archive)
    if actual!=expected_sha256:
        raise ValueError('source ZIP SHA-256 mismatch')
    members={}
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name=PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or stat.S_ISLNK(item.external_attr>>16):
                raise ValueError('unsafe ZIP member')
            if item.is_dir():continue
            if item.filename in members:raise ValueError('duplicate ZIP member')
            target=root.joinpath(*name.parts)
            if not target.resolve().is_relative_to(root) or target.is_symlink() or not target.is_file():
                raise ValueError('missing/unsafe extracted member: '+item.filename)
            h=hashlib.sha256()
            with z.open(item) as f:
                for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
            expected=h.hexdigest()
            if target.stat().st_size!=item.file_size or file_hash(target)!=expected:
                raise ValueError('extracted bytes differ: '+item.filename)
            members[item.filename]=expected
    return dict(schema='r14-archive-verification-v1',status='VERIFIED_BYTES',
                declared_artifact_id=artifact_id,expected_zip_sha256=expected_sha256,
                measured_zip_sha256=actual,extracted_members_verified=len(members),
                member_sha256=members,read_only=True,scientific_acceptance=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True);p.add_argument('--artifact-id',type=int)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.resolve().is_relative_to(a.root.resolve()):p.error('output must be outside immutable checkpoint')
    result=verify_archive(a.archive,a.root,expected_sha256=a.expected_sha256,artifact_id=a.artifact_id)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('Verified ZIP and',result['extracted_members_verified'],'extracted files; no scientific acceptance.')

if __name__=='__main__':main()
