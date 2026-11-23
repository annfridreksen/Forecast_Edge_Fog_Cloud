"""Publish only this executor's generated R1.5 delivery, with a HEAD lease.
Never changes visibility, protected paths, source branches, or signatures.
The manuscript remains unsubmitted and incomplete in author metadata.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_r15_submission import package_zip,sha,put
REPO='annfridreksen/Forecast_Edge_Fog_Cloud'
BRANCH='night/fefc-v3'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def finalize(out):
    delivery=out/'delivery'; repro=out/'work/reproducibility'
    shutil.copytree(out/'work/submission',repro/'article',dirs_exist_ok=True)
    for f in (ROOT/'v2/code/bt26').glob('*.py'):
        target=repro/'v2/code/bt26'/f.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    shutil.copytree(ROOT/'tests',repro/'tests',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ROOT/'article/tests',repro/'article/tests',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    # The standalone validation imports ROOT/article/r14-values.tex to verify the unchanged raw cell output.
    shutil.copy2(ROOT/'article/r14-values.tex',repro/'article/r14-values.tex')
    shutil.copy2(ROOT/'article/r14-references.tex',repro/'article/r14-references.tex')
    package_zip(repro,delivery/'reproducibility.zip')
    hashes={p.relative_to(delivery).as_posix():sha(p) for p in sorted(delivery.rglob('*')) if p.is_file() and p.name!='SHA256.json'}
    put(delivery/'SHA256.json',hashes)


def publish(out):
    expected=os.environ['GITHUB_SHA'];ref='refs/heads/'+BRANCH
    def remote_head():return git('ls-remote','origin',ref).split()[0]
    if remote_head()!=expected:raise RuntimeError('Branch changed; keep artifact, do not publish or overwrite another owner')
    # Anonymous repository read verifies that no visibility change is required.
    request=urllib.request.Request(f'https://api.github.com/repos/{REPO}',headers={'User-Agent':'FEFC-R15-public-check'})
    with urllib.request.urlopen(request,timeout=30) as f:meta=json.load(f)
    if meta.get('private') or meta.get('visibility')!='public':
        raise RuntimeError('Repository is not already public; automatic visibility change prohibited')
    target=ROOT/'deliverables/r15';target.mkdir(parents=True,exist_ok=True)
    for p in sorted((out/'delivery').rglob('*')):
        if not p.is_file():continue
        if p.stat().st_size>=100*1024*1024:raise ValueError('Delivery item exceeds normal GitHub file limit')
        dest=target/p.relative_to(out/'delivery');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    git('config','user.name','FEFC build executor')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--','deliverables/r15')
    staged=git('diff','--cached','--name-only').splitlines()
    if not staged or any(not p.startswith('deliverables/r15/') for p in staged):
        raise RuntimeError('Only the generated delivery directory may be staged')
    if remote_head()!=expected:raise RuntimeError('HEAD lease lost before publication')
    git('commit','-m','Issue #4 п.10–12 / R1.5 C: сохранить собранный комплект и синтетические первичные данные')
    published=git('rev-parse','HEAD')
    git('push','origin','HEAD:'+ref)
    if remote_head()!=published:raise RuntimeError('Published remote SHA differs')
    checks=[]
    required=['article.pdf','submission.zip','reproducibility.zip','difference.pdf','data-parts.json']
    required += [p['name'] for p in json.loads((target/'data-parts.json').read_text())['parts']]
    for name in required:
        url=f'https://raw.githubusercontent.com/{REPO}/{published}/deliverables/r15/{name}'
        digest=hashlib.sha256();size=0
        req=urllib.request.Request(url,headers={'User-Agent':'FEFC-R15-anonymous-download'})
        with urllib.request.urlopen(req,timeout=180) as f:
            while block:=f.read(1<<20):digest.update(block);size+=len(block)
        if digest.hexdigest()!=sha(target/name):raise ValueError('Anonymous download differs: '+name)
        checks.append({'file':name,'url':url,'sha256':digest.hexdigest(),'bytes':size,'authenticated':False})
    result={'status':'PUBLIC_DOWNLOAD_VERIFIED','source_sha':expected,'delivery_sha':published,
            'branch':BRANCH,'checks':checks,'visibility_changed':False,'article_sent':False,
            'ready_to_submit':False,'reason':'Author metadata, permissions and independent acceptance remain open.'}
    put(out/'publication.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();finalize(args.out.resolve());publish(args.out.resolve())
