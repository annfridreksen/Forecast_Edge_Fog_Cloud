"""Reassemble the exact published frozen scientific ZIP; no authentication."""
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=Path('.'))
    p.add_argument('--revision',help='Exact published Git commit; optional when parts are already local')
    p.add_argument('--output',type=Path,default=Path('frozen131.zip'))
    a=p.parse_args();a.directory.mkdir(parents=True,exist_ok=True)
    base=f'https://raw.githubusercontent.com/annfridreksen/Forecast_Edge_Fog_Cloud/{a.revision}/deliverables/r15/'
    def fetch(name):
        with urllib.request.urlopen(base+name,timeout=180) as src,(a.directory/name).open('wb') as dst:
            while block:=src.read(1<<20):dst.write(block)
    manifest=a.directory/'data-parts.json'
    if a.revision and not manifest.exists():fetch('data-parts.json')
    obj=json.loads(manifest.read_text());temporary=a.output.with_name(a.output.name+'.partial')
    with temporary.open('wb') as out:
        for item in obj['parts']:
            path=a.directory/item['name']
            if a.revision and not path.exists():fetch(item['name'])
            if path.stat().st_size!=item['size'] or sha(path)!=item['sha256']:raise ValueError('Part mismatch: '+path.name)
            with path.open('rb') as src:
                while block:=src.read(1<<20):out.write(block)
    if temporary.stat().st_size!=obj['size'] or sha(temporary)!=obj['sha256']:raise ValueError('Complete ZIP mismatch')
    temporary.replace(a.output)
    print('Verified exact frozen archive:',a.output,obj['sha256'])

if __name__=='__main__':main()
